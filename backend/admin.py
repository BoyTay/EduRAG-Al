"""
admin.py - Router quản trị tài liệu
Cung cấp endpoints để upload, xóa tài liệu và cập nhật vector store.
"""

import os
import shutil
import threading
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger
from starlette.concurrency import run_in_threadpool

import pymupdf as fitz

from chunk_inspection import EDITABLE_METHODS, list_document_chunks, summarize_pages
from db import DocumentMetadata, as_utc_iso, get_db, add_document_metadata, remove_document_metadata, list_documents, update_document_metadata, log_activity, get_page_overrides, get_page_review_rows, upsert_page_review, delete_page_review
from auth import get_current_user, require_admin
from document_ingestion import (
    DocumentIngestionError,
    DocumentIngestionResult,
    IngestionSettings,
    cleanup_document_cache,
    cleanup_new_cache_entries,
    load_and_chunk_document,
    read_page_ocr_text,
    sha256_file,
)
from page_review import PageOverride

# ─── Cấu hình ─────────────────────────────────────────────────────────────────
DATA_PATH = Path(os.getenv("DATA_PATH", str(Path(__file__).parent.parent / "data")))
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
MAX_BATCH_UPLOAD_BYTES = int(os.getenv("MAX_BATCH_UPLOAD_BYTES", str(100 * 1024 * 1024)))
UPLOAD_CHUNK_BYTES = 1024 * 1024

router = APIRouter(prefix="/admin", tags=["admin"])


class DocumentMetadataUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=80)
    issuing_unit: Optional[str] = Field(None, max_length=150)
    document_year: Optional[int] = Field(None, ge=1900, le=2100)
    summary: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, max_length=30)


class DocumentReviewRequest(BaseModel):
    reviewed: bool

# Import rag_chain_instance sẽ được inject sau
_rag_chain = None
_rebuild_lock = threading.Lock()


def set_rag_chain(chain):
    """Inject RAG chain instance từ main.py."""
    global _rag_chain
    _rag_chain = chain


def normalize_document_filename(filename: Optional[str]) -> str:
    """Only accept a plain filename, never a client-supplied path."""
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ")
    filename = filename.strip()
    if "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Tên file không được chứa đường dẫn")
    if len(filename) > 255 or any(ord(char) < 32 for char in filename):
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ")
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ")
    return filename


def get_safe_document_path(filename: Optional[str]) -> tuple[str, Path]:
    """Resolve a document path and prove it stays directly inside DATA_PATH."""
    safe_filename = normalize_document_filename(filename)
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    data_root = DATA_PATH.resolve()
    file_path = (data_root / safe_filename).resolve()
    if file_path.parent != data_root:
        raise HTTPException(status_code=400, detail="Đường dẫn tài liệu không hợp lệ")
    return safe_filename, file_path


def validate_document_content(file_path: Path, file_ext: str) -> None:
    """Validate lightweight file signatures before a loader receives the upload."""
    if file_ext == ".pdf":
        with file_path.open("rb") as uploaded_file:
            if not uploaded_file.read(5).startswith(b"%PDF-"):
                raise ValueError("Nội dung file không phải PDF hợp lệ")
        return

    if file_ext == ".docx":
        if not zipfile.is_zipfile(file_path):
            raise ValueError("Nội dung file không phải DOCX hợp lệ")
        with zipfile.ZipFile(file_path) as archive:
            members = set(archive.namelist())
            if "[Content_Types].xml" not in members or "word/document.xml" not in members:
                raise ValueError("File ZIP không có cấu trúc DOCX hợp lệ")
        return

    raise ValueError("Định dạng file không được hỗ trợ")


async def save_upload_file(upload: UploadFile, destination: Path, byte_limit: int) -> int:
    """Stream an upload to disk while enforcing a hard byte limit."""
    temporary_path = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.upload")
    total_bytes = 0
    try:
        with temporary_path.open("wb") as output:
            while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                total_bytes += len(chunk)
                if total_bytes > byte_limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File vượt quá giới hạn {byte_limit // (1024 * 1024)} MB",
                    )
                output.write(chunk)
        temporary_path.replace(destination)
        return total_bytes
    except Exception:
        safe_delete_file(temporary_path)
        raise


# ─── Helper: Vector write & document transaction ─────────────────────────────

@dataclass
class VectorWriteResult:
    vector_store: Any
    filename: str
    new_ids: list[str]
    old_ids: list[str]
    count: int


@dataclass
class ProcessedDocument:
    ingestion: DocumentIngestionResult
    vector_write: VectorWriteResult
    document: DocumentMetadata


def add_to_vector_store(chunks: list, filename: str, vector_store=None) -> VectorWriteResult:
    """Upsert a versioned vector set and return exact IDs for commit/rollback."""
    if _rag_chain is None:
        raise RuntimeError("RAG chain chưa được khởi tạo")

    vs = vector_store or _rag_chain.vector_store
    if vs is None:
        raise RuntimeError("Vector store chưa sẵn sàng")
    embedding_model = _rag_chain.embedding_model
    if embedding_model is None:
        raise RuntimeError("Embedding model chưa sẵn sàng")

    texts = []
    metadatas = []
    for chunk in chunks:
        text = (chunk.page_content or "").strip()
        if not text:
            continue
        texts.append(text)
        metadata = dict(chunk.metadata or {})
        metadata["filename"] = filename
        metadatas.append(metadata)

    if not texts:
        raise ValueError(
            f"Không trích xuất được nội dung văn bản hợp lệ từ '{filename}'. "
            "File có thể là PDF scan/ảnh hoặc text bị rỗng."
        )

    # Capture the old IDs before writing. New IDs are versioned so an upsert
    # can succeed without overwriting an old chunk that has not been retired.
    existing = vs._collection.get(
        where={"filename": {"$eq": filename}}, include=["documents"]
    )
    old_ids = existing.get("ids", [])

    embeddings = embedding_model.embed_documents(texts)
    if not embeddings:
        raise ValueError(
            f"Embedding trả về rỗng cho '{filename}'. "
            "Hãy kiểm tra lại model embedding hoặc nội dung file."
        )
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Số embedding ({len(embeddings)}) không khớp số chunk ({len(texts)})."
        )

    ingestion_id = uuid.uuid4().hex
    for metadata in metadatas:
        metadata["ingestion_id"] = ingestion_id
    new_ids = [f"{filename}_{ingestion_id}_chunk_{i}" for i in range(len(texts))]
    try:
        vs._collection.upsert(
            ids=new_ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
    except Exception:
        # Chroma may have accepted part of a request before surfacing an error.
        try:
            vs._collection.delete(ids=new_ids)
        except Exception as rollback_error:
            logger.error(f"Could not roll back new chunks for '{filename}': {rollback_error}")
        raise
    logger.info(f"Added {len(texts)} chunks to vector store for '{filename}'")
    return VectorWriteResult(
        vector_store=vs,
        filename=filename,
        new_ids=new_ids,
        old_ids=old_ids,
        count=len(texts),
    )


def rollback_vector_write(write: VectorWriteResult) -> None:
    """Delete only vectors created by one ingestion attempt."""
    if write.new_ids:
        write.vector_store._collection.delete(ids=write.new_ids)


def finalize_vector_write(write: VectorWriteResult) -> None:
    """Retire an older version only after SQLite/activity have committed."""
    if write.old_ids:
        write.vector_store._collection.delete(ids=write.old_ids)


def page_reviews_for(db: Session, file_path: Path) -> dict[int, PageOverride]:
    """Bản sửa / xác nhận trang của đúng nội dung file này (khóa theo SHA-256). DOCX không có."""
    if file_path.suffix.lower() != ".pdf":
        return {}
    return get_page_overrides(db, sha256_file(file_path))


def reingest_document(
    db: Session,
    document: DocumentMetadata,
    action: str,
    entity_name: str,
    current_user: dict,
    page_reviews: dict[int, PageOverride] | None = None,
    persist=None,
) -> int:
    """Nạp lại một tài liệu đã có sau khi admin sửa/xác nhận trang; trả số đoạn mới.

    Khác process_saved_document: không bao giờ xóa file, không reset reviewed_at. Lỗi ở bất kỳ
    bước nào thì rollback SQLite và xóa đoạn mới, giữ nguyên đoạn cũ. Người gọi phải đang giữ
    _rebuild_lock.

    `page_reviews` (mặc định đọc từ DB) là quyết định *sẽ* có hiệu lực; `persist()` ghi chúng vào DB.
    Mọi request dùng chung một kết nối SQLite (StaticPool), nên không được để thay đổi treo chưa
    commit trong lúc đọc lại tài liệu (có thể hàng phút): request khác commit hộ hoặc rollback mất.
    Vì vậy persist() chỉ chạy sau khi đã ghi chỉ mục, ngay trước commit.
    """
    file_path = Path(document.file_path)
    vector_write: VectorWriteResult | None = None
    try:
        if page_reviews is None:
            page_reviews = page_reviews_for(db, file_path)
        ingestion = load_and_chunk_document(file_path, page_reviews=page_reviews)
        vector_write = add_to_vector_store(ingestion.chunks, document.filename)
        if persist is not None:
            persist()
        document.chunk_count = vector_write.count
        log_activity(
            db, action, "document", entity_name,
            current_user["name"], current_user["role"],
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        if vector_write is not None:
            try:
                rollback_vector_write(vector_write)
            except Exception as rollback_error:
                logger.error("Không thể rollback đoạn mới của '{}': {}", document.filename, rollback_error)
        raise
    try:
        finalize_vector_write(vector_write)
    except Exception as exc:
        logger.warning("Không thể dọn đoạn cũ của '{}': {}", document.filename, exc)
    return vector_write.count


def process_saved_document(
    file_path: Path,
    file_size_kb: float,
    db: Session,
    current_user: dict,
    metadata_values: dict[str, Any] | None = None,
) -> ProcessedDocument:
    """Run CPU ingestion and commit SQLite/activity as one compensating unit."""
    metadata_values = metadata_values or {}
    ingestion: DocumentIngestionResult | None = None
    vector_write: VectorWriteResult | None = None
    try:
        ingestion = load_and_chunk_document(file_path, page_reviews=page_reviews_for(db, file_path))
        vector_write = add_to_vector_store(ingestion.chunks, file_path.name)
        document = add_document_metadata(
            db=db,
            filename=file_path.name,
            file_path=str(file_path),
            file_type=file_path.suffix.lstrip("."),
            chunk_count=vector_write.count,
            file_size_kb=file_size_kb,
            commit=False,
            **metadata_values,
        )
        log_activity(
            db,
            "document_uploaded",
            "document",
            document.display_name or document.filename,
            current_user["name"],
            current_user["role"],
            commit=False,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        if vector_write is not None:
            try:
                rollback_vector_write(vector_write)
            except Exception as rollback_error:
                logger.error(
                    "Không thể rollback vector mới của '{}': {}",
                    file_path.name,
                    rollback_error,
                )
        cache_files = (
            ingestion.created_cache_files
            if ingestion is not None
            else list(getattr(exc, "created_cache_files", []))
        )
        cleanup_new_cache_entries(cache_files)
        # This worker is only used for a newly-saved upload. Removing the file
        # here makes the compensation complete even if a caller forgets its
        # own idempotent cleanup.
        safe_delete_file(file_path)
        raise

    try:
        finalize_vector_write(vector_write)
    except Exception as exc:
        # Upload trùng filename bị chặn 409, nên nhánh này chỉ là phòng vệ.
        # Giữ cả hai version an toàn hơn việc xóa version mới đã có metadata.
        logger.warning("Không thể dọn vector cũ của '{}': {}", file_path.name, exc)
    return ProcessedDocument(
        ingestion=ingestion,
        vector_write=vector_write,
        document=document,
    )


def remove_from_vector_store(filename: str) -> int:
    """
    Xóa tất cả chunks của file khỏi vector store.
    Trả về số chunks đã xóa.
    """
    if _rag_chain is None:
        raise RuntimeError("RAG chain chưa được khởi tạo")

    vs = _rag_chain.vector_store
    if vs is None:
        raise RuntimeError("Vector store chưa sẵn sàng")

    # Tìm tất cả documents của file này
    results = vs._collection.get(
        where={"filename": {"$eq": filename}},
        include=["documents"],
    )
    ids_to_delete = results.get("ids", [])

    if ids_to_delete:
        vs._collection.delete(ids=ids_to_delete)
        logger.info(f"Deleted {len(ids_to_delete)} chunks for '{filename}'")
    else:
        logger.warning(f"No chunks found in vector store for '{filename}'")

    return len(ids_to_delete)


def safe_delete_file(file_path: Path) -> None:
    """Xóa file nếu có thể; không che mất lỗi gốc nếu cleanup thất bại."""
    try:
        if file_path.exists():
            file_path.unlink()
    except PermissionError as exc:
        logger.warning(f"Không thể xóa file tạm '{file_path}': {exc}")
    except OSError as exc:
        logger.warning(f"Lỗi khi xóa file tạm '{file_path}': {exc}")


# ─── Endpoints ────────────────────────────────────────────────────────────────

def _needs_review_page_counts() -> dict[str, int]:
    """Số trang "cần đối chiếu" của mỗi tài liệu, đếm từ metadata đoạn trong chỉ mục."""
    if _rag_chain is None or _rag_chain.vector_store is None:
        return {}
    try:
        result = _rag_chain.vector_store._collection.get(
            where={"review_status": "needs_review"}, include=["metadatas"]
        )
    except Exception as exc:
        logger.warning("Không đếm được trang cần đối chiếu: {}", exc)
        return {}
    pages = {(meta.get("filename"), meta.get("page")) for meta in result.get("metadatas") or [] if meta}
    counts: dict[str, int] = {}
    for filename, _page in pages:
        counts[filename] = counts.get(filename, 0) + 1
    return counts


@router.get("/documents")
def get_documents(db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    """Liệt kê tất cả tài liệu đã nạp vào hệ thống."""
    docs = list_documents(db)
    needs_review = _needs_review_page_counts()
    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "chunk_count": doc.chunk_count,
                "file_size_kb": round(doc.file_size_kb, 2),
                "uploaded_at": doc.uploaded_at.isoformat(),
                "description": doc.description,
                "display_name": doc.display_name,
                "category": doc.category,
                "issuing_unit": doc.issuing_unit,
                "document_year": doc.document_year,
                "summary": doc.summary,
                "status": doc.status or "active",
                "reviewed_at": as_utc_iso(doc.reviewed_at) or None,
                "reviewed_by": doc.reviewed_by,
                "needs_review_pages": needs_review.get(doc.filename, 0),
            }
            for doc in docs
        ],
        "total": len(docs),
    }


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    display_name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    issuing_unit: Optional[str] = Form(None),
    document_year: Optional[int] = Form(None),
    summary: Optional[str] = Form(None),
    status: Optional[str] = Form("active"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    Upload tài liệu PDF/DOCX mới:
    1. Lưu file vào thư mục data/
    2. Load, làm sạch, chunk document
    3. Embed và thêm vào Chroma
    4. Lưu metadata vào SQLite
    """
    safe_filename = normalize_document_filename(file.filename)
    file_ext = Path(safe_filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ chấp nhận file PDF hoặc DOCX. File của bạn: {file_ext}",
        )

    safe_filename, file_path = get_safe_document_path(safe_filename)
    if file_path.exists():
        raise HTTPException(status_code=409, detail="Tài liệu cùng tên đã tồn tại")

    try:
        uploaded_bytes = await save_upload_file(file, file_path, MAX_UPLOAD_BYTES)
        validate_document_content(file_path, file_ext)
        file_size_kb = uploaded_bytes / 1024
        logger.info(f"File saved: {file_path} ({file_size_kb:.1f} KB)")
    except HTTPException:
        safe_delete_file(file_path)
        await file.close()
        raise
    except ValueError as exc:
        safe_delete_file(file_path)
        await file.close()
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as e:
        safe_delete_file(file_path)
        await file.close()
        raise HTTPException(status_code=500, detail=f"Lỗi lưu file: {str(e)}")

    # Xử lý CPU-bound trong worker thread; event loop chỉ điều phối request.
    try:
        processed = await run_in_threadpool(
            partial(
                process_saved_document,
                file_path=file_path,
                file_size_kb=file_size_kb,
                db=db,
                current_user=current_user,
                metadata_values={
                    "description": description,
                    "display_name": display_name,
                    "category": category,
                    "issuing_unit": issuing_unit,
                    "document_year": document_year,
                    "summary": summary,
                    "status": status,
                },
            )
        )

        return {
            "success": True,
            "message": f"Đã nạp thành công '{safe_filename}'",
            "filename": safe_filename,
            "chunk_count": processed.vector_write.count,
            "file_size_kb": round(file_size_kb, 2),
            "warnings": processed.ingestion.warnings,
        }
    except DocumentIngestionError as exc:
        safe_delete_file(file_path)
        logger.warning("Document ingestion rejected {}: {}", safe_filename, exc)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as e:
        safe_delete_file(file_path)
        logger.error(f"Error processing {safe_filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý tài liệu: {str(e)}")
    finally:
        await file.close()


@router.patch("/documents/{filename}")
def update_document(
    filename: str,
    request: DocumentMetadataUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Cập nhật thông tin hiển thị của một tài liệu đã upload."""
    document = update_document_metadata(db, filename, **request.model_dump())
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    log_activity(db, "document_updated", "document", document.display_name or document.filename, current_user["name"], current_user["role"])
    return {"success": True, "filename": document.filename}


def _get_document_or_404(db: Session, filename: str) -> DocumentMetadata:
    safe_filename = normalize_document_filename(filename)
    document = db.query(DocumentMetadata).filter(DocumentMetadata.filename == safe_filename).first()
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    return document


@router.get("/documents/{filename}/chunks")
def get_document_chunks(
    filename: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Các đoạn đã lập chỉ mục của một tài liệu, theo thứ tự nạp, kèm cờ nghi lỗi."""
    document = _get_document_or_404(db, filename)
    if _rag_chain is None or _rag_chain.vector_store is None:
        raise HTTPException(status_code=503, detail="Chỉ mục chưa sẵn sàng")
    chunks = list_document_chunks(_rag_chain.vector_store._collection, document.filename)
    return {
        "filename": document.filename,
        "chunks": chunks,
        "total": len(chunks),
        "flagged": sum(bool(chunk["flags"]) for chunk in chunks),
    }


@router.post("/documents/{filename}/review")
def set_document_review(
    filename: str,
    request: DocumentReviewRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Đánh dấu (hoặc bỏ đánh dấu) tài liệu đã được admin đối chiếu với PDF gốc."""
    document = _get_document_or_404(db, filename)
    document.reviewed_at = datetime.utcnow() if request.reviewed else None
    document.reviewed_by = current_user["email"] if request.reviewed else None
    db.commit()
    return {
        "filename": document.filename,
        "reviewed_at": as_utc_iso(document.reviewed_at) or None,
        "reviewed_by": document.reviewed_by,
    }


# ─── Kiểm tra / sửa từng trang scan ──────────────────────────────────────────

MAX_CORRECTION_CHARS = 20000


class PageCorrectionRequest(BaseModel):
    text: str = Field(..., max_length=MAX_CORRECTION_CHARS)


def _scanned_pdf_path(document: DocumentMetadata, page: int) -> Path:
    """File PDF của tài liệu, sau khi kiểm tra định dạng, sự tồn tại và số trang (đánh số từ 1)."""
    file_path = Path(document.file_path)
    if file_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=422, detail="Chỉ sửa được trang PDF scan")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy file của tài liệu")
    with fitz.open(file_path) as pdf:
        page_count = pdf.page_count
    if not 1 <= page <= page_count:
        raise HTTPException(status_code=404, detail=f"Tài liệu không có trang {page}")
    return file_path


def _index_chunks(filename: str) -> list[dict]:
    if _rag_chain is None or _rag_chain.vector_store is None:
        raise HTTPException(status_code=503, detail="Chỉ mục chưa sẵn sàng")
    return list_document_chunks(_rag_chain.vector_store._collection, filename)


def _page_is_editable(document: DocumentMetadata, file_hash: str, page_index: int, db: Session) -> bool:
    if page_index in get_page_review_rows(db, file_hash):
        return True
    return any(
        chunk["page"] == page_index and chunk["extraction_method"] in EDITABLE_METHODS
        for chunk in _index_chunks(document.filename)
    )


def _read_original_text(file_path: Path, page_index: int) -> str | None:
    try:
        return read_page_ocr_text(file_path, page_index)
    except Exception as exc:  # chỉ để lưu vết; không chặn thao tác của admin
        logger.warning("Không đọc được chữ OCR gốc trang {} của {}: {}", page_index + 1, file_path.name, exc)
        return None


def _apply_page_review(
    filename: str,
    page: int,
    db: Session,
    current_user: dict,
    action: str,
    stage,
) -> int:
    """Kiểm tra, nạp lại tài liệu với quyết định mới, rồi mới ghi page_reviews và commit.

    `stage(file_path, file_hash, page_index, overrides)` sửa `overrides` (bản trong bộ nhớ) theo
    thao tác, hoặc ném HTTPException; nó trả về hàm ghi DB sẽ chạy ngay trước commit.
    Nạp lại lỗi thì không có gì được ghi; đoạn và file cũ giữ nguyên.
    """
    document = _get_document_or_404(db, filename)
    file_path = _scanned_pdf_path(document, page)
    if not _rebuild_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Đang tạo lại chỉ mục, thử lại sau")
    try:
        file_hash = sha256_file(file_path)
        page_index = page - 1
        if not _page_is_editable(document, file_hash, page_index, db):
            raise HTTPException(status_code=422, detail="Chỉ sửa hoặc xác nhận được trang đọc bằng OCR")
        overrides = get_page_overrides(db, file_hash)
        persist = stage(file_path, file_hash, page_index, overrides)
        name = document.display_name or document.filename
        try:
            return reingest_document(
                db, document, action, f"{name} · Tr. {page}", current_user,
                page_reviews=overrides, persist=persist,
            )
        except Exception as exc:
            db.rollback()
            logger.error("Nạp lại '{}' sau thao tác {} thất bại: {}", document.filename, action, exc)
            raise HTTPException(status_code=500, detail="Không thể nạp lại tài liệu; dữ liệu cũ vẫn được giữ")
    finally:
        _rebuild_lock.release()


@router.get("/documents/{filename}/pages")
def get_document_pages(
    filename: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Trạng thái kiểm tra của từng trang (theo các đoạn đang có trong chỉ mục)."""
    document = _get_document_or_404(db, filename)
    file_path = Path(document.file_path)
    reviews = (
        get_page_review_rows(db, sha256_file(file_path))
        if file_path.suffix.lower() == ".pdf" and file_path.is_file()
        else {}
    )
    pages = summarize_pages(_index_chunks(document.filename), reviews)
    for page in pages:
        page["reviewed_at"] = as_utc_iso(page["reviewed_at"]) or None
    return {
        "filename": document.filename,
        "pages": pages,
        "needs_review": sum(page["review_status"] == "needs_review" for page in pages),
    }


@router.get("/documents/{filename}/pages/{page}/text")
def get_page_text(
    filename: str,
    page: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Chữ hiện tại của trang để đưa vào ô sửa: bản sửa nếu có, nếu không thì chữ OCR nguyên trang."""
    document = _get_document_or_404(db, filename)
    file_path = _scanned_pdf_path(document, page)
    review = get_page_review_rows(db, sha256_file(file_path)).get(page - 1)
    if review is not None and review.status == "corrected" and review.corrected_text:
        return {"page": page, "text": review.corrected_text, "source": "correction"}
    try:
        text = read_page_ocr_text(file_path, page - 1)
    except Exception as exc:
        logger.error("Không đọc được chữ OCR trang {} của {}: {}", page, document.filename, exc)
        raise HTTPException(status_code=500, detail="Không đọc được chữ OCR của trang")
    return {"page": page, "text": text, "source": "ocr"}


@router.put("/documents/{filename}/pages/{page}/correction")
def save_page_correction(
    filename: str,
    page: int,
    request: PageCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Thay chữ OCR của trang bằng bản sửa tay, rồi nạp lại tài liệu."""
    text = request.text.strip()
    if sum(character.isalnum() for character in text) < IngestionSettings.from_env().sanity_min_chars:
        raise HTTPException(status_code=422, detail="Bản sửa quá ngắn")

    def stage(file_path: Path, file_hash: str, page_index: int, overrides: dict) -> callable:
        original_text = _read_original_text(file_path, page_index)
        overrides[page_index] = PageOverride("corrected", text)
        return lambda: upsert_page_review(
            db, file_hash, page_index, "corrected", filename=file_path.name,
            reviewed_by=current_user["email"], original_text=original_text, corrected_text=text,
        )

    count = _apply_page_review(filename, page, db, current_user, "page_corrected", stage)
    return {"page": page, "status": "corrected", "chunk_count": count}


def _stage_removal(db: Session, status: str, missing_detail: str):
    """Bỏ quyết định `status` của trang: kiểm tra có tồn tại (404 nếu không) trước khi nạp lại."""
    def stage(_file_path: Path, file_hash: str, page_index: int, overrides: dict) -> callable:
        current = overrides.get(page_index)
        if current is None or current.status != status:
            raise HTTPException(status_code=404, detail=missing_detail)
        del overrides[page_index]
        return lambda: delete_page_review(db, file_hash, page_index, status)
    return stage


@router.delete("/documents/{filename}/pages/{page}/correction")
def remove_page_correction(
    filename: str,
    page: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Bỏ bản sửa tay, quay về chữ OCR, rồi nạp lại tài liệu."""
    count = _apply_page_review(
        filename, page, db, current_user, "page_correction_removed",
        _stage_removal(db, "corrected", "Trang chưa có bản sửa"),
    )
    return {"page": page, "status": None, "chunk_count": count}


@router.put("/documents/{filename}/pages/{page}/confirmation")
def confirm_page(
    filename: str,
    page: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Admin xác nhận chữ OCR của trang là đúng, rồi nạp lại tài liệu để tắt cảnh báo."""
    def stage(file_path: Path, file_hash: str, page_index: int, overrides: dict) -> callable:
        original_text = _read_original_text(file_path, page_index)
        overrides[page_index] = PageOverride("confirmed")
        return lambda: upsert_page_review(
            db, file_hash, page_index, "confirmed", filename=file_path.name,
            reviewed_by=current_user["email"], original_text=original_text,
        )

    count = _apply_page_review(filename, page, db, current_user, "page_confirmed", stage)
    return {"page": page, "status": "confirmed", "chunk_count": count}


@router.delete("/documents/{filename}/pages/{page}/confirmation")
def unconfirm_page(
    filename: str,
    page: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Bỏ xác nhận của trang, rồi nạp lại tài liệu."""
    count = _apply_page_review(
        filename, page, db, current_user, "page_confirmation_removed",
        _stage_removal(db, "confirmed", "Trang chưa được xác nhận"),
    )
    return {"page": page, "status": None, "chunk_count": count}


@router.post("/upload-multiple")
async def upload_multiple_documents(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    Upload nhiều tài liệu PDF/DOCX cùng lúc.
    Trả về kết quả xử lý từng file.
    """
    results = []
    total_success = 0
    total_failed = 0

    batch_bytes = 0

    for file in files:
        original_filename = file.filename or ""
        try:
            safe_filename = normalize_document_filename(original_filename)
        except HTTPException as exc:
            results.append({"filename": original_filename, "success": False, "error": exc.detail})
            total_failed += 1
            await file.close()
            continue

        file_ext = Path(safe_filename).suffix.lower()

        # Kiểm tra định dạng
        if file_ext not in ALLOWED_EXTENSIONS:
            results.append({
                "filename": safe_filename,
                "success": False,
                "error": f"Định dạng không hỗ trợ: {file_ext}",
            })
            total_failed += 1
            await file.close()
            continue

        safe_filename, file_path = get_safe_document_path(safe_filename)
        if file_path.exists():
            results.append({
                "filename": safe_filename,
                "success": False,
                "error": "Tài liệu cùng tên đã tồn tại",
            })
            total_failed += 1
            await file.close()
            continue

        try:
            remaining_batch_bytes = MAX_BATCH_UPLOAD_BYTES - batch_bytes
            if remaining_batch_bytes <= 0:
                raise HTTPException(status_code=413, detail="Tổng dung lượng upload đã vượt giới hạn")
            uploaded_bytes = await save_upload_file(
                file, file_path, min(MAX_UPLOAD_BYTES, remaining_batch_bytes)
            )
            validate_document_content(file_path, file_ext)
            batch_bytes += uploaded_bytes
            file_size_kb = uploaded_bytes / 1024

            processed = await run_in_threadpool(
                partial(
                    process_saved_document,
                    file_path=file_path,
                    file_size_kb=file_size_kb,
                    db=db,
                    current_user=current_user,
                )
            )

            results.append({
                "filename": safe_filename,
                "success": True,
                "chunk_count": processed.vector_write.count,
                "file_size_kb": round(file_size_kb, 2),
                "warnings": processed.ingestion.warnings,
            })
            total_success += 1

        except Exception as e:
            safe_delete_file(file_path)
            logger.error(f"Error processing {safe_filename}: {e}")
            results.append({
                "filename": safe_filename,
                "success": False,
                "error": str(e),
            })
            total_failed += 1
        finally:
            await file.close()

    return {
        "success": total_failed == 0,
        "message": f"Đã xử lý {total_success}/{len(files)} file thành công",
        "total_success": total_success,
        "total_failed": total_failed,
        "results": results,
    }


@router.delete("/delete/{filename}")
def delete_document(
    filename: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    Xóa tài liệu:
    1. Xóa chunks khỏi Chroma vector store
    2. Xóa file khỏi thư mục data/
    3. Xóa metadata khỏi SQLite
    """
    safe_filename, file_path = get_safe_document_path(filename)

    # Kiểm tra file tồn tại
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy file: {safe_filename}",
        )

    try:
        # 1. Xóa khỏi vector store
        deleted_chunks = remove_from_vector_store(safe_filename)

        # 2. Dọn plaintext OCR cache theo SHA-256 trước khi file bị xóa.
        # Cleanup là best-effort và không được làm tài liệu sống lại.
        cleanup_document_cache(file_path)

        # 3. Xóa file
        file_path.unlink()
        logger.info(f"File deleted: {file_path}")

        # 4. Xóa metadata SQLite
        document = db.query(DocumentMetadata).filter_by(filename=safe_filename).first()
        display_name = (document.display_name or document.filename) if document else safe_filename
        remove_document_metadata(db, safe_filename)
        log_activity(db, "document_deleted", "document", display_name, current_user["name"], current_user["role"])

        return {
            "success": True,
            "message": f"Đã xóa thành công '{safe_filename}'",
            "deleted_chunks": deleted_chunks,
        }
    except Exception as e:
        logger.error(f"Error deleting {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi xóa tài liệu: {str(e)}")


@router.post("/rebuild-index")
def rebuild_index(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    Rebuild toàn bộ vector store từ tất cả file trong data/.
    Hữu ích khi cần đồng bộ lại sau sự cố.
    """
    if _rag_chain is None or _rag_chain.vector_store is None:
        raise HTTPException(status_code=500, detail="RAG chain chưa sẵn sàng")

    if not _rebuild_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Hệ thống đang rebuild index. Vui lòng thử lại sau.")

    staging_collection = f"edurag_rebuild_{uuid.uuid4().hex}"
    activated = False
    previous_collection: str | None = None
    keep_staging_for_safety = False
    new_cache_files: list[Path] = []
    try:
        # Build entirely in an isolated collection. The live collection remains
        # queryable until the staging collection has passed validation.
        from rag_chain import get_vector_store

        staging_store = get_vector_store(_rag_chain.embedding_model, staging_collection)
        DATA_PATH.mkdir(parents=True, exist_ok=True)
        all_files = list(DATA_PATH.glob("*.pdf")) + list(DATA_PATH.glob("*.docx"))
        if not all_files:
            raise HTTPException(status_code=422, detail="Không có tài liệu nào để rebuild index")

        total_chunks = 0
        processed_files = []
        chunk_counts = {}
        failures = []

        for file_path in all_files:
            try:
                ingestion = load_and_chunk_document(
                    file_path, page_reviews=page_reviews_for(db, file_path)
                )
                new_cache_files.extend(ingestion.created_cache_files)
                vector_write = add_to_vector_store(
                    ingestion.chunks, file_path.name, staging_store
                )
                total_chunks += vector_write.count
                processed_files.append(file_path.name)
                chunk_counts[file_path.name] = vector_write.count
            except Exception as e:
                new_cache_files.extend(getattr(e, "created_cache_files", []))
                logger.error(f"Error rebuilding {file_path.name}: {e}")
                failures.append({"filename": file_path.name, "error": str(e)})

        if failures:
            raise HTTPException(
                status_code=422,
                detail={"message": "Rebuild bị hủy; index hiện tại vẫn được giữ nguyên", "failures": failures},
            )
        if total_chunks == 0 or staging_store._collection.count() != total_chunks:
            raise RuntimeError("Index tạm không đầy đủ; index hiện tại vẫn được giữ nguyên")

        # Stage SQLite metadata and activity in one transaction. They remain
        # uncommitted while the active collection marker is switched.
        for file_path in all_files:
            file_size_kb = file_path.stat().st_size / 1024
            add_document_metadata(
                db=db,
                filename=file_path.name,
                file_path=str(file_path),
                file_type=file_path.suffix.lstrip("."),
                chunk_count=chunk_counts[file_path.name],
                file_size_kb=file_size_kb,
                commit=False,
            )

        log_activity(
            db, "index_rebuilt", "search_index", f"{len(processed_files)} tài liệu",
            current_user["name"], current_user["role"],
            commit=False,
        )

        previous_collection = _rag_chain.activate_collection(staging_collection)
        activated = True
        db.commit()

        return {
            "success": True,
            "message": "Đã rebuild index thành công",
            "processed_files": processed_files,
            "total_chunks": total_chunks,
            "previous_collection": previous_collection,
        }
    except Exception as e:
        db.rollback()
        if activated and previous_collection:
            try:
                _rag_chain.activate_collection(previous_collection)
                activated = False
            except Exception as rollback_error:
                keep_staging_for_safety = True
                logger.critical(
                    "Không thể khôi phục collection '{}' sau lỗi rebuild: {}",
                    previous_collection,
                    rollback_error,
                )
        cleanup_new_cache_entries(new_cache_files)
        logger.error(f"Error rebuilding index: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Không thể rebuild index; index hiện tại vẫn được giữ nguyên")
    finally:
        if not activated and not keep_staging_for_safety:
            try:
                _rag_chain.vector_store._client.delete_collection(staging_collection)
            except Exception:
                pass
        _rebuild_lock.release()
