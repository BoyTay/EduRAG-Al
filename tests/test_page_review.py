import unittest

from page_review import REVIEW_CONFIDENCE, has_malformed_date, review_reasons, row_number_gaps
from tesseract_service import LAYOUT_RETRY_CONFIDENCE

# Trang 5 kế hoạch Tuần định hướng, đọc theo ô (14/11/2026): số thứ tự 4 và 6 đọc hỏng, ngày lẫn ký tự lạ.
PAGE5 = "\n".join([
    "DANH SÁCH PHÂN BỐ ĐỊA ĐIỂM, THỜI GIAN VÀ PHÂN CÔNG",
    "'TT | ĐƠN VỊ | TRƯỜNG | NGÀY | PHÒNG CHỨC NĂNG | LÃNH ĐAO",
    "1 | |Khoa Toán - Tin học | |24/8/2026 | ThS. Hoàng Minh Tiến",
    "2 | |Khoa Sinh học | 25/8/2026 | PGS.TS. Lê Thị Anh Tú",
    "3 | |Khoa Hỏa học và Môi trường | A8B | |26/8/2026 | PGS.TS. Lê Thị Thanh Trân",
    "Á | |Khoa Nông lâm | |z7/8/2026 | ThS. Đỗ Văn Khoa",
    "5 | |Khoa Công nghệ thông tin | |28/8/2026 | ThS. Trần Thống",
    "® | |Khoa Luật học | |24/8/2026 | TS. Võ Thị Thanh Linh",
    "7 | lKhoa Quốc tế học | |25/8/2026 | TS. Hoàng Việt Bách Khoa",
    "15 | |Khoa Ngữ văn và Lịch sử | [28/8/2026 | ThS. Văn Quang Viên",
])

# Văn xuôi trang 1: có ngày hợp lệ và mục đánh số trong câu, không phải bảng.
PROSE = "\n".join([
    "Số: 1340/KH-ĐHĐL, Lâm Đồng, ngày 12 tháng 8 năm 2026",
    "3.3. Địa điểm: theo danh sách phân bố kèm theo; thời gian từ 24/8/2026 đến 28/8/2026.",
    "1. Mục đích: giúp Tân sinh viên làm quen môi trường học tập.",
    "2. Yêu cầu: đảm bảo an toàn, tiết kiệm.",
])

OCR_GARBAGE = (
    "cÄ kế —_ = \" Š = vị = 8 r= = n BĐ c Ế ' kO c>|# SmZ4 2 H| 2 Ê>? s# He. b0 ‹©. ‹\" |«s _- "
    "tạp mởi Đ E5 S9 8.e 2z HH =mq D2 S \"9 5< \\ả |xẩ 1. - « m© hEL6ëës Ä%k ‹d]$‹"
)


class ReviewReasonsTests(unittest.TestCase):
    def test_threshold_is_the_ocr_layout_retry_threshold(self):
        self.assertEqual(REVIEW_CONFIDENCE, LAYOUT_RETRY_CONFIDENCE)

    def test_page5_has_row_number_gap_and_malformed_date(self):
        self.assertEqual(review_reasons(PAGE5, 0.84), ["low_confidence", "row_number_gap", "malformed_date"])

    def test_clean_prose_page_has_no_reasons(self):
        self.assertEqual(review_reasons(PROSE, 0.93), [])

    def test_confidence_at_threshold_is_not_low(self):
        self.assertNotIn("low_confidence", review_reasons(PROSE, 0.85))

    def test_missing_confidence_is_not_low(self):
        self.assertEqual(review_reasons(PROSE, None), [])

    def test_garbled_text_is_reported(self):
        self.assertIn("garbled_text", review_reasons(OCR_GARBAGE, 0.9))


class RowNumberGapTests(unittest.TestCase):
    def test_consecutive_numbers_have_no_gap(self):
        self.assertFalse(row_number_gaps("1 | a\n2 | b\n3 | c"))

    def test_skipped_number_is_a_gap(self):
        self.assertTrue(row_number_gaps("1 | a\n2 | b\n4 | c"))

    def test_fewer_than_two_numbered_rows_is_never_a_gap(self):
        self.assertFalse(row_number_gaps("7 | a"))

    def test_header_row_is_not_a_broken_number(self):
        self.assertFalse(row_number_gaps("'TT | Đơn vị | Ngày\n1 | a | x\n2 | b | y"))
        self.assertFalse(row_number_gaps("STT | Đơn vị\n1 | a\n2 | b"))

    def test_row_starting_with_long_text_is_ignored(self):
        self.assertFalse(row_number_gaps("1 | a\nKhoa Kinh tế | HHTV\n2 | b"))


class MalformedDateTests(unittest.TestCase):
    def test_valid_dates_are_not_malformed(self):
        self.assertFalse(has_malformed_date("ngày 24/8/2026 và 05/09/2026."))

    def test_dates_with_stray_characters_are_malformed(self):
        for text in ("z7/8/2026", "[28/8/2026", "2l/8/2026"):
            with self.subTest(text=text):
                self.assertTrue(has_malformed_date(text))
