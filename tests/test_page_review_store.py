import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base, PageReview, delete_page_review, get_page_overrides, get_page_review_rows, upsert_page_review
from page_review import PageOverride

HASH_A = "a" * 64
HASH_B = "b" * 64


class PageReviewStoreTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def _upsert(self, status, file_hash=HASH_A, page=4, corrected_text=None):
        return upsert_page_review(
            self.db, file_hash, page, status, filename="ke-hoach.pdf",
            reviewed_by="admin@example.com", original_text="chữ OCR", corrected_text=corrected_text,
        )

    def test_upsert_then_get_returns_override(self):
        self._upsert("corrected", corrected_text="sửa")
        self.assertEqual(get_page_overrides(self.db, HASH_A), {4: PageOverride("corrected", "sửa")})

    def test_second_upsert_overwrites_same_page(self):
        self._upsert("confirmed")
        self._upsert("corrected", corrected_text="sửa lần hai")
        rows = self.db.query(PageReview).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "corrected")
        self.assertEqual(get_page_review_rows(self.db, HASH_A)[4].corrected_text, "sửa lần hai")

    def test_confirming_clears_previous_correction_text(self):
        self._upsert("corrected", corrected_text="sửa")
        self._upsert("confirmed")
        self.assertEqual(get_page_overrides(self.db, HASH_A), {4: PageOverride("confirmed", None)})

    def test_other_file_hash_is_not_returned(self):
        self._upsert("confirmed", file_hash=HASH_A)
        self.assertEqual(get_page_overrides(self.db, HASH_B), {})

    def test_delete_only_matching_status(self):
        self._upsert("confirmed")
        self.assertFalse(delete_page_review(self.db, HASH_A, 4, "corrected"))
        self.assertEqual(len(self.db.query(PageReview).all()), 1)
        self.assertTrue(delete_page_review(self.db, HASH_A, 4, "confirmed"))
        self.assertEqual(self.db.query(PageReview).all(), [])
