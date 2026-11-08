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


if __name__ == "__main__":
    unittest.main()
