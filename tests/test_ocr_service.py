import threading
import time
import unittest
import subprocess
import sys

from ocr_service import PaddleOCRService


class FakePaddleModel:
    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def predict(self, _image):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            return [{
                "rec_texts": ["Dòng sau", "Dòng trước"],
                "rec_scores": [0.8, 0.9],
                "rec_boxes": [[0, 50, 100, 70], [0, 10, 100, 30]],
            }]
        finally:
            with self.lock:
                self.active -= 1


class OCRServiceTests(unittest.TestCase):
    def test_import_is_lazy_and_does_not_import_paddleocr(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import ocr_service, sys; "
                "assert 'paddleocr' not in sys.modules; "
                "assert ocr_service.PaddleOCRService().initialization_count == 0",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_lazy_loader_initializes_once_and_reuses_model(self):
        model = FakePaddleModel()
        factory_calls = []

        def factory(config):
            factory_calls.append(config)
            return model

        service = PaddleOCRService(model_factory=factory)
        self.assertEqual(service.initialization_count, 0)

        first = service.recognize_page(object())
        second = service.recognize_page(object())

        self.assertEqual(len(factory_calls), 1)
        self.assertEqual(service.initialization_count, 1)
        self.assertEqual(first.text, "Dòng trước\nDòng sau")
        self.assertAlmostEqual(second.confidence, 0.85)
        self.assertEqual(len(first.lines), 2)
        self.assertTrue(first.lines[0].bounding_box)
        self.assertFalse(factory_calls[0]["enable_mkldnn"])
        self.assertEqual(factory_calls[0]["device"], "cpu")

    def test_ocr_concurrency_never_exceeds_one(self):
        model = FakePaddleModel(delay=0.04)
        service = PaddleOCRService(model_factory=lambda _config: model, concurrency=1)
        errors = []

        def worker():
            try:
                service.recognize_page(object())
            except Exception as exc:  # pragma: no cover - assertion captures it
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(model.max_active, 1)
        self.assertEqual(service.initialization_count, 1)


if __name__ == "__main__":
    unittest.main()
