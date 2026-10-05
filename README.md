# EduRAG AI

EduRAG là ứng dụng hỏi đáp tài liệu học vụ bằng Retrieval-Augmented Generation (RAG). Sinh viên có thể tìm tài liệu, hỏi trên toàn bộ thư viện hoặc giới hạn trong một tài liệu, xem nguồn và trang tham chiếu, tiếp tục hội thoại và gửi phản hồi. Quản trị viên nạp, cập nhật, vô hiệu hóa, xóa tài liệu và tạo lại chỉ mục.

## Kiến trúc

```text
React 19 + TypeScript + Vite (:3000)
    │ REST API / Bearer token
    ▼
FastAPI (:8000) ─────────► SQLite (tài khoản, phiên, metadata, chat, log)
    │
    ├─► PDF/DOCX ─► OCR khi cần ─► ChromaDB (vector tài liệu)
    └─► truy hồi + rerank ─► Ollama (:11434 trên host) ─► câu trả lời và nguồn
```

Backend dùng FastAPI, SQLAlchemy, LangChain và ChromaDB. Frontend dùng React Router, TanStack Query, Zustand và Tailwind CSS. Model sinh câu trả lời mặc định là `qwen3.5:9b` qua Ollama, đổi được bằng `LLM_MODEL`. Embedding mặc định là `AITeamVN/Vietnamese_Embedding` qua Hugging Face.

PDF có text được đọc trực tiếp. Trang scan hoặc thiếu text được OCR riêng theo trang; Docker mặc định dùng Tesseract `vie`. PaddleOCR là lựa chọn thay thế qua `OCR_PROVIDER` và có kiểm tra bảng ký tự tiếng Việt. Luồng RAG chỉ dùng tài liệu `active`, xét các lượt hội thoại gần đây để xử lý câu hỏi tiếp nối, rerank chunk và từ chối khi thiếu bằng chứng phù hợp.

## Chạy bằng Docker Compose

Cần Docker Compose và Ollama. Ollama chạy trên **máy host**, không nằm trong Compose.

1. Chuẩn bị `ADMIN_USERNAME`, `ADMIN_PASSWORD` riêng của bạn. Mật khẩu admin đầu tiên phải dài ít nhất 12 ký tự. Không commit `.env`. Hai biến này chỉ tạo tài khoản admin khi SQLite chưa có admin; thay đổi chúng sau đó không đổi mật khẩu tài khoản đã tạo.
2. Đảm bảo Ollama đang chạy và tải model: `ollama pull qwen3.5:9b`. Chạy `ollama serve` nếu Ollama chưa chạy.
3. Từ thư mục gốc, tạo `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

   Mở `.env`, sửa `ADMIN_USERNAME` và `ADMIN_PASSWORD`, lưu file, rồi khởi động:

   ```powershell
   if (-not (Test-Path chat_history.db)) { New-Item -ItemType File chat_history.db | Out-Null }
   docker compose up --build -d
   docker compose ps
   ```

Giao diện ở `http://localhost:3000`, API ở `http://localhost:8000`, tài liệu OpenAPI ở `http://localhost:8000/docs`. Đăng nhập admin để nạp PDF/DOCX; sinh viên có thể tự đăng ký. Backend cần thời gian tải embedding model ở lần chạy đầu. Compose đợi `/health` thành công trước khi khởi động frontend.

Image frontend được build với `VITE_API_URL=http://localhost:8000`. Nếu mở từ máy khác hoặc đổi địa chỉ API, sửa build arg trong `docker-compose.yml` rồi build lại frontend. `CORS_ORIGINS` phải gồm origin frontend tương ứng. Backend trong container gọi Ollama qua `host.docker.internal:11434`.

### Dữ liệu cần giữ

- `data/`: PDF/DOCX đã upload.
- `chroma_db/`: collection vector và marker collection đang hoạt động.
- `chat_history.db`: tài khoản, phiên đăng nhập, metadata, chat và nhật ký.
- Docker volumes `edurag_hf_cache`, `edurag_ppocr_cache`, `edurag_ocr_result_cache`: cache model và kết quả OCR.

Sao lưu nhất quán `data/`, `chroma_db/` và `chat_history.db` trước khi thay đổi dữ liệu hoặc triển khai lại. `/health` trả trạng thái backend, số vector và tên model được cấu hình; endpoint này **không xác minh** Ollama đang chạy hoặc đã tải model.

## Chạy để phát triển trên Windows

`setup.bat` tạo `venv`, cài dependency Python và frontend; `run.bat` mở Ollama, backend và Vite trong các cửa sổ riêng. Cần Python, Node.js, Ollama và, nếu xử lý PDF scan bằng Tesseract, bản Tesseract có dữ liệu ngôn ngữ `vie` trong PATH. Các script batch không tự tải model Ollama hoặc nạp `.env` vào tiến trình backend.

Chạy thủ công trong PowerShell để đặt biến môi trường cho backend:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd frontend
npm install
Copy-Item .env.example .env
cd ..
$env:ADMIN_USERNAME = "your-admin-username"
$env:ADMIN_PASSWORD = "replace-with-a-strong-password"
$env:PYTHONPATH = (Resolve-Path backend).Path
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Mở terminal khác để chạy `cd frontend; npm run dev`. Frontend dev mặc định gọi `http://localhost:8000` theo `frontend/.env.example`. Với Python local, cấu hình OCR/cache và các dependency hệ thống cần tương ứng với máy; Dockerfile là cấu hình CPU của dự án. Nếu đã có database, dùng tài khoản hiện có.

## Tính năng và quyền truy cập

- **Khách:** đăng ký, đăng nhập, xem cấu hình nhà cung cấp đăng nhập; đăng nhập Google khi có `GOOGLE_CLIENT_ID`; yêu cầu đặt lại mật khẩu khi cấu hình SMTP. `GET /health` và `GET /admin/documents` cũng công khai.
- **Sinh viên và admin đã đăng nhập:** chat, xem/xóa phiên của mình, gửi feedback, xem thư viện và preview PDF/DOCX, sửa hồ sơ và mật khẩu. `document_filename` trong yêu cầu chat giới hạn câu hỏi vào một tài liệu đang active.
- **Admin:** xem thống kê, hoạt động và câu hỏi RAG bị từ chối; upload một hoặc nhiều PDF/DOCX, sửa metadata/trạng thái, xóa tài liệu và rebuild index. Upload trùng tên bị từ chối. Giới hạn mặc định là 20 MiB mỗi file và 100 MiB cho một batch.

Các nhóm endpoint chính:

- Xác thực: `/auth/register`, `/auth/login`, `/admin/login`, `/auth/google`, `/auth/logout`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/providers`.
- Tài khoản: `/account`, `/account/profile`, `/account/password`.
- Hỏi đáp: `/chat`, `/chat/{message_id}/feedback`, `/history/{session_id}`, `/sessions`, `/sessions/{session_id}`.
- Tài liệu: `/admin/documents`, `/documents/{filename}/preview`, `/admin/upload`, `/admin/upload-multiple`, `/admin/documents/{filename}`, `/admin/delete/{filename}`, `/admin/rebuild-index`.
- Vận hành: `/health`, `/admin/stats`, `/admin/activities`, `/admin/rag-refusals`.

Schema và mã trạng thái có tại `/docs`. API chat cần header `Authorization: Bearer <token>`. Ví dụ dùng token nhận từ đăng nhập:

```powershell
curl.exe -X POST http://localhost:8000/chat `
  -H "Authorization: Bearer <token>" `
  -H "Content-Type: application/json" `
  -d '{"question":"Điều kiện tốt nghiệp là gì?"}'
```

## Cấu hình thường dùng

Các giá trị mẫu nằm trong `.env.example`; Compose chỉ truyền các biến được khai báo trong `docker-compose.yml` vào backend. Sau khi đổi biến môi trường, khởi động lại dịch vụ; sau khi đổi build arg frontend, build lại image.

- `LLM_MODEL=qwen3.5:9b`, `LLM_TEMPERATURE=0.3`, `LLM_AUDIT_TEMPERATURE=0.0`: model và nhiệt độ cho lượt trả lời/rà soát.
- `RETRIEVAL_CANDIDATE_K=30`, `TOP_K=8`, `MIN_RELEVANCE_SCORE=0.30`: số candidate, số chunk đưa vào prompt và ngưỡng từ chối. Cần đánh giá trên tài liệu thật trước khi chỉnh ngưỡng.
- `OCR_ENABLED=true`, `OCR_PROVIDER=tesseract`, `OCR_TESSERACT_PSM=6`, `OCR_DPI=300`: xử lý scan. `OCR_TESSERACT_REMOVE_COLORED_OVERLAYS=true` hỗ trợ nhận dạng chữ trên nền có lớp màu.
- `OCR_PROVIDER=paddleocr`: dùng PaddleOCR; `OCR_DETECTION_MODEL` và `OCR_RECOGNITION_MODEL` chỉ áp dụng với lựa chọn này. Model thiếu ký tự tiếng Việt bị từ chối.
- `CORS_ORIGINS`, `GOOGLE_CLIENT_ID`, `SMTP_*`, `FRONTEND_URL`: origin được phép gọi API và các tính năng đăng nhập/đặt lại mật khẩu tùy chọn.

`EMBEDDING_MODEL` mặc định được khai báo trong backend và image. Compose hiện đặt cố định `AITeamVN/Vietnamese_Embedding`; muốn đổi model khi chạy bằng Compose phải sửa cấu hình Compose và tạo lại chỉ mục phù hợp. Không dùng embedding model mới trên collection cũ.

## Quản lý chỉ mục và kiểm thử

Admin dùng `POST /admin/rebuild-index` để đồng bộ tài liệu. Backend tạo collection staging, kiểm tra việc nạp rồi mới chuyển marker collection active; nếu rebuild thất bại, collection đang dùng được giữ lại. Endpoint yêu cầu Bearer token của admin. `scripts/build_index.py` chỉ phục vụ phát triển; `--reset` đã bị vô hiệu hóa và không thay thế rebuild qua API.

Các kiểm thử đơn vị nằm trong `tests/test_*.py`. Sau khi cài dependency backend, chạy từ thư mục gốc:

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -m unittest discover -s tests -p "test_*.py"
cd frontend
npm run build
```

`tests/run_e2e_completeness_test.py` là bộ đánh giá chất lượng câu trả lời cần dữ liệu, model và chỉ mục thực; không nằm trong lệnh unit test trên. Các thử nghiệm model nằm trong `experiments/llm_benchmark/`; Qwen 2.5 còn xuất hiện ở đây để so sánh lịch sử, không phải model chat mặc định. Tài liệu triển khai và kế hoạch kiểm thử bổ sung nằm trong `docs/`.
