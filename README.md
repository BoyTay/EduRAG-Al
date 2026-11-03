# EduRAG AI

Trợ lý hỏi đáp tài liệu học vụ dùng Retrieval-Augmented Generation (RAG). Sinh viên hỏi trên toàn bộ thư viện hoặc giới hạn trong một tài liệu, xem nguồn và trang tham chiếu, tiếp tục hội thoại và gửi phản hồi. Quản trị viên nạp, cập nhật, vô hiệu hóa, xóa tài liệu và tạo lại chỉ mục.

## Mục lục

- [Tính năng](#tính-năng)
- [Kiến trúc](#kiến-trúc)
- [Chạy nhanh bằng Docker Compose](#chạy-nhanh-bằng-docker-compose)
- [Chạy để phát triển trên Windows](#chạy-để-phát-triển-trên-windows)
- [Cấu hình](#cấu-hình)
- [Quyền truy cập và API](#quyền-truy-cập-và-api)
- [Dữ liệu và chỉ mục](#dữ-liệu-và-chỉ-mục)
- [Kiểm thử và đánh giá](#kiểm-thử-và-đánh-giá)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Xử lý sự cố](#xử-lý-sự-cố)

## Tính năng

- **Hỏi đáp có nguồn:** câu trả lời kèm tên tài liệu và trang tham chiếu; từ chối khi không đủ bằng chứng thay vì đoán.
- **Hội thoại nhiều lượt:** xét các lượt gần đây để hiểu câu hỏi tiếp nối; mỗi phiên tách biệt nhau.
- **Khóa theo tài liệu:** giới hạn câu hỏi trong một tài liệu đang `active`.
- **Nạp tài liệu PDF/DOCX:** PDF có text được đọc trực tiếp; mỗi dòng bảng được lưu cùng tiêu đề cột và câu dẫn phía trên bảng (kể cả bảng ngắt giữa hai trang hoặc có ô gộp). Trang scan hoặc thiếu text được OCR riêng theo trang.
- **Truy hồi và xếp hạng lại:** lấy ứng viên từ ChromaDB, chấm lại bằng cross-encoder cho câu tra cứu một giá trị (bảng điểm, bậc chuẩn đầu ra…).
- **Quản trị:** thống kê, nhật ký hoạt động, danh sách câu hỏi bị từ chối, rebuild index an toàn (collection staging, giữ bản cũ nếu lỗi).
- **Chạy offline:** embedding, reranker và LLM đều chạy cục bộ; sau khi đã có cache model thì không cần mạng.
- **Giao diện:** thanh bên có thể thu gọn (rail 72px, nhớ trạng thái), lịch sử hội thoại theo nhóm ngày, tìm kiếm hội thoại.

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

| Thành phần | Công nghệ |
|---|---|
| Backend | FastAPI, SQLAlchemy, LangChain, ChromaDB |
| Frontend | React Router, TanStack Query, Zustand, Tailwind CSS, Phosphor Icons |
| LLM | `qwen3.5:9b` qua Ollama (đổi bằng `LLM_MODEL`) |
| Embedding | `AITeamVN/Vietnamese_Embedding` (Hugging Face) |
| Reranker | `BAAI/bge-reranker-v2-m3` (cross-encoder, CPU; để trống để tắt) |
| OCR | Tesseract `vie` (mặc định), PaddleOCR (tùy chọn) |

## Chạy nhanh bằng Docker Compose

Cần Docker Compose và Ollama. Ollama chạy trên **máy host**, không nằm trong Compose.

1. Tải model và bảo đảm Ollama đang chạy:

   ```powershell
   ollama pull qwen3.5:9b
   ollama serve   # bỏ qua nếu Ollama đã chạy
   ```

2. Tạo `.env` từ file mẫu rồi sửa `ADMIN_USERNAME`, `ADMIN_PASSWORD` (mật khẩu admin đầu tiên dài ít nhất 12 ký tự). Không commit `.env`.

   ```powershell
   Copy-Item .env.example .env
   ```

   Hai biến này chỉ tạo admin khi SQLite chưa có admin; đổi chúng về sau không đổi mật khẩu tài khoản đã tạo. Nếu đã có database, dùng tài khoản hiện có.

3. Khởi động:

   ```powershell
   if (-not (Test-Path chat_history.db)) { New-Item -ItemType File chat_history.db | Out-Null }
   docker compose up --build -d
   docker compose ps
   ```

| Dịch vụ | Địa chỉ |
|---|---|
| Giao diện | http://localhost:3000 |
| API | http://localhost:8000 |
| OpenAPI | http://localhost:8000/docs |

Lần chạy đầu cần thời gian tải embedding model; Compose đợi `/health` thành công trước khi khởi động frontend. Dừng bằng `docker compose down` (dữ liệu được giữ). **Không** dùng `-v` nếu muốn giữ cache model.

### Chế độ offline (`HF_HUB_OFFLINE`)

Backend trong Compose chạy với `HF_HUB_OFFLINE=1` mặc định: dùng model đã có trong volume `edurag_hf_cache` và không gọi Hugging Face Hub. Với máy mới hoặc volume trống, chạy lần đầu để tải model:

```powershell
$env:HF_HUB_OFFLINE = "0"; docker compose up --build -d
```

Sau khi tải xong, đặt lại biến hoặc mở terminal mới. Log có dòng "Could not reach the Hub… Using cached commit hash" là bình thường ở chế độ offline.

### Địa chỉ API và CORS

Image frontend build với `VITE_API_URL=http://localhost:8000`. Nếu mở từ máy khác hoặc đổi địa chỉ API, sửa build arg trong `docker-compose.yml` rồi build lại frontend; `CORS_ORIGINS` phải gồm origin frontend tương ứng. Backend trong container gọi Ollama qua `host.docker.internal:11434`.

## Chạy để phát triển trên Windows

`setup.bat` tạo `venv`, cài dependency Python và frontend; `run.bat` mở Ollama, backend và Vite trong các cửa sổ riêng. Các script này không tự tải model Ollama và không nạp `.env` vào tiến trình backend. Cần Python 3.10+, Node.js 20+, Ollama và, nếu xử lý PDF scan bằng Tesseract, bản Tesseract có dữ liệu ngôn ngữ `vie` trong PATH.

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

Mở terminal khác: `cd frontend; npm run dev`. Frontend dev gọi `http://localhost:8000` theo `frontend/.env.example`. Với Python local, cấu hình OCR/cache và dependency hệ thống cần tương ứng với máy; `Dockerfile.backend` là cấu hình CPU chuẩn của dự án.

Không nạp `.env` bằng `source` trong bash: giá trị có ký tự đặc biệt sẽ làm lệnh lỗi. Đặt giá trị trong dấu ngoặc kép hoặc dùng `$env:` như trên.

## Cấu hình

Giá trị mẫu nằm trong `.env.example`. Compose chỉ truyền các biến được khai báo trong `docker-compose.yml`. Sau khi đổi biến môi trường, khởi động lại dịch vụ; sau khi đổi build arg frontend, build lại image.

| Nhóm | Biến | Mặc định | Ý nghĩa |
|---|---|---|---|
| LLM | `LLM_MODEL` | `qwen3.5:9b` | Model sinh câu trả lời |
| | `LLM_TEMPERATURE` / `LLM_AUDIT_TEMPERATURE` | `0.3` / `0.0` | Nhiệt độ lượt trả lời / lượt rà soát |
| | `LLM_NUM_CTX` | `6144` | Cửa sổ ngữ cảnh (vừa GPU 8 GB; tăng lên 8192 nếu GPU lớn hơn) |
| | `LLM_KEEP_ALIVE` | `30m` | Thời gian Ollama giữ model trong bộ nhớ |
| Truy hồi | `RETRIEVAL_CANDIDATE_K` | `30` | Số ứng viên vòng đầu |
| | `TOP_K` | `8` | Số chunk đưa vào prompt |
| | `MIN_RELEVANCE_SCORE` | `0.30` | Ngưỡng từ chối (0–1) |
| | `MAX_SECTION_CHUNKS` | `20` | Số chunk tối đa cho câu hỏi liệt kê |
| Reranker | `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Trống = tắt; lần đầu tải khoảng 2,2 GB, thêm vài giây mỗi câu |
| | `RERANKER_TOP_N`, `RERANKER_KEEP_RATIO`, `RERANKER_TIE_RATIO`, `RERANKER_MAX_PER_TABLE` | — | Chỉnh cách lọc ngữ cảnh |
| OCR | `OCR_ENABLED`, `OCR_PROVIDER` | `true`, `tesseract` | Bật OCR và chọn nhà cung cấp (`tesseract` hoặc `paddleocr`) |
| | `OCR_TESSERACT_PSM`, `OCR_DPI` | `6`, `300` | Tham số Tesseract / độ phân giải |
| | `OCR_TESSERACT_REMOVE_COLORED_OVERLAYS` | `true` | Hỗ trợ nhận dạng chữ trên nền có lớp màu |
| | `OCR_DETECTION_MODEL`, `OCR_RECOGNITION_MODEL` | PP-OCRv6 small | Chỉ áp dụng với PaddleOCR; model thiếu ký tự tiếng Việt bị từ chối |
| Bảo mật | `ADMIN_USERNAME`, `ADMIN_PASSWORD` | — | Chỉ dùng khi tạo admin đầu tiên |
| | `AUTH_RATE_LIMIT`, `CHAT_RATE_LIMIT` | `10`, `20` | Đăng nhập/đăng ký: số lần / 5 phút / IP; chat: số câu / phút / tài khoản |
| | `CORS_ORIGINS` | `http://localhost:3000` | Origin được phép gọi API; không chấp nhận `*` |
| Tùy chọn | `GOOGLE_CLIENT_ID`, `SMTP_*`, `FRONTEND_URL` | — | Đăng nhập Google và email đặt lại mật khẩu |
| Offline | `HF_HUB_OFFLINE` | `1` (Compose) | Dùng cache Hugging Face, không gọi Hub |

`EMBEDDING_MODEL` mặc định được khai báo trong backend và image; Compose đặt cố định `AITeamVN/Vietnamese_Embedding`. Muốn đổi model khi dùng Compose phải sửa cấu hình Compose và tạo lại chỉ mục. **Không dùng embedding model mới trên collection cũ.**

Các ngưỡng truy hồi cần được hiệu chỉnh trên tài liệu thật. Nếu quá nhiều từ chối hợp lệ (xem `/admin/rag-refusals`) hãy giảm `MIN_RELEVANCE_SCORE` xuống 0,22–0,25; nếu AI trả lời lạc đề hoặc bịa, tăng lên 0,35–0,40.

## Quyền truy cập và API

- **Khách:** đăng ký, đăng nhập, xem cấu hình nhà cung cấp đăng nhập; đăng nhập Google khi có `GOOGLE_CLIENT_ID`; yêu cầu đặt lại mật khẩu khi cấu hình SMTP; `GET /health`.
- **Sinh viên và admin đã đăng nhập:** chat, xem/xóa phiên của mình, gửi feedback, xem thư viện và preview PDF/DOCX (xem danh sách tài liệu qua `GET /admin/documents` cũng cần đăng nhập), sửa hồ sơ và mật khẩu.
- **Admin:** xem thống kê, hoạt động và câu hỏi bị từ chối; upload một hoặc nhiều PDF/DOCX; sửa metadata/trạng thái; xóa tài liệu; rebuild index. Upload trùng tên bị từ chối. Giới hạn mặc định 20 MiB mỗi file và 100 MiB mỗi batch.

| Nhóm | Endpoint chính |
|---|---|
| Xác thực | `/auth/register`, `/auth/login`, `/admin/login`, `/auth/google`, `/auth/logout`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/providers` |
| Tài khoản | `/account`, `/account/profile`, `/account/password` |
| Hỏi đáp | `/chat`, `/chat/{message_id}/feedback`, `/history/{session_id}`, `/sessions`, `/sessions/{session_id}` |
| Tài liệu | `/admin/documents`, `/documents/{filename}/preview`, `/admin/upload`, `/admin/upload-multiple`, `/admin/documents/{filename}`, `/admin/delete/{filename}`, `/admin/rebuild-index` |
| Vận hành | `/health`, `/admin/stats`, `/admin/activities`, `/admin/rag-refusals` |

Schema và mã trạng thái có tại `/docs`. API chat cần header `Authorization: Bearer <token>`:

```powershell
curl.exe -X POST http://localhost:8000/chat `
  -H "Authorization: Bearer <token>" `
  -H "Content-Type: application/json" `
  -d '{"question":"Điều kiện tốt nghiệp là gì?"}'
```

`document_filename` trong yêu cầu chat giới hạn câu hỏi vào một tài liệu đang `active`.

## Dữ liệu và chỉ mục

Giữ và sao lưu nhất quán các mục sau trước khi đổi dữ liệu hoặc triển khai lại:

| Đường dẫn | Nội dung |
|---|---|
| `data/` | PDF/DOCX đã upload |
| `chroma_db/` | Collection vector và marker collection đang hoạt động |
| `chat_history.db` | Tài khoản, phiên đăng nhập, metadata, chat, nhật ký |
| Volume `edurag_hf_cache` | Cache embedding và reranker (cần cho chế độ offline) |
| Volume `edurag_ppocr_cache`, `edurag_ocr_result_cache` | Cache model Paddle và kết quả OCR |

Các thư mục/tệp dữ liệu nằm trong `.gitignore`, không được commit.

Admin dùng `POST /admin/rebuild-index` để đồng bộ tài liệu: backend tạo collection staging, kiểm tra việc nạp rồi mới chuyển marker collection active; nếu rebuild thất bại, collection đang dùng được giữ lại. `scripts/build_index.py` chỉ phục vụ phát triển; `--reset` đã bị vô hiệu hóa và không thay thế rebuild qua API.

`/health` trả trạng thái backend, số vector và tên model được cấu hình; endpoint này **không xác minh** Ollama đang chạy hoặc đã tải model.

## Kiểm thử và đánh giá

Kiểm thử đơn vị, chạy từ thư mục gốc sau khi cài dependency backend:

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -m unittest discover -s tests -p "test_*.py"
cd frontend
npm run build   # gồm kiểm tra kiểu TypeScript
```

Đánh giá chất lượng câu trả lời (cần dữ liệu, model và chỉ mục thực, không nằm trong lệnh unit test):

- `experiments/evaluation/`: bộ 59 câu hỏi và `run_eval.py`, đo độ liên quan, tính đúng nguồn, thời gian phản hồi và tài nguyên. Xem `experiments/evaluation/README.md`.
- `tests/run_e2e_completeness_test.py`: kiểm tra độ đầy đủ của câu trả lời.
- `experiments/llm_benchmark/`: so sánh model; Qwen 2.5 còn ở đây để đối chiếu lịch sử, không phải model chat mặc định.

## Cấu trúc thư mục

```text
backend/        FastAPI: main.py (API), rag_chain.py (lõi RAG), document_ingestion.py,
                ocr_service.py, tesseract_service.py, admin.py, auth.py, db.py
frontend/       React + Vite (src/components, src/pages, src/stores, src/services)
scripts/        build_index.py, create_sample_doc.py
tests/          Kiểm thử đơn vị và e2e
experiments/    evaluation/, llm_benchmark/, ppocrv6_cpu/
docs/           Kế hoạch, báo cáo và tài liệu thiết kế (docs/design/sidebar)
data/           Tài liệu nguồn (không commit)
```

Tài liệu bổ sung: kế hoạch triển khai, kế hoạch kiểm thử PDF scan, tích hợp PP-OCRv6 và vấn đề bảng ký tự tiếng Việt nằm trong `docs/`.

## Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Chat báo lỗi hoặc không trả lời | Ollama chưa chạy hoặc chưa tải model (`/health` không kiểm tra) | `ollama serve` và `ollama pull qwen3.5:9b` |
| Backend không tải được model khi chạy lần đầu | `HF_HUB_OFFLINE=1` và volume cache trống | Chạy với `HF_HUB_OFFLINE=0` một lần |
| `docker compose build` lỗi ở bước cài `paddlepaddle` | Lỗi mạng tạm thời tới index PaddlePaddle | Chạy lại lệnh build |
| Không đăng nhập được admin | Admin đã tồn tại nên `ADMIN_*` bị bỏ qua | Dùng tài khoản đã có |
| Nhiều câu hỏi hợp lệ bị từ chối | Ngưỡng `MIN_RELEVANCE_SCORE` quá cao | Xem `/admin/rag-refusals` rồi giảm ngưỡng |
| Mất cache model sau khi dọn Docker | Đã xóa volume `edurag_hf_cache` (ví dụ `down -v`) | Tải lại với `HF_HUB_OFFLINE=0` |
| Lỗi `command not found` khi nạp `.env` bằng bash | Giá trị có ký tự đặc biệt | Đặt giá trị trong dấu ngoặc kép hoặc dùng `$env:` |
