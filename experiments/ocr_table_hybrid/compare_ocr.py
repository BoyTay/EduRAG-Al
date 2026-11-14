"""So sánh các cách OCR một trang bảng scan với đáp án gõ tay.

Gọi đúng mã OCR của backend (tesseract_service, cell_detection), nên số liệu phản ánh cách
hệ thống đang chạy. Cần Tesseract `vie` + `osd` và PaddleOCR, nên chạy trong container backend:

    docker cp experiments/ocr_table_hybrid edurag_backend:/tmp/ocr_table_hybrid
    docker exec -w /app/backend edurag_backend python /tmp/ocr_table_hybrid/compare_ocr.py \
        --pdf /app/data/1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf \
        --output /tmp/ocr_table_hybrid/results.json

(Trên Git Bash cần đặt MSYS_NO_PATHCONV=1 cho lệnh docker exec.)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import fitz
import numpy as np

from tesseract_service import TesseractOCRService, prepare_tesseract_image, rotate_image

HERE = Path(__file__).resolve().parent


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    return re.sub(r"\s+", " ", re.sub(r"\s*-\s*", " - ", text)).strip()


def score(text: str, rows: list[dict]) -> dict:
    """Đếm số dòng bảng đọc đúng: từng trường riêng lẻ, và các trường nằm chung một dòng chữ.

    "Chung một dòng" quan trọng cho RAG: đơn vị và lãnh đạo ở hai dòng rời nhau thì chatbot
    không biết lãnh đạo nào thuộc đơn vị nào.
    """
    lines = [normalize(line) for line in text.splitlines()]
    whole = normalize(text)

    def same_line(*values: str) -> bool:
        return any(all(normalize(value) in line for value in values) for line in lines)

    return {
        "unit_found": sum(normalize(row["unit"]) in whole for row in rows),
        "leader_found": sum(normalize(row["leader"]) in whole for row in rows),
        "unit_with_leader_same_line": sum(same_line(row["unit"], row["leader"]) for row in rows),
        "unit_with_date_same_line": sum(same_line(row["unit"], row["date"]) for row in rows),
        "chars": len(text),
        "rows_total": len(rows),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--truth", default=str(HERE / "page5_table_truth.json"))
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--output")
    args = parser.parse_args()

    truth = json.loads(Path(args.truth).read_text(encoding="utf-8"))
    page = fitz.open(args.pdf)[truth["page"] - 1]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(args.dpi / 72, args.dpi / 72), colorspace=fitz.csRGB, alpha=False)
    raw = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n).copy()

    service = TesseractOCRService()
    service.cache_fingerprint
    prepared = prepare_tesseract_image(raw, service.remove_colored_overlays)
    rotation = service._detect_rotation(prepared) or 0
    upright = rotate_image(prepared, rotation)
    service._read_cells(upright[:50, :50])  # nạp mô hình phát hiện trước, không tính vào thời gian

    methods = {
        "psm6 (cũ)": lambda: service._recognize(upright, 6),
        "psm3": lambda: service._recognize(upright, 3),
        "Paddle tìm ô + Tesseract đọc ô": lambda: service._read_cells(upright),
        "recognize_page (hệ thống chọn)": lambda: service.recognize_page(raw),
    }
    results = {"source": truth["source"], "page": truth["page"], "dpi": args.dpi, "rotation": rotation, "methods": {}}
    for name, run in methods.items():
        started = time.perf_counter()
        page_result = run()
        seconds = time.perf_counter() - started
        entry = {**score(page_result.text, truth["rows"]), "confidence": page_result.confidence,
                 "model": page_result.model_name, "seconds": round(seconds, 2), "text": page_result.text}
        results["methods"][name] = entry
        print(f"{name:34s} đơn vị {entry['unit_found']:2d}/15 · lãnh đạo {entry['leader_found']:2d}/15 · "
              f"đơn vị+lãnh đạo cùng dòng {entry['unit_with_leader_same_line']:2d}/15 · "
              f"đơn vị+ngày cùng dòng {entry['unit_with_date_same_line']:2d}/15 · "
              f"tin cậy {entry['confidence'] or 0:.2f} · {seconds:.1f}s")

    if args.output:
        Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
