import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from langchain_core.documents import Document

import admin
from document_ingestion import DocumentIngestionResult


class FakeCollection:
    def __init__(self):
        self.ids = set()
        self.deleted = []
        self.fail_upsert_after_write = False

    def get(self, **_kwargs):
        return {"ids": []}

    def upsert(self, ids, **_kwargs):
        self.ids.update(ids)
        if self.fail_upsert_after_write:
            raise RuntimeError("partial upsert fault")

    def delete(self, ids):
        self.deleted.extend(ids)
        self.ids.difference_update(ids)

    def count(self):
        return len(self.ids)


class FakeStore:
    def __init__(self):
        self._collection = FakeCollection()
        self.deleted_collections = []
        self._client = SimpleNamespace(delete_collection=self.deleted_collections.append)


class FakeEmbedding:
    def embed_documents(self, texts):
        return [[float(index), 1.0] for index, _text in enumerate(texts)]


class FakeRag:
    def __init__(self):
        self.vector_store = FakeStore()
        self.embedding_model = FakeEmbedding()
        self.activate_calls = []

    def activate_collection(self, name):
        self.activate_calls.append(name)
        return "active_docs" if len(self.activate_calls) == 1 else "staging_docs"


class FakeDb:
    def __init__(self, fail_commit=False):
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = fail_commit

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("commit fault")

    def rollback(self):
        self.rollbacks += 1


class AdminIngestionTests(unittest.TestCase):
    def setUp(self):
        self.rag = FakeRag()
        self.rag_patch = patch.object(admin, "_rag_chain", self.rag)
        self.rag_patch.start()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.file_path = self.root / "sample.pdf"
        self.file_path.write_bytes(b"%PDF-1.4 test")
        self.ingestion = DocumentIngestionResult(
            chunks=[Document(page_content="Noi dung hop le", metadata={"page": 0})],
            created_cache_files=[self.root / "new-cache.json"],
        )
        self.actor = {"name": "admin", "role": "admin"}

    def tearDown(self):
        self.rag_patch.stop()
        self.temporary.cleanup()

    def _document(self):
        return SimpleNamespace(filename="sample.pdf", display_name=None)

    def test_metadata_failure_after_upsert_removes_new_vectors(self):
        db = FakeDb()
        with (
            patch.object(admin, "load_and_chunk_document", return_value=self.ingestion),
            patch.object(admin, "add_document_metadata", side_effect=RuntimeError("metadata fault")),
            patch.object(admin, "cleanup_new_cache_entries") as cleanup,
        ):
            with self.assertRaises(RuntimeError):
                admin.process_saved_document(self.file_path, 1.0, db, self.actor)
        self.assertEqual(self.rag.vector_store._collection.ids, set())
        self.assertEqual(db.rollbacks, 1)
        cleanup.assert_called_once_with(self.ingestion.created_cache_files)
        self.assertFalse(self.file_path.exists())

    def test_activity_failure_after_upsert_removes_new_vectors(self):
        db = FakeDb()
        with (
            patch.object(admin, "load_and_chunk_document", return_value=self.ingestion),
            patch.object(admin, "add_document_metadata", return_value=self._document()),
            patch.object(admin, "log_activity", side_effect=RuntimeError("activity fault")),
            patch.object(admin, "cleanup_new_cache_entries"),
        ):
            with self.assertRaises(RuntimeError):
                admin.process_saved_document(self.file_path, 1.0, db, self.actor)
        self.assertEqual(self.rag.vector_store._collection.ids, set())
        self.assertEqual(db.rollbacks, 1)
        self.assertFalse(self.file_path.exists())

    def test_partial_upsert_failure_removes_exact_new_vectors(self):
        collection = self.rag.vector_store._collection
        collection.fail_upsert_after_write = True
        with self.assertRaises(RuntimeError):
            admin.add_to_vector_store(self.ingestion.chunks, self.file_path.name)
        self.assertEqual(collection.ids, set())
        self.assertEqual(len(collection.deleted), 1)
        self.assertIn("_chunk_0", collection.deleted[0])

    def test_success_commits_metadata_and_keeps_new_vectors(self):
        db = FakeDb()
        with (
            patch.object(admin, "load_and_chunk_document", return_value=self.ingestion),
            patch.object(admin, "add_document_metadata", return_value=self._document()),
            patch.object(admin, "log_activity"),
        ):
            result = admin.process_saved_document(self.file_path, 1.0, db, self.actor)
        self.assertEqual(db.commits, 1)
        self.assertEqual(len(self.rag.vector_store._collection.ids), 1)
        self.assertEqual(result.vector_write.count, 1)

    def test_batch_upload_separates_each_file_error(self):
        db = FakeDb()
        first = UploadFile(filename="ok.pdf", file=io.BytesIO(b"%PDF-1.4 ok"))
        second = UploadFile(filename="bad.pdf", file=io.BytesIO(b"%PDF-1.4 bad"))
        outcome = SimpleNamespace(
            vector_write=SimpleNamespace(count=1),
            ingestion=SimpleNamespace(warnings=[]),
        )

        def process(**kwargs):
            if kwargs["file_path"].name == "bad.pdf":
                raise RuntimeError("fault for bad.pdf")
            return outcome

        with (
            patch.object(admin, "DATA_PATH", self.root),
            patch.object(admin, "process_saved_document", side_effect=process),
        ):
            response = asyncio.run(
                admin.upload_multiple_documents([first, second], db, self.actor)
            )

        self.assertEqual(response["total_success"], 1)
        self.assertEqual(response["total_failed"], 1)
        self.assertTrue(response["results"][0]["success"])
        self.assertFalse(response["results"][1]["success"])
        self.assertFalse((self.root / "bad.pdf").exists())

    def test_rebuild_failure_does_not_activate_staging(self):
        db = FakeDb()
        staging = FakeStore()
        with (
            patch.object(admin, "DATA_PATH", self.root),
            patch("rag_chain.get_vector_store", return_value=staging),
            patch.object(admin, "load_and_chunk_document", side_effect=RuntimeError("OCR fault")),
        ):
            with self.assertRaises(HTTPException):
                admin.rebuild_index(db, self.actor)
        self.assertEqual(self.rag.activate_calls, [])
        self.assertEqual(db.rollbacks, 1)

    def test_rebuild_commit_failure_restores_previous_collection(self):
        db = FakeDb(fail_commit=True)
        staging = FakeStore()
        with (
            patch.object(admin, "DATA_PATH", self.root),
            patch("rag_chain.get_vector_store", return_value=staging),
            patch.object(admin, "load_and_chunk_document", return_value=self.ingestion),
            patch.object(admin, "add_document_metadata", return_value=self._document()),
            patch.object(admin, "log_activity"),
        ):
            with self.assertRaises(HTTPException):
                admin.rebuild_index(db, self.actor)
        self.assertEqual(len(self.rag.activate_calls), 2)
        self.assertEqual(self.rag.activate_calls[1], "active_docs")


if __name__ == "__main__":
    unittest.main()
