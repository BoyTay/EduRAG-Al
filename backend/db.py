"""
db.py - SQLite database models và helper functions
Sử dụng SQLAlchemy ORM để quản lý lịch sử hội thoại, metadata tài liệu,
và tài khoản admin.
"""

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, create_engine, Index, func
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.pool import StaticPool
from loguru import logger

# ─── Đường dẫn database ───────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "chat_history.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ─── SQLAlchemy setup ─────────────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def as_utc_iso(value: Optional[datetime]) -> str:
    """SQLite lưu UTC dạng naive; API phải ghi rõ timezone để client không lệch ngày."""
    if not value:
        return ""
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.astimezone(timezone.utc).isoformat()


# ─── Models ───────────────────────────────────────────────────────────────────

class ChatHistory(Base):
    """Bảng lưu lịch sử hội thoại."""
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    # Các phiên cũ có thể chưa có chủ sở hữu; phiên mới luôn gắn với tài khoản.
    user_id = Column(Integer, nullable=True, index=True)
    # Cần lưu cả role vì ID của AdminUser và Student có thể trùng nhau.
    user_role = Column(String(20), nullable=True, index=True)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)      # JSON string: list of source dicts
    retrieval_score = Column(Float, nullable=True)  # Average similarity score
    feedback = Column(String(10), nullable=True)     # "up", "down", or null
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_chat_session_time", "session_id", "timestamp"),
    )

    def sources_list(self) -> list:
        """Chuyển JSON string sources thành list."""
        if not self.sources:
            return []
        try:
            return json.loads(self.sources)
        except (json.JSONDecodeError, TypeError):
            return []


class DocumentMetadata(Base):
    """Bảng lưu metadata các tài liệu đã nạp vào vector store."""
    __tablename__ = "document_metadata"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(255), nullable=False, unique=True, index=True)
    file_path = Column(Text, nullable=False)
    file_type = Column(String(10), nullable=False)   # "pdf" or "docx"
    chunk_count = Column(Integer, default=0)
    file_size_kb = Column(Float, default=0.0)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    description = Column(Text, nullable=True)
    display_name = Column(String(255), nullable=True)
    category = Column(String(80), nullable=True, index=True)
    issuing_unit = Column(String(150), nullable=True)
    document_year = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(30), nullable=True, default="active")


class AdminUser(Base):
    """Bảng lưu tài khoản admin."""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(64), nullable=False)  # SHA-256 hash
    display_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)


class StudentUser(Base):
    """Tài khoản sinh viên đăng ký trực tiếp trên EduRAG."""
    __tablename__ = "student_users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)


class AuthSession(Base):
    """Phiên đăng nhập đã hash; token thô không bao giờ lưu trong SQLite."""
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    user_role = Column(String(20), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PasswordResetToken(Base):
    """Token đặt lại mật khẩu, chỉ dùng một lần và tự hết hạn."""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    user_role = Column(String(20), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ActivityLog(Base):
    """Nhật ký hành động thật để hiển thị trên dashboard quản trị."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    action = Column(String(40), nullable=False, index=True)
    entity_type = Column(String(40), nullable=False)
    entity_name = Column(String(255), nullable=True)
    actor_name = Column(String(120), nullable=False)
    actor_role = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# ─── Password Hashing ────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str | None = None) -> str:
    """Hash mật khẩu bằng PBKDF2-HMAC-SHA256 (không lưu mật khẩu thô)."""
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Hỗ trợ cả hash PBKDF2 mới và hash SHA-256 của tài khoản admin cũ."""
    if stored_hash.startswith("pbkdf2_sha256$"):
        _, salt, _ = stored_hash.split("$", 2)
        return hmac.compare_digest(_hash_password(password, salt), stored_hash)
    return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored_hash)


# ─── Database Initialization ──────────────────────────────────────────────────

def init_db() -> None:
    """Tạo tất cả bảng nếu chưa tồn tại."""
    Base.metadata.create_all(bind=engine)

    # Migration nhẹ: thêm cột feedback nếu DB cũ chưa có
    try:
        with engine.connect() as conn:
            from sqlalchemy import text, inspect
            inspector = inspect(engine)
            columns = [c["name"] for c in inspector.get_columns("chat_history")]
            if "feedback" not in columns:
                conn.execute(text("ALTER TABLE chat_history ADD COLUMN feedback VARCHAR(10)"))
                conn.commit()
                logger.info("Migration: added 'feedback' column to chat_history")
            if "user_id" not in columns:
                conn.execute(text("ALTER TABLE chat_history ADD COLUMN user_id INTEGER"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_history_user_id ON chat_history (user_id)"))
                conn.commit()
                logger.info("Migration: added 'user_id' column to chat_history")
            if "user_role" not in columns:
                conn.execute(text("ALTER TABLE chat_history ADD COLUMN user_role VARCHAR(20)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_history_user_role ON chat_history (user_role)"))
                conn.commit()
                logger.info("Migration: added 'user_role' column to chat_history")

            document_columns = [c["name"] for c in inspector.get_columns("document_metadata")]
            document_migrations = {
                "display_name": "ALTER TABLE document_metadata ADD COLUMN display_name VARCHAR(255)",
                "category": "ALTER TABLE document_metadata ADD COLUMN category VARCHAR(80)",
                "issuing_unit": "ALTER TABLE document_metadata ADD COLUMN issuing_unit VARCHAR(150)",
                "document_year": "ALTER TABLE document_metadata ADD COLUMN document_year INTEGER",
                "summary": "ALTER TABLE document_metadata ADD COLUMN summary TEXT",
                "status": "ALTER TABLE document_metadata ADD COLUMN status VARCHAR(30) DEFAULT 'active'",
            }
            for column, statement in document_migrations.items():
                if column not in document_columns:
                    conn.execute(text(statement))
                    logger.info(f"Migration: added '{column}' to document_metadata")
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_metadata_category ON document_metadata (category)"))
            conn.commit()
    except Exception as e:
        logger.debug(f"Migration check skipped: {e}")

    logger.info(f"Database initialized at: {DB_PATH}")


# ─── Dependency (FastAPI) ─────────────────────────────────────────────────────

def get_db():
    """FastAPI dependency: cung cấp database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Admin User Helpers ──────────────────────────────────────────────────────

def create_default_admin(db: Session) -> None:
    """
    Tạo admin đầu tiên từ biến môi trường nếu database chưa có admin nào.
    Không bao giờ dùng thông tin đăng nhập hard-code.
    """
    existing = db.query(AdminUser).first()
    if existing:
        logger.info(f"Admin user already exists: {existing.username}")
        return

    default_username = (os.getenv("ADMIN_USERNAME") or "").strip()
    default_password = os.getenv("ADMIN_PASSWORD") or ""
    if not default_username or not default_password:
        raise RuntimeError(
            "Database chưa có admin. Hãy đặt ADMIN_USERNAME và ADMIN_PASSWORD trong file .env trước khi khởi động."
        )
    if len(default_password) < 12:
        raise RuntimeError("ADMIN_PASSWORD phải có ít nhất 12 ký tự")

    admin = AdminUser(
        username=default_username,
        password_hash=_hash_password(default_password),
        display_name="Quản trị viên",
    )
    db.add(admin)
    db.commit()
    logger.info(f"Initial admin created: username='{default_username}'")


def verify_admin(db: Session, username: str, password: str) -> Optional[AdminUser]:
    """
    Xác thực đăng nhập admin.
    Trả về AdminUser nếu hợp lệ, None nếu sai.
    """
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if admin and not _verify_password(password, admin.password_hash):
        admin = None
    if admin:
        # Cập nhật last_login
        admin.last_login = datetime.utcnow()
        db.commit()
        db.refresh(admin)
        logger.info(f"Admin login successful: {username}")
    else:
        logger.warning(f"Admin login failed: {username}")
    return admin


def create_student(db: Session, email: str, password: str, display_name: str | None = None) -> StudentUser:
    """Tạo tài khoản sinh viên; caller cần kiểm tra email trùng trước."""
    student = StudentUser(
        email=email.lower().strip(),
        password_hash=_hash_password(password),
        display_name=(display_name or "").strip() or None,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def get_student_by_email(db: Session, email: str) -> Optional[StudentUser]:
    return db.query(StudentUser).filter(StudentUser.email == email.lower().strip()).first()


def verify_student(db: Session, email: str, password: str) -> Optional[StudentUser]:
    student = get_student_by_email(db, email)
    if not student or not _verify_password(password, student.password_hash):
        return None
    student.last_login = datetime.utcnow()
    db.commit()
    db.refresh(student)
    return student


def get_account_user(db: Session, user_id: int, role: str) -> Optional[AdminUser | StudentUser]:
    """Lấy đúng tài khoản theo token hiện hành."""
    if role == "admin":
        return db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if role == "student":
        return db.query(StudentUser).filter(StudentUser.id == user_id).first()
    return None


def update_account_display_name(
    db: Session, user_id: int, role: str, display_name: str
) -> Optional[AdminUser | StudentUser]:
    account = get_account_user(db, user_id, role)
    if not account:
        return None
    account.display_name = display_name.strip()
    db.commit()
    db.refresh(account)
    return account


def change_account_password(
    db: Session, user_id: int, role: str, current_password: str, new_password: str
) -> bool:
    """Đổi mật khẩu sau khi kiểm tra mật khẩu hiện tại."""
    account = get_account_user(db, user_id, role)
    if not account or not _verify_password(current_password, account.password_hash):
        return False
    account.password_hash = _hash_password(new_password)
    db.commit()
    return True


def create_auth_session(
    db: Session, user_id: int, role: str, email: str, remember: bool = False
) -> str:
    token = secrets.token_urlsafe(32)
    session = AuthSession(
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        user_id=user_id,
        user_role=role,
        email=email,
        expires_at=datetime.utcnow() + timedelta(days=30 if remember else 0, hours=0 if remember else 12),
    )
    db.add(session)
    db.commit()
    return token


def get_auth_session(db: Session, token: str) -> Optional[AuthSession]:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = db.query(AuthSession).filter(AuthSession.token_hash == token_hash).first()
    if not session:
        return None
    if session.expires_at <= datetime.utcnow():
        db.delete(session)
        db.commit()
        return None
    return session


def revoke_auth_session(db: Session, token: str) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.query(AuthSession).filter(AuthSession.token_hash == token_hash).delete()
    db.commit()


def revoke_user_sessions(db: Session, user_id: int, role: str) -> None:
    db.query(AuthSession).filter(AuthSession.user_id == user_id, AuthSession.user_role == role).delete()
    db.commit()


def create_password_reset_token(db: Session, user_id: int, role: str) -> str:
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.user_role == role,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": datetime.utcnow()})
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        user_id=user_id,
        user_role=role,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    ))
    db.commit()
    return token


def consume_password_reset_token(db: Session, token: str, new_password: str) -> bool:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    reset = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    if not reset or reset.used_at or reset.expires_at <= datetime.utcnow():
        return False
    account = get_account_user(db, reset.user_id, reset.user_role)
    if not account:
        return False
    account.password_hash = _hash_password(new_password)
    reset.used_at = datetime.utcnow()
    db.query(AuthSession).filter(AuthSession.user_id == reset.user_id, AuthSession.user_role == reset.user_role).delete()
    db.commit()
    return True


def log_activity(
    db: Session, action: str, entity_type: str, entity_name: Optional[str],
    actor_name: str, actor_role: str,
) -> ActivityLog:
    record = ActivityLog(
        action=action, entity_type=entity_type, entity_name=entity_name,
        actor_name=actor_name, actor_role=actor_role,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_recent_activities(db: Session, limit: int = 50) -> list[ActivityLog]:
    return db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit).all()


# ─── Chat History Helpers ─────────────────────────────────────────────────────

def save_chat(
    db: Session,
    session_id: str,
    user_message: str,
    bot_response: str,
    sources: Optional[list] = None,
    retrieval_score: Optional[float] = None,
    user_id: Optional[int] = None,
    user_role: Optional[str] = None,
) -> ChatHistory:
    """Lưu một lượt hội thoại vào database."""
    sources_json = json.dumps(sources, ensure_ascii=False) if sources else None
    record = ChatHistory(
        session_id=session_id,
        user_message=user_message,
        bot_response=bot_response,
        sources=sources_json,
        retrieval_score=retrieval_score,
        user_id=user_id,
        user_role=user_role,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.debug(f"Chat saved: session={session_id}, id={record.id}")
    return record


def save_feedback(db: Session, message_id: int, feedback: str, user_id: Optional[int] = None, user_role: Optional[str] = None) -> bool:
    """
    Lưu feedback cho một tin nhắn.
    feedback: "up" hoặc "down"
    """
    query = db.query(ChatHistory).filter(ChatHistory.id == message_id)
    if user_id is not None:
        query = query.filter(ChatHistory.user_id == user_id)
    if user_role is not None:
        query = query.filter(ChatHistory.user_role == user_role)
    record = query.first()
    if record:
        record.feedback = feedback
        db.commit()
        logger.info(f"Feedback saved: message_id={message_id}, feedback={feedback}")
        return True
    return False


def get_chat_history(db: Session, session_id: str, limit: int = 50, user_id: Optional[int] = None, user_role: Optional[str] = None) -> list[ChatHistory]:
    """Lấy lịch sử hội thoại của một session."""
    query = db.query(ChatHistory).filter(ChatHistory.session_id == session_id)
    if user_id is not None:
        query = query.filter(ChatHistory.user_id == user_id)
    if user_role is not None:
        query = query.filter(ChatHistory.user_role == user_role)
    return query.order_by(ChatHistory.timestamp.asc()).limit(limit).all()


def get_recent_chat_history(
    db: Session,
    session_id: str,
    limit: int = 4,
    user_id: Optional[int] = None,
    user_role: Optional[str] = None,
) -> list[ChatHistory]:
    """Return the newest conversation turns in chronological order for RAG context."""
    query = db.query(ChatHistory).filter(ChatHistory.session_id == session_id)
    if user_id is not None:
        query = query.filter(ChatHistory.user_id == user_id)
    if user_role is not None:
        query = query.filter(ChatHistory.user_role == user_role)
    newest_first = query.order_by(ChatHistory.timestamp.desc(), ChatHistory.id.desc()).limit(limit).all()
    return list(reversed(newest_first))


def get_all_sessions(db: Session) -> list[str]:
    """Lấy danh sách tất cả session_id."""
    result = db.query(ChatHistory.session_id).distinct().all()
    return [r[0] for r in result]


def get_all_sessions_with_info(db: Session, limit: int = 30, user_id: Optional[int] = None, user_role: Optional[str] = None) -> list[dict]:
    """Lấy danh sách session cùng câu hỏi đầu tiên (tiêu đề) và thời gian gần nhất."""
    # Lấy ID tin nhắn đầu tiên và thời gian gần nhất của từng session
    base_query = db.query(
            ChatHistory.session_id.label("sid"),
            func.min(ChatHistory.id).label("first_msg_id"),
            func.max(ChatHistory.timestamp).label("last_activity")
        )
    if user_id is not None:
        base_query = base_query.filter(ChatHistory.user_id == user_id)
    if user_role is not None:
        base_query = base_query.filter(ChatHistory.user_role == user_role)
    sub = base_query.group_by(ChatHistory.session_id).subquery()

    records = (
        db.query(
            sub.c.sid,
            sub.c.last_activity,
            ChatHistory.user_message
        )
        .join(ChatHistory, ChatHistory.id == sub.c.first_msg_id)
        .order_by(sub.c.last_activity.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "session_id": r[0],
            "last_time": as_utc_iso(r[1]),
            "title": r[2] if r[2] else f"Phiên {r[0][:8]}..."
        }
        for r in records
    ]


# ─── Document Metadata Helpers ────────────────────────────────────────────────

def add_document_metadata(
    db: Session,
    filename: str,
    file_path: str,
    file_type: str,
    chunk_count: int = 0,
    file_size_kb: float = 0.0,
    description: Optional[str] = None,
    display_name: Optional[str] = None,
    category: Optional[str] = None,
    issuing_unit: Optional[str] = None,
    document_year: Optional[int] = None,
    summary: Optional[str] = None,
    status: Optional[str] = "active",
) -> DocumentMetadata:
    """Thêm hoặc cập nhật metadata tài liệu."""
    existing = db.query(DocumentMetadata).filter_by(filename=filename).first()
    if existing:
        # Cập nhật nếu đã tồn tại
        existing.file_path = file_path
        existing.file_type = file_type
        existing.chunk_count = chunk_count
        existing.file_size_kb = file_size_kb
        existing.uploaded_at = datetime.utcnow()
        existing.description = description
        existing.display_name = display_name or existing.display_name
        existing.category = category or existing.category
        existing.issuing_unit = issuing_unit or existing.issuing_unit
        existing.document_year = document_year or existing.document_year
        existing.summary = summary or existing.summary
        existing.status = status or existing.status
        db.commit()
        db.refresh(existing)
        logger.info(f"Document metadata updated: {filename}")
        return existing
    else:
        doc = DocumentMetadata(
            filename=filename,
            file_path=file_path,
            file_type=file_type,
            chunk_count=chunk_count,
            file_size_kb=file_size_kb,
            description=description,
            display_name=display_name,
            category=category,
            issuing_unit=issuing_unit,
            document_year=document_year,
            summary=summary,
            status=status,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        logger.info(f"Document metadata added: {filename}")
        return doc


def remove_document_metadata(db: Session, filename: str) -> bool:
    """Xóa metadata tài liệu. Trả về True nếu xóa thành công."""
    doc = db.query(DocumentMetadata).filter_by(filename=filename).first()
    if doc:
        db.delete(doc)
        db.commit()
        logger.info(f"Document metadata removed: {filename}")
        return True
    return False


def update_document_metadata(db: Session, filename: str, **values) -> Optional[DocumentMetadata]:
    """Cập nhật phần metadata mô tả, không tác động file hay vector store."""
    doc = db.query(DocumentMetadata).filter_by(filename=filename).first()
    if not doc:
        return None
    allowed_fields = {"display_name", "category", "issuing_unit", "document_year", "summary", "status", "description"}
    for field, value in values.items():
        if field in allowed_fields and value is not None:
            setattr(doc, field, value)
    db.commit()
    db.refresh(doc)
    return doc


def list_documents(db: Session) -> list[DocumentMetadata]:
    """Liệt kê tất cả tài liệu đã nạp."""
    return db.query(DocumentMetadata).order_by(DocumentMetadata.uploaded_at.desc()).all()


def get_retrievable_document_filenames(db: Session) -> list[str]:
    """Return only documents that are currently allowed to answer RAG queries."""
    rows = (
        db.query(DocumentMetadata.filename)
        .filter((DocumentMetadata.status == "active") | DocumentMetadata.status.is_(None))
        .all()
    )
    return [row[0] for row in rows]


# ─── System Stats ─────────────────────────────────────────────────────────────

def get_system_stats(db: Session) -> dict:
    """Lấy thống kê tổng quát của hệ thống."""
    total_docs = db.query(func.count(DocumentMetadata.id)).scalar() or 0
    total_chunks = db.query(func.sum(DocumentMetadata.chunk_count)).scalar() or 0
    total_sessions = db.query(func.count(func.distinct(ChatHistory.session_id))).scalar() or 0
    total_messages = db.query(func.count(ChatHistory.id)).scalar() or 0
    total_feedback_up = (
        db.query(func.count(ChatHistory.id))
        .filter(ChatHistory.feedback == "up")
        .scalar() or 0
    )
    total_feedback_down = (
        db.query(func.count(ChatHistory.id))
        .filter(ChatHistory.feedback == "down")
        .scalar() or 0
    )

    # Thời gian upload gần nhất
    last_upload = (
        db.query(func.max(DocumentMetadata.uploaded_at)).scalar()
    )

    return {
        "total_documents": total_docs,
        "total_chunks": int(total_chunks),
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_feedback_up": total_feedback_up,
        "total_feedback_down": total_feedback_down,
        "last_upload": last_upload.isoformat() if last_upload else None,
    }
