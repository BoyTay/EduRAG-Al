import sys
import unittest
from unittest.mock import patch

import numpy as np

from cell_detection import PaddleCellDetector, default_cell_detector, polygons_to_boxes


class PolygonsToBoxesTests(unittest.TestCase):
    def test_polygon_becomes_enclosing_rectangle(self):
        polygon = [[10, 20], [110, 18], [112, 40], [9, 42]]
        self.assertEqual(polygons_to_boxes([polygon]), [[9, 18, 112, 42]])

    def test_empty_polygon_is_skipped(self):
        self.assertEqual(polygons_to_boxes([[]]), [])


class DefaultCellDetectorTests(unittest.TestCase):
    def test_paddle_is_default(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsInstance(default_cell_detector(), PaddleCellDetector)

    def test_can_be_disabled(self):
        with patch.dict("os.environ", {"OCR_CELL_DETECTOR": "none"}, clear=True):
            self.assertIsNone(default_cell_detector())


class PaddleUnavailableTests(unittest.TestCase):
    def test_missing_paddle_returns_none_instead_of_failing(self):
        detector = PaddleCellDetector()
        with patch.dict(sys.modules, {"paddleocr": None}):  # import paddleocr → ImportError
            self.assertIsNone(detector.detect(np.zeros((4, 4), dtype=np.uint8)))
            self.assertIsNone(detector.detect(np.zeros((4, 4), dtype=np.uint8)))

    def test_detection_error_on_one_page_returns_none(self):
        class BrokenModel:
            def predict(self, image):
                raise RuntimeError("bad page")

        detector = PaddleCellDetector()
        detector._model = BrokenModel()
        self.assertIsNone(detector.detect(np.zeros((4, 4), dtype=np.uint8)))

    def test_grayscale_page_is_given_to_model_as_rgb(self):
        seen = []

        class Model:
            def predict(self, image):
                seen.append(image.shape)
                return iter([{"dt_polys": [[[0, 0], [2, 0], [2, 1], [0, 1]]]}])

        detector = PaddleCellDetector()
        detector._model = Model()
        self.assertEqual(detector.detect(np.zeros((4, 5), dtype=np.uint8)), [[0, 0, 2, 1]])
        self.assertEqual(seen, [(4, 5, 3)])
