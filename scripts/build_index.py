"""
build_index.py - Script tạo/cập nhật vector store từ thư mục data/

Cách dùng:
    python scripts/build_index.py           # Tạo index (skip file đã có)
    python scripts/build_index.py --reset   # Xóa và tạo lại toàn bộ index
    python scripts/build_index.py --file "ten_file.pdf"  # Chỉ xử lý 1 file
"""

import argparse
import os
import sys
import shutil
from pathlib import Path

# Thêm thư mục backend vào PYTHONPATH
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

import torch
from langchain_community.document_loaders import PyMuPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from loguru import logger

# ─── Cấu hình ─────────────────────────────────────────────────────────────────
DATA_PATH = ROOT_DIR / "data"
CHROMA_PATH = ROOT_DIR / "chroma_db"
# Model embedding tiếng Việt:
# - "AITeamVN/Vietnamese_Embedding" (~560MB) - khuyen nghi
# - "BAAI/bge-m3" (~2.3GB) - tot nhat nhung nang hon
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "AITeamVN/Vietnamese_Embedding")
COLLECTION_NAME = "edurag_docs"
CHUNK_SIZE = 700
CHUNK_OVERLAP = 150

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


def get_device() -> str:
    """Phát hiện GPU khả dụng."""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"🎮 GPU detected: {gpu_name} — using CUDA")
        return "cuda"
    logger.info("💻 No GPU detected — using CPU")
    return "cpu"


def load_embedding_model() -> HuggingFaceEmbeddings:
    """Tải model embedding BAAI/bge-small-vi."""
    device = get_device()
    logger.info(f"📥 Loading embedding model: {EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
    )


def load_document(file_path: Path) -> list:
    """Đọc file PDF hoặc DOCX, trả về list Documents."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        loader = PyMuPDFLoader(str(file_path))
    elif ext == ".docx":
        loader = Docx2txtLoader(str(file_path))
    else:
        logger.warning(f"Skipping unsupported file: {file_path.name}")
        return []

    docs = loader.load()
    logger.info(f"  📄 Loaded: {file_path.name} ({len(docs)} pages)")
    return docs


def clean_documents(docs: list, file_path: Path) -> list:
    """Làm sạch text và gắn metadata cho documents."""
    cleaned = []
    for doc in docs:
        text = doc.page_content
        text = " ".join(text.split())       # Normalize whitespace
        text = text.replace("\x00", "")     # Loại null bytes
        if len(text.strip()) < 50:          # Bỏ qua trang quá ngắn
            continue
        doc.page_content = text
        doc.metadata["source"] = str(file_path)
        doc.metadata["filename"] = file_path.name
        cleaned.append(doc)
    return cleaned


def chunk_documents(docs: list) -> list:
    """Phân đoạn documents thành chunks nhỏ hơn."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ".", ";", ":", " ", ""],
    )
    return splitter.split_documents(docs)


def process_file(file_path: Path, vector_store: Chroma, existing_filenames: set) -> int:
    """
    Xử lý một file: load → clean → chunk → embed → add to vector store.
    Trả về số chunks đã thêm.
    """
    if file_path.name in existing_filenames:
        logger.info(f"  ⏭️  Skipping (already indexed): {file_path.name}")
        return 0

    # Load
    docs = load_document(file_path)
    if not docs:
        return 0

    # Clean
    docs = clean_documents(docs, file_path)
    if not docs:
        logger.warning(f"  ⚠️  No valid content found in: {file_path.name}")
        return 0

    # Chunk
    chunks = chunk_documents(docs)
    logger.info(f"  ✂️  Chunked: {len(chunks)} chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    # Add to vector store với unique IDs
    ids = [f"{file_path.name}_chunk_{i}" for i in range(len(chunks))]
    vector_store.add_documents(documents=chunks, ids=ids)
    logger.info(f"  ✅ Indexed: {file_path.name} → {len(chunks)} chunks")
    return len(chunks)


def get_indexed_filenames(vector_store: Chroma) -> set:
    """Lấy danh sách tên file đã được index trong vector store."""
    try:
        result = vector_store._collection.get(include=["metadatas"])
        metadatas = result.get("metadatas", [])
        return {m.get("filename", "") for m in metadatas if m}
    except Exception:
        return set()


def main():
    parser = argparse.ArgumentParser(
        description="Tạo/cập nhật vector store cho EduRAG"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Xóa và tạo lại toàn bộ vector store",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Chỉ xử lý một file cụ thể (tên file trong data/)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🎓 EduRAG — Build Index Script")
    logger.info("=" * 60)

    # Kiểm tra thư mục data
    if not DATA_PATH.exists():
        DATA_PATH.mkdir(parents=True)
        logger.warning(f"📁 Created empty data directory: {DATA_PATH}")
        logger.warning("Vui lòng đặt file PDF/DOCX vào thư mục data/ và chạy lại.")
        sys.exit(0)

    # Lấy danh sách file cần xử lý
    if args.file:
        target_file = DATA_PATH / args.file
        if not target_file.exists():
            logger.error(f"File không tồn tại: {target_file}")
            sys.exit(1)
        files_to_process = [target_file]
    else:
        files_to_process = (
            list(DATA_PATH.glob("*.pdf")) +
            list(DATA_PATH.glob("*.docx"))
        )

    if not files_to_process:
        logger.warning("⚠️  Không tìm thấy file PDF/DOCX trong thư mục data/")
        logger.info("Hãy đặt tài liệu vào thư mục data/ rồi chạy lại script này.")
        sys.exit(0)

    logger.info(f"📂 Data directory: {DATA_PATH}")
    logger.info(f"📊 Files to process: {len(files_to_process)}")
    for f in files_to_process:
        logger.info(f"   - {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    # Reset nếu cần
    if args.reset and CHROMA_PATH.exists():
        logger.warning("🗑️  Deleting existing vector store...")
        shutil.rmtree(CHROMA_PATH)
        logger.info("Vector store deleted.")

    # Tạo thư mục chroma_db
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)

    # Load embedding model
    logger.info("\n" + "─" * 40)
    embedding_model = load_embedding_model()

    # Kết nối/tạo vector store
    logger.info(f"🗄️  Connecting to Chroma: {CHROMA_PATH}")
    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedding_model,
        persist_directory=str(CHROMA_PATH),
    )

    initial_count = vector_store._collection.count()
    logger.info(f"📈 Current documents in store: {initial_count}")

    # Lấy danh sách file đã index
    existing_filenames = get_indexed_filenames(vector_store)
    if existing_filenames:
        logger.info(f"🔍 Already indexed: {existing_filenames}")

    # Xử lý từng file
    logger.info("\n" + "─" * 40)
    logger.info("📝 Processing documents...")
    total_chunks = 0
    processed_count = 0

    for file_path in files_to_process:
        logger.info(f"\n📄 Processing: {file_path.name}")
        chunks_added = process_file(file_path, vector_store, existing_filenames)
        total_chunks += chunks_added
        if chunks_added > 0:
            processed_count += 1

    # Kết quả
    final_count = vector_store._collection.count()
    logger.info("\n" + "=" * 60)
    logger.info("✅ Build index completed!")
    logger.info(f"   📁 Files processed: {processed_count}/{len(files_to_process)}")
    logger.info(f"   📊 Chunks added: {total_chunks}")
    logger.info(f"   📈 Total documents in store: {final_count}")
    logger.info(f"   💾 Saved to: {CHROMA_PATH}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
