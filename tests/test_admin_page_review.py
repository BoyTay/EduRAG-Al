import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pymupdf as fitz
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import admin
from db import Base, DocumentMetadata, PageReview

ACTOR = {"name": "Admin", "role": "admin", "email": "admin@example.com"}


def _chunk(page, method="tesseract", **extra):
    return {"id": f"c{page}", "content": "x", "page": page, "extraction_method": method, "flags": [], **extra}


class AdminPageReviewTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.pdf = self.root / "ke-hoach.pdf"
        with fitz.open() as document:
            document.new_page()
            document.new_page()
            document.save(self.pdf)
        self.db.add(DocumentMetadata(filename="ke-hoach.pdf", file_path=str(self.pdf), file_type="pdf",
                                     display_name="Kế hoạch"))
        self.db.commit()

        self.reingest_calls = []

        def fake_reingest(db, document, action, entity_name, current_user):
            self.reingest_calls.append((action, entity_name))
            db.commit()
            return 3

        patches = [
            patch.object(admin, "_rag_chain", SimpleNamespace(vector_store=SimpleNamespace(_collection=object()))),
            patch.object(admin, "reingest_document", side_effect=fake_reingest),
            patch.object(admin, "read_page_ocr_text", return_value="chữ OCR gốc"),
            patch.object(admin, "list_document_chunks", return_value=[_chunk(0), _chunk(1)]),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def tearDown(self):
        self.db.close()
        self.temporary.cleanup()

    def _correct(self, page=1, text="Bảng đã sửa\n1 | Khoa Hóa học", filename="ke-hoach.pdf"):
        return admin.save_page_correction(filename, page, admin.PageCorrectionRequest(text=text), self.db, ACTOR)

    def _rows(self):
        return self.db.query(PageReview).all()

    def _status(self, error):
        return error.exception.status_code

    def test_put_correction_saves_row_and_reingests(self):
        response = self._correct()
        self.assertEqual(response, {"page": 1, "status": "corrected", "chunk_count": 3})
        row = self._rows()[0]
        self.assertEqual((row.page_index, row.status, row.original_text), (0, "corrected", "chữ OCR gốc"))
        self.assertEqual(row.corrected_text, "Bảng đã sửa\n1 | Khoa Hóa học")
        self.assertEqual(self.reingest_calls, [("page_corrected", "Kế hoạch · Tr. 1")])

    def test_correction_with_too_few_characters_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            self._correct(text=" .. ")
        self.assertEqual(self._status(error), 422)
        self.assertEqual(self._rows(), [])

    def test_reingest_failure_rolls_back_review_row(self):
        with patch.object(admin, "reingest_document", side_effect=RuntimeError("OCR fault")):
            with self.assertRaises(HTTPException) as error:
                self._correct()
        self.assertEqual(self._status(error), 500)
        self.assertIn("dữ liệu cũ vẫn được giữ", error.exception.detail)
        self.assertEqual(self._rows(), [])

    def test_page_out_of_range_is_404(self):
        for page in (0, 3):
            with self.subTest(page=page):
                with self.assertRaises(HTTPException) as error:
                    self._correct(page=page)
                self.assertEqual(self._status(error), 404)
        self.assertEqual(self._rows(), [])
        self.assertEqual(self.reingest_calls, [])

    def test_docx_document_is_422(self):
        docx = self.root / "so-tay.docx"
        docx.write_bytes(b"PK")
        self.db.add(DocumentMetadata(filename="so-tay.docx", file_path=str(docx), file_type="docx"))
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            self._correct(filename="so-tay.docx")
        self.assertEqual(self._status(error), 422)
        self.assertEqual(error.exception.detail, "Chỉ sửa được trang PDF scan")

    def test_missing_file_on_disk_is_404(self):
        self.pdf.unlink()
        with self.assertRaises(HTTPException) as error:
            self._correct()
        self.assertEqual(self._status(error), 404)
        self.assertEqual(self.reingest_calls, [])

    def test_native_page_cannot_be_corrected(self):
        with patch.object(admin, "list_document_chunks", return_value=[_chunk(0, "native")]):
            with self.assertRaises(HTTPException) as error:
                self._correct()
        self.assertEqual(self._status(error), 422)
        self.assertEqual(self._rows(), [])

    def test_rebuild_in_progress_is_409(self):
        self.assertTrue(admin._rebuild_lock.acquire(blocking=False))
        try:
            with self.assertRaises(HTTPException) as error:
                self._correct()
        finally:
            admin._rebuild_lock.release()
        self.assertEqual(self._status(error), 409)
        self.assertEqual(error.exception.detail, "Đang tạo lại chỉ mục, thử lại sau")

    def test_lock_is_released_after_each_action(self):
        self._correct()
        self.assertTrue(admin._rebuild_lock.acquire(blocking=False))
        admin._rebuild_lock.release()

    def test_get_text_prefers_correction(self):
        self.assertEqual(admin.get_page_text("ke-hoach.pdf", 1, self.db, ACTOR)["source"], "ocr")
        self._correct()
        response = admin.get_page_text("ke-hoach.pdf", 1, self.db, ACTOR)
        self.assertEqual(response, {"page": 1, "text": "Bảng đã sửa\n1 | Khoa Hóa học", "source": "correction"})

    def test_confirm_then_unconfirm(self):
        self.assertEqual(admin.confirm_page("ke-hoach.pdf", 2, self.db, ACTOR)["status"], "confirmed")
        self.assertEqual(self._rows()[0].status, "confirmed")
        self.assertEqual(admin.unconfirm_page("ke-hoach.pdf", 2, self.db, ACTOR)["status"], None)
        self.assertEqual(self._rows(), [])
        self.assertEqual([call[0] for call in self.reingest_calls], ["page_confirmed", "page_confirmation_removed"])

    def test_remove_correction(self):
        self._correct()
        self.assertEqual(admin.remove_page_correction("ke-hoach.pdf", 1, self.db, ACTOR)["status"], None)
        self.assertEqual(self._rows(), [])
        self.assertEqual(self.reingest_calls[-1][0], "page_correction_removed")

    def test_delete_confirmation_when_none_is_404(self):
        with self.assertRaises(HTTPException) as error:
            admin.unconfirm_page("ke-hoach.pdf", 1, self.db, ACTOR)
        self.assertEqual(self._status(error), 404)
        self.assertEqual(self.reingest_calls, [])

    def test_pages_lists_status_and_count(self):
        chunks = [_chunk(0, review_status="needs_review", review_reasons=["low_confidence"], ocr_confidence=0.8),
                  _chunk(1, "native")]
        with patch.object(admin, "list_document_chunks", return_value=chunks):
            response = admin.get_document_pages("ke-hoach.pdf", self.db, ACTOR)
        self.assertEqual(response["needs_review"], 1)
        self.assertEqual([page["page"] for page in response["pages"]], [1, 2])
        self.assertTrue(response["pages"][0]["editable"])
        self.assertFalse(response["pages"][1]["editable"])


class NeedsReviewCountTests(unittest.TestCase):
    def test_counts_distinct_pages_per_document(self):
        metadatas = [
            {"filename": "a.pdf", "page": 4}, {"filename": "a.pdf", "page": 4},
            {"filename": "a.pdf", "page": 7}, {"filename": "b.pdf", "page": 0},
        ]
        collection = SimpleNamespace(get=lambda **_kwargs: {"metadatas": metadatas})
        with patch.object(admin, "_rag_chain", SimpleNamespace(vector_store=SimpleNamespace(_collection=collection))):
            self.assertEqual(admin._needs_review_page_counts(), {"a.pdf": 2, "b.pdf": 1})

    def test_index_error_gives_no_counts(self):
        def broken(**_kwargs):
            raise RuntimeError("chroma down")

        collection = SimpleNamespace(get=broken)
        with patch.object(admin, "_rag_chain", SimpleNamespace(vector_store=SimpleNamespace(_collection=collection))):
            self.assertEqual(admin._needs_review_page_counts(), {})
