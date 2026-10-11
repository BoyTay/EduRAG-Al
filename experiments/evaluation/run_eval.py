"""Đánh giá EduRAG theo nội dung 6 của đề tài.

Đo bốn nhóm chỉ số trên bộ câu hỏi kiểm thử:
  1. Độ liên quan: bao phủ ý bắt buộc, điểm truy xuất, không chứa chi tiết cấm.
  2. Tính đúng nguồn: đúng tài liệu, đúng trang chính, không hiện nguồn khi từ chối.
  3. Thời gian phản hồi: p50, p95, lớn nhất.
  4. Tài nguyên: RAM tiến trình backend, RAM Ollama, VRAM GPU (nếu có).

Dùng đúng RAGChain và cấu hình của ứng dụng (không thay model nếu không truyền --model).

Chạy (từ thư mục gốc dự án):
    $env:PYTHONPATH="backend;experiments/llm_benchmark"
    python experiments/evaluation/run_eval.py
    python experiments/evaluation/run_eval.py --repeats 3 --case-id S-07
    python experiments/evaluation/run_eval.py --report-only experiments/evaluation/results_eval.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import shutil
import statistics
import subprocess
import threading
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:  # psutil là tùy chọn; thiếu thì bỏ qua đo RAM
    psutil = None

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = [
    HERE / "cases_eval.json",
    HERE.parent / "llm_benchmark" / "cases.json",
]
REFUSAL_MARKERS = (
    "khong tim thay thong tin phu hop",
    "tai lieu khong co thong tin",
    "khong co thong tin trong tai lieu",
)


def fold(value: str) -> str:
    text = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def coverage(answer: str, groups: list[list[str]]) -> dict[str, Any]:
    if not groups:
        return {"matched": 0, "total": 0, "ratio": 1.0, "missing": []}
    folded = fold(answer)
    missing = [g for g in groups if not any(fold(t) in folded for t in g)]
    return {"matched": len(groups) - len(missing), "total": len(groups),
            "ratio": round((len(groups) - len(missing)) / len(groups), 4), "missing": missing}


def forbidden(answer: str, groups: list[list[str]]) -> dict[str, Any]:
    folded = fold(answer)
    found = [g for g in groups if any(fold(t) in folded for t in g)]
    return {"pass": not found, "found": found}


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100
    low, high = math.floor(rank), math.ceil(rank)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (rank - low), 3)


# ---------------------------------------------------------------- tài nguyên
def _gpu_used_mb() -> float | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=False).stdout
        return float(sum(float(x) for x in out.split()))
    except Exception:  # noqa: BLE001
        return None


def _ollama_rss_mb() -> float | None:
    if psutil is None:
        return None
    total, found = 0, False
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            if "ollama" in (proc.info["name"] or "").lower():
                total += proc.info["memory_info"].rss
                found = True
        except Exception:  # noqa: BLE001
            continue
    return round(total / 2**20, 1) if found else None


class ResourceSampler:
    """Lấy mẫu RAM/VRAM nền; trả về đỉnh trong khoảng start()..stop()."""

    def __init__(self, interval: float = 0.5) -> None:
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.peak: dict[str, float | None] = {}

    def _sample(self) -> None:
        values = {
            "backend_rss_mb": round(psutil.Process().memory_info().rss / 2**20, 1) if psutil else None,
            "ollama_rss_mb": _ollama_rss_mb(),
            "gpu_used_mb": _gpu_used_mb(),
        }
        for key, val in values.items():
            if val is not None and (self.peak.get(key) is None or val > self.peak[key]):
                self.peak[key] = val

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._sample()
            self._stop.wait(self.interval)

    def start(self) -> None:
        self.peak, self._stop = {}, threading.Event()
        self._sample()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, float | None]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._sample()
        return dict(self.peak)


# ---------------------------------------------------------------- chấm nguồn
def check_sources(sources: list[dict[str, Any]], case: dict[str, Any], refused: bool) -> dict[str, Any]:
    exp_doc = case.get("expected_only_document") or case.get("expected_document") or case.get("document_filename")
    exp_pages = set(case.get("expected_pages") or [])
    in_doc = [s for s in sources if not exp_doc or s.get("filename") == exp_doc]
    cited = {int(s["page"]) for s in in_doc if s.get("page") is not None}
    primary = {int(s["page"]) for s in in_doc if s.get("page") is not None and s.get("is_primary")}
    result: dict[str, Any] = {
        "n_sources": len(sources),
        "cited_pages": sorted(cited),
        "primary_pages": sorted(primary),
        "page_cited": (not exp_pages) or bool(exp_pages & cited),
        "page_primary": (not exp_pages) or bool(exp_pages & primary),
        "wrong_document_cited": bool(exp_doc) and any(s.get("filename") != exp_doc for s in sources),
        "sources_shown_on_refusal": refused and bool(sources),
    }
    if case.get("expected_only_document"):
        result["locked_document_ok"] = not result["wrong_document_cited"]
    return result


def verdict(rec: dict[str, Any], case: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not rec["refusal_pass"] and not case.get("refusal_optional"):
        reasons.append("từ chối sai (thiếu hoặc thừa)")
    if not case.get("expect_refusal") and not rec["refusal_detected"]:
        if rec["coverage"]["ratio"] < 1:
            reasons.append(f"thiếu ý: {rec['coverage']['missing']}")
        if not rec["source_check"]["page_primary"]:
            reasons.append("trang chính sai")
        if rec["source_check"].get("locked_document_ok") is False:
            reasons.append("lẫn tài liệu khác")
    if not rec["forbidden_check"]["pass"]:
        reasons.append(f"chứa chi tiết cấm: {rec['forbidden_check']['found']}")
    if rec["source_check"]["sources_shown_on_refusal"]:
        reasons.append("hiện nguồn khi từ chối")
    if rec.get("isolation_leak"):
        reasons.append("lịch sử rò sang phiên khác")
    if not reasons:
        return "đạt", reasons
    return ("đạt một phần" if rec["coverage"]["ratio"] >= 0.5 and rec["refusal_pass"] else "không đạt"), reasons


# ---------------------------------------------------------------- chạy
async def run_one(chain: Any, case: dict[str, Any], sampler: ResourceSampler, timeout: float) -> dict[str, Any]:
    history: list[dict[str, str]] = []
    for prior in case.get("prior_turns", []):
        ans, *_ = await asyncio.wait_for(chain.achat(prior, conversation_history=history or None,
                                         document_filename=case.get("document_filename")), timeout)
        history.append({"question": prior, "answer": ans})

    sampler.start()
    started = time.perf_counter()
    answer, sources, avg_score, refusal_reason = await asyncio.wait_for(
        chain.achat(case["question"], conversation_history=history or None,
                    document_filename=case.get("document_filename")), timeout)
    elapsed = round(time.perf_counter() - started, 3)
    resources = sampler.stop()

    refused = refusal_reason is not None or any(m in fold(answer) for m in REFUSAL_MARKERS)
    expect_refusal = bool(case.get("expect_refusal"))
    rec: dict[str, Any] = {
        "case_id": case["id"], "category": case["category"], "status": "ok",
        "question": case["question"], "answer": answer, "elapsed_seconds": elapsed,
        "avg_retrieval_score": round(float(avg_score or 0), 4), "refusal_reason": refusal_reason,
        "refusal_detected": refused, "refusal_pass": refused == expect_refusal,
        "coverage": coverage(answer, case.get("required_groups", [])),
        "forbidden_check": forbidden(answer, case.get("forbidden_groups", [])),
        "source_check": check_sources(sources, case, refused),
        "sources": sources, "resources_peak": resources, "answer_words": len(answer.split()),
    }
    if case.get("isolation_check"):  # cùng câu hỏi nhưng phiên mới: không được trả đủ ý nhờ lịch sử cũ
        alone, *_ = await asyncio.wait_for(chain.achat(case["question"], document_filename=case.get("document_filename")), timeout)
        rec["isolation_leak"] = coverage(alone, case["required_groups"])["ratio"] == 1.0
        rec["answer_without_history"] = alone
    rec["verdict"], rec["verdict_reasons"] = verdict(rec, case)
    return rec


async def run(args: argparse.Namespace) -> Path:
    from rag_chain import RAGChain  # import muộn để --report-only không cần backend

    cases: list[dict[str, Any]] = []
    for path in args.cases:
        cases += json.loads(Path(path).read_text(encoding="utf-8"))
    if args.case_id:
        cases = [c for c in cases if c["id"] in set(args.case_id)]

    chain = RAGChain()
    chain.initialize()
    if args.model:
        from run_benchmark import _make_llm
        chain._llm = _make_llm(args.model, float(os.getenv("LLM_TEMPERATURE", "0.3")))
    model = args.model or getattr(chain._llm, "model", os.getenv("LLM_MODEL", "?"))

    payload: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(), "model": model,
        "config": {k: os.getenv(k) for k in ("RETRIEVAL_CANDIDATE_K", "TOP_K", "MIN_RELEVANCE_SCORE",
                                            "LLM_NUM_CTX", "LLM_TEMPERATURE", "RERANKER_ENABLED")},
        "repeats": args.repeats, "cases": [c["id"] for c in cases], "results": [],
    }
    out = Path(args.output)
    sampler = ResourceSampler()
    await asyncio.wait_for(chain._llm.ainvoke("Chỉ trả lời: OK"), args.timeout)  # khởi động model, loại khỏi thống kê

    for rep in range(1, args.repeats + 1):
        for i, case in enumerate(cases, 1):
            print(f"[lần {rep}/{args.repeats} | {i}/{len(cases)}] {case['id']}", flush=True)
            try:
                rec = await run_one(chain, case, sampler, args.timeout)
                print(f"  {rec['elapsed_seconds']:.1f}s | {rec['verdict']} {rec['verdict_reasons']}", flush=True)
            except Exception as exc:  # noqa: BLE001
                rec = {"case_id": case["id"], "category": case["category"], "status": "case_error",
                       "error": repr(exc), "verdict": "lỗi"}
                print(f"  LỖI: {exc!r}", flush=True)
            rec["repeat"] = rep
            payload["results"].append(rec)
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


# ---------------------------------------------------------------- báo cáo
def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.1%})" if d else "–"


def build_report(payload: dict[str, Any]) -> str:
    rows = payload["results"]
    ok = [r for r in rows if r.get("status") == "ok"]
    answerable = [r for r in ok if not r["refusal_detected"] and r["category"] not in ("out_of_scope", "scope_other_document", "unanswerable")]
    lat = [r["elapsed_seconds"] for r in ok]
    L: list[str] = []
    L.append("# Báo cáo đánh giá EduRAG\n")
    L.append(f"- Model: `{payload['model']}` · bắt đầu {payload['started_at'][:19]} UTC · {len(payload['cases'])} câu × {payload['repeats']} lần")
    L.append("- Cấu hình: " + ", ".join(f"{k}={v}" for k, v in payload["config"].items() if v))
    L.append(f"- Số lượt chạy: {len(rows)} (lỗi hệ thống: {len(rows) - len(ok)})\n")

    L.append("## 1. Kết luận theo lượt chạy\n")
    for v in ("đạt", "đạt một phần", "không đạt", "lỗi"):
        L.append(f"- {v.capitalize()}: {pct(sum(r['verdict'] == v for r in rows), len(rows))}")

    L.append("\n## 2. Độ liên quan\n")
    if ok:
        full = sum(r["coverage"]["ratio"] == 1 for r in answerable)
        mean_cov = statistics.mean(r["coverage"]["ratio"] for r in answerable) if answerable else 0
        L.append(f"- Câu có đủ mọi ý bắt buộc: {pct(full, len(answerable))}")
        L.append(f"- Độ bao phủ ý trung bình: {mean_cov:.1%}")
        L.append(f"- Không chứa chi tiết cấm: {pct(sum(r['forbidden_check']['pass'] for r in ok), len(ok))}")
        L.append(f"- Điểm truy xuất trung bình: {statistics.mean(r['avg_retrieval_score'] for r in ok):.3f}")
        ref = [r for r in ok if r["category"] in ("out_of_scope", "scope_other_document", "unanswerable")]
        L.append(f"- Từ chối đúng với câu ngoài phạm vi: {pct(sum(r['refusal_pass'] for r in ref), len(ref))}")

    L.append("\n## 3. Tính đúng nguồn\n")
    if answerable:
        L.append(f"- Trang chính đúng: {pct(sum(r['source_check']['page_primary'] for r in answerable), len(answerable))}")
        L.append(f"- Trang đúng nằm trong nguồn trích: {pct(sum(r['source_check']['page_cited'] for r in answerable), len(answerable))}")
        L.append(f"- Số nguồn hiển thị trung bình/câu: {statistics.mean(r['source_check']['n_sources'] for r in answerable):.1f}")
    refd = [r for r in ok if r["refusal_detected"]]
    L.append(f"- Hiện nguồn khi đã từ chối (lỗi): {pct(sum(r['source_check']['sources_shown_on_refusal'] for r in refd), len(refd))}")
    L.append(f"- Lẫn tài liệu khác khi khóa tài liệu: {sum(r['source_check'].get('locked_document_ok') is False for r in ok)} lượt")
    iso = [r for r in ok if "isolation_leak" in r]
    if iso:
        L.append(f"- Rò lịch sử sang phiên khác: {sum(r['isolation_leak'] for r in iso)}/{len(iso)} ca đa lượt")

    L.append("\n## 4. Thời gian phản hồi (giây, tính từ lúc gửi câu hỏi đến khi có đáp án đầy đủ)\n")
    if lat:
        L.append(f"- p50: {percentile(lat, 50)} · p95: {percentile(lat, 95)} · trung bình: {statistics.mean(lat):.3f} · lớn nhất: {max(lat)}")
        by_cat: dict[str, list[float]] = {}
        for r in ok:
            by_cat.setdefault(r["category"], []).append(r["elapsed_seconds"])
        L.append("\n| Nhóm câu hỏi | Số lượt | p50 | Lớn nhất |\n|---|---:|---:|---:|")
        for cat, vals in sorted(by_cat.items()):
            L.append(f"| {cat} | {len(vals)} | {percentile(vals, 50)} | {max(vals)} |")

    L.append("\n## 5. Tài nguyên sử dụng (đỉnh trong lúc trả lời)\n")
    for key, label in (("backend_rss_mb", "RAM backend"), ("ollama_rss_mb", "RAM Ollama"), ("gpu_used_mb", "VRAM GPU (toàn máy)")):
        vals = [r["resources_peak"][key] for r in ok if r.get("resources_peak", {}).get(key) is not None]
        L.append(f"- {label}: " + (f"đỉnh {max(vals):.0f} MB · trung bình {statistics.mean(vals):.0f} MB" if vals else "không đo được (thiếu psutil hoặc nvidia-smi)"))

    L.append("\n## 6. Các lượt chưa đạt\n")
    bad = [r for r in rows if r["verdict"] != "đạt"]
    if bad:
        L.append("| Câu | Kết luận | Lý do |\n|---|---|---|")
        for r in bad:
            L.append(f"| {r['case_id']} (lần {r['repeat']}) | {r['verdict']} | {'; '.join(r.get('verdict_reasons', [r.get('error', '')]))} |")
    else:
        L.append("Không có.")
    L.append("\n> Kết luận tự động chỉ dựa trên từ khóa bắt buộc/cấm và trang nguồn. Ground truth lấy từ `docs/ke_hoach_kiem_thu_cau_hoi_pdf_scan.md` cần được đối chiếu với PDF trước khi dùng làm số liệu chính thức; câu có ghi `note` cần chấm tay.")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=[str(p) for p in DEFAULT_CASES])
    ap.add_argument("--output", default=str(HERE / "results_eval.json"))
    ap.add_argument("--model", help="Ghi đè model; mặc định dùng cấu hình của ứng dụng")
    ap.add_argument("--case-id", action="append")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--report-only", help="Chỉ dựng báo cáo từ file kết quả JSON")
    args = ap.parse_args()
    src = Path(args.report_only) if args.report_only else asyncio.run(run(args))
    report = HERE / "bao_cao_danh_gia.md"
    report.write_text(build_report(json.loads(src.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"Báo cáo: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
