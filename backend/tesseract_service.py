"""Vietnamese CPU OCR with in-memory PNG input and structured TSV output."""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import unicodedata

import numpy as np

from cell_detection import CellDetector, default_cell_detector
from ocr_service import OCRConfigurationError, OCRLine, OCRPageResult


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def read_tesseract_psm() -> int:
    """Use a predictable text-block mode while allowing an explicit override."""
    try:
        value = int(os.getenv("OCR_TESSERACT_PSM", "6"))
    except ValueError:
        return 6
    return value if value in {3, 4, 6, 11, 12} else 6


def prepare_tesseract_image(image, remove_colored_overlays: bool = True) -> np.ndarray:
    """Keep dark document text while whitening colored stamps and annotations.

    Taking the brightest RGB channel preserves black/gray glyphs, but makes a
    saturated red or blue stamp nearly white. This prevents a stamp crossing a
    line from changing Vietnamese words or hiding a list item. The behavior is
    configurable for documents whose primary text is intentionally colored.
    """
    pixels = np.asarray(image)
    if not remove_colored_overlays or pixels.ndim != 3 or pixels.shape[2] < 3:
        return pixels
    return np.max(pixels[:, :, :3], axis=2).astype(np.uint8)


# OSD của Tesseract cho điểm tin cậy hướng trang; dưới ngưỡng này coi như chưa biết hướng.
MIN_OSD_CONFIDENCE = 1.0
# Trang chưa biết hướng mà OCR tin cậy thấp hơn ngưỡng này thì thử đủ 4 hướng.
LOW_OCR_CONFIDENCE = 0.6
ROTATIONS = (0, 90, 180, 270)
# psm 6 coi cả trang là một khối chữ: tốt cho văn xuôi nhưng bỏ sót bảng, poster. Trang đọc
# kém hơn ngưỡng này được đọc lại bằng psm 3 (tự phân tích bố cục), giữ bản tin cậy hơn.
# Đo 14/11/2026: trang văn xuôi 0,92–0,95 (không đọc lại); bảng scan 0,75 → 0,83 với psm 3.
LAYOUT_RETRY_CONFIDENCE = 0.85
LAYOUT_RETRY_PSM = 3
# Trang vẫn kém thì tìm từng ô chữ (Paddle) rồi đọc từng ô bằng psm 7 (một dòng chữ), ghép theo
# hàng. Cách này giữ được từng dòng bảng nên được ưu tiên trừ khi kém hơn hẳn psm 3.
# Đo 14/11/2026 trên bảng trang 5 (15 dòng): cùng dòng đơn vị + lãnh đạo 4/15 → 14/15.
CELL_PSM = 7
CELL_PADDING = 6
CELL_PREFERENCE_MARGIN = 0.05
ROW_OVERLAP = 0.6


def _confidence(result: OCRPageResult) -> float:
    return result.confidence or 0.0


def parse_osd_rotation(osd: str) -> int | None:
    """Số độ cần xoay theo chiều kim đồng hồ để trang đứng thẳng; None nếu OSD không chắc."""
    rotate = re.search(r"^Rotate:\s*(\d+)", osd, re.MULTILINE)
    confidence = re.search(r"^Orientation confidence:\s*([\d.]+)", osd, re.MULTILINE)
    if not rotate or not confidence or float(confidence.group(1)) < MIN_OSD_CONFIDENCE:
        return None
    degrees = int(rotate.group(1)) % 360
    return degrees if degrees in ROTATIONS else None


def rotate_image(pixels: np.ndarray, degrees: int) -> np.ndarray:
    """Xoay ảnh theo chiều kim đồng hồ (np.rot90 xoay ngược chiều nên dùng k âm)."""
    return np.ascontiguousarray(np.rot90(pixels, k=-(degrees // 90)))


def group_cells_into_rows(cells: list[OCRLine]) -> list[OCRLine]:
    """Gom các ô có tâm dọc gần nhau thành một hàng, xếp trái → phải, nối bằng " | "."""
    def center(cell: OCRLine) -> float:
        return (cell.bounding_box[1] + cell.bounding_box[3]) / 2

    def height(cell: OCRLine) -> float:
        return cell.bounding_box[3] - cell.bounding_box[1]

    rows: list[list[OCRLine]] = []
    for cell in sorted(cells, key=center):
        previous = rows[-1][-1] if rows else None
        if previous is None or abs(center(cell) - center(previous)) > ROW_OVERLAP * max(height(cell), height(previous)):
            rows.append([])
        rows[-1].append(cell)
    lines = []
    for row in rows:
        row.sort(key=lambda cell: cell.bounding_box[0])
        confidences = [cell.confidence for cell in row if cell.confidence is not None]
        lines.append(OCRLine(
            text=" | ".join(cell.text for cell in row),
            confidence=sum(confidences) / len(confidences) if confidences else None,
            bounding_box=[min(cell.bounding_box[0] for cell in row), min(cell.bounding_box[1] for cell in row),
                          max(cell.bounding_box[2] for cell in row), max(cell.bounding_box[3] for cell in row)],
        ))
    return lines


def parse_tesseract_tsv(tsv: str) -> OCRPageResult:
    groups: dict[tuple[str, ...], list[tuple[str, float, list[int]]]] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row.get("level") != "5" or not (row.get("text") or "").strip():
            continue
        confidence = float(row["conf"])
        if confidence < 0:
            continue
        left, top, width, height = (int(row[key]) for key in ("left", "top", "width", "height"))
        key = tuple(row[name] for name in ("page_num", "block_num", "par_num", "line_num"))
        groups.setdefault(key, []).append((
            unicodedata.normalize("NFC", row["text"].strip()),
            confidence / 100.0, [left, top, left + width, top + height],
        ))
    lines = []
    for words in groups.values():
        lines.append(OCRLine(
            text=" ".join(word[0] for word in words),
            confidence=sum(word[1] for word in words) / len(words),
            bounding_box=[min(word[2][0] for word in words), min(word[2][1] for word in words),
                          max(word[2][2] for word in words), max(word[2][3] for word in words)],
        ))
    return OCRPageResult(
        text="\n".join(line.text for line in lines),
        confidence=sum(line.confidence for line in lines) / len(lines) if lines else None,
        lines=lines, model_name="tesseract-vie",
    )


class TesseractOCRService:
    def __init__(self, cell_detector: CellDetector | None | str = "default") -> None:
        self._fingerprint = None
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(1)
        self._binary = None
        self.psm = read_tesseract_psm()
        self.remove_colored_overlays = _env_bool(
            "OCR_TESSERACT_REMOVE_COLORED_OVERLAYS", True
        )
        self.cell_detector = default_cell_detector() if cell_detector == "default" else cell_detector

    @property
    def cache_fingerprint(self) -> dict:
        with self._lock:
            if self._fingerprint is None:
                self._binary = shutil.which("tesseract")
                if self._binary is None:
                    raise OCRConfigurationError("Thiếu Tesseract; cần build backend với tesseract-ocr và tesseract-ocr-vie.")
                version = subprocess.run([self._binary, "--version"], capture_output=True, check=True, timeout=15)
                listing = subprocess.run([self._binary, "--list-langs"], capture_output=True, check=True, timeout=15)
                text = (listing.stdout + listing.stderr).decode("utf-8", errors="replace")
                if "vie" not in text.splitlines():
                    raise OCRConfigurationError("Tesseract thiếu dữ liệu ngôn ngữ vie (tiếng Việt).")
                match = re.search(r'List of available languages in "([^"]+)"', text)
                if not match:
                    raise OCRConfigurationError("Không xác minh được thư mục dữ liệu Tesseract.")
                traineddata = Path(match.group(1)) / "vie.traineddata"
                digest = hashlib.sha256(traineddata.read_bytes()).hexdigest()
                self._fingerprint = {
                    "provider": "tesseract", "version": version.stdout.decode().splitlines()[0],
                    "lang": "vie", "traineddata_sha256": digest, "psm": self.psm, "oem": 1,
                    "remove_colored_overlays": self.remove_colored_overlays,
                    "parser_revision": 2,
                    # Kết quả cũ đọc trang nằm ngang sai hướng; đổi khóa để không dùng lại cache đó.
                    "orientation": "osd",
                    "layout_retry_psm": LAYOUT_RETRY_PSM,
                    "cell_detector": self.cell_detector.name if self.cell_detector else None,
                }
        return dict(self._fingerprint)

    def recognize_page(self, image) -> OCRPageResult:
        self.cache_fingerprint
        with self._semaphore:
            prepared_image = prepare_tesseract_image(image, self.remove_colored_overlays)
            rotation = self._detect_rotation(prepared_image)
            upright = rotate_image(prepared_image, rotation or 0)
            result = self._recognize(upright)
            if rotation is None and _confidence(result) < LOW_OCR_CONFIDENCE:
                # OSD không chắc (ít chữ, nhiều bảng): đọc thử các hướng còn lại, giữ bản tin cậy nhất.
                for degrees in ROTATIONS[1:]:
                    image_at = rotate_image(prepared_image, degrees)
                    candidate = self._try_recognize(image_at)
                    if candidate is not None and _confidence(candidate) > _confidence(result):
                        upright, result = image_at, candidate
            if _confidence(result) < LAYOUT_RETRY_CONFIDENCE:
                if self.psm != LAYOUT_RETRY_PSM:
                    candidate = self._try_recognize(upright, LAYOUT_RETRY_PSM)
                    if candidate is not None and _confidence(candidate) > _confidence(result):
                        result = candidate
                cells = self._read_cells(upright)
                if cells is not None and _confidence(cells) >= _confidence(result) - CELL_PREFERENCE_MARGIN:
                    result = cells
        return result

    def _read_cells(self, pixels: np.ndarray) -> OCRPageResult | None:
        """Đọc từng ô chữ do bộ phát hiện tìm được; None nếu không có bộ phát hiện hoặc không đọc được ô nào."""
        if self.cell_detector is None:
            return None
        boxes = self.cell_detector.detect(pixels)
        if not boxes:
            return None
        height, width = pixels.shape[:2]
        cells = []
        for x0, y0, x1, y1 in boxes:
            crop = pixels[max(0, y0 - CELL_PADDING):min(height, y1 + CELL_PADDING),
                          max(0, x0 - CELL_PADDING):min(width, x1 + CELL_PADDING)]
            if crop.size == 0:
                continue
            read = self._try_recognize(np.ascontiguousarray(crop), CELL_PSM)
            text = " ".join((read.text if read else "").split())
            if text:
                cells.append(OCRLine(text=text, confidence=read.confidence, bounding_box=[x0, y0, x1, y1]))
        rows = group_cells_into_rows(cells)
        if not rows:
            return None
        confidences = [cell.confidence for cell in cells if cell.confidence is not None]
        return OCRPageResult(
            text="\n".join(row.text for row in rows),
            confidence=sum(confidences) / len(confidences) if confidences else None,
            lines=rows, model_name=f"{self.cell_detector.name}+tesseract-vie",
        )

    def _try_recognize(self, pixels: np.ndarray, psm: int | None = None) -> OCRPageResult | None:
        """Lần đọc bổ sung: lỗi (vd. quá thời gian) thì bỏ qua, không làm mất cả trang."""
        try:
            return self._recognize(pixels, psm)
        except RuntimeError:
            return None

    @staticmethod
    def _to_png(pixels: np.ndarray) -> bytes:
        from PIL import Image

        output = io.BytesIO()
        Image.fromarray(pixels).save(output, format="PNG")
        return output.getvalue()

    def _run(
        self, png: bytes, psm: int, options: tuple[str, ...] = (), configs: tuple[str, ...] = ()
    ) -> subprocess.CompletedProcess:
        # No image files or document content are written to logs/disk.
        # Tesseract yêu cầu tệp cấu hình (vd. "tsv") đứng sau mọi tùy chọn.
        return subprocess.run(
            [self._binary, "stdin", "stdout", *options, "--psm", str(psm), *configs],
            input=png, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True, timeout=180, env={**os.environ, "OMP_THREAD_LIMIT": "1"},
        )

    def _detect_rotation(self, pixels: np.ndarray) -> int | None:
        """Hướng trang theo OSD của Tesseract; None khi OSD thất bại hoặc không chắc."""
        try:
            completed = self._run(self._to_png(pixels), 0)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        return parse_osd_rotation(completed.stdout.decode("utf-8", errors="replace"))

    def _recognize(self, pixels: np.ndarray, psm: int | None = None) -> OCRPageResult:
        try:
            completed = self._run(
                self._to_png(pixels), psm or self.psm, ("-l", "vie", "--oem", "1"), ("tsv",)
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("Tesseract không hoàn tất nhận dạng trang") from exc
        return parse_tesseract_tsv(completed.stdout.decode("utf-8"))
