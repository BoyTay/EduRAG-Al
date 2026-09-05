"""
db.py - SQLite database models và helper functions
Sử dụng SQLAlchemy ORM để quản lý lịch sử hội thoại, metadata tài liệu,
và tài khoản admin.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime
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


# ─── Models ───────────────────────────────────────────────────────────────────

class ChatHistory(Base):
    """Bảng lưu lịch sử hội thoại."""
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    # Các phiên cũ có thể chưa có chủ sở hữu; phiên mới luôn gắn với tài khoản.
    user_id = Column(Integer, nullable=True, index=True)
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
    Tạo tài khoản admin mặc định nếu chưa có admin nào trong DB.
    Username/password lấy từ biến môi trường hoặc mặc định admin/admin123.
    """
    existing = db.query(AdminUser).first()
    if existing:
        logger.info(f"Admin user already exists: {existing.username}")
        return

    default_username = os.getenv("ADMIN_USERNAME", "admin")
    default_password = os.getenv("ADMIN_PASSWORD", "admin123")

    admin = AdminUser(
        username=default_username,
        password_hash=_hash_password(default_password),
        display_name="Quản trị viên",
    )
    db.add(admin)
    db.commit()
    logger.info(f"Default admin created: username='{default_username}'")


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


# ─── Chat History Helpers ─────────────────────────────────────────────────────

def save_chat(
    db: Session,
    session_id: str,
    user_message: str,
    bot_response: str,
    sources: Optional[list] = None,
    retrieval_score: Optional[float] = None,
    user_id: Optional[int] = None,
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
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.debug(f"Chat saved: session={session_id}, id={record.id}")
    return record


def save_feedback(db: Session, message_id: int, feedback: str, user_id: Optional[int] = None) -> bool:
    """
    Lưu feedback cho một tin nhắn.
    feedback: "up" hoặc "down"
    """
    query = db.query(ChatHistory).filter(ChatHistory.id == message_id)
    if user_id is not None:
        query = query.filter(ChatHistory.user_id == user_id)
    record = query.first()
    if record:
        record.feedback = feedback
        db.commit()
        logger.info(f"Feedback saved: message_id={message_id}, feedback={feedback}")
        return True
    return False


def get_chat_history(db: Session, session_id: str, limit: int = 50, user_id: Optional[int] = None) -> list[ChatHistory]:
    """Lấy lịch sử hội thoại của một session."""
    query = db.query(ChatHistory).filter(ChatHistory.session_id == session_id)
    if user_id is not None:
        query = query.filter(ChatHistory.user_id == user_id)
    return query.order_by(ChatHistory.timestamp.asc()).limit(limit).all()


def get_all_sessions(db: Session) -> list[str]:
    """Lấy danh sách tất cả session_id."""
    result = db.query(ChatHistory.session_id).distinct().all()
    return [r[0] for r in result]


def get_all_sessions_with_info(db: Session, limit: int = 30, user_id: Optional[int] = None) -> list[dict]:
    """Lấy danh sách session cùng câu hỏi đầu tiên (tiêu đề) và thời gian gần nhất."""
    # Lấy ID tin nhắn đầu tiên và thời gian gần nhất của từng session
    base_query = db.query(
            ChatHistory.session_id.label("sid"),
            func.min(ChatHistory.id).label("first_msg_id"),
            func.max(ChatHistory.timestamp).label("last_activity")
        )
    if user_id is not None:
        base_query = base_query.filter(ChatHistory.user_id == user_id)
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
            "last_time": r[1].isoformat() if r[1] else "",
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


def list_documents(db: Session) -> list[DocumentMetadata]:
    """Liệt kê tất cả tài liệu đã nạp."""
    return db.query(DocumentMetadata).order_by(DocumentMetadata.uploaded_at.desc()).all()


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
