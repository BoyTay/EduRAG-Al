"""Chấm điểm bộ câu hỏi kiểm thử EduRAG (thuần Python, không gọi model).

Mỗi case có giá trị bắt buộc (`expected_values`), giá trị cấm (`forbidden`),
tài liệu/trang nguồn mong đợi và cờ `should_refuse`. Trang dùng chỉ số 0-based
giống metadata của chunk.
"""

from __future__ import annotations

import json
import statistics
import unicodedata
from pathlib import Path
from typing import Any

REQUIRED_KEYS = (
    "id", "category", "question", "expected_values", "forbidden",
    "source_filename", "pages", "should_refuse",
)


def fold(text: str) -> str:
    """Bỏ dấu tiếng Việt và chữ hoa để so khớp giá trị."""
    decomposed = unicodedata.normalize("NFD", (text or "").casefold())
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return without_marks.replace("đ", "d")


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    seen: set[str] = set()
    for index, case in enumerate(cases):
        case_id = case.get("id", f"#{index}")
        missing = [key for key in REQUIRED_KEYS if key not in case]
        if missing:
            raise ValueError(f"Case id={case_id} thiếu khóa: {', '.join(missing)}")
        if case_id in seen:
            raise ValueError(f"Case id={case_id} bị trùng")
        seen.add(case_id)
    return cases


def _groups_found(folded_answer: str, groups: list[list[str]]) -> list[list[str]]:
    return [group for group in groups if any(fold(term) in folded_answer for term in group)]


def score_case(
    case: dict[str, Any],
    answer: str,
    sources: list[dict[str, Any]],
    refusal_reason: str | None,
    elapsed: float,
) -> dict[str, Any]:
    folded_answer = fold(answer)
    expected = case.get("expected_values", [])
    found_expected = _groups_found(folded_answer, expected)
    missing_values = [group for group in expected if group not in found_expected]
    forbidden_found = _groups_found(folded_answer, case.get("forbidden", []))
    pages = set(case.get("pages", []))
    source_ok = any(
        source.get("filename") == case.get("source_filename")
        and source.get("page") is not None
        and int(source["page"]) in pages
        for source in sources or []
    )
    refusal_detected = refusal_reason is not None
    should_refuse = bool(case.get("should_refuse"))
    refusal_ok = refusal_detected == should_refuse
    if should_refuse:
        value_ok = source_ok = refusal_detected
    else:
        value_ok = not missing_values and not forbidden_found and not refusal_detected
    return {
        "case_id": case["id"],
        "category": case["category"],
        "status": "ok",
        "value_ok": value_ok,
        "missing_values": missing_values,
        "forbidden_found": forbidden_found,
        "source_ok": source_ok,
        "refusal_detected": refusal_detected,
        "should_refuse": should_refuse,
        "refusal_ok": refusal_ok,
        "elapsed_seconds": round(float(elapsed), 3),
    }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _percentiles(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) < 2:
        return values[0], values[0]
    cuts = statistics.quantiles(values, n=100, method="inclusive")
    return round(cuts[49], 3), round(cuts[94], 3)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [record for record in records if record.get("status") == "ok"]
    answerable = [record for record in scored if not record["should_refuse"]]
    refusals = [record for record in scored if record["should_refuse"]]
    p50, p95 = _percentiles([record["elapsed_seconds"] for record in scored])
    categories: dict[str, list[dict[str, Any]]] = {}
    for record in scored:
        categories.setdefault(record["category"], []).append(record)
    return {
        "total": len(records),
        "errors": len(records) - len(scored),
        "value_accuracy": _ratio(sum(r["value_ok"] for r in scored), len(scored)),
        "source_accuracy": _ratio(sum(r["source_ok"] for r in scored), len(scored)),
        "false_refusal_rate": _ratio(sum(r["refusal_detected"] for r in answerable), len(answerable)),
        "missed_refusal_rate": _ratio(sum(not r["refusal_detected"] for r in refusals), len(refusals)),
        "p50_seconds": p50,
        "p95_seconds": p95,
        "by_category": {
            category: _ratio(sum(r["value_ok"] for r in items), len(items))
            for category, items in sorted(categories.items())
        },
    }
