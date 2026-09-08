"""
admin.py - Router quản trị tài liệu
Cung cấp endpoints để upload, xóa tài liệu và cập nhật vector store.
"""

import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger

from db import DocumentMetadata, get_db, add_document_metadata, remove_document_metadata, list_documents, update_document_metadata, get_auth_session, log_activity

# ─── Cấu hình ─────────────────────────────────────────────────────────────────
DATA_PATH = Path(os.getenv("DATA_PATH", str(Path(__file__).parent.parent / "data")))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "700"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
ALLOWED_EXTENSIONS = {".pdf", ".docx"}

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
) -> dict:
    """Bảo vệ thao tác quản trị tài liệu và dùng actor cho nhật ký."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập để tiếp tục")
    session = get_auth_session(db, authorization.removeprefix("Bearer ").strip())
    if not session or session.user_role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên được phép thực hiện")
    return {"name": session.email, "role": session.user_role}


class DocumentMetadataUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=80)
    issuing_unit: Optional[str] = Field(None, max_length=150)
    document_year: Optional[int] = Field(None, ge=1900, le=2100)
    summary: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, max_length=30)

# Import rag_chain_instance sẽ được inject sau
_rag_chain = None


def set_rag_chain(chain):
    """Inject RAG chain instance từ main.py."""
    global _rag_chain
    _rag_chain = chain


# ─── Helper: Load & Chunk document ───────────────────────────────────────────

def load_and_chunk_document(file_path: Path) -> list:
    """
    Đọc file PDF hoặc DOCX, làm sạch text, phân đoạn thành chunks.
    Trả về list các LangChain Document objects.
    """
    from langchain_community.document_loaders import PyMuPDFLoader, Docx2txtLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    ext = file_path.suffix.lower()

    # Load document
    if ext == ".pdf":
        loader = PyMuPDFLoader(str(file_path))
    elif ext == ".docx":
        loader = Docx2txtLoader(str(file_path))
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    docs = loader.load()
    logger.info(f"Loaded {len(docs)} pages from {file_path.name}")
    if not docs:
        raise ValueError(
            f"Không trích xuất được văn bản từ '{file_path.name}'. "
            "File có thể là PDF scan/ảnh hoặc không chứa text đọc được."
        )

    # Làm sạch text
    for doc in docs:
        # Chuẩn hóa khoảng trắng và ký tự đặc biệt
        text = doc.page_content
        text = " ".join(text.split())          # Normalize whitespace
        text = text.replace("\x00", "")        # Loại null bytes
        doc.page_content = text
        # Thêm filename vào metadata
        doc.metadata["source"] = str(file_path)
        doc.metadata["filename"] = file_path.name

    # Lọc bỏ các trang rỗng
    docs = [d for d in docs if len(d.page_content.strip()) > 50]
    if not docs:
        raise ValueError(
            f"Không có trang nào chứa đủ văn bản hợp lệ trong '{file_path.name}'. "
            "Nếu đây là PDF scan, cần OCR trước khi upload."
        )

    # Phân đoạn (chunking)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ".", ";", ":", " ", ""],
    )
    chunks = text_splitter.split_documents(docs)
    logger.info(
        f"Chunked {file_path.name}: {len(docs)} pages → {len(chunks)} chunks "
        f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})"
    )
    if not chunks:
        raise ValueError(
            f"Không tạo được chunk nào từ '{file_path.name}'. "
            "Vui lòng thử file khác hoặc giảm mức làm sạch văn bản."
        )
    return chunks


def add_to_vector_store(chunks: list, filename: str) -> None:
    """Thêm chunks vào Chroma vector store."""
    if _rag_chain is None:
        raise RuntimeError("RAG chain chưa được khởi tạo")

    vs = _rag_chain.vector_store
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

    ids = [f"{filename}_chunk_{i}" for i in range(len(texts))]
    vs._collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    logger.info(f"Added {len(texts)} chunks to vector store for '{filename}'")


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

@router.get("/documents")
def get_documents(db: Session = Depends(get_db)):
    """Liệt kê tất cả tài liệu đã nạp vào hệ thống."""
    docs = list_documents(db)
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
    # Kiểm tra định dạng file
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ chấp nhận file PDF hoặc DOCX. File của bạn: {file_ext}",
        )

    # Đảm bảo thư mục data tồn tại
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    file_path = DATA_PATH / file.filename

    # Lưu file
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        file_size_kb = len(content) / 1024
        logger.info(f"File saved: {file_path} ({file_size_kb:.1f} KB)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu file: {str(e)}")

    # Xử lý document
    try:
        chunks = load_and_chunk_document(file_path)
        add_to_vector_store(chunks, file.filename)

        # Cập nhật metadata trong SQLite
        document = add_document_metadata(
            db=db,
            filename=file.filename,
            file_path=str(file_path),
            file_type=file_ext.lstrip("."),
            chunk_count=len(chunks),
            file_size_kb=file_size_kb,
            description=description,
            display_name=display_name,
            category=category,
            issuing_unit=issuing_unit,
            document_year=document_year,
            summary=summary,
            status=status,
        )
        log_activity(db, "document_uploaded", "document", document.display_name or document.filename, current_user["name"], current_user["role"])

        return {
            "success": True,
            "message": f"Đã nạp thành công '{file.filename}'",
            "filename": file.filename,
            "chunk_count": len(chunks),
            "file_size_kb": round(file_size_kb, 2),
        }
    except Exception as e:
        # Rollback: xóa file nếu xử lý lỗi
        safe_delete_file(file_path)
        logger.error(f"Error processing {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý tài liệu: {str(e)}")


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

    DATA_PATH.mkdir(parents=True, exist_ok=True)

    for file in files:
        file_ext = Path(file.filename).suffix.lower()

        # Kiểm tra định dạng
        if file_ext not in ALLOWED_EXTENSIONS:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": f"Định dạng không hỗ trợ: {file_ext}",
            })
            total_failed += 1
            continue

        file_path = DATA_PATH / file.filename

        try:
            # Lưu file
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            file_size_kb = len(content) / 1024

            # Xử lý
            chunks = load_and_chunk_document(file_path)
            add_to_vector_store(chunks, file.filename)

            # Metadata
            document = add_document_metadata(
                db=db,
                filename=file.filename,
                file_path=str(file_path),
                file_type=file_ext.lstrip("."),
                chunk_count=len(chunks),
                file_size_kb=file_size_kb,
            )
            log_activity(db, "document_uploaded", "document", document.display_name or document.filename, current_user["name"], current_user["role"])

            results.append({
                "filename": file.filename,
                "success": True,
                "chunk_count": len(chunks),
                "file_size_kb": round(file_size_kb, 2),
            })
            total_success += 1

        except Exception as e:
            safe_delete_file(file_path)
            logger.error(f"Error processing {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e),
            })
            total_failed += 1

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
    file_path = DATA_PATH / filename

    # Kiểm tra file tồn tại
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy file: {filename}",
        )

    try:
        # 1. Xóa khỏi vector store
        deleted_chunks = remove_from_vector_store(filename)

        # 2. Xóa file
        file_path.unlink()
        logger.info(f"File deleted: {file_path}")

        # 3. Xóa metadata SQLite
        document = db.query(DocumentMetadata).filter_by(filename=filename).first()
        display_name = (document.display_name or document.filename) if document else filename
        remove_document_metadata(db, filename)
        log_activity(db, "document_deleted", "document", display_name, current_user["name"], current_user["role"])

        return {
            "success": True,
            "message": f"Đã xóa thành công '{filename}'",
            "deleted_chunks": deleted_chunks,
        }
    except Exception as e:
        logger.error(f"Error deleting {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi xóa tài liệu: {str(e)}")


@router.post("/rebuild-index")
def rebuild_index(db: Session = Depends(get_db)):
    """
    Rebuild toàn bộ vector store từ tất cả file trong data/.
    Hữu ích khi cần đồng bộ lại sau sự cố.
    """
    if _rag_chain is None:
        raise HTTPException(status_code=500, detail="RAG chain chưa sẵn sàng")

    try:
        # Xóa collection cũ
        vs = _rag_chain.vector_store
        vs._client.delete_collection(vs._collection.name)
        logger.info("Old collection deleted")

        # Tải lại tất cả tài liệu
        DATA_PATH.mkdir(parents=True, exist_ok=True)
        all_files = list(DATA_PATH.glob("*.pdf")) + list(DATA_PATH.glob("*.docx"))

        total_chunks = 0
        processed_files = []

        for file_path in all_files:
            try:
                chunks = load_and_chunk_document(file_path)
                add_to_vector_store(chunks, file_path.name)
                total_chunks += len(chunks)
                processed_files.append(file_path.name)

                # Cập nhật metadata
                file_size_kb = file_path.stat().st_size / 1024
                add_document_metadata(
                    db=db,
                    filename=file_path.name,
                    file_path=str(file_path),
                    file_type=file_path.suffix.lstrip("."),
                    chunk_count=len(chunks),
                    file_size_kb=file_size_kb,
                )
            except Exception as e:
                logger.error(f"Error rebuilding {file_path.name}: {e}")

        # Reload vector store instance
        _rag_chain.reload_vector_store()

        return {
            "success": True,
            "message": f"Đã rebuild index thành công",
            "processed_files": processed_files,
            "total_chunks": total_chunks,
        }
    except Exception as e:
        logger.error(f"Error rebuilding index: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi rebuild index: {str(e)}")
