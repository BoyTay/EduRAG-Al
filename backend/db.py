"""
db.py - SQLite database models và helper functions
Sử dụng SQLAlchemy ORM để quản lý lịch sử hội thoại và metadata tài liệu.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, create_engine, Index
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
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)      # JSON string: list of source dicts
    retrieval_score = Column(Float, nullable=True)  # Average similarity score
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


# ─── Database Initialization ──────────────────────────────────────────────────

def init_db() -> None:
    """Tạo tất cả bảng nếu chưa tồn tại."""
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized at: {DB_PATH}")


# ─── Dependency (FastAPI) ─────────────────────────────────────────────────────

def get_db():
    """FastAPI dependency: cung cấp database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Chat History Helpers ─────────────────────────────────────────────────────

def save_chat(
    db: Session,
    session_id: str,
    user_message: str,
    bot_response: str,
    sources: Optional[list] = None,
    retrieval_score: Optional[float] = None,
) -> ChatHistory:
    """Lưu một lượt hội thoại vào database."""
    sources_json = json.dumps(sources, ensure_ascii=False) if sources else None
    record = ChatHistory(
        session_id=session_id,
        user_message=user_message,
        bot_response=bot_response,
        sources=sources_json,
        retrieval_score=retrieval_score,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.debug(f"Chat saved: session={session_id}, id={record.id}")
    return record


def get_chat_history(db: Session, session_id: str, limit: int = 50) -> list[ChatHistory]:
    """Lấy lịch sử hội thoại của một session."""
    return (
        db.query(ChatHistory)
        .filter(ChatHistory.session_id == session_id)
        .order_by(ChatHistory.timestamp.asc())
        .limit(limit)
        .all()
    )


def get_all_sessions(db: Session) -> list[str]:
    """Lấy danh sách tất cả session_id."""
    result = db.query(ChatHistory.session_id).distinct().all()
    return [r[0] for r in result]


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
