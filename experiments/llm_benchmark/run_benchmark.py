"""Reproducible local-model smoke benchmark for EduRAG.

The script keeps retrieval and prompt logic unchanged and swaps only the
answer/audit Ollama model. Results are written after every case so a long local
run can be resumed or inspected even if a later model fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Benchmark local models without remote metadata probes from Hugging Face.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from langchain_ollama import ChatOllama

from rag_chain import LLM_AUDIT_TEMPERATURE, RAGChain


DEFAULT_MODELS = ["qwen2.5:7b", "qwen3.5:9b", "gemma4:12b"]
BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
ANSWER_TEMPERATURE = float(os.getenv("BENCHMARK_TEMPERATURE", "0.3"))


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _coverage(answer: str, groups: list[list[str]]) -> dict[str, Any]:
    if not groups:
        return {"matched": 0, "total": 0, "ratio": 1.0, "missing": []}
    folded = _fold(answer)
    missing = [group for group in groups if not any(_fold(term) in folded for term in group)]
    matched = len(groups) - len(missing)
    return {
        "matched": matched,
        "total": len(groups),
        "ratio": round(matched / len(groups), 4),
        "missing": missing,
    }


def _forbidden_check(answer: str, groups: list[list[str]]) -> dict[str, Any]:
    folded = _fold(answer)
    found = [group for group in groups if any(_fold(term) in folded for term in group)]
    return {"pass": not found, "found": found}


def _source_check(sources: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    filename = case.get("document_filename")
    expected_pages = set(case.get("expected_pages", []))
    matching = [source for source in sources if not filename or source.get("filename") == filename]
    cited_pages = {int(source["page"]) for source in matching if source.get("page") is not None}
    primary_pages = {
        int(source["page"])
        for source in matching
        if source.get("page") is not None and source.get("is_primary")
    }
    return {
        "cited_pages": sorted(cited_pages),
        "primary_pages": sorted(primary_pages),
        "expected_page_cited": not expected_pages or bool(expected_pages & cited_pages),
        "expected_page_primary": not expected_pages or bool(expected_pages & primary_pages),
    }


def _make_llm(model: str, temperature: float) -> ChatOllama:
    return ChatOllama(
        model=model,
        base_url=BASE_URL,
        temperature=temperature,
        reasoning=False,
        num_ctx=8192,
        num_predict=1000,
        top_p=0.9,
        repeat_penalty=1.1,
        keep_alive="10m",
    )


def _write_results(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def _run(args: argparse.Namespace) -> int:
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    selected_ids = set(args.case_id or [])
    if selected_ids:
        cases = [case for case in cases if case["id"] in selected_ids]

    chain = RAGChain()
    chain.initialize()
    payload: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "temperature": ANSWER_TEMPERATURE,
        "audit_temperature": LLM_AUDIT_TEMPERATURE,
        "models": args.models,
        "cases": [case["id"] for case in cases],
        "repeats": args.repeats,
        "results": [],
    }
    output_path = Path(args.output)
    _write_results(output_path, payload)

    for model in args.models:
        print(f"\n=== {model} ===", flush=True)
        chain._llm = _make_llm(model, ANSWER_TEMPERATURE)
        chain._audit_llm = _make_llm(model, LLM_AUDIT_TEMPERATURE)

        warm_started = time.perf_counter()
        try:
            await asyncio.wait_for(chain._llm.ainvoke("Chỉ trả lời: OK"), timeout=args.timeout)
            warmup_seconds = round(time.perf_counter() - warm_started, 3)
        except Exception as exc:  # noqa: BLE001 - benchmark must record model failures
            payload["results"].append(
                {"model": model, "status": "model_error", "error": repr(exc)}
            )
            _write_results(output_path, payload)
            print(f"MODEL ERROR: {exc!r}", flush=True)
            continue

        for repeat_index in range(1, args.repeats + 1):
            for index, case in enumerate(cases, start=1):
                print(
                    f"[run {repeat_index}/{args.repeats} | {index}/{len(cases)}] "
                    f"{case['id']}",
                    flush=True,
                )
                started = time.perf_counter()
                try:
                    answer, sources, avg_score, refusal_reason = await asyncio.wait_for(
                        chain.achat(
                            case["question"],
                            document_filename=case.get("document_filename"),
                        ),
                        timeout=args.timeout,
                    )
                    elapsed = round(time.perf_counter() - started, 3)
                    coverage = _coverage(answer, case.get("required_groups", []))
                    forbidden_check = _forbidden_check(
                        answer, case.get("forbidden_groups", [])
                    )
                    source_check = _source_check(sources, case)
                    expected_refusal = bool(case.get("expect_refusal"))
                    normalized_answer = _fold(answer)
                    refusal_detected = refusal_reason is not None or any(
                        marker in normalized_answer
                        for marker in (
                            "khong tim thay thong tin phu hop",
                            "tai lieu khong co thong tin",
                            "khong co thong tin trong tai lieu",
                        )
                    )
                    refusal_pass = refusal_detected == expected_refusal
                    record = {
                        "model": model,
                        "repeat": repeat_index,
                        "case_id": case["id"],
                        "category": case["category"],
                        "status": "ok",
                        "question": case["question"],
                        "answer": answer,
                        "elapsed_seconds": elapsed,
                        "warmup_seconds": warmup_seconds,
                        "avg_retrieval_score": round(avg_score, 4),
                        "refusal_reason": refusal_reason,
                        "refusal_detected": refusal_detected,
                        "refusal_pass": refusal_pass,
                        "coverage": coverage,
                        "forbidden_check": forbidden_check,
                        "source_check": source_check,
                        "sources": sources,
                        "answer_words": len(answer.split()),
                    }
                    print(
                        f"  {elapsed:.1f}s coverage={coverage['ratio']:.0%} "
                        f"grounded={forbidden_check['pass']} "
                        f"source={source_check['expected_page_cited']} refusal={refusal_pass}",
                        flush=True,
                    )
                except Exception as exc:  # noqa: BLE001 - preserve remaining cases
                    record = {
                        "model": model,
                        "repeat": repeat_index,
                        "case_id": case["id"],
                        "category": case["category"],
                        "status": "case_error",
                        "error": repr(exc),
                        "elapsed_seconds": round(time.perf_counter() - started, 3),
                    }
                    print(f"  ERROR: {exc!r}", flush=True)
                payload["results"].append(record)
                _write_results(output_path, payload)

        subprocess.run(["ollama", "stop", model], check=False, capture_output=True, text=True)

    payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_results(output_path, payload)
    print(f"\nResults: {output_path}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="experiments/llm_benchmark/cases.json")
    parser.add_argument("--output", default="experiments/llm_benchmark/results_smoke.json")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180.0)
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
