"""Đối chiếu bảng thô trong PDF với đoạn text mà bộ nạp sẽ lập chỉ mục.

Chỉ đọc, không ghi vào Chroma. Dùng để so trước/sau khi sửa bộ đọc bảng.

    $env:PYTHONPATH = "backend"
    python experiments/evaluation/audit_tables.py experiments/evaluation/audit_before.txt
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pymupdf as fitz

from document_ingestion import _native_table_documents, normalize_text

REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE_TEXT_THRESHOLD = 50


def audit_pdf(pdf_path: Path) -> list[str]:
    lines: list[str] = []
    state: dict = {}
    with fitz.open(pdf_path) as pdf:
        lines.append(f"\n##### {pdf_path.name} ({len(pdf)} trang)")
        for index, page in enumerate(pdf):
            native = normalize_text(page.get_text("text"))
            if len(native) < NATIVE_TEXT_THRESHOLD:
                lines.append(f"-- p{index + 1}: không có text gốc ({len(native)} ký tự) -> OCR")
                continue
            tables = page.find_tables().tables
            documents, _bounds = _native_table_documents(page, pdf_path, index, state)
            if not tables:
                continue
            lines.append(f"-- p{index + 1}: find_tables={len(tables)} docs={len(documents)}")
            for table_index, table in enumerate(tables):
                rows = table.extract()
                lines.append(f"  [bảng {table_index}] cột={table.col_count} dòng={len(rows)}")
                lines.extend("    RAW | " + " | ".join(normalize_text(c) for c in row) for row in rows)
            lines.extend("    DOC > " + document.page_content for document in documents)
    return lines


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) != 2:
        print("Cách dùng: audit_tables.py <output.txt>")
        return 2
    data_path = Path(os.getenv("DATA_PATH", str(REPO_ROOT / "data")))
    lines: list[str] = []
    for pdf_path in sorted(data_path.glob("*.pdf")):
        lines.extend(audit_pdf(pdf_path))
    Path(sys.argv[1]).write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(lines)} dòng -> {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
