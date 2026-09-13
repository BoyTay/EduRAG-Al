# EduRAG: Chatbot AI hỗ trợ sinh viên

---

**Trường Đại học Đà Lạt — Khoa Công nghệ Thông tin**

| STT | Họ và tên | MSSV | Lớp | Email liên hệ |
|---|---|---|---|---|
| 1 | Phan Trung Hiếu | 2312616 | CTK47A | 2312616@dlu.edu.vn |
| 2 | Trương Bảo Bảo | 2312582 | CTK47A | 2312582@dlu.edu.vn |
| 3 | Hoàng Trịnh Việt Linh | 2312664 | CTK47A | 2312664@dlu.edu.vn |

**Giáo viên hướng dẫn:** KS. La Quốc Thắng

---

## Tổng quan dự án

EduRAG là chatbot hỗ trợ sinh viên tra cứu quy chế đào tạo, công tác sinh viên và tài liệu nghiệp vụ Khoa. Hệ thống áp dụng kỹ thuật RAG (Retrieval-Augmented Generation) để trả lời câu hỏi dựa hoàn toàn trên tài liệu đã được nạp vào, không tự suy diễn hay dùng kiến thức bên ngoài.

### Công nghệ sử dụng

| Tầng | Công nghệ |
|---|---|
| **Frontend** | React 19, TypeScript, Vite 7, Tailwind CSS 4, React Router DOM 6, Zustand 5, TanStack Query 5, Axios, React Hook Form, Zod |
| **Backend** | Python 3.11, FastAPI 0.115+, Uvicorn, SQLAlchemy 2, Pydantic v2, Loguru |
| **AI / ML** | LangChain 0.3, LangChain-Ollama, Qwen2.5:7b (qua Ollama), `AITeamVN/Vietnamese_Embedding` (HuggingFace), sentence-transformers |
| **Vector DB** | ChromaDB 0.5+ (lưu tại `chroma_db/`) |
| **Database** | SQLite (file `chat_history.db`, ORM qua SQLAlchemy) |
| **Đóng gói** | Docker (multi-stage build), Docker Compose, Nginx 1.27-alpine (serve frontend) |
| **Xác thực** | Bearer token (hash SHA-256 trong SQLite), Google OAuth2 (tuỳ chọn) |

---

## Trạng thái triển khai — cập nhật 10/09/2026

| Giai đoạn | Nội dung chính | Trạng thái |
|---|---|---|
| Nghiên cứu | Xác định công nghệ RAG, chọn embedding tiếng Việt, thiết kế kiến trúc | ✅ Hoàn thành |
| Backend | FastAPI, RAG pipeline, auth, admin API, SQLite | ✅ Hoàn thành |
| Frontend | React + Vite, các trang Chat / Library / Admin / Settings | ✅ Hoàn thành |
| Dữ liệu | Upload PDF/DOCX, chunk, embed, lưu vào Chroma | ✅ Hoàn thành |
| Kiểm thử | Unit test, test RAG thủ công | 📋 Kế hoạch |
| CI/CD | Pipeline tự động, staging environment | 📋 Kế hoạch |
| Tài liệu | Kế hoạch triển khai, hướng dẫn vận hành | 🔄 Đang thực hiện |

### Tiến độ tổng thể

| Hạng mục | Tiến độ |
|---|---|
| Backend & API | 100% |
| Pipeline RAG | 100% |
| Xác thực & phân quyền | 100% |
| Frontend React | 90% |
| Dữ liệu tài liệu | 60% |
| Kiểm thử | 20% |
| Tài liệu & báo cáo | 50% |

---

## Kiến trúc kỹ thuật

### Frontend — React + Vite

Ứng dụng React chạy tại cổng `3000`. Trong môi trường production, Nginx phục vụ bản build tĩnh từ `dist/`. Biến môi trường `VITE_API_URL` trỏ đến backend. Token xác thực được lưu vào `localStorage` (nhớ đăng nhập) hoặc `sessionStorage` (phiên thường). Khi nhận mã 401 từ API, toàn bộ thông tin xác thực bị xoá và người dùng bị chuyển về `/login`.

State toàn cục quản lý bởi Zustand qua hai store:

- `authStore.ts` — token, user, hàm login/logout
- `chatStore.ts` — danh sách session, tin nhắn hiện tại

### Backend — FastAPI

Backend khởi động theo lifespan: khởi tạo SQLite (`init_db`), tạo admin mặc định từ biến môi trường nếu chưa có, nạp embedding model và vector store, sau đó inject `RAGChain` vào admin router. CORS chỉ chấp nhận danh sách origin được khai báo trong `CORS_ORIGINS`, không cho phép wildcard `*`.

### AI Pipeline — RAGChain

`RAGChain` (singleton `rag_chain_instance`) thực hiện pipeline:

1. Nhận câu hỏi, lấy 4 lượt hội thoại gần nhất cùng session để xây dựng retrieval query.
2. Gọi `similarity_search_with_relevance_scores` trên Chroma, lọc theo danh sách file có `status = active`.
3. Nếu không có tài liệu active hoặc `best_score < MIN_RELEVANCE_SCORE` (mặc định 0.42), từ chối và trả thông điệp thay thế.
4. Định dạng context từ top-K chunks, kèm nhãn tài liệu từ SQLite.
5. Gọi Qwen2.5:7b (qua Ollama) với system prompt bắt buộc chỉ dùng tài liệu.
6. Chuẩn hoá output: loại citation lặp (`remove_embedded_citations`), giới hạn 100 từ (`normalize_answer`).
7. Trả về `(answer, sources, avg_score)`.

Retrieval dùng **Maximum Marginal Relevance** khi build chain (`_build_chain`); inference realtime dùng `similarity_search_with_relevance_scores` để lấy score trực tiếp.

### Database — SQLite

Tất cả dữ liệu vận hành lưu trong `chat_history.db`. Các bảng:

| Bảng | Mục đích |
|---|---|
| `chat_history` | Lịch sử hội thoại (session_id, user_id, user_role, sources JSON, retrieval_score, feedback) |
| `document_metadata` | Metadata tài liệu (display_name, category, issuing_unit, document_year, status) |
| `admin_users` | Tài khoản admin (hash PBKDF2-HMAC-SHA256) |
| `student_users` | Tài khoản sinh viên (hash PBKDF2-HMAC-SHA256) |
| `auth_sessions` | Phiên đăng nhập (token_hash SHA-256, expires_at) |
| `password_reset_tokens` | Token đặt lại mật khẩu một lần, hết hạn sau 30 phút |
| `activity_logs` | Nhật ký hành động (upload, delete, rebuild, chat) |

Khi khởi động, `init_db` chạy migration nhẹ để thêm cột mới vào DB cũ (không xoá dữ liệu hiện có).

### Cấu trúc thư mục

```
EduRAG Al/
├── backend/
│   ├── main.py            # FastAPI app, endpoints chính, lifespan
│   ├── rag_chain.py       # RAGChain class, embedding, Chroma
│   ├── admin.py           # Admin router: upload, delete, rebuild-index
│   ├── db.py              # SQLAlchemy models, helper functions
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx        # Định nghĩa routes
│   │   ├── pages/
│   │   │   ├── Chat.tsx
│   │   │   ├── Library.tsx
│   │   │   ├── AdminDashboard.tsx
│   │   │   ├── Settings.tsx
│   │   │   ├── Login.tsx
│   │   │   └── ResetPassword.tsx
│   │   ├── components/
│   │   │   ├── admin/
│   │   │   ├── chat/
│   │   │   ├── library/
│   │   │   ├── sidebar/
│   │   │   ├── common/
│   │   │   └── ui/
│   │   ├── stores/
│   │   │   ├── authStore.ts
│   │   │   └── chatStore.ts
│   │   ├── services/
│   │   │   └── api.ts     # Axios client, tất cả API call
│   │   ├── layouts/
│   │   ├── types/
│   │   └── utils/
│   ├── package.json
│   ├── nginx.conf
│   └── vite.config.ts
├── scripts/
│   ├── build_index.py     # CLI build/reset vector index
│   └── create_sample_doc.py
├── data/                  # Tài liệu nguồn PDF/DOCX
├── chroma_db/             # Vector store (dữ liệu vận hành)
├── chat_history.db        # SQLite database
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Tính năng đã hoàn thành

### Module Chat

- Gửi câu hỏi và nhận câu trả lời từ RAG pipeline
- Truyền `session_id` để duy trì ngữ cảnh hội thoại
- Giới hạn câu hỏi trong một tài liệu cụ thể (`document_filename`)
- Hiển thị nguồn trích dẫn kèm tên tài liệu, đơn vị ban hành, số trang, nhãn nguồn chính (`is_primary`)
- Phản hồi thumbs-up/thumbs-down cho từng câu trả lời
- Tải lịch sử hội thoại theo session, xoá session
- Đưa 4 lượt hội thoại gần nhất vào prompt để giải quyết câu hỏi tiếp nối

### Module Auth

- Đăng ký tài khoản sinh viên (email, mật khẩu tối thiểu 8 ký tự)
- Đăng nhập sinh viên và admin (hai endpoint riêng, cùng flow trả token)
- Đăng nhập bằng Google OAuth2 (xác minh ID token tại `oauth2.googleapis.com`, tạo tài khoản nếu chưa có)
- Quên mật khẩu: gửi link reset qua SMTP (hết hạn sau 30 phút)
- Đặt lại mật khẩu bằng token một lần
- Đăng xuất (thu hồi session trên server)
- Token session có hai thời hạn: 12 giờ (phiên thường) hoặc 30 ngày (nhớ đăng nhập)

### Module Admin

- Xem danh sách tài liệu với đầy đủ metadata
- Upload một tài liệu PDF/DOCX (tối đa 20 MB)
- Upload nhiều tài liệu cùng lúc (tổng tối đa 100 MB)
- Xóa tài liệu (xoá chunks khỏi Chroma, xoá file, xoá metadata SQLite)
- Cập nhật metadata tài liệu (`display_name`, `category`, `issuing_unit`, `document_year`, `summary`, `status`)
- Rebuild toàn bộ vector index từ thư mục `data/` (zero-downtime: build trên collection tạm, kích hoạt sau khi xác minh)
- Xem thống kê hệ thống: tổng tài liệu, tổng chunks, tổng phiên, tổng tin nhắn, lượt feedback
- Xem nhật ký hoạt động gần đây (upload, xoá, rebuild, chat)
- Xem preview tài liệu PDF/DOCX trong trình duyệt (yêu cầu xác thực)

### Module RAG Pipeline

- Tải `AITeamVN/Vietnamese_Embedding` từ HuggingFace, tự động dùng CUDA nếu có GPU
- Phân đoạn tài liệu bằng `RecursiveCharacterTextSplitter` (`chunk_size=700`, `chunk_overlap=150`)
- Lưu chunks vào Chroma với metadata `filename`, `source`, `page`, `ingestion_id`
- Cập nhật tài liệu nguyên tử: ghi chunk mới trước, xoá chunk cũ sau (rollback nếu xoá thất bại)
- Lọc retrieval theo file active hoặc một file được chọn (dùng Chroma `where` filter)
- Từ chối câu hỏi ngoài phạm vi khi `best_score < 0.42`
- Xác định nguồn chính bằng `_support_score` (kết hợp token overlap và cụm 3 từ)
- Thay tên file kỹ thuật bằng nhãn thân thiện trong câu trả lời

### Module Account

- Xem thông tin tài khoản hiện tại
- Cập nhật tên hiển thị
- Đổi mật khẩu (yêu cầu mật khẩu hiện tại)

---

## Luồng hoạt động chính

### Luồng đăng nhập phân quyền

```
Người dùng nhập email + mật khẩu
  → POST /auth/login (sinh viên)
      ├── Nếu thành công → nhận access_token (role: student)
      └── Nếu thất bại → thử POST /admin/login
            ├── Nếu thành công → nhận access_token (role: admin)
            └── Nếu thất bại → báo lỗi đăng nhập

  → Token lưu vào localStorage/sessionStorage (key: edurag_token)
  → Mọi request tiếp theo gửi kèm Authorization: Bearer <token>
  → Backend xác minh token: tìm token_hash trong auth_sessions, kiểm tra expires_at
  → Role trong session quyết định quyền truy cập endpoint
```

### Luồng RAG (câu hỏi → câu trả lời)

```
Sinh viên gửi câu hỏi
  → POST /chat { question, session_id, document_filename? }
  → Backend xác thực token
  → Lấy danh sách file active từ SQLite
  → Lấy tối đa 4 lượt hội thoại gần nhất của session
  → Xây dựng retrieval query (kết hợp câu hỏi + câu hỏi trước nếu có)
  → similarity_search_with_relevance_scores trên Chroma (TOP_K=5)
      ├── Nếu không có file active → trả thông báo từ chối
      ├── Nếu best_score < 0.42 → trả thông báo từ chối
      └── Nếu không tìm được chunk → trả thông báo không có thông tin
  → Format context từ chunks kèm nhãn tài liệu
  → Gọi Qwen2.5:7b qua Ollama (temperature=0.1, num_ctx=4096, num_predict=220)
  → Chuẩn hoá output (loại citation, giới hạn 100 từ)
  → Xác định nguồn chính bằng _support_score
  → Enrich sources từ SQLite (display_name, category, issuing_unit, document_year)
  → Lưu vào chat_history, ghi activity_log
  → Trả ChatResponse { answer, sources, session_id, retrieval_score, message_id }
```

### Luồng upload tài liệu

```
Admin chọn file PDF/DOCX, điền metadata
  → POST /admin/upload (multipart/form-data)
  → Kiểm tra định dạng (.pdf, .docx), giới hạn 20 MB
  → Xác minh nội dung file (magic bytes PDF hoặc cấu trúc ZIP/DOCX)
  → Kiểm tra file cùng tên chưa tồn tại (409 nếu trùng)
  → Lưu file vào data/ (ghi qua file tạm, rename nguyên tử)
  → Load bằng PyMuPDF (PDF) hoặc Docx2txt (DOCX)
  → Làm sạch text (chuẩn hoá khoảng trắng, loại null bytes, bỏ trang < 50 ký tự)
  → Chunk bằng RecursiveCharacterTextSplitter (size=700, overlap=150)
  → Embed và ghi vào Chroma (upsert với ingestion_id mới, xoá chunk cũ)
  → Lưu metadata vào SQLite
  → Ghi activity_log (document_uploaded)
  → Trả kết quả { filename, chunk_count, file_size_kb }
  Rollback: nếu bất kỳ bước nào thất bại → xoá file đã lưu
```

---

## Thông số kỹ thuật quan trọng

| Tham số | Giá trị | Nguồn cấu hình |
|---|---|---|
| `LLM_MODEL` | `qwen2.5:7b` | biến môi trường / docker-compose |
| `EMBEDDING_MODEL` | `AITeamVN/Vietnamese_Embedding` | biến môi trường / docker-compose |
| `CHUNK_SIZE` | `700` ký tự | `CHUNK_SIZE` env, mặc định trong `admin.py` |
| `CHUNK_OVERLAP` | `150` ký tự | `CHUNK_OVERLAP` env, mặc định trong `admin.py` |
| `TOP_K` | `5` | `TOP_K` env, mặc định trong `rag_chain.py` |
| `MIN_RELEVANCE_SCORE` | `0.42` | `MIN_RELEVANCE_SCORE` env |
| `temperature` | `0.1` | hard-coded trong `RAGChain.initialize()` |
| `num_ctx` | `4096` | hard-coded trong `RAGChain.initialize()` |
| `num_predict` | `220` | hard-coded trong `RAGChain.initialize()` |
| `top_p` | `0.9` | hard-coded trong `RAGChain.initialize()` |
| `repeat_penalty` | `1.1` | hard-coded trong `RAGChain.initialize()` |
| Câu trả lời tối đa | `100` từ | `normalize_answer(max_words=100)` |
| Lượt hội thoại đưa vào context | `4` lượt | `MAX_CONVERSATION_TURNS = 4` |
| Kích thước context hội thoại | `3 500` ký tự | `MAX_CONVERSATION_CHARS = 3_500` |
| Token session thường | `12 giờ` | `create_auth_session`, `timedelta(hours=12)` |
| Token session nhớ đăng nhập | `30 ngày` | `create_auth_session`, `timedelta(days=30)` |
| Token reset mật khẩu | `30 phút` | `create_password_reset_token` |
| Upload tối đa mỗi file | `20 MB` | `MAX_UPLOAD_BYTES` env |
| Upload batch tối đa | `100 MB` | `MAX_BATCH_UPLOAD_BYTES` env |
| MMR lambda_mult | `0.7` | `_build_chain` trong `RAGChain` |
| fetch_k (MMR) | `TOP_K x 3 = 15` | `_build_chain` trong `RAGChain` |
| Chroma collection | `edurag_docs` | `COLLECTION_NAME` trong `rag_chain.py` |
| Chroma path | `/app/chroma_db` | `CHROMA_PATH` env |
| Data path | `/app/data` | `DATA_PATH` env |
| Backend port | `8000` | docker-compose |
| Frontend port | `3000` | docker-compose, package.json |
| Ollama URL | `http://host.docker.internal:11434` | docker-compose |

---

## API Endpoints

### Xác thực (`/auth`)

| Method | Endpoint | Quyền | Chức năng |
|---|---|---|---|
| POST | `/auth/register` | Công khai | Đăng ký tài khoản sinh viên |
| POST | `/auth/login` | Công khai | Đăng nhập sinh viên |
| POST | `/admin/login` | Công khai | Đăng nhập admin |
| GET | `/auth/providers` | Công khai | Lấy cấu hình Google OAuth |
| POST | `/auth/google` | Công khai | Đăng nhập bằng Google ID token |
| POST | `/auth/forgot-password` | Công khai | Gửi link đặt lại mật khẩu |
| POST | `/auth/reset-password` | Công khai | Đặt lại mật khẩu bằng token |
| POST | `/auth/logout` | Đã đăng nhập | Thu hồi session |

### Hội thoại (`/chat`, `/history`, `/sessions`)

| Method | Endpoint | Quyền | Chức năng |
|---|---|---|---|
| POST | `/chat` | Đã đăng nhập | Gửi câu hỏi, nhận câu trả lời RAG |
| POST | `/chat/{message_id}/feedback` | Đã đăng nhập | Lưu feedback up/down |
| GET | `/history/{session_id}` | Đã đăng nhập | Lấy lịch sử một phiên |
| GET | `/sessions` | Đã đăng nhập | Danh sách phiên của tài khoản |
| DELETE | `/sessions/{session_id}` | Đã đăng nhập | Xoá một phiên và tin nhắn |

### Tài khoản (`/account`)

| Method | Endpoint | Quyền | Chức năng |
|---|---|---|---|
| GET | `/account` | Đã đăng nhập | Thông tin tài khoản hiện tại |
| PATCH | `/account/profile` | Đã đăng nhập | Cập nhật tên hiển thị |
| POST | `/account/password` | Đã đăng nhập | Đổi mật khẩu |

### Tài liệu và admin

| Method | Endpoint | Quyền | Chức năng |
|---|---|---|---|
| GET | `/admin/documents` | Công khai | Danh sách tài liệu và metadata |
| POST | `/admin/upload` | Admin | Upload một tài liệu PDF/DOCX |
| POST | `/admin/upload-multiple` | Admin | Upload nhiều tài liệu cùng lúc |
| PATCH | `/admin/documents/{filename}` | Admin | Cập nhật metadata tài liệu |
| DELETE | `/admin/delete/{filename}` | Admin | Xoá tài liệu |
| POST | `/admin/rebuild-index` | Admin | Rebuild toàn bộ vector index |
| GET | `/admin/stats` | Admin | Thống kê hệ thống và uptime |
| GET | `/admin/activities` | Admin | Nhật ký hoạt động (tối đa 100) |
| GET | `/documents/{filename}/preview` | Đã đăng nhập | Xem preview PDF/DOCX |
| GET | `/health` | Công khai | Kiểm tra trạng thái backend |

---

## Kế hoạch triển khai tiếp theo

| Giai đoạn | Công việc | Đầu ra | Ưu tiên | Thời lượng dự kiến | Tiêu chí nghiệm thu |
|---|---|---|---|---|---|
| T1 | Viết test case RAG thủ công (câu hỏi có đáp án, câu ngoài phạm vi, câu tiếp nối, tài liệu inactive) | Tập test case kèm kết quả dự kiến | Cao | 3-5 ngày | Tập test được xác nhận, có dữ liệu đầu vào và kết quả mong đợi |
| T2 | Cấu hình SMTP và kiểm thử flow quên mật khẩu | Email reset hoạt động đầu cuối | Cao | 1-2 ngày | Nhận email trong 1 phút, link hết hạn đúng 30 phút |
| T3 | Thêm phân trang danh sách session (hiện giới hạn 30) | Endpoint `/sessions` có `?page` hoặc cursor | Trung bình | 1-2 ngày | Sinh viên có hơn 30 phiên vẫn thấy đầy đủ |
| T4 | Tích hợp PaddleOCR cho PDF scan | Upload PDF scan tạo ra chunk có nội dung | Trung bình | 5-7 ngày | PDF scan 5 trang trich xuất duoc toi thieu 80% van ban |
| T5 | Viết unit test cho `normalize_answer`, `_support_score`, `format_conversation_history` | Pytest suite chạy trong CI | Trung bình | 2-3 ngày | Tất cả test pass, coverage ≥ 70% trên ba hàm đó |
| T6 | Bổ sung lọc tài liệu theo category, đơn vị ban hành, năm | Filter UI trên trang Library | Thấp | 3-4 ngày | Admin lọc được theo category, kết quả chính xác |
| T7 | Cấu hình CI pipeline (GitHub Actions hoặc tương đương) | Build + test tự động khi push | Thấp | 2-3 ngày | Pipeline xanh trên nhánh main |

---

## Hướng mở rộng

### Tích hợp PaddleOCR cho PDF scan

Hiện tại, `load_and_chunk_document` trong `admin.py` dùng `PyMuPDFLoader` để đọc text layer của PDF. Khi gặp PDF chỉ chứa ảnh (scan), loader trả về text rỗng và hệ thống từ chối với thông báo:

> `"Không trích xuất được văn bản từ '...'. File có thể là PDF scan/ảnh hoặc không chứa text đọc được."`

Để hỗ trợ PDF scan, thêm bước fallback trong `load_and_chunk_document`:

1. Gọi PyMuPDFLoader trước.
2. Nếu kết quả rỗng hoặc tổng ký tự quá ít, chuyển sang PaddleOCR để nhận diện văn bản từng trang.
3. Chuẩn hoá output OCR về định dạng `Document` của LangChain, sau đó đưa vào pipeline chunking như bình thường.

Cần cân nhắc: PaddleOCR tăng thời gian xử lý đáng kể và yêu cầu cài thêm gói `paddleocr`, `paddlepaddle`. Nên chạy OCR trong background task hoặc worker riêng để không block API.

### Danh mục tài liệu với metadata đầy đủ

Model `DocumentMetadata` đã có các cột `display_name`, `category`, `issuing_unit`, `document_year`, `summary` và `status`. Hướng mở rộng tiếp theo:

- Bổ sung filter UI trên trang Library để lọc theo `category` và `issuing_unit`.
- Cho phép admin nhập `summary` khi upload để hiển thị mô tả ngắn trước khi xem preview.
- Thêm trường `effective_date` (ngày hiệu lực) và `expiry_date` (ngày hết hiệu lực) để hệ thống tự quản lý `status` theo thời gian.
- Bổ sung endpoint tìm kiếm văn bản toàn văn trên `display_name` và `summary` trong SQLite để sinh viên tìm tài liệu nhanh hơn.

---

## Hướng dẫn chạy dự án

### Yêu cầu

- Docker Desktop (Linux containers)
- Ollama đang chạy trên máy host với model `qwen2.5:7b` đã được kéo về:

```powershell
ollama pull qwen2.5:7b
```

### Cấu hình môi trường

```powershell
# Sao chép file mẫu
Copy-Item .env.example .env

# Mở và điền các giá trị bắt buộc:
#   ADMIN_USERNAME  — tên đăng nhập admin (bắt buộc khi tạo DB mới)
#   ADMIN_PASSWORD  — mật khẩu tối thiểu 12 ký tự (bắt buộc khi tạo DB mới)
#   CORS_ORIGINS    — mặc định http://localhost:3000
```

Các biến tuỳ chọn trong `.env`:

| Biến | Mô tả |
|---|---|
| `GOOGLE_CLIENT_ID` | Bật đăng nhập Google OAuth2 |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Gửi email đặt lại mật khẩu |
| `FRONTEND_URL` | URL frontend dùng trong link email (mặc định `http://localhost:3000`) |
| `MIN_RELEVANCE_SCORE` | Ngưỡng từ chối RAG (mặc định `0.42`) |

### Khởi động bằng Docker Compose

```powershell
# Build và khởi động toàn bộ hệ thống
docker compose up --build -d

# Theo dõi log
docker compose logs -f

# Kiểm tra trạng thái
docker compose ps
```

- Giao diện web: `http://localhost:3000`
- API docs (Swagger): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Dừng và xoá container

```powershell
# Dừng nhưng giữ volume
docker compose down

# Dừng và xoá toàn bộ (bao gồm volume embedding model cache)
docker compose down -v
```

### Nạp tài liệu vào hệ thống

**Cách 1 — Upload qua giao diện admin (khuyến nghị):**

Đăng nhập với tài khoản admin, chuyển sang tab Thư viện, nhấn "Tải lên tài liệu", chọn file PDF/DOCX.

**Cách 2 — Chạy script build_index.py:**

```powershell
# Đặt file PDF/DOCX vào thư mục data/, sau đó:
docker compose exec backend python /app/scripts/build_index.py

# Chỉ xử lý một file cụ thể
docker compose exec backend python /app/scripts/build_index.py --file "quy_che_dao_tao.pdf"

# Xoá và tạo lại toàn bộ index (cẩn thận: xoá dữ liệu Chroma hiện tại)
docker compose exec backend python /app/scripts/build_index.py --reset
```

**Cách 3 — Rebuild qua API admin (zero-downtime):**

```powershell
# Rebuild trong collection tạm, chỉ kích hoạt sau khi xác minh thành công
curl -X POST http://localhost:8000/admin/rebuild-index -H "Authorization: Bearer <admin_token>"
```

### Chạy frontend riêng để phát triển

```powershell
cd frontend
Copy-Item .env.example .env   # VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

Frontend dev server chạy tại `http://localhost:3000`, tự reload khi sửa code.

### Biến môi trường Docker Compose (tham khảo nhanh)

| Biến | Mặc định trong Compose | Ghi chú |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Trỏ đến Ollama trên máy host |
| `LLM_MODEL` | `qwen2.5:7b` | Phải có sẵn trong Ollama |
| `EMBEDDING_MODEL` | `AITeamVN/Vietnamese_Embedding` | Tự động tải về từ HuggingFace |
| `VITE_API_URL` (build arg) | `http://localhost:8000` | URL backend mà trình duyệt gọi |
| `CHROMA_PATH` | `/app/chroma_db` | Mount vào `./chroma_db` trên host |
| `DATA_PATH` | `/app/data` | Mount vào `./data` trên host |

Volume `hf_cache` (tên `edurag_hf_cache`) cache model embedding để tránh tải lại mỗi lần khởi động container.

---

## Lưu ý

- Số liệu đo chất lượng RAG (precision, recall, độ trễ) chưa có; cần chạy tập test trên tài liệu thực trước khi báo cáo.
- Cấu hình SMTP chưa được kiểm thử thực tế; xác minh flow quên mật khẩu trước khi công bố cho sinh viên.
- Đăng nhập Google cần Google Client ID từ Google Cloud Console; điền vào `.env` trước khi bật tính năng này.
- Danh sách tài liệu đang nạp trong `data/` và `chroma_db/` cần được thống kê bổ sung vào phần Dữ liệu khi hoàn thiện.
