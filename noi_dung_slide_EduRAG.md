# Nội dung Slide Thuyết Trình — EduRAG
> **Tổng thời gian:** 10 phút | **Công cụ:** PowerPoint / Google Slides
> **Nguồn:** Trích xuất trực tiếp từ source code — mọi số liệu đều có thể kiểm chứng.

---

## Slide 1 — Giới thiệu
> ⏱️ **Thời gian trình bày: ~30 giây**

**Tiêu đề:**
# EduRAG — Chatbot AI Hỗ Trợ Sinh Viên Tra Cứu Quy Chế Đào Tạo

**Nội dung:**
- 📌 **Tên đồ án:** EduRAG — Educational Retrieval-Augmented Generation
- 👥 **Thành viên:** *(để trống — điền thêm)*
- 👨‍🏫 **GVHD:** *(để trống — điền thêm)*
- 📅 **Học kỳ / Năm học:** *(để trống — điền thêm)*
- 🔗 **API Version:** `2.0.0` · **Backend:** FastAPI · **Frontend:** React + Vite

---

## Slide 2 — Mục tiêu đề tài
> ⏱️ **Thời gian trình bày: ~1 phút**

**Tiêu đề:** Vấn Đề Thực Tế & Mục Tiêu Xây Dựng Hệ Thống

**Nội dung:**
- 🔴 **Bài toán:** Sinh viên khó tra cứu thông tin chính xác từ các văn bản học vụ dài, phức tạp (quy chế đào tạo, chuẩn đầu ra, thông báo học phí…)
- 🎯 **Mục tiêu:** Xây dựng chatbot AI trả lời câu hỏi chính xác, có trích dẫn nguồn — chạy hoàn toàn trên local, không phụ thuộc internet hoặc API trả phí
- 👤 **Đối tượng:** Sinh viên (tra cứu) + Cán bộ Khoa — Admin (quản lý tài liệu, upload, thống kê)
- 📄 **Phạm vi tài liệu:** File PDF / DOCX gồm quy chế đào tạo, chuẩn đầu ra, thông báo học vụ — hỗ trợ cả PDF scan qua OCR
- ⚙️ **Yêu cầu phi chức năng:** Chạy offline (Ollama local), bảo mật phân quyền (token session + PBKDF2-SHA256), triển khai bằng Docker Compose

---

## Slide 3a — Sơ Đồ Kiến Trúc Hệ Thống
> ⏱️ **Thời gian trình bày: ~1 phút**

**Tiêu đề:** Kiến Trúc 4 Tầng của EduRAG

**Mô tả sơ đồ (ASCII — vẽ lại trong PowerPoint):**

```
+----------------------------------------------------------+
|              NGUOI DUNG (Trinh duyet)                    |
+-------------------+--------------------------------------+
                    | HTTP
+-------------------v--------------------------------------+
|  TANG 1 — FRONTEND (React + Vite + Nginx)               |
|  Port: 3000  |  Container: edurag_frontend               |
|  Trang: Login, Chat, Library (Admin), Settings           |
+-------------------+--------------------------------------+
                    | REST API (CORS)
+-------------------v--------------------------------------+
|  TANG 2 — BACKEND (FastAPI, Python)                      |
|  Port: 8000  |  Container: edurag_backend                |
|  18 endpoint: /chat, /auth/*, /admin/*, /sessions        |
+----------+----------------------------+-----------------+
           | Embed / LLM call          | SQLAlchemy ORM
+----------v-----------+   +-----------v-----------------+
|  TANG 3 — AI PIPELINE|   |  TANG 4 — STORAGE           |
|  LangChain + Ollama  |   |  Chroma DB (vector)         |
|  LLM: Qwen2.5-7B     |   |  SQLite: chat_history.db    |
|  Embed: Vietnamese_  |   |  Volume: ./chroma_db        |
|  Embedding (768 dim) |   |  Volume: ./data (PDF/DOCX)  |
|  Ollama: port 11434  |   |                             |
+----------------------+   +-----------------------------+
```

**Luồng kết nối chính:**
- Người dùng gửi câu hỏi → Frontend (3000) → Backend API (8000)
- Backend → Chroma tìm kiếm vector → Ollama sinh câu trả lời
- Backend → SQLite lưu lịch sử + phản hồi (feedback 👍/👎)
- Admin upload PDF → Backend chunk + embed → Chroma lưu vector

---

## Slide 3b — Công Nghệ Sử Dụng
> ⏱️ **Thời gian trình bày: ~1 phút**

**Tiêu đề:** Bảng Công Nghệ — Lấy Trực Tiếp Từ Source Code

| Tầng | Công nghệ | Vai trò |
|------|-----------|---------|
| Frontend | React 18 + Vite + TypeScript | Giao diện người dùng, SPA |
| Frontend | Nginx (Docker) | Serve static build, port 3000 |
| Backend | FastAPI (Python) v2.0.0 | REST API, 18 endpoint |
| Backend | SQLAlchemy + SQLite | ORM, 6 bảng dữ liệu |
| AI Pipeline | LangChain (Core + Ollama + Chroma) | Orchestration RAG pipeline |
| AI Pipeline | Qwen2.5:7b (Ollama) | Mô hình sinh ngôn ngữ (LLM) |
| AI Pipeline | AITeamVN/Vietnamese_Embedding | Embedding tiếng Việt (~560MB, 768 chiều) |
| Storage | Chroma DB | Vector store, persistent local file |
| Storage | SQLite chat_history.db | Lưu chat, tài khoản, hoạt động |
| DevOps | Docker Compose | Orchestration 2 container |
| DevOps | Ollama (host, port 11434) | Serve LLM local, không phụ thuộc cloud |

---

## Slide 4a — Lý Thuyết: RAG (Retrieval-Augmented Generation)
> ⏱️ **Thời gian trình bày: ~40 giây**

**Tiêu đề:** RAG Là Gì? Tại Sao EduRAG Chọn RAG?

**Định nghĩa ngắn gọn:**
> RAG = Truy xuất thông tin từ tài liệu → Bổ sung vào ngữ cảnh → Sinh câu trả lời dựa trên tài liệu thật

**So sánh RAG vs LLM thuần:**

| Tiêu chí | LLM thuần (không RAG) | RAG (EduRAG) |
|----------|----------------------|--------------|
| Nguồn thông tin | Kiến thức huấn luyện (có thể lỗi thời) | Tài liệu thật được upload |
| Trích dẫn nguồn | ❌ Không có | ✅ Có tên file + số trang |
| Hallucination | ⚠️ Cao | ✅ Thấp (chỉ dùng tài liệu có sẵn) |
| Cập nhật tài liệu | ❌ Phải train lại model | ✅ Upload → rebuild index |
| Chi phí | 💰 API trả phí (OpenAI...) | 🆓 Chạy local với Ollama |

**Lý do chọn RAG:**
- Quy chế đào tạo thay đổi theo năm → cần tài liệu luôn mới
- Câu trả lời phải chính xác, có trích dẫn để kiểm chứng
- Chạy offline hoàn toàn, không phụ thuộc API ngoài

---

## Slide 4b — Embedding & Vector Database
> ⏱️ **Thời gian trình bày: ~40 giây**

**Tiêu đề:** Embedding & Chroma — Nền Tảng Tìm Kiếm Ngữ Nghĩa

**Embedding là gì:**
> Chuyển đoạn văn bản → vector số (tọa độ nhiều chiều) để so sánh độ tương đồng ngữ nghĩa giữa câu hỏi và tài liệu bằng phép tính toán học.

**Model dùng trong EduRAG** (từ rag_chain.py dòng 30):
- `AITeamVN/Vietnamese_Embedding` — Fine-tuned trên 300.000 cặp câu tiếng Việt
- Chiều vector: 768 chiều, normalize cosine similarity
- Kích thước: ~560MB, tự động cache tại Docker volume `hf_cache`
- Batch size: 32, hỗ trợ GPU CUDA tự động (fallback CPU)

**Chroma DB:**
- Lưu toàn bộ vectors tại `./chroma_db` (persistent volume)
- Collection `edurag_docs` — active/staging tách biệt → rebuild không downtime
- Pipeline: L2 distance → convert sang cosine score → ngưỡng `MIN_RELEVANCE_SCORE=0.30`

---

## Slide 4c — MMR: Maximum Marginal Relevance
> ⏱️ **Thời gian trình bày: ~40 giây**

**Tiêu đề:** MMR — Tránh Kết Quả Trùng Lặp, Tăng Chất Lượng Ngữ Cảnh

**Vấn đề của Similarity Search thuần:**
- Trả về nhiều chunk giống nhau (cùng đoạn văn, ít khác biệt)
- Ngữ cảnh lặp → LLM không nhận thêm thông tin → câu trả lời thiếu

**MMR giải quyết:**
> Chọn kết quả vừa liên quan (relevance) vừa đa dạng (diversity) qua tham số lambda_mult

**Thông số thực tế** (từ rag_chain.py dòng 835–841):

```python
retriever = vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": TOP_K,          # = 8 chunk đưa vào prompt LLM
        "fetch_k": TOP_K*3,  # = 24 chunk ứng viên vòng đầu
        "lambda_mult": 0.7,  # 70% relevance + 30% diversity
    }
)
```

- RETRIEVAL_CANDIDATE_K = 30: vòng pre-retrieval lấy rộng hơn
- k = 8: chọn 8 chunk tốt nhất đưa vào prompt
- lambda_mult = 0.7: ưu tiên relevance nhưng đảm bảo đa dạng

---

## Slide 5a — Công Việc Đã Thực Hiện: Backend & AI Pipeline
> ⏱️ **Thời gian trình bày: ~1 phút**

**Tiêu đề:** Đợt 1 — Backend & AI Pipeline Đã Hoàn Thành

**Các module đã hoàn thành:**

| Module | File | Mô tả |
|--------|------|--------|
| RAG Pipeline | rag_chain.py (1.047 dòng) | Embed → MMR Retrieve → Rerank → LLM → Normalize |
| FastAPI App | main.py (720 dòng) | 18 endpoint: /chat, /auth/*, /account/*, /admin/*, /sessions/* |
| Admin Router | admin.py (752 dòng) | Upload PDF/DOCX đơn/batch, xóa, rebuild index, cập nhật metadata |
| Database | db.py (703 dòng) | 6 bảng SQLite: chat_history, document_metadata, admin_users, student_users, auth_sessions, activity_logs |
| Document Ingestion | document_ingestion.py | Load, clean, chunk (size=700, overlap=150), OCR Tesseract + PaddleOCR PP-OCRv6 |
| Build Index Script | scripts/build_index.py | Script dev: load → chunk → embed → lưu Chroma |

**Bảo mật đã triển khai:**
- Hash mật khẩu: PBKDF2-HMAC-SHA256 (200.000 iterations) — không lưu mật khẩu thô
- Phân quyền 2 cấp: Admin (upload, xóa, thống kê) / Student (chat, feedback)
- Google Sign-In OAuth2 tích hợp sẵn
- Reset mật khẩu qua email SMTP (token 1 lần, hết hạn 30 phút)

---

## Slide 5b — Công Việc Đã Thực Hiện: Frontend & Tích Hợp
> ⏱️ **Thời gian trình bày: ~1 phút**

**Tiêu đề:** Đợt 1 — Frontend React & Docker Deployment

**Các trang đã hoàn thành (React + TypeScript + Vite):**

- 🔐 Login.tsx — Đăng nhập / Đăng ký phân quyền Admin & Sinh viên, Google Sign-In, quên mật khẩu
- 💬 Chat.tsx — Bubble tin nhắn, hiệu ứng typing, source badge (tên tài liệu + số trang), nút 👍/👎 feedback, 4 quick question cards gợi ý
- 📚 Library.tsx (Admin) — Bảng tài liệu, upload đơn/batch, xóa, cập nhật metadata, preview PDF/DOCX inline
- 📊 AdminDashboard.tsx — Thống kê (tổng docs, chunks, sessions, messages, uptime), biểu đồ category, nhật ký hoạt động, RAG refusal panel
- ⚙️ Settings.tsx — Đổi tên hiển thị, đổi mật khẩu
- 🔑 ResetPassword.tsx — Đặt lại mật khẩu qua token email

**Docker Deployment (docker-compose.yml):**
- 2 container: edurag_backend (port 8000) + edurag_frontend (port 3000)
- 5 volume: hf_cache, ppocr_cache, ocr_result_cache, chroma_db, data
- Health check: GET /health mỗi 15 giây, start_period 240 giây (chờ load model embedding)

**Người thực hiện:** *(để trống — điền thêm)*

---

## Slide 6 — Thuận Lợi và Khó Khăn
> ⏱️ **Thời gian trình bày: ~1 phút**

**Tiêu đề:** Đánh Giá Quá Trình Thực Hiện Đợt 1

**✅ Thuận lợi:**
- 🤖 Công cụ AI hỗ trợ phát triển mạnh (Antigravity IDE, Claude) — rút ngắn thời gian viết boilerplate, debug nhanh, viết system prompt phức tạp
- 🔗 LangChain + Ollama cung cấp abstraction tốt — tích hợp LLM local (qwen2.5:7b) và embedding model chỉ vài chục dòng code, dễ hoán đổi model
- 🐳 Docker Compose đảm bảo môi trường nhất quán giữa dev và production — volume tự quản lý data, health check tự động restart khi lỗi

**❌ Khó khăn:**
- 📄 PDF scan (ảnh) không đọc được text thông thường — đang tích hợp Tesseract OCR và nghiên cứu PaddleOCR PP-OCRv6; text OCR còn lỗi ký tự ảnh hưởng chất lượng retrieval
- 🎯 Tối ưu câu trả lời LLM phức tạp — phải viết system prompt 14 quy tắc (rag_chain.py dòng 161–175) để chặn hallucination, chặn trích nguyên văn dài, giữ đúng nghĩa "bắt buộc" trong văn bản pháp lý
- 📊 Hiệu chỉnh ngưỡng retrieval tốn nhiều thời gian thực nghiệm — MIN_RELEVANCE_SCORE, TOP_K, RETRIEVAL_CANDIDATE_K cần bộ test câu hỏi thật đủ lớn để calibrate chính xác

---

## Slide 7 — Kế Hoạch Đợt Tiếp Theo
> ⏱️ **Thời gian trình bày: ~1 phút**

**Tiêu đề:** Kế Hoạch Công Việc Đợt 2

| Công việc | Mô tả ngắn | Độ ưu tiên |
|-----------|------------|------------|
| Tích hợp PaddleOCR PP-OCRv6 | Thay thế/bổ sung Tesseract để đọc PDF scan tiếng Việt chính xác hơn; model PP-OCRv6_small_det/rec đã cấu hình sẵn trong .env.example | 🔴 Cao |
| Bổ sung danh mục tài liệu | Upload đầy đủ quy chế đào tạo, chuẩn đầu ra, biểu mẫu học vụ; điền metadata (display_name, category, issuing_unit, document_year) | 🔴 Cao |
| Kiểm thử với sinh viên thực tế | Thu thập 50–100 câu hỏi thật; đánh giá độ chính xác; dùng log /admin/rag-refusals để điều chỉnh ngưỡng MIN_RELEVANCE_SCORE | 🟠 Trung bình |
| Tối ưu chunking & retrieval | Thử nghiệm CHUNK_SIZE, CHUNK_OVERLAP, RETRIEVAL_CANDIDATE_K; cân nhắc semantic chunking theo cấu trúc điều/khoản văn bản pháp lý | 🟠 Trung bình |
| Viết báo cáo đồ án | Chương Lý thuyết, Thiết kế hệ thống, Kết quả thực nghiệm, Kết luận theo cấu trúc nhà trường yêu cầu | 🟡 Thấp |

---

## Slide 8 — Demo
> ⏱️ **Thời gian trình bày: ~30 giây giới thiệu + thời gian demo thực tế**

**Tiêu đề:** Demo Trực Tiếp — EduRAG Hoạt Động Thực Tế

**Flow demo sẽ trình bày:**

1. 🔐 **Đăng nhập tài khoản sinh viên** — Vào trang Login, nhập email/password (hoặc Google Sign-In) → hệ thống cấp token phiên 12 giờ, chuyển sang trang Chat
2. 💬 **Đặt câu hỏi về quy chế** — Gõ câu hỏi thực tế (vd: "Điều kiện xét học bổng là gì?") → xem câu trả lời kèm source badge (tên tài liệu + trang), bấm 👍/👎 để gửi feedback
3. 🔑 **Đăng nhập Admin** — Vào Dashboard: xem thống kê (tổng tài liệu, chunks, sessions, uptime hệ thống); xem nhật ký hoạt động và danh sách câu hỏi RAG từ chối
4. 📤 **Upload tài liệu mới → Rebuild index** — Upload PDF mới qua Library, điền metadata → hệ thống tự chunk + embed vào Chroma; bấm "Rebuild Index" đồng bộ toàn bộ không downtime (staging collection)

---

## Ghi chú kỹ thuật cho người trình bày

**Chuẩn bị trước khi demo:**
- Chạy `docker compose up` và chờ health check pass (~4 phút lần đầu do load model embedding ~560MB)
- Đảm bảo Ollama đang chạy trên host: `ollama serve` và đã pull model: `ollama pull qwen2.5:7b`
- Đã có ít nhất 1 tài liệu PDF trong thư mục `./data` và đã rebuild index
- Tài khoản demo: đặt trong file `.env` (biến ADMIN_USERNAME, ADMIN_PASSWORD — tối thiểu 12 ký tự)

**Thời gian phân bổ gợi ý:**

| Slide | Nội dung | Thời gian |
|-------|----------|-----------|
| 1 | Giới thiệu | 0:30 |
| 2 | Mục tiêu | 1:00 |
| 3a + 3b | Kiến trúc hệ thống | 2:00 |
| 4a + 4b + 4c | Lý thuyết (RAG, Embedding, MMR) | 2:00 |
| 5a + 5b | Công việc đã thực hiện | 2:00 |
| 6 | Thuận lợi / Khó khăn | 1:00 |
| 7 | Kế hoạch đợt 2 | 1:00 |
| 8 | Demo | 0:30 |
| **Tổng** | | **10:00** |
