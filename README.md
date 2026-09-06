# EduRAG — Chatbot học vụ dùng RAG

EduRAG hỗ trợ sinh viên tra cứu quy chế đào tạo và tài liệu học vụ. Giao diện là React + Vite; FastAPI, ChromaDB và Ollama đảm nhận API và RAG pipeline.

## Kiến trúc

```
React frontend (:3000) → FastAPI (:8000) → RAG / ChromaDB / Ollama (:11434)
                                  └──────→ SQLite (chat_history.db)
```

## Thư mục chính

```
backend/             FastAPI, RAG pipeline và API quản trị
frontend/            React + TypeScript + Vite frontend
data/                Tài liệu nguồn PDF/DOCX
chroma_db/           Vector store được tạo từ tài liệu
scripts/             Lệnh tạo lại chỉ mục vector
```

`chroma_db/` và `chat_history.db` chứa dữ liệu vận hành. Không xóa chúng nếu cần giữ chỉ mục hoặc lịch sử trò chuyện.

## Chạy bằng Docker

Đảm bảo Ollama chạy trên máy host và đã có model `qwen2.5:7b`, sau đó chạy từ thư mục gốc:

```powershell
docker compose up --build -d
```

- Giao diện: `http://localhost:3000`
- FastAPI docs: `http://localhost:8000/docs`

Xem trạng thái:

```powershell
docker compose ps
```

## Chạy để phát triển frontend

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Frontend gọi API tại `http://localhost:8000` theo mặc định.

## Tạo lại chỉ mục RAG

Đặt tài liệu vào `data/`, sau đó:

```powershell
docker compose exec backend python /app/scripts/build_index.py
```
