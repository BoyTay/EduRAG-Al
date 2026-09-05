# 🎓 EduRAG – Chatbot AI Hỗ Trợ Sinh Viên

**EduRAG** là hệ thống chatbot AI sử dụng kỹ thuật **RAG (Retrieval-Augmented Generation)** giúp sinh viên tra cứu quy chế đào tạo, công tác sinh viên và tài liệu nghiệp vụ của Khoa. Hệ thống chạy **hoàn toàn trên máy cục bộ (local)**, không phụ thuộc internet sau khi đã tải model.

---

## 📐 Kiến trúc hệ thống

```
User (Streamlit UI)
       │
       ▼
  Frontend (Streamlit :8501)
       │  HTTP
       ▼
  Backend API (FastAPI :8000)
       │
       ├─► RAG Chain (LangChain)
       │       ├─► Chroma Vector DB (chroma_db/)
       │       │       └─► Embeddings: BAAI/bge-small-vi
       │       └─► LLM: Qwen2.5-7B-Instruct (Ollama :11434)
       │
       └─► SQLite (chat_history.db)
```

---

## 🗂️ Cấu trúc thư mục

```
EduRAG/
│
├── data/                    # Tài liệu nguồn (PDF, DOCX)
├── chroma_db/               # Vector store (tạo tự động)
├── chat_history.db          # SQLite database (tạo tự động)
│
├── backend/
│   ├── main.py              # FastAPI app chính
│   ├── rag_chain.py         # Pipeline RAG
│   ├── db.py                # SQLite models & helpers
│   ├── admin.py             # Router admin (upload/delete)
│   └── requirements.txt     # Dependencies backend
│
├── frontend/
│   ├── app.py               # Streamlit giao diện chat
│   ├── admin_page.py        # Streamlit trang quản trị
│   └── requirements.txt     # Dependencies frontend
│
├── scripts/
│   └── build_index.py       # Script tạo/cập nhật vector store
│
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## ⚙️ Yêu cầu hệ thống

| Thành phần | Yêu cầu |
|---|---|
| OS | Windows 10/11, Ubuntu 20.04+ |
| Python | 3.10+ |
| RAM | Tối thiểu 8GB (khuyến nghị 16GB) |
| GPU | NVIDIA GPU (tùy chọn, tăng tốc embedding) |
| Ollama | Đã cài & pull model `qwen2.5:7b` |
| Docker | Docker Desktop (nếu chạy bằng Docker) |

---

## 🚀 Hướng dẫn cài đặt & chạy

### Cách 1: Chạy thủ công (Recommended for Development)

#### Bước 1: Clone & chuẩn bị môi trường

```bash
# Clone repository
git clone <your-repo-url>
cd EduRAG

# Tạo virtual environment
python -m venv venv

# Kích hoạt venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

#### Bước 2: Cài đặt dependencies

```bash
# Cài backend + frontend (trong cùng venv)
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

#### Bước 3: Kiểm tra Ollama

```bash
# Kiểm tra Ollama đang chạy
ollama list

# Nếu chưa pull model:
ollama pull qwen2.5:7b

# Chạy Ollama (nếu chưa chạy)
ollama serve
```

#### Bước 4: Chuẩn bị tài liệu

```bash
# Đặt file PDF/DOCX vào thư mục data/
mkdir data
# copy your documents to data/
```

#### Bước 5: Tạo vector store lần đầu

```bash
# Từ thư mục gốc dự án
python scripts/build_index.py
```

Lệnh này sẽ:
- Đọc tất cả PDF/DOCX trong `data/`
- Chunk thành đoạn 700 token, overlap 150
- Tạo embedding bằng `BAAI/bge-small-vi`
- Lưu vào `chroma_db/`

> Lần đầu chạy sẽ tự động tải model embedding (~130MB). Cần kết nối internet.

#### Bước 6: Chạy Backend (FastAPI)

```bash
# Terminal 1
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API docs: http://localhost:8000/docs

#### Bước 7: Chạy Frontend (Streamlit)

```bash
# Terminal 2
cd frontend
streamlit run app.py --server.port 8501
```

Giao diện: http://localhost:8501

---

### Cách 2: Chạy bằng Docker Compose

```bash
# Đảm bảo Ollama đang chạy trên host
ollama serve

# Build và chạy tất cả services
docker-compose up --build

# Truy cập:
# Frontend: http://localhost:8501
# Backend API: http://localhost:8000
```

Tạo vector store trong Docker:
```bash
docker-compose exec backend python /app/scripts/build_index.py
```

---

## 🔑 Tài khoản Admin mặc định

- **Password**: `admin123`

---

## 📡 API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| `POST` | `/auth/register` | Đăng ký tài khoản sinh viên |
| `POST` | `/auth/login` | Đăng nhập tài khoản sinh viên |
| `POST` | `/chat` | Gửi câu hỏi, nhận trả lời RAG |
| `GET` | `/history/{session_id}` | Lấy lịch sử hội thoại |
| `GET` | `/admin/documents` | Liệt kê tài liệu đã nạp |
| `POST` | `/admin/upload` | Upload tài liệu mới |
| `DELETE` | `/admin/delete/{filename}` | Xóa tài liệu |
| `POST` | `/admin/rebuild-index` | Rebuild toàn bộ vector store |
| `GET` | `/health` | Health check |

Các API chat, lịch sử và danh sách phiên yêu cầu header `Authorization: Bearer <access_token>`. Mỗi phiên chat được gắn với tài khoản đăng nhập, nên sinh viên chỉ xem được lịch sử của chính mình.

---

## 🧠 Luồng hoạt động RAG

```
1. User nhập câu hỏi
2. Embed câu hỏi → vector (BAAI/bge-small-vi)
3. Tìm kiếm ngữ nghĩa trong Chroma (Top-K=5 chunks)
4. Ghép context từ các chunks tìm được
5. Tạo prompt ChatML → gọi Qwen2.5-7B qua Ollama
6. Trả về câu trả lời + danh sách nguồn
7. Lưu vào SQLite (session_id, question, answer, sources, timestamp)
```

---

## 🐛 Troubleshooting

**Lỗi kết nối Ollama:**
```bash
curl http://localhost:11434/api/tags
# Nếu không có kết quả → chạy: ollama serve
```

**Vector store trống:**
```bash
python scripts/build_index.py --reset
```

---

## 📝 License

MIT License - Dự án đồ án chuyên ngành.
