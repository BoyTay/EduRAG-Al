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


# Dấu hiệu UTF-8 tiếng Việt bị đọc nhầm thành Latin-1 ("Ä‘" thay cho "đ", "á»" ...).
MOJIBAKE = re.compile(r"Ã[\u0080-ÿ]|Ä[‘’\u0080-¿]|Æ[°¡]|á[º»]")
NUMBER = re.compile(r"\d+(?:[.,/:-]\d+)*%?")
EDGE_PUNCTUATION = "\"'“”‘’()[]{}.,;:!?…"
MIN_JUDGED_TOKENS = 10
MIN_WORD_RATIO = 0.7
# Ký hiệu như | = # § < > © gần như không có trong văn bản hành chính; OCR rác thì đầy.
NORMAL_PUNCTUATION = set(".,;:!?()[]\"'“”‘’-–—/%…+&*")
MIN_SYMBOL_JUDGED_CHARS = 20
MAX_SYMBOL_RATIO = 0.15


def _is_word(token: str) -> bool:
    """Từ bình thường (viết thường, Viết Hoa đầu hoặc VIẾT HOA, có thể nối gạch ngang) hoặc con số."""
    if NUMBER.fullmatch(token):
        return True
    parts = token.split("-")
    return all(
        part.isalpha() and (part.islower() or part.isupper() or (part[0].isupper() and part[1:].islower()))
        for part in parts
    )


def is_garbled(content: str) -> bool:
    """Chữ OCR đọc sai hướng / mờ, hoặc tiếng Việt bị lỗi mã hóa.

    Chỉ xét các token có ít nhất hai ký tự chữ-số: ký hiệu đứng riêng (—, -, |) và chữ cái
    đơn (a, b trong liệt kê) không nói lên gì. Đoạn quá ít token thì không phán xét.
    """
    if MOJIBAKE.search(content):
        return True
    visible = [char for char in content if not char.isspace()]
    symbols = sum(not char.isalnum() and char not in NORMAL_PUNCTUATION for char in visible)
    if len(visible) >= MIN_SYMBOL_JUDGED_CHARS and symbols / len(visible) > MAX_SYMBOL_RATIO:
        return True
    judged = good = 0
    for raw in content.split():
        token = raw.strip(EDGE_PUNCTUATION)
        if sum(char.isalnum() for char in token) < 2:
            continue
        judged += 1
        good += _is_word(token)
    return judged >= MIN_JUDGED_TOKENS and good / judged < MIN_WORD_RATIO


def flag_chunk(content: str, metadata: dict[str, Any]) -> list[str]:
    """Trả về các cờ nghi lỗi của một chunk: chữ lỗi cho mọi chunk, thêm cờ cấu trúc cho chunk bảng."""
    flags: list[str] = ["garbled_text"] if is_garbled(content) else []
    if metadata.get("extraction_method") != "native_table":
        return flags
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
            "ocr_model": metadata.get("ocr_model"),
            "ocr_confidence": metadata.get("ocr_confidence"),
            "review_status": metadata.get("review_status"),
            "review_reasons": [reason for reason in (metadata.get("review_reasons") or "").split(",") if reason],
            "flags": flag_chunk(content, metadata),
            "_order": (metadata.get("chunk_index") or 0, metadata.get("page") or 0),
        })
    chunks.sort(key=lambda chunk: chunk["_order"])
    for chunk in chunks:
        del chunk["_order"]
    return chunks


# Trang đọc bằng OCR (hoặc đã sửa tay) mới được admin xác nhận/sửa ở cấp trang.
EDITABLE_METHODS = {"tesseract", "ppocrv6", "manual"}


def summarize_pages(chunks: list[dict[str, Any]], reviews: dict[int, Any]) -> list[dict[str, Any]]:
    """Gom các đoạn theo trang: cách đọc, độ tin cậy, trạng thái kiểm tra; trang đánh số từ 1.

    `reviews` là page_index → dòng page_reviews (cần reviewed_by, reviewed_at).
    """
    pages: dict[int, dict[str, Any]] = {}
    for chunk in chunks:
        page_index = chunk.get("page")
        if page_index is None or page_index in pages:
            continue
        review = reviews.get(page_index)
        pages[page_index] = {
            "page": page_index + 1,
            "extraction_method": chunk.get("extraction_method"),
            "ocr_model": chunk.get("ocr_model"),
            "ocr_confidence": chunk.get("ocr_confidence"),
            "review_status": chunk.get("review_status"),
            "review_reasons": list(chunk.get("review_reasons") or []),
            "reviewed_by": getattr(review, "reviewed_by", None),
            "reviewed_at": getattr(review, "reviewed_at", None),
            "editable": chunk.get("extraction_method") in EDITABLE_METHODS,
        }
    return [pages[index] for index in sorted(pages)]
