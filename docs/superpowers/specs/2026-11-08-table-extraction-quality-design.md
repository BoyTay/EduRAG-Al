# Thiết kế: Nâng chất lượng đọc bảng và đo được độ đúng của EduRAG

Ngày: 2026-11-08 · Trạng thái: chờ duyệt

## 1. Mục đích và lý do

Đề tài yêu cầu câu trả lời **bám sát nguồn, có trích dẫn** (mục 3–4) và có **bộ câu hỏi kiểm thử đo độ liên quan, đúng nguồn, thời gian phản hồi** (mục 6). Người làm đề tài lo nhất ở chỗ: chatbot trả lời đúng theo dữ liệu đã nạp, nhưng chưa chắc **dữ liệu trong bảng được đọc vào đã đúng** so với PDF gốc.

Kiểm tra ngày 2026-11-08 (chạy `document_ingestion._native_table_documents` trên 4 PDF trong `data/`) cho thấy:

- **Bảng đơn giản đọc đúng:** chuẩn đầu ra ngoại ngữ, quy đổi chứng chỉ (tiêu đề nhiều dòng), xếp loại học tập (nối qua 2 trang), xếp hạng năm học, danh sách ngành, biểu mẫu.
- **Bảng phức tạp đọc sai** (Sổ tay sinh viên, tr. 45–61):
  1. *Dòng vỡ:* một ô nhiều dòng bị tách thành nhiều "dòng bảng" có cột STT trống, ví dụ `HỒ SƠ: mẫu phụ lục 2)`, tách khỏi đối tượng (tr. 49–51).
  2. *Nối bảng qua trang sai:* trang sau không được nhận là phần tiếp nên dòng dữ liệu đầu tiên bị dùng làm tiêu đề cột. Ví dụ tr. 51: mức 100.000 đ/tháng mất nhãn đối tượng.
  3. *Bảng giả:* văn bản trình bày 2 cột bị nhận là bảng nên câu bị chẻ đôi, ví dụ `Mục đích và: nhiệm vụ của Hội Sinh viên` (tr. 52–58).
  4. *Mất nhãn cột:* danh bạ (tr. 60–61) nối bằng " - " không có nhãn, nên không phân biệt được điện thoại với email. Dòng bảng dài hơn `CHUNK_SIZE` (700) bị cắt giữa chừng, phần sau mất nhãn.
- **Lỗi của chính nguồn:** email của Phòng Quản lý đào tạo và Phòng Chính trị & CTSV bị đảo trong PDF. Hệ thống đọc đúng nguồn, nên không sửa trong code mà ghi vào báo cáo.
- **Chưa kiểm chứng:** file scan `1340-KH-DHDL…` (5 trang, đi qua OCR), và chunk thực tế đang nằm trong `chroma_db/`.

## 2. Mục tiêu

- G1. Có **bộ câu hỏi kiểm thử cho bảng** với đáp án chuẩn, kèm script chấm tự động. Script cho ra số liệu: đúng giá trị, đúng tài liệu/trang, tỉ lệ từ chối sai, thời gian phản hồi (p50/p95).
- G2. Sửa bộ đọc bảng để hết 4 lỗi ở mục 1 **mà không làm hỏng các bảng đang đúng**.
- G3. Có **số liệu trước/sau** (chạy G1 trước và sau G2) để đưa vào báo cáo và slide.
- G4. Admin có **trang kiểm tra dữ liệu nạp**: xem các đoạn hệ thống trích ra từ một tài liệu bên cạnh PDF gốc, và đánh dấu tài liệu "đã kiểm tra".
- G5 (tùy chọn). Thử nhanh một thư viện đọc bảng khác trên tr. 45–61 để có số liệu so sánh.

## 3. Ngoài phạm vi

- Không cho admin sửa tay nội dung chunk trong giao diện (khi PDF sai thì sửa PDF rồi nạp lại).
- Không đổi embedding, LLM, prompt hay ngưỡng từ chối trong đợt này. Bộ câu hỏi chỉ để đo; nếu số liệu cho thấy cần đổi thì làm đợt sau.
- Không đưa bộ đánh giá dùng tài liệu thật vào CI, vì `data/` bị gitignore.
- Không xử lý DOCX (DOCX hiện không tách bảng; chưa có tài liệu DOCX có bảng).

## 4. Phản mục tiêu (dù chạy được vẫn coi là hỏng)

- Bảng đang đúng (chuẩn đầu ra, quy đổi bậc, xếp loại, xếp hạng năm học) cho kết quả khác đi.
- Thêm model hoặc thư viện nặng khiến máy phổ thông (GPU 8 GB, CPU) nạp tài liệu chậm hẳn hoặc tốn RAM đáng kể.
- Sửa bằng luật gắn với tên file hoặc số trang cụ thể. Luật phải tổng quát theo hình dạng bảng.
- Bộ câu hỏi được "chỉnh cho đẹp số", tức là đáp án lấy từ output của hệ thống thay vì từ PDF gốc.

## 5. Ràng buộc

- Chạy cục bộ, LLM < 10B (`qwen3.5:9b`), giữ PyMuPDF làm bộ đọc chính.
- Test đơn vị dùng `unittest` như hiện có (`tests/test_document_ingestion.py`), và PDF tổng hợp tạo bằng PyMuPDF trong test, không phụ thuộc `data/`.
- Sau khi đổi code nạp, phải **tạo lại chỉ mục** (`POST /admin/rebuild-index`) thì câu trả lời mới thay đổi.

## 6. Những gì đã quyết định

Thứ tự làm do người làm đề tài chọn: **(1) bộ câu hỏi → (2) sửa bộ đọc bảng → chạy lại (1) → (3) trang kiểm tra cho admin → (4) thử thư viện khác nếu còn thời gian.**

### 6.1. Bộ câu hỏi kiểm thử (G1)
- Đặt ở `experiments/evaluation/`. README hiện đã trỏ tới thư mục này nhưng thư mục đang trống.
- Gồm `table_cases.json` và `run_eval.py`. Dùng lại cách chấm của `experiments/llm_benchmark/run_benchmark.py`: các nhóm từ khóa bắt buộc, từ cấm, kiểm tra nguồn và trang.
- Khoảng 25–30 câu, phủ:
  - các bảng đang đúng, để chống hồi quy;
  - 4 loại lỗi ở mục 1;
  - 3–5 câu về file scan 1340, để kiểm tra phần OCR;
  - 3–5 câu ngoài phạm vi, để kiểm tra từ chối.
- Mỗi câu có: `question`, `expected_values` (giá trị phải có), `forbidden` (giá trị sai dễ nhầm), `source_filename`, `pages`, `should_refuse`.
- Script gọi trực tiếp `rag_chain_instance` (giống benchmark), ghi JSON kết quả và in bảng tổng hợp gồm đúng giá trị %, đúng nguồn %, từ chối sai %, p50/p95 giây.
- Thêm một script phụ `dump_chunks.py`: xuất toàn bộ chunk của một tài liệu từ Chroma ra file đọc được. Script này dùng để kiểm chứng phần "chưa kiểm chứng" ở mục 1.

### 6.2. Sửa bộ đọc bảng (G2)
Chỉ sửa trong `backend/document_ingestion.py`, theo 4 luật tổng quát:
1. **Gộp dòng vỡ:** dòng có cột đầu (STT/TT) trống, ít ô có chữ, và ô có chữ trùng cột với ô của dòng trên thì nối text vào ô tương ứng của dòng trên, không tạo đoạn mới. Ô gộp dọc kiểu "Đạt" ở bảng xếp loại phải giữ nguyên hành vi hiện tại.
2. **Nối bảng qua trang:** bảng ở đầu trang có cùng số cột với bảng cuối trang trước, và dòng đầu không giống một dòng tiêu đề, thì là phần tiếp. Bỏ yêu cầu bảng trước phải "chạm đáy trang" khi các dấu hiệu khác đủ mạnh.
3. **Bảng giả:** bảng 2 cột mà phần lớn dòng chỉ có chữ ở một cột, hoặc nội dung là câu văn bị ngắt dòng, thì trả về văn bản thường (không tạo tài liệu bảng, không cắt chữ khỏi phần văn xuôi).
4. **Giữ nhãn:**
   - Tiêu đề kiểu "tên bảng" (một ô chiếm cả dòng) được dùng làm caption, không dùng làm nhãn cột.
   - Danh bạ và các bảng nhóm cột luôn ghi `Nhãn: giá trị`.
   - Dòng bảng dài hơn `CHUNK_SIZE` được chia sao cho mỗi phần vẫn mang tiền tố định danh của dòng (caption, STT, cột đối tượng).
- Mỗi luật có test đơn vị trên PDF tổng hợp tái hiện đúng hình dạng lỗi. 5 test bảng hiện có phải tiếp tục qua.

### 6.3. Trang kiểm tra dữ liệu nạp (G4)
- Backend: thêm `GET /admin/documents/{filename}/chunks`, chỉ admin gọi được. Endpoint đọc chunk từ collection đang hoạt động theo `filename`, trả về theo thứ tự `chunk_index`, gồm nội dung, trang, `extraction_method` và metadata bảng (`table_index`, `table_row`, `table_caption`, `table_continued`).
- Backend: thêm cột `reviewed_at` và `reviewed_by` vào `document_metadata` (migration nhẹ theo kiểu hiện có trong `init_db`), cùng `POST /admin/documents/{filename}/review` để đánh dấu hoặc bỏ đánh dấu.
- Frontend: từ bảng tài liệu ở trang quản trị, mở một khung chia đôi. Bên trái là PDF (dùng lại endpoint preview hiện có, nhảy trang bằng `#page=N`). Bên phải là danh sách chunk nhóm theo trang, chunk bảng hiển thị dạng `nhãn | giá trị`, chunk nghi lỗi được gắn cờ.
- Luật gắn cờ nghi lỗi: chunk bảng có nhãn `Cột N`, nội dung quá ngắn, hoặc nhãn dài bất thường.

## 7. Để lại cho người thực hiện

- Ngưỡng cụ thể cho các luật ở 6.2 (bao nhiêu ô trống thì là dòng vỡ, tỉ lệ nào thì là bảng giả). Ngưỡng chọn theo test và theo tr. 45–61.
- Bố cục chi tiết và style của khung kiểm tra, theo giao diện hiện có và skill thiết kế của dự án (`.agents/skills/design-taste-frontend`).
- Cách hiển thị số liệu trước/sau (bảng markdown trong `experiments/evaluation/README.md`).

## 8. Các quyết định do Claude tự đưa ra (cần người làm đề tài xem lại)

- Đáp án chuẩn **theo đúng PDF**, kể cả khi PDF sai (như email bị đảo). Lỗi của nguồn được ghi riêng trong README đánh giá.
- Không cho sửa chunk bằng tay (mục 3).
- Nhảy trang PDF bằng `#page=N` trên iframe sẵn có, thay vì render ảnh trang ở backend.
- Thư mục và tên file như ở 6.1. Endpoint và cột DB như ở 6.3.
- G5 chỉ là bản thử bỏ đi, kết quả chỉ ghi vào README đánh giá.
