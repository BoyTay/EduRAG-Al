"""PP-OCRv6 service with lazy model loading and bounded CPU concurrency."""

from __future__ import annotations

import importlib.metadata
import json
import os
import threading
from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable

from loguru import logger


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _primitive(value: Any) -> Any:
    """Convert NumPy/Paddle values to JSON-compatible primitives."""
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float | None
    bounding_box: list[Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "bounding_box": _primitive(self.bounding_box),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OCRLine":
        confidence = value.get("confidence")
        return cls(
            text=str(value.get("text") or ""),
            confidence=float(confidence) if confidence is not None else None,
            bounding_box=list(value.get("bounding_box") or []),
        )


@dataclass(frozen=True)
class OCRPageResult:
    text: str
    confidence: float | None
    lines: list[OCRLine]
    model_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "lines": [line.to_dict() for line in self.lines],
            "model_name": self.model_name,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OCRPageResult":
        confidence = value.get("confidence")
        return cls(
            text=str(value.get("text") or ""),
            confidence=float(confidence) if confidence is not None else None,
            lines=[OCRLine.from_dict(item) for item in value.get("lines") or []],
            model_name=str(value.get("model_name") or "unknown"),
        )


@runtime_checkable
class OCRServiceProtocol(Protocol):
    """Small interface used by document ingestion and fake unit-test engines."""

    @property
    def cache_fingerprint(self) -> dict[str, str | int | float | bool]: ...

    def recognize_page(self, image: Any) -> OCRPageResult: ...


def _result_payload(result: Any) -> dict[str, Any]:
    if hasattr(result, "json"):
        value = result.json
        value = value() if callable(value) else value
        if isinstance(value, str):
            return json.loads(value)
        if isinstance(value, dict):
            return value
    if isinstance(result, dict):
        return result
    raise TypeError(f"PaddleOCR trả kiểu kết quả không được hỗ trợ: {type(result)!r}")


def _box_sort_key(box: list[Any]) -> tuple[float, float]:
    try:
        if box and isinstance(box[0], (list, tuple)):
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            return min(ys), min(xs)
        if len(box) >= 4:
            return float(box[1]), float(box[0])
    except (TypeError, ValueError, IndexError):
        pass
    return float("inf"), float("inf")


def parse_paddle_result(result: Any, model_name: str) -> OCRPageResult:
    payload = _result_payload(result)
    data = payload.get("res", payload)
    texts = list(data.get("rec_texts") or [])
    scores = list(data.get("rec_scores") or [])
    boxes = list(data.get("rec_boxes") or data.get("rec_polys") or [])

    lines: list[OCRLine] = []
    for index, raw_text in enumerate(texts):
        text = str(raw_text or "").strip()
        if not text:
            continue
        confidence = None
        if index < len(scores) and scores[index] is not None:
            confidence = float(scores[index])
        box = _primitive(boxes[index]) if index < len(boxes) else []
        lines.append(OCRLine(text=text, confidence=confidence, bounding_box=list(box)))

    lines.sort(key=lambda line: _box_sort_key(line.bounding_box))
    confidences = [line.confidence for line in lines if line.confidence is not None]
    mean_confidence = sum(confidences) / len(confidences) if confidences else None
    return OCRPageResult(
        text="\n".join(line.text for line in lines),
        confidence=mean_confidence,
        lines=lines,
        model_name=model_name,
    )


class PaddleOCRService:
    """Lazy singleton-compatible PP-OCRv6 Small service for CPU inference."""

    def __init__(
        self,
        model_factory: Callable[[dict[str, Any]], Any] | None = None,
        concurrency: int = 1,
    ) -> None:
        self.detection_model = os.getenv("OCR_DETECTION_MODEL", "PP-OCRv6_small_det")
        self.recognition_model = os.getenv("OCR_RECOGNITION_MODEL", "PP-OCRv6_small_rec")
        self.device = os.getenv("OCR_DEVICE", "cpu")
        self.enable_mkldnn = _as_bool(os.getenv("OCR_ENABLE_MKLDNN"), False)
        self._model_factory = model_factory or self._create_paddle_model
        self._model: Any | None = None
        self._load_lock = threading.Lock()
        self._inference_semaphore = threading.Semaphore(max(1, concurrency))
        self._initialization_count = 0

    @property
    def cache_fingerprint(self) -> dict[str, str | int | float | bool]:
        try:
            paddleocr_version = importlib.metadata.version("paddleocr")
        except importlib.metadata.PackageNotFoundError:
            paddleocr_version = "not-installed"
        try:
            paddlepaddle_version = importlib.metadata.version("paddlepaddle")
        except importlib.metadata.PackageNotFoundError:
            paddlepaddle_version = "not-installed"
        return {
            "provider": "paddleocr",
            "version": paddleocr_version,
            "runtime_version": paddlepaddle_version,
            "ocr_version": "PP-OCRv6",
            "lang": "vi",
            "detection_model": self.detection_model,
            "recognition_model": self.recognition_model,
            "device": self.device,
            "enable_mkldnn": self.enable_mkldnn,
            "doc_orientation": False,
            "doc_unwarping": False,
            "textline_orientation": False,
        }

    @property
    def initialization_count(self) -> int:
        return self._initialization_count

    def _create_paddle_model(self, config: dict[str, Any]) -> Any:
        # Deliberately imported here: text PDFs, DOCX and OCR-disabled mode must
        # not import PaddleOCR or download a model during backend startup.
        from paddleocr import PaddleOCR

        return PaddleOCR(**config)

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is None:
                logger.info(
                    "Khởi tạo PP-OCRv6 Small trên thiết bị {} (lazy-load)",
                    self.device,
                )
                config = {
                    "lang": "vi",
                    "ocr_version": "PP-OCRv6",
                    "text_detection_model_name": self.detection_model,
                    "text_recognition_model_name": self.recognition_model,
                    "use_doc_orientation_classify": False,
                    "use_doc_unwarping": False,
                    "use_textline_orientation": False,
                    # Workaround verified for PaddlePaddle 3.3.0 + PaddleOCR
                    # 3.7.0. Re-test before changing either dependency.
                    "enable_mkldnn": self.enable_mkldnn,
                    "device": self.device,
                }
                self._model = self._model_factory(config)
                self._initialization_count += 1
        return self._model

    def recognize_page(self, image: Any) -> OCRPageResult:
        with self._inference_semaphore:
            model = self._get_model()
            results = list(model.predict(image))
        if not results:
            raise RuntimeError("PP-OCRv6 không trả kết quả cho trang")
        return parse_paddle_result(
            results[0],
            f"{self.detection_model}+{self.recognition_model}",
        )


_default_service: PaddleOCRService | None = None
_default_service_lock = threading.Lock()


def get_default_ocr_service() -> PaddleOCRService:
    global _default_service
    if _default_service is None:
        with _default_service_lock:
            if _default_service is None:
                _default_service = PaddleOCRService(concurrency=1)
    return _default_service
