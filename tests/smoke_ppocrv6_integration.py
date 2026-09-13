"""Real-model smoke test for the production OCR and ingestion modules.

This script creates only synthetic, non-sensitive fixtures. It is intentionally
kept outside unittest discovery because it downloads/loads PP-OCRv6 Small.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pymupdf as fitz
import numpy as np
from docx import Document as WordDocument
from PIL import Image, ImageDraw, ImageFont

from document_ingestion import IngestionSettings, OCRResultCache, load_and_chunk_document
from ocr_service import PaddleOCRService


def _make_scan_image(path: Path) -> None:
    image = Image.new("RGB", (1800, 700), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=58)
    lines = (
        "QUY CHE DAO TAO",
        "DIEU 12 - DANG KY HOC PHAN",
        "NGAY 13 THANG 09 NAM 2026",
    )
    for index, line in enumerate(lines):
        draw.text((90, 90 + index * 170), line, fill="black", font=font)
    image.save(path)


def _make_scan_pdf(image_path: Path, pdf_path: Path) -> None:
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(35, 200, 560, 405), filename=str(image_path))
    pdf.save(pdf_path)
    pdf.close()


def _make_mixed_pdf(image_path: Path, pdf_path: Path) -> None:
    pdf = fitz.open()
    native_page = pdf.new_page(width=595, height=842)
    native_page.insert_text(
        (50, 90),
        "Native text page. " * 12,
        fontsize=14,
    )
    scan_page = pdf.new_page(width=595, height=842)
    scan_page.insert_image(fitz.Rect(35, 200, 560, 405), filename=str(image_path))
    pdf.new_page(width=595, height=842)
    pdf.save(pdf_path)
    pdf.close()


def _make_docx(path: Path) -> None:
    document = WordDocument()
    document.add_paragraph("Quy chế đào tạo giữ nguyên luồng DOCX. " * 8)
    document.save(path)


def _settings(cache_path: Path) -> IngestionSettings:
    return IngestionSettings(
        ocr_enabled=True,
        dpi=200,
        native_text_threshold=50,
        sanity_min_chars=3,
        blank_pixel_threshold=245,
        blank_dark_ratio=0.0005,
        blank_stddev=2.0,
        chunk_size=700,
        chunk_overlap=150,
        cache_path=cache_path,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="edurag-ocr-smoke-") as temp_name:
        temp = Path(temp_name)
        image_path = temp / "fixture.png"
        scan_pdf = temp / "scan.pdf"
        mixed_pdf = temp / "mixed.pdf"
        docx_path = temp / "native.docx"
        cache_path = temp / "ocr-cache"
        _make_scan_image(image_path)
        _make_scan_pdf(image_path, scan_pdf)
        _make_mixed_pdf(image_path, mixed_pdf)
        _make_docx(docx_path)

        service = PaddleOCRService(concurrency=1)
        settings = _settings(cache_path)
        cache = OCRResultCache(cache_path)

        direct = service.recognize_page(np.asarray(Image.open(image_path).convert("RGB")))
        if not direct.text or direct.confidence is None or not direct.lines:
            raise RuntimeError("OCR service thiếu text, confidence hoặc lines")
        if any(not line.bounding_box for line in direct.lines):
            raise RuntimeError("OCR service thiếu bounding box")

        started = time.perf_counter()
        scan = load_and_chunk_document(scan_pdf, service, settings, cache)
        first_scan_seconds = time.perf_counter() - started
        if service.initialization_count != 1:
            raise RuntimeError("PP-OCRv6 Small phải lazy-load đúng một lần")
        scan_metadata = scan.chunks[0].metadata
        if scan_metadata.get("extraction_method") != "ppocrv6":
            raise RuntimeError("PDF scan không đi qua PP-OCRv6")
        if not scan_metadata.get("ocr_model") or "ocr_confidence" not in scan_metadata:
            raise RuntimeError("Thiếu metadata model/confidence của OCR")

        started = time.perf_counter()
        cached_scan = load_and_chunk_document(scan_pdf, service, settings, cache)
        cache_hit_seconds = time.perf_counter() - started
        if service.initialization_count != 1 or not cached_scan.chunks:
            raise RuntimeError("OCR cache không tái sử dụng được kết quả")

        mixed = load_and_chunk_document(mixed_pdf, service, settings, cache)
        methods = {chunk.metadata.get("extraction_method") for chunk in mixed.chunks}
        if not {"native", "ppocrv6"}.issubset(methods):
            raise RuntimeError(f"PDF mixed thiếu extraction method: {sorted(methods)}")
        if not any("trang trắng 3" in warning for warning in mixed.warnings):
            raise RuntimeError("Trang trắng của PDF mixed không được ghi warning")

        docx = load_and_chunk_document(docx_path, service, settings, cache)
        if any(chunk.metadata.get("extraction_method") != "native" for chunk in docx.chunks):
            raise RuntimeError("DOCX không giữ nguyên native extraction")

        cache_files = list(cache_path.rglob("*.json"))
        if not cache_files:
            raise RuntimeError("OCR result cache không tạo JSON")

        result = {
            "status": "PASS",
            "model_initializations": service.initialization_count,
            "direct_line_count": len(direct.lines),
            "direct_confidence": round(direct.confidence, 6),
            "first_scan_seconds": round(first_scan_seconds, 3),
            "cache_hit_seconds": round(cache_hit_seconds, 3),
            "scan_text": scan.chunks[0].page_content,
            "scan_metadata": scan_metadata,
            "mixed_methods": sorted(method for method in methods if method),
            "mixed_warnings": mixed.warnings,
            "docx_chunks": len(docx.chunks),
            "ocr_cache_json_files": len(cache_files),
        }
        print("INTEGRATION_SMOKE_RESULT=" + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
