"""Chạy bộ câu hỏi kiểm thử qua đúng pipeline RAG của EduRAG và chấm điểm.

Ví dụ (PowerShell, từ gốc repo, Ollama đang chạy):
    $env:PYTHONPATH="backend"
    python experiments/evaluation/run_eval.py --output experiments/evaluation/results_before.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Chạy hoàn toàn cục bộ: dùng model đã có trong cache Hugging Face.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from resources import ResourceMonitor, process_sampler, read_ollama_model, system_info  # noqa: E402
from scoring import load_cases, score_case, summarize  # noqa: E402

DEFAULT_CASES = Path(__file__).resolve().parent / "table_cases.json"


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_summary(summary: dict[str, Any]) -> None:
    print("\n=== Tổng hợp ===")
    for key in (
        "total", "errors", "value_accuracy", "source_accuracy",
        "false_refusal_rate", "missed_refusal_rate", "p50_seconds", "p95_seconds",
    ):
        print(f"{key:<22}{summary[key]}")
    print("Theo nhóm:")
    for category, accuracy in summary["by_category"].items():
        print(f"  {category:<20}{accuracy:.0%}")


def _print_resources(resources: dict[str, Any]) -> None:
    print("\n=== Tài nguyên ===")
    system = resources["system"]
    print(f"Máy: {system['cpu']} ({system['cpu_logical_cores']} luồng), RAM {system['ram_total_mb']} MB, "
          f"GPU {system['gpu_name']} {system['gpu_mem_total_mb']} MB")
    print(f"RAM tiến trình RAG sau khi nạp model: {resources['rss_after_init_mb']} MB")
    usage = resources["during_run"]
    print(f"Trong lúc chạy: RAM đỉnh {usage['peak_rss_mb']} MB, CPU trung bình {usage['mean_cpu_percent']}% "
          f"(đỉnh {usage['peak_cpu_percent']}%), VRAM GPU đỉnh {usage['peak_gpu_mem_used_mb']} MB")
    llm = resources["ollama_model"]
    if llm:
        print(f"LLM {llm['model']} ({llm['parameter_size']}, {llm['quantization']}, ctx {llm['context_length']}): "
              f"{llm['size_mb']} MB, trên GPU {llm['vram_mb']} MB ({llm['gpu_share']:.0%})")


async def _run(args: argparse.Namespace) -> int:
    from rag_chain import LLM_MODEL, RAGChain

    cases = load_cases(Path(args.cases))
    if args.case_id:
        selected = set(args.case_id)
        cases = [case for case in cases if case["id"] in selected]

    sampler = process_sampler()
    chain = RAGChain()
    chain.initialize()
    rss_after_init = sampler()["rss_mb"]
    output = Path(args.output)
    payload: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": LLM_MODEL,
        "cases_file": str(args.cases),
        "results": [],
    }
    runs = [(repeat, index, case) for repeat in range(1, args.repeats + 1) for index, case in enumerate(cases, start=1)]
    payload["repeats"] = args.repeats
    monitor = ResourceMonitor(interval=args.sample_interval, sample_fn=sampler).__enter__()
    for repeat, index, case in runs:
        print(f"[lần {repeat}/{args.repeats} | {index}/{len(cases)}] {case['id']}", flush=True)
        started = time.perf_counter()
        try:
            answer, sources, _score, refusal_reason = await asyncio.wait_for(
                chain.achat(case["question"], document_filename=case.get("document_filename")),
                timeout=args.timeout,
            )
            record = score_case(case, answer, sources, refusal_reason, time.perf_counter() - started)
            record.update({"repeat": repeat, "question": case["question"], "answer": answer, "refusal_reason": refusal_reason,
                           "sources": [{"filename": s.get("filename"), "page": s.get("page")} for s in sources]})
            print(f"  {record['elapsed_seconds']:.1f}s value={record['value_ok']} "
                  f"source={record['source_ok']} refusal_ok={record['refusal_ok']}", flush=True)
        except Exception as exc:  # noqa: BLE001 - một case lỗi không được dừng cả lượt đo
            record = {"case_id": case["id"], "category": case["category"], "status": "case_error", "repeat": repeat,
                      "error": repr(exc), "elapsed_seconds": round(time.perf_counter() - started, 3)}
            print(f"  ERROR: {exc!r}", flush=True)
        payload["results"].append(record)
        payload["summary"] = summarize(payload["results"])
        _write(output, payload)

    monitor.__exit__(None, None, None)
    from rag_chain import OLLAMA_BASE_URL

    payload["resources"] = {
        "system": system_info(),
        "rss_after_init_mb": rss_after_init,
        "during_run": monitor.summary(),
        "ollama_model": read_ollama_model(OLLAMA_BASE_URL, LLM_MODEL),
    }
    payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    payload["summary"] = summarize(payload["results"])
    _write(output, payload)
    _print_summary(payload["summary"])
    _print_resources(payload["resources"])
    print(f"\nKết quả: {output}")
    return 0


def main() -> int:
    # Console Windows mặc định cp1252 không in được tiếng Việt.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Đánh giá EduRAG trên bộ câu hỏi kiểm thử")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--output", required=True)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--repeats", type=int, default=1, help="Chạy cả bộ nhiều lần để đo độ dao động của LLM")
    parser.add_argument("--sample-interval", type=float, default=0.5, help="Chu kỳ lấy mẫu RAM/CPU/VRAM (giây)")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
