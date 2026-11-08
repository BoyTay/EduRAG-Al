import io
import os
import tempfile
import unittest
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw
from docx import Document as DocxDocument

from document_ingestion import (
    annotate_chunk_metadata,
    detect_section_title,
    DocumentIngestionError,
    IngestionSettings,
    OCRResultCache,
    load_and_chunk_document,
)
from langchain_core.documents import Document
from ocr_service import OCRConfigurationError, OCRLine, OCRPageResult


class FakeOCR:
    def __init__(self, fingerprint="small-a", fail=False):
        self.calls = 0
        self.fail = fail
        self._fingerprint = fingerprint

    @property
    def cache_fingerprint(self):
        return {"provider": "fake", "version": self._fingerprint}

    def recognize_page(self, _image):
        self.calls += 1
        if self.fail:
            raise RuntimeError("fault injection")
        line = OCRLine("Điều 12. Nội dung nhận dạng từ trang scan.", 0.93, [5, 5, 100, 30])
        return OCRPageResult(line.text, line.confidence, [line], "fake-small")


class PyMuPDFVersionTests(unittest.TestCase):
    def test_pymupdf_major_version_is_below_2(self):
        # PyMuPDF 2.x tách chữ tiếng Việt trong ô bảng ("Si nh viên"); xem Dockerfile.backend.
        major = int(fitz.__version__.split(".")[0])
        self.assertLess(major, 2, f"PyMuPDF {fitz.__version__} làm vỡ chữ trong bảng; dùng bản 1.x")


class DocumentIngestionTests(unittest.TestCase):
    def test_invalid_ocr_alphabet_rejects_scan_with_page_number(self):
        class InvalidOCR(FakeOCR):
            def recognize_page(self, _image):
                raise OCRConfigurationError("Model thiếu ký tự tiếng Việt")

        path = self._pdf("unsupported.pdf", ["native", "scan"])
        with self.assertRaises(DocumentIngestionError) as caught:
            load_and_chunk_document(path, InvalidOCR(), self.settings, self.cache)
        self.assertEqual(caught.exception.failed_pages, [2])
        self.assertIn("thiếu ký tự tiếng Việt", str(caught.exception))

    def test_invalid_ocr_alphabet_preserves_short_native_text(self):
        class InvalidOCR(FakeOCR):
            def recognize_page(self, _image):
                raise OCRConfigurationError("Model thiếu ký tự tiếng Việt")

        path = self._pdf("short-supported.pdf", ["short"])
        result = load_and_chunk_document(path, InvalidOCR(), self.settings, self.cache)
        self.assertIn("Dieu 1", result.chunks[0].page_content)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.cache = OCRResultCache(self.root / "cache")
        self.settings = IngestionSettings(
            ocr_enabled=True,
            dpi=96,
            native_text_threshold=50,
            sanity_min_chars=3,
            blank_pixel_threshold=245,
            blank_dark_ratio=0.0005,
            blank_stddev=2.0,
            chunk_size=1000,
            chunk_overlap=0,
            cache_path=self.root / "cache",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_section_heading_is_inherited_by_following_chunks_on_page(self):
        chunks = [
            Document(
                page_content="2 3.3 Địa điểm III. NÓI DUNG - Giới thiệu tổng quan",
                metadata={"page": 1},
            ),
            Document(
                page_content="Hướng dẫn xem thời khóa biểu và đăng ký học phần",
                metadata={"page": 1},
            ),
            Document(
                page_content="IV. KINH PHÍ - Nhà trường hỗ trợ tổ chức",
                metadata={"page": 2},
            ),
        ]

        annotate_chunk_metadata(chunks)

        self.assertEqual(detect_section_title(chunks[0].page_content), "NỘI DUNG")
        self.assertEqual(chunks[0].metadata["section_title"], "NỘI DUNG")
        self.assertEqual(chunks[1].metadata["section_title"], "NỘI DUNG")
        self.assertEqual(chunks[1].metadata["page_chunk_index"], 1)
        self.assertEqual(chunks[2].metadata["section_title"], "KINH PHÍ")

    @staticmethod
    def _image_bytes():
        image = Image.new("RGB", (500, 180), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 30, 470, 140), outline="black", width=4)
        draw.text((35, 70), "DIEU 12 - NOI DUNG SCAN", fill="black")
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def _pdf(self, name, page_kinds):
        path = self.root / name
        with fitz.open() as document:
            for kind in page_kinds:
                page = document.new_page(width=500, height=220)
                if kind == "native":
                    page.insert_text(
                        (20, 40),
                        "Quy dinh hoc vu co noi dung native du dai de khong can goi OCR. "
                        "Thong tin nay chi dung cho unit test.",
                    )
                elif kind == "short":
                    page.insert_text((20, 40), "Dieu 1")
                elif kind == "scan":
                    page.insert_image(page.rect, stream=self._image_bytes())
                elif kind == "uncertain":
                    page.draw_rect(fitz.Rect(30, 30, 200, 120), color=(0, 0, 0), fill=(0, 0, 0))
                elif kind != "blank":
                    raise AssertionError(kind)
            document.save(path)
        return path

    def test_text_pdf_does_not_call_ocr(self):
        path = self._pdf("native.pdf", ["native"])
        fake = FakeOCR()
        result = load_and_chunk_document(path, fake, self.settings, self.cache)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(result.chunks[0].metadata["extraction_method"], "native")

    def test_native_table_keeps_each_level_with_its_own_scores(self):
        path = self.root / "levels.pdf"
        with fitz.open() as document:
            page = document.new_page(width=580, height=240)
            x_positions = (20, 65, 155, 250, 350, 450, 560)
            y_positions = (25, 55, 85, 115)
            for x in x_positions:
                page.draw_line((x, 25), (x, 115), color=(0, 0, 0))
            for y in y_positions:
                page.draw_line((20, y), (560, y), color=(0, 0, 0))
            cells = (
                ("TT", "Language", "Certificate", "Bac 3", "Bac 4", "Bac 5"),
                ("1", "English", "TOEIC", "Listen 275-399", "Listen 400-489", "Listen 490-495"),
                ("", "", "IELTS", "4.0-5.0", "5.5-6.5", "7.0-8.0"),
            )
            for row_index, row in enumerate(cells):
                for column, value in enumerate(row):
                    if value:
                        page.insert_text((x_positions[column] + 4, y_positions[row_index] + 19), value, fontsize=8)
            page.insert_text((25, 150), "Other policy text outside the table must remain searchable.")
            document.save(path)

        result = load_and_chunk_document(path, settings=self.settings, cache=self.cache)
        toeic = [chunk for chunk in result.chunks if "TOEIC" in chunk.page_content]
        self.assertEqual(len(toeic), 3)
        bac3 = next(chunk for chunk in toeic if "Bac 3" in chunk.page_content)
        bac4 = next(chunk for chunk in toeic if "Bac 4" in chunk.page_content)
        bac5 = next(chunk for chunk in toeic if "Bac 5" in chunk.page_content)
        self.assertIn("Listen 275-399", bac3.page_content)
        self.assertNotIn("400-489", bac3.page_content)
        self.assertIn("Listen 400-489", bac4.page_content)
        self.assertNotIn("275-399", bac4.page_content)
        self.assertNotIn("490-495", bac4.page_content)
        self.assertIn("Listen 490-495", bac5.page_content)
        self.assertNotIn("400-489", bac5.page_content)
        self.assertEqual(bac4.metadata["extraction_method"], "native_table")
        self.assertEqual(bac4.metadata["page"], 0)
        self.assertEqual(bac4.metadata["table_level"], 4)
        self.assertTrue(any(
            chunk.metadata["extraction_method"] == "native"
            and "Other policy text" in chunk.page_content
            and "TOEIC" not in chunk.page_content
            for chunk in result.chunks
        ))

    def _grid(self, page, x_positions, y_positions, skip_vertical=None):
        """Vẽ lưới bảng; skip_vertical = {(cột, hàng)} bỏ đoạn kẻ dọc để tạo ô gộp ngang."""
        skip_vertical = skip_vertical or set()
        for y in y_positions:
            page.draw_line((x_positions[0], y), (x_positions[-1], y), color=(0, 0, 0))
        for column, x in enumerate(x_positions):
            for row in range(len(y_positions) - 1):
                if (column, row) not in skip_vertical:
                    page.draw_line((x, y_positions[row]), (x, y_positions[row + 1]), color=(0, 0, 0))

    def _write_cells(self, page, x_positions, y_positions, rows):
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                if value:
                    page.insert_text((x_positions[c] + 4, y_positions[r] + 17), value, fontsize=9)

    def test_table_split_across_pages_keeps_caption_headers_and_merged_cells(self):
        path = self.root / "split.pdf"
        xs = (40, 160, 300, 460)
        with fitz.open() as document:
            first = document.new_page(width=520, height=420)
            first.insert_text((40, 330), "6. Xep loai hoc tap theo diem trung binh chung tich luy nhu sau:", fontsize=9)
            ys1 = (345, 370, 395)
            # Ô tiêu đề "Xep loai" trải trên hai cột đầu: bỏ kẻ dọc giữa chúng ở hàng tiêu đề.
            self._grid(first, xs, ys1, skip_vertical={(1, 0)})
            self._write_cells(first, xs, ys1, (("Xep loai", "", "Thang diem 4"), ("Dat", "Xuat sac", "Tu 3,60 den 4,00")))
            second = document.new_page(width=520, height=420)
            second.insert_text((40, 300), "Van ban noi dung de trang co du chu native khong can nhan dang OCR.", fontsize=9)
            ys2 = (30, 55, 80, 105)
            self._grid(second, xs, ys2)
            self._write_cells(second, xs, ys2, (("", "Gioi", "Tu 3,20 den 3,59"), ("", "Kha", "Tu 2,50 den 3,19"), ("Khong dat", "Yeu", "Tu 1,00 den 1,99")))
            document.save(path)

        result = load_and_chunk_document(path, settings=self.settings, cache=self.cache)
        rows = [chunk for chunk in result.chunks if chunk.metadata["extraction_method"] == "native_table"]
        texts = [chunk.page_content for chunk in rows]
        self.assertEqual(len(rows), 4, texts)
        for text in texts:
            self.assertIn("Xep loai hoc tap theo diem trung binh chung tich luy", text)
            self.assertNotIn("Cột", text)
        by_grade = {name: next(t for t in texts if name in t) for name in ("Xuat sac", "Gioi", "Kha", "Yeu")}
        self.assertIn("Xep loai: Dat - Xuat sac", by_grade["Xuat sac"])
        self.assertIn("Xep loai: Dat - Gioi; Thang diem 4: Tu 3,20 den 3,59", by_grade["Gioi"])
        self.assertIn("Xep loai: Dat - Kha", by_grade["Kha"])
        self.assertIn("Xep loai: Khong dat - Yeu", by_grade["Yeu"])
        continued = [chunk for chunk in rows if chunk.metadata.get("table_continued")]
        self.assertEqual(len(continued), 3)

    def test_table_with_its_own_header_on_next_page_is_not_a_continuation(self):
        path = self.root / "two_tables.pdf"
        xs = (40, 160, 300, 460)
        with fitz.open() as document:
            first = document.new_page(width=520, height=420)
            first.insert_text((40, 200), "Van ban noi dung de trang co du chu native khong can nhan dang OCR.", fontsize=9)
            ys1 = (330, 355, 380)
            self._grid(first, xs, ys1)
            self._write_cells(first, xs, ys1, (("TT", "Ten", "Gia tri"), ("1", "Alpha", "Mot")))
            second = document.new_page(width=520, height=420)
            second.insert_text((40, 300), "Van ban noi dung de trang co du chu native khong can nhan dang OCR.", fontsize=9)
            ys2 = (30, 55, 80)
            self._grid(second, xs, ys2)
            self._write_cells(second, xs, ys2, (("TT", "Nhom", "Muc"), ("1", "Beta", "Hai")))
            document.save(path)

        result = load_and_chunk_document(path, settings=self.settings, cache=self.cache)
        texts = [c.page_content for c in result.chunks if c.metadata["extraction_method"] == "native_table"]
        self.assertTrue(any("Nhom: Beta; Muc: Hai" in text for text in texts), texts)
        self.assertFalse(any(c.metadata.get("table_continued") for c in result.chunks))

    def test_long_paragraph_above_table_is_not_used_as_caption(self):
        path = self.root / "paragraph.pdf"
        xs = (40, 160, 300, 460)
        with fitz.open() as document:
            page = document.new_page(width=520, height=300)
            page.insert_text((40, 60), "Day la mot doan van dai khong phai ten bang " + "noi dung " * 25 + ":", fontsize=6)
            ys = (100, 125, 150)
            self._grid(page, xs, ys)
            self._write_cells(page, xs, ys, (("Ten", "Gia tri", "Ghi chu"), ("A", "1", "x")))
            document.save(path)

        result = load_and_chunk_document(path, settings=self.settings, cache=self.cache)
        rows = [c for c in result.chunks if c.metadata["extraction_method"] == "native_table"]
        self.assertTrue(rows)
        self.assertFalse(any("table_caption" in c.metadata for c in rows))

    FILLER = "Van ban noi dung de trang co du chu native khong can nhan dang OCR."

    def _table_pdf(self, name, pages):
        """Mỗi phần tử của `pages` là dict(xs, ys, rows, height=420, top_text=None)."""
        path = self.root / name
        with fitz.open() as document:
            for spec in pages:
                page = document.new_page(width=spec.get("width", 520), height=spec.get("height", 420))
                page.insert_text((40, spec.get("filler_y", 400)), self.FILLER, fontsize=8)
                if spec.get("top_text"):
                    page.insert_text((40, spec["ys"][0] - 8), spec["top_text"], fontsize=9)
                self._grid(page, spec["xs"], spec["ys"], spec.get("skip_vertical"))
                self._write_cells(page, spec["xs"], spec["ys"], spec["rows"])
            document.save(path)
        return load_and_chunk_document(path, settings=self.settings, cache=self.cache)

    @staticmethod
    def _table_texts(result):
        return [c.page_content for c in result.chunks if c.metadata["extraction_method"] == "native_table"]

    def test_wrapped_cell_lines_are_merged_into_their_numbered_row(self):
        result = self._table_pdf("wrapped.pdf", [{
            "xs": (20, 50, 190, 360, 500),
            "ys": (40, 65, 90, 115, 140),
            "rows": (
                ("TT", "Doi tuong", "Ho so", "Ghi chu"),
                ("1", "Sinh vien khuyet tat", "1. Don de nghi", "Xet 1 lan"),
                ("", "", "(theo mau phu luc 1)", ""),
                ("", "", "2. Ban sao giay khai sinh", ""),
            ),
        }])
        texts = self._table_texts(result)
        self.assertEqual(len(texts), 1, texts)
        self.assertIn("Ho so: 1. Don de nghi (theo mau phu luc 1) 2. Ban sao giay khai sinh", texts[0])
        self.assertIn("Doi tuong: Sinh vien khuyet tat", texts[0])

    def test_full_sub_rows_under_vertically_merged_number_are_not_merged(self):
        result = self._table_pdf("sub_rows.pdf", [{
            "xs": (20, 50, 190, 330, 500),
            "ys": (40, 65, 90, 115),
            "rows": (
                ("TT", "Ngon ngu", "Chung chi", "Diem"),
                ("1", "Tieng Anh", "TOEFL iBT", "46-93"),
                ("", "", "IELTS", "5.5-6.5"),
            ),
        }])
        texts = self._table_texts(result)
        self.assertEqual(len(texts), 2, texts)
        self.assertIn("Chung chi: IELTS; Diem: 5.5-6.5", texts[1])
        self.assertNotIn("TOEFL", texts[1])

    def test_wrapped_rows_in_headerless_numbered_table_are_merged(self):
        result = self._table_pdf("headerless_wrapped.pdf", [{
            "xs": (20, 50, 190, 360, 500),
            "ys": (60, 85, 110, 135),
            "rows": (
                ("2", "Sinh vien khuyet tat", "1. Don xin nhan tro cap xa", "100.000"),
                ("", "", "hoi (theo mau phu luc 4)", ""),
                ("3", "Sinh vien ho ngheo", "Giay chung nhan ho ngheo", "100.000"),
            ),
        }])
        texts = self._table_texts(result)
        self.assertEqual(len(texts), 2, texts)
        self.assertIn("1. Don xin nhan tro cap xa hoi (theo mau phu luc 4)", texts[0])

    def test_full_rows_with_blank_first_cell_in_unnumbered_table_are_not_merged(self):
        result = self._table_pdf("vertical_merge.pdf", [{
            "xs": (40, 160, 300, 460),
            "ys": (40, 65, 90, 115),
            "rows": (
                ("Xep loai", "Muc", "Thang diem 4"),
                ("Dat", "Gioi", "Tu 3,20 den 3,59"),
                ("", "Kha", "Tu 2,50 den 3,19"),
            ),
        }])
        texts = self._table_texts(result)
        self.assertEqual(len(texts), 2, texts)
        self.assertIn("Xep loai: Dat; Muc: Kha", texts[1])

    SUPPORT_XS = (40, 80, 300, 460)

    def test_headerless_table_continues_even_if_previous_ends_mid_page(self):
        result = self._table_pdf("continue_mid.pdf", [
            {"xs": self.SUPPORT_XS, "ys": (200, 225, 250),
             "rows": (("TT", "Doi tuong", "Muc ho tro"), ("1", "Sinh vien mo coi", "100.000"))},
            {"xs": self.SUPPORT_XS, "ys": (30, 55),
             "rows": (("2", "Sinh vien vung cao", "140.000"),)},
        ])
        chunk = next(c for c in result.chunks if "vung cao" in c.page_content)
        self.assertIn("Doi tuong: Sinh vien vung cao; Muc ho tro: 140.000", chunk.page_content)
        self.assertTrue(chunk.metadata.get("table_continued"))
        self.assertFalse(any("Sinh vien vung cao:" in text for text in self._table_texts(result)))

    def test_three_page_table_keeps_first_header(self):
        result = self._table_pdf("three_pages.pdf", [
            {"xs": self.SUPPORT_XS, "ys": (330, 355, 380),
             "rows": (("TT", "Doi tuong", "Muc ho tro"), ("1", "Nhom mot", "100.000"))},
            {"xs": self.SUPPORT_XS, "ys": (30, 55), "rows": (("2", "Nhom hai", "120.000"),)},
            {"xs": self.SUPPORT_XS, "ys": (30, 55), "rows": (("3", "Nhom ba", "140.000"),)},
        ])
        third = next(c for c in result.chunks if "Nhom ba" in c.page_content)
        self.assertEqual(third.metadata["page"], 2)
        self.assertIn("Doi tuong: Nhom ba; Muc ho tro: 140.000", third.page_content)

    def test_unmatched_headerless_table_uses_generic_labels_not_data(self):
        result = self._table_pdf("headerless.pdf", [
            {"xs": self.SUPPORT_XS, "ys": (60, 85, 110),
             "rows": (("5", "Alpha", "Mot"), ("6", "Beta", "Hai"))},
        ])
        texts = self._table_texts(result)
        self.assertEqual(len(texts), 2, texts)
        self.assertTrue(any("Cột 2: Alpha" in text for text in texts), texts)
        self.assertFalse(any("Alpha:" in text for text in texts), texts)

    def test_continued_row_without_number_takes_previous_number(self):
        result = self._table_pdf("row_split.pdf", [
            {"xs": self.SUPPORT_XS, "ys": (330, 355, 380),
             "rows": (("TT", "Doi tuong", "Ho so"), ("3", "Sinh vien ho ngheo", "Don de nghi"))},
            {"xs": self.SUPPORT_XS, "ys": (30, 55, 80),
             "rows": (("", "", "Giay chung nhan ho ngheo"), ("4", "Sinh vien khuyet tat", "Giay xac nhan"))},
        ])
        part = next(c for c in result.chunks if "Giay chung nhan ho ngheo" in c.page_content)
        self.assertIn("TT: 3", part.page_content)
        self.assertTrue(part.metadata.get("table_row_continued"))
        self.assertTrue(any("TT: 4; Doi tuong: Sinh vien khuyet tat" in t for t in self._table_texts(result)))

    def test_two_column_text_layout_stays_as_prose(self):
        lines = (
            "Doan truong la co so Doan", "tuong duong cap huyen truc thuoc",
            "tinh doan Lam Dong va co", "14 Doan khoa voi 159 Chi doan",
            "co so truc thuoc voi quy mo", "11.670 doan vien",
        )
        result = self._table_pdf("prose_layout.pdf", [{
            "xs": (40, 300, 480),
            "ys": (40, 65, 90, 115, 140, 165, 190),
            "rows": tuple((line, "") for line in lines),
        }])
        self.assertEqual(self._table_texts(result), [])
        prose = " ".join(c.page_content for c in result.chunks if c.metadata["extraction_method"] == "native")
        self.assertIn("Doan truong la co so Doan tuong duong cap huyen", prose)
        self.assertIn("159 Chi doan", prose)

    def test_real_two_column_table_is_kept(self):
        result = self._table_pdf("two_columns.pdf", [{
            "xs": (40, 300, 480),
            "ys": (40, 65, 90, 115, 140),
            "rows": (
                ("Nganh dao tao", "Chuan dau ra"),
                ("Ngon ngu Anh", "5/6"),
                ("Cac nganh khac, he ky su", "4/6"),
                ("Cac nganh khac, he cu nhan", "3/6"),
            ),
        }])
        texts = self._table_texts(result)
        self.assertEqual(len(texts), 3, texts)
        self.assertIn("Nganh dao tao: Ngon ngu Anh; Chuan dau ra: 5/6", texts[0])

    CONTACT_XS = (20, 60, 230, 360, 600, 780)
    CONTACT_HEADER = ("STT", "Ten phong", "So dien thoai", "Email", "Ghi chu")

    @staticmethod
    def _merged_rows(*rows):
        """Ô gộp ngang toàn dòng (dòng tên bảng): bỏ các đường kẻ dọc bên trong."""
        return {(column, row) for row in rows for column in range(1, 5)}

    def test_full_width_title_row_becomes_caption_and_next_row_is_header(self):
        result = self._table_pdf("contacts.pdf", [{
            "width": 800, "xs": self.CONTACT_XS, "ys": (40, 65, 90, 115),
            "skip_vertical": self._merged_rows(0),
            "rows": (
                ("CAC PHONG BAN CAN LIEN HE", "", "", "", ""),
                self.CONTACT_HEADER,
                ("3", "Phong Tai chinh", "0263. 3820566", "phongtaichinh@dlu.edu.vn", "Hoc phi"),
            ),
        }])
        texts = self._table_texts(result)
        self.assertEqual(len(texts), 1, texts)
        self.assertIn("[CAC PHONG BAN CAN LIEN HE]", texts[0])
        self.assertIn("So dien thoai: 0263. 3820566", texts[0])
        self.assertIn("Email: phongtaichinh@dlu.edu.vn", texts[0])
        self.assertNotIn(" - ", texts[0])

    def test_mid_table_title_row_starts_new_header_group(self):
        result = self._table_pdf("contacts_groups.pdf", [{
            "width": 800, "xs": self.CONTACT_XS, "ys": (40, 65, 90, 115, 140, 165, 190),
            "skip_vertical": self._merged_rows(0, 3),
            "rows": (
                ("CAC PHONG BAN CAN LIEN HE", "", "", "", ""),
                self.CONTACT_HEADER,
                ("3", "Phong Tai chinh", "0263. 3820566", "phongtaichinh@dlu.edu.vn", "Hoc phi"),
                ("KHOA CAN LIEN HE", "", "", "", ""),
                ("STT", "Khoa", "So dien thoai", "Email", "Ghi chu"),
                ("2", "Cong nghe thong tin", "0263. 3552540", "it@dlu.edu.vn", ""),
            ),
        }])
        texts = self._table_texts(result)
        self.assertEqual(len(texts), 2, texts)
        it = next(text for text in texts if "it@dlu.edu.vn" in text)
        self.assertIn("[KHOA CAN LIEN HE]", it)
        self.assertIn("Khoa: Cong nghe thong tin", it)
        self.assertIn("So dien thoai: 0263. 3552540", it)

    def test_long_row_is_split_with_identity_on_every_part(self):
        self.settings = IngestionSettings(**{**self.settings.__dict__, "chunk_size": 120})
        record = "Ban sao giay chung nhan nguoi co cong voi cach mang"
        result = self._table_pdf("long_row.pdf", [{
            "width": 800, "xs": (20, 60, 250, 640, 780), "ys": (40, 65, 90),
            "rows": (
                ("TT", "Doi tuong", "Ho so", "Ghi chu"),
                ("2", "Nguoi co cong voi cach mang", f"1. Don de nghi; 2. {record}", "Xet mot lan"),
            ),
        }])
        texts = self._table_texts(result)
        self.assertGreater(len(texts), 1, texts)
        for text in texts:
            self.assertLessEqual(len(text), 120, text)
            self.assertIn("TT: 2", text)
            self.assertIn("Doi tuong: Nguoi co cong voi cach mang", text)
        joined = " ".join(texts)
        self.assertIn("Ghi chu: Xet mot lan", joined)
        squashed = joined.replace(" ", "")
        for word in record.split():
            self.assertIn(word, squashed)

    def test_split_long_row_keeps_all_text_within_limit(self):
        from document_ingestion import _split_long_row
        identity = "TT: 2; Doi tuong: Sinh vien"
        value = " ".join(f"giay{i}" for i in range(120))
        pieces = _split_long_row(identity, [f"Ho so: {value}", "Ghi chu: Xet mot lan"], 200)
        self.assertTrue(all(len(piece) <= 200 and piece.startswith(identity) for piece in pieces), pieces)
        joined = " ".join(pieces)
        for i in range(120):
            self.assertRegex(joined, rf"\bgiay{i}\b")
        self.assertIn("Ho so (tiếp):", joined)
        self.assertIn("Ghi chu: Xet mot lan", joined)

    def test_split_long_row_terminates_when_identity_exceeds_limit(self):
        import threading

        from document_ingestion import _split_long_row
        identity = "[" + "Ghi chu rat dai " * 44 + "] TT: 2; Doi tuong: Sinh vien"
        self.assertGreater(len(identity), 700)
        result = {}
        worker = threading.Thread(
            target=lambda: result.update(pieces=_split_long_row(identity, ["Ho so: " + "giay " * 200], 700)),
            daemon=True,
        )
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive(), "_split_long_row không dừng khi identity dài hơn max_chars")
        self.assertTrue(all(len(piece) <= 700 for piece in result["pieces"]), [len(p) for p in result["pieces"]])
        self.assertEqual(" ".join(result["pieces"]).count("giay"), 200)

    def test_first_cell_only_row_in_vertical_merge_table_is_data_not_title(self):
        result = self._table_pdf("vertical_label_row.pdf", [{
            "xs": (40, 160, 300, 460),
            "ys": (40, 65, 90, 115, 140),
            "rows": (
                ("Xep loai", "Muc", "Thang diem 4"),
                ("Dat", "Gioi", "Tu 3,20 den 3,59"),
                ("Khong dat", "", ""),
                ("", "Yeu", "Tu 1,00 den 1,99"),
            ),
        }])
        texts = self._table_texts(result)
        yeu = next(text for text in texts if "Yeu" in text)
        self.assertIn("Xep loai: Khong dat; Muc: Yeu", yeu)
        self.assertFalse(any("[Khong dat]" in text for text in texts), texts)

    def test_partial_level_sub_row_is_not_merged_into_row_above(self):
        result = self._table_pdf("levels_partial.pdf", [{
            "width": 600, "xs": (20, 50, 140, 240, 340, 440, 560),
            "ys": (40, 65, 90, 115),
            "rows": (
                ("TT", "Language", "Certificate", "Bac 3", "Bac 4", "Bac 5"),
                ("1", "English", "TOEIC", "275-399", "400-489", "490-495"),
                ("", "", "VSTEP", "Bac 3", "", ""),
            ),
        }])
        texts = self._table_texts(result)
        self.assertTrue(any("Certificate: VSTEP" in text for text in texts), texts)
        self.assertFalse(any("TOEIC VSTEP" in text for text in texts), texts)

    def test_wrapped_rows_on_headerless_continuation_page_are_merged(self):
        result = self._table_pdf("headerless_cont.pdf", [
            {"xs": self.SUPPORT_XS, "ys": (330, 355, 380),
             "rows": (("2", "Nhom hai", "Ho so hai"), ("3", "Nhom ba", "Ho so ba"))},
            {"xs": self.SUPPORT_XS, "ys": (30, 55, 80, 105),
             "rows": (("", "", "tiep a"), ("", "", "tiep b"), ("4", "Nhom bon", "Ho so bon"))},
        ])
        texts = [c.page_content for c in result.chunks
                 if c.metadata["extraction_method"] == "native_table" and c.metadata["page"] == 1]
        self.assertEqual(len(texts), 2, texts)
        self.assertIn("tiep a tiep b", texts[0])
        self.assertIn("Cột 1: 3", texts[0])

    def test_two_column_table_with_vertically_merged_group_is_kept(self):
        rows = [("Khoa", "Nganh"), ("Cong nghe thong tin", "Ky thuat phan mem")]
        rows += [("", f"Nganh con {i}") for i in range(5)]
        result = self._table_pdf("merged_two_columns.pdf", [{
            "xs": (40, 260, 480),
            "ys": tuple(40 + 25 * i for i in range(len(rows) + 1)),
            "rows": tuple(rows),
        }])
        texts = self._table_texts(result)
        self.assertEqual(len(texts), 6, texts)
        self.assertIn("Khoa: Cong nghe thong tin; Nganh: Nganh con 4", texts[-1])

    def test_scan_pdf_calls_fake_ocr_and_keeps_zero_based_page(self):
        path = self._pdf("scan.pdf", ["scan"])
        fake = FakeOCR()
        result = load_and_chunk_document(path, fake, self.settings, self.cache)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(result.chunks[0].metadata["page"], 0)
        self.assertEqual(result.chunks[0].metadata["extraction_method"], "ppocrv6")
        self.assertIsInstance(result.chunks[0].metadata["ocr_confidence"], float)

    def test_mixed_pdf_only_ocr_pages_without_enough_text(self):
        path = self._pdf("mixed.pdf", ["native", "scan", "native"])
        fake = FakeOCR()
        result = load_and_chunk_document(path, fake, self.settings, self.cache)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(
            [chunk.metadata["extraction_method"] for chunk in result.chunks],
            ["native", "ppocrv6", "native"],
        )

    def test_short_native_text_survives_ocr_failure(self):
        path = self._pdf("short.pdf", ["short"])
        result = load_and_chunk_document(path, FakeOCR(fail=True), self.settings, self.cache)
        self.assertIn("Dieu 1", result.chunks[0].page_content)
        self.assertEqual(result.chunks[0].metadata["extraction_method"], "native_low_text")

    def test_blank_page_is_skipped(self):
        path = self._pdf("blank.pdf", ["blank", "native"])
        fake = FakeOCR()
        result = load_and_chunk_document(path, fake, self.settings, self.cache)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(len(result.chunks), 1)
        self.assertTrue(any("trang trắng 1" in warning for warning in result.warnings))

    def test_uncertain_page_is_not_treated_as_blank(self):
        path = self._pdf("uncertain.pdf", ["uncertain"])
        fake = FakeOCR()
        load_and_chunk_document(path, fake, self.settings, self.cache)
        self.assertEqual(fake.calls, 1)

    def test_ocr_failure_lists_one_based_pages(self):
        path = self._pdf("failed.pdf", ["scan", "scan"])
        with self.assertRaises(DocumentIngestionError) as context:
            load_and_chunk_document(path, FakeOCR(fail=True), self.settings, self.cache)
        self.assertEqual(context.exception.failed_pages, [1, 2])
        self.assertIn("Trang thất bại: 1, 2", str(context.exception))

    def test_ocr_disabled_does_not_call_service(self):
        path = self._pdf("disabled.pdf", ["scan"])
        fake = FakeOCR()
        settings = IngestionSettings(**{**self.settings.__dict__, "ocr_enabled": False})
        with self.assertRaises(DocumentIngestionError):
            load_and_chunk_document(path, fake, settings, self.cache)
        self.assertEqual(fake.calls, 0)

    def test_docx_path_is_unchanged_and_never_calls_ocr(self):
        path = self.root / "document.docx"
        document = DocxDocument()
        document.add_paragraph(
            "Noi dung DOCX du dai de tiep tuc dung loader cu va khong can OCR. "
            "Day la du lieu unit test khong nhay cam."
        )
        document.save(path)
        fake = FakeOCR()
        result = load_and_chunk_document(path, fake, self.settings, self.cache)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(result.chunks[0].metadata["extraction_method"], "native")

    def test_cache_hit_does_not_call_model_again(self):
        path = self._pdf("cache-hit.pdf", ["scan"])
        first = FakeOCR(fingerprint="same")
        load_and_chunk_document(path, first, self.settings, self.cache)
        second = FakeOCR(fingerprint="same", fail=True)
        load_and_chunk_document(path, second, self.settings, self.cache)
        self.assertEqual(first.calls, 1)
        self.assertEqual(second.calls, 0)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are not enforced on Windows")
    def test_cache_files_and_directories_are_private(self):
        path = self._pdf("private-cache.pdf", ["scan"])
        result = load_and_chunk_document(path, FakeOCR(), self.settings, self.cache)
        cache_file = result.created_cache_files[0]
        self.assertEqual(self.cache.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(cache_file.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(cache_file.stat().st_mode & 0o777, 0o600)

    def test_fingerprint_change_creates_cache_miss(self):
        path = self._pdf("cache-miss.pdf", ["scan"])
        first = FakeOCR(fingerprint="config-a")
        second = FakeOCR(fingerprint="config-b")
        load_and_chunk_document(path, first, self.settings, self.cache)
        load_and_chunk_document(path, second, self.settings, self.cache)
        self.assertEqual(first.calls, 1)
        self.assertEqual(second.calls, 1)

    def test_delete_document_removes_only_its_cache(self):
        first_path = self._pdf("first.pdf", ["scan"])
        second_path = self._pdf("second.pdf", ["scan", "native"])
        load_and_chunk_document(first_path, FakeOCR(), self.settings, self.cache)
        load_and_chunk_document(second_path, FakeOCR(), self.settings, self.cache)
        from document_ingestion import sha256_file

        first_hash = sha256_file(first_path)
        second_hash = sha256_file(second_path)

        self.cache.delete_document(first_path)

        self.assertFalse((self.cache.root / first_hash).exists())
        self.assertTrue((self.cache.root / second_hash).exists())


if __name__ == "__main__":
    unittest.main()
