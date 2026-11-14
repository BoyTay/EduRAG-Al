# Thiết kế: Kiểm tra và sửa trang scan đọc sai

Ngày: 2026-11-14 · Trạng thái: chờ duyệt

## 1. Mục đích và lý do

OCR có lúc đọc sai, nhất là với bảng scan phức tạp. Ví dụ là trang 5 của kế hoạch Tuần định hướng (`1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf`): đây là bảng 15 dòng scan nằm ngang. Sau các cải tiến ngày 14/11 (tự nhận hướng trang, đọc theo ô), hệ thống đọc đúng 14/15 dòng, nhưng vẫn còn lỗi như "Hỏa học", "z7/8/2026", số thứ tự đọc thành "Á", "®".

Hiện nay, khi dữ liệu đã nạp bị sai:
- Admin **không biết trang nào** cần xem lại. Màn Kiểm tra đoạn chỉ gắn cờ theo từng đoạn, và chưa hiện độ tin cậy OCR dù hệ thống đã lưu (`ocr_confidence`, `ocr_model`).
- Admin **không sửa được**. Cách duy nhất là xóa rồi nạp lại file, và OCR sẽ đọc sai đúng như cũ.
- Sinh viên **không được báo** khi câu trả lời lấy từ một trang scan chưa ai kiểm tra.

Thiết kế này khép kín vòng xử lý: **phát hiện → sửa → giữ bản sửa → báo người hỏi trong lúc chưa sửa**. Nó phục vụ mục 2 (làm sạch, chuẩn hóa dữ liệu) và mục 5 (trang quản trị tài liệu) của đề tài.

## 2. Mục tiêu

- **G1. Tự đánh dấu trang cần đối chiếu.** Trang đọc bằng OCR bị đánh dấu "cần đối chiếu" khi có ít nhất một dấu hiệu nghi lỗi (mục 6.2). Màn Kiểm tra đoạn hiện, cho từng trang: cách đọc, độ tin cậy, trạng thái và lý do nghi lỗi.
- **G2. Admin xác nhận hoặc sửa từng trang.**
  - "Trang này đúng": giữ nguyên chữ OCR, tắt cảnh báo.
  - "Sửa trang": ô soạn thảo hiện sẵn chữ hiện tại của trang. Admin sửa rồi lưu.
  - "Bỏ bản sửa": quay về chữ OCR. Mọi thao tác đều đảo ngược được.
- **G3. Bản sửa bền vững.** Bản sửa vẫn được dùng sau khi tạo lại chỉ mục, sau khi khởi động lại hệ thống, và sau khi nâng cấp mô hình OCR. Bản sửa tự hết hiệu lực khi file PDF bị thay bằng nội dung khác.
- **G4. Chỉ nạp lại tài liệu được sửa.** Lưu bản sửa hoặc xác nhận chỉ nạp lại đúng tài liệu đó (vài giây, vì OCR đã có trong cache), không tạo lại cả chỉ mục (khoảng 3 phút).
- **G5. Cảnh báo trong chat** (người dùng đã chọn phương án A). Trang "cần đối chiếu" vẫn được dùng để trả lời. Nhãn nguồn dưới câu trả lời có dấu cảnh báo và chú thích "Trích từ bản scan chưa được kiểm tra, nên đối chiếu bản gốc".
- **G6. Bấm nguồn để mở trang gốc.** Mọi nhãn nguồn trong chat, có cảnh báo hay không, đều bấm được và mở PDF đúng trang đó.
- **G7. Lưu vết.** Mỗi lần xác nhận, sửa hoặc bỏ sửa được ghi vào nhật ký hoạt động. Bản sửa lưu kèm chữ OCR gốc, người sửa và thời điểm sửa.

## 3. Ngoài phạm vi

- Sửa các trang PDF có sẵn lớp chữ (`native`, `native_table`). Ví dụ là các ô bảng bị dính chữ trong file Chuẩn đầu ra ("Chứngchỉ/Vănbằ ng"). Những trang này tách bảng thành nhiều đoạn có metadata riêng. Thay cả trang bằng văn bản thường sẽ mất cấu trúc đó, nên để đợt sau.
- Sửa nội dung file DOCX.
- Tải lên bảng Excel/CSV để thay một trang. Đợt này chỉ sửa bằng văn bản.
- Từ điển thuật ngữ tự sửa lỗi chính tả, và LLM gợi ý bản sửa (việc 4 và 5 trong đề xuất trước).
- Đổi prompt hệ thống. Cảnh báo chỉ hiện ở giao diện, không đưa vào ngữ cảnh gửi LLM, để không làm thay đổi kết quả của bộ đánh giá 28 câu đã đo.
- Tự điền ô gộp (cột hội trường gộp 5 dòng).
- Thay PDF scan bằng file gốc (Word/Excel). Việc này thuộc tính năng quản lý phiên bản (`2026-11-08-document-versioning-design.md`).

## 4. Phản mục tiêu (dù chạy được vẫn coi là hỏng)

- Bản sửa biến mất sau khi tạo lại chỉ mục, hoặc chỉ được áp ở một trong hai đường nạp (tải lên, tạo lại chỉ mục).
- Nạp lại sau khi sửa bị lỗi làm **xóa file PDF**, hoặc làm tài liệu mất hết đoạn trong chỉ mục. Khi lỗi, đoạn cũ phải còn nguyên.
- Bản sửa của file cũ bị áp sang một file mới cùng tên nhưng khác nội dung.
- Cảnh báo xuất hiện trên trang có lớp chữ sẵn, hoặc trên trang scan đọc tốt (độ tin cậy cao, không có dấu hiệu lỗi). Cảnh báo quá nhiều thì người dùng sẽ bỏ qua.
- Sinh viên thấy hoặc gọi được các thao tác sửa.
- Câu trả lời của chatbot thay đổi ở những câu hỏi không dùng trang scan.

## 5. Ràng buộc

- Giữ kiến trúc hiện có: SQLite với migration nhẹ trong `init_db()`, Chroma, FastAPI, React. Không thêm thư viện mới.
- `load_and_chunk_document` hiện không đụng tới cơ sở dữ liệu, và cần giữ như vậy để dễ test. Bản sửa được truyền vào hàm này dưới dạng tham số.
- Metadata trong Chroma chỉ nhận giá trị đơn (chuỗi, số, bool). Danh sách lý do nghi lỗi lưu thành chuỗi phân tách bằng dấu phẩy.
- Test bằng `unittest` theo mẫu hiện có (SQLite trong bộ nhớ, collection giả như `tests/test_chunk_inspection.py`). Frontend kiểm bằng `npm run build` và bấm thử.

## 6. Những gì đã quyết định

### 6.1. Cách làm đã chọn: sửa theo trang, bản sửa lưu ngoài chỉ mục

Các phương án đã cân nhắc:

| Phương án | Trade-off | Kết quả |
|---|---|---|
| **1. Sửa cả trang, lưu bản sửa trong SQLite theo mã băm file + số trang, áp khi nạp** | Bền khi tạo lại chỉ mục, dùng lại cấu trúc cache OCR theo trang. Đổi lại, sửa lỗi nhỏ vẫn phải mở cả trang (một trang scan chỉ 1–3 đoạn) | **Được chọn** |
| 2. Sửa từng đoạn trực tiếp trong Chroma | Nhanh cho lỗi nhỏ, nhưng tạo lại chỉ mục sẽ cắt đoạn khác đi, nên bản sửa không gắn lại đúng chỗ | Loại |
| 3. Chỉ cho thay PDF bằng file gốc Word/Excel | Chất lượng tốt nhất khi có file gốc, nhưng vô dụng khi chỉ có bản scan | Để làm cùng tính năng quản lý phiên bản |

### 6.2. Thế nào là "cần đối chiếu"

Một trang **đọc bằng OCR** (`extraction_method` là `tesseract` hoặc `ppocrv6`) bị đánh dấu khi có ít nhất một dấu hiệu sau. Mỗi dấu hiệu có mã riêng để hiển thị lý do:

| Mã | Điều kiện | Ví dụ ở trang 5 |
|---|---|---|
| `low_confidence` | Độ tin cậy OCR của trang dưới 0,85. Đây là cùng ngưỡng đang dùng để quyết định đọc lại theo ô (`LAYOUT_RETRY_CONFIDENCE`) | 0,84 |
| `garbled_text` | Chữ của trang bị `is_garbled` trong `chunk_inspection.py` đánh giá là chữ lỗi | Không |
| `row_number_gap` | Các dòng bắt đầu bằng số thứ tự (dạng `N \|`) có số bị thiếu hoặc nhảy cóc | 1, 2, 3, *Á*, 5, *®*, 7… |
| `malformed_date` | Có cụm gần giống ngày (`?/?/yyyy`) nhưng lẫn ký tự lạ | `z7/8/2026`, `[28/8/2026` |

Trang có lớp chữ sẵn không bao giờ bị đánh dấu.

**Trạng thái của trang:**
- `needs_review`: có dấu hiệu nghi lỗi, chưa ai xử lý.
- `confirmed`: admin bấm "Trang này đúng".
- `corrected`: đang dùng bản sửa tay.
- Không có giá trị: trang đọc tốt, hoặc là trang có lớp chữ sẵn.

**Cách quyết định trạng thái:**
- Trạng thái được tính lúc nạp tài liệu và ghi vào metadata của mọi đoạn thuộc trang đó, gồm:
  - `review_status`
  - `review_reasons` (chuỗi mã, phân tách bằng dấu phẩy)
  - `ocr_confidence` (đã có sẵn)
- Nếu trang có bản sửa thì trạng thái là `corrected`. Nếu admin đã xác nhận thì là `confirmed`. Hai trường hợp này không cần kiểm tra dấu hiệu nghi lỗi.

### 6.3. Giữ ranh giới dòng cho trang đọc theo ô

Hiện `normalize_text` gộp mọi khoảng trắng, kể cả xuống dòng. Vì vậy các dòng bảng dính vào nhau, ví dụ "…Hoàng Minh Tiến 2 | Khoa Sinh học…". Điều này làm hỏng kiểm tra `row_number_gap` và khiến admin khó đọc khi sửa.

Quyết định: với trang OCR, **giữ dấu xuống dòng giữa các dòng**, chỉ chuẩn hóa khoảng trắng bên trong từng dòng. Trang văn xuôi OCR cũng được giữ xuống dòng. Bộ tách đoạn đã có `"\n"` trong danh sách điểm cắt, nên sẽ ưu tiên cắt ở ranh giới dòng.

Việc này đổi nội dung đoạn của các trang scan, nên cần chạy lại bộ đánh giá 28 câu (`experiments/evaluation`) để chắc chắn kết quả không giảm (mục 8).

### 6.4. Lưu bản sửa và trạng thái xác nhận

Thêm bảng SQLite `page_reviews`:

| Cột | Ý nghĩa |
|---|---|
| `file_sha256` | Mã băm SHA-256 của file PDF. File đổi nội dung thì bản sửa tự không còn khớp |
| `page_index` | Số trang, bắt đầu từ 0 như metadata `page` |
| `status` | `confirmed` hoặc `corrected` |
| `corrected_text` | Chữ admin đã sửa, chỉ có khi `corrected` |
| `original_text` | Chữ OCR lúc admin bắt đầu sửa hoặc xác nhận, để đối chiếu và lưu vết |
| `filename` | Tên file lúc tạo, chỉ để hiển thị |
| `reviewed_by`, `reviewed_at` | Email admin, thời điểm theo UTC như các bảng khác |

- Mỗi cặp `(file_sha256, page_index)` có tối đa một dòng. Sửa lại thì ghi đè. "Bỏ bản sửa" hoặc "bỏ xác nhận" thì xóa dòng đó.
- Xóa tài liệu thì **không** xóa các dòng này. Nếu đúng file đó được nạp lại sau này, bản sửa vẫn dùng được. Các dòng mồ côi rất nhỏ, không cần dọn.

### 6.5. Áp bản sửa khi nạp

- `load_and_chunk_document` nhận thêm tham số `page_reviews`: một bảng tra `page_index → (status, corrected_text)`.
- Trong `_load_pdf_pages`, với một trang đọc bằng OCR:
  - Có `corrected`: bỏ qua OCR, dùng `corrected_text`, `extraction_method = "manual"`, `review_status = "corrected"`.
  - Có `confirmed`: dùng OCR như thường, `review_status = "confirmed"`.
  - Không có: chạy các kiểm tra ở mục 6.2.
- **Cả hai đường nạp** phải tra `page_reviews` theo mã băm file và truyền vào: `process_saved_document` (tải lên) và `rebuild_index` (tạo lại chỉ mục). Có test cho từng đường.

### 6.6. Nạp lại một tài liệu sau khi sửa

Viết hàm mới để nạp lại một tài liệu đã có, **không dùng `process_saved_document`**, vì hàm đó xóa file khi gặp lỗi. Hàm mới:
1. Nạp và tách đoạn lại tài liệu, có áp `page_reviews`.
2. Ghi đoạn mới theo cơ chế phiên bản sẵn có của `add_to_vector_store` (ID mới, giữ ID cũ để quay lại).
3. Cập nhật `chunk_count` trong `document_metadata`. **Không** reset `reviewed_at` cấp tài liệu.
4. Gặp lỗi ở bất kỳ bước nào thì xóa đoạn mới, giữ nguyên đoạn cũ và file, rồi trả lỗi cho admin.
5. Thành công thì xóa đoạn cũ (`finalize_vector_write`).

Thứ tự lưu: ghi `page_reviews` → nạp lại → commit. Nếu nạp lại lỗi thì rollback cả dòng `page_reviews`, để cơ sở dữ liệu và chỉ mục không lệch nhau.

Nếu đang tạo lại chỉ mục (`_rebuild_lock` đang giữ) thì từ chối thao tác với mã 409 và thông báo "Đang tạo lại chỉ mục, thử lại sau".

### 6.7. API (chỉ admin)

| Phương thức và đường dẫn | Việc |
|---|---|
| `GET /admin/documents/{filename}/pages` | Danh sách trang của tài liệu: số trang, cách đọc, độ tin cậy, `review_status`, `review_reasons`, có bản sửa hay không. Lấy từ metadata đoạn trong Chroma |
| `GET /admin/documents/{filename}/pages/{page}/text` | Chữ hiện tại của trang để đưa vào ô soạn thảo: bản sửa nếu có, nếu không thì chữ OCR từ cache OCR (đúng chữ trước khi cắt đoạn, không bị lặp phần chồng lấn giữa các đoạn) |
| `PUT /admin/documents/{filename}/pages/{page}/correction` | Lưu bản sửa (`text`), rồi nạp lại tài liệu |
| `DELETE /admin/documents/{filename}/pages/{page}/correction` | Bỏ bản sửa, rồi nạp lại tài liệu |
| `PUT /admin/documents/{filename}/pages/{page}/confirmation` | Đánh dấu trang đúng, rồi nạp lại tài liệu |
| `DELETE /admin/documents/{filename}/pages/{page}/confirmation` | Bỏ đánh dấu, rồi nạp lại tài liệu |

**Quy tắc chung:**
- Số trang trong đường dẫn bắt đầu từ **1**, giống nhãn "Tr. 5" người dùng nhìn thấy. Bên trong chuyển sang `page_index` (bắt đầu từ 0).
- Chỉ trang có `extraction_method` OCR, hoặc trang đang có bản sửa, mới được sửa hay xác nhận. Trang khác trả 422.
- Bản sửa rỗng, hoặc ít ký tự chữ-số hơn ngưỡng `sanity_min_chars`, trả 422. Không cho thay một trang bằng chuỗi rỗng.
- Bản sửa dài tối đa 20.000 ký tự (một trang A4 dày đặc khoảng 4.000 ký tự).
- Mỗi thao tác ghi một dòng vào nhật ký hoạt động: `page_corrected`, `page_correction_removed`, `page_confirmed`, `page_confirmation_removed`. Nội dung ghi gồm tên hiển thị của tài liệu và số trang.

### 6.8. Màn Kiểm tra đoạn (admin)

Màn này đã nhóm đoạn theo trang (`ChunkInspector.tsx`). Phần đầu của mỗi nhóm trang được bổ sung như sau:

```
Trang 5 · Bản scan · đọc theo ô · tin cậy 0,84        [Cần đối chiếu]
Lý do: số thứ tự đứt quãng · ngày sai định dạng
                                   [Trang này đúng]  [Sửa trang]
```

- **Nhãn trạng thái:**
  - "Cần đối chiếu": màu hổ phách.
  - "Đã xác nhận": màu xanh, kèm người và ngày xác nhận.
  - "Đã sửa tay": màu xanh, kèm người và ngày sửa, và nút "Bỏ bản sửa".
- **Bấm "Sửa trang":** mở ô soạn thảo thay cho danh sách đoạn của trang đó. PDF gốc vẫn hiện ở khung bên cạnh, đã có sẵn trong màn này. Có nút "Lưu và nạp lại" và "Hủy". Trong lúc nạp lại, hiện trạng thái đang xử lý và khóa các nút. Xong thì tải lại danh sách đoạn.
- **Bộ lọc** có thêm lựa chọn "Chỉ trang cần đối chiếu", cạnh bộ lọc "Chỉ hiện đoạn nghi lỗi" sẵn có.
- **Dòng tóm tắt** ở đầu màn có thêm số trang cần đối chiếu, ví dụ: "21 đoạn · 0 đoạn nghi lỗi · 1 trang cần đối chiếu".

Thêm vào đó, danh sách tài liệu trong trang quản trị hiện số trang cần đối chiếu của từng tài liệu, để admin biết nên mở tài liệu nào trước.

### 6.9. Chat: cảnh báo và mở trang gốc

**Phía backend:**
- `extract_sources` trả thêm hai trường cho mỗi nguồn: `needs_review` (true nếu có đoạn nào của trang đó đang `needs_review`) và `is_scan` (trang đọc bằng OCR).
- Lịch sử chat lưu nguồn theo cách hiện có. Câu trả lời cũ không có hai trường này thì giao diện coi như `false`.
- Sau khi admin sửa hoặc xác nhận, cảnh báo ở các câu trả lời **cũ** vẫn giữ nguyên. Cảnh báo đó phản ánh đúng dữ liệu tại thời điểm trả lời, nên không cần cập nhật lại.

**Phía giao diện** (`ChatMessage.tsx`):
- Nhãn nguồn có `needs_review` hiện thêm biểu tượng cảnh báo màu hổ phách. Di chuột hoặc chạm vào thì hiện chú thích: "Trích từ bản scan chưa được kiểm tra, nên đối chiếu bản gốc".
- Mọi nhãn nguồn, cả nguồn chính và các "trang liên quan", trở thành nút bấm. Bấm vào thì mở khung xem PDF ở đúng trang đó, dùng endpoint `/documents/{filename}/preview` sẵn có (mọi người dùng đăng nhập đều xem được) và cách mở PDF đã dùng trong `PreviewDrawer`.
- Với file DOCX, mở tài liệu mà không nhảy trang.

### 6.10. Các trường hợp biên (người viết thiết kế tự quyết)

- **Cache OCR của trang không còn**, ví dụ volume cache bị xóa. Khi đó `GET .../pages/{page}/text` cho OCR lại riêng trang đó (khoảng 1–8 giây), rồi trả kết quả.
- **Hai admin cùng sửa một trang:** bản lưu sau cùng thắng. Số admin ít nên không cần khóa.
- **Đánh giá 28 câu giảm sau thay đổi ở mục 6.3:** thu hẹp việc giữ xuống dòng, chỉ áp cho trang đọc theo ô (`model_name` có dạng `…+tesseract-vie`), rồi đo lại.
- **Triển khai:** các đoạn đang có trong chỉ mục chưa có `review_status`. Sau khi cập nhật mã cần tạo lại chỉ mục một lần. Ghi bước này vào hướng dẫn cập nhật.

## 7. Phần để người xây dựng tự quyết

- Tên hàm, tên module, cách chia file mã nguồn.
- Biểu thức chính xác cho `row_number_gap` và `malformed_date`. Điều kiện bắt buộc: phải bắt được các ví dụ ở trang 5, và không được bắt trang 1–4 cùng file (văn xuôi, chứa ngày hợp lệ như "12/8/2026").
- Cách mở PDF đúng trang: `#page=N` trên URL blob, hoặc cách khác chạy được trên Chrome/Edge.
- Bố cục chi tiết và màu sắc, theo phong cách hiện có của trang quản trị.
- Cách nhóm thông tin trang ở `GET .../pages`: tính từ metadata đoạn lúc gọi, hay lưu riêng.

## 8. Kiểm tra hoàn thành

- **Test đơn vị** cho:
  - Tính trạng thái và lý do theo bảng ở mục 6.2.
  - Áp bản sửa và xác nhận trong `_load_pdf_pages`.
  - Bản sửa không áp sang file khác mã băm.
  - Cả hai đường nạp (tải lên, tạo lại chỉ mục) đều áp bản sửa.
  - Nạp lại lỗi thì giữ đoạn cũ và file.
  - Từng API: quyền admin, mã lỗi 409/422, ghi nhật ký hoạt động.
  - `extract_sources` trả `needs_review` và `is_scan`.
- **Trên dữ liệu thật:**
  - Trang 5 của file Tuần định hướng hiện "Cần đối chiếu", có lý do `row_number_gap` và `malformed_date`.
  - Trang 1–4 của file đó, và mọi trang của ba tài liệu PDF có lớp chữ sẵn, không bị đánh dấu.
  - Sửa trang 5, sau đó tạo lại toàn bộ chỉ mục: bản sửa vẫn được dùng (`extraction_method = "manual"`).
  - Hỏi chatbot về lịch Tuần định hướng: trước khi sửa, nguồn có cảnh báo; sau khi xác nhận hoặc sửa, câu hỏi mới không còn cảnh báo. Bấm nguồn mở đúng trang 5.
- **Đánh giá:** chạy lại bộ 28 câu (`experiments/evaluation/run_eval.py`). Tỷ lệ đúng giá trị và đúng nguồn không được thấp hơn lần đo gần nhất (85,7% và 100%), vì mục 6.3 đổi cách tách đoạn của trang scan.
- `npm run build` thành công. Bộ test backend xanh toàn bộ.
