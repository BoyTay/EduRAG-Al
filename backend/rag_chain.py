"""
rag_chain.py - Pipeline RAG chính
Kết hợp Chroma retriever + Qwen3.5-9B (Ollama) + LangChain để trả lời câu hỏi
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
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5:9b")


def _read_temperature(env_name: str, default: float) -> float:
    """Read a bounded Ollama temperature without breaking startup."""
    raw_value = os.getenv(env_name, str(default))
    try:
        return min(1.0, max(0.0, float(raw_value)))
    except ValueError:
        logger.warning("{}='{}' không hợp lệ; dùng {}", env_name, raw_value, default)
        return default


# Lượt trả lời được phép diễn đạt tự nhiên; lượt rà soát vẫn deterministic.
LLM_TEMPERATURE = _read_temperature("LLM_TEMPERATURE", 0.3)
LLM_AUDIT_TEMPERATURE = _read_temperature("LLM_AUDIT_TEMPERATURE", 0.0)
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
NO_RELEVANT_DOCUMENTS_MESSAGE = (
    "Xin lỗi, tôi không tìm thấy tài liệu phù hợp để trả lời câu hỏi này. "
    "Vui lòng liên hệ trực tiếp với Khoa để được hỗ trợ."
)

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
8. Nếu có từ hai ý độc lập, dùng bullet và diễn giải mỗi ý thành một câu ngắn, đầy đủ nghĩa.
9. Câu trả lời thông thường tối đa 150 từ. Riêng câu hỏi yêu cầu liệt kê toàn bộ nội dung có thể dùng tối đa 280 từ, hoặc 320 từ khi người dùng yêu cầu đầy đủ/chi tiết. Không dùng dấu ngoặc kép hoặc ký hiệu Markdown để in đậm.
10. Không viết "Trích dẫn từ", "Theo Điều...", tên tệp, đường dẫn, đuôi .pdf/.docx hoặc tên có dấu gạch dưới. Nguồn đã được hiển thị riêng bên dưới câu trả lời.
11. Với câu hỏi liệt kê hoặc tổng hợp, phải đọc hết mục trực tiếp trả lời câu hỏi và giữ mọi ý độc lập trong mục đó. Không dừng ở một số lượng bullet tùy ý. Khi nguồn có từ năm ý trở lên, có thể nhóm thành 3–5 chủ đề để dễ đọc nhưng từng chi tiết độc lập vẫn phải xuất hiện. Không trộn nội dung của mục hoặc đối tượng khác chỉ vì có từ khóa gần giống.
12. Chỉ thêm câu kết về nghĩa vụ, tính bắt buộc hoặc yêu cầu tham gia khi chính phần nguồn dùng để trả lời nêu rõ điều đó. Không biến lời khuyên thành quy định.
13. Với số tiền, giữ nguyên giá trị số và đối tượng/điều kiện áp dụng trong nguồn. Phần trong ngoặc viết số tiền bằng chữ chỉ diễn giải cùng một số tiền; "đồng chẵn" không phải đơn vị tính hoặc mẫu số. Có thể bỏ phần viết bằng chữ khi đã nêu số tiền bằng số. Nếu OCR làm sai dấu ở phần viết bằng chữ, không sao chép lỗi đó thành đơn vị như "đồng/chãn", "đồng/chăn" hay "đồng/chẵn". Không tự thêm đơn vị theo người, tháng hoặc năm nếu nguồn không nêu; nếu số tiền bằng số và bằng chữ mâu thuẫn hoặc không đọc rõ thì nói rõ chưa xác định được, không tự sửa con số.
14. TUYỆT ĐỐI không thêm câu kết mang tính tổng hợp, nhắc nhở, hoặc kêu gọi tuân thủ nếu phần nguồn dùng để trả lời không nêu rõ điều đó. Ví dụ: không được tự thêm 'Sinh viên cần tuân thủ đầy đủ các quy định trên' hay 'Đây là điều bắt buộc với mọi sinh viên.'
15. Chỉ trả lời đúng thuộc tính, đối tượng và điều kiện được hỏi. Không ghép ngưỡng, phân loại hoặc điều kiện của đoạn lân cận vào câu trả lời. Nếu nhiều đoạn cùng trang nói về các tiêu chí khác nhau, chỉ dùng đoạn trực tiếp định nghĩa nội dung được hỏi.
16. Với câu hỏi xác nhận như "đúng không", "phải không" hoặc "có phải", phải đánh giá mệnh đề trước khi trả lời. Nếu mệnh đề sai, mở đầu bằng "Không," và nêu thông tin đúng. Nếu mệnh đề đúng, mở đầu bằng "Đúng,". Không được mở đầu đồng tình rồi phủ định chính mệnh đề đó trong cùng câu trả lời.
17. Với dữ liệu bảng, chỉ dùng giá trị nằm đúng hàng và cột tương ứng với đối tượng, chứng chỉ hoặc bậc được hỏi; không lấy số ở cột bên cạnh."""

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

ENUMERATION_REPAIR_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Bạn là bộ kiểm tra độ bao phủ cho câu trả lời RAG. Chỉ dùng nguồn được cung cấp, "
        "không nhắc tên tệp hoặc trang và không thêm kiến thức ngoài nguồn.",
    ),
    (
        "human",
        "[Câu hỏi]\n{question}\n\n[Nguồn]\n{context}\n\n"
        "[Câu trả lời ban đầu]\n{existing_answer}\n\n"
        "Hãy đối chiếu nội bộ câu trả lời với đúng mục và đúng đối tượng trong nguồn, rồi bổ sung mọi ý độc lập còn thiếu. "
        "Tuyệt đối không mô tả quá trình đối chiếu, không viết các nhãn như bước kiểm tra, tách ý, so sánh hay nhận xét. "
        "Phản hồi duy nhất bằng cách đặt toàn bộ nội dung câu trả lời đầy đủ bên trong cặp thẻ <FINAL> và </FINAL>. "
        "Bên trong thẻ <FINAL>, mở đầu bằng một câu trực tiếp rồi dùng bullet. "
        "Nếu có từ năm ý trở lên, được nhóm thành 3–5 chủ đề nhưng không được làm mất chi tiết. "
        "Không lấy nhiệm vụ, quyền hoặc nội dung của đối tượng khác để điền vào câu trả lời.",
    ),
])

CONFIRMATION_REPAIR_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Bạn là bộ kiểm tra nhất quán cho câu trả lời RAG dạng đúng/sai. Chỉ dùng nguồn "
        "được cung cấp, không nhắc tên tệp hoặc trang và không thêm kiến thức ngoài nguồn.",
    ),
    (
        "human",
        "[Mệnh đề cần xác nhận]\n{question}\n\n[Nguồn]\n{context}\n\n"
        "[Câu trả lời ban đầu]\n{existing_answer}\n\n"
        "Hãy tự đối chiếu mệnh đề với nguồn. Nếu mệnh đề sai, câu trả lời phải bắt đầu "
        "bằng 'Không,' rồi nêu thông tin đúng. Nếu mệnh đề đúng, câu trả lời phải bắt đầu "
        "bằng 'Đúng,'. Không được vừa đồng ý vừa phủ định cùng một mệnh đề. Chỉ trả về "
        "câu trả lời đã sửa bên trong cặp thẻ <FINAL> và </FINAL>.",
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
    """Use the preceding user question to make a short follow-up searchable.

    When the follow-up is very short (e.g. "Còn nữa không?"), the previous
    question is prepended in full so the embedding captures enough context.
    """
    if not conversation_history:
        return question
    previous_questions = [str(turn.get("question", "")).strip() for turn in conversation_history]
    previous_question = next((item for item in reversed(previous_questions) if item), "")
    if not previous_question:
        return question
    # Câu hỏi tiếp nối rất ngắn: nối đủ câu trước để retrieval có context
    if len(question.strip()) < 20:
        return f"{previous_question} {question}"
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


def _enumeration_answer_word_limit(question: str) -> int:
    """Allow broad list questions enough space without lengthening normal replies."""
    normalized = _search_normalize(question)
    exhaustive_markers = ("day du", "toan bo", "tat ca", "chi tiet", "khong bo sot")
    return 320 if any(marker in normalized for marker in exhaustive_markers) else 280


def asks_for_enumeration(question: str) -> bool:
    """Detect list/coverage intent without tying it to one document or sentence."""
    normalized = _search_normalize(question)
    explicit_markers = (
        "bao gom", "gom nhung", "liet ke", "day du", "toan bo", "tat ca",
        "khong bo sot", "duoc huong dan", "can lam gi", "co trach nhiem gi",
        "co nhung quyen", "co nhung nghia vu",
    )
    if any(marker in normalized for marker in explicit_markers):
        return True
    return bool(
        re.search(r"\b(?:nhung|cac)\b.{0,70}\b(?:gi|nao)\b", normalized)
        or re.search(
            r"\b(?:noi dung|ky nang|dieu kien|yeu cau|trach nhiem|nghia vu|quyen loi|thu tuc|truong hop)\b.{0,45}\b(?:gi|nao)\b",
            normalized,
        )
    )


def asks_for_confirmation(question: str) -> bool:
    """Detect Vietnamese yes/no assertions that require an explicit verdict."""
    normalized = _search_normalize(question)
    return bool(
        re.search(r"\b(?:dung|phai)\s+khong\b", normalized)
        or re.search(r"\bco\s+phai\b", normalized)
    )


def build_answer_guidance(question: str) -> str:
    if asks_for_enumeration(question):
        return (
            "Đây là câu hỏi liệt kê/tổng hợp. Xác định đúng mục và đúng đối tượng được hỏi, "
            "đọc hết các đoạn liên tiếp của mục rồi nêu mọi ý độc lập có trong nguồn; không "
            "dừng sau một số bullet tùy ý. Mở đầu bằng một câu trực tiếp và dùng bullet. "
            "Nếu có từ năm ý trở lên, nhóm thành 3–5 chủ đề để dễ đọc nhưng vẫn giữ đủ chi tiết. "
            "Không lấy nội dung của mục hoặc đối tượng khác có từ khóa gần giống."
        )
    if asks_for_confirmation(question):
        return (
            "Đây là câu hỏi xác nhận một mệnh đề. Đối chiếu toàn bộ mệnh đề với nguồn trước "
            "khi trả lời. Nếu sai, bắt đầu đúng bằng 'Không,' rồi sửa lại thông tin; nếu đúng, "
            "bắt đầu đúng bằng 'Đúng,'. Không đồng tình xã giao và không đưa ra hai kết luận "
            "mâu thuẫn trong cùng câu trả lời."
        )
    return "Trả lời trực tiếp, ngắn gọn theo các quy tắc hệ thống."


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


def _is_major_section_start(document: Document) -> bool:
    """Detect a top-level heading so section expansion stops at its boundary."""
    normalized = _search_normalize(document.page_content[:240])
    heading_names = (
        "muc dich", "yeu cau", "doi tuong", "thoi gian", "dia diem",
        "noi dung", "kinh phi", "to chuc thuc hien", "phan cong",
    )
    return bool(
        re.match(
            rf"^(?:[ivxlcdm]+|\d+)\s+(?:{'|'.join(heading_names)})\b",
            normalized,
        )
    )


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

    if asks_for_enumeration(question):
        section_title = _search_normalize(str(document.metadata.get("section_title", "")))
        section_tokens = {
            token for token in section_title.split() if len(token) >= 3
        }
        focus_stopwords = {
            "bao", "cac", "cho", "co", "cua", "duoc", "gi", "khi", "la",
            "nao", "nhung", "phai", "the", "tham", "theo", "trong", "ve",
            "truong", "dai", "hoc", "sinh", "vien", "hom", "nay", "hay",
            "biet", "cho", "voi", "mot", "nhieu", "it",
        }
        focus_tokens = {
            token for token in query_tokens if token not in focus_stopwords
        }
        heading_overlap = len(section_tokens & focus_tokens)
        if section_title and section_title in query:
            bonus += 0.30
        else:
            bonus += min(0.24, heading_overlap * 0.12)

        # Generic heading fallback: only reward prefix overlap if at least 2 distinct
        # non-stopword tokens match, avoiding false boosts from institutional headers.
        prefix_tokens = set(normalized_document[:220].split())
        prefix_overlap = len(focus_tokens & prefix_tokens)
        if prefix_overlap >= 2:
            bonus += min(0.12, (prefix_overlap - 1) * 0.04)

        duty_intent = any(
            marker in query
            for marker in (
                "trach nhiem", "nghia vu", "can lam", "can thuc hien",
                "phai lam", "phai thuc hien",
            )
        )
        responsibility_heading = re.search(
            r"\btrach nhiem cua\b.{0,80}", normalized_document[:220]
        )
        if duty_intent and responsibility_heading:
            heading_actor_tokens = set(responsibility_heading.group(0).split())
            actor_overlap = len(focus_tokens & heading_actor_tokens)
            bonus += 0.20
            if actor_overlap:
                bonus += 0.15

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

    finance_intent = any(
        marker in query
        for marker in ("kinh phi", "hoc phi", "muc chi", "muc ho tro", "so tien", "chi phi")
    )
    if finance_intent:
        money_matches = re.findall(
            r"\b\d{1,3}(?:\.\d{3})+\b|\b\d+\s*(?:trieu|nghin|dong)\b",
            normalized_document,
        )
        if money_matches:
            bonus += min(0.25, len(money_matches) * 0.12)
        if "kinh phi" in normalized_document[:220] or "hoc phi" in normalized_document[:220]:
            bonus += 0.15
    return bonus


def retrieval_evidence_score(question: str, document: Document, semantic_score: float) -> float:
    """Combine calibrated semantic similarity with explicit evidence signals."""
    return min(1.0, max(0.0, semantic_score + _retrieval_intent_bonus(question, document)))


def has_relevant_document(
    question: str,
    results: Sequence[tuple[Document, float]],
) -> bool:
    """Require evidence for named identifiers and topics before generation.

    Intent bonuses can lift a weak semantic match above the refusal threshold
    (for example, a handbook paragraph about weeks rather than a named event).
    Search both chunk text and its filename because scanned headings can be noisy.
    """
    if not results:
        return False
    normalized_question = _search_normalize(question)
    evidence = [
        _search_normalize(
            f"{doc.metadata.get('filename', '')} {doc.page_content}"
        )
        for doc, _score in results
    ]
    identifiers = set(re.findall(r"\b[a-z]+\d+\b", normalized_question))
    identifiers.update(re.findall(r"\bkhoa\s+\d+\b", normalized_question))
    def identifier_in_text(identifier: str, text: str) -> bool:
        aliases = {identifier}
        # Cohort labels can be abbreviated or written out in the PDF.
        cohort = re.fullmatch(r"k(\d+)", identifier)
        if cohort:
            aliases.add(f"khoa {cohort.group(1)}")
        full_cohort = re.fullmatch(r"khoa\s+(\d+)", identifier)
        if full_cohort:
            aliases.add(f"k{full_cohort.group(1)}")
        return any(re.search(rf"\b{re.escape(alias)}\b", text) for alias in aliases)

    # Common question words and broad university terms do not establish that
    # the retrieved document actually covers the subject being asked about.
    stopwords = {
        "ai", "bao", "cho", "co", "cua", "dai", "dien", "duoc", "gi",
        "hoc", "hoi", "khi", "khong", "la", "lam", "nao", "nhung",
        "phai", "ra", "sinh", "tai", "tan", "the", "theo", "trong",
        "truong", "tu", "ve", "vien", "vao",
    }
    tokens = normalized_question.split()
    topic_phrases = {
        f"{left} {right}"
        for left, right in zip(tokens, tokens[1:])
        if left not in stopwords and right not in stopwords
        and len(left) >= 3 and len(right) >= 3
    }
    topic_tokens = {
        token for token in tokens if token not in stopwords and len(token) >= 3
    }
    for (_doc, score), text in zip(results, evidence):
        if any(not identifier_in_text(identifier, text) for identifier in identifiers):
            continue
        if not topic_phrases or any(phrase in text for phrase in topic_phrases):
            return True
        if len(topic_tokens & set(text.split())) >= 2:
            return True
        # Preserve a strong semantic hit when OCR has damaged the wording.
        if score >= 0.45:
            return True
    return False


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
    """Select compact context or the complete matching section for list questions."""
    if not ranked_results:
        return []
    requested_level = re.search(
        r"\b(?:bac|level|muc)\s*(\d+)\b", _search_normalize(question)
    )
    if requested_level:
        level = int(requested_level.group(1))
        ranked_results = [
            (document, score) for document, score in ranked_results
            if document.metadata.get("table_level") in (None, level)
        ]
        if not ranked_results:
            return []
    selected = list(ranked_results[:TOP_K])
    if not asks_for_enumeration(question):
        return selected

    anchor_document, anchor_score = ranked_results[0]
    filename = str(anchor_document.metadata.get("filename", ""))
    if not filename:
        return selected

    try:
        records = vector_store._collection.get(
            where={"filename": {"$eq": filename}},
            include=["documents", "metadatas"],
        )
    except Exception as exc:
        logger.warning("Không thể mở rộng các chunk cùng mục: {}", exc)
        return selected

    score_by_text = {doc.page_content: score for doc, score in ranked_results}
    file_chunks = []
    for record_id, text, metadata in zip(
        records.get("ids", []),
        records.get("documents", []),
        records.get("metadatas", []),
    ):
        if not text or not metadata:
            continue
        if requested_level and metadata.get("table_level") not in (None, level):
            continue
        file_chunk = Document(page_content=text, metadata=dict(metadata))
        file_chunks.append(
            (
                _chunk_order(record_id, metadata),
                file_chunk,
                score_by_text.get(text, anchor_score),
            )
        )
    file_chunks.sort(key=lambda item: item[0])

    anchor_order = anchor_document.metadata.get("chunk_index")
    anchor_index = next((
        index for index, (order, document, _score) in enumerate(file_chunks)
        if (isinstance(anchor_order, int) and order == anchor_order)
        or document.page_content == anchor_document.page_content
    ), None)
    if anchor_index is None:
        return selected

    anchor_section = _search_normalize(
        str(anchor_document.metadata.get("section_title", ""))
    )
    start_index = anchor_index
    while start_index > 0 and anchor_index - start_index < 4:
        previous = file_chunks[start_index - 1][1]
        previous_section = _search_normalize(
            str(previous.metadata.get("section_title", ""))
        )
        if anchor_section and previous_section and previous_section != anchor_section:
            break
        if not anchor_section and _is_major_section_start(previous):
            break
        start_index -= 1

    section_chunks = []
    for index in range(start_index, len(file_chunks)):
        order, document, score = file_chunks[index]
        section = _search_normalize(str(document.metadata.get("section_title", "")))
        if index > anchor_index:
            if anchor_section and section and section != anchor_section:
                break
            if _is_major_section_start(document) and (
                not anchor_section or section != anchor_section
            ):
                break
            if not anchor_section and index > anchor_index + 2:
                break
        section_chunks.append((order, document, score))
        max_section_chunks = int(os.getenv("MAX_SECTION_CHUNKS", "20"))
        if len(section_chunks) >= max_section_chunks:
            logger.warning(f"Mục trả lời vượt {max_section_chunks} chunks; giới hạn ngữ cảnh đã được áp dụng")
            break

    expanded: list[tuple[Document, float]] = [
        (document, score) for _order, document, score in section_chunks
    ]
    if expanded:
        return expanded
    return selected


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
    cleaned = re.sub(r"[ \t]+", " ", answer or "").replace("**", "")
    # Restore the money-spelling suffix, including observed OCR errors,
    # only after a numeric amount and at a phrase boundary. This must not alter
    # real units or phrases such as "đồng chăn nuôi". Keep raw OCR unchanged.
    cleaned = re.sub(
        r"(\d[\d., \t]*[ \t]+đồng)(?:[ \t]*/[ \t]*|[ \t]+)"
        r"(?:chẵn|chãn|chăn|chắn|chan)\b(?=[ \t]*(?:$|[.,;:!?\n)]))",
        r"\1 chẵn",
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


def extract_final_answer(value: str) -> str:
    """Keep only the final answer when a coverage pass leaks its audit text."""
    text = (value or "").strip()
    tagged = re.search(r"<FINAL>\s*(.*?)\s*</FINAL>", text, flags=re.IGNORECASE | re.DOTALL)
    if tagged:
        content = tagged.group(1).strip()
        if content.lower().rstrip(". ,") not in ("câu trả lời hoàn chỉnh", "final answer", "..."):
            return content
    marker = re.search(
        r"(?:câu trả lời cuối cùng|final answer)\s*:?\s*(.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if marker:
        m_content = marker.group(1).strip()
        if m_content.lower().rstrip(". ,") not in ("câu trả lời hoàn chỉnh", "final answer", "..."):
            return m_content
    return text


def deduplicate_answer_lines(value: str) -> str:
    """Remove repeated list items and any connector left dangling after them."""
    kept: list[str] = []
    seen: set[str] = set()
    for line in (value or "").splitlines():
        content = re.sub(r"^[-•]\s+", "", line.strip())
        signature = _search_normalize(content)
        if len(signature.split()) >= 5 and signature in seen:
            continue
        if signature:
            seen.add(signature)
        kept.append(line)
    dangling_connectors = {"ngoai ra", "cu the", "bao gom"}
    while kept and _search_normalize(kept[-1]) in dangling_connectors:
        kept.pop()
    return "\n".join(kept).strip()


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
    4. Gọi Qwen3.5-9B qua Ollama
    5. Parse output
    """

    def __init__(self):
        self._embedding_model: Optional[HuggingFaceEmbeddings] = None
        self._vector_store: Optional[Chroma] = None
        self._llm: Optional[ChatOllama] = None
        self._audit_llm: Optional[ChatOllama] = None
        self._chain = None

    def initialize(self) -> None:
        """Khởi tạo tất cả components. Gọi một lần khi startup."""
        logger.info("Initializing RAG Chain...")

        # 1. Embedding model
        self._embedding_model = get_embedding_model()

        # 2. Vector store
        self._vector_store = get_vector_store(self._embedding_model)

        # 3. LLM (Qwen3.5-9B qua Ollama)
        self._llm = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            reasoning=False,
            temperature=LLM_TEMPERATURE,
            num_ctx=8192,           # Đủ cho một mục nhiều chunk và lịch sử ngắn
            num_predict=1000,       # Đủ cho câu trả lời liệt kê tối đa 320 từ
            top_p=0.9,
            repeat_penalty=1.1,
        )

        # Lượt kiểm tra danh sách cần ổn định để không thêm/bớt ý ngẫu nhiên.
        self._audit_llm = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            reasoning=False,
            temperature=LLM_AUDIT_TEMPERATURE,
            num_ctx=8192,
            num_predict=1000,
            top_p=0.9,
            repeat_penalty=1.1,
        )

        logger.info(
            "RAG Chain initialized: model={}, answer_temperature={}, "
            "audit_temperature={}",
            LLM_MODEL,
            LLM_TEMPERATURE,
            LLM_AUDIT_TEMPERATURE,
        )

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
    ) -> tuple[str, list[dict], float, Optional[str]]:
        """
        Async chat: trả về (answer, sources, avg_score, refusal_reason).

        refusal_reason là None khi LLM trả lời bình thường, hoặc một chuỗi
        mô tả lý do từ chối để main.py ghi vào activity log.
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
            return no_data_msg, [], 0.0, "no_data"

        # Retrieve documents với score
        retrieval_query = build_retrieval_query(question, conversation_history)
        if active_filenames is not None and not active_filenames:
            logger.info("RAG refusal: no active documents are available")
            return NO_ACTIVE_DOCUMENTS_MESSAGE, [], 0.0, "no_active_docs"

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
                NO_RELEVANT_DOCUMENTS_MESSAGE,
                [],
                0.0,
                "empty_retrieval",
            )

        if not has_relevant_document(question, retriever_with_score):
            logger.info("RAG refusal: no document supports the named topic or identifier")
            return NO_RELEVANT_DOCUMENTS_MESSAGE, [], 0.0, "no_relevant_document"

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
                f"low_score={best_evidence_score:.3f}",
            )

        context_results = select_context_results(
            self._vector_store,
            question,
            retriever_with_score,
        )
        if not context_results:
            logger.info("RAG refusal: no context remains after table-level filtering")
            return NO_RELEVANT_DOCUMENTS_MESSAGE, [], 0.0, "no_matching_table_level"
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
        is_enumeration = asks_for_enumeration(question)
        is_confirmation = asks_for_confirmation(question)
        response = await self._llm.ainvoke(prompt_messages)
        answer = response.content if hasattr(response, "content") else str(response)
        answer_word_limit = _enumeration_answer_word_limit(question) if is_enumeration else 100
        draft_word_limit = answer_word_limit + 80 if is_enumeration else answer_word_limit
        # Repair pass cần không gian rộng hơn để viết đầy đủ trước khi trim
        repair_word_limit = answer_word_limit + 150 if is_enumeration else answer_word_limit
        answer = remove_embedded_citations(
            normalize_answer(answer, max_words=draft_word_limit)
        )

        if is_confirmation:
            # Natural-temperature generation can agree socially before
            # contradicting the user's proposition. Re-evaluate the verdict
            # deterministically against the same retrieved evidence.
            repair_messages = CONFIRMATION_REPAIR_PROMPT.format_messages(
                question=question,
                context=context,
                existing_answer=answer,
            )
            reviewer = self._audit_llm or self._llm
            repair_response = await reviewer.ainvoke(repair_messages)
            repair_answer = (
                repair_response.content
                if hasattr(repair_response, "content")
                else str(repair_response)
            )
            repair_answer = normalize_answer(
                extract_final_answer(repair_answer),
                max_words=answer_word_limit,
            )
            if repair_answer:
                answer = remove_embedded_citations(repair_answer)

        if is_enumeration:
            # A second, domain-independent pass compares the draft with the
            # complete matching section. This avoids adding one hard-coded
            # checklist for every new wording or document topic.
            repair_messages = ENUMERATION_REPAIR_PROMPT.format_messages(
                question=question,
                context=context,
                existing_answer=answer,
            )
            reviewer = self._audit_llm or self._llm
            repair_response = await reviewer.ainvoke(repair_messages)
            repair_answer = (
                repair_response.content
                if hasattr(repair_response, "content")
                else str(repair_response)
            )
            repair_answer = extract_final_answer(repair_answer)
            repair_answer = normalize_answer(repair_answer, max_words=repair_word_limit)
            if repair_answer:
                answer = deduplicate_answer_lines(repair_answer)
            # Repair có thể tái sinh citation → cleanup sau cùng
            answer = remove_embedded_citations(answer)
            answer = normalize_answer(answer, max_words=answer_word_limit)

        if not answer.strip():
            logger.info("RAG refusal: model returned an empty answer")
            return NO_RELEVANT_DOCUMENTS_MESSAGE, [], avg_score, "empty_answer"

        # Trích xuất sources
        sources = extract_sources(docs, answer, scores)

        logger.info(
            f"RAG query: '{question[:50]}...' → "
            f"{len(retriever_with_score)} candidates, {len(docs)} context chunks, "
            f"avg_score={avg_score:.3f}, "
            f"best_evidence={best_evidence_score:.3f}"
        )
        return answer, sources, avg_score, None

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
