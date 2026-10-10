"""Shared PDF/DOCX ingestion with page-level PP-OCRv6 fallback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf as fitz
import numpy as np
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from ocr_service import OCRConfigurationError, OCRPageResult, OCRServiceProtocol, get_default_ocr_service


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("{} không hợp lệ; dùng {}", name, default)
        return default


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        return min(maximum, max(minimum, float(os.getenv(name, str(default)))))
    except ValueError:
        logger.warning("{} không hợp lệ; dùng {}", name, default)
        return default


@dataclass(frozen=True)
class IngestionSettings:
    ocr_enabled: bool = True
    dpi: int = 300
    native_text_threshold: int = 50
    sanity_min_chars: int = 3
    blank_pixel_threshold: int = 245
    blank_dark_ratio: float = 0.0005
    blank_stddev: float = 2.0
    chunk_size: int = 700
    chunk_overlap: int = 150
    cache_path: Path = Path("ocr_cache")

    @classmethod
    def from_env(cls) -> "IngestionSettings":
        return cls(
            ocr_enabled=_env_bool("OCR_ENABLED", True),
            dpi=_env_int("OCR_DPI", 300, 72),
            native_text_threshold=_env_int("OCR_NATIVE_TEXT_THRESHOLD", 50),
            sanity_min_chars=_env_int("OCR_SANITY_MIN_CHARS", 3),
            blank_pixel_threshold=_env_int("OCR_BLANK_PIXEL_THRESHOLD", 245, 1),
            blank_dark_ratio=_env_float("OCR_BLANK_DARK_RATIO", 0.0005, 0.0, 1.0),
            blank_stddev=_env_float("OCR_BLANK_STDDEV", 2.0, 0.0, 255.0),
            chunk_size=_env_int("CHUNK_SIZE", 700),
            chunk_overlap=_env_int("CHUNK_OVERLAP", 150, 0),
            cache_path=Path(os.getenv("OCR_RESULT_CACHE_PATH", "/app/ocr_cache")),
        )


@dataclass
class DocumentIngestionResult:
    chunks: list[Document]
    warnings: list[str] = field(default_factory=list)
    created_cache_files: list[Path] = field(default_factory=list)
    file_sha256: str | None = None


class DocumentIngestionError(ValueError):
    def __init__(
        self,
        message: str,
        failed_pages: list[int] | None = None,
        created_cache_files: list[Path] | None = None,
    ) -> None:
        self.failed_pages = sorted(set(failed_pages or []))
        self.created_cache_files = list(created_cache_files or [])
        if self.failed_pages:
            pages = ", ".join(str(page) for page in self.failed_pages)
            message = f"{message} Trang thất bại: {pages}."
        super().__init__(message)


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").replace("\x00", "").split())


_SECTION_HEADINGS = {
    "muc dich": "MỤC ĐÍCH",
    "yeu cau": "YÊU CẦU",
    "doi tuong": "ĐỐI TƯỢNG",
    "thoi gian": "THỜI GIAN",
    "dia diem": "ĐỊA ĐIỂM",
    "noi dung": "NỘI DUNG",
    "kinh phi": "KINH PHÍ",
    "to chuc thuc hien": "TỔ CHỨC THỰC HIỆN",
    "cac khoa": "CÁC KHOA",
    "trach nhiem": "TRÁCH NHIỆM",
}


def _heading_normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", (value or "").lower())
    without_marks = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    return " ".join(re.findall(r"[a-z0-9]+", without_marks))


def detect_section_title(value: str) -> str | None:
    """Find the last recognizable numbered heading in one flattened chunk."""
    normalized = _heading_normalize(value[:900])
    matches: list[tuple[int, str]] = []
    for heading, canonical in _SECTION_HEADINGS.items():
        match = re.search(
            rf"\b(?:[ivxlcdm]{{1,8}}|\d+(?:\s+\d+){{0,2}})\s+{re.escape(heading)}\b",
            normalized,
        )
        if match:
            matches.append((match.start(), canonical))
    return max(matches, default=(0, None), key=lambda item: item[0])[1]


def annotate_chunk_metadata(chunks: list[Document]) -> None:
    """Persist stable chunk order and inherited page section metadata."""
    section_by_page: dict[object, str] = {}
    page_chunk_counts: dict[object, int] = {}
    for chunk_index, chunk in enumerate(chunks):
        metadata = dict(chunk.metadata or {})
        page = metadata.get("page")
        page_key: object = page if page is not None else "document"
        detected_title = detect_section_title(chunk.page_content)
        if detected_title:
            section_by_page[page_key] = detected_title
        if page_key in section_by_page:
            metadata["section_title"] = section_by_page[page_key]
        metadata["chunk_index"] = chunk_index
        metadata["page_chunk_index"] = page_chunk_counts.get(page_key, 0)
        page_chunk_counts[page_key] = metadata["page_chunk_index"] + 1
        chunk.metadata = metadata


def has_sane_text(value: str, minimum_alnum: int) -> bool:
    text = normalize_text(value)
    return bool(text) and sum(character.isalnum() for character in text) >= minimum_alnum


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OCRResultCache:
    """Private, reproducible JSON cache. Rendered page images are never stored."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def from_env(cls) -> "OCRResultCache":
        return cls(IngestionSettings.from_env().cache_path)

    def _fingerprint(
        self,
        file_sha256: str,
        page_index: int,
        dpi: int,
        service_fingerprint: dict[str, str | int | float | bool],
    ) -> str:
        payload = {
            "file_sha256": file_sha256,
            "page_index": page_index,
            "dpi": dpi,
            "ocr": service_fingerprint,
        }
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def entry_path(
        self,
        file_sha256: str,
        page_index: int,
        dpi: int,
        service_fingerprint: dict[str, str | int | float | bool],
    ) -> Path:
        key = self._fingerprint(file_sha256, page_index, dpi, service_fingerprint)
        return self.root / file_sha256 / f"page-{page_index}-{key}.json"

    def read(
        self,
        file_sha256: str,
        page_index: int,
        dpi: int,
        service_fingerprint: dict[str, str | int | float | bool],
    ) -> OCRPageResult | None:
        path = self.entry_path(file_sha256, page_index, dpi, service_fingerprint)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return OCRPageResult.from_dict(payload["result"])
        except FileNotFoundError:
            return None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Bỏ qua OCR cache không hợp lệ tại {}: {}", path, exc)
            return None

    def write(
        self,
        file_sha256: str,
        page_index: int,
        dpi: int,
        service_fingerprint: dict[str, str | int | float | bool],
        result: OCRPageResult,
    ) -> Path:
        path = self.entry_path(file_sha256, page_index, dpi, service_fingerprint)
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.parent.chmod(0o700)
        except OSError:
            pass
        temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        payload = {
            "file_sha256": file_sha256,
            "page_index": page_index,
            "dpi": dpi,
            "ocr": service_fingerprint,
            "result": result.to_dict(),
        }
        try:
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            try:
                temporary_path.chmod(0o600)
            except OSError:
                pass
            temporary_path.replace(path)
            return path
        finally:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    def delete_entries(self, paths: list[Path]) -> None:
        root = self.root.resolve()
        for path in paths:
            try:
                resolved = path.resolve()
                if root not in resolved.parents:
                    logger.warning("Từ chối xóa OCR cache ngoài cache root: {}", resolved)
                    continue
                resolved.unlink(missing_ok=True)
                try:
                    resolved.parent.rmdir()
                except OSError:
                    pass
            except OSError as exc:
                logger.warning("Không thể dọn OCR cache {}: {}", path, exc)

    def delete_file_hash(self, file_sha256: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", file_sha256):
            raise ValueError("SHA-256 tài liệu không hợp lệ")
        directory = (self.root / file_sha256).resolve()
        root = self.root.resolve()
        if directory.parent != root:
            raise ValueError("Đường dẫn OCR cache không hợp lệ")
        if directory.exists():
            shutil.rmtree(directory)

    def delete_document(self, file_path: Path) -> None:
        self.delete_file_hash(sha256_file(file_path))


def _render_page(page: fitz.Page, dpi: int) -> np.ndarray:
    scale = dpi / 72.0
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
    return np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    ).copy()


def is_confidently_blank(image: np.ndarray, settings: IngestionSettings) -> bool:
    if image.size == 0:
        return True
    grayscale = image.astype(np.float32).mean(axis=2) if image.ndim == 3 else image.astype(np.float32)
    dark_ratio = float(np.mean(grayscale < settings.blank_pixel_threshold))
    standard_deviation = float(np.std(grayscale))
    return dark_ratio <= settings.blank_dark_ratio and standard_deviation <= settings.blank_stddev


def _page_document(
    file_path: Path,
    page_index: int,
    text: str,
    extraction_method: str,
    ocr_result: OCRPageResult | None = None,
) -> Document:
    metadata: dict[str, str | int | float | bool] = {
        "source": str(file_path),
        "filename": file_path.name,
        "page": page_index,
        "extraction_method": extraction_method,
    }
    if ocr_result is not None:
        metadata["ocr_model"] = ocr_result.model_name
        if ocr_result.confidence is not None:
            metadata["ocr_confidence"] = float(ocr_result.confidence)
    return Document(page_content=normalize_text(text), metadata=metadata)


_CAPTION_SEARCH_PT = 70
_CAPTION_MAX_CHARS = 180
_CONTINUATION_TOP_PT = 120
_CONTINUATION_BOTTOM_PT = 120


def _table_caption(
    page: fitz.Page, bbox: tuple[float, float, float, float], other_bboxes: list | None = None
) -> str:
    """Câu dẫn ngay trên bảng ("… như sau:" hoặc "Bảng N. …"), để dòng bảng không mất ngữ cảnh.

    Không có câu dẫn rõ ràng thì trả về chuỗi rỗng, tránh gắn nhầm một đoạn văn bất kỳ.
    """
    top = bbox[1]
    # Bỏ chữ nằm trong các bảng khác (vd. dòng cuối của bảng ngay phía trên).
    others = [fitz.Rect(other) for other in (other_bboxes or [])]
    words = [
        word for word in page.get_text("words", sort=True)
        if top - _CAPTION_SEARCH_PT <= word[3] <= top + 1
        and not any(
            rect.contains(fitz.Point((word[0] + word[2]) / 2, (word[1] + word[3]) / 2))
            for rect in others
        )
    ]
    text = normalize_text(" ".join(word[4] for word in words))
    if not text:
        return ""
    # Cắt ở dấu kết câu cuối cùng không phải số thứ tự ("6." hay "a)").
    start = 0
    for match in re.finditer(r"[.;!?]\s+", text):
        before = text[:match.start() + 1].split()[-1].rstrip(".;!?")
        if re.fullmatch(r"\d{1,2}|[a-zđ]", before, re.IGNORECASE):
            continue
        start = match.end()
    sentence = text[start:].strip()
    sentence = re.sub(r"^(?:\d{1,2}\s*[.)]|[a-zđ]\))\s*", "", sentence, flags=re.IGNORECASE)
    if not (sentence.endswith(":") or re.match(r"(?:bảng|biểu|table)\b", sentence, re.IGNORECASE)):
        return ""
    sentence = re.sub(r"\s*(?:cụ thể\s+)?(?:như sau|sau đây)?\s*:\s*$", "", sentence, flags=re.IGNORECASE)
    sentence = sentence.rstrip(" ,;").strip()
    # Câu dẫn thật ngắn gọn; một đoạn dài là văn bản thường chứ không phải tên bảng.
    return sentence if len(sentence) <= _CAPTION_MAX_CHARS else ""


def _is_table_continuation(
    page: fitz.Page, table: "fitz.table.Table", rows: list, previous: dict | None, page_index: int
) -> bool:
    """Bảng đầu trang tiếp nối bảng cuối trang trước: cùng số cột và không lặp lại dòng tiêu đề."""
    if not previous or previous["page"] != page_index - 1 or table.col_count != previous["columns"]:
        return False
    if not previous["ends_low"] or table.bbox[1] > _CONTINUATION_TOP_PT:
        return False
    first_row = [normalize_text(cell) for cell in rows[0]]
    if first_row and first_row[0].lower() in {"tt", "stt"}:
        return False  # dòng đầu là tiêu đề của một bảng mới
    repeated_header = [normalize_text(h).lower() for h in previous["raw_headers"]]
    return [cell.lower() for cell in first_row] != repeated_header


def _native_table_documents(
    page: fitz.Page, file_path: Path, page_index: int, state: dict | None = None
) -> tuple[list[Document], list[fitz.Rect]]:
    """Keep native PDF table headers attached to their individual cells.

    `state` (do _load_pdf_pages giữ qua các trang) cho phép nối bảng bị ngắt giữa hai trang:
    phần tiếp theo không có dòng tiêu đề nên dùng lại tiêu đề, câu dẫn và ô gộp dọc của phần trước.
    """
    if state is None:
        state = {}
    try:
        tables = page.find_tables().tables
    except Exception as exc:
        logger.warning("Không thể nhận diện bảng ở trang {} của {}: {}", page_index + 1, file_path.name, exc)
        state.pop("last", None)
        return [], []

    documents: list[Document] = []
    bounds: list[fitz.Rect] = []
    last_on_this_page: dict | None = None
    for table_index, table in enumerate(tables):
        rows = table.extract()
        column_count = table.col_count
        if column_count < 2 or len(rows) < 1:
            continue
        previous = state.get("last") if table_index == 0 else None
        continuation = len(rows) >= 1 and _is_table_continuation(page, table, rows, previous, page_index)
        if not continuation and len(rows) < 2:
            continue

        if continuation:
            raw_headers = list(previous["raw_headers"])
            caption = previous["caption"]
            carried_first = previous["carried_first"]
            header_end = 0
        else:
            caption = _table_caption(
                page, table.bbox, [other.bbox for other in tables if other is not table]
            )
            carried_first = ""
            # Some PDF headers span several physical rows. A continuation row
            # fills blank header cells or contains only a small fragment such as
            # the level number; the first populated data row ends the header.
            header_end = 1
            if any(not normalize_text(cell) for cell in rows[0]):
                for row in rows[1:4]:
                    first = normalize_text(row[0]) if row else ""
                    filled = sum(bool(normalize_text(cell)) for cell in row)
                    if first.isdigit() or (filled > column_count // 2 and first.lower() != "tt"):
                        break
                    header_end += 1
            raw_headers = [
                normalize_text(" ".join(
                    str(row[column]) for row in rows[:header_end]
                    if column < len(row) and normalize_text(row[column])
                ))
                for column in range(column_count)
            ]
        headers = [heading or f"Cột {column + 1}" for column, heading in enumerate(raw_headers)]
        # Ô tiêu đề gộp ngang (vd. "Xếp loại" trải trên 2 cột) để trống ở cột sau: coi các cột đó
        # là một nhóm, giá trị được nối lại thay vì thành "Cột 2".
        group_of = list(range(column_count))
        for column in range(1, column_count):
            if not raw_headers[column] and raw_headers[column - 1]:
                group_of[column] = group_of[column - 1]
            elif not raw_headers[column] and group_of[column - 1] != column - 1:
                group_of[column] = group_of[column - 1]
        grouped = len(set(group_of)) < column_count

        level_columns = [
            column for column, heading in enumerate(headers)
            if re.search(r"\b(?:bậc|bac|level|mức)\s*\d+\b", heading, re.IGNORECASE)
        ]
        # A multi-level table gets one searchable document per value cell;
        # ordinary tables get one document per row with labeled columns.
        separate_levels = len(level_columns) >= 2
        context_columns = [
            column for column in range(column_count)
            if column not in level_columns
        ] if separate_levels else list(range(column_count))
        carried = [""] * column_count
        carried[0] = carried_first
        table_documents: list[Document] = []
        prefix = f"[{caption}] " if caption else ""
        for row_index, row in enumerate(rows[header_end:], start=header_end):
            values = [
                re.sub(r"(?<=\d)-\s+(?=\d)", "-", normalize_text(row[column]))
                if column < len(row) else ""
                for column in range(column_count)
            ]
            if not any(values):
                continue
            # Ô gộp dọc ở cột đầu (vd. "Đạt" bao trùm nhiều dòng) chỉ có giá trị ở dòng đầu tiên.
            if not values[0] and raw_headers[0].lower() not in {"tt", "stt"} and carried[0]:
                values[0] = carried[0]
            for column in context_columns:
                if values[column]:
                    carried[column] = values[column]
            if separate_levels:
                context = [
                    f"{headers[column]}: {carried[column]}"
                    for column in context_columns if carried[column] and headers[column] != "TT"
                ]
                for column in level_columns:
                    if not values[column]:
                        continue
                    text = prefix + "; ".join([*context, f"{headers[column]}: {values[column]}"])
                    doc = _page_document(file_path, page_index, text, "native_table")
                    doc.metadata.update(table_index=table_index, table_row=row_index, table_column=column)
                    if caption:
                        doc.metadata["table_caption"] = caption
                    level = re.search(r"\b(?:bậc|bac|level|mức)\s*(\d+)\b", headers[column], re.IGNORECASE)
                    if level:
                        doc.metadata["table_level"] = int(level.group(1))
                    table_documents.append(doc)
            else:
                if grouped:
                    parts: list[str] = []
                    for group in dict.fromkeys(group_of):
                        members = [values[c] for c in range(column_count) if group_of[c] == group and values[c]]
                        if members:
                            parts.append(f"{headers[group]}: {' - '.join(members)}")
                else:
                    parts = [
                        f"{headers[column]}: {values[column]}"
                        for column in range(column_count) if values[column]
                    ]
                doc = _page_document(file_path, page_index, prefix + "; ".join(parts), "native_table")
                doc.metadata.update(table_index=table_index, table_row=row_index)
                if caption:
                    doc.metadata["table_caption"] = caption
                if continuation:
                    doc.metadata["table_continued"] = True
                table_documents.append(doc)
        if table_documents:
            documents.extend(table_documents)
            bounds.append(fitz.Rect(table.bbox))
            last_on_this_page = {
                "page": page_index,
                "columns": column_count,
                "raw_headers": raw_headers,
                "caption": caption,
                "carried_first": carried[0],
                "ends_low": table.bbox[3] >= page.rect.height - _CONTINUATION_BOTTOM_PT,
            }
    if last_on_this_page is not None:
        state["last"] = last_on_this_page
    else:
        state.pop("last", None)
    return documents, bounds


def _native_text_outside_tables(page: fitz.Page, bounds: list[fitz.Rect]) -> str:
    """Remove flattened table words while keeping text around the table."""
    words = page.get_text("words", sort=True)
    kept = [
        word[4]
        for word in words
        if not any(
            rect.contains(fitz.Point((word[0] + word[2]) / 2, (word[1] + word[3]) / 2))
            for rect in bounds
        )
    ]
    return normalize_text(" ".join(kept))


def _load_pdf_pages(
    file_path: Path,
    settings: IngestionSettings,
    ocr_service: OCRServiceProtocol | None,
    cache: OCRResultCache,
) -> tuple[list[Document], list[str], list[Path], str]:
    file_hash = sha256_file(file_path)
    pages: list[Document] = []
    warnings: list[str] = []
    created_cache_files: list[Path] = []
    failed_pages: list[int] = []
    service = ocr_service

    try:
        table_state: dict = {}
        with fitz.open(file_path) as pdf:
            for page_index, page in enumerate(pdf):
                native_text = normalize_text(page.get_text("text"))
                if len(native_text) >= settings.native_text_threshold:
                    table_documents, table_bounds = _native_table_documents(
                        page, file_path, page_index, table_state
                    )
                    if table_documents:
                        prose = _native_text_outside_tables(page, table_bounds)
                        if has_sane_text(prose, settings.sanity_min_chars):
                            pages.append(_page_document(file_path, page_index, prose, "native"))
                        pages.extend(table_documents)
                    else:
                        pages.append(_page_document(file_path, page_index, native_text, "native"))
                    continue

                native_is_sane = has_sane_text(native_text, settings.sanity_min_chars)
                image = _render_page(page, settings.dpi)
                if not native_is_sane and is_confidently_blank(image, settings):
                    warnings.append(f"Bỏ qua trang trắng {page_index + 1} của {file_path.name}")
                    continue

                if not settings.ocr_enabled:
                    if native_is_sane:
                        pages.append(
                            _page_document(file_path, page_index, native_text, "native_low_text")
                        )
                        warnings.append(
                            f"Giữ native text ngắn ở trang {page_index + 1} vì OCR đang tắt"
                        )
                    else:
                        failed_pages.append(page_index + 1)
                    continue

                if service is None:
                    service = get_default_ocr_service()
                fingerprint = service.cache_fingerprint
                ocr_result = cache.read(file_hash, page_index, settings.dpi, fingerprint)
                if ocr_result is None:
                    try:
                        ocr_result = service.recognize_page(image)
                    except OCRConfigurationError as exc:
                        if native_is_sane:
                            pages.append(_page_document(file_path, page_index, native_text, "native_low_text"))
                            warnings.append(f"Giữ native text trang {page_index + 1}: {exc}")
                            continue
                        raise DocumentIngestionError(
                            str(exc), failed_pages=[page_index + 1],
                            created_cache_files=created_cache_files,
                        ) from exc
                    except Exception as exc:
                        logger.warning(
                            "OCR thất bại ở trang {} của {}: {}",
                            page_index + 1,
                            file_path.name,
                            type(exc).__name__,
                        )
                        if native_is_sane:
                            pages.append(
                                _page_document(
                                    file_path, page_index, native_text, "native_low_text"
                                )
                            )
                            warnings.append(
                                f"Giữ native text ngắn ở trang {page_index + 1} do OCR thất bại"
                            )
                        else:
                            failed_pages.append(page_index + 1)
                        continue
                    try:
                        cache_path = cache.write(
                            file_hash, page_index, settings.dpi, fingerprint, ocr_result
                        )
                        created_cache_files.append(cache_path)
                    except Exception as exc:
                        # Cache is an optimization. A valid OCR result must not be
                        # discarded just because its derived cache cannot be written.
                        logger.warning(
                            "Không thể ghi OCR cache cho trang {} của {}: {}",
                            page_index + 1,
                            file_path.name,
                            type(exc).__name__,
                        )

                if has_sane_text(ocr_result.text, settings.sanity_min_chars):
                    pages.append(
                        _page_document(
                            file_path, page_index, ocr_result.text,
                            "tesseract" if fingerprint.get("provider") == "tesseract" else "ppocrv6",
                            ocr_result,
                        )
                    )
                elif native_is_sane:
                    pages.append(
                        _page_document(file_path, page_index, native_text, "native_low_text")
                    )
                    warnings.append(
                        f"Giữ native text ngắn ở trang {page_index + 1} vì OCR không có text hợp lệ"
                    )
                else:
                    failed_pages.append(page_index + 1)
    except DocumentIngestionError:
        raise
    except Exception as exc:
        raise DocumentIngestionError(
            f"Không thể đọc PDF '{file_path.name}': {exc}",
            created_cache_files=created_cache_files,
        ) from exc

    if failed_pages:
        raise DocumentIngestionError(
            f"Không thể trích xuất nội dung hợp lệ từ '{file_path.name}'.",
            failed_pages=failed_pages,
            created_cache_files=created_cache_files,
        )
    return pages, warnings, created_cache_files, file_hash


def _load_docx_pages(file_path: Path, settings: IngestionSettings) -> list[Document]:
    from langchain_community.document_loaders import Docx2txtLoader

    docs = Docx2txtLoader(str(file_path)).load()
    cleaned: list[Document] = []
    for doc in docs:
        text = normalize_text(doc.page_content)
        # Preserve the pre-OCR behavior for DOCX: short/empty documents are not indexed.
        if len(text) <= settings.native_text_threshold:
            continue
        metadata = dict(doc.metadata or {})
        metadata.update(
            {
                "source": str(file_path),
                "filename": file_path.name,
                "extraction_method": "native",
            }
        )
        cleaned.append(Document(page_content=text, metadata=metadata))
    return cleaned


def load_and_chunk_document(
    file_path: Path,
    ocr_service: OCRServiceProtocol | None = None,
    settings: IngestionSettings | None = None,
    cache: OCRResultCache | None = None,
) -> DocumentIngestionResult:
    settings = settings or IngestionSettings.from_env()
    cache = cache or OCRResultCache(settings.cache_path)
    extension = file_path.suffix.lower()
    warnings: list[str] = []
    created_cache_files: list[Path] = []
    file_hash: str | None = None

    if extension == ".pdf":
        pages, warnings, created_cache_files, file_hash = _load_pdf_pages(
            file_path, settings, ocr_service, cache
        )
    elif extension == ".docx":
        pages = _load_docx_pages(file_path, settings)
    else:
        raise DocumentIngestionError(f"Định dạng không được hỗ trợ: {extension}")

    if not pages:
        raise DocumentIngestionError(
            f"Không có trang nào chứa đủ văn bản hợp lệ trong '{file_path.name}'.",
            created_cache_files=created_cache_files,
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ".", ";", ":", " ", ""],
    )
    chunks = splitter.split_documents(pages)
    if not chunks:
        raise DocumentIngestionError(
            f"Không tạo được chunk nào từ '{file_path.name}'.",
            created_cache_files=created_cache_files,
        )
    annotate_chunk_metadata(chunks)

    logger.info(
        "Chunked {}: {} pages, {} text/table sections -> {} chunks (size={}, overlap={})",
        file_path.name,
        len({page.metadata.get("page") for page in pages}),
        len(pages),
        len(chunks),
        settings.chunk_size,
        settings.chunk_overlap,
    )
    return DocumentIngestionResult(
        chunks=chunks,
        warnings=warnings,
        created_cache_files=created_cache_files,
        file_sha256=file_hash,
    )


def cleanup_new_cache_entries(paths: list[Path], cache: OCRResultCache | None = None) -> None:
    (cache or OCRResultCache.from_env()).delete_entries(paths)


def cleanup_document_cache(file_path: Path, cache: OCRResultCache | None = None) -> None:
    try:
        (cache or OCRResultCache.from_env()).delete_document(file_path)
    except Exception as exc:
        logger.warning("Không thể dọn OCR cache của {}: {}", file_path.name, exc)
