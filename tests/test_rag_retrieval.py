import unittest
from types import SimpleNamespace

from langchain_core.documents import Document

from rag_chain import (
    asks_for_enumeration,
    build_answer_guidance,
    asks_for_confirmation,
    deduplicate_answer_lines,
    extract_sources,
    extract_final_answer,
    infer_document_filename,
    l2_distance_to_relevance,
    normalize_answer,
    RAGChain,
    RETRIEVAL_CANDIDATE_K,
    rerank_retrieval_results,
    retrieval_evidence_score,
    SYSTEM_PROMPT,
)


ORIENTATION_SOURCE = """II. NỘI DUNG
Giới thiệu tổng quan về Khoa; tầm nhìn, sứ mệnh, cơ cấu tổ chức, đội ngũ giảng viên;
các ngành/chương trình đào tạo và định hướng, cơ hội nghề nghiệp của từng ngành.
Hướng dẫn sử dụng các hệ thống công nghệ thông tin, kênh thông tin - truyền thông;
khai thác tài nguyên thư viện; bảo đảm an toàn thông tin khi sử dụng Internet và mạng xã hội.
Hướng dẫn xem thời khóa biểu, lịch thi, đăng ký học phần, quy trình thủ tục hành chính;
phương thức liên hệ, trao đổi công việc với Khoa, phòng chức năng và tổ chức Đoàn - Hội.
Giới thiệu chương trình đào tạo áp dụng đối với Tân sinh viên Khóa 50; quy chế đào tạo
trình độ đại học; quy định bảo đảm chất lượng; quy chế công tác sinh viên.
Trang bị phương pháp học tập và tự học; kỹ năng nghiên cứu khoa học; kỹ năng thuyết trình,
giao tiếp và làm việc nhóm; quản lý thời gian, quản lý tài chính cá nhân; kỹ năng thích nghi
với môi trường học tập và cuộc sống tự lập. Phổ biến Quy tắc văn hóa ứng xử.
Trung tâm Truyền thông và Hỗ trợ Người học truyền thông đa nền tảng và xây dựng hệ sinh thái hỗ trợ toàn diện.
Giới thiệu hoạt động ngoại khóa, Đoàn - Hội, câu lạc bộ, đội, nhóm; chương trình hỗ trợ
sinh viên; cơ hội học bổng; định hướng nghề nghiệp, thực tập và việc làm.
Định hướng mục tiêu học tập, rèn luyện trong học kỳ I; xây dựng kế hoạch học tập, rèn luyện
và cam kết thực hiện quy định. Giao lưu, chia sẻ kinh nghiệm từ cựu sinh viên, doanh nhân,
nhà tuyển dụng, chuyên gia. Giải đáp các câu hỏi, khó khăn, vướng mắc; nội dung phù hợp
với đặc thù ngành và điều kiện thực tế của Khoa."""

STUDENT_RESPONSIBILITY_SOURCE = """5.8. Trách nhiệm của Tân sinh viên
- Nghiêm túc thực hiện kế hoạch Tuần định hướng theo đúng quy định của Nhà trường và Khoa;
- Tham gia đầy đủ, đúng giờ; tập trung lắng nghe và chủ động ghi chép các thông tin quan trọng;
- Tích cực tham gia các hoạt động giao lưu, đặt câu hỏi giải đáp thắc mắc để đạt hiệu quả tiếp thu cao nhất."""


GROUPED_ORIENTATION_ANSWER = """Tân sinh viên được hướng dẫn các nội dung chính sau:
- Giới thiệu: Tổng quan Khoa, chương trình đào tạo và cơ hội nghề nghiệp.
- Công cụ học tập: CNTT, thư viện, lịch thi, đăng ký học phần và thủ tục.
- Kỹ năng và quy chế: Tự học, nghiên cứu, làm việc nhóm, quản lý thời gian, quy chế và văn hóa ứng xử.
- Kết nối: Hoạt động ngoại khóa, học bổng, thực tập, việc làm, giao lưu và giải đáp thắc mắc."""


class RagRetrievalTests(unittest.TestCase):
    def test_duplicate_list_item_and_dangling_connector_are_removed(self):
        answer = (
            "Thực hiện đúng quy định của Nhà trường và Khoa:\n"
            "- Tham gia đầy đủ, đúng giờ.\n"
            "Ngoài ra:\n"
            "- Thực hiện đúng quy định của Nhà trường và Khoa."
        )
        self.assertEqual(
            deduplicate_answer_lines(answer),
            "Thực hiện đúng quy định của Nhà trường và Khoa:\n- Tham gia đầy đủ, đúng giờ.",
        )

    def test_coverage_audit_text_is_removed_from_final_answer(self):
        leaked = (
            "- Xác định đúng mục.\n- So sánh câu trả lời.\n"
            "Câu trả lời cuối cùng:\n- Ý một.\n- Ý hai."
        )
        self.assertEqual(extract_final_answer(leaked), "- Ý một.\n- Ý hai.")
        self.assertEqual(
            extract_final_answer("<FINAL>Mở đầu.\n- Ý đầy đủ.</FINAL>"),
            "Mở đầu.\n- Ý đầy đủ.",
        )

    def test_money_spelling_is_not_a_denominator(self):
        for suffix in ("chẵn", "chãn", "chăn", "chắn"):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    normalize_answer(f"Mức hỗ trợ là 5.000.000 đồng/{suffix}."),
                    "Mức hỗ trợ là 5.000.000 đồng chẵn.",
                )

    def test_money_suffix_without_slash_matches_reported_answer(self):
        for suffix in ("chẵn", "chãn", "chăn", "chắn", "chan"):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    normalize_answer(
                        f"Khoa có 200 tân sinh viên sẽ được hỗ trợ kinh phí 7.000.000 đồng {suffix}."
                    ),
                    "Khoa có 200 tân sinh viên sẽ được hỗ trợ kinh phí 7.000.000 đồng chẵn.",
                )
        self.assertEqual(normalize_answer("7.000.000 đồng chăn"), "7.000.000 đồng chẵn")

    def test_correct_money_suffix_is_preserved_and_correction_is_idempotent(self):
        answer = "Mức hỗ trợ là 7.000.000 đồng chẵn."
        self.assertEqual(normalize_answer(answer), answer)
        self.assertEqual(normalize_answer(normalize_answer("7.000.000 đồng/chăn.")), "7.000.000 đồng chẵn.")

    def test_money_suffix_cleanup_does_not_remove_other_words(self):
        answer = "Hỗ trợ 7.000.000 đồng chăn nuôi."
        self.assertEqual(normalize_answer(answer), answer)

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

    def test_content_question_is_detected_as_enumeration(self):
        self.assertTrue(
            asks_for_enumeration("Tân sinh viên được hướng dẫn những nội dung gì?")
        )

    def test_inline_bullets_are_normalized_to_separate_lines(self):
        answer = "- Ý thứ nhất. - Ý thứ hai. - Ý thứ ba."
        self.assertEqual(normalize_answer(answer).count("\n- "), 2)

    def test_markdown_bold_markers_are_removed_for_plain_text_chat(self):
        self.assertEqual(normalize_answer("- **Nhóm:** Nội dung."), "- Nhóm: Nội dung.")

    def test_content_guidance_groups_topics_and_does_not_invent_obligation(self):
        guidance = build_answer_guidance(
            "Trong Tuần định hướng, tân sinh viên được hướng dẫn những nội dung gì?"
        )
        self.assertIn("mọi ý độc lập", guidance)
        self.assertIn("3–5 chủ đề", guidance)
        self.assertIn("Không lấy nội dung của mục hoặc đối tượng khác", guidance)
        self.assertIn("từng chi tiết độc lập vẫn phải xuất hiện", SYSTEM_PROMPT)

    def test_confirmation_question_requires_consistent_verdict(self):
        for question in (
            "Tên trường được viết tắt bằng Dalat Uni đúng không?",
            "Có phải tên viết tắt của Trường là DLU?",
            "Tên viết tắt là DLU phải không?",
        ):
            with self.subTest(question=question):
                self.assertTrue(asks_for_confirmation(question))
                guidance = build_answer_guidance(question)
                self.assertIn("Nếu sai", guidance)
                self.assertIn("Không,", guidance)
                self.assertIn("mâu thuẫn", guidance)

    def test_enumeration_intent_handles_different_phrasings(self):
        questions = (
            "Tân sinh viên có trách nhiệm gì khi tham gia Tuần định hướng?",
            "Sinh viên cần làm những việc nào trong chương trình?",
            "Hãy liệt kê đầy đủ quyền lợi của người học.",
            "Chương trình bao gồm các nội dung nào?",
        )
        for question in questions:
            with self.subTest(question=question):
                self.assertTrue(asks_for_enumeration(question))
                self.assertIn("không dừng", build_answer_guidance(question))

    def test_matching_section_heading_gets_generic_enumeration_bonus(self):
        responsibility = Document(
            page_content=STUDENT_RESPONSIBILITY_SOURCE,
            metadata={"section_title": "TRÁCH NHIỆM", "page": 3},
        )
        faculty = Document(
            page_content="Các Khoa tổ chức Tuần định hướng cho Tân sinh viên.",
            metadata={"section_title": "CÁC KHOA", "page": 3},
        )
        for question in (
            "Tân sinh viên có trách nhiệm gì khi tham gia Tuần định hướng?",
            "Khi dự Tuần định hướng, sinh viên cần thực hiện những việc nào?",
            "Cần làm gì để tham gia Tuần định hướng hiệu quả?",
        ):
            with self.subTest(question=question):
                ranked = rerank_retrieval_results(
                    question,
                    [(faculty, 0.50), (responsibility, 0.35)],
                )
                self.assertIs(ranked[0][0], responsibility)

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

        answer, sources, _score, *_rest = await chain.achat(
            "Kế hoạch số 1340/KH-ĐHĐL được ban hành ngày nào?",
            active_filenames=[filename, "Quy_che_dao_tao_theo_tin_chi.pdf"],
        )

        self.assertEqual(answer, "Kế hoạch được ban hành ngày 12/8/2026.")
        self.assertEqual(store.search_kwargs["filter"], {"filename": filename})
        self.assertEqual(store.search_kwargs["k"], RETRIEVAL_CANDIDATE_K)
        self.assertEqual(sources[0]["page"], 1)

    async def test_content_question_expands_section_across_pages_until_next_heading(self):
        filename = "1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf"
        content_anchor = Document(
            page_content="III. NÓI DUNG - Giới thiệu tổng quan về Khoa.",
            metadata={"filename": filename, "source": filename, "page": 1, "section_title": "NỘI DUNG", "chunk_index": 2},
        )
        responsibility = Document(
            page_content="5.6 Các Khoa xây dựng chương trình Tuần định hướng.",
            metadata={"filename": filename, "source": filename, "page": 3, "section_title": "CÁC KHOA", "chunk_index": 5},
        )
        records = {
            "ids": [
                f"{filename}_chunk_3",
                f"{filename}_chunk_2",
                f"{filename}_chunk_4",
                f"{filename}_chunk_5",
            ],
            "documents": [
                "Hướng dẫn thời khóa biểu, lịch thi và đăng ký học phần.",
                content_anchor.page_content,
                "Trang tiếp theo: thực tập, việc làm và giải đáp các câu hỏi.",
                "IV. KINH PHÍ - Nhà trường hỗ trợ kinh phí tổ chức.",
            ],
            "metadatas": [
                {"filename": filename, "source": filename, "page": 1, "chunk_index": 3, "section_title": "NỘI DUNG"},
                {"filename": filename, "source": filename, "page": 1, "chunk_index": 2, "section_title": "NỘI DUNG"},
                {"filename": filename, "source": filename, "page": 2, "chunk_index": 4},
                {"filename": filename, "source": filename, "page": 3, "chunk_index": 5, "section_title": "KINH PHÍ"},
            ],
        }
        store = _FakeVectorStore(
            [(responsibility, 1.30), (content_anchor, 1.64)],
            records,
        )
        llm = _FakeLlm([GROUPED_ORIENTATION_ANSWER])
        chain = RAGChain()
        chain._vector_store = store
        chain._llm = llm

        await chain.achat(
            "Trong Tuần định hướng, tân sinh viên được hướng dẫn những nội dung gì?",
            active_filenames=[filename, "So_tay_sinh_vien.pdf"],
        )

        self.assertEqual(
            store.search_query,
            "Trong Tuần định hướng, tân sinh viên được hướng dẫn những nội dung gì?",
        )
        self.assertEqual(store.search_kwargs["filter"], {"filename": filename})
        rendered_prompt = "\n".join(str(message.content) for message in llm.messages)
        self.assertLess(
            rendered_prompt.index("Giới thiệu tổng quan"),
            rendered_prompt.index("Hướng dẫn thời khóa biểu"),
        )
        self.assertIn("Trang tiếp theo: thực tập", rendered_prompt)
        self.assertNotIn("IV. KINH PHÍ", rendered_prompt)
        self.assertNotIn("5.6 Các Khoa", rendered_prompt)

    async def test_incomplete_enumeration_answer_gets_generic_coverage_pass(self):
        filename = "1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf"
        anchor = Document(
            page_content=ORIENTATION_SOURCE,
            metadata={"filename": filename, "source": filename, "page": 1},
        )
        records = {
            "ids": [f"{filename}_chunk_0", f"{filename}_chunk_1"],
            "documents": [anchor.page_content, "IV. KINH PHÍ"],
            "metadatas": [
                {
                    "filename": filename,
                    "source": filename,
                    "page": index + 1,
                    "chunk_index": index,
                }
                for index in range(2)
            ],
        }
        answer_llm = _FakeLlm(["Câu dẫn.\n- Nhóm 1\n- Nhóm 2"])
        audit_llm = _FakeLlm([GROUPED_ORIENTATION_ANSWER])
        chain = RAGChain()
        chain._vector_store = _FakeVectorStore([(anchor, 1.60)], records)
        chain._llm = answer_llm
        chain._audit_llm = audit_llm

        answer, _sources, _score, *_rest = await chain.achat(
            "Tuần định hướng hướng dẫn tân sinh viên những nội dung gì?",
            document_filename=filename,
            active_filenames=[filename],
        )

        self.assertEqual(answer_llm.calls, 1)
        self.assertEqual(audit_llm.calls, 1)
        self.assertEqual(answer, GROUPED_ORIENTATION_ANSWER)


if __name__ == "__main__":
    unittest.main()
