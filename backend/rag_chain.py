"""
rag_chain.py - Pipeline RAG chính
Kết hợp Chroma retriever + Qwen2.5-7B (Ollama) + LangChain để trả lời câu hỏi
dựa trên tài liệu được cung cấp.
"""

import os
import re
from pathlib import Path
from typing import Mapping, Optional

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
TOP_K = int(os.getenv("TOP_K", "5"))

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

def get_vector_store(embedding_model: Optional[HuggingFaceEmbeddings] = None) -> Chroma:
    """
    Kết nối hoặc tạo mới Chroma vector store.
    Nếu chưa có dữ liệu, trả về store rỗng (không lỗi).
    """
    if embedding_model is None:
        embedding_model = get_embedding_model()

    # Tạo thư mục nếu chưa có
    Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedding_model,
        persist_directory=CHROMA_PATH,
    )
    count = vector_store._collection.count()
    logger.info(f"Chroma loaded: {count} documents in collection '{COLLECTION_NAME}'")
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
8. Nếu có từ hai ý độc lập, dùng bullet; mỗi ý không quá 10 từ.
9. Toàn bộ câu trả lời tối đa 100 từ, không dùng dấu ngoặc kép.
10. Không viết "Trích dẫn từ", "Theo Điều...", tên tệp, đường dẫn, đuôi .pdf/.docx hoặc tên có dấu gạch dưới. Nguồn đã được hiển thị riêng bên dưới câu trả lời."""

USER_PROMPT_TEMPLATE = """[Tài liệu tham khảo]
{context}

[Câu hỏi của sinh viên]
{question}

Hãy chỉ dùng chi tiết được nêu trực tiếp trong đoạn phù hợp nhất. Không suy diễn thêm điều kiện. Nguồn sẽ được hệ thống hiển thị riêng bên dưới."""

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", USER_PROMPT_TEMPLATE),
])


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
    sources = []
    seen = set()
    for index, doc in enumerate(docs):
        meta = doc.metadata
        source = meta.get("source", "")
        source_name = Path(source).name if source else "Không rõ nguồn"
        page = meta.get("page", None)

        key = f"{source_name}_{page}"
        if key not in seen:
            seen.add(key)
            sources.append({
                "filename": source_name,
                "page": (page + 1) if page is not None else None,
                "source_path": source,
                # Ưu tiên đoạn chứng minh trực tiếp nội dung answer.
                "is_primary": index == primary_index,
            })
    return sources


def normalize_answer(answer: str, max_words: int = 100) -> str:
    """Dọn output local LLM và chặn câu trả lời dài vượt chuẩn UI."""
    cleaned = re.sub(r"[ \t]+", " ", answer or "")
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
            num_predict=220,        # Đủ cho câu trả lời ngắn, tránh lan man
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
                "answer": (lambda x: {"context": x["context"], "question": x["question"]})
                          | RAG_PROMPT
                          | self._llm
                          | StrOutputParser(),
                "docs": lambda x: x["docs"],
            }
        )
        return chain

    async def achat(
        self, question: str, source_labels: Optional[Mapping[str, str]] = None
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
        retriever_with_score = self._vector_store.similarity_search_with_relevance_scores(
            question, k=TOP_K
        )

        if not retriever_with_score:
            return (
                "Xin lỗi, tôi không tìm thấy thông tin phù hợp trong tài liệu hiện có. "
                "Vui lòng liên hệ trực tiếp với Khoa để được hỗ trợ.",
                [],
                0.0,
            )

        docs = [doc for doc, _ in retriever_with_score]
        scores = [score for _, score in retriever_with_score]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Format context
        context = format_docs(docs, source_labels)

        # Gọi LLM
        prompt_messages = RAG_PROMPT.format_messages(
            context=context, question=question
        )
        response = await self._llm.ainvoke(prompt_messages)
        answer = response.content if hasattr(response, "content") else str(response)
        answer = remove_embedded_citations(normalize_answer(answer))

        # Trích xuất sources
        sources = extract_sources(docs, answer, scores)

        logger.info(
            f"RAG query: '{question[:50]}...' → "
            f"{len(docs)} retrieved, avg_score={avg_score:.3f}"
        )
        return answer, sources, avg_score

    def reload_vector_store(self) -> None:
        """Reload vector store sau khi cập nhật tài liệu."""
        logger.info("Reloading vector store...")
        self._vector_store = get_vector_store(self._embedding_model)
        count = self._vector_store._collection.count()
        logger.info(f"Vector store reloaded: {count} documents")

    @property
    def vector_store(self) -> Optional[Chroma]:
        return self._vector_store

    @property
    def embedding_model(self) -> Optional[HuggingFaceEmbeddings]:
        return self._embedding_model


# ─── Singleton instance ───────────────────────────────────────────────────────
# Dùng singleton để tránh load model nhiều lần
rag_chain_instance = RAGChain()
