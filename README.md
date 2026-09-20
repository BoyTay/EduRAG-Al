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
backend/ocr_service.py       Chọn OCR provider, kiểm tra bảng ký tự Paddle
backend/tesseract_service.py OCR CPU tiếng Việt qua Tesseract vie
backend/document_ingestion.py Đọc PDF/DOCX và OCR fallback theo trang
frontend/            React + TypeScript + Vite frontend
data/                Tài liệu nguồn PDF/DOCX
chroma_db/           Vector store được tạo từ tài liệu
scripts/             Lệnh tạo lại chỉ mục vector
```

`chroma_db/` và `chat_history.db` chứa dữ liệu vận hành. Không xóa chúng nếu cần giữ chỉ mục hoặc lịch sử trò chuyện.

## Chạy bằng Docker

Đảm bảo Ollama chạy trên máy host và đã có model `qwen3.5:9b`, sau đó chạy từ thư mục gốc:

```powershell
docker compose up --build -d
```

- Giao diện: `http://localhost:3000`
- FastAPI docs: `http://localhost:8000/docs`

Xem trạng thái:

```powershell
docker compose ps
```

PDF có native text đủ dài được đọc trực tiếp. Chỉ trang PDF thiếu text mới được
render trong bộ nhớ ở 300 DPI và gửi qua Tesseract với ngôn ngữ `vie`.
Model tiếng Việt được cài sẵn trong image; không cần tải ở lần upload đầu.
Kết quả OCR dạng text/JSON nằm trong volume riêng `edurag_ocr_result_cache`,
không được phục vụ công khai.

Các biến chính trong `.env.example`:

- `OCR_ENABLED`: bật/tắt OCR mà không tải model khi tắt;
- `OCR_DEVICE=cpu`: Docker CPU là cấu hình mặc định;
- `OCR_DPI`, `OCR_NATIVE_TEXT_THRESHOLD` và các ngưỡng trang trắng: cấu hình
  ban đầu, cần benchmark trên tài liệu thật;
- `OCR_PROVIDER=tesseract`: cấu hình mặc định cho PDF scan tiếng Việt. Mặc định
  dùng `OCR_TESSERACT_PSM=6` để giữ đủ các dòng trong văn bản một cột và làm
  nhạt con dấu/chú thích màu bằng `OCR_TESSERACT_REMOVE_COLORED_OVERLAYS=true`.
- `OCR_DETECTION_MODEL` và `OCR_RECOGNITION_MODEL`: chỉ áp dụng khi chọn
  `OCR_PROVIDER=paddleocr`; model thiếu bảng ký tự tiếng Việt sẽ bị chặn.

Small/Medium đã thử mất dấu do thiếu ký tự trong artifact đã tải. Tesseract `vie`
đã đọc đúng hai dòng kinh phí trên trang 3; chưa có benchmark toàn corpus.
Cache dùng provider, phiên bản engine, SHA-256 model, DPI và cấu hình; đổi provider
không tái sử dụng cache Paddle. Rebuild qua API admin để thay chunk cũ.
Nếu `.env` cũ đặt `OCR_DPI=200`, đổi thành `300` khi chuyển sang Tesseract.

RAG lấy 30 candidate mặc định, quy đổi squared-L2 của embedding đã normalize
về cosine score, rerank rồi chỉ gửi tối đa 8 chunk vào prompt. Câu hỏi yêu cầu
liệt kê nội dung được mở rộng theo tiêu đề mục và gom các chunk cùng trang;
câu hỏi chứa ngày tháng/số văn bản có thêm tín hiệu rerank. Có thể điều chỉnh
`RETRIEVAL_CANDIDATE_K`, `TOP_K` và `MIN_RELEVANCE_SCORE` trong `.env`; cần
benchmark trước khi thay đổi ngưỡng từ chối.

`LLM_TEMPERATURE=0.3` áp dụng cho lượt sinh câu trả lời để cách diễn đạt tự
nhiên hơn. `LLM_AUDIT_TEMPERATURE=0.0` chỉ áp dụng cho lượt rà soát câu hỏi
liệt kê, giúp việc bổ sung ý còn thiếu ổn định và hạn chế phát sinh nội dung.
Model mặc định là `qwen3.5:9b`; chế độ reasoning được tắt để giảm độ trễ và
không đưa suy luận nội bộ vào câu trả lời. Chỉ tăng lên `LLM_TEMPERATURE=0.4`
sau kiểm thử A/B vì mức 0.4 chưa cho thấy lợi ích rõ ràng về độ chính xác.

Torch và PaddlePaddle được cài từ các CPU index riêng; không đổi các lệnh này
thành một lần resolve chung trên PyPI vì có thể kéo theo wheel CUDA dung lượng lớn.

## Chạy để phát triển frontend

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Frontend gọi API tại `http://localhost:8000` theo mặc định.

## Tạo lại chỉ mục RAG

Luồng production duy nhất là API quản trị có Bearer token:

```powershell
curl.exe -X POST http://localhost:8000/admin/rebuild-index -H "Authorization: Bearer <ADMIN_TOKEN>"
```

`scripts/build_index.py` chỉ dành cho phát triển và không quản lý collection
active/staging. Tùy chọn `--reset` đã bị chặn; không dùng script để rebuild
production.
