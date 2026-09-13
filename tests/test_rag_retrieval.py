import unittest
from types import SimpleNamespace

from langchain_core.documents import Document

from rag_chain import (
    content_answer_coverage,
    content_answer_is_complete,
    expand_retrieval_query,
    compact_content_bullets,
    extract_sources,
    infer_document_filename,
    l2_distance_to_relevance,
    normalize_answer,
    RAGChain,
    RETRIEVAL_CANDIDATE_K,
    rerank_retrieval_results,
    retrieval_evidence_score,
)


class RagRetrievalTests(unittest.TestCase):
    def test_money_spelling_is_not_a_denominator(self):
        for suffix in ("chẵn", "chãn", "chăn", "chắn"):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    normalize_answer(f"Mức hỗ trợ là 5.000.000 đồng/{suffix}."),
                    "Mức hỗ trợ là 5.000.000 đồng.",
                )

    def test_money_cleanup_preserves_real_units_and_conditions(self):
        answer = "Dưới 150 sinh viên: 5.000.000 đồng/Khoa; từ 150: 7.000.000 đồng/Khoa."
        self.assertEqual(normalize_answer(answer), answer)
        self.assertEqual(normalize_answer("500.000 đồng/tháng."), "500.000 đồng/tháng.")
        self.assertEqual(normalize_answer("Năm triệu đồng chẵn."), "Năm triệu đồng chẵn.")

    def test_squared_l2_is_converted_to_bounded_cosine_relevance(self):
        self.assertEqual(l2_distance_to_relevance(0.0), 1.0)
        self.assertAlmostEqual(l2_distance_to_relevance(1.2297), 0.38515)
        self.assertEqual(l2_distance_to_relevance(2.0), 0.0)
        self.assertEqual(l2_distance_to_relevance(3.0), 0.0)

    def test_time_range_chunk_is_reranked_above_document_issue_date(self):
        issue_date = Document(
            page_content=(
                "Lâm Đồng, ngày 12 tháng 8 năm 2026. Kế hoạch tổ chức "
                "Tuần định hướng dành cho Tân sinh viên khóa 50."
            ),
            metadata={"page": 0},
        )
        event_range = Document(
            page_content=(
                "II. Đối tượng, thời gian. Thời gian: Từ ngày 24/8/2026 "
                "đến hết ngày 28/8/2026."
            ),
            metadata={"page": 0},
        )
        ranked = rerank_retrieval_results(
            "Tuần định hướng dành cho tân sinh viên khóa 50 diễn ra vào ngày nào?",
            [(issue_date, 0.385), (event_range, 0.289)],
        )
        self.assertIs(ranked[0][0], event_range)
        self.assertEqual(ranked[0][1], 0.289)

    def test_ocr_degraded_time_range_still_receives_temporal_rerank(self):
        generic = Document(
            page_content="T chc Tun đnh hưóng dành cho Tân sinh viên khóa 50.",
            metadata={"page": 2},
        )
        degraded_range = Document(
            page_content=(
                "II. ĐI TUNG, THÒI GIAN. Thi gian: Tù ngày 24/8/2026 "
                "đn ht ngày 28/8/2026."
            ),
            metadata={"page": 0},
        )
        ranked = rerank_retrieval_results(
            "Tuần định hướng diễn ra khi nào?",
            [(generic, 0.36), (degraded_range, 0.25)],
        )
        self.assertIs(ranked[0][0], degraded_range)

    def test_document_number_uniquely_selects_filename(self):
        filenames = [
            "Quy_che_dao_tao_theo_tin_chi.pdf",
            "1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf",
        ]
        selected = infer_document_filename(
            "Kế hoạch số 1340/KH-ĐHĐL được ban hành ngày nào?",
            filenames,
        )
        self.assertEqual(selected, filenames[1])

    def test_year_alone_does_not_select_a_document(self):
        self.assertIsNone(
            infer_document_filename(
                "Quy định ban hành năm 2026?",
                ["1340-KH-DHDL_12082026.pdf", "Ke_hoach_tuyen_sinh_2026.pdf"],
            )
        )

    def test_unique_filename_topic_scopes_content_question(self):
        filenames = [
            "So_tay_sinh_vien.pdf",
            "Quy_che_dao_tao_theo_tin_chi.pdf",
            "1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf",
        ]
        selected = infer_document_filename(
            "Trong Tuần định hướng, tân sinh viên được hướng dẫn nội dung gì?",
            filenames,
        )
        self.assertEqual(selected, filenames[2])

    def test_content_question_gets_section_heading_query_hint(self):
        expanded = expand_retrieval_query(
            "Tân sinh viên được hướng dẫn những nội dung gì?",
            "Tân sinh viên được hướng dẫn những nội dung gì?",
        )
        self.assertIn("III. NỘI DUNG", expanded)

    def test_inline_bullets_are_normalized_to_separate_lines(self):
        answer = "- Ý thứ nhất. - Ý thứ hai. - Ý thứ ba."
        self.assertEqual(normalize_answer(answer).count("\n- "), 2)

    def test_content_bullets_are_compacted_without_losing_ten_items(self):
        answer = "\n".join(
            f"- Nhóm {index} " + " ".join(f"từ{word}" for word in range(20))
            for index in range(1, 11)
        )
        compacted = compact_content_bullets(answer)
        self.assertEqual(len(compacted.splitlines()), 10)
        self.assertLessEqual(len(compacted.split()), 100)

    def test_orientation_coverage_requires_final_question_resolution(self):
        complete = """- Tổng quan Khoa và ngành
- CNTT, truyền thông, thư viện, an toàn mạng
- Lịch thi, đăng ký và thủ tục
- Chương trình đào tạo và quy chế
- Kỹ năng học tập
- Văn hóa ứng xử
- Ngoại khóa, Đoàn Hội, học bổng
- Mục tiêu và kế hoạch học tập
- Giao lưu, chia sẻ kinh nghiệm
- Giải đáp thắc mắc"""
        self.assertEqual(content_answer_coverage(complete), 10)
        self.assertTrue(content_answer_is_complete(complete))
        self.assertFalse(
            content_answer_is_complete(
                complete.replace("Giải đáp thắc mắc", "Thông tin khác")
            )
        )

    def test_grouped_source_is_primary_when_same_page_chunk_is_primary(self):
        docs = [
            Document(page_content="không khớp", metadata={"source": "a.pdf", "page": 1}),
            Document(page_content="giải đáp thắc mắc", metadata={"source": "a.pdf", "page": 1}),
        ]
        sources = extract_sources(docs, "giải đáp thắc mắc", [0.2, 0.8])
        self.assertEqual(len(sources), 1)
        self.assertTrue(sources[0]["is_primary"])

    def test_content_heading_beats_responsibility_chunk(self):
        content = Document(
            page_content="III. NÓI DUNG - Gii thiu tng quan v Khoa",
            metadata={"section_title": "NỘI DUNG", "page": 1},
        )
        responsibility = Document(
            page_content="5.6 Các Khoa xây dựng chương trình Tuần định hướng",
            metadata={"section_title": "TỔ CHỨC THỰC HIỆN", "page": 3},
        )
        ranked = rerank_retrieval_results(
            "Tân sinh viên được hướng dẫn những nội dung gì?",
            [(responsibility, 0.34), (content, 0.18)],
        )
        self.assertIs(ranked[0][0], content)

    def test_issue_date_header_beats_schedule_for_issue_question(self):
        filename = "1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf"
        issue_header = Document(
            page_content=(
                "TRUÒNG DAI HOC ĐÀ LAT s:/340/KH-DHDL Lâm Đồng, "
                "ngày12tháng 8 năm 2026 KÉ HOACH T chc Tun đnh hưóng."
            ),
            metadata={"filename": filename, "page": 0},
        )
        noisy_schedule = Document(
            page_content="THII GIAN 13440-1430 ngày 24/8/2026 ngày 28/8/2026",
            metadata={"filename": filename, "page": 4},
        )
        question = "Kế hoạch số 1340/KH-ĐHĐL được ban hành ngày nào?"
        ranked = rerank_retrieval_results(
            question,
            [(noisy_schedule, 0.251), (issue_header, 0.148)],
        )
        self.assertIs(ranked[0][0], issue_header)
        self.assertGreaterEqual(
            retrieval_evidence_score(question, issue_header, 0.148),
            0.30,
        )


class _FakeCollection:
    def __init__(self, records=None):
        self.records = records or {"ids": [], "documents": [], "metadatas": []}

    def count(self):
        return 1

    def get(self, **_kwargs):
        return self.records


class _FakeVectorStore:
    def __init__(self, results, records=None):
        self._collection = _FakeCollection(records)
        self.results = results
        self.search_kwargs = None
        self.search_query = None

    def similarity_search_with_score(self, query, **kwargs):
        self.search_query = query
        self.search_kwargs = kwargs
        return self.results


class _FakeLlm:
    def __init__(self, responses=None):
        self.messages = None
        self.responses = list(responses or ["Kế hoạch được ban hành ngày 12/8/2026."])
        self.calls = 0

    async def ainvoke(self, _messages):
        self.messages = _messages
        response_index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return SimpleNamespace(content=self.responses[response_index])


class RagChainRetrievalFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_document_identifier_filters_and_prevents_false_refusal(self):
        filename = "1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf"
        issue_header = Document(
            page_content=(
                "TRUÒNG DAI HOC ĐÀ LAT s:/340/KH-DHDL Lâm Đồng, "
                "ngày12tháng 8 năm 2026 KÉ HOACH T chc Tun đnh hưóng."
            ),
            metadata={"filename": filename, "source": filename, "page": 0},
        )
        store = _FakeVectorStore([(issue_header, 1.704)])
        chain = RAGChain()
        chain._vector_store = store
        chain._llm = _FakeLlm()

        answer, sources, _score = await chain.achat(
            "Kế hoạch số 1340/KH-ĐHĐL được ban hành ngày nào?",
            active_filenames=[filename, "Quy_che_dao_tao_theo_tin_chi.pdf"],
        )

        self.assertEqual(answer, "Kế hoạch được ban hành ngày 12/8/2026.")
        self.assertEqual(store.search_kwargs["filter"], {"filename": filename})
        self.assertEqual(store.search_kwargs["k"], RETRIEVAL_CANDIDATE_K)
        self.assertEqual(sources[0]["page"], 1)

    async def test_content_question_uses_heading_and_same_page_chunks(self):
        filename = "1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf"
        content_anchor = Document(
            page_content="III. NÓI DUNG - Giới thiệu tổng quan về Khoa.",
            metadata={"filename": filename, "source": filename, "page": 1},
        )
        responsibility = Document(
            page_content="5.6 Các Khoa xây dựng chương trình Tuần định hướng.",
            metadata={"filename": filename, "source": filename, "page": 3},
        )
        records = {
            "ids": [f"{filename}_chunk_3", f"{filename}_chunk_2"],
            "documents": [
                "Hướng dẫn thời khóa biểu, lịch thi và đăng ký học phần.",
                content_anchor.page_content,
            ],
            "metadatas": [
                {"filename": filename, "source": filename, "page": 1, "chunk_index": 3},
                {"filename": filename, "source": filename, "page": 1, "chunk_index": 2},
            ],
        }
        store = _FakeVectorStore(
            [(responsibility, 1.30), (content_anchor, 1.64)],
            records,
        )
        llm = _FakeLlm([
            "\n".join(f"- Nhóm nội dung {index}" for index in range(1, 11))
        ])
        chain = RAGChain()
        chain._vector_store = store
        chain._llm = llm

        await chain.achat(
            "Trong Tuần định hướng, tân sinh viên được hướng dẫn những nội dung gì?",
            active_filenames=[filename, "So_tay_sinh_vien.pdf"],
        )

        self.assertIn("III. NỘI DUNG", store.search_query)
        self.assertEqual(store.search_kwargs["filter"], {"filename": filename})
        rendered_prompt = "\n".join(str(message.content) for message in llm.messages)
        self.assertLess(
            rendered_prompt.index("Giới thiệu tổng quan"),
            rendered_prompt.index("Hướng dẫn thời khóa biểu"),
        )
        self.assertNotIn("5.6 Các Khoa", rendered_prompt)

    async def test_incomplete_content_answer_is_completed_from_tail_chunks(self):
        filename = "1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf"
        anchor = Document(
            page_content="III. NỘI DUNG - Nội dung mở đầu.",
            metadata={"filename": filename, "source": filename, "page": 1},
        )
        records = {
            "ids": [f"{filename}_chunk_{index}" for index in range(6)],
            "documents": [f"Nội dung nguồn thứ {index}" for index in range(6)],
            "metadatas": [
                {
                    "filename": filename,
                    "source": filename,
                    "page": 1,
                    "chunk_index": index,
                }
                for index in range(6)
            ],
        }
        records["documents"][0] = anchor.page_content
        llm = _FakeLlm([
            "- Nhóm 1\n- Nhóm 2",
            "- Nhóm 1\n- Nhóm 2\n- Nhóm 3\n- Nhóm 4",
            "\n".join(f"- Nhóm {index}" for index in range(5, 11)),
        ])
        chain = RAGChain()
        chain._vector_store = _FakeVectorStore([(anchor, 1.60)], records)
        chain._llm = llm

        answer, _sources, _score = await chain.achat(
            "Tuần định hướng hướng dẫn tân sinh viên những nội dung gì?",
            document_filename=filename,
            active_filenames=[filename],
        )

        self.assertEqual(llm.calls, 4)
        self.assertEqual(answer.splitlines(), [f"- Nhóm {index}" for index in range(1, 11)])


if __name__ == "__main__":
    unittest.main()
