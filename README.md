# EduRAG AI

Trợ lý hỏi đáp tài liệu học vụ dùng RAG (Retrieval-Augmented Generation). Sinh viên đặt câu hỏi và nhận câu trả lời kèm tên tài liệu, số trang; nếu tài liệu không có thông tin, hệ thống từ chối thay vì đoán. Quản trị viên nạp tài liệu PDF/DOCX (có OCR cho bản scan).

## Tính năng

- Hỏi đáp trên toàn bộ thư viện hoặc trong một tài liệu, có nguồn và trang tham chiếu.
- Hội thoại nhiều lượt, lưu lịch sử theo phiên.
- Quản trị: upload, sửa, xóa tài liệu, tạo lại chỉ mục, xem thống kê.
- Chạy hoàn toàn cục bộ, không cần mạng sau lần cài đầu.

## Kiến trúc

```text
React + Vite (:3000)  ──►  FastAPI (:8000)  ──►  ChromaDB + SQLite
                                  │
                                  └──►  Ollama (trên máy host, :11434)
```

Model mặc định: LLM `qwen3.5:9b` (Ollama), embedding `AITeamVN/Vietnamese_Embedding`, reranker `BAAI/bge-reranker-v2-m3`.

## Chạy bằng Docker

**Cần có:** Docker Compose và [Ollama](https://ollama.com) (Ollama chạy trên máy host, không nằm trong Docker).

```powershell
# 1. Tải model cho Ollama
ollama pull qwen3.5:9b

# 2. Tạo file cấu hình, rồi mở .env sửa ADMIN_USERNAME và ADMIN_PASSWORD (từ 12 ký tự)
Copy-Item .env.example .env

# 3. Khởi động
if (-not (Test-Path chat_history.db)) { New-Item -ItemType File chat_history.db | Out-Null }
docker compose up --build -d
```

Mở http://localhost:3000 và đăng nhập bằng tài khoản admin vừa đặt. Tài liệu API ở http://localhost:8000/docs.

Dừng: `docker compose down`.

> **Lần chạy đầu cần mạng** để tải model embedding và reranker (khoảng 4 GB):
> `$env:HF_HUB_OFFLINE = "0"; docker compose up --build -d`.
> Từ lần sau, Docker dùng model đã lưu trong volume `edurag_hf_cache` và chạy được khi không có mạng. Đừng chạy `docker compose down -v` vì sẽ xóa volume này.

## Dữ liệu cần giữ

| Đường dẫn | Nội dung |
|---|---|
| `data/` | Tài liệu đã upload |
| `chroma_db/` | Chỉ mục vector |
| `chat_history.db` | Tài khoản, lịch sử chat |

Ba mục này không được commit lên git. Hãy sao lưu trước khi triển khai lại.

## Cấu hình thường dùng

Chỉnh trong `.env`, rồi chạy lại `docker compose up -d`. Danh sách đầy đủ có trong `.env.example`.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LLM_MODEL` | `qwen3.5:9b` | Model sinh câu trả lời |
| `MIN_RELEVANCE_SCORE` | `0.30` | Ngưỡng từ chối. Giảm nếu từ chối quá nhiều, tăng nếu AI trả lời lạc đề |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Để trống để tắt reranker (nhanh hơn, kém chính xác hơn) |
| `OCR_PROVIDER` | `tesseract` | OCR cho PDF scan |

## Kiểm thử

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -m unittest discover -s tests -p "test_*.py"
```

Bộ 59 câu hỏi đánh giá chất lượng nằm ở `experiments/evaluation/` (xem README trong thư mục đó).

## Gặp lỗi?

| Triệu chứng | Cách xử lý |
|---|---|
| Chat không trả lời | Kiểm tra Ollama đang chạy và đã `ollama pull qwen3.5:9b` |
| Backend không khởi động được lần đầu | Chạy với `HF_HUB_OFFLINE=0` để tải model |
| Build lỗi ở bước cài `paddlepaddle` | Lỗi mạng tạm thời, chạy lại `docker compose up --build -d` |
| Không đăng nhập được admin | Nếu database đã có admin thì `ADMIN_*` trong `.env` bị bỏ qua, hãy dùng tài khoản đã có |
