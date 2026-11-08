"""Đọc các chunk đã lập chỉ mục của một tài liệu để kiểm tra chất lượng nạp.

Dùng chung cho script `experiments/evaluation/dump_chunks.py` và endpoint
`GET /admin/documents/{filename}/chunks`.
"""

from __future__ import annotations

import re
from typing import Any

GENERIC_LABEL = re.compile(r"\bCột \d+:")
CAPTION_PREFIX = re.compile(r"^\[[^\]]*\]\s*")
MIN_TABLE_CHUNK_CHARS = 25
MAX_LABEL_CHARS = 60


def flag_chunk(content: str, metadata: dict[str, Any]) -> list[str]:
    """Trả về các cờ nghi lỗi của một chunk bảng (chunk văn xuôi không bị gắn cờ)."""
    if metadata.get("extraction_method") != "native_table":
        return []
    flags: list[str] = []
    if GENERIC_LABEL.search(content):
        flags.append("generic_label")
    if len(content) < MIN_TABLE_CHUNK_CHARS:
        flags.append("too_short")
    body = CAPTION_PREFIX.sub("", content, count=1)
    labels = [part.split(":", 1)[0] for part in body.split("; ") if ":" in part]
    if any(len(label.strip()) > MAX_LABEL_CHARS for label in labels):
        flags.append("long_label")
    return flags


def list_document_chunks(collection, filename: str) -> list[dict[str, Any]]:
    """Lấy mọi chunk của `filename` theo thứ tự đã nạp, kèm cờ nghi lỗi."""
    result = collection.get(where={"filename": filename}, include=["documents", "metadatas"])
    rows = zip(result.get("ids") or [], result.get("documents") or [], result.get("metadatas") or [])
    chunks = []
    for chunk_id, content, metadata in rows:
        metadata = metadata or {}
        content = content or ""
        chunks.append({
            "id": chunk_id,
            "content": content,
            "page": metadata.get("page"),
            "extraction_method": metadata.get("extraction_method"),
            "table_index": metadata.get("table_index"),
            "table_row": metadata.get("table_row"),
            "table_caption": metadata.get("table_caption"),
            "table_continued": bool(metadata.get("table_continued", False)),
            "flags": flag_chunk(content, metadata),
            "_order": (metadata.get("chunk_index") or 0, metadata.get("page") or 0),
        })
    chunks.sort(key=lambda chunk: chunk["_order"])
    for chunk in chunks:
        del chunk["_order"]
    return chunks
