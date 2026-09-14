import unittest
from unittest.mock import patch

import numpy as np

from tesseract_service import (
    parse_tesseract_tsv,
    prepare_tesseract_image,
    read_tesseract_psm,
)


class TesseractParsingTests(unittest.TestCase):
    def test_preserves_accents_confidence_and_combines_word_boxes(self):
        header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        rows = (
            "5\t1\t1\t1\t1\t1\t10\t20\t20\t10\t90\tđồng\n"
            "5\t1\t1\t1\t1\t2\t35\t20\t25\t10\t98\tchẵn\n"
            "5\t1\t1\t1\t2\t1\t10\t40\t30\t10\t96\ttriệu\n"
        )
        result = parse_tesseract_tsv(header + rows)
        self.assertEqual(result.text, "đồng chẵn\ntriệu")
        self.assertEqual(result.lines[0].bounding_box, [10, 20, 60, 30])
        self.assertAlmostEqual(result.lines[0].confidence, 0.94)

    def test_empty_output_does_not_invent_text(self):
        result = parse_tesseract_tsv("level\ttext\n1\t\n")
        self.assertEqual(result.text, "")
        self.assertIsNone(result.confidence)

    def test_psm_6_is_default_and_invalid_override_falls_back(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(read_tesseract_psm(), 6)
        with patch.dict("os.environ", {"OCR_TESSERACT_PSM": "99"}, clear=True):
            self.assertEqual(read_tesseract_psm(), 6)
        with patch.dict("os.environ", {"OCR_TESSERACT_PSM": "11"}, clear=True):
            self.assertEqual(read_tesseract_psm(), 11)

    def test_colored_overlay_removal_preserves_black_text_pixels(self):
        image = np.array([[[0, 0, 0], [120, 120, 120], [255, 0, 0]]], dtype=np.uint8)
        prepared = prepare_tesseract_image(image)
        self.assertEqual(prepared.tolist(), [[0, 120, 255]])

    def test_colored_overlay_removal_can_be_disabled(self):
        image = np.array([[[255, 0, 0]]], dtype=np.uint8)
        prepared = prepare_tesseract_image(image, remove_colored_overlays=False)
        self.assertEqual(prepared.tolist(), image.tolist())
