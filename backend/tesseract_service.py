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
    def __init__(self) -> None:
        self._fingerprint = None
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(1)
        self._binary = None
        self.psm = read_tesseract_psm()
        self.remove_colored_overlays = _env_bool(
            "OCR_TESSERACT_REMOVE_COLORED_OVERLAYS", True
        )

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
                }
        return dict(self._fingerprint)

    def recognize_page(self, image) -> OCRPageResult:
        from PIL import Image

        self.cache_fingerprint
        with self._semaphore:
            output = io.BytesIO()
            prepared_image = prepare_tesseract_image(
                image, self.remove_colored_overlays
            )
            Image.fromarray(prepared_image).save(output, format="PNG")
            # No image files or document content are written to logs/disk.
            try:
                result = subprocess.run(
                    [
                        self._binary, "stdin", "stdout", "-l", "vie",
                        "--oem", "1", "--psm", str(self.psm), "tsv",
                    ],
                    input=output.getvalue(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    check=True, timeout=180, env={**os.environ, "OMP_THREAD_LIMIT": "1"},
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError("Tesseract không hoàn tất nhận dạng trang") from exc
        return parse_tesseract_tsv(result.stdout.decode("utf-8"))
