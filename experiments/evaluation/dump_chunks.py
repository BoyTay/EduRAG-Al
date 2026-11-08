"""Xuất các chunk thực tế đang lưu trong Chroma của một tài liệu.

Đọc thẳng collection đang hoạt động bằng chromadb (không nạp model embedding).

    $env:PYTHONPATH = "backend"
    python experiments/evaluation/dump_chunks.py --filename So_tay_sinh_vien.pdf --output experiments/evaluation/chunks_so_tay.txt
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import chromadb

from chunk_inspection import list_document_chunks

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COLLECTION = "edurag_docs"


def active_collection_name(chroma_path: Path) -> str:
    marker = chroma_path / ".active_collection"
    try:
        name = marker.read_text(encoding="utf-8").strip()
        return name or DEFAULT_COLLECTION
    except FileNotFoundError:
        return DEFAULT_COLLECTION


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Xuất chunk của một tài liệu từ Chroma")
    parser.add_argument("--filename", required=True)
    parser.add_argument("--output")
    parser.add_argument("--chroma-path", default=os.getenv("CHROMA_PATH", str(REPO_ROOT / "chroma_db")))
    args = parser.parse_args()

    chroma_path = Path(args.chroma_path)
    name = active_collection_name(chroma_path)
    collection = chromadb.PersistentClient(path=str(chroma_path)).get_collection(name)
    chunks = list_document_chunks(collection, args.filename)
    lines = [f"# {args.filename} — collection '{name}' — {len(chunks)} chunk"]
    for chunk in chunks:
        page = "?" if chunk["page"] is None else chunk["page"] + 1
        flags = f" {chunk['flags']}" if chunk["flags"] else ""
        lines.append(f"p{page} [{chunk['extraction_method']}]{flags} | {chunk['content']}")
    flagged = sum(bool(chunk["flags"]) for chunk in chunks)
    lines.append(f"# {flagged} chunk nghi lỗi")
    text = "\n".join(lines)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"{len(chunks)} chunk ({flagged} nghi lỗi) -> {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
