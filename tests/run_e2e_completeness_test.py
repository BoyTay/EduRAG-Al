"""
Script kiểm thử tự động đánh giá Tính Hoàn Thiện của Câu Trả Lời EduRAG AI.
Thực thi toàn bộ kịch bản kiểm thử theo kế hoạch:
- Ưu tiên 1: PDF Scan 1 (1340-KH-DHDL...)
- Ưu tiên 2: PDF Scan 2 (Chuan_dau_ra_ngoai_ngu_tin_hoc.pdf)
- Ưu tiên 3: PDF Text 1 (Quy_che_dao_tao_theo_tin_chi.pdf)
- Ưu tiên 4: PDF Text 2 (So_tay_sinh_vien.pdf)
- Ưu tiên 5: Edge cases & Refusals (Kiểm tra Rule 14, False/True Refusal)

Đánh giá theo 6 trục tiêu chuẩn chất lượng (Rubric):
C1: Coverage & Enumeration (Đủ ý, không cắt cụt)
C2: Syntactic Integrity (Câu hoàn chỉnh, kết thúc bằng dấu câu)
C3: Anti-Hallucination & Rule 14 (Không tự bịa câu kết nghĩa vụ)
C4: Data Precision (Số tiền, ngày tháng, không lỗi 'đồng/chẵn')
C5: Source Attribution (Đúng tên file, đúng số trang)
C6: Multi-turn & Refusal (Kế thừa ngữ cảnh, từ chối chuẩn xác)
"""

import argparse
import asyncio
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

# Thêm backend vào sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from backend.rag_chain import RAGChain, normalize_answer
    from backend.db import SessionLocal, log_activity, DocumentMetadata
except ImportError:
    from rag_chain import RAGChain, normalize_answer  # type: ignore # pyrefly: ignore [missing-import]
    from db import SessionLocal, log_activity, DocumentMetadata  # type: ignore # pyrefly: ignore [missing-import]


# ─────────────────────────────────────────────────────────────────────────────
# ĐỊNH NGHĨA TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    id: str
    group: str
    priority: int  # 1 (cao nhất) đến 5
    question: str
    expected_doc: Optional[str] = None
    expected_keywords: List[str] = field(default_factory=list)
    forbidden_phrases: List[str] = field(default_factory=list)
    required_numbers: List[str] = field(default_factory=list)
    is_multi_turn: bool = False
    turn1_question: Optional[str] = None
    is_edge_refusal: bool = False
    notes: str = ""


TEST_CASES: List[TestCase] = [
    # ─── NHÓM I: PDF SCAN 1 (1340-KH-DHDL...) - ƯU TIÊN 1 ───────────────────
    TestCase(
        id="TC-SCAN-01",
        group="PDF Scan: 1340-KH-DHDL",
        priority=1,
        question="Trong Tuần định hướng, tân sinh viên khóa 50 được hướng dẫn những nội dung gì?",
        expected_doc="1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf",
        expected_keywords=[
            "giới thiệu", "khoa", "thời khóa biểu", "thư viện", 
            "công nghệ thông tin", "đăng ký học phần", "kỹ năng"
        ],
        forbidden_phrases=[
            "đồng/chẵn", "đồng/chãn", "đồng/chăn",
            "sinh viên cần tuân thủ đầy đủ các quy định trên",
            "đây là điều bắt buộc với mọi sinh viên",
        ],
        notes="Kiểm tra bao phủ danh sách nội dung dài, mở rộng section chunks, không ngắt cụt.",
    ),
    TestCase(
        id="TC-SCAN-02",
        group="PDF Scan: 1340-KH-DHDL",
        priority=1,
        question="Tân sinh viên có trách nhiệm gì khi tham gia Tuần định hướng?",
        expected_doc="1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf",
        expected_keywords=["nghiêm túc", "đầy đủ", "đúng giờ", "lắng nghe", "ghi chép"],
        forbidden_phrases=["xây dựng kế hoạch chi tiết", "ban giám hiệu", "kinh phí"],
        notes="Trích xuất đúng mục 5.8 trách nhiệm SV, không nhầm sang trách nhiệm của Khoa.",
    ),
    TestCase(
        id="TC-SCAN-03",
        group="PDF Scan: 1340-KH-DHDL",
        priority=1,
        question="Nhà trường hỗ trợ kinh phí cho các Khoa tổ chức Tuần định hướng như thế nào?",
        expected_doc="1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf",
        expected_keywords=["kinh phí", "5.000.000", "7.000.000"],
        required_numbers=["5.000.000", "7.000.000"],
        forbidden_phrases=["đồng/chẵn", "đồng/chãn", "đồng/chăn", "đồng/chan"],
        notes="Kiểm tra xử lý số tiền và chống lỗi OCR biến chẵn thành mẫu số.",
    ),
    TestCase(
        id="TC-SCAN-04",
        group="PDF Scan: 1340-KH-DHDL",
        priority=1,
        question="Kế hoạch số 1340/KH-ĐHĐL được ban hành vào ngày tháng năm nào và do ai ban hành?",
        expected_doc="1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf",
        expected_keywords=["12", "8", "2026", "đại học đà lạt"],
        notes="Bóc tách chính xác số hiệu văn bản và ngày ban hành từ đầu trang scan OCR.",
    ),
    TestCase(
        id="TC-SCAN-05",
        group="PDF Scan: 1340-KH-DHDL",
        priority=1,
        question="Còn địa điểm tổ chức ở đâu?",
        expected_doc="1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf",
        is_multi_turn=True,
        turn1_question="Thời gian tổ chức Tuần định hướng diễn ra khi nào?",
        expected_keywords=["khoa", "hội trường", "trường"],
        notes="Hội thoại đa lượt: câu hỏi ngắn tiếp nối được bổ sung ngữ cảnh để retrieval.",
    ),

    # ─── NHÓM II: PDF SCAN 2 (Chuan_dau_ra_ngoai_ngu_tin_hoc.pdf) - ƯU TIÊN 2 ──
    TestCase(
        id="TC-SCAN-06",
        group="PDF Scan: Ngoại ngữ & Tin học",
        priority=2,
        question="Chuẩn đầu ra tin học đối với sinh viên chính quy bao gồm những chứng chỉ nào?",
        expected_doc="Chuan_dau_ra_ngoai_ngu_tin_hoc.pdf",
        expected_keywords=["công nghệ thông tin", "cơ bản", "chứng chỉ"],
        forbidden_phrases=["sinh viên cần tuân thủ đầy đủ"],
        notes="Liệt kê đầy đủ các chứng chỉ tin học được công nhận.",
    ),
    TestCase(
        id="TC-SCAN-07",
        group="PDF Scan: Ngoại ngữ & Tin học",
        priority=2,
        question="Quy định chuẩn đầu ra tiếng Anh đối với sinh viên đại học chính quy như thế nào?",
        expected_doc="Chuan_dau_ra_ngoai_ngu_tin_hoc.pdf",
        expected_keywords=["tiếng anh", "chuẩn", "ngành"],
        forbidden_phrases=["đồng/chẵn"],
        notes="Độ hoàn thiện khi tổng hợp ma trận chuẩn tiếng Anh theo các nhóm ngành.",
    ),
    TestCase(
        id="TC-SCAN-08",
        group="PDF Scan: Ngoại ngữ & Tin học",
        priority=2,
        question="Thời hạn hiệu lực của chứng chỉ tiếng Anh quốc tế để xét chuẩn đầu ra là bao lâu?",
        expected_doc="Chuan_dau_ra_ngoai_ngu_tin_hoc.pdf",
        expected_keywords=["chứng chỉ", "tháng"],
        notes="Kiểm tra trích xuất thời hạn chứng chỉ và quy định xét miễn.",
    ),
    TestCase(
        id="TC-SCAN-09",
        group="PDF Scan: Ngoại ngữ & Tin học",
        priority=2,
        question="Còn điều kiện về tin học thì sao?",
        expected_doc="Chuan_dau_ra_ngoai_ngu_tin_hoc.pdf",
        is_multi_turn=True,
        turn1_question="Chuẩn đầu ra tiếng Anh áp dụng cho sinh viên như thế nào?",
        expected_keywords=["tin học", "công nghệ thông tin", "chuẩn"],
        notes="Hội thoại đa lượt chuyển từ chuẩn ngoại ngữ sang chuẩn tin học.",
    ),

    # ─── NHÓM III: PDF TEXT 1 (Quy_che_dao_tao_theo_tin_chi.pdf) - ƯU TIÊN 3 ──
    TestCase(
        id="TC-TEXT-10",
        group="PDF Text: Quy chế đào tạo",
        priority=3,
        question="Những trường hợp nào sinh viên sẽ bị cảnh báo học tập hoặc bị buộc thôi học?",
        expected_doc="Quy_che_dao_tao_theo_tin_chi.pdf|So_tay_sinh_vien.pdf",
        expected_keywords=["cảnh báo", "buộc thôi học", "điểm trung bình", "học kỳ"],
        notes="Liệt kê danh sách điều kiện dài, kiểm tra MAX_SECTION_CHUNKS hoạt động.",
    ),
    TestCase(
        id="TC-TEXT-11",
        group="PDF Text: Quy chế đào tạo",
        priority=3,
        question="Điều kiện để sinh viên được xét và công nhận tốt nghiệp đại học gồm những gì?",
        expected_doc="Quy_che_dao_tao_theo_tin_chi.pdf|So_tay_sinh_vien.pdf",
        expected_keywords=["tốt nghiệp", "tín chỉ", "điểm trung bình", "chuẩn đầu ra"],
        notes="Kiểm tra tính hoàn chỉnh của danh sách tiêu chuẩn tốt nghiệp.",
    ),
    TestCase(
        id="TC-TEXT-12",
        group="PDF Text: Quy chế đào tạo",
        priority=3,
        question="Cách quy đổi điểm chữ sang thang điểm 4 và xếp loại học lực được tính thế nào?",
        expected_doc="Quy_che_dao_tao_theo_tin_chi.pdf|So_tay_sinh_vien.pdf",
        expected_keywords=["thang điểm 4", "xuất sắc", "giỏi", "khá", "trung bình"],
        notes="Kiểm tra trình bày bảng thang điểm và xếp loại học lực.",
    ),

    # ─── NHÓM IV: PDF TEXT 2 (So_tay_sinh_vien.pdf) - ƯU TIÊN 4 ───────────────
    TestCase(
        id="TC-TEXT-13",
        group="PDF Text: Sổ tay sinh viên",
        priority=4,
        question="Tiêu chuẩn và điều kiện để được xét cấp học bổng khuyến khích học tập là gì?",
        expected_doc="So_tay_sinh_vien.pdf",
        expected_keywords=["học bổng", "khuyến khích", "học tập"],
        notes="Kiểm tra trích xuất quy chế học bổng trong file lớn ~3.5MB.",
    ),
    TestCase(
        id="TC-TEXT-14",
        group="PDF Text: Sổ tay sinh viên",
        priority=4,
        question="Điểm rèn luyện của sinh viên được đánh giá theo những khung tiêu chí nào?",
        expected_doc="So_tay_sinh_vien.pdf|Quy_che_dao_tao_theo_tin_chi.pdf",
        expected_keywords=["rèn luyện", "tiêu chí", "học tập", "hoạt động"],
        notes="Kiểm tra bao quát đủ 5 tiêu chí đánh giá rèn luyện.",
    ),
    TestCase(
        id="TC-TEXT-15",
        group="PDF Text: Sổ tay sinh viên",
        priority=4,
        question="Sinh viên cần làm gì khi bị mất thẻ bảo hiểm y tế hoặc muốn gia hạn BHYT?",
        expected_doc="So_tay_sinh_vien.pdf",
        expected_keywords=["bảo hiểm y tế", "thẻ", "công tác sinh viên"],
        notes="Kiểm tra câu trả lời hướng dẫn thủ tục hành chính.",
    ),

    # ─── NHÓM V: EDGE CASES & REFUSALS - ƯU TIÊN 5 ───────────────────────────
    TestCase(
        id="TC-EDGE-16",
        group="Edge & Refusal",
        priority=5,
        question="Hôm nay canteen trường bán những món ăn gì và giá bao nhiêu?",
        is_edge_refusal=True,
        notes="Câu hỏi ngoài phạm vi: Phải từ chối lịch sự, ghi nhận log rag_refusal.",
    ),
    TestCase(
        id="TC-EDGE-17",
        group="Edge & Refusal",
        priority=5,
        question="Quy chế nhà trường có bắt buộc sinh viên phải mặc áo vest đi học hàng ngày không?",
        expected_keywords=["không", "quy chế", "quy định"],
        forbidden_phrases=[
            "sinh viên cần tuân thủ",
            "đây là điều bắt buộc",
            "chúc các bạn sinh viên",
        ],
        notes="Bẫy Rule 14: Phủ định chính xác, tuyệt đối không bịa câu kết nghĩa vụ.",
    ),
    TestCase(
        id="TC-EDGE-18",
        group="Edge & Refusal",
        priority=5,
        question="Còn điều gì khác nữa không?",
        is_edge_refusal=True,
        notes="Câu hỏi lửng lơ không ngữ cảnh: Hệ thống phải báo cần nêu rõ câu hỏi.",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# LOGIC CHẤM ĐIỂM & ĐÁNH GIÁ (RUBRIC EVALUATOR)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EvaluationResult:
    tc: TestCase
    answer: str
    sources: List[Dict[str, Any]]
    evidence_score: float
    refusal_reason: Optional[str]
    duration_s: float
    c1_coverage: bool = False
    c2_integrity: bool = False
    c3_anti_hallucination: bool = False
    c4_data_precision: bool = False
    c5_source_attribution: bool = False
    c6_refusal_logic: bool = False
    overall_status: str = "FAIL"  # PASS, WARN, FAIL
    fail_reasons: List[str] = field(default_factory=list)


def evaluate_test_case(tc: TestCase, answer: str, sources: List[Dict[str, Any]], 
                       score: float, refusal_reason: Optional[str], duration: float) -> EvaluationResult:
    res = EvaluationResult(
        tc=tc,
        answer=answer,
        sources=sources,
        evidence_score=score,
        refusal_reason=refusal_reason,
        duration_s=duration,
        fail_reasons=[],
    )
    lower_ans = answer.lower()

    # 1. Edge Refusal Case (TC-EDGE-16, TC-EDGE-18)
    if tc.is_edge_refusal:
        # Kỳ vọng từ chối hoặc trả lời rõ là không có thông tin
        is_refusal = (
            refusal_reason is not None or
            "không có thông tin" in lower_ans or
            "không tìm thấy" in lower_ans or
            "không đề cập" in lower_ans or
            "vui lòng nêu rõ" in lower_ans or
            "chưa rõ" in lower_ans
        )
        res.c6_refusal_logic = is_refusal
        res.c2_integrity = bool(answer.strip().endswith((".", "!", "?", '"', "'")))
        res.c3_anti_hallucination = True
        res.c1_coverage = is_refusal
        res.c4_data_precision = True
        res.c5_source_attribution = True

        if is_refusal and res.c2_integrity:
            res.overall_status = "PASS"
        else:
            res.overall_status = "FAIL"
            res.fail_reasons.append("Hệ thống không từ chối đúng đối với câu hỏi ngoài phạm vi.")
        return res

    # 2. C1: Coverage & Enumeration
    missing_keywords = [kw for kw in tc.expected_keywords if kw.lower() not in lower_ans]
    word_count = len(answer.split())
    if len(missing_keywords) <= 1 and word_count >= 20:
        res.c1_coverage = True
    else:
        res.c1_coverage = False
        res.fail_reasons.append(f"C1 Thiếu từ khóa trọng tâm: {missing_keywords} (Độ dài: {word_count} từ)")

    # 3. C2: Syntactic Integrity
    stripped = answer.strip()
    ends_cleanly = bool(re.search(r"[.!?'\":)\]\d]$", stripped))
    has_dangling = any(stripped.endswith(dan) for dan in ["Ngoài ra,", "Bên cạnh đó,", "Và,", "Đồng thời,"])
    if ends_cleanly and not has_dangling:
        res.c2_integrity = True
    else:
        res.c2_integrity = False
        res.fail_reasons.append("C2 Câu kết bị đứt đoạn hoặc có liên từ mồ côi ở cuối.")

    # 4. C3: Anti-Hallucination & Rule 14
    found_forbidden = [phrase for phrase in tc.forbidden_phrases if phrase.lower() in lower_ans]
    moral_patterns = [
        r"sinh viên cần tuân thủ đầy đủ các quy định trên",
        r"đây là điều bắt buộc với mọi sinh viên",
        r"chúc các bạn sinh viên",
        r"hy vọng các bạn sinh viên sẽ",
    ]
    has_moral_closing = any(re.search(pat, lower_ans) for pat in moral_patterns)
    if not found_forbidden and not has_moral_closing:
        res.c3_anti_hallucination = True
    else:
        res.c3_anti_hallucination = False
        res.fail_reasons.append(f"C3 Vi phạm Rule 14 (Chứa cụm cấm/bịa đặt): {found_forbidden or 'Câu kết giáo điều'}")

    # 5. C4: Data Precision
    has_bad_money = any(bad in lower_ans for bad in ["đồng/chẵn", "đồng/chãn", "đồng/chăn", "đồng/chan"])
    missing_numbers = [num for num in tc.required_numbers if num not in answer]
    if not has_bad_money and not missing_numbers:
        res.c4_data_precision = True
    else:
        res.c4_data_precision = False
        res.fail_reasons.append(f"C4 Sai dữ liệu (Lỗi OCR/Số tiền: bad_money={has_bad_money}, thiếu số={missing_numbers})")

    # 6. C5: Source Attribution
    if sources and len(sources) > 0:
        primary_source = sources[0]
        has_page = primary_source.get("page", 0) > 0
        if tc.expected_doc:
            accepted_docs = [d.strip().lower() for d in tc.expected_doc.split("|")]
            doc_matched = any(
                ad in str(primary_source.get("filename", "")).lower() or
                ad in str(primary_source.get("source", "")).lower()
                for ad in accepted_docs
            )
        else:
            doc_matched = True
        
        if doc_matched and has_page:
            res.c5_source_attribution = True
        else:
            res.c5_source_attribution = False
            res.fail_reasons.append(f"C5 Nguồn không khớp hoặc thiếu trang: doc_matched={doc_matched}, page={primary_source.get('page')}")
    else:
        res.c5_source_attribution = False
        res.fail_reasons.append("C5 Không trả về nguồn trích dẫn nào.")

    # 7. C6: Refusal & Multi-turn
    if refusal_reason is not None:
        res.c6_refusal_logic = False
        res.fail_reasons.append(f"C6 Bị từ chối oan uổng (False Refusal: {refusal_reason})")
    else:
        res.c6_refusal_logic = True

    # 8. Overall Status
    crit_passes = [res.c1_coverage, res.c2_integrity, res.c3_anti_hallucination, 
                   res.c4_data_precision, res.c5_source_attribution, res.c6_refusal_logic]
    
    if all(crit_passes):
        res.overall_status = "PASS"
    elif sum(crit_passes) >= 4 and res.c2_integrity and res.c3_anti_hallucination:
        res.overall_status = "WARN"
    else:
        res.overall_status = "FAIL"

    return res


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER CHÍNH
# ─────────────────────────────────────────────────────────────────────────────

async def run_completeness_tests(
    test_filter_group: Optional[str] = None,
    test_filter_id: Optional[str] = None,
    report_path: Optional[Path] = None,
) -> Tuple[List[EvaluationResult], str]:
    print("=" * 80)
    print("KHỞI ĐỘNG HỆ THỐNG KIỂM THỬ TÍNH HOÀN THIỆN CÂU TRẢ LỜI EDURAG")
    print("=" * 80)

    # 1. Khởi tạo RAG Chain
    chain = RAGChain()
    chain.initialize()

    # 2. Lấy danh sách tài liệu active trong DB
    active_filenames = []
    db = SessionLocal()
    try:
        docs = db.query(DocumentMetadata).filter(DocumentMetadata.status == "active").all()
        active_filenames = [d.filename for d in docs]
    finally:
        db.close()
    
    print(f"Tài liệu Active trong DB ({len(active_filenames)} tệp):")
    for fn in active_filenames:
        print(f"   - {fn}")

    # 3. Lọc danh sách test cases
    filtered_cases = TEST_CASES
    if test_filter_id:
        filtered_cases = [tc for tc in filtered_cases if tc.id == test_filter_id]
    elif test_filter_group == "scan-only":
        filtered_cases = [tc for tc in filtered_cases if tc.priority in (1, 2)]
    
    print(f"\nTổng số ca kiểm thử sẽ chạy: {len(filtered_cases)} test cases\n")

    results: List[EvaluationResult] = []

    for idx, tc in enumerate(filtered_cases, 1):
        print("-" * 80)
        print(f"[{idx}/{len(filtered_cases)}] Đang chạy {tc.id} (Ưu tiên {tc.priority}) - Nhóm: {tc.group}")
        print(f"Câu hỏi: {tc.question}")

        conversation_history = None
        start_time = time.time()

        # Xử lý hội thoại đa lượt
        if tc.is_multi_turn and tc.turn1_question:
            print(f"   [Lượt 1]: {tc.turn1_question}")
            t1_ans, t1_src, t1_sc, t1_ref = await chain.achat(
                tc.turn1_question,
                active_filenames=active_filenames,
            )
            conversation_history = [
                {"question": tc.turn1_question, "answer": t1_ans}
            ]
            print(f"   [Lượt 2]: {tc.question}")

        # Chạy câu hỏi kiểm thử chính
        answer, sources, avg_score, refusal_reason = await chain.achat(
            tc.question,
            conversation_history=conversation_history,
            active_filenames=active_filenames,
        )
        duration = time.time() - start_time

        # Ghi log rag_refusal vào DB nếu bị từ chối
        if refusal_reason is not None:
            db = SessionLocal()
            try:
                log_activity(
                    db, "rag_refusal", "chat",
                    f"{tc.question[:100]} [{refusal_reason}]",
                    "test_runner@edurag.internal", "tester"
                )
            finally:
                db.close()

        # Đánh giá kết quả
        res = evaluate_test_case(tc, answer, sources, avg_score, refusal_reason, duration)
        results.append(res)

        status_emoji = "PASS" if res.overall_status == "PASS" else ("WARN" if res.overall_status == "WARN" else "FAIL")
        print(f"Kết quả: [{status_emoji}] | Thời gian: {duration:.2f}s | Score: {avg_score:.3f}")
        first_line = answer.split("\n")[0] if answer else ""
        print(f"Trả lời ({len(answer.split())} từ): {first_line[:140]}...")
        if res.fail_reasons:
            print(f"   Vấn đề: {'; '.join(res.fail_reasons)}")
        if sources:
            src_str = ", ".join([f"{s.get('filename')} (trang {s.get('page')})" for s in sources[:2]])
            print(f"   Nguồn: {src_str}")

    # 4. Tạo báo cáo Markdown
    report_content = generate_markdown_report(results, active_filenames)
    if report_path is None:
        report_path = Path(__file__).resolve().parent / "completeness_test_report.md"
    
    report_path.write_text(report_content, encoding="utf-8")
    print("\n" + "=" * 80)
    print("KIỂM THỬ HOÀN TẤT! Báo cáo chi tiết đã lưu tại:")
    print(f"👉 {report_path}")
    print("=" * 80)

    return results, report_content


# ─────────────────────────────────────────────────────────────────────────────
# TẠO BÁO CÁO MARKDOWN
# ─────────────────────────────────────────────────────────────────────────────

def generate_markdown_report(results: List[EvaluationResult], active_filenames: List[str]) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.overall_status == "PASS")
    warned = sum(1 for r in results if r.overall_status == "WARN")
    failed = sum(1 for r in results if r.overall_status == "FAIL")
    pass_rate = (passed / total * 100) if total > 0 else 0
    avg_duration = sum(r.duration_s for r in results) / total if total > 0 else 0

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = []
    md.append("# Báo cáo Kiểm thử Tính Hoàn Thiện Câu Trả Lời EduRAG AI\n")
    md.append(f"- **Thời gian kiểm thử**: `{now_str}`")
    md.append(f"- **Mô hình LLM**: `Qwen2.5-7B` (Ollama)")
    md.append(f"- **Mô hình Embedding**: `AITeamVN/Vietnamese_Embedding`")
    md.append(f"- **Số tài liệu tham chiếu**: `{len(active_filenames)} tệp active`\n")

    md.append("## 1. Tổng quan Chỉ số Đạt chuẩn (Overview Metrics)\n")
    md.append("| Tổng số TC | Đạt (PASS) | Cảnh báo (WARN) | Không đạt (FAIL) | Tỷ lệ Đạt | Thời gian TB |")
    md.append("|:---:|:---:|:---:|:---:|:---:|:---:|")
    md.append(f"| **{total}** | **{passed}** | **{warned}** | **{failed}** | **{pass_rate:.1f}%** | **{avg_duration:.2f}s** |\n")

    # Bảng phân nhóm
    groups = {}
    for r in results:
        groups.setdefault(r.tc.group, []).append(r)

    md.append("## 2. Kết quả theo Phân nhóm Tài liệu (Group Breakdown)\n")
    md.append("| Nhóm kiểm thử | Độ ưu tiên | Tổng TC | PASS | WARN | FAIL | Tỷ lệ đạt |")
    md.append("|---|:---:|:---:|:---:|:---:|:---:|:---:|")
    for grp_name, group_res in groups.items():
        g_total = len(group_res)
        g_pass = sum(1 for r in group_res if r.overall_status == "PASS")
        g_warn = sum(1 for r in group_res if r.overall_status == "WARN")
        g_fail = sum(1 for r in group_res if r.overall_status == "FAIL")
        g_rate = (g_pass / g_total * 100) if g_total > 0 else 0
        prio = group_res[0].tc.priority
        md.append(f"| **{grp_name}** | Ưu tiên {prio} | {g_total} | {g_pass} | {g_warn} | {g_fail} | **{g_rate:.1f}%** |")
    md.append("\n---\n")

    md.append("## 3. Bảng Chi tiết Từng Ca Kiểm thử (Detailed Test Cases)\n")
    md.append("| Mã TC | Nhóm | Câu hỏi | Trạng thái | Điểm tương đồng | Lỗi / Cảnh báo ghi nhận |")
    md.append("|---|---|---|:---:|:---:|---|")
    for r in results:
        status_badge = "✅ PASS" if r.overall_status == "PASS" else ("⚠️ WARN" if r.overall_status == "WARN" else "❌ FAIL")
        fail_note = "<br>".join(r.fail_reasons) if r.fail_reasons else "Thỏa mãn 6 trục tiêu chí"
        md.append(f"| **{r.tc.id}** | {r.tc.group} | {r.tc.question} | {status_badge} | `{r.evidence_score:.3f}` | {fail_note} |")
    md.append("\n---\n")

    md.append("## 4. Chi tiết Nội dung & Đánh giá 6 Trục (Rubric Inspection)\n")
    for r in results:
        status_emoji = "✅ PASS" if r.overall_status == "PASS" else ("⚠️ WARN" if r.overall_status == "WARN" else "❌ FAIL")
        md.append(f"### {r.tc.id}: {r.tc.question} — {status_emoji}\n")
        md.append(f"- **Nhóm**: `{r.tc.group}` (Độ ưu tiên: {r.tc.priority})")
        md.append(f"- **Thời gian xử lý**: `{r.duration_s:.2f}s` | **Evidence Score**: `{r.evidence_score:.3f}`")
        if r.refusal_reason:
            md.append(f"- **Refusal Reason**: `{r.refusal_reason}`")
        
        md.append("\n**Kết quả kiểm tra 6 tiêu chuẩn:**")
        md.append(f"- **C1 (Độ bao phủ & Đầy đủ)**: {'✅ Đạt' if r.c1_coverage else '❌ Không đạt'}")
        md.append(f"- **C2 (Toàn vẹn câu chữ)**: {'✅ Đạt' if r.c2_integrity else '❌ Không đạt'}")
        md.append(f"- **C3 (Chống bịa đặt - Rule 14)**: {'✅ Đạt' if r.c3_anti_hallucination else '❌ Không đạt'}")
        md.append(f"- **C4 (Chính xác dữ liệu & OCR)**: {'✅ Đạt' if r.c4_data_precision else '❌ Không đạt'}")
        md.append(f"- **C5 (Độ chính xác nguồn & trang)**: {'✅ Đạt' if r.c5_source_attribution else '❌ Không đạt'}")
        md.append(f"- **C6 (Hội thoại tiếp nối / Từ chối)**: {'✅ Đạt' if r.c6_refusal_logic else '❌ Không đạt'}")

        clean_answer = r.answer.replace("\n", "\n> ")
        md.append(f"\n**Nội dung câu trả lời của AI:**\n> {clean_answer}\n")

        if r.sources:
            md.append("**Trích dẫn nguồn:**")
            for s in r.sources:
                md.append(f"- File: `{s.get('filename')}` | Trang: `{s.get('page')}` | Đoạn: `{s.get('snippet', '')[:100]}...`")
        md.append("\n---\n")

    md.append("## 5. Đánh giá & Khuyến nghị Tinh chỉnh Hệ thống (Actionable Insights)\n")
    false_refusals = [r for r in results if not r.tc.is_edge_refusal and r.refusal_reason is not None]
    if false_refusals:
        md.append(f"> [!WARNING]\n> Phát hiện {len(false_refusals)} câu hỏi hợp lệ bị từ chối oan uổng (False Refusal). Cần xem xét hạ `MIN_RELEVANCE_SCORE` từ `0.30` xuống `0.25` trong file `.env`.\n")
    else:
        md.append("> [!TIP]\n> Ngưỡng `MIN_RELEVANCE_SCORE=0.30` hoạt động rất tốt với mô hình `AITeamVN/Vietnamese_Embedding`, không có câu hỏi hợp lệ nào bị từ chối sai.\n")

    rule14_violations = [r for r in results if not r.c3_anti_hallucination]
    if rule14_violations:
        md.append(f"> [!CAUTION]\n> Phát hiện {len(rule14_violations)} câu vi phạm Rule 14 (tự bịa câu kết nghĩa vụ). Cần tăng cường prompt constraints.\n")
    else:
        md.append("> [!NOTE]\n> Hệ thống tuân thủ 100% Rule 14: Không xuất hiện câu kết đạo đức, giáo điều hoặc tự sinh nghĩa vụ.\n")

    return "\n".join(md)


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run EduRAG Answer Completeness E2E Tests")
    parser.add_argument("--scan-only", action="store_true", help="Chỉ kiểm thử 2 file PDF Scan (Ưu tiên 1 và 2)")
    parser.add_argument("--case", type=str, default=None, help="Chạy một test case cụ thể (vd: TC-SCAN-01)")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn file báo cáo Markdown xuất ra")
    args = parser.parse_args()

    group_filter = "scan-only" if args.scan_only else None
    out_path = Path(args.output) if args.output else None

    asyncio.run(run_completeness_tests(
        test_filter_group=group_filter,
        test_filter_id=args.case,
        report_path=out_path,
    ))


if __name__ == "__main__":
    main()
