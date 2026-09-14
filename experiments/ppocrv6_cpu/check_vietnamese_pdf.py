"""Read-only real PDF OCR comparison; never opens the application databases."""
import argparse
import json
import time
from pathlib import Path

import pymupdf as fitz
from document_ingestion import _render_page
from ocr_service import PaddleOCRService


parser = argparse.ArgumentParser()
parser.add_argument("pdf")
parser.add_argument("--page", type=int, default=3)
parser.add_argument("--dpi", type=int, default=200)
args = parser.parse_args()
with fitz.open(args.pdf) as pdf:
    image = _render_page(pdf[args.page - 1], args.dpi)
service = PaddleOCRService()
started = time.perf_counter()
result = service.recognize_page(image)
print(json.dumps({
    "file": Path(args.pdf).name, "page": args.page, "dpi": args.dpi,
    "model": result.model_name, "seconds": round(time.perf_counter() - started, 2),
    "confidence": result.confidence,
    "lines": [line.to_dict() for line in result.lines],
}, ensure_ascii=False), flush=True)
