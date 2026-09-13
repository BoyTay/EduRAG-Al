# Kế hoạch tích hợp PaddleOCR PP-OCRv6 cho EduRAG

**Ngày cập nhật:** 13/09/2026  
**Trạng thái:** Kế hoạch kỹ thuật — chưa triển khai, chưa cài dependency, chưa chạy model và chưa benchmark trên tài liệu EduRAG.

## 1. Mục tiêu và phạm vi

Mục tiêu là bổ sung khả năng đọc PDF scan chỉ chứa hình ảnh bằng PP-OCRv6, đồng thời giữ nguyên luồng đang hoạt động cho PDF có text layer và DOCX:

```text
PDF có text layer
  → đọc text native theo từng trang
  → làm sạch → chunk → embedding → ChromaDB

PDF scan hoặc trang PDF thiếu text
  → render riêng trang cần OCR
  → PP-OCRv6 nhận dạng tiếng Việt
  → tạo Document theo trang
  → làm sạch → chunk → embedding → ChromaDB

DOCX
  → giữ nguyên Docx2txtLoader
  → làm sạch → chunk → embedding → ChromaDB
```

PP-OCRv6 là fallback theo trang, không phải bộ đọc mặc định cho mọi PDF. PP-StructureV3 và PaddleOCR-VL không thuộc phạm vi chính; chỉ xem xét sau nếu benchmark chứng minh tài liệu bảng, nhiều cột hoặc bố cục phức tạp không đạt yêu cầu với PP-OCRv6.

### 1.1 Các quyết định triển khai đã chốt

| Nội dung | Quyết định |
| --- | --- |
| Môi trường mặc định | Docker CPU; chưa tạo profile GPU trong lần đầu, nhưng abstraction không được phụ thuộc cứng vào CPU |
| Model cho spike | PP-OCRv6 Small; benchmark Small và Medium trên cùng ground truth trước khi chọn model cuối |
| Phạm vi OCR | Chỉ PP-OCRv6, không tích hợp PP-StructureV3 hoặc PaddleOCR-VL |
| Đơn vị fallback | Từng trang; không OCR lại trang có text native đủ dùng |
| Lỗi theo trang | Bỏ qua trang được xác định là trắng; trang có nội dung nhưng không trích xuất được làm hủy toàn bộ ingestion |
| Native text ngắn | Luôn giữ làm candidate; OCR thất bại không được tự động xóa text native chính xác |
| Cache | Volume riêng, chỉ text/JSON; khóa bằng SHA-256 file + page + model/version + DPI + cấu hình; xóa theo tài liệu |
| Hiệu năng | Mục tiêu benchmark PDF scan khoảng 20 trang không quá khoảng 120 giây trên CPU demo; concurrency OCR bằng 1 |
| Frontend | Chưa hiển thị trạng thái OCR/confidence; backend trả lỗi rõ và log tổng hợp, không log nội dung OCR |
| Ground truth | Nhóm dự án tạo và kiểm tra thủ công khoảng 30–50 trang tiếng Việt thực tế |
| Rebuild | `POST /admin/rebuild-index` là luồng chính thức; script chỉ dùng phát triển và phải có cảnh báo deprecate |
| Rollback | Sửa vector mồ côi trong cùng đợt OCR bằng `ingestion_id` hoặc danh sách vector ID mới và fault injection |

## 2. Tóm tắt hiện trạng có dẫn chứng mã nguồn

### 2.1 Pipeline tài liệu hiện tại

| Hạng mục | Hiện trạng | Dẫn chứng |
| --- | --- | --- |
| Định dạng hỗ trợ | PDF và DOCX | `backend/admin.py:25`, `backend/admin.py:140-148` |
| Đọc PDF runtime | `PyMuPDFLoader` trong `load_and_chunk_document()` | `backend/admin.py:132-150` |
| Đọc DOCX runtime | `Docx2txtLoader` trong cùng hàm | `backend/admin.py:145-150` |
| Làm sạch | Gộp whitespace, bỏ null byte | `backend/admin.py:158-164` |
| Trang hợp lệ | Chỉ giữ trang có hơn 50 ký tự sau làm sạch | `backend/admin.py:169-175` |
| Chunk runtime | `RecursiveCharacterTextSplitter`, size/overlap lấy từ biến môi trường | `backend/admin.py:22-24`, `backend/admin.py:177-184` |
| Embedding | `HuggingFaceEmbeddings`, model lấy từ `EMBEDDING_MODEL` | `backend/rag_chain.py:29`, `backend/rag_chain.py:63-79` |
| Ghi vector | Embed toàn bộ text rồi `upsert` vào Chroma với `ingestion_id` | `backend/admin.py:197-266` |
| Collection runtime | Collection active được đọc từ `.active_collection` | `backend/rag_chain.py:31-35`, `backend/rag_chain.py:84-130` |
| Upload đơn | Lưu file → validate → đọc/chunk → vector → SQLite | `backend/admin.py:337-423` |
| Upload nhiều | Lặp từng file và dùng chung hàm runtime | `backend/admin.py:441-543` |
| Rebuild qua API | Build collection staging, kiểm tra rồi activate | `backend/admin.py:591-681` |
| Script build index | Có pipeline đọc/chunk riêng, không dùng hàm runtime | `scripts/build_index.py:63-134` |
| Khởi tạo tài nguyên | Database, admin, embedding và vector store được khởi tạo trong lifespan | `backend/main.py:228-259` |
| Python Docker | `python:3.11-slim`; patch version không được khóa | `Dockerfile.backend:2` |
| Kiểm thử tự động | Không tìm thấy thư mục/file test trong repository | Kết quả khảo sát `rg --files -g '*test*'` ngày 13/09/2026 |

### 2.2 Trả lời 14 câu hỏi khảo sát

1. **Hàm đang đọc PDF và DOCX:** luồng API dùng `load_and_chunk_document(file_path)` trong `backend/admin.py:132`; PDF dùng `PyMuPDFLoader`, DOCX dùng `Docx2txtLoader`. Script độc lập dùng `load_document()`, `clean_documents()` và `chunk_documents()` trong `scripts/build_index.py:63-103`.

2. **PDF scan hiện được phát hiện/xử lý:** chưa có phát hiện scan chuyên biệt. Loader được gọi như PDF thường; nếu không trả `docs`, hệ thống báo không trích xuất được text (`backend/admin.py:150-156`). Nếu có danh sách trang nhưng mọi trang còn tối đa 50 ký tự sau làm sạch, hệ thống báo cần OCR trước khi upload (`backend/admin.py:169-175`). Không có OCR fallback.

3. **Điều kiện trang rỗng/không hợp lệ:** sau khi `" ".join(text.split())` và bỏ `\x00`, trang chỉ được giữ khi `len(page_content.strip()) > 50` (`backend/admin.py:158-170`). Vì dùng dấu `>`, trang đúng 50 ký tự cũng bị loại.

4. **Dùng chung hàm đọc:** upload đơn (`backend/admin.py:389`), upload nhiều (`backend/admin.py:503`) và endpoint rebuild (`backend/admin.py:626`) dùng chung `load_and_chunk_document()`. `scripts/build_index.py` không dùng chung; script có loader, cleaner, splitter và hằng chunk riêng.

5. **Nơi tạo metadata:** `page` do `PyMuPDFLoader` tạo; mã dự án không tự gán lại page. `source` và `filename` được ghi trong `backend/admin.py:165-167`, sau đó `add_to_vector_store()` bảo đảm lại `filename` ở dòng 216-218. Script ghi `source`/`filename` tại `scripts/build_index.py:89-90`.

6. **Quy ước số trang:** metadata nội bộ đang được xử lý như zero-based. `format_docs()` cộng 1 khi đưa trang vào prompt (`backend/rag_chain.py:220-224`) và `extract_sources()` cộng 1 trước khi trả API (`backend/rag_chain.py:259-267`). OCR phải tiếp tục lưu `page=0` cho trang PDF đầu tiên.

7. **Chunk size/overlap:** runtime đọc `CHUNK_SIZE` và `CHUNK_OVERLAP`, mặc định 700/150 (`backend/admin.py:22-24`); Compose đặt cùng giá trị (`docker-compose.yml:28-29`). Script hard-code 700/150 (`scripts/build_index.py:35-36`) nên có nguy cơ lệch cấu hình runtime trong tương lai.

8. **Rollback khi xử lý lỗi:**
   - File upload được stream vào file tạm và xóa file tạm nếu ghi lỗi (`backend/admin.py:109-127`).
   - Lỗi validate/lưu xóa file đích (`backend/admin.py:369-385`).
   - Lỗi xử lý sau đó xóa file (`backend/admin.py:417-423`, `backend/admin.py:525-535`).
   - `add_to_vector_store()` tạo bộ ID mới, chỉ xóa chunk cũ sau khi ghi mới; nếu xóa chunk cũ thất bại thì cố xóa bộ chunk mới (`backend/admin.py:226-264`).
   - **Vấn đề:** nếu vector đã ghi xong nhưng ghi metadata SQLite hoặc log activity lỗi, exception handler chỉ xóa file, không xóa vector vừa ghi. Upload có thể để lại vector mồ côi.
   - Rebuild giữ collection cũ khi lỗi trước activate và xóa staging trong `finally` (`backend/admin.py:635-641`, `backend/admin.py:670-680`). Tuy nhiên collection mới được activate trước khi cập nhật metadata (`backend/admin.py:643-656`); lỗi metadata sau activate có thể trả lỗi dù collection mới đã active và metadata mới chỉ cập nhật một phần.

9. **Đồng bộ/bất đồng bộ:** ghi upload dùng `await upload.read()` nhưng đọc PDF, OCR dự kiến, chunk và embedding đều là hàm đồng bộ. Upload đơn/nhiều là `async def` nhưng gọi trực tiếp công việc CPU-bound (`backend/admin.py:337-390`, `backend/admin.py:441-504`), nên có thể chặn event loop. Endpoint rebuild là `def` đồng bộ (`backend/admin.py:591-592`), FastAPI có thể chạy route sync trong threadpool. Chat gọi LLM bằng `await` (`backend/rag_chain.py:460-467`).

10. **CPU/GPU Docker:** Compose hiện không khai báo `gpus`, device reservation hoặc NVIDIA runtime (`docker-compose.yml:7-53`). Backend dùng image `python:3.11-slim`, không phải CUDA image (`Dockerfile.backend:2`). Vì vậy môi trường Docker hiện tại phải được coi là CPU. Ollama chạy trên host (`docker-compose.yml:23`, `docker-compose.yml:44-46`) và có thể dùng GPU của host độc lập, nhưng chưa có cấu hình nguồn chứng minh điều đó.

11. **Phiên bản Python:** backend Docker dùng dòng Python 3.11; patch version thay đổi theo tag `python:3.11-slim` tại thời điểm build, nên chưa được khóa chính xác.

12. **OCR dependency hiện có:** `backend/requirements.txt:1-35` không có `paddleocr`, `paddlepaddle`, `paddlepaddle-gpu`, OpenCV hoặc công cụ OCR khác. `pymupdf` đã có và có thể dùng để render trang PDF thành ảnh mà không cần thêm trình raster hóa PDF riêng.

13. **Test upload/chunk/rebuild:** chưa có test tự động được tìm thấy. Các nhận định trên là phân tích mã, không phải kết quả kiểm thử runtime.

14. **Phạm vi có thể bị ảnh hưởng:** `POST /admin/upload`, `POST /admin/upload-multiple`, `POST /admin/rebuild-index`, `load_and_chunk_document()`, `add_to_vector_store()`, lifespan nếu chọn eager-load, Docker/requirements/cache, frontend upload nếu chuyển sang background job, và `scripts/build_index.py` nếu script tiếp tục được hỗ trợ.

### 2.3 Vấn đề cần giải quyết trước hoặc cùng lúc với OCR

| Vấn đề | Mức ảnh hưởng | Hướng xử lý trong kế hoạch |
| --- | --- | --- |
| Pipeline runtime và script bị trùng | OCR dễ chỉ hoạt động ở một luồng | Tách loader/clean/chunk dùng chung; script gọi lại service chung hoặc ghi rõ deprecate |
| CPU-bound chạy trực tiếp trong route async | OCR có thể làm API kém phản hồi | Chạy ingestion/OCR trong threadpool; giới hạn đồng thời |
| Rollback vector chưa bao phủ lỗi SQLite/log | Có thể để vector mồ côi | Trả về ID phiên ingestion và bù trừ vector nếu bước sau lỗi |
| Rebuild activate trước metadata | Trạng thái “API lỗi nhưng index mới active” | Chuẩn bị metadata/transaction trước switch hoặc có rollback marker rõ ràng |
| Chưa có benchmark | Không thể khẳng định độ đúng tiếng Việt | Tạo bộ benchmark và đo CER/WER trước khi khóa model/config |
| Chưa có OCR cache | Rebuild có thể OCR lại toàn bộ | Cache text OCR theo hash file + model + cấu hình |

## 3. Đánh giá PP-OCRv6

### 3.1 Khả năng tương thích đã xác minh từ tài liệu chính thức

- General OCR pipeline hỗ trợ PP-OCRv6 và tài liệu hiện tại ghi PP-OCRv6 medium trở thành mặc định từ PaddleOCR 3.7.
- PP-OCRv6 hỗ trợ `lang="vi"`.
- `PaddleOCR.predict()` nhận ảnh dạng NumPy, đường dẫn ảnh hoặc đường dẫn PDF. Với PDF, kết quả có `page_index`; tuy nhiên EduRAG nên truyền ảnh của từng trang thiếu text để không OCR lại trang native.
- Kết quả cung cấp `rec_texts`, `rec_scores`, `rec_polys` và `rec_boxes`; đủ để ghép text, tính confidence và sắp xếp theo vị trí.
- Gói `paddleocr` hỗ trợ Python từ 3.8; PaddlePaddle hiện hỗ trợ Python 3.9–3.13 trên nền tảng được liệt kê. Python 3.11 của backend nằm trong dải hỗ trợ, nhưng vẫn phải kiểm tra toàn bộ dependency graph với LangChain, PyTorch và image `slim`.
- General OCR không cần nhóm dependency `doc-parser`; không cần cài `paddleocr[all]` cho phạm vi này.

Nguồn chính thức:

- [General OCR Pipeline Usage](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html)
- [PP-OCRv6 Introduction](https://www.paddleocr.ai/main/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html)
- [PaddleOCR Installation](https://www.paddleocr.ai/main/en/version3.x/installation.html)
- [PaddlePaddle Installation Guide](https://www.paddlepaddle.org.cn/documentation/docs/en/install/index_en.html)

### 3.2 Lựa chọn Tiny, Small và Medium

| Tier | Kích thước model detection | Kích thước model recognition | Đánh giá cho EduRAG |
| --- | ---: | ---: | --- |
| Tiny | 1,9 MB | 4,4 MB | Nhẹ nhất nhưng độ chính xác công bố thấp nhất trong ba tier; chỉ cân nhắc thiết bị rất hạn chế |
| Small | 9,6 MB | 20,4 MB | Cân bằng tài nguyên/độ chính xác; phù hợp làm mặc định CPU thử nghiệm |
| Medium | 59,4 MB | 73,3 MB | Hướng server ưu tiên độ chính xác; cần so sánh CPU latency/RAM với Small |

Các kích thước trên chỉ là trọng số detection/recognition được tài liệu chính thức công bố, chưa gồm PaddlePaddle, OpenCV, model orientation, cache hoặc overhead runtime. Không có benchmark riêng cho tiếng Việt và tài liệu EduRAG; độ chính xác thực tế **chưa xác minh**.

**Quyết định cho spike:** dùng PP-OCRv6 Small trên Docker CPU. Sau đó benchmark Small và Medium trên cùng bộ 30–50 trang. Chỉ chọn Medium làm cấu hình cuối nếu CER/WER, lỗi dấu tiếng Việt, số điều/khoản và ngày tháng cải thiện rõ, đồng thời thời gian xử lý vẫn đáp ứng mục tiêu. Model cuối **chưa được khóa** trước khi có kết quả benchmark. Tiny không thuộc vòng so sánh ban đầu.

### 3.3 Rủi ro tài nguyên

- Backend hiện đã giữ embedding model trong bộ nhớ từ lúc startup (`backend/main.py:248-253`, `backend/rag_chain.py:333-354`). Lazy-load OCR giúp backend vẫn khởi động nhanh và không tải OCR nếu chỉ dùng PDF text/DOCX.
- OCR trang ảnh có thể tăng mạnh CPU/RAM và kéo dài request. Lần triển khai đầu giới hạn đúng một tác vụ OCR đồng thời trong mỗi backend instance.
- Nếu sau này cùng expose GPU cho backend, PyTorch embedding và PaddlePaddle có thể tranh VRAM. Ollama chạy trên host cũng có thể dùng cùng GPU; cần đo tổng VRAM thay vì chỉ đo OCR riêng.
- GPU không thuộc lần triển khai đầu. Abstraction `device` và factory model vẫn cần tách khỏi nghiệp vụ để có thể bổ sung GPU sau này mà không viết lại loader/chunking.

## 4. Điểm tích hợp OCR phù hợp

### 4.1 Vị trí đề xuất

Tách hai trách nhiệm:

1. **OCR service thuần:** module dự kiến `backend/ocr_service.py` hoặc tên tương đương sau khi thống nhất. Module chỉ lazy-load model, nhận ảnh một trang và trả `OCRPageResult(text, confidence, boxes, model_name)`. Module không biết FastAPI, chunking, SQLite hoặc ChromaDB.
2. **Document ingestion:** tách phần đọc/làm sạch/tạo `Document`/chunk khỏi router `backend/admin.py` sang module dự kiến `backend/document_ingestion.py`. Upload đơn, upload nhiều và API rebuild bắt buộc dùng chung implementation. Script phát triển có thể gọi lại module này hoặc chỉ giữ chức năng không ghi collection; không bắt buộc tích hợp OCR đầy đủ nếu đã được deprecate rõ.

Tên file trên là đề xuất, không phải cấu trúc đã có. Nếu muốn thay đổi tối thiểu ở vòng prototype, có thể giữ orchestrator trong `backend/admin.py` nhưng vẫn nên cô lập class/protocol OCR để unit test không tải model thật.

### 4.2 Hợp đồng dữ liệu đề xuất

```text
OCRService.recognize_page(image, page_index) -> OCRPageResult

OCRPageResult:
  text: str
  mean_confidence: float | None
  lines: list[OCRLine]
  model_name: str

OCRLine:
  text: str
  confidence: float
  box: polygon | rectangle
```

Bounding box được dùng tạm thời để sắp xếp dòng. Mặc định không ghi toàn bộ box vào Chroma vì làm metadata lớn và không phục vụ retrieval hiện tại. Có thể giữ JSON debug trong OCR cache khi bật chế độ chẩn đoán.

## 5. So sánh phương án

### 5.1 Phương án A — Chỉnh sửa tối thiểu trong loader hiện tại

**Cách làm:** thêm lazy singleton và fallback ngay trong `load_and_chunk_document()` của `backend/admin.py`.

**Ưu điểm:** ít file thay đổi, nhanh tạo prototype, upload/rebuild API tự nhận OCR vì đang dùng chung hàm.

**Nhược điểm/rủi ro:** `admin.py` tiếp tục ôm router, loader, chunk, vector và OCR; khó mock; script vẫn lệch; dễ vô tình load model theo mỗi request; bảo trì và kiểm thử rollback khó.

**Phù hợp:** spike ngắn để xác nhận dependency/API, không nên là kiến trúc cuối.

### 5.2 Phương án B — Service OCR trong cùng backend

**Cách làm:** tách OCR service và ingestion module dùng chung. Model lazy-load một lần, có lock/semaphore; router chỉ điều phối upload và transaction.

**Ưu điểm:** ranh giới rõ, mock dễ, tái sử dụng bắt buộc cho upload/rebuild và tùy chọn cho script phát triển, backend vẫn là một service Docker, không cần network nội bộ mới.

**Nhược điểm/rủi ro:** nhiều file thay đổi hơn A; vẫn giữ request mở trong lúc OCR; phải thiết kế thread-safety, cache và rollback.

**Phù hợp:** quy mô đồ án hiện tại, cần chất lượng mã tốt nhưng chưa cần queue/worker.

### 5.3 Phương án C — Background processing

**Cách làm:** upload lưu file và tạo job `pending`; worker chuyển `processing → completed/failed`; frontend polling hoặc nhận sự kiện.

**Phần phải bổ sung:** bảng/job status, migration, API lấy trạng thái, cơ chế retry/idempotency, worker/queue, frontend progress, recovery khi restart.

**Ưu điểm:** tránh timeout request, hiển thị tiến độ tốt, phù hợp PDF lớn/nhiều upload.

**Nhược điểm/rủi ro:** độ phức tạp vận hành và tính nhất quán tăng đáng kể; cần thêm service/volume/queue hoặc hàng đợi bền vững.

**Phù hợp:** chỉ xem xét sau nếu p95 của PDF scan khoảng 20 trang thường xuyên vượt 120 giây, tài liệu thực tế dài hơn đáng kể, hoặc upload làm API mất phản hồi. Mốc 120 giây là mục tiêu benchmark, không phải timeout hard-code.

### 5.4 Phương án khuyến nghị

Chọn **Phương án B — service OCR trong cùng backend**, kết hợp:

- Fallback theo từng trang.
- Lazy loading model một lần.
- Chạy ingestion CPU-bound ngoài event loop.
- Semaphore giới hạn concurrency OCR bằng 1 trong giai đoạn đầu.
- Cache OCR theo hash để rebuild không phải nhận dạng lại.
- Giữ API hiện tại ở giai đoạn đầu; chỉ nâng lên phương án C nếu benchmark xác nhận cần thiết.
- Khắc phục vector mồ côi trong cùng đợt thay đổi, không mở rộng sang nghiệp vụ khác.

Phương án này giải quyết sự trùng lặp loader và khả năng test mà không biến đồ án thành hệ thống worker phân tán.

## 6. Thiết kế luồng fallback

### 6.1 Thuật toán

1. Xác định phần mở rộng và giữ nguyên nhánh DOCX.
2. Với PDF, mở file bằng PyMuPDF một lần và duyệt theo `page_index` zero-based.
3. Trích text native từng trang.
4. Chuẩn hóa whitespace và bỏ null byte bằng cùng quy tắc hiện tại.
5. Luôn giữ text native khác rỗng làm candidate, kể cả khi ngắn hơn ngưỡng kích hoạt OCR.
6. Nếu text native đủ nội dung, tạo `Document` với `extraction_method="native"`; không gọi OCR.
7. Nếu text native rỗng/quá ngắn, render trang và chạy bộ phân loại trắng/nội dung theo hướng bảo thủ.
8. Nếu trang được xác định chắc chắn là trắng, bỏ qua và ghi warning với số trang one-based; không gọi OCR.
9. Nếu trang có hoặc có khả năng có nội dung, kiểm tra OCR cache bằng SHA-256 file, page index, model, version, DPI và fingerprint cấu hình.
10. Nếu cache miss, dùng ảnh render trong bộ nhớ và gọi PP-OCRv6 với `lang="vi"`, model Small ở bước spike và device CPU.
11. Lấy `rec_texts`, `rec_scores`, `rec_boxes`/`rec_polys`; bỏ dòng rỗng và ghép theo thứ tự đọc đã kiểm thử.
12. Chuẩn hóa text OCR, tính confidence tổng hợp để lưu metadata/quan sát; không dùng confidence như điều kiện loại trang trước khi benchmark.
13. Nếu OCR hợp lệ, tạo `Document` theo đúng trang và giữ `source`, `filename`, `page`; ảnh render được giải phóng, không ghi xuống cache.
14. Nếu OCR không hợp lệ nhưng native candidate vượt kiểm tra tối thiểu về ký tự đọc được, giữ native text với `extraction_method="native_low_text"` và ghi warning.
15. Nếu trang có nội dung nhưng cả OCR lẫn native candidate đều không dùng được, thu thập số trang one-based và hủy toàn bộ ingestion. Thông báo cho admin phải liệt kê các trang thất bại.
16. Đưa danh sách `Document` native + native ngắn + OCR vào một bộ splitter dùng chung và loại chunk rỗng.
17. Embed và upsert vector, đồng thời theo dõi `ingestion_id` hoặc chính xác danh sách ID mới.
18. Ghi SQLite và activity log. Nếu bất kỳ bước nào sau upsert lỗi, xóa vector mới, rollback DB, xóa file mới và cache vừa sinh cho lần ingestion đó.
19. Log chỉ gồm filename an toàn, số trang, phương thức trích xuất, thời gian, warning/error code; không log toàn bộ nội dung native/OCR.

#### Phân biệt trang trắng và trang có nội dung

Không dùng riêng “OCR trả rỗng” để kết luận trang trắng. Bộ phân loại đề xuất kết hợp:

- Text native sau chuẩn hóa.
- Tỷ lệ pixel gần trắng và độ biến thiên ảnh sau khi render grayscale.
- Diện tích vùng pixel khác nền sau khi bỏ lề.
- Sự tồn tại/diện tích của image object hoặc drawing object từ PDF.
- Kết quả text detection của PP-OCRv6 nếu trang không chắc chắn.

Chỉ bỏ trang khi mọi tín hiệu đều cho thấy trang trắng. Các ngưỡng pixel, variance, diện tích vùng nội dung và lề đều là **đề xuất cần kiểm thử** trên ground truth. Nếu kết quả phân loại không chắc chắn, hệ thống phải coi trang là có nội dung; OCR thất bại sẽ làm ingestion thất bại thay vì âm thầm mất nội dung.

Sanity check cho native candidate không dùng lại ngưỡng kích hoạt OCR. Nó chỉ xác nhận chuỗi còn ký tự Unicode có thể đọc được (ưu tiên chữ/số/dấu câu hữu ích), không chỉ gồm whitespace, control character hoặc ký tự thay thế lỗi. Ngưỡng/heuristic chính xác phải được test; mục tiêu là bảo toàn đoạn tiêu đề, số điều hoặc ghi chú ngắn nhưng chính xác.

### 6.2 Pseudocode

```python
def load_pdf_documents(file_path, ocr_service, config):
    pdf = open_pdf(file_path)
    documents = []
    failed_pages = []

    for page_index, page in enumerate(pdf.pages):
        native_text = normalize(page.get_text())
        native_candidate = native_text if is_readable_text(native_text) else ""

        if has_enough_text(native_text, config.min_native_chars):
            documents.append(Document(
                page_content=native_text,
                metadata=page_metadata(file_path, page_index, "native"),
            ))
            continue

        image = render_page_in_memory(page, dpi=config.dpi)
        if is_confidently_blank(page, image, config.blank_detection):
            warn_blank_page(file_path.name, page_index + 1)
            continue

        if not config.enabled:
            if native_candidate:
                documents.append(Document(
                    page_content=native_candidate,
                    metadata=page_metadata(file_path, page_index, "native_low_text"),
                ))
            else:
                failed_pages.append(page_index + 1)
            continue

        cache_key = make_cache_key(
            sha256(file_path), page_index, config.model,
            config.model_version, config.dpi, config.fingerprint,
        )
        cached = ocr_cache.get(cache_key)
        result = cached or ocr_service.recognize_page(
            image,
            page_index=page_index,
        )
        ocr_text = normalize(order_lines(result.lines))

        if has_enough_ocr_text(ocr_text):
            ocr_cache.put_atomic(cache_key, text_json_only(result))
            documents.append(Document(
                page_content=ocr_text,
                metadata=page_metadata(
                    file_path,
                    page_index,
                    "ocr",
                    ocr_model=result.model_name,
                    ocr_confidence=result.mean_confidence,
                ),
            ))
        elif native_candidate:
            warn_native_fallback(file_path.name, page_index + 1)
            documents.append(Document(
                page_content=native_candidate,
                metadata=page_metadata(file_path, page_index, "native_low_text"),
            ))
        else:
            failed_pages.append(page_index + 1)

    if failed_pages:
        raise OCRPagesFailedError(file_path.name, failed_pages)

    if not documents:
        raise NoUsableContentError(file_path.name)

    return documents
```

Pseudocode thể hiện thiết kế, không khẳng định tên API cụ thể trước khi khóa phiên bản PaddleOCR.

### 6.3 Quyết định cấu hình cần benchmark

| Quyết định | Khuyến nghị ban đầu | Trạng thái |
| --- | --- | --- |
| OCR toàn file hay từng trang | Chỉ OCR trang thiếu text | Đã chốt |
| Ngưỡng native text | Bắt đầu từ 50 ký tự để tương thích hành vi hiện tại; thử thêm 20/100 và tỷ lệ ký tự chữ/số | Đề xuất cần kiểm thử |
| DPI render | Bắt đầu 200 DPI; so sánh 200/250/300 | Đề xuất cần kiểm thử |
| Tier model | Small dùng cho spike; benchmark cùng Medium trước khi khóa model cuối | Đã chốt quy trình lựa chọn |
| Confidence threshold | Không lọc cứng ở vòng đầu; lưu score để hiệu chỉnh. Thử 0,3/0,5 nếu nhiễu cao | Đề xuất cần kiểm thử |
| Orientation | Thử bật document orientation cho trang xoay; đo chi phí. Unwarping không bật mặc định | Đề xuất cần kiểm thử |
| Phân loại trang trắng | Kết hợp tín hiệu PDF + pixel; chỉ bỏ khi chắc chắn, trường hợp không chắc coi là có nội dung | Đã chốt chính sách; ngưỡng cần kiểm thử |
| Native text ngắn | Giữ candidate; dùng khi OCR thất bại nếu text vượt sanity check | Đã chốt chính sách; sanity check cần kiểm thử |
| Bounding box | Chỉ dùng để sắp xếp dòng, không ghi vào Chroma | Đã chốt |
| Metadata OCR | `extraction_method`, `ocr_model`, `ocr_confidence`; `page` vẫn zero-based | Đã chốt schema định hướng |
| Cache kết quả | Chỉ text/JSON; SHA-256 file + page + model/version + DPI + cấu hình | Đã chốt |
| Cache model | Named volume riêng, mount vào `/app/model_cache/paddleocr`; đường dẫn thật được khóa sau spike | Đề xuất cần kiểm thử |
| OCR concurrency | Một tác vụ OCR/backend trong lần đầu | Đã chốt |
| Mục tiêu hiệu năng | PDF scan khoảng 20 trang ≤ khoảng 120 giây trên CPU demo; đo p50/p95/thời gian trang | Đã chốt mục tiêu benchmark, không hard-code timeout |

Không dùng một confidence threshold tùy ý để loại cả trang: score thấp vẫn có thể chứa điều/khoản quan trọng. Vòng đầu nên lưu score, đánh dấu cảnh báo và đo trên ground truth; chỉ lọc khi đã biết tác động CER/WER.

### 6.4 Metadata và số trang

Metadata tối thiểu phải tương thích hiện tại:

```json
{
  "source": "/app/data/ten-tai-lieu.pdf",
  "filename": "ten-tai-lieu.pdf",
  "page": 0,
  "extraction_method": "ocr",
  "ocr_model": "PP-OCRv6_small",
  "ocr_confidence": 0.0
}
```

Giá trị chỉ minh họa schema. `ocr_confidence` thực tế không được mặc định thành độ tin cậy của toàn bộ câu trả lời RAG. Với trang native, chỉ cần `extraction_method="native"`; tránh lưu `None` nếu phiên bản Chroma không chấp nhận kiểu đó.

### 6.5 Lỗi API và logging

- Khi ingestion thất bại do một hoặc nhiều trang có nội dung nhưng không đọc được, API trả lỗi nghiệp vụ và danh sách trang one-based, ví dụ `pages: [3, 7]`. Mã HTTP/chính xác schema lỗi sẽ được khóa khi triển khai, nhưng không trả stack trace hoặc đường dẫn nội bộ.
- Upload nhiều file giữ kết quả riêng theo filename; file lỗi phải có danh sách trang thất bại của chính file đó.
- Log tổng hợp gồm số trang native, OCR, native ngắn, trắng và thất bại; model/version, DPI, thời gian từng trang và tổng thời gian có thể ghi dưới dạng metric.
- Không log `rec_texts`, toàn bộ native text, prompt hoặc JSON cache vì có thể chứa nội dung quy chế/dữ liệu nội bộ.
- Chưa bổ sung trạng thái OCR hoặc confidence lên frontend trong giai đoạn đầu.

## 7. Dependency và Docker

### 7.1 Môi trường CPU mặc định

Docker CPU đã được chọn làm môi trường mặc định. Mục tiêu là giữ `python:3.11-slim` và Compose hiện tại làm đường chạy đầu tiên. Dependency cần nghiên cứu/khóa trong một container thử nghiệm sạch:

1. `paddleocr` có PP-OCRv6 (tài liệu chỉ ra mốc PaddleOCR 3.7).
2. `paddlepaddle` bản CPU tương thích Python 3.11 và kiến trúc image.
3. Dependency OpenCV/headless thực tế do resolver chọn; không thêm đồng thời nhiều biến thể OpenCV nếu chưa kiểm tra xung đột.
4. Các package hệ thống mà wheel cần trên `python:3.11-slim`.

Không cài `paddleocr[all]` vì phạm vi không dùng document parser. Không khóa một version cụ thể trong kế hoạch; quy trình đúng là dựng image thử, chạy `paddle.utils.run_check()`, import PaddleOCR, tải model, OCR fixture, sau đó xuất lock/constraints chính xác đã kiểm thử.

### 7.2 GPU tùy chọn

GPU là hướng mở rộng, không tạo profile GPU và không cài `paddlepaddle-gpu` trong lần triển khai đầu. Thiết kế phải giữ `device` trong cấu hình và factory OCR, không rải nhánh CPU trong loader. Khi mở rộng, dùng `paddlepaddle-gpu` thay cho `paddlepaddle` CPU, xác minh driver/CUDA/NVIDIA Container Toolkit và triển khai bằng Compose override hoặc profile riêng để đường CPU không bị ảnh hưởng.

### 7.3 Cache và volume

Đề xuất tách hai loại cache:

```text
paddle_models  → /app/model_cache/paddleocr
ocr_cache      → /app/ocr_cache
```

- `paddle_models` giữ trọng số/model runtime để không tải lại mỗi lần build/restart.
- `ocr_cache` chỉ giữ text/JSON cần thiết; không giữ ảnh render sau khi xử lý.
- Cache key/fingerprint phải gồm SHA-256 file, page index zero-based, model, model version, DPI và toàn bộ cấu hình ảnh hưởng kết quả.
- Cache đổi namespace/tự miss khi file, model hoặc cấu hình thay đổi; không tái sử dụng kết quả không cùng fingerprint.
- Xóa tài liệu qua `DELETE /admin/delete/{filename}` phải xóa namespace/cache entry liên quan sau khi xác định đúng file hash; lỗi xóa cache phải được cảnh báo nhưng không được làm sống lại tài liệu đã xóa.
- `ocr_cache` không commit Git, không mount vào Nginx/frontend và không có endpoint tải công khai.
- Vì cache chứa plaintext tài liệu, thư mục/file chỉ cấp quyền cho user backend (mục tiêu tương đương directory `0700`, file `0600` trên Linux nếu filesystem hỗ trợ). Đây là dữ liệu phát sinh có thể xóa và tạo lại từ PDF gốc.
- Không dùng chung với `hf_cache` hiện tại vì vòng đời và cơ chế vô hiệu hóa khác nhau.
- Đường dẫn cache mặc định của PaddleOCR có thể thay đổi theo version; triển khai phải dùng đường dẫn cấu hình rõ hoặc model directory rõ của version đã khóa. Hiện **chưa xác minh** đường dẫn cache cuối cùng.
- Cache không chứa file upload thừa; có quota, checksum, quyền ghi tối thiểu và cơ chế dọn theo LRU/tuổi sau khi được kiểm thử.

### 7.4 Khả năng chạy trong Docker hiện tại

Về phiên bản Python, image hiện tại nằm trong dải hỗ trợ. Tuy nhiên chưa thể kết luận Dockerfile chạy được chỉ từ tài liệu vì `slim` có thể thiếu shared library và dependency OCR có thể xung đột với Torch/Numpy/OpenCV. Cần một bước build thử trong giai đoạn khóa dependency; không thay đổi Docker production trước khi bước này đạt.

## 8. Danh sách file dự kiến ảnh hưởng

| File | Thay đổi dự kiến | Bắt buộc cho phương án B |
| --- | --- | --- |
| `backend/ocr_service.py` | Abstraction, lazy singleton, lock/semaphore, parse kết quả PP-OCRv6 | Có, file mới đề xuất |
| `backend/document_ingestion.py` | Đọc PDF/DOCX, fallback từng trang, clean, metadata, chunk | Có, file mới đề xuất |
| `backend/admin.py` | Gọi ingestion dùng chung, thread offload, transaction/rollback | Có |
| `scripts/build_index.py` | Giữ cho phát triển, cảnh báo deprecate `--reset`; nếu duy trì ghi index thì phải tôn trọng active/staging | Có, giới hạn phạm vi |
| `backend/requirements.txt` hoặc các file requirements CPU/GPU | Dependency đã khóa sau spike | Có |
| `.env.example` | Biến bật/tắt OCR, model, device, DPI, threshold, cache | Có |
| `Dockerfile.backend` | Dependency hệ thống/CPU và thư mục cache sau khi xác minh | Có thể |
| `docker-compose.yml` | Volume/model cache, OCR env, resource limit | Có thể |
| `.gitignore` | Bảo đảm cache local/fallback path không được commit nếu dùng bind path khi phát triển | Có thể |
| File Compose/Docker GPU riêng | Hướng mở rộng tương lai, không tạo trong lần đầu | Không |
| `tests/...` | Unit, integration, rollback, benchmark fixture | Có |
| `frontend/src/services/api.ts` và admin UI | Chỉ cần nếu chọn background job/status | Không cho phương án B ban đầu |
| `README.md` và tài liệu vận hành | Cấu hình, prewarm, lỗi, rebuild qua API | Có khi triển khai xong |

Rebuild runtime chính thức là `POST /admin/rebuild-index` với Bearer token admin. Không dùng `scripts/build_index.py --reset` trong vận hành vì script đang cố định collection `edurag_docs` và không tuân theo marker active/staging của runtime (`scripts/build_index.py:34`, `scripts/build_index.py:198-217`; `backend/rag_chain.py:84-130`). Script được giữ cho phát triển và phải có cảnh báo deprecate rõ. Không bắt buộc đưa toàn bộ OCR vào script nếu API rebuild đã dùng ingestion chung; nhưng nếu script còn ghi Chroma, nó không được tạo hoặc reset collection trái với marker active/staging.

## 9. Kế hoạch kiểm thử

### 9.1 Unit test

Định nghĩa protocol/interface OCR và inject fake:

```text
FakeOCRService
  calls: list[page_index]
  recognize_page(image, page_index):
    trả OCRPageResult cố định hoặc ném exception theo fixture
```

Unit test không import/tải PaddleOCR thật. Chỉ một nhóm smoke/integration riêng được đánh dấu mới dùng model thật và cache riêng.

| Mã | Trường hợp | Kết quả mong đợi |
| --- | --- | --- |
| U-01 | PDF có text đủ ở mọi trang | Fake OCR không được gọi |
| U-02 | PDF scan hoàn toàn | OCR được gọi đúng một lần mỗi trang cần đọc |
| U-03 | PDF kết hợp | Chỉ trang thiếu text gọi OCR |
| U-04 | DOCX | Giữ loader/metadata/chunk hiện tại; OCR không gọi |
| U-05 | OCR trả dòng lộn thứ tự | Ghép lại theo box theo quy tắc đã chọn |
| U-06 | OCR trả dòng rỗng | Không tạo chunk rỗng |
| U-07 | OCR exception | Ném lỗi miền rõ ràng; orchestrator rollback |
| U-08 | OCR disabled | PDF text/DOCX chạy; trang có nội dung không có native text làm ingestion bị từ chối, không bị bỏ âm thầm |
| U-09 | Gọi hai lần cùng model | Factory khởi tạo model đúng một lần |
| U-10 | Cache hit/miss | Hit không gọi model; đổi hash/model/config làm cache miss |
| U-11 | Trang trắng và trang có logo/nét/bảng | Chỉ trang chắc chắn trắng được bỏ; trường hợp không chắc được coi là có nội dung |
| U-12 | Native text ngắn, OCR thất bại | Giữ native text vượt sanity check với metadata/warning phù hợp |
| U-13 | Nhiều trang OCR thất bại | Error chứa đủ số trang one-based, không lộ text/path nội bộ |
| U-14 | Xóa tài liệu | Cache theo hash/namespace của tài liệu được xóa |

### 9.2 Integration test bắt buộc

| Mã | Dữ liệu | Xác minh |
| --- | --- | --- |
| I-01 | PDF text | Không gọi OCR; chunk và page không đổi |
| I-02 | PDF scan hoàn toàn | PP-OCRv6 được gọi; tạo chunk có nội dung |
| I-03 | PDF kết hợp | Chỉ OCR trang không đủ native text |
| I-04 | Scan tiếng Việt đủ dấu | So sánh ground truth, tính CER/WER và lỗi dấu |
| I-05 | Trang nghiêng/xoay 90/180/270° | Đánh giá cấu hình orientation, không tự tuyên bố đạt |
| I-06 | Scan chất lượng thấp | Ghi CER/WER, confidence, latency; không crash |
| I-07 | Trang có nội dung nhưng không nhận dạng được | Hủy toàn bộ ingestion; lỗi liệt kê đúng trang one-based; không tạo chunk/vector rác |
| I-08 | PDF vượt giới hạn | Bị từ chối theo 20 MB hiện tại; không gọi OCR |
| I-09 | OCR exception giữa file | Không còn file/vector/metadata dở dang |
| I-10 | Upload nhiều gồm text, DOCX và scan | Kết quả từng file đúng, batch không làm lẫn metadata |
| I-11 | Rebuild chứa scan | Staging đầy đủ mới activate; lỗi giữ collection cũ |
| I-12 | DOCX regression | Nội dung, filename và chunk không bị ảnh hưởng |
| I-13 | Metadata page/filename/source | `page` nội bộ zero-based; API hiển thị one-based; filename đúng |
| I-14 | Trang/chunk rỗng | Không có document/chunk rỗng trong Chroma |
| I-15 | Lỗi sau khi ghi vector | Bù trừ ID mới; không để vector mồ côi |
| I-16 | Model reuse | Nhiều trang/file không khởi tạo model lại |
| I-17 | `OCR_ENABLED=false` | Backend chạy, PDF text/DOCX hoạt động, scan bị từ chối rõ |
| I-18 | Backend startup chưa dùng OCR | Không tải model, không yêu cầu network model lúc startup |
| I-19 | Trang thật sự trắng xen giữa tài liệu | Bỏ trang, ghi warning, các trang có nội dung vẫn đúng số trang |
| I-20 | Native text dưới threshold + OCR lỗi | Không mất native text hợp lệ; áp dụng sanity check và warning |
| I-21 | Xóa tài liệu đã OCR | File, metadata, vector và OCR cache liên quan đều được dọn đúng phạm vi |
| I-22 | Fault sau Chroma upsert, trước/sau SQLite/activity | Xóa đúng vector ID/`ingestion_id` mới và file; dữ liệu cũ không bị ảnh hưởng |
| I-23 | Kiểm tra log | Có thống kê/trang lỗi nhưng không chứa toàn bộ OCR/native text |
| I-24 | Tải đồng thời khi OCR đang chạy | Concurrency OCR không vượt 1; request khác không làm event loop mất phản hồi |

### 9.3 Bộ benchmark nhỏ

Nhóm dự án tạo và kiểm tra thủ công ground truth từ tài liệu thực tế, dự kiến khoảng **30–50 trang**, có text chuẩn theo từng trang và bao phủ:

- PDF scan rõ 200–300 DPI.
- PDF scan mờ/nén mạnh.
- Văn bản nhiều dấu tiếng Việt.
- Văn bản có số điều, khoản, tỷ lệ, năm học.
- Trang có bảng.
- Trang hai hoặc nhiều cột.
- Trang xoay/nghiêng.
- PDF kết hợp text + scan.

Chỉ số phải ghi lại theo model/config:

| Chỉ số | Ý nghĩa |
| --- | --- |
| CER | Tỷ lệ lỗi ký tự so với ground truth |
| WER | Tỷ lệ lỗi từ |
| Độ chính xác dấu | Tỷ lệ ký tự/từ tiếng Việt giữ đúng dấu |
| Đúng số trang | Nội dung OCR được gắn đúng page |
| Thời gian/trang | p50, p95 và tổng thời gian file |
| RAM/VRAM đỉnh | Đo cả backend khi embedding và Ollama cùng hoạt động |
| Chunk hợp lệ | Tỷ lệ chunk không rỗng, đủ nội dung và đúng page |

Mục tiêu hiệu năng ban đầu là PDF scan khoảng 20 trang hoàn thành trong tối đa khoảng 120 giây trên máy demo CPU. Đây là mục tiêu benchmark, không phải timeout hard-code. Báo cáo phải có p50, p95, thời gian từng trang và tổng thời gian file cho Small/Medium. Nếu p95 thường xuyên vượt 120 giây, tài liệu thực tế quá dài hoặc upload làm API mất phản hồi, mới mở đánh giá background job.

Quy tắc chọn model cuối: chạy Small và Medium trên đúng cùng corpus, cùng DPI/cấu hình và cùng máy demo. Medium chỉ được chọn khi cải thiện rõ CER/WER và các lỗi quan trọng về dấu tiếng Việt, số điều/khoản, ngày tháng, trong khi thời gian/tài nguyên vẫn được nhóm chấp nhận. Mức “cải thiện rõ” cần được lượng hóa sau khi có baseline; không đổi model bằng cảm nhận từ vài trang.

## 10. Rủi ro và rollback

| Rủi ro | Giảm thiểu | Rollback vận hành |
| --- | --- | --- |
| Dependency xung đột Torch/Numpy/OpenCV | Build matrix trong image sạch, khóa constraints sau smoke test | Gỡ lớp OCR khỏi image/tag, dùng image CPU trước đó |
| Model download lỗi/mất mạng | Cache/pinned artifact, lazy load, health riêng | `OCR_ENABLED=false`; PDF text/DOCX tiếp tục |
| OCR sai điều/khoản | Benchmark, confidence chỉ để quan sát, nguồn vẫn theo trang | Tắt OCR và yêu cầu tài liệu text/pre-OCR đã duyệt |
| Timeout/upload mất phản hồi | Thread offload, concurrency=1, đo p50/p95 với mục tiêu 20 trang/120 giây | Tối ưu sau benchmark; chỉ chuyển phương án C khi đạt điều kiện đã chốt |
| RAM cạn | Giới hạn đồng thời bằng 1, Small cho spike, resource limit sau đo | Tắt OCR và quay lại image CPU trước đó |
| Sai thứ tự nhiều cột/bảng | Test box sorting; đánh dấu giới hạn | Không đưa PP-StructureV3 vào mặc định; xem xét mở rộng riêng |
| Nhận nhầm trang có nội dung là trắng | Bộ phân loại bảo thủ, test pixel/PDF object, trường hợp không chắc coi là có nội dung | Hủy ingestion thay vì bỏ trang; hiệu chỉnh ngưỡng bằng ground truth |
| Mất native text ngắn | Luôn giữ candidate; fallback về native nếu OCR lỗi và sanity check đạt | Không ghi vector cho phiên lỗi nếu cả hai nguồn không dùng được |
| Cache cũ/rò plaintext | Fingerprint đầy đủ, quyền filesystem tối thiểu, không public/commit, xóa theo tài liệu | Vô hiệu hóa/xóa đúng namespace cache OCR; cache có thể tạo lại |
| Vector mồ côi | Track `new_ids`/`ingestion_id`; fault injection ngay sau upsert và khi SQLite/activity lỗi | Xóa đúng vector mới và file tương ứng; không đụng dữ liệu ngoài ingestion |
| Rebuild mới active nhưng metadata lỗi | Điều chỉnh thứ tự commit/switch và lưu previous collection | Kích hoạt lại previous collection đã biết, không xóa dữ liệu cũ ngay |

Rollback không được xóa toàn bộ `chroma_db` hoặc volume. Mỗi ingestion phải giữ `ingestion_id` hoặc danh sách ID mới để compensation chính xác. Nếu SQLite hoặc activity log lỗi sau Chroma upsert, rollback DB, xóa vector mới, file tương ứng và cache mới của ingestion; không mở rộng thay đổi sang lịch sử chat hoặc nghiệp vụ khác. Rebuild sử dụng endpoint admin với staging/active, không chạy script reset trên dữ liệu vận hành.

Trong phạm vi document ingestion, metadata và activity cần nằm trong một transaction SQLite duy nhất hoặc có compensation tường minh, vì các helper hiện tự `commit()`. Trình tự dự kiến: chuẩn bị file/cache → tạo chunk/embedding → upsert vector mới và lưu IDs → `flush` metadata + activity → commit DB → xác nhận ingestion. Nếu DB commit lỗi, rollback session và xóa đúng vector/file/cache mới. Việc thay đổi transaction chỉ áp dụng cho upload/rebuild/delete tài liệu liên quan, không chỉnh nghiệp vụ tài khoản hoặc lịch sử chat.

## 11. Các giai đoạn triển khai

| Giai đoạn | Công việc | File dự kiến ảnh hưởng | Rủi ro | Cách kiểm tra | Tiêu chí hoàn thành |
| --- | --- | --- | --- | --- | --- |
| 1. Spike dependency CPU | Dựng matrix Python 3.11 với PP-OCRv6 Small; xác minh PaddleOCR/vi | requirements/constraints, tài liệu thử nghiệm | Resolver/xung đột wheel | Build image sạch, import, `run_check`, OCR fixture | Có bộ version CPU tái lập được; chưa đổi production |
| 2. Abstraction OCR | Protocol, result types, fake service, lazy factory | `backend/ocr_service.py`, tests | Model load lặp/thread unsafe | Unit test factory và exception | Model chỉ khởi tạo một lần khi cần |
| 3. Ingestion dùng chung | Tách load/clean/chunk khỏi router | `backend/document_ingestion.py`, `backend/admin.py` | Regression PDF/DOCX | Golden test text/chunk/metadata | PDF text và DOCX giữ hành vi mong đợi |
| 4. Fallback PDF | Native-first, giữ native ngắn, phân loại trắng bảo thủ, OCR từng trang | ingestion + OCR service | Sai trang/mất nội dung/thứ tự dòng | Test text/scan/mixed/blank/low-text | Chỉ bỏ trang chắc chắn trắng; lỗi liệt kê page one-based |
| 5. Metadata OCR | Thêm extraction method/model/confidence | ingestion, tests | Kiểu metadata Chroma không hợp lệ | Upsert/query test | Metadata primitive, page zero-based |
| 6. Upload đơn/nhiều | Thread offload và OCR concurrency=1; lỗi có page list | `backend/admin.py` | Event loop block/batch kéo dài | Concurrent API test + metric | API vẫn phản hồi; batch tách lỗi theo file |
| 7. Rebuild | Dùng ingestion chung trong staging | `backend/admin.py` | Activate/metadata không nguyên tử | Fault injection trước/sau activate | Lỗi không làm mất collection active hợp lệ |
| 8. Rollback | Track vector IDs/`ingestion_id`, DB rollback, cleanup file/cache | admin/ingestion | Vector/file mồ côi | Fault injection sau upsert và tại SQLite/activity | Không còn trạng thái dở dang; không ảnh hưởng dữ liệu khác |
| 9. Env và cache | OCR enable/model/device/DPI; cache text/JSON nguyên tử và xóa theo tài liệu | `.env.example`, Compose | Cache phình/rò plaintext/quyền file | Restart, hit/miss, invalidation, delete test | Cache không public/commit; đổi fingerprint tự miss |
| 10. Docker CPU | Bổ sung dependency/library đã xác minh | `Dockerfile.backend`, Compose | Image lớn/build lâu | Clean build + health + OCR smoke | CPU là đường chạy mặc định ổn định |
| 11. Giữ khả năng mở rộng GPU | Bảo đảm OCR factory nhận `device`, không tạo profile GPU | OCR config/factory | Phụ thuộc cứng CPU | Unit test cấu hình, review dependency boundary | Lần đầu chỉ CPU nhưng không phải viết lại nghiệp vụ để thêm GPU |
| 12. Test và benchmark | Chạy unit/integration + 30–50 trang; so sánh Small/Medium | `tests/`, benchmark assets/scripts | Ground truth sai | Review thủ công + cùng máy/corpus/config | Có report CER/WER/dấu/page/p50/p95/thời gian trang/RAM |
| 13. Tài liệu vận hành | Cấu hình, prewarm, lỗi, rebuild/rollback | `README.md`, docs | Hướng dẫn lệch runtime | Diễn tập trên máy sạch | Người khác triển khai CPU từ tài liệu được |

Thời lượng chỉ ước tính sau khi chốt fixture và môi trường: phương án B dự kiến 5–8 ngày làm việc gồm dependency spike, triển khai, test và benchmark; đây không phải tiến độ hoặc ngày hoàn thành đã cam kết.

## 12. Tiêu chí nghiệm thu

1. PDF có text và DOCX không gọi OCR, không regression metadata/page/chunk đã chốt.
2. PDF scan và PDF kết hợp chỉ OCR đúng trang cần thiết.
3. Trang chắc chắn trắng được bỏ và warning; trang có nội dung nhưng không đọc được làm hủy toàn bộ ingestion với danh sách page one-based.
4. Native text ngắn không bị mất chỉ vì thấp hơn threshold; OCR lỗi phải fallback về native candidate đạt sanity check hoặc fail rõ.
5. `filename`, `source`, `page` giữ tương thích; metadata nội bộ zero-based và lỗi/nguồn cho người dùng one-based.
6. Không tạo document/chunk rỗng.
7. Model lazy-load một lần và backend khởi động khi OCR chưa dùng; concurrency OCR bằng 1.
8. Có thể tắt OCR bằng biến môi trường mà PDF text/DOCX vẫn hoạt động.
9. Upload lỗi sau Chroma upsert không để file, metadata, cache hoặc vector mới dở dang; có fault injection cho SQLite/activity.
10. Rebuild lỗi không làm mất collection active trước đó; vận hành dùng `POST /admin/rebuild-index` với Bearer token admin.
11. `scripts/build_index.py --reset` được cảnh báo không dùng trong vận hành và không được ghi trái marker active/staging nếu còn duy trì.
12. Cache chỉ có text/JSON, key đầy đủ, tự miss khi thay đổi, không public/commit và được xóa khi xóa tài liệu.
13. Log không chứa toàn bộ nội dung OCR/native; lỗi admin nêu đúng trang thất bại.
14. Docker CPU là cấu hình duy nhất của lần đầu; thiết kế factory/config không ngăn bổ sung GPU sau này.
15. Dependency được khóa từ build/smoke test thực tế, không chỉ dựa trên version range.
16. Có unit test dùng fake OCR và integration test dùng fixture thật.
17. Có ground truth 30–50 trang được kiểm tra thủ công và báo cáo so sánh Small/Medium về CER, WER, lỗi dấu, số điều/khoản, ngày tháng, đúng trang, p50/p95, thời gian trang và RAM.
18. Benchmark ghi rõ việc đạt/chưa đạt mục tiêu PDF scan khoảng 20 trang trong khoảng 120 giây trên máy demo CPU; mốc này không được hard-code thành timeout.
19. Frontend không phải thay đổi để hiển thị OCR/confidence trong lần đầu.
20. PP-StructureV3/PaddleOCR-VL không xuất hiện trong dependency hoặc runtime; vấn đề bảng/nhiều cột chỉ được ghi thành hướng mở rộng nếu benchmark chứng minh cần.

## 13. Nội dung còn phải xác minh trong spike và benchmark

Các quyết định nghiệp vụ cần để bắt đầu spike dependency CPU đã đủ. Những nội dung dưới đây là đầu ra của spike/benchmark, không phải điều kiện phải trả lời trước khi bắt đầu:

1. Bộ version chính xác của `paddleocr`, `paddlepaddle` CPU, NumPy/OpenCV và system library chạy ổn trên `python:3.11-slim`.
2. Đường dẫn/cơ chế model cache được API của version đã khóa hỗ trợ chính thức.
3. Ngưỡng native text, sanity check, DPI, orientation và các ngưỡng phân loại trang trắng.
4. Mức cải thiện CER/WER được coi là “rõ” để chọn Medium thay Small sau khi có baseline; quyết định phải ưu tiên lỗi dấu, số điều/khoản và ngày tháng.
5. Dung lượng tối đa và chính sách retention/LRU cụ thể cho OCR cache plaintext.
6. Kết quả p50/p95 và độ phản hồi API trên máy demo; chỉ kết quả này mới quyết định có mở giai đoạn background job hay không.
7. Mức sai thứ tự thực tế ở bảng/nhiều cột; nếu nghiêm trọng mới lập kế hoạch mở rộng riêng, không tự động đưa công nghệ khác vào phạm vi.

Không còn vấn đề nghiệp vụ nào cản trở việc bắt đầu spike dependency CPU trong môi trường tách biệt. Việc triển khai mã nguồn chỉ bắt đầu khi có yêu cầu riêng; tài liệu này không ghi nhận rằng dependency, model hoặc benchmark đã được chạy.
