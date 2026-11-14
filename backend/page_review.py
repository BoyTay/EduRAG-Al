"""Dấu hiệu một trang OCR cần người đối chiếu với bản gốc.

Chỉ dùng cho trang đọc bằng OCR; trang PDF có lớp chữ sẵn không qua đây. Mỗi dấu hiệu có một mã
để màn Kiểm tra đoạn hiện lý do: low_confidence, garbled_text, row_number_gap, malformed_date.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from chunk_inspection import is_garbled
from tesseract_service import LAYOUT_RETRY_CONFIDENCE

# Cùng ngưỡng với lúc OCR quyết định đọc lại theo ô: dưới mức này là trang khó.
REVIEW_CONFIDENCE = LAYOUT_RETRY_CONFIDENCE

_FIRST_CELL_NOISE = "'\"[]().: "
_HEADER_CELLS = {"tt", "stt"}
# Ứng viên ngày: ba phần ngăn bởi "/", phần cuối là năm 4 chữ số; phần đầu có thể lẫn chữ ("2l", "z7").
_DATE_CANDIDATE = re.compile(r"\S{0,4}/\S{1,3}/\d{4}\S*")
_VALID_DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
# "|" dính vào ngày là viền ô bảng chứ không phải ngày hỏng; dấu câu cuối là của câu văn.
_DATE_EDGE = "|.,;:)("


@dataclass(frozen=True)
class PageOverride:
    """Quyết định của admin cho một trang: "confirmed" (giữ chữ OCR) hoặc "corrected" (dùng chữ sửa tay)."""

    status: str
    corrected_text: str | None = None


def row_number_gaps(text: str) -> bool:
    """Số thứ tự của bảng bị đọc hỏng ("Á", "®") hoặc không tăng liên tục."""
    numbers: list[int] = []
    broken = False
    for line in text.splitlines():
        if "|" not in line:
            continue
        first = line.split("|", 1)[0].strip(_FIRST_CELL_NOISE)
        if first.isdigit() and 1 <= int(first) <= 999:
            numbers.append(int(first))
        elif 1 <= len(first) <= 3 and first.lower() not in _HEADER_CELLS:
            broken = True
    if len(numbers) < 2:
        return False
    return broken or any(later != earlier + 1 for earlier, later in zip(numbers, numbers[1:]))


def has_malformed_date(text: str) -> bool:
    """Có cụm trông như ngày (d/m/yyyy) nhưng lẫn ký tự lạ, vd. "z7/8/2026", "[28/8/2026"."""
    return any(
        not _VALID_DATE.fullmatch(candidate.strip(_DATE_EDGE))
        for candidate in _DATE_CANDIDATE.findall(text)
    )


def review_reasons(text: str, confidence: float | None) -> list[str]:
    """Các mã lý do nghi lỗi của một trang OCR, theo thứ tự cố định; rỗng nếu trang ổn."""
    reasons = []
    if confidence is not None and confidence < REVIEW_CONFIDENCE:
        reasons.append("low_confidence")
    if is_garbled(text):
        reasons.append("garbled_text")
    if row_number_gaps(text):
        reasons.append("row_number_gap")
    if has_malformed_date(text):
        reasons.append("malformed_date")
    return reasons
