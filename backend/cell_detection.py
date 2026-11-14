"""Tìm vị trí các ô/dòng chữ trên ảnh trang để Tesseract đọc từng ô.

Chỉ dùng phần *phát hiện* (detection) của PaddleOCR. Phần *nhận dạng* của PP-OCRv6 thiếu
nhiều ký tự tiếng Việt (docs/ocr_vietnamese_charset_issue.md), nên chữ vẫn do Tesseract đọc.
Paddle được nạp lười ở lần dùng đầu; nạp lỗi (thiếu thư viện, thiếu mô hình khi offline)
thì trả None để OCR quay về psm 3 thay vì làm hỏng việc nạp tài liệu.
"""
from __future__ import annotations

import os
import threading
from typing import Protocol

import numpy as np
from loguru import logger

Box = list[int]  # [x0, y0, x1, y1] theo pixel của ảnh đầu vào


class CellDetector(Protocol):
    name: str

    def detect(self, pixels: np.ndarray) -> list[Box] | None: ...


def polygons_to_boxes(polygons) -> list[Box]:
    """Đa giác bao chữ của Paddle → hình chữ nhật [x0, y0, x1, y1]."""
    boxes = []
    for polygon in polygons:
        points = np.asarray(polygon)
        if points.size == 0:
            continue
        boxes.append([int(points[:, 0].min()), int(points[:, 1].min()),
                      int(points[:, 0].max()), int(points[:, 1].max())])
    return boxes


class PaddleCellDetector:
    def __init__(self, model_name: str = "PP-OCRv6_small_det") -> None:
        self.name = model_name
        self._model = None
        self._unavailable = False
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None and not self._unavailable:
                try:
                    from paddleocr import TextDetection

                    self._model = TextDetection(
                        model_name=self.name,
                        device=os.getenv("OCR_DEVICE", "cpu"),
                        enable_mkldnn=os.getenv("OCR_ENABLE_MKLDNN", "false").strip().lower() in {"1", "true", "yes", "on"},
                    )
                except Exception as exc:  # thiếu thư viện/mô hình: dùng psm 3 thay thế
                    self._unavailable = True
                    logger.warning("Không nạp được bộ phát hiện ô chữ {}: {}", self.name, exc)
        return self._model

    def detect(self, pixels: np.ndarray) -> list[Box] | None:
        model = self._load()
        if model is None:
            return None
        rgb = pixels if pixels.ndim == 3 else np.stack([pixels] * 3, axis=2)
        try:
            output = next(iter(model.predict(np.ascontiguousarray(rgb))))
            return polygons_to_boxes(output["dt_polys"])
        except Exception as exc:
            logger.warning("Phát hiện ô chữ thất bại: {}", type(exc).__name__)
            return None


def default_cell_detector() -> CellDetector | None:
    """OCR_CELL_DETECTOR=paddle (mặc định) hoặc none để tắt."""
    choice = os.getenv("OCR_CELL_DETECTOR", "paddle").strip().lower()
    if choice in {"none", "off", "false", "0"}:
        return None
    return PaddleCellDetector()
