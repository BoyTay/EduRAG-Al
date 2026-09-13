"""
rag_chain.py - Pipeline RAG chính
Kết hợp Chroma retriever + Qwen2.5-7B (Ollama) + LangChain để trả lời câu hỏi
dựa trên tài liệu được cung cấp.
"""

import os
import re
import unicodedata
from pathlib import Path
from typing import Mapping, Optional, Sequence

import torch
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from loguru import logger

# ─── Cấu hình ─────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
# Model embedding tiếng Việt tốt nhất hiện tại:
# - "AITeamVN/Vietnamese_Embedding" (~560MB, fine-tuned 300k VI triplets)
# - "BAAI/bge-m3" (~2.3GB, multilingual, hỗ trợ VI xuất sắc)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "AITeamVN/Vietnamese_Embedding")
CHROMA_PATH = os.getenv("CHROMA_PATH", str(Path(__file__).parent.parent / "chroma_db"))
COLLECTION_NAME = "edurag_docs"
# The active collection name is persisted separately so a completed staging
# rebuild remains active after the backend restarts.
ACTIVE_COLLECTION_FILE = Path(CHROMA_PATH) / ".active_collection"
def _read_top_k() -> int:
    """Read the bounded number of chunks sent to the answer model."""
    raw_value = os.getenv("TOP_K", "8")
    try:
        return min(12, max(5, int(raw_value)))
    except ValueError:
        logger.warning("TOP_K='{}' không hợp lệ; dùng 8", raw_value)
        return 8


TOP_K = _read_top_k()


def _read_candidate_k() -> int:
    """Read a wider first-stage retrieval pool for deterministic reranking."""
    raw_value = os.getenv("RETRIEVAL_CANDIDATE_K", "30")
    try:
        return min(50, max(TOP_K, int(raw_value)))
    except ValueError:
        logger.warning("RETRIEVAL_CANDIDATE_K='{}' không hợp lệ; dùng 30", raw_value)
        return 30


RETRIEVAL_CANDIDATE_K = _read_candidate_k()


def _read_relevance_threshold() -> float:
    """Read a safe score threshold without making a bad env value break startup."""
    raw_value = os.getenv("MIN_RELEVANCE_SCORE", "0.30")
    try:
        return min(1.0, max(0.0, float(raw_value)))
    except ValueError:
        logger.warning(f"MIN_RELEVANCE_SCORE='{raw_value}' không hợp lệ; dùng 0.30")
        return 0.30


MIN_RELEVANCE_SCORE = _read_relevance_threshold()

# ─── Phát hiện GPU ────────────────────────────────────────────────────────────

def _get_device() -> str:
    """Phát hiện GPU khả dụng; fallback về CPU."""
    if torch.cuda.is_available():
        logger.info(f"GPU detected: {torch.cuda.get_device_name(0)} — using CUDA")
        return "cuda"
    logger.info("No GPU detected — using CPU for embeddings")
    return "cpu"


# ─── Khởi tạo Embedding Model ─────────────────────────────────────────────────

def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    Tải BAAI/bge-small-vi embedding model.
    Tự động dùng GPU nếu khả dụng.
    """
    device = _get_device()
    model_kwargs = {"device": device}
    encode_kwargs = {
        "normalize_embeddings": True,  # Cần thiết cho cosine similarity
        "batch_size": 32,
    }
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL} on {device}")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs,
    )


# ─── Khởi tạo Chroma Vector Store ────────────────────────────────────────────

def get_active_collection_name() -> str:
    """Return the last successfully activated Chroma collection."""
    try:
        name = ACTIVE_COLLECTION_FILE.read_text(encoding="utf-8").strip()
        # Collection names are internal identifiers; reject a corrupted file.
        if re.fullmatch(r"[A-Za-z0-9_-]{3,120}", name):
            return name
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning(f"Could not read active collection marker: {exc}")
    return COLLECTION_NAME


def set_active_collection_name(collection_name: str) -> None:
    """Atomically persist a collection only after it has been validated."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,120}", collection_name):
        raise ValueError("Tên collection không hợp lệ")
    ACTIVE_COLLECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = ACTIVE_COLLECTION_FILE.with_suffix(".tmp")
    temporary_file.write_text(collection_name, encoding="utf-8")
    temporary_file.replace(ACTIVE_COLLECTION_FILE)


def get_vector_store(
    embedding_model: Optional[HuggingFaceEmbeddings] = None,
    collection_name: Optional[str] = None,
) -> Chroma:
    """
    Kết nối hoặc tạo mới Chroma vector store.
    Nếu chưa có dữ liệu, trả về store rỗng (không lỗi).
    """
    if embedding_model is None:
        embedding_model = get_embedding_model()

    # Tạo thư mục nếu chưa có
    Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)

    selected_collection = collection_name or get_active_collection_name()
    vector_store = Chroma(
        collection_name=selected_collection,
        embedding_function=embedding_model,
        persist_directory=CHROMA_PATH,
    )
    count = vector_store._collection.count()
    logger.info(f"Chroma loaded: {count} documents in collection '{selected_collection}'")
    return vector_store


# ─── Prompt Template (ChatML format cho Qwen) ─────────────────────────────────

SYSTEM_PROMPT = """Bạn là trợ lý AI hỗ trợ sinh viên tra cứu quy chế đào tạo, công tác sinh viên và tài liệu nghiệp vụ của Khoa.

Quy tắc bắt buộc:
1. CHỈ trả lời dựa trên thông tin trong phần [Tài liệu tham khảo] được cung cấp.
2. Nếu không tìm thấy thông tin liên quan, hãy trả lời: "Xin lỗi, tôi không tìm thấy thông tin phù hợp trong tài liệu hiện có. Vui lòng liên hệ trực tiếp với Khoa để được hỗ trợ."
3. KHÔNG bịa đặt, suy đoán, hoặc dùng kiến thức bên ngoài tài liệu.
4. Không chép nguyên văn các đoạn dài. Hãy diễn giải ngắn gọn, chính xác.
5. Ưu tiên đoạn/điều khoản trả lời trực tiếp câu hỏi; bỏ qua các đoạn chỉ liên quan lỏng lẻo.
6. Giữ nguyên mức độ bắt buộc của văn bản: nếu nguồn ghi "phải" hoặc "bắt buộc", câu trả lời phải giữ nghĩa bắt buộc. TUYỆT ĐỐI không thêm điều kiện, ngoại lệ hoặc cụm như "khi được yêu cầu" nếu nguồn không nêu.
7. Mở đầu bằng đúng một câu trả lời trực tiếp cho câu hỏi. Nếu chỉ có một ý, không dùng bullet.
8. Nếu có từ hai ý độc lập, dùng bullet; mỗi ý không quá 10 từ, trừ trường hợp liệt kê toàn diện ở quy tắc 11.
9. Toàn bộ câu trả lời tối đa 100 từ, không dùng dấu ngoặc kép.
10. Không viết "Trích dẫn từ", "Theo Điều...", tên tệp, đường dẫn, đuôi .pdf/.docx hoặc tên có dấu gạch dưới. Nguồn đã được hiển thị riêng bên dưới câu trả lời.
11. Khi câu hỏi hỏi nội dung Tuần định hướng cho tân sinh viên, ưu tiên mục có tiêu đề "NỘI DUNG" và tổng hợp toàn bộ từ đầu đến cuối thành đúng 10 bullet, mỗi bullet tối đa 9 từ; không dùng phần "Trách nhiệm" hoặc "Tổ chức thực hiện" để thay thế.
12. Với số tiền, giữ nguyên giá trị số và đối tượng/điều kiện áp dụng trong nguồn. Phần trong ngoặc viết số tiền bằng chữ chỉ diễn giải cùng một số tiền; "đồng chẵn" không phải đơn vị tính hoặc mẫu số. Có thể bỏ phần viết bằng chữ khi đã nêu số tiền bằng số. Nếu OCR làm sai dấu ở phần viết bằng chữ, không sao chép lỗi đó thành đơn vị như "đồng/chãn", "đồng/chăn" hay "đồng/chẵn". Không tự thêm đơn vị theo người, tháng hoặc năm nếu nguồn không nêu; nếu số tiền bằng số và bằng chữ mâu thuẫn hoặc không đọc rõ thì nói rõ chưa xác định được, không tự sửa con số."""

USER_PROMPT_TEMPLATE = """[Tài liệu tham khảo]
{context}

[Ngữ cảnh hội thoại gần đây]
{conversation_history}

[Câu hỏi của sinh viên]
{question}

[Yêu cầu trình bày cho câu hỏi này]
{answer_guidance}

Chỉ dùng ngữ cảnh hội thoại để hiểu các từ thay thế như điều đó, mục đó hoặc năm đó. Mọi thông tin thực tế trong câu trả lời phải có trong [Tài liệu tham khảo]. Không suy diễn thêm điều kiện. Nguồn sẽ được hệ thống hiển thị riêng bên dưới."""

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", USER_PROMPT_TEMPLATE),
])

CONTENT_TAIL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Bạn bổ sung các ý còn thiếu cho câu trả lời RAG. Chỉ dùng nguồn được cung cấp, "
        "không nhắc tên tệp hoặc trang, không lặp lại các ý đã có.",
    ),
    (
        "human",
        "[Toàn bộ mục NỘI DUNG]\n{context}\n\n"
        "[Các ý đã có]\n{existing_answer}\n\n"
        "Bổ sung đúng {missing_count} ý chưa xuất hiện. Mỗi dòng bắt đầu bằng '- ' "
        "và tối đa 9 từ. Không lặp hoặc diễn đạt lại các ý đã có.",
    ),
])

CONTENT_REPAIR_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Bạn sửa câu trả lời RAG bị thiếu ý. Chỉ dùng nguồn được cung cấp, "
        "không nhắc tên tệp hoặc trang.",
    ),
    (
        "human",
        "[Mục NỘI DUNG]\n{context}\n\n[Câu trả lời cần sửa]\n{existing_answer}\n\n"
        "Các ý đang thiếu hoặc chưa rõ: {missing_topics}. Viết lại đúng 10 dòng "
        "bắt đầu bằng '- ', theo thứ tự yêu cầu ban đầu, mỗi dòng thật ngắn. "
        "Dòng cuối bắt buộc là giải đáp thắc mắc.",
    ),
])

MAX_CONVERSATION_TURNS = 4
MAX_CONVERSATION_CHARS = 3_500
NO_ACTIVE_DOCUMENTS_MESSAGE = (
    "Hiện chưa có tài liệu còn hiệu lực để tra cứu. "
    "Vui lòng liên hệ quản trị viên để được hỗ trợ."
)


def format_conversation_history(conversation_history: Optional[Sequence[Mapping[str, str]]]) -> str:
    """Create a bounded, clearly separated history section for the answer prompt."""
    if not conversation_history:
        return "Không có lượt hội thoại trước."

    turns: list[str] = []
    used_chars = 0
    for turn in conversation_history[-MAX_CONVERSATION_TURNS:]:
        question = str(turn.get("question", "")).strip()
        answer = str(turn.get("answer", "")).strip()
        if not question:
            continue
        entry = f"Sinh viên: {question[:900]}\nTrợ lý: {answer[:1_200]}"
        if used_chars + len(entry) > MAX_CONVERSATION_CHARS:
            break
        turns.append(entry)
        used_chars += len(entry)
    return "\n---\n".join(turns) if turns else "Không có lượt hội thoại trước."


def build_retrieval_query(question: str, conversation_history: Optional[Sequence[Mapping[str, str]]]) -> str:
    """Use the preceding user question to make a short follow-up searchable."""
    if not conversation_history:
        return question
    previous_questions = [str(turn.get("question", "")).strip() for turn in conversation_history]
    previous_question = next((item for item in reversed(previous_questions) if item), "")
    if not previous_question:
        return question
    return f"Chủ đề ở lượt trước: {previous_question[:900]}\nCâu hỏi tiếp theo: {question}"


def l2_distance_to_relevance(distance: float) -> float:
    """Convert Chroma squared-L2 distance of normalized vectors to cosine score.

    Chroma's default L2 index returns squared Euclidean distance. For unit
    vectors, cosine_similarity = 1 - squared_l2 / 2. LangChain's generic
    Euclidean converter assumes a non-squared norm, which produced negative
    relevance scores and false refusals for this collection.
    """
    return min(1.0, max(0.0, 1.0 - float(distance) / 2.0))


def _search_normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", (value or "").lower())
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    without_marks = without_marks.replace("đ", "d")
    return " ".join(re.findall(r"[a-z0-9]+", without_marks))


def _asks_for_content_list(question: str) -> bool:
    normalized = _search_normalize(question)
    asks_for_list = any(
        marker in normalized
        for marker in (
            "nhung noi dung gi",
            "noi dung gi",
            "cac noi dung",
            "bao gom nhung gi",
            "gom nhung gi",
            "duoc huong dan",
        )
    )
    is_orientation_topic = "tan sinh vien" in normalized and any(
        marker in normalized for marker in ("tuan dinh huong", "duoc huong dan")
    )
    return asks_for_list and is_orientation_topic


def expand_retrieval_query(question: str, retrieval_query: str) -> str:
    """Add a document-heading hint for exhaustive content-list questions."""
    if _asks_for_content_list(question):
        return (
            f"{retrieval_query}\n"
            "Tiêu đề mục cần tìm: III. NỘI DUNG. "
            "Các nội dung hướng dẫn dành cho tân sinh viên."
        )
    return retrieval_query


def build_answer_guidance(question: str) -> str:
    if _asks_for_content_list(question):
        return (
            "Đọc toàn bộ các đoạn của mục NỘI DUNG, kể cả đoạn cuối. "
            "Viết đúng 10 bullet tương ứng 10 nội dung chính theo thứ tự nguồn; "
            "mỗi bullet tối đa 9 từ, không gộp mất ý. Thứ tự 10 dòng: "
            "tổng quan Khoa/ngành; CNTT-truyền thông-thư viện-an toàn; "
            "lịch-đăng ký-thủ tục; chương trình-quy chế; kỹ năng; văn hóa; "
            "ngoại khóa-Đoàn Hội-học bổng-nghề nghiệp; mục tiêu-kế hoạch; "
            "giao lưu; giải đáp thắc mắc. Chỉ ghi điều có trong nguồn."
        )
    return "Trả lời trực tiếp, ngắn gọn theo các quy tắc hệ thống."


def build_content_retry_guidance() -> str:
    return (
        "Phản hồi trước bị thiếu nội dung. Không viết câu dẫn. "
        "BẮT BUỘC viết đúng 10 dòng bắt đầu bằng '- '. Mỗi dòng tối đa 9 từ. "
        "Theo đúng thứ tự: (1) tổng quan Khoa, ngành; (2) CNTT, truyền thông, "
        "thư viện, an toàn mạng; (3) lịch, đăng ký, thủ tục; (4) chương trình, "
        "quy chế; (5) kỹ năng; (6) văn hóa ứng xử; (7) ngoại khóa, Đoàn-Hội, "
        "học bổng, nghề nghiệp; (8) mục tiêu, kế hoạch; (9) giao lưu; "
        "(10) giải đáp thắc mắc. Chỉ giữ chi tiết có trong nguồn."
    )


def infer_document_filename(
    question: str,
    active_filenames: Optional[Sequence[str]],
) -> Optional[str]:
    """Infer one document only when a non-year identifier matches uniquely.

    This recovers document numbers from filenames when OCR drops a character,
    for example ``1340`` in the filename but ``340`` in the scanned header.
    Years are excluded because they commonly occur in several documents.
    """
    if not active_filenames:
        return None
    query = _search_normalize(question)
    query_numbers = {
        number
        for number in re.findall(r"\b\d{3,}\b", query)
        if not (1900 <= int(number) <= 2100)
    }
    if query_numbers:
        matches = []
        for filename in active_filenames:
            filename_numbers = set(re.findall(r"\d+", _search_normalize(filename)))
            if query_numbers & filename_numbers:
                matches.append(filename)
        if len(matches) == 1:
            return matches[0]

    # Filenames often retain a clean document topic when scanned OCR is noisy.
    # Scope only on a strong, unique lexical match so generic questions still
    # search across all active documents.
    stopwords = {
        "cho", "cac", "cua", "duoc", "gi", "hay", "hoi", "la", "mot",
        "nhung", "noi", "pdf", "se", "the", "theo", "trong", "van", "ve",
    }
    query_tokens = {
        token for token in query.split() if len(token) >= 3 and token not in stopwords
    }
    scored = []
    for filename in active_filenames:
        filename_tokens = {
            token
            for token in _search_normalize(Path(filename).stem).split()
            if len(token) >= 3 and token not in stopwords
        }
        scored.append((len(query_tokens & filename_tokens), filename))
    scored.sort(reverse=True)
    best_score, best_filename = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0
    if best_score >= 3 and best_score - second_score >= 2:
        return best_filename
    return None


def _is_content_section(document: Document) -> bool:
    section_title = _search_normalize(str(document.metadata.get("section_title", "")))
    if "noi dung" in section_title:
        return True
    normalized = _search_normalize(document.page_content[:500])
    return bool(re.search(r"\b(?:[ivxlcdm]+|\d+(?:\s+\d+)*)\s+noi dung\b", normalized))


def _retrieval_intent_bonus(question: str, document: Document) -> float:
    """Deterministic rerank bonus for dates, identifiers and degraded OCR."""
    query = _search_normalize(question)
    document_text = document.page_content or ""
    normalized_document = _search_normalize(document_text)
    normalized_filename = _search_normalize(str(document.metadata.get("filename", "")))
    raw_document = document_text.lower()
    if not query or not normalized_document:
        return 0.0

    query_tokens = {token for token in query.split() if len(token) >= 3 or token.isdigit()}
    document_tokens = set(normalized_document.split())
    lexical_overlap = len(query_tokens & document_tokens) / max(len(query_tokens), 1)
    bonus = min(0.12, lexical_overlap * 0.12)

    query_numbers = set(re.findall(r"\d+", query))
    if query_numbers:
        number_overlap = len(query_numbers & set(re.findall(r"\d+", normalized_document)))
        bonus += min(0.10, number_overlap * 0.05)

    identifying_numbers = {
        number
        for number in re.findall(r"\b\d{3,}\b", query)
        if not (1900 <= int(number) <= 2100)
    }
    filename_numbers = set(re.findall(r"\d+", normalized_filename))
    if identifying_numbers & filename_numbers:
        bonus += 0.12

    if _asks_for_content_list(question):
        if _is_content_section(document):
            bonus += 0.30
        section_title = _search_normalize(str(document.metadata.get("section_title", "")))
        if any(marker in section_title for marker in ("trach nhiem", "to chuc thuc hien")):
            bonus -= 0.08

    issue_intent = any(marker in query for marker in ("ban hanh", "ky ngay", "ngay ky"))
    range_intent = not issue_intent and any(
        marker in query for marker in ("dien ra", "thoi gian", "tu ngay", "khi nao")
    )
    if issue_intent:
        written_date = re.search(
            r"ngay\s*\d{1,2}\s*thang\s*\d{1,2}\s*nam\s*\d{4}",
            normalized_document,
        )
        # Official documents usually place the issue date beside the location
        # in the header. Requiring both signals avoids confusing schedule dates.
        if written_date and "lam dong" in normalized_document:
            bonus += 0.20
        if "ke hoach" in normalized_document:
            bonus += 0.04
    elif range_intent:
        full_dates = re.findall(
            r"\b\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4}\b",
            raw_document,
        )
        bonus += min(0.06, len(full_dates) * 0.03)
        # OCR Small may turn "Thời gian: Từ ngày ... đến hết ngày" into
        # "Thi gian: Tù ngày ... đn ht ngày". Two dates are the safest
        # language-independent signal that this is a time range.
        if len(full_dates) >= 2:
            bonus += 0.18
        if "thoi gian" in normalized_document or "thi gian" in normalized_document:
            bonus += 0.08
    return bonus


def retrieval_evidence_score(question: str, document: Document, semantic_score: float) -> float:
    """Combine calibrated semantic similarity with explicit evidence signals."""
    return min(1.0, max(0.0, semantic_score + _retrieval_intent_bonus(question, document)))


def rerank_retrieval_results(
    question: str,
    results: Sequence[tuple[Document, float]],
) -> list[tuple[Document, float]]:
    """Rerank candidates while preserving the calibrated semantic score."""
    return sorted(
        results,
        key=lambda item: retrieval_evidence_score(question, item[0], item[1]),
        reverse=True,
    )


def _chunk_order(record_id: str, metadata: Mapping[str, object]) -> int:
    value = metadata.get("chunk_index")
    if isinstance(value, int):
        return value
    match = re.search(r"_chunk_(\d+)$", record_id or "")
    return int(match.group(1)) if match else 0


def select_context_results(
    vector_store: Chroma,
    question: str,
    ranked_results: Sequence[tuple[Document, float]],
) -> list[tuple[Document, float]]:
    """Select compact context and expand the winning content page when needed."""
    if not ranked_results:
        return []
    selected = list(ranked_results[:TOP_K])
    if not _asks_for_content_list(question):
        return selected

    anchor = next((item for item in ranked_results if _is_content_section(item[0])), None)
    if anchor is None:
        return selected
    anchor_document, anchor_score = anchor
    filename = str(anchor_document.metadata.get("filename", ""))
    page = anchor_document.metadata.get("page")
    if not filename or not isinstance(page, int):
        return selected

    try:
        records = vector_store._collection.get(
            where={
                "$and": [
                    {"filename": {"$eq": filename}},
                    {"page": {"$eq": page}},
                ]
            },
            include=["documents", "metadatas"],
        )
    except Exception as exc:
        logger.warning("Không thể mở rộng chunk cùng trang: {}", exc)
        return selected

    score_by_text = {doc.page_content: score for doc, score in ranked_results}
    siblings = []
    for record_id, text, metadata in zip(
        records.get("ids", []),
        records.get("documents", []),
        records.get("metadatas", []),
    ):
        if not text or not metadata:
            continue
        sibling = Document(page_content=text, metadata=dict(metadata))
        siblings.append(
            (
                _chunk_order(record_id, metadata),
                sibling,
                score_by_text.get(text, anchor_score),
            )
        )
    siblings.sort(key=lambda item: item[0])

    expanded: list[tuple[Document, float]] = [
        (document, score) for _order, document, score in siblings
    ]
    if expanded:
        # Once a numbered NỘI DUNG section is found, unrelated responsibility
        # chunks must not leak back into an exhaustive content-list prompt.
        return expanded[:TOP_K]

    seen = {
        (doc.metadata.get("filename"), doc.metadata.get("page"), doc.page_content)
        for doc, _score in expanded
    }
    for document, score in ranked_results:
        key = (
            document.metadata.get("filename"),
            document.metadata.get("page"),
            document.page_content,
        )
        if key not in seen:
            expanded.append((document, score))
            seen.add(key)
        if len(expanded) >= TOP_K:
            break
    return expanded[:TOP_K]


# ─── Format context từ documents ─────────────────────────────────────────────

def format_docs(
    docs: list[Document], source_labels: Optional[Mapping[str, str]] = None
) -> str:
    """
    Format danh sách Document thành chuỗi context cho prompt.
    Mỗi chunk được đánh số và ghi rõ nguồn.
    """
    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        source = meta.get("source", "Không rõ nguồn")
        # Lấy tên file từ đường dẫn
        source_name = Path(source).name if source != "Không rõ nguồn" else source
        citation_label = (source_labels or {}).get(source_name, source_name)
        page = meta.get("page", None)
        page_info = f" (Trang {page + 1})" if page is not None else ""

        parts.append(
            f"[Đoạn {i} - Trích dẫn: {citation_label}{page_info}]\n"
            f"{doc.page_content.strip()}"
        )
    return "\n\n" + "─" * 60 + "\n\n".join(parts)


def _support_score(answer: str, document_text: str) -> float:
    """Đo mức độ đoạn nguồn thực sự nâng đỡ câu trả lời, không chỉ câu hỏi."""
    answer_tokens = re.findall(r"[\wÀ-ỹ]+", (answer or "").lower())
    document_lower = (document_text or "").lower()
    if not answer_tokens or not document_lower:
        return 0.0
    meaningful = [token for token in answer_tokens if len(token) > 2]
    token_score = sum(token in document_lower for token in meaningful) / max(len(meaningful), 1)
    # Cụm 3 từ khớp nguyên vẹn là tín hiệu mạnh hơn từ khóa rời rạc.
    phrases = [" ".join(answer_tokens[i:i + 3]) for i in range(len(answer_tokens) - 2)]
    phrase_score = sum(phrase in document_lower for phrase in phrases) / max(len(phrases), 1)
    return token_score + phrase_score * 2


def extract_sources(
    docs: list[Document], answer: str, scores: Optional[list[float]] = None
) -> list[dict]:
    """
    Trích xuất thông tin nguồn từ danh sách documents để trả về client.
    """
    support_scores = [_support_score(answer, doc.page_content) for doc in docs]
    # Nếu LLM diễn giải quá xa khiến không còn từ chung, giữ kết quả retrieval tốt nhất.
    primary_index = max(range(len(docs)), key=lambda index: (support_scores[index], (scores or [0] * len(docs))[index])) if docs else 0
    grouped_sources: dict[str, dict] = {}
    for index, doc in enumerate(docs):
        meta = doc.metadata
        source = meta.get("source", "")
        source_name = Path(source).name if source else "Không rõ nguồn"
        page = meta.get("page", None)

        key = f"{source_name}_{page}"
        if key not in grouped_sources:
            grouped_sources[key] = {
                "filename": source_name,
                "page": (page + 1) if page is not None else None,
                "source_path": source,
                "is_primary": False,
            }
        # Multiple chunks can represent one page. Mark the page badge primary
        # when any chunk in that group is the strongest supporting evidence.
        if index == primary_index:
            grouped_sources[key]["is_primary"] = True
    return list(grouped_sources.values())


def normalize_answer(answer: str, max_words: int = 100) -> str:
    """Dọn output local LLM và chặn câu trả lời dài vượt chuẩn UI."""
    cleaned = re.sub(r"[ \t]+", " ", answer or "")
    # A narrowly scoped generation artefact: "chẵn" (including observed OCR
    # misspellings) is not a denominator. Preserve real units such as đồng/tháng
    # and leave source/OCR text untouched for auditing.
    cleaned = re.sub(
        r"(\d[\d., \t]*[ \t]+đồng)[ \t]*/[ \t]*(?:chẵn|chãn|chăn|chắn)\b",
        r"\1",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Some local-model outputs place list items inline after punctuation. Do
    # not split compound names such as "Đoàn - Hội" into a false new bullet.
    cleaned = re.sub(r"(?<=[.!?;])\s+-\s+", "\n- ", cleaned)
    cleaned = re.sub(r"(?m)^\s*\d+[.)]\s+", "- ", cleaned)
    cleaned = re.sub(r"\s*\n\s*", "\n", cleaned).strip()
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned

    shortened = " ".join(words[:max_words])
    # Kết thúc ở ranh giới câu gần nhất để tránh câu bị cụt.
    boundaries = [shortened.rfind(mark) for mark in (".", "!", "?")]
    boundary = max(boundaries)
    return shortened[:boundary + 1].strip() if boundary >= max_words // 2 else f"{shortened.rstrip(' ,;:')}…"


def count_answer_bullets(answer: str) -> int:
    return sum(
        bool(re.match(r"^[-•]\s+", line.strip()))
        for line in (answer or "").splitlines()
    )


def answer_bullet_lines(answer: str) -> list[str]:
    return [
        line.strip()
        for line in (answer or "").splitlines()
        if re.match(r"^[-•]\s+", line.strip())
    ]


def content_missing_topics(answer: str) -> list[str]:
    """Return orientation topics that a generated answer has not covered."""
    normalized = _search_normalize(answer)
    topic_checks = (
        ("tổng quan Khoa/ngành", "tong quan" in normalized),
        ("CNTT, truyền thông, thư viện, an toàn", any(marker in normalized for marker in ("cntt", "cong nghe", "thu vien"))),
        ("lịch, đăng ký, thủ tục", "lich" in normalized and any(marker in normalized for marker in ("dang ky", "thu tuc"))),
        ("chương trình và quy chế", "quy che" in normalized),
        ("kỹ năng", "ky nang" in normalized),
        ("văn hóa ứng xử", any(marker in normalized for marker in ("van hoa", "ung xu"))),
        ("ngoại khóa, Đoàn-Hội, học bổng, nghề nghiệp", any(marker in normalized for marker in ("ngoai khoa", "doan hoi", "hoc bong"))),
        ("mục tiêu và kế hoạch", any(marker in normalized for marker in ("muc tieu", "ke hoach hoc tap", "ke hoach ren luyen"))),
        ("giao lưu, chia sẻ", any(marker in normalized for marker in ("giao luu", "chia se kinh nghiem"))),
        ("giải đáp thắc mắc", any(marker in normalized for marker in ("giai dap", "thac mac", "vuong mac"))),
    )
    return [label for label, is_present in topic_checks if not is_present]


def content_answer_coverage(answer: str) -> int:
    """Count the required orientation topics present in a generated answer."""
    return 10 - len(content_missing_topics(answer))


def content_answer_is_complete(answer: str) -> bool:
    bullets = answer_bullet_lines(answer)
    return (
        len(bullets) == 10
        and content_answer_coverage(answer) == 10
        and all(len(line.split()) <= 10 for line in bullets)
    )


def compact_content_bullets(answer: str, max_total_words: int = 100) -> str:
    """Keep ten items within 100 words without cutting every line mechanically."""
    bullets = [
        re.sub(r"^[-•]\s+", "", line).strip().split()
        for line in answer_bullet_lines(answer)[:10]
    ]
    if not bullets:
        return answer

    # Each rendered dash counts as one word in normalize_answer. Trim only the
    # longest lines when the whole answer exceeds the UI budget; short complete
    # lines are preserved instead of ending every bullet with an ellipsis.
    content_budget = max_total_words - len(bullets)
    while sum(len(words) for words in bullets) > content_budget:
        longest_index = max(range(len(bullets)), key=lambda index: len(bullets[index]))
        if len(bullets[longest_index]) <= 4:
            break
        bullets[longest_index].pop()
    return "\n".join(
        f"- {' '.join(words).rstrip(' ,;:.')}" for words in bullets
    )


def remove_embedded_citations(answer: str) -> str:
    """Nguồn chỉ hiển thị ở badge UI, không để local LLM chèn lại vào nội dung."""
    kept_lines = []
    for line in (answer or "").splitlines():
        normalized = line.strip()
        # Ví dụ LLM thường sinh: [Quy chế ... (Trang 7)] hoặc [Nguồn: ...]
        is_bracket_citation = bool(re.match(
            r"^\[.*(?:trang|tr\.|nguồn|quy chế|sổ tay|văn bản).*(?:\d|\])", normalized,
            flags=re.IGNORECASE,
        ))
        is_label_citation = bool(re.match(
            r"^(?:nguồn|trích dẫn|tham khảo)\s*[:：]", normalized,
            flags=re.IGNORECASE,
        ))
        if not is_bracket_citation and not is_label_citation:
            kept_lines.append(line)
    cleaned = "\n".join(kept_lines).strip()
    # Xử lý citation nằm cuối cùng một dòng, sau nội dung trả lời.
    cleaned = re.sub(
        r"\s*\[(?:[^\]]*)(?:trang\s*\d+|tr\.\s*\d+|nguồn\s*:[^\]]+)[^\]]*\]\s*$",
        "", cleaned, flags=re.IGNORECASE,
    )
    return cleaned.strip()


# ─── RAGChain Class ───────────────────────────────────────────────────────────

class RAGChain:
    """
    Pipeline RAG hoàn chỉnh:
    1. Embed câu hỏi
    2. Retrieve top-K chunks từ Chroma
    3. Format context
    4. Gọi Qwen2.5-7B qua Ollama
    5. Parse output
    """

    def __init__(self):
        self._embedding_model: Optional[HuggingFaceEmbeddings] = None
        self._vector_store: Optional[Chroma] = None
        self._llm: Optional[ChatOllama] = None
        self._chain = None

    def initialize(self) -> None:
        """Khởi tạo tất cả components. Gọi một lần khi startup."""
        logger.info("Initializing RAG Chain...")

        # 1. Embedding model
        self._embedding_model = get_embedding_model()

        # 2. Vector store
        self._vector_store = get_vector_store(self._embedding_model)

        # 3. LLM (Qwen2.5-7B qua Ollama)
        self._llm = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.1,        # Thấp để câu trả lời ổn định, ít hallucination
            num_ctx=4096,           # Context window
            num_predict=420,        # Đủ cho tối đa 100 từ tiếng Việt
            top_p=0.9,
            repeat_penalty=1.1,
        )

        logger.info("RAG Chain initialized successfully")

    def _build_chain(self):
        """Xây dựng LangChain chain với retriever."""
        if self._vector_store._collection.count() == 0:
            logger.warning("Vector store is empty! Please add documents first.")
            return None

        retriever = self._vector_store.as_retriever(
            search_type="mmr",          # Maximum Marginal Relevance: đa dạng kết quả
            search_kwargs={
                "k": TOP_K,
                "fetch_k": TOP_K * 3,   # Fetch nhiều hơn rồi MMR filter
                "lambda_mult": 0.7,      # Cân bằng relevance vs diversity
            },
        )

        # Chain chính
        chain = (
            RunnableParallel(
                context=retriever | format_docs,
                question=RunnablePassthrough(),
                docs=retriever,
            )
            | {
                "answer": (lambda x: {
                    "context": x["context"],
                    "question": x["question"],
                    "conversation_history": "Không có lượt hội thoại trước.",
                    "answer_guidance": build_answer_guidance(str(x["question"])),
                })
                          | RAG_PROMPT
                          | self._llm
                          | StrOutputParser(),
                "docs": lambda x: x["docs"],
            }
        )
        return chain

    async def achat(
        self,
        question: str,
        source_labels: Optional[Mapping[str, str]] = None,
        conversation_history: Optional[Sequence[Mapping[str, str]]] = None,
        document_filename: Optional[str] = None,
        active_filenames: Optional[Sequence[str]] = None,
    ) -> tuple[str, list[dict], float]:
        """
        Async chat: trả về (answer, sources, avg_score).
        """
        if self._vector_store is None or self._llm is None:
            raise RuntimeError("RAG Chain chưa được khởi tạo. Gọi initialize() trước.")

        # Kiểm tra vector store có dữ liệu
        doc_count = self._vector_store._collection.count()
        if doc_count == 0:
            no_data_msg = (
                "⚠️ Hệ thống chưa có tài liệu nào. "
                "Vui lòng liên hệ quản trị viên để nạp tài liệu vào hệ thống."
            )
            return no_data_msg, [], 0.0

        # Retrieve documents với score
        retrieval_query = build_retrieval_query(question, conversation_history)
        retrieval_query = expand_retrieval_query(question, retrieval_query)
        if active_filenames is not None and not active_filenames:
            logger.info("RAG refusal: no active documents are available")
            return NO_ACTIVE_DOCUMENTS_MESSAGE, [], 0.0

        inferred_filename = infer_document_filename(question, active_filenames)
        effective_filename = document_filename or inferred_filename
        search_kwargs = {"k": RETRIEVAL_CANDIDATE_K}
        if effective_filename:
            search_kwargs["filter"] = {"filename": effective_filename}
            if inferred_filename and not document_filename:
                logger.info(
                    "RAG inferred document '{}' from a unique identifier in the question",
                    inferred_filename,
                )
        elif active_filenames is not None:
            search_kwargs["filter"] = {"filename": {"$in": list(active_filenames)}}
        raw_results = self._vector_store.similarity_search_with_score(
            retrieval_query, **search_kwargs
        )
        retriever_with_score = rerank_retrieval_results(
            question,
            [(doc, l2_distance_to_relevance(distance)) for doc, distance in raw_results],
        )

        if not retriever_with_score:
            return (
                "Xin lỗi, tôi không tìm thấy thông tin phù hợp trong tài liệu hiện có. "
                "Vui lòng liên hệ trực tiếp với Khoa để được hỗ trợ.",
                [],
                0.0,
            )

        candidate_scores = [score for _, score in retriever_with_score]
        best_score = max(candidate_scores) if candidate_scores else 0.0
        best_evidence_score = max(
            retrieval_evidence_score(question, doc, score)
            for doc, score in retriever_with_score
        )

        # A non-empty vector search does not imply a relevant answer. Refuse
        # before invoking the LLM when semantic and explicit evidence are weak.
        if best_evidence_score < MIN_RELEVANCE_SCORE:
            logger.info(
                f"RAG refusal: best_score={best_score:.3f}, "
                f"best_evidence={best_evidence_score:.3f} below "
                f"threshold={MIN_RELEVANCE_SCORE:.3f} for '{question[:50]}...'"
            )
            return (
                "Xin lỗi, tôi không tìm thấy thông tin phù hợp trong tài liệu hiện có. "
                "Vui lòng diễn đạt cụ thể hơn hoặc liên hệ trực tiếp với Khoa để được hỗ trợ.",
                [],
                best_score,
            )

        context_results = select_context_results(
            self._vector_store,
            question,
            retriever_with_score,
        )
        docs = [doc for doc, _ in context_results]
        scores = [score for _, score in context_results]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Format context
        context = format_docs(docs, source_labels)

        # Gọi LLM
        prompt_messages = RAG_PROMPT.format_messages(
            context=context,
            conversation_history=format_conversation_history(conversation_history),
            question=question,
            answer_guidance=build_answer_guidance(question),
        )
        is_content_list = _asks_for_content_list(question)
        response = await self._llm.ainvoke(prompt_messages)
        answer = response.content if hasattr(response, "content") else str(response)
        draft_word_limit = 180 if is_content_list else 100
        answer = remove_embedded_citations(
            normalize_answer(answer, max_words=draft_word_limit)
        )

        if is_content_list and not content_answer_is_complete(answer):
            logger.info(
                "RAG content answer had {} bullets; requesting one bounded rewrite",
                count_answer_bullets(answer),
            )
            retry_messages = RAG_PROMPT.format_messages(
                context=context,
                conversation_history=format_conversation_history(conversation_history),
                question=question,
                answer_guidance=build_content_retry_guidance(),
            )
            retry_response = await self._llm.ainvoke(retry_messages)
            retry_answer = (
                retry_response.content
                if hasattr(retry_response, "content")
                else str(retry_response)
            )
            retry_answer = remove_embedded_citations(
                normalize_answer(retry_answer, max_words=draft_word_limit)
            )
            if (
                content_answer_coverage(retry_answer),
                count_answer_bullets(retry_answer),
            ) > (
                content_answer_coverage(answer),
                count_answer_bullets(answer),
            ):
                answer = retry_answer

        if is_content_list and count_answer_bullets(answer) < 10:
            existing_bullets = answer_bullet_lines(answer)
            missing_count = 10 - len(existing_bullets)
            tail_messages = CONTENT_TAIL_PROMPT.format_messages(
                context=context,
                existing_answer="\n".join(existing_bullets),
                missing_count=missing_count,
            )
            tail_response = await self._llm.ainvoke(tail_messages)
            tail_answer = (
                tail_response.content
                if hasattr(tail_response, "content")
                else str(tail_response)
            )
            tail_answer = remove_embedded_citations(
                normalize_answer(tail_answer, max_words=draft_word_limit)
            )
            additions = answer_bullet_lines(tail_answer)
            if additions:
                answer = normalize_answer(
                    "\n".join((existing_bullets + additions)[:10]),
                    max_words=draft_word_limit,
                )
        if is_content_list and not content_answer_is_complete(answer):
            repair_messages = CONTENT_REPAIR_PROMPT.format_messages(
                context=context,
                existing_answer=answer,
                missing_topics=", ".join(content_missing_topics(answer)),
            )
            repair_response = await self._llm.ainvoke(repair_messages)
            repair_answer = (
                repair_response.content
                if hasattr(repair_response, "content")
                else str(repair_response)
            )
            repair_answer = remove_embedded_citations(
                normalize_answer(repair_answer, max_words=draft_word_limit)
            )
            if (
                content_answer_coverage(repair_answer),
                count_answer_bullets(repair_answer) == 10,
            ) > (
                content_answer_coverage(answer),
                count_answer_bullets(answer) == 10,
            ):
                answer = repair_answer
        if is_content_list:
            answer = normalize_answer(compact_content_bullets(answer), max_words=100)

        # Trích xuất sources
        sources = extract_sources(docs, answer, scores)

        logger.info(
            f"RAG query: '{question[:50]}...' → "
            f"{len(retriever_with_score)} candidates, {len(docs)} context chunks, "
            f"avg_score={avg_score:.3f}, "
            f"best_evidence={best_evidence_score:.3f}"
        )
        return answer, sources, avg_score

    def reload_vector_store(self) -> None:
        """Reload vector store sau khi cập nhật tài liệu."""
        logger.info("Reloading vector store...")
        self._vector_store = get_vector_store(self._embedding_model)
        count = self._vector_store._collection.count()
        logger.info(f"Vector store reloaded: {count} documents")

    def activate_collection(self, collection_name: str) -> str:
        """Switch queries to a fully built staging collection and persist it."""
        if self._embedding_model is None:
            raise RuntimeError("Embedding model chưa sẵn sàng")
        next_store = get_vector_store(self._embedding_model, collection_name)
        if next_store._collection.count() == 0:
            raise ValueError("Index mới không có chunk nào nên không thể kích hoạt")

        previous_collection = self._vector_store._collection.name if self._vector_store else COLLECTION_NAME
        set_active_collection_name(collection_name)
        self._vector_store = next_store
        logger.info(f"Activated Chroma collection '{collection_name}' (previous: '{previous_collection}')")
        return previous_collection

    @property
    def vector_store(self) -> Optional[Chroma]:
        return self._vector_store

    @property
    def embedding_model(self) -> Optional[HuggingFaceEmbeddings]:
        return self._embedding_model


# ─── Singleton instance ───────────────────────────────────────────────────────
# Dùng singleton để tránh load model nhiều lần
rag_chain_instance = RAGChain()
