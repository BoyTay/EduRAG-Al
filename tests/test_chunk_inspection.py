import unittest

from chunk_inspection import flag_chunk, list_document_chunks


class FakeCollection:
    def __init__(self, documents, metadatas):
        self.documents = documents
        self.metadatas = metadatas
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "ids": [f"id-{index}" for index in range(len(self.documents))],
            "documents": self.documents,
            "metadatas": self.metadatas,
        }


def table_meta(**extra):
    return {"filename": "a.pdf", "page": 1, "extraction_method": "native_table", **extra}


class ListDocumentChunksTests(unittest.TestCase):
    def test_chunks_sorted_by_chunk_index(self):
        collection = FakeCollection(
            ["hai", "không", "một"],
            [{"filename": "a.pdf", "chunk_index": 2}, {"filename": "a.pdf", "chunk_index": 0},
             {"filename": "a.pdf", "chunk_index": 1}],
        )
        chunks = list_document_chunks(collection, "a.pdf")
        self.assertEqual([chunk["content"] for chunk in chunks], ["không", "một", "hai"])
        self.assertEqual(collection.calls[0]["where"], {"filename": "a.pdf"})

    def test_missing_metadata_keys_become_none(self):
        chunk = list_document_chunks(FakeCollection(["Nội dung DOCX"], [{"filename": "a.docx"}]), "a.docx")[0]
        self.assertIsNone(chunk["page"])
        self.assertIsNone(chunk["extraction_method"])
        self.assertIsNone(chunk["table_caption"])
        self.assertFalse(chunk["table_continued"])
        self.assertEqual(chunk["flags"], [])

    def test_empty_collection_returns_empty_list(self):
        self.assertEqual(list_document_chunks(FakeCollection([], []), "a.pdf"), [])


class FlagChunkTests(unittest.TestCase):
    def test_flags_generic_label_short_and_long_label(self):
        self.assertIn("generic_label", flag_chunk("TT: 1; Cột 2: giá trị không có nhãn", table_meta()))
        self.assertIn("too_short", flag_chunk("TT: 1", table_meta()))
        long_label = "Một nhãn cột rất dài bất thường vì thực ra là một dòng dữ liệu bị dùng làm tiêu đề"
        self.assertGreater(len(long_label), 60)
        self.assertIn("long_label", flag_chunk(f"{long_label}: giá trị", table_meta()))

    def test_caption_prefix_is_not_a_long_label(self):
        content = (
            "[Xếp loại học tập theo học kỳ, năm học hoặc điểm trung bình chung tích lũy] "
            "Xếp loại: Đạt - Giỏi; Thang điểm 4: Từ 3,20 đến 3,59"
        )
        self.assertEqual(flag_chunk(content, table_meta()), [])

    def test_prose_chunks_are_not_checked_for_table_flags(self):
        self.assertEqual(flag_chunk("Ngắn", {"extraction_method": "native"}), [])


class InspectionEndpointTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        import admin
        from db import Base, DocumentMetadata

        self.admin = admin
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.addCleanup(self.db.close)
        self.db.add(DocumentMetadata(filename="a.pdf", file_path="/data/a.pdf", file_type="pdf"))
        self.db.add(DocumentMetadata(filename="empty.pdf", file_path="/data/empty.pdf", file_type="pdf"))
        self.db.commit()
        self.collection = FakeCollection(
            ["Cột 2: x", "TT: 1; Doi tuong: Sinh vien; Muc: 100.000"],
            [table_meta(chunk_index=1), table_meta(chunk_index=0)],
        )
        self.collection.get_for = {"a.pdf"}
        original_get = self.collection.get

        def get(**kwargs):
            if kwargs["where"]["filename"] not in self.collection.get_for:
                return {"ids": [], "documents": [], "metadatas": []}
            return original_get(**kwargs)

        self.collection.get = get
        rag = SimpleNamespace(vector_store=SimpleNamespace(_collection=self.collection))
        patcher = patch.object(admin, "_rag_chain", rag)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = {"user_id": 1, "role": "admin", "email": "admin@khoa", "name": "admin@khoa"}

    def test_chunks_endpoint_returns_sorted_chunks_and_flag_count(self):
        response = self.admin.get_document_chunks("a.pdf", db=self.db, _=self.user)
        self.assertEqual(response["filename"], "a.pdf")
        self.assertEqual(response["total"], 2)
        self.assertEqual(response["flagged"], 1)
        self.assertEqual(response["chunks"][0]["content"], "TT: 1; Doi tuong: Sinh vien; Muc: 100.000")

    def test_chunks_endpoint_unknown_document_is_404(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as caught:
            self.admin.get_document_chunks("missing.pdf", db=self.db, _=self.user)
        self.assertEqual(caught.exception.status_code, 404)

    def test_chunks_endpoint_document_without_chunks_returns_empty(self):
        response = self.admin.get_document_chunks("empty.pdf", db=self.db, _=self.user)
        self.assertEqual((response["chunks"], response["total"], response["flagged"]), ([], 0, 0))

    def test_chunks_endpoint_rejects_path_in_filename(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as caught:
            self.admin.get_document_chunks("../x.pdf", db=self.db, _=self.user)
        self.assertEqual(caught.exception.status_code, 400)

    def test_review_sets_and_clears_reviewer(self):
        marked = self.admin.set_document_review(
            "a.pdf", self.admin.DocumentReviewRequest(reviewed=True), db=self.db, current_user=self.user
        )
        self.assertEqual(marked["reviewed_by"], "admin@khoa")
        self.assertTrue(marked["reviewed_at"].endswith("Z") or "+" in marked["reviewed_at"])
        listed = self.admin.get_documents(db=self.db, _=self.user)["documents"]
        self.assertEqual(next(d for d in listed if d["filename"] == "a.pdf")["reviewed_by"], "admin@khoa")

        cleared = self.admin.set_document_review(
            "a.pdf", self.admin.DocumentReviewRequest(reviewed=False), db=self.db, current_user=self.user
        )
        self.assertIsNone(cleared["reviewed_at"])
        self.assertIsNone(cleared["reviewed_by"])

    def test_init_db_adds_review_columns_to_old_table(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from sqlalchemy import create_engine, inspect, text

        import db as db_module

        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'old.db'}")
            with engine.begin() as connection:
                connection.execute(text(
                    "CREATE TABLE document_metadata (id INTEGER PRIMARY KEY, filename VARCHAR(255) NOT NULL, "
                    "file_path TEXT NOT NULL, file_type VARCHAR(10) NOT NULL, chunk_count INTEGER, "
                    "file_size_kb FLOAT, uploaded_at DATETIME NOT NULL, description TEXT)"
                ))
            with patch.object(db_module, "engine", engine):
                db_module.init_db()
            columns = {column["name"] for column in inspect(engine).get_columns("document_metadata")}
            engine.dispose()
        self.assertTrue({"reviewed_at", "reviewed_by"} <= columns, columns)


if __name__ == "__main__":
    unittest.main()
