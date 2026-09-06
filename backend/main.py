"""
main.py - FastAPI application chính
Khởi tạo app, các endpoints chính và lifespan management.
"""

import secrets
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger

from db import (
    get_db, init_db, save_chat, get_chat_history, get_all_sessions,
    get_all_sessions_with_info, create_default_admin, verify_admin,
    save_feedback, get_system_stats, create_student, get_student_by_email,
    verify_student, DocumentMetadata,
)
from rag_chain import rag_chain_instance
from admin import DATA_PATH, router as admin_router, set_rag_chain


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request body cho endpoint /chat."""
    question: str = Field(..., min_length=1, max_length=2000, description="Câu hỏi của người dùng")
    session_id: Optional[str] = Field(None, description="Session ID (tạo mới nếu không cung cấp)")


class SourceInfo(BaseModel):
    """Thông tin nguồn tài liệu."""
    filename: str
    page: Optional[int] = None
    source_path: Optional[str] = None
    display_name: Optional[str] = None
    category: Optional[str] = None
    issuing_unit: Optional[str] = None
    document_year: Optional[int] = None


class ChatResponse(BaseModel):
    """Response body cho endpoint /chat."""
    answer: str
    sources: list[SourceInfo]
    session_id: str
    retrieval_score: float
    message_id: int


class HistoryMessage(BaseModel):
    """Một tin nhắn trong lịch sử hội thoại."""
    id: int
    user_message: str
    bot_response: str
    sources: list
    timestamp: str
    retrieval_score: Optional[float] = None
    feedback: Optional[str] = None


class LoginRequest(BaseModel):
    """Request body cho endpoint /admin/login."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=100)
    display_name: Optional[str] = Field(None, max_length=100)


class FeedbackRequest(BaseModel):
    """Request body cho endpoint /chat/{message_id}/feedback."""
    feedback: str = Field(..., pattern="^(up|down)$", description="Feedback: 'up' hoặc 'down'")


# ─── Startup timestamp ───────────────────────────────────────────────────────
_startup_time: Optional[datetime] = None
# Token chỉ tồn tại trong bộ nhớ backend: khởi động lại dịch vụ yêu cầu đăng nhập lại.
_access_tokens: dict[str, dict] = {}


def _issue_token(user_id: int, role: str, email: str) -> str:
    token = secrets.token_urlsafe(32)
    _access_tokens[token] = {"user_id": user_id, "role": role, "email": email}
    return token


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập để tiếp tục")
    user = _access_tokens.get(authorization.removeprefix("Bearer ").strip())
    if not user:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn; vui lòng đăng nhập lại")
    return user


def enrich_sources(db: Session, sources: list) -> list[dict]:
    """Gắn metadata dễ đọc vào nguồn RAG mà không thay đổi vector store."""
    enriched = []
    for source in sources or []:
        item = dict(source)
        filename = item.get("filename")
        document = db.query(DocumentMetadata).filter(DocumentMetadata.filename == filename).first() if filename else None
        fallback_name = _humanize_filename(filename) if filename else "Tài liệu học vụ"
        if document:
            item.update({
                "display_name": document.display_name or fallback_name,
                "category": document.category,
                "issuing_unit": document.issuing_unit,
                "document_year": document.document_year,
            })
        else:
            item["display_name"] = fallback_name
        enriched.append(item)
    return enriched


def _humanize_filename(filename: str) -> str:
    """Biến tên file kỹ thuật thành nhãn an toàn khi chưa có metadata."""
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
    return re.sub(r"[_-]+", " ", stem).strip().title() or "Tài liệu học vụ"


def build_citation_labels(db: Session) -> dict[str, str]:
    """Tạo nhãn dùng trong prompt; filename chỉ còn là khóa nội bộ."""
    labels: dict[str, str] = {}
    for document in db.query(DocumentMetadata).all():
        title = document.display_name or _humanize_filename(document.filename)
        details = [value for value in (document.issuing_unit, document.document_year) if value]
        labels[document.filename] = f"{title} ({', '.join(map(str, details))})" if details else title
    return labels


def replace_technical_citations(answer: str, labels: dict[str, str]) -> str:
    """Lớp bảo vệ: không để LLM trả lời bằng tên file dù không tuân thủ prompt."""
    for filename, label in sorted(labels.items(), key=lambda item: len(item[0]), reverse=True):
        answer = re.sub(re.escape(filename), label, answer, flags=re.IGNORECASE)
    return answer


# ─── Lifespan (Startup & Shutdown) ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi tạo tài nguyên khi startup, dọn dẹp khi shutdown."""
    global _startup_time

    # STARTUP
    logger.info("=" * 60)
    logger.info("EduRAG Backend starting up...")

    # 1. Khởi tạo database
    init_db()

    # 2. Tạo tài khoản admin mặc định (nếu chưa có)
    from db import SessionLocal
    db = SessionLocal()
    try:
        create_default_admin(db)
    finally:
        db.close()

    # 3. Khởi tạo RAG chain (load embedding model + vector store)
    logger.info("Loading RAG components (this may take a moment)...")
    rag_chain_instance.initialize()

    # 4. Inject RAG chain vào admin router
    set_rag_chain(rag_chain_instance)

    _startup_time = datetime.utcnow()
    logger.info("EduRAG Backend ready! 🚀")
    logger.info("=" * 60)

    yield  # App đang chạy

    # SHUTDOWN
    logger.info("EduRAG Backend shutting down...")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="EduRAG API",
    description="Chatbot AI hỗ trợ sinh viên tra cứu quy chế đào tạo và tài liệu nghiệp vụ Khoa",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS - cho phép Streamlit frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong production, thay bằng URL cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount admin router
app.include_router(admin_router)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/documents/{filename}/preview", tags=["documents"])
def preview_pdf_document(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    """Trả file PDF đã nạp để frontend hiển thị preview có xác thực."""
    safe_filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if safe_filename != filename or not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ xem trước file PDF hợp lệ")

    file_path = DATA_PATH / safe_filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=safe_filename,
        content_disposition_type="inline",
    )

@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint."""
    vs = rag_chain_instance.vector_store
    doc_count = vs._collection.count() if vs else 0
    return {
        "status": "healthy",
        "vector_store_docs": doc_count,
        "llm_model": "qwen2.5:7b",
        "embedding_model": "AITeamVN/Vietnamese_Embedding",
    }


@app.post("/admin/login", tags=["admin"])
def admin_login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Đăng nhập admin với username và password.
    Trả về thông tin admin nếu đăng nhập thành công.
    """
    admin = verify_admin(db, request.username, request.password)
    if admin is None:
        raise HTTPException(
            status_code=401,
            detail="Sai tên đăng nhập hoặc mật khẩu",
        )
    return {
        "success": True,
        "user": {"id": admin.id, "email": admin.username, "display_name": admin.display_name or admin.username},
        "username": admin.username,
        "display_name": admin.display_name or admin.username,
        "last_login": admin.last_login.isoformat() if admin.last_login else None,
        "access_token": _issue_token(admin.id, "admin", admin.username),
    }


@app.post("/auth/register", status_code=201, tags=["auth"])
def register_student(request: RegisterRequest, db: Session = Depends(get_db)):
    """Đăng ký một tài khoản sinh viên mới."""
    email = request.email.lower().strip()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Email không hợp lệ")
    if get_student_by_email(db, email):
        raise HTTPException(status_code=409, detail="Email này đã được đăng ký")
    student = create_student(db, email, request.password, request.display_name)
    return {
        "success": True,
        "user": {"id": student.id, "email": student.email, "display_name": student.display_name or student.email},
        "access_token": _issue_token(student.id, "student", student.email),
    }


@app.post("/auth/login", tags=["auth"])
def student_login(request: LoginRequest, db: Session = Depends(get_db)):
    """Xác thực tài khoản sinh viên đã đăng ký."""
    student = verify_student(db, request.username, request.password)
    if not student:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    return {
        "success": True,
        "user": {"id": student.id, "email": student.email, "display_name": student.display_name or student.email},
        "access_token": _issue_token(student.id, "student", student.email),
    }


@app.get("/admin/stats", tags=["admin"])
def admin_stats(db: Session = Depends(get_db)):
    """Lấy thống kê tổng quát của hệ thống."""
    stats = get_system_stats(db)

    # Thêm thông tin uptime
    if _startup_time:
        uptime_seconds = (datetime.utcnow() - _startup_time).total_seconds()
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        stats["uptime"] = f"{hours}h {minutes}m"
    else:
        stats["uptime"] = "N/A"

    return stats


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Endpoint chính: nhận câu hỏi, thực hiện RAG, trả về câu trả lời kèm nguồn.

    - **question**: Câu hỏi của sinh viên
    - **session_id**: ID phiên hội thoại (tùy chọn, tạo mới nếu không có)
    """
    # Tạo session_id nếu chưa có
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(f"Chat request: session={session_id}, question='{request.question[:80]}'")

    try:
        # Thực hiện RAG
        citation_labels = build_citation_labels(db)
        answer, sources, avg_score = await rag_chain_instance.achat(
            request.question, citation_labels
        )
        answer = replace_technical_citations(answer, citation_labels)

        # Lưu lịch sử vào SQLite
        enriched_sources = enrich_sources(db, sources)
        record = save_chat(
            db=db,
            session_id=session_id,
            user_message=request.question,
            bot_response=answer,
            sources=enriched_sources,
            retrieval_score=avg_score,
            user_id=current_user["user_id"],
            user_role=current_user["role"],
        )

        return ChatResponse(
            answer=answer,
            sources=[SourceInfo(**s) for s in enriched_sources],
            session_id=session_id,
            retrieval_score=round(avg_score, 4),
            message_id=record.id,
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi xử lý câu hỏi: {str(e)}",
        )


@app.post("/chat/{message_id}/feedback", tags=["chat"])
def chat_feedback(
    message_id: int,
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Lưu feedback (👍/👎) cho một câu trả lời."""
    success = save_feedback(db, message_id, request.feedback, current_user["user_id"], current_user["role"])
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy tin nhắn với ID {message_id}",
        )
    return {
        "success": True,
        "message_id": message_id,
        "feedback": request.feedback,
    }


@app.get("/history/{session_id}", tags=["chat"])
def get_history(
    session_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Lấy lịch sử hội thoại của một session."""
    history = get_chat_history(db, session_id, limit, current_user["user_id"], current_user["role"])
    return {
        "session_id": session_id,
        "messages": [
            HistoryMessage(
                id=msg.id,
                user_message=msg.user_message,
                bot_response=msg.bot_response,
                sources=enrich_sources(db, msg.sources_list()),
                timestamp=msg.timestamp.isoformat(),
                retrieval_score=msg.retrieval_score,
                feedback=msg.feedback,
            )
            for msg in history
        ],
        "total": len(history),
    }


@app.get("/sessions", tags=["chat"])
def get_sessions(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Lấy danh sách session của chính tài khoản đang đăng nhập."""
    sessions_detail = get_all_sessions_with_info(db, user_id=current_user["user_id"], user_role=current_user["role"])
    session_ids = [s["session_id"] for s in sessions_detail]
    return {
        "sessions": session_ids,
        "sessions_detail": sessions_detail,
        "total": len(sessions_detail),
    }
