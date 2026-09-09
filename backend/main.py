"""
main.py - FastAPI application chính
Khởi tạo app, các endpoints chính và lifespan management.
"""

import os
import re
import smtplib
import ssl
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from email.message import EmailMessage
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header
import httpx
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger

from db import (
    get_db, init_db, save_chat, get_chat_history, get_all_sessions,
    get_all_sessions_with_info, get_recent_chat_history, create_default_admin, verify_admin,
    save_feedback, get_system_stats, create_student, get_student_by_email,
    verify_student, DocumentMetadata, get_account_user,
    update_account_display_name, change_account_password, create_auth_session,
    get_auth_session, revoke_auth_session, create_password_reset_token,
    consume_password_reset_token, get_recent_activities, get_retrievable_document_filenames, log_activity, as_utc_iso,
)
from rag_chain import rag_chain_instance
from admin import DATA_PATH, router as admin_router, set_rag_chain


def get_cors_origins() -> list[str]:
    """Parse an explicit CORS allowlist; wildcard origins are never accepted."""
    raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]
    if not origins:
        raise RuntimeError("CORS_ORIGINS phải chứa ít nhất một origin hợp lệ")
    if "*" in origins:
        raise RuntimeError("CORS_ORIGINS không được dùng '*'; hãy khai báo domain frontend cụ thể")
    return origins


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request body cho endpoint /chat."""
    question: str = Field(..., min_length=1, max_length=2000, description="Câu hỏi của người dùng")
    session_id: Optional[str] = Field(None, max_length=64, description="Session ID (tạo mới nếu không cung cấp)")
    document_filename: Optional[str] = Field(None, max_length=255, description="Chỉ tìm trong tài liệu này")


class SourceInfo(BaseModel):
    """Thông tin nguồn tài liệu."""
    filename: str
    page: Optional[int] = None
    source_path: Optional[str] = None
    display_name: Optional[str] = None
    category: Optional[str] = None
    issuing_unit: Optional[str] = None
    document_year: Optional[int] = None
    is_primary: bool = False


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
    remember: bool = False


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=100)
    display_name: Optional[str] = Field(None, max_length=100)


class FeedbackRequest(BaseModel):
    """Request body cho endpoint /chat/{message_id}/feedback."""
    feedback: str = Field(..., pattern="^(up|down)$", description="Feedback: 'up' hoặc 'down'")


class AccountProfileUpdate(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=100)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=100)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=100)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(..., min_length=20, max_length=5000)


# ─── Startup timestamp ───────────────────────────────────────────────────────
_startup_time: Optional[datetime] = None


def _issue_token(db: Session, user_id: int, role: str, email: str, remember: bool = False) -> str:
    return create_auth_session(db, user_id, role, email, remember)


def get_current_user(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập để tiếp tục")
    session = get_auth_session(db, authorization.removeprefix("Bearer ").strip())
    if not session:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn; vui lòng đăng nhập lại")
    return {"user_id": session.user_id, "role": session.user_role, "email": session.email}


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên được phép truy cập")
    return current_user


def _send_reset_email(email: str, token: str) -> None:
    """Gửi liên kết reset qua SMTP; thông tin nhạy cảm lấy từ biến môi trường."""
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM")
    if not host or not sender:
        raise RuntimeError("SMTP chưa được cấu hình")
    reset_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000').rstrip('/')}/reset-password?token={token}"
    message = EmailMessage()
    message["Subject"] = "Đặt lại mật khẩu EduRAG"
    message["From"] = sender
    message["To"] = email
    message.set_content(f"Bạn đã yêu cầu đặt lại mật khẩu EduRAG. Liên kết có hiệu lực 30 phút:\n{reset_url}\n\nNếu không phải bạn yêu cầu, hãy bỏ qua email này.")
    port = int(os.getenv("SMTP_PORT", "587"))
    username, password = os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD")
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as server:
            if username and password:
                server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=ssl.create_default_context())
            if username and password:
                server.login(username, password)
            server.send_message(message)


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

# CORS - chỉ cho phép các origin frontend đã khai báo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
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
    """Trả file PDF hoặc DOCX đã nạp để frontend hiển thị preview có xác thực."""
    safe_filename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    ext = safe_filename.lower().rsplit(".", 1)[-1] if "." in safe_filename else ""
    if safe_filename != filename or ext not in {"pdf", "docx"}:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ xem trước file PDF hoặc DOCX hợp lệ")

    file_path = DATA_PATH / safe_filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    media_type = (
        "application/pdf"
        if ext == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(
        path=file_path,
        media_type=media_type,
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
        "access_token": _issue_token(db, admin.id, "admin", admin.username, request.remember),
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
        "access_token": _issue_token(db, student.id, "student", student.email, True),
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
        "access_token": _issue_token(db, student.id, "student", student.email, request.remember),
    }


@app.get("/auth/providers", tags=["auth"])
def auth_providers():
    """Cấu hình provider có thể hiển thị ở frontend; Client ID Google vốn là public."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    return {"google": {"enabled": bool(client_id), "client_id": client_id}}


@app.post("/auth/forgot-password", tags=["auth"])
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Tạo token một lần và gửi mail cho sinh viên nếu địa chỉ tồn tại."""
    if not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM"):
        raise HTTPException(status_code=503, detail="Chức năng email chưa được cấu hình")
    student = get_student_by_email(db, request.email)
    if student:
        token = create_password_reset_token(db, student.id, "student")
        try:
            _send_reset_email(student.email, token)
        except Exception as error:
            logger.error(f"Cannot send password reset email: {error}")
            raise HTTPException(status_code=503, detail="Không thể gửi email đặt lại mật khẩu")
    # Phản hồi chung để không tiết lộ email nào đã tồn tại.
    return {"success": True, "message": "Nếu email tồn tại, liên kết đặt lại mật khẩu đã được gửi."}


@app.post("/auth/reset-password", tags=["auth"])
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    if not consume_password_reset_token(db, request.token, request.new_password):
        raise HTTPException(status_code=400, detail="Liên kết không hợp lệ hoặc đã hết hạn")
    return {"success": True, "message": "Đặt lại mật khẩu thành công. Hãy đăng nhập lại."}


@app.post("/auth/google", tags=["auth"])
async def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    """Xác minh Google ID token ở Google trước khi tạo/đăng nhập sinh viên."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=503, detail="Google Sign-In chưa được cấu hình")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": request.credential})
            response.raise_for_status()
            claims = response.json()
    except httpx.HTTPError:
        raise HTTPException(status_code=401, detail="Không thể xác minh tài khoản Google")
    if claims.get("aud") != client_id or claims.get("email_verified") not in (True, "true"):
        raise HTTPException(status_code=401, detail="Google credential không hợp lệ")
    email = str(claims.get("email", "")).lower().strip()
    if not email:
        raise HTTPException(status_code=401, detail="Google không cung cấp email hợp lệ")
    student = get_student_by_email(db, email)
    if not student:
        student = create_student(db, email, secrets.token_urlsafe(32), str(claims.get("name") or "Sinh viên"))
    return {
        "success": True,
        "user": {"id": student.id, "email": student.email, "display_name": student.display_name or student.email},
        "access_token": _issue_token(db, student.id, "student", student.email, True),
    }


@app.post("/auth/logout", tags=["auth"])
def logout(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if authorization and authorization.startswith("Bearer "):
        revoke_auth_session(db, authorization.removeprefix("Bearer ").strip())
    return {"success": True}


@app.get("/account", tags=["account"])
def get_account(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    """Thông tin hồ sơ của tài khoản hiện tại."""
    account = get_account_user(db, current_user["user_id"], current_user["role"])
    if not account:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    identifier = account.username if current_user["role"] == "admin" else account.email
    return {"user": {"id": account.id, "email": identifier, "display_name": account.display_name or identifier, "role": current_user["role"]}}


@app.patch("/account/profile", tags=["account"])
def update_account_profile(
    request: AccountProfileUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    display_name = request.display_name.strip()
    if len(display_name) < 2:
        raise HTTPException(status_code=422, detail="Tên hiển thị phải có ít nhất 2 ký tự")
    account = update_account_display_name(db, current_user["user_id"], current_user["role"], display_name)
    if not account:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    identifier = account.username if current_user["role"] == "admin" else account.email
    return {"success": True, "user": {"id": account.id, "email": identifier, "display_name": account.display_name or identifier, "role": current_user["role"]}}


@app.post("/account/password", tags=["account"])
def update_account_password(
    request: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if request.current_password == request.new_password:
        raise HTTPException(status_code=422, detail="Mật khẩu mới phải khác mật khẩu hiện tại")
    if not change_account_password(db, current_user["user_id"], current_user["role"], request.current_password, request.new_password):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    return {"success": True, "message": "Đã cập nhật mật khẩu"}


@app.get("/admin/stats", tags=["admin"])
def admin_stats(db: Session = Depends(get_db), _: dict = Depends(require_admin)):
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


@app.get("/admin/activities", tags=["admin"])
def admin_activities(
    limit: int = 20,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Danh sách hoạt động thật được ghi trong SQLite."""
    activities = get_recent_activities(db, max(1, min(limit, 100)))
    return {"activities": [{
        "id": activity.id,
        "action": activity.action,
        "entity_type": activity.entity_type,
        "entity_name": activity.entity_name,
        "actor_name": activity.actor_name,
        "actor_role": activity.actor_role,
        "created_at": as_utc_iso(activity.created_at),
    } for activity in activities]}


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
    document_filename = request.document_filename.strip() if request.document_filename else None
    if document_filename:
        # A document-scoped query must point to a real library item. This also
        # prevents arbitrary metadata values being sent to the vector filter.
        if "/" in document_filename or "\\" in document_filename or document_filename in {".", ".."}:
            raise HTTPException(status_code=400, detail="Tên tài liệu không hợp lệ")
        document = db.query(DocumentMetadata).filter(DocumentMetadata.filename == document_filename).first()
        if not document:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu được chọn")
        if document.status not in (None, "active"):
            raise HTTPException(
                status_code=409,
                detail="Tài liệu được chọn hiện không còn hiệu lực để trả lời AI",
            )

    active_filenames = get_retrievable_document_filenames(db)

    logger.info(
        f"Chat request: session={session_id}, question='{request.question[:80]}', "
        f"document={document_filename or 'all'}"
    )

    try:
        # Only the latest turns from this user's own session are used to
        # resolve follow-up references such as "điều kiện đó".
        previous_turns = get_recent_chat_history(
            db, session_id, limit=4,
            user_id=current_user["user_id"], user_role=current_user["role"],
        )
        conversation_history = [
            {"question": turn.user_message, "answer": turn.bot_response}
            for turn in previous_turns
        ]

        # Thực hiện RAG
        citation_labels = build_citation_labels(db)
        answer, sources, avg_score = await rag_chain_instance.achat(
            request.question, citation_labels, conversation_history,
            document_filename, active_filenames,
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
        log_activity(
            db, "chat_processed", "chat", None,
            current_user["email"], current_user["role"],
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
                timestamp=as_utc_iso(msg.timestamp),
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


@app.delete("/sessions/{session_id}", tags=["chat"])
def delete_session(session_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Xóa một phiên hội thoại cùng toàn bộ tin nhắn thuộc phiên đó."""
    query = db.query(ChatHistory).filter(ChatHistory.session_id == session_id)
    if current_user.get("role") != "admin":
        query = query.filter(ChatHistory.user_id == current_user["user_id"])
    count = query.delete(synchronize_session=False)
    db.commit()
    return {"status": "deleted", "session_id": session_id, "count": count}
