import io
import subprocess
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from ocr_service import OCRLine, OCRPageResult
from tesseract_service import (
    TesseractOCRService,
    group_cells_into_rows,
    parse_osd_rotation,
    parse_tesseract_tsv,
    prepare_tesseract_image,
    read_tesseract_psm,
    rotate_image,
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


OSD_SIDEWAYS = (
    "Page number: 0\nOrientation in degrees: 270\nRotate: 90\n"
    "Orientation confidence: 6.42\nScript: Latin\nScript confidence: 3.10\n"
)


class OrientationParsingTests(unittest.TestCase):
    def test_confident_osd_returns_clockwise_rotation(self):
        self.assertEqual(parse_osd_rotation(OSD_SIDEWAYS), 90)

    def test_low_confidence_osd_is_treated_as_unknown(self):
        weak = OSD_SIDEWAYS.replace("6.42", "0.30")
        self.assertIsNone(parse_osd_rotation(weak))

    def test_unparseable_osd_is_unknown(self):
        self.assertIsNone(parse_osd_rotation("Too few characters. Skipping this page"))

    def test_rotate_image_turns_clockwise(self):
        image = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        self.assertEqual(rotate_image(image, 90).tolist(), [[3, 1], [4, 2]])
        self.assertEqual(rotate_image(image, 0).tolist(), image.tolist())


def _page(text: str, confidence: float) -> OCRPageResult:
    return OCRPageResult(text=text, confidence=confidence, lines=[], model_name="tesseract-vie")


class FakeTesseractCase(unittest.TestCase):
    """Giả lập lệnh tesseract để kiểm tra recognize_page mà không cần cài Tesseract."""

    def setUp(self):
        self.service = TesseractOCRService()
        self.service._binary = "tesseract"
        self.service._fingerprint = {"provider": "tesseract"}  # bỏ qua bước dò cài đặt thật
        self.service.cell_detector = None  # các test hướng trang không dùng Paddle
        # Ảnh 2x3 khác biệt từng điểm ảnh để nhận ra ảnh đã bị xoay hay chưa.
        self.image = np.arange(6, dtype=np.uint8).reshape(2, 3)
        self.seen_shapes = []
        self.seen_psms = []

    def _fake_run(self, osd_output):
        """Giả lập Tesseract: lệnh --psm 0 trả kết quả OSD, lệnh còn lại ghi lại ảnh đã nhận."""
        def run(command, input=None, **kwargs):
            if command[command.index("--psm") + 1] == "0":
                if osd_output is None:
                    raise subprocess.CalledProcessError(1, command)
                return subprocess.CompletedProcess(command, 0, osd_output.encode(), b"")
            self.seen_shapes.append(np.asarray(Image.open(io.BytesIO(input))).tolist())
            self.seen_psms.append(int(command[command.index("--psm") + 1]))
            return subprocess.CompletedProcess(command, 0, b"", b"")
        return run

    def _recognize(self, osd_output, parse_results):
        with patch("tesseract_service.subprocess.run", side_effect=self._fake_run(osd_output)), \
                patch("tesseract_service.parse_tesseract_tsv", side_effect=parse_results):
            return self.service.recognize_page(self.image)


class OrientationRecognitionTests(FakeTesseractCase):
    """recognize_page tự xoay trang nằm ngang trước khi đọc, không xoay cố định."""

    def test_sideways_page_is_rotated_before_ocr(self):
        result = self._recognize(OSD_SIDEWAYS, [_page("đúng", 0.9)])
        self.assertEqual(result.text, "đúng")
        self.assertEqual(self.seen_shapes, [rotate_image(self.image, 90).tolist()])

    def test_upright_page_is_read_once_without_rotation(self):
        upright = OSD_SIDEWAYS.replace("Rotate: 90", "Rotate: 0")
        self._recognize(upright, [_page("đúng", 0.3), _page("bố cục", 0.2)])
        self.assertEqual(self.seen_shapes, [self.image.tolist()] * 2)

    def test_unknown_orientation_with_low_confidence_tries_all_and_keeps_best(self):
        results = [_page("rác", 0.2), _page("đúng", 0.88), _page("rác", 0.3), _page("rác", 0.25)]
        result = self._recognize(None, results)
        self.assertEqual(result.text, "đúng")
        self.assertEqual(len(self.seen_shapes), 4)
        self.assertEqual(self.seen_shapes[1], rotate_image(self.image, 90).tolist())

    def test_failed_extra_orientation_does_not_lose_the_page(self):
        results = [
            _page("rác", 0.2), RuntimeError("timeout"), _page("đúng", 0.8), _page("rác", 0.1),
            _page("bố cục kém", 0.5),
        ]
        result = self._recognize(None, results)
        self.assertEqual(result.text, "đúng")

    def test_unknown_orientation_with_good_confidence_is_read_once(self):
        result = self._recognize(None, [_page("đúng", 0.9)])
        self.assertEqual(result.text, "đúng")
        self.assertEqual(len(self.seen_shapes), 1)

    def test_low_confidence_page_is_reread_with_layout_analysis(self):
        """Trang bảng/poster: psm 6 đọc kém thì đọc lại bằng psm 3 và giữ bản tin cậy hơn."""
        result = self._recognize(OSD_SIDEWAYS, [_page("ít chữ", 0.75), _page("đủ bảng", 0.83)])
        self.assertEqual(result.text, "đủ bảng")
        self.assertEqual(self.seen_psms, [6, 3])
        self.assertEqual(self.seen_shapes, [rotate_image(self.image, 90).tolist()] * 2)

    def test_layout_reread_that_is_worse_is_discarded(self):
        result = self._recognize(OSD_SIDEWAYS, [_page("psm 6", 0.8), _page("psm 3", 0.6)])
        self.assertEqual(result.text, "psm 6")

    def test_confident_page_is_not_reread(self):
        self._recognize(OSD_SIDEWAYS, [_page("văn xuôi", 0.93)])
        self.assertEqual(self.seen_psms, [6])

    def test_layout_reread_uses_best_orientation_from_fallback(self):
        results = [_page("rác", 0.2), _page("hướng đúng", 0.7), _page("rác", 0.3), _page("rác", 0.25),
                   _page("hướng đúng, đủ bảng", 0.8)]
        result = self._recognize(None, results)
        self.assertEqual(result.text, "hướng đúng, đủ bảng")
        self.assertEqual(self.seen_psms[-1], 3)
        self.assertEqual(self.seen_shapes[-1], rotate_image(self.image, 90).tolist())

    def test_failed_layout_reread_keeps_first_result(self):
        result = self._recognize(OSD_SIDEWAYS, [_page("psm 6", 0.7), RuntimeError("timeout")])
        self.assertEqual(result.text, "psm 6")

    def test_cache_fingerprint_changes_when_orientation_detection_is_added(self):
        with patch("tesseract_service.shutil.which", return_value="tesseract"), \
                patch("tesseract_service.subprocess.run") as run, \
                patch("tesseract_service.Path.read_bytes", return_value=b"vie"):
            run.side_effect = [
                subprocess.CompletedProcess([], 0, b"tesseract 5.3.0\n", b""),
                subprocess.CompletedProcess(
                    [], 0, b'List of available languages in "/td/" (2):\nosd\nvie\n', b""
                ),
            ]
            fingerprint = TesseractOCRService().cache_fingerprint
        self.assertEqual(fingerprint["orientation"], "osd")
        self.assertEqual(fingerprint["layout_retry_psm"], 3)


class GroupCellsIntoRowsTests(unittest.TestCase):
    def test_cells_on_one_row_are_joined_left_to_right(self):
        cells = [
            OCRLine(text="TS. Phan Tuấn Anh", confidence=0.9, bounding_box=[300, 10, 500, 30]),
            OCRLine(text="Khoa Kinh tế", confidence=0.8, bounding_box=[0, 12, 200, 32]),
            OCRLine(text="Khoa Ngoại ngữ", confidence=0.7, bounding_box=[0, 60, 200, 80]),
        ]
        rows = group_cells_into_rows(cells)
        self.assertEqual([row.text for row in rows], ["Khoa Kinh tế | TS. Phan Tuấn Anh", "Khoa Ngoại ngữ"])
        self.assertEqual(rows[0].bounding_box, [0, 10, 500, 32])
        self.assertAlmostEqual(rows[0].confidence, 0.85)

    def test_no_cells_gives_no_rows(self):
        self.assertEqual(group_cells_into_rows([]), [])


class FakeCellDetector:
    name = "fake-det"

    def __init__(self, boxes):
        self.boxes = boxes
        self.calls = 0

    def detect(self, pixels):
        self.calls += 1
        return self.boxes


class CellReadingTests(FakeTesseractCase):
    """Trang đọc kém: Paddle tìm từng ô chữ, Tesseract đọc từng ô (psm 7), ghép lại theo hàng."""

    def _with_detector(self, boxes):
        detector = FakeCellDetector(boxes)
        self.service.cell_detector = detector
        return detector

    def test_low_confidence_page_is_read_cell_by_cell_into_rows(self):
        # Ảnh 2x3: hai ô cùng hàng.
        self._with_detector([[2, 0, 3, 2], [0, 0, 1, 2]])
        results = [_page("ít chữ", 0.75), _page("bảng psm3", 0.83), _page("A", 0.9), _page("B", 0.8)]
        result = self._recognize(OSD_SIDEWAYS, results)
        self.assertEqual(result.text, "B | A")
        self.assertAlmostEqual(result.confidence, 0.85)
        self.assertEqual(result.model_name, "fake-det+tesseract-vie")
        self.assertEqual(self.seen_psms, [6, 3, 7, 7])

    def test_cells_slightly_less_confident_than_psm3_are_still_preferred(self):
        self._with_detector([[0, 0, 1, 2]])
        result = self._recognize(OSD_SIDEWAYS, [_page("psm6", 0.7), _page("psm3", 0.84), _page("ô", 0.81)])
        self.assertEqual(result.text, "ô")

    def test_clearly_worse_cells_are_discarded(self):
        self._with_detector([[0, 0, 1, 2]])
        result = self._recognize(OSD_SIDEWAYS, [_page("psm6", 0.7), _page("psm3", 0.84), _page("ô", 0.5)])
        self.assertEqual(result.text, "psm3")

    def test_unavailable_detector_falls_back_to_psm3(self):
        self._with_detector(None)
        result = self._recognize(OSD_SIDEWAYS, [_page("psm6", 0.7), _page("psm3", 0.8)])
        self.assertEqual(result.text, "psm3")
        self.assertEqual(self.seen_psms, [6, 3])

    def test_confident_page_does_not_run_detector(self):
        detector = self._with_detector([[0, 0, 1, 2]])
        self._recognize(OSD_SIDEWAYS, [_page("văn xuôi", 0.93)])
        self.assertEqual(detector.calls, 0)

    def test_failed_cell_read_is_skipped(self):
        self._with_detector([[0, 0, 1, 2], [2, 0, 3, 2]])
        results = [_page("psm6", 0.7), _page("psm3", 0.8), RuntimeError("timeout"), _page("B", 0.9)]
        result = self._recognize(OSD_SIDEWAYS, results)
        self.assertEqual(result.text, "B")

    def test_cache_fingerprint_names_cell_detector(self):
        service = TesseractOCRService(cell_detector=FakeCellDetector([]))
        with patch("tesseract_service.shutil.which", return_value="tesseract"), \
                patch("tesseract_service.subprocess.run") as run, \
                patch("tesseract_service.Path.read_bytes", return_value=b"vie"):
            run.side_effect = [
                subprocess.CompletedProcess([], 0, b"tesseract 5.3.0\n", b""),
                subprocess.CompletedProcess(
                    [], 0, b'List of available languages in "/td/" (2):\nosd\nvie\n', b""
                ),
            ]
            fingerprint = service.cache_fingerprint
        self.assertEqual(fingerprint["cell_detector"], "fake-det")
