"""Reproducible, non-production PP-OCRv6 Small CPU smoke test."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import resource
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from paddleocr import PaddleOCR


MODEL_CONFIG = {
    "lang": "vi",
    "ocr_version": "PP-OCRv6",
    "text_detection_model_name": "PP-OCRv6_small_det",
    "text_recognition_model_name": "PP-OCRv6_small_rec",
    "use_doc_orientation_classify": False,
    "use_doc_unwarping": False,
    "use_textline_orientation": False,
    "enable_mkldnn": False,
    "device": "cpu",
}

PACKAGES = (
    "paddlepaddle",
    "paddleocr",
    "paddlex",
    "numpy",
    "opencv-python",
    "opencv-contrib-python",
    "opencv-python-headless",
    "opencv-contrib-python-headless",
    "torch",
    "langchain",
    "langchain-core",
    "langchain-community",
    "chromadb",
    "sentence-transformers",
    "pymupdf",
    "fastapi",
    "pydantic",
)


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def max_rss_mb() -> float:
    # Linux ru_maxrss is KiB.
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def make_fixture(path: Path) -> None:
    image = Image.new("RGB", (1500, 540), "white")
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    title = ImageFont.truetype(font_path, 64)
    body = ImageFont.truetype(font_path, 44)
    draw.text((70, 55), "QUY CHẾ ĐÀO TẠO", fill="black", font=title)
    draw.text((70, 180), "Điều 12. Sinh viên đăng ký học phần.", fill="black", font=body)
    draw.text((70, 275), "Ngày 13 tháng 09 năm 2026", fill="black", font=body)
    draw.text((70, 370), "Học phí: 1.250.000 đồng", fill="black", font=body)
    image.save(path)


def result_payload(result: Any) -> dict[str, Any]:
    if hasattr(result, "json"):
        value = result.json
        if callable(value):
            value = value()
        if isinstance(value, str):
            return json.loads(value)
        if isinstance(value, dict):
            return value
    if isinstance(result, dict):
        return result
    raise TypeError(f"Unsupported result type: {type(result)!r}")


def extract_fields(result: Any) -> tuple[list[str], list[float], list[Any], list[Any]]:
    payload = result_payload(result)
    data = payload.get("res", payload)
    texts = list(data.get("rec_texts") or [])
    scores = [float(value) for value in (data.get("rec_scores") or [])]
    polygons = list(data.get("rec_polys") or [])
    boxes = list(data.get("rec_boxes") or [])
    return texts, scores, polygons, boxes


def main() -> None:
    fixture = Path("/tmp/ppocrv6_vi_smoke.png")
    make_fixture(fixture)

    cache_home = Path(os.environ.get("PADDLE_PDX_CACHE_HOME", "/opt/ppocr-cache"))
    cache_before = directory_size(cache_home)
    rss_before = max_rss_mb()

    init_started = time.perf_counter()
    ocr = PaddleOCR(**MODEL_CONFIG)
    init_seconds = time.perf_counter() - init_started
    rss_after_init = max_rss_mb()

    runs: list[dict[str, Any]] = []
    for run_number in (1, 2):
        started = time.perf_counter()
        results = list(ocr.predict(str(fixture)))
        elapsed = time.perf_counter() - started
        if not results:
            raise RuntimeError("PaddleOCR returned no result objects")
        texts, scores, polygons, boxes = extract_fields(results[0])
        if not texts or not scores or not polygons or not boxes:
            raise RuntimeError(
                "Smoke result must contain text, confidence, polygons and boxes"
            )
        runs.append(
            {
                "run": run_number,
                "seconds": round(elapsed, 3),
                "text_count": len(texts),
                "texts": texts,
                "confidence_count": len(scores),
                "confidence_min": round(min(scores), 6),
                "confidence_mean": round(sum(scores) / len(scores), 6),
                "polygon_count": len(polygons),
                "box_count": len(boxes),
                "max_rss_mb": max_rss_mb(),
            }
        )

    cache_after = directory_size(cache_home)
    summary = {
        "status": "PASS",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": package_versions(),
        "model_config": MODEL_CONFIG,
        "model_instances": 1,
        "predict_calls": 2,
        "init_seconds": round(init_seconds, 3),
        "rss_before_mb": rss_before,
        "rss_after_init_mb": rss_after_init,
        "rss_peak_mb": max_rss_mb(),
        "cache_home": str(cache_home),
        "cache_bytes_before": cache_before,
        "cache_bytes_after": cache_after,
        "runs": runs,
    }
    print("SPIKE_RESULT=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
