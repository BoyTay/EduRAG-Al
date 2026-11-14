# Kiểm tra và sửa trang scan đọc sai: kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Mục tiêu:** Trang scan nghi lỗi được tự đánh dấu. Admin xác nhận hoặc sửa từng trang, và bản sửa được giữ khi tạo lại chỉ mục. Chat cảnh báo khi nguồn là trang chưa được kiểm, và mở được đúng trang PDF gốc.

**Kiến trúc:**
- Các hàm kiểm tra chạy độc lập, không phụ thuộc phần nào khác (`page_review.py`).
- Lúc nạp tài liệu, các hàm này tính trạng thái của từng trang OCR và ghi vào metadata của đoạn trong Chroma.
- Bản sửa và xác nhận lưu ở bảng SQLite `page_reviews`, khóa theo mã băm file + số trang. Chúng được truyền vào `load_and_chunk_document` ở cả hai đường nạp: tải lên và tạo lại chỉ mục.
- Mỗi thao tác của admin nạp lại đúng một tài liệu bằng hàm riêng. Hàm này không bao giờ xóa file.

**Công nghệ:** FastAPI, SQLAlchemy (SQLite), Chroma, LangChain splitter, React + TanStack Query + Tailwind, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-14-ocr-page-review-design.md`

## Điều kiện trước khi bắt đầu

Công việc OCR trước đó (nhận hướng trang, cờ chữ lỗi, đọc lại bằng psm 3, đọc theo ô) đang nằm chưa commit trên nhánh `feat/ocr-orientation-garbage-flag`. Kế hoạch này dùng `LAYOUT_RETRY_CONFIDENCE` và `is_garbled` từ phần việc đó. Commit phần việc đó trước (theo quyết định của người dùng), rồi tạo nhánh `feat/ocr-page-review` từ đó.

Cách chạy test trên Git Bash, từ thư mục gốc repo: `PYTHONPATH=backend python -m unittest <module> -v`.

## Ràng buộc chung

- Ngưỡng "tin cậy thấp" là `0.85`. Dùng lại hằng `LAYOUT_RETRY_CONFIDENCE` của `backend/tesseract_service.py`, không khai báo số mới.
- Mã lý do nghi lỗi, đúng chính tả: `low_confidence`, `garbled_text`, `row_number_gap`, `malformed_date`.
- Giá trị `review_status`: `needs_review`, `confirmed`, `corrected`, hoặc không có (không ghi khóa vào metadata).
- `extraction_method` của trang có bản sửa là `"manual"`. Phương thức OCR là `{"tesseract", "ppocrv6"}`.
- Metadata Chroma chỉ chứa giá trị đơn. `review_reasons` là chuỗi nối bằng `","`.
- Số trang trong URL API bắt đầu từ 1. `page_index` trong cơ sở dữ liệu và metadata bắt đầu từ 0.
- Bản sửa phải có ít nhất `sanity_min_chars` ký tự chữ-số và dài tối đa 20.000 ký tự. Sai thì trả 422.
- Đang tạo lại chỉ mục (`_rebuild_lock` bị giữ) thì trả 409 với nội dung "Đang tạo lại chỉ mục, thử lại sau".
- Mã hoạt động trong nhật ký: `page_corrected`, `page_correction_removed`, `page_confirmed`, `page_confirmation_removed`.
- Chú thích cảnh báo trong chat, đúng nguyên văn: "Trích từ bản scan chưa được kiểm tra, nên đối chiếu bản gốc".
- Không đổi `SYSTEM_PROMPT`, `USER_PROMPT_TEMPLATE` và `format_docs`.
- Không thêm thư viện mới.

## Trọng tâm khi review

1. **Số trang ngoài phạm vi** (0, âm, hoặc lớn hơn số trang PDF): trả 404, không ghi gì. Test ở Task 5.
2. **Tài liệu DOCX** gọi các API trang: trả 422 "Chỉ sửa được trang PDF scan". Test ở Task 5.
3. **File PDF đã mất trên đĩa** nhưng metadata còn: trả 404, không đụng chỉ mục. Test ở Task 5.
4. **Bản sửa có nhiều dòng và ký tự `|`** (dán từ bảng): giữ nguyên xuống dòng và ký tự `|` trong đoạn được lập chỉ mục. Test ở Task 2.
5. **Trang vừa có bản sửa vừa có kết quả OCR trong cache:** luôn dùng bản sửa và không gọi OCR, kể cả khi cache trống. Test ở Task 2.

---

### Task 1: Hàm kiểm tra trang nghi lỗi

**Files:**
- Create: `backend/page_review.py`
- Test: `tests/test_page_review.py`

**Interfaces:**
- Consumes: `is_garbled(content: str) -> bool` từ `backend/chunk_inspection.py`; `LAYOUT_RETRY_CONFIDENCE` từ `backend/tesseract_service.py`.
- Produces:
  - `@dataclass(frozen=True) class PageOverride: status: str; corrected_text: str | None = None`. `status` là `"confirmed"` hoặc `"corrected"`.
  - `REVIEW_CONFIDENCE: float` (bằng `LAYOUT_RETRY_CONFIDENCE`).
  - `review_reasons(text: str, confidence: float | None) -> list[str]`: các mã theo đúng thứ tự `low_confidence, garbled_text, row_number_gap, malformed_date`, chỉ những mã xảy ra.
  - `row_number_gaps(text: str) -> bool`
  - `has_malformed_date(text: str) -> bool`

- [ ] **Step 1: Viết test fail**

Dùng hằng `PAGE5` là đoạn văn bản thật của trang 5, gồm 15 dòng, mỗi dòng một hàng. Chép từ chỉ mục hiện tại; các dòng mở đầu như sau:

```text
1 | |Khoa Toán - Tin học | |24/8/2026 | ThS. Hoàng Minh Tiến
2 | |Khoa Sinh học | 25/8/2026 | PGS.TS. Lê Thị Anh Tú
3 | |Khoa Hỏa học và Môi trường | A8B | |26/8/2026 | PGS.TS. Lê Thị Thanh Trân
Á | |Khoa Nông lâm | |z7/8/2026 | ThS. Đỗ Văn Khoa
5 | |Khoa Công nghệ thông tin | |28/8/2026 | ThS. Trần Thống
® | |Khoa Luật học | |24/8/2026 | TS. Võ Thị Thanh Linh
7 | lKhoa Quốc tế học | |25/8/2026 | TS. Hoàng Việt Bách Khoa
15 | |Khoa Ngữ văn và Lịch sử | [28/8/2026 | ThS. Văn Quang Viên
```

Dùng hằng `PROSE` là văn xuôi trang 1, có ngày hợp lệ và các mục đánh số trong câu:

```text
Số: 1340/KH-ĐHĐL, Lâm Đồng, ngày 12 tháng 8 năm 2026
3.3. Địa điểm: theo danh sách phân bố kèm theo; thời gian từ 24/8/2026 đến 28/8/2026.
1. Mục đích: giúp Tân sinh viên làm quen môi trường học tập.
2. Yêu cầu: đảm bảo an toàn, tiết kiệm.
```

Các test cần viết:
- `test_page5_has_row_number_gap_and_malformed_date`:
  ```python
  assertEqual(review_reasons(PAGE5, 0.84), ["low_confidence", "row_number_gap", "malformed_date"])
  ```
- `test_clean_prose_page_has_no_reasons`:
  ```python
  assertEqual(review_reasons(PROSE, 0.93), [])
  ```
- `test_confidence_at_threshold_is_not_low`:
  ```python
  assertNotIn("low_confidence", review_reasons(PROSE, 0.85))
  ```
- `test_missing_confidence_is_not_low`:
  ```python
  assertEqual(review_reasons(PROSE, None), [])
  ```
- `test_consecutive_numbers_have_no_gap`: dòng `"1 | a\n2 | b\n3 | c"` cho `row_number_gaps` trả `False`.
- `test_skipped_number_is_a_gap`: dòng `"1 | a\n2 | b\n4 | c"` cho `True`.
- `test_fewer_than_two_numbered_rows_is_never_a_gap`: dòng `"7 | a"` cho `False`.
- `test_header_row_is_not_a_broken_number`: `"'TT | Đơn vị | Ngày\n1 | a | x\n2 | b | y"` và `"STT | Đơn vị\n1 | a\n2 | b"` đều cho `False`. Bảng đọc đúng thì không bị cảnh báo vì dòng tiêu đề.
- `test_row_starting_with_long_text_is_ignored`: `"1 | a\nKhoa Kinh tế | HHTV\n2 | b"` cho `False`.
- `test_valid_dates_are_not_malformed`:
  ```python
  assertFalse(has_malformed_date("ngày 24/8/2026 và 05/09/2026"))
  ```
- `test_dates_with_stray_characters_are_malformed`: `"z7/8/2026"`, `"[28/8/2026"` và `"2l/8/2026"`, mỗi chuỗi đều cho `True`.
- `test_garbled_text_is_reported`: chuỗi rác `OCR_GARBAGE` (chép từ `tests/test_chunk_inspection.py`) với độ tin cậy 0.9 cho kết quả chứa `"garbled_text"`.

- [ ] **Step 2: Chạy, thấy fail**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_page_review -v`
Kỳ vọng: `ModuleNotFoundError: No module named 'page_review'`

- [ ] **Step 3: Viết `backend/page_review.py`**

- **`row_number_gaps`:** chỉ xét các dòng có chứa `|`. Lấy ô đầu (phần trước dấu `|` đầu tiên), bỏ khoảng trắng và dấu câu `'"[](). `.
  - Ô đầu là số nguyên 1–999: là số thứ tự.
  - Ô đầu dài 1–3 ký tự, không phải số, và không phải `TT`/`STT` (không phân biệt hoa thường): là "số thứ tự đọc hỏng" (`Á`, `®`, `lãi`).
  - Ô đầu khác (rỗng, chữ dài như "Khoa Kinh tế", hoặc `TT`/`STT`): bỏ qua dòng đó.
  - Có gap khi có từ 2 số thứ tự trở lên **và** gặp một trong hai trường hợp: có "số thứ tự đọc hỏng", hoặc dãy số không tăng liên tục đúng 1.
- **`has_malformed_date`:** tìm cụm `\S*\d{1,2}/\d{1,2}/\d{4}\S*`. Bỏ dấu câu cuối `.,;:)`. Ngày bị coi là hỏng khi phần còn lại không khớp đúng `\d{1,2}/\d{1,2}/\d{4}`.

- [ ] **Step 4: Chạy, thấy pass**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_page_review -v`
Kỳ vọng: tất cả `OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/page_review.py tests/test_page_review.py
git commit -m "feat(ocr): detect scanned pages that need human review"
```

---

### Task 2: Áp trạng thái và bản sửa khi nạp PDF

**Files:**
- Modify: `backend/document_ingestion.py`: `normalize_text` (dòng 100), `_page_document` (dòng 318), nhánh OCR trong `_load_pdf_pages` (dòng 769–900), `load_and_chunk_document` (dòng 924)
- Test: `tests/test_document_ingestion.py`

**Interfaces:**
- Consumes: `PageOverride`, `review_reasons` (Task 1).
- Produces:
  - `normalize_ocr_text(value: str | None) -> str`: chuẩn hóa khoảng trắng *trong* từng dòng, bỏ dòng rỗng, nối lại bằng `"\n"`.
  - `load_and_chunk_document(file_path, ocr_service=None, settings=None, cache=None, page_reviews: Mapping[int, PageOverride] | None = None) -> DocumentIngestionResult`
  - `read_page_ocr_text(file_path: Path, page_index: int, ocr_service=None, settings=None, cache=None) -> str`: chữ OCR của một trang, đã qua `normalize_ocr_text`. Đọc từ cache; cache không có thì OCR lại rồi ghi vào cache.
  - Metadata của đoạn trang OCR có thêm `review_status` và `review_reasons`, chỉ khi có giá trị.

- [ ] **Step 1: Viết test fail** (trong `DocumentIngestionTests`; dùng `self._pdf`, `FakeOCR` sẵn có)

- `test_ocr_page_keeps_line_breaks`: `FakeOCR` trả text `"1 | Khoa A\n2 | Khoa B"`. Đoạn được lập chỉ mục chứa `"1 | Khoa A\n2 | Khoa B"`.
- `test_low_confidence_ocr_page_needs_review`: `FakeOCR` có confidence 0.5. Khi đó `metadata["review_status"] == "needs_review"`, và `"low_confidence"` nằm trong `metadata["review_reasons"].split(",")`.
- `test_confident_clean_ocr_page_has_no_review_status`: confidence 0.93 với văn bản sạch. Khi đó `"review_status" not in metadata`.
- `test_native_page_never_gets_review_status`: dùng `self._pdf(..., ["native"])`. Khi đó không có khóa `review_status`.
- `test_confirmed_page_uses_ocr_and_is_confirmed`: truyền `page_reviews={0: PageOverride("confirmed")}`, confidence 0.5. Khi đó `review_status == "confirmed"`, không có `review_reasons`, và `extraction_method == "ppocrv6"`.
- `test_corrected_page_skips_ocr_and_uses_text`: dùng `page_reviews={0: PageOverride("corrected", "Bảng đã sửa\n1 | Khoa Hóa học")}`. Khi đó `fake.calls == 0`, `extraction_method == "manual"`, `review_status == "corrected"`, và đoạn chứa `"1 | Khoa Hóa học"`. Đây cũng là test cho mục 5 của phần review: trang có bản sửa không gọi OCR, kể cả khi cache trống.
- `test_corrected_text_keeps_pipes_and_newlines`: bản sửa `"A | B\nC | D"` cho ra đoạn chứa đúng `"A | B\nC | D"`. Đây là test cho mục 4 của phần review.
- `test_review_for_other_page_is_ignored`: PDF có 2 trang scan, `page_reviews={1: PageOverride("corrected", "Trang hai đã sửa")}`. Trang 0 vẫn đọc bằng OCR, trang 1 là `manual`.
- `test_read_page_ocr_text_uses_cache_then_ocr`: gọi `read_page_ocr_text` hai lần trên trang scan. `fake.calls == 1`, và kết quả bằng chữ OCR.

- [ ] **Step 2: Chạy, thấy fail**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_document_ingestion -v`
Kỳ vọng: các test mới fail (`unexpected keyword argument 'page_reviews'`, hoặc `KeyError: 'review_status'`). Các test cũ vẫn pass.

- [ ] **Step 3: Sửa mã**

- `_page_document` nhận thêm `normalize=normalize_text` và tham số `review: tuple[str, list[str]] | None`. Trang OCR và trang `manual` dùng `normalize_ocr_text`.
- Trong `_load_pdf_pages`, nhận `page_reviews`. Thứ tự xử lý cho trang cần OCR (sau bước bỏ trang trắng, trước bước `settings.ocr_enabled`):
  1. Có `corrected`: dùng `corrected_text`, phương thức `manual`, trạng thái `corrected`. `continue`, không gọi OCR.
  2. Không có: đọc OCR như hiện tại. Sau khi có `ocr_result`:
     - nếu là `confirmed`: trạng thái `confirmed`;
     - nếu không: tính `review_reasons(normalize_ocr_text(text), ocr_result.confidence)`. Không rỗng thì trạng thái `needs_review`.
- `load_and_chunk_document` truyền `page_reviews` xuống. DOCX bỏ qua tham số này.
- `read_page_ocr_text` dùng lại `_render_page`, `cache.read`/`cache.write` và `get_default_ocr_service()`, cùng mẫu như vòng nạp. `page_index` ngoài phạm vi thì ném `IndexError`.

- [ ] **Step 4: Chạy, thấy pass**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_document_ingestion -v`
Kỳ vọng: tất cả `OK`, kể cả các test cũ.

- [ ] **Step 5: Commit**

```bash
git add backend/document_ingestion.py tests/test_document_ingestion.py
git commit -m "feat(ingestion): apply page reviews and flag scanned pages needing review"
```

---

### Task 3: Bảng `page_reviews` trong SQLite

**Files:**
- Modify: `backend/db.py`: thêm model sau `DocumentMetadata` (dòng 81–101) và các hàm truy cập.
- Test: `tests/test_page_review_store.py`

**Interfaces:**
- Consumes: `PageOverride` (Task 1).
- Produces:
  - Model `PageReview`, bảng `page_reviews`. Các cột:
    - `id`
    - `file_sha256 String(64)`
    - `page_index Integer`
    - `status String(20)`
    - `corrected_text Text null`
    - `original_text Text null`
    - `filename String(255)`
    - `reviewed_by String(100)`
    - `reviewed_at DateTime`

    Ràng buộc `UniqueConstraint("file_sha256", "page_index")`. Bảng mới nên `create_all` tự tạo, không cần migration.
  - `get_page_overrides(db, file_sha256: str) -> dict[int, PageOverride]`
  - `get_page_review_rows(db, file_sha256: str) -> dict[int, PageReview]`
  - `upsert_page_review(db, file_sha256, page_index, status, filename, reviewed_by, original_text, corrected_text=None) -> PageReview`. Chỉ `flush`, không commit.
  - `delete_page_review(db, file_sha256, page_index, status: str) -> bool`. Chỉ xóa khi dòng có đúng `status`. Chỉ `flush`.

- [ ] **Step 1: Viết test fail**

Dùng SQLite trong bộ nhớ: `create_engine("sqlite://")`, rồi `Base.metadata.create_all`. Các test:
- `test_upsert_then_get_returns_override`: sau khi upsert `corrected` cho trang 4, `get_page_overrides(db, "a"*64) == {4: PageOverride("corrected", "sửa")}`.
- `test_second_upsert_overwrites_same_page`: hai lần upsert cùng `(hash, 4)` vẫn chỉ cho ra 1 dòng, mang `status` của lần sau.
- `test_other_file_hash_is_not_returned`: dòng của hash `"a"*64` không xuất hiện khi tra hash `"b"*64`.
- `test_delete_only_matching_status`: đang có `confirmed`. Gọi `delete_page_review(..., "corrected")` trả `False` và dòng vẫn còn. Gọi với `"confirmed"` trả `True`.

- [ ] **Step 2: Chạy, thấy fail**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_page_review_store -v`
Kỳ vọng: `ImportError: cannot import name 'PageReview'`

- [ ] **Step 3: Thêm model và bốn hàm vào `backend/db.py`**

`reviewed_at` mặc định là `datetime.utcnow`, giống các bảng khác.

- [ ] **Step 4: Chạy, thấy pass**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_page_review_store -v`
Kỳ vọng: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/db.py tests/test_page_review_store.py
git commit -m "feat(db): store page corrections and confirmations by file hash"
```

---

### Task 4: Áp bản sửa ở cả hai đường nạp, và nạp lại một tài liệu

**Files:**
- Modify: `backend/admin.py`: `process_saved_document` (dòng 238), `rebuild_index` (dòng 681, vòng lặp ở dòng 716); thêm hàm mới sau `finalize_vector_write`.
- Test: `tests/test_admin_ingestion.py` (dùng `FakeRag`, `FakeDb`, `FakeStore` sẵn có)

**Interfaces:**
- Consumes: `get_page_overrides` (Task 3); `load_and_chunk_document(..., page_reviews=...)` (Task 2); `sha256_file` từ `document_ingestion`.
- Produces:
  - `page_reviews_for(db, file_path: Path) -> dict[int, PageOverride]`: trả `{}` với file không phải `.pdf`.
  - `reingest_document(db, document: DocumentMetadata, action: str, entity_name: str, current_user: dict) -> int`: nạp lại tài liệu với `page_reviews_for`. Ghi đoạn bằng `add_to_vector_store`, đặt `document.chunk_count`, gọi `log_activity(..., commit=False)`, rồi `db.commit()` và `finalize_vector_write`. Trả về số đoạn.
    - Gặp lỗi: `db.rollback()`, `rollback_vector_write` nếu đã ghi, rồi ném lại lỗi. Không bao giờ xóa file và không đụng tới `reviewed_at`.
    - Hàm này giả định người gọi đang giữ `_rebuild_lock`.

- [ ] **Step 1: Viết test fail**

- `test_upload_passes_page_reviews_to_loader`: patch `admin.page_reviews_for` trả `{0: PageOverride("corrected", "x")}`, patch `load_and_chunk_document`. Sau khi gọi `process_saved_document`, `load.call_args.kwargs["page_reviews"]` bằng đúng dict đó.
- `test_rebuild_passes_page_reviews_to_loader`: giống test trên, nhưng cho `rebuild_index`.
- `test_reingest_success_replaces_vectors_and_commits`: collection có sẵn ID cũ `{"old"}`, cho `FakeCollection.get` trả ID đó. Sau khi gọi, `db.commits == 1`, `"old"` nằm trong `deleted`, `document.chunk_count == 1`, và `log_activity` được gọi với action truyền vào.
- `test_reingest_failure_keeps_old_vectors_and_file`: `load_and_chunk_document` ném `RuntimeError`. Kết quả: ném lại lỗi, `db.rollbacks == 1`, `self.file_path.exists()`, và `"old"` không nằm trong `deleted`.
- `test_reingest_commit_failure_removes_new_vectors`: `FakeDb(fail_commit=True)`. Kết quả: ID mới bị xóa, ID cũ còn, file còn.
- `test_page_reviews_for_docx_is_empty`: file `.docx` cho `{}`, không gọi `sha256_file`.

`FakeCollection.get` hiện luôn trả `{"ids": []}`. Thêm thuộc tính `existing_ids` để giả lập ID cũ.

- [ ] **Step 2: Chạy, thấy fail**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_admin_ingestion -v`
Kỳ vọng: các test mới fail (`AttributeError: module 'admin' has no attribute 'page_reviews_for'`).

- [ ] **Step 3: Sửa `backend/admin.py`**

- Hai chỗ gọi `load_and_chunk_document(file_path)`, ở dòng 250 và 718, đổi thành `load_and_chunk_document(file_path, page_reviews=page_reviews_for(db, file_path))`.
- Thêm `page_reviews_for` và `reingest_document` theo đúng các Interface ở trên.

- [ ] **Step 4: Chạy, thấy pass**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_admin_ingestion -v`
Kỳ vọng: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/admin.py tests/test_admin_ingestion.py
git commit -m "feat(admin): apply page reviews on upload/rebuild and reingest one document safely"
```

---

### Task 5: API trang cho admin

**Files:**
- Modify: `backend/admin.py`: endpoint mới sau `set_document_review` (dòng 511); `get_documents` (dòng 349) thêm số trang cần đối chiếu.
- Modify: `backend/chunk_inspection.py`: `list_document_chunks` trả thêm trường; thêm `summarize_pages`.
- Test: `tests/test_admin_page_review.py`; `tests/test_chunk_inspection.py`

**Interfaces:**
- Consumes: Task 2 (`read_page_ocr_text`), Task 3 (`upsert_page_review`, `delete_page_review`, `get_page_review_rows`), Task 4 (`reingest_document`, `_rebuild_lock`).
- Produces:
  - Mỗi đoạn trong `list_document_chunks` có thêm `ocr_model`, `ocr_confidence`, `review_status`, `review_reasons: list[str]`.
  - `summarize_pages(chunks: list[dict], reviews: dict[int, PageReview]) -> list[dict]`. Mỗi phần tử:
    ```
    { page: int (1-based), extraction_method, ocr_model, ocr_confidence, review_status,
      review_reasons: list[str], reviewed_by, reviewed_at, editable: bool }
    ```
    `editable` đúng khi phương thức thuộc OCR hoặc là `manual`.
  - Endpoint (mọi endpoint dùng `require_admin`; `{page}` là `int`, bắt đầu từ 1):
    - `GET /admin/documents/{filename}/pages` trả `{filename, pages, needs_review: int}`.
    - `GET /admin/documents/{filename}/pages/{page}/text` trả `{page, text, source: "correction" | "ocr"}`.
    - `PUT .../pages/{page}/correction` với body `{text: str}` (Pydantic `max_length=20000`) trả `{page, status: "corrected", chunk_count}`.
    - `DELETE .../pages/{page}/correction` trả `{page, status: null, chunk_count}`.
    - `PUT .../pages/{page}/confirmation` trả `{page, status: "confirmed", chunk_count}`.
    - `DELETE .../pages/{page}/confirmation` trả `{page, status: null, chunk_count}`.
  - Mỗi tài liệu trong `GET /admin/documents` có thêm `needs_review_pages: int`. Lấy bằng một lần `collection.get(where={"review_status": "needs_review"}, include=["metadatas"])`, rồi đếm số cặp `(filename, page)` khác nhau.

- [ ] **Step 1: Viết test fail**

`tests/test_chunk_inspection.py`:
- `test_summarize_pages_groups_by_page_and_marks_editable`: hai đoạn trang 4 (`tesseract`, `needs_review`, lý do `"low_confidence,row_number_gap"`) và một đoạn trang 0 (`native`). Kết quả có 2 trang. Trang 5 có `review_reasons == ["low_confidence", "row_number_gap"]` và `editable is True`. Trang 1 có `editable is False`.

`tests/test_admin_page_review.py`: gọi trực tiếp hàm endpoint giống cách `tests/test_admin_ingestion.py` làm. Dùng SQLite trong bộ nhớ cho `PageReview` và `DocumentMetadata`, patch `admin.reingest_document` (trả 3), patch `admin.DATA_PATH` sang thư mục tạm có file PDF scan 2 trang (tạo bằng `fitz` như `tests/test_document_ingestion.py`). Các test:
- `test_put_correction_saves_row_and_reingests`: trạng thái trả về là `"corrected"`, dòng `page_reviews` có `page_index == 0`, và `original_text` bằng chữ OCR (patch `admin.read_page_ocr_text`).
- `test_correction_with_too_few_characters_is_rejected`: `text=" .. "` cho ra `HTTPException` 422, không có dòng nào.
- `test_reingest_failure_rolls_back_review_row`: `reingest_document` ném lỗi, kết quả là không còn dòng nào trong `page_reviews`.
- `test_page_out_of_range_is_404`: trang `0` và trang `3` của PDF 2 trang đều cho 404, không ghi gì. Đây là test cho mục 1 của phần review.
- `test_docx_document_is_422`: tài liệu `.docx` cho 422 với "Chỉ sửa được trang PDF scan". Mục 2.
- `test_missing_file_on_disk_is_404`: có metadata nhưng không có file, cho 404, và `reingest_document` không được gọi. Mục 3.
- `test_native_page_cannot_be_corrected`: trang có `extraction_method == "native"` trong chỉ mục (patch `list_document_chunks`) cho 422.
- `test_rebuild_in_progress_is_409`: giữ `admin._rebuild_lock` trước khi gọi, kết quả 409 với nội dung "Đang tạo lại chỉ mục, thử lại sau".
- `test_get_text_prefers_correction`: khi có dòng `corrected`, `source == "correction"`.
- `test_delete_confirmation_when_none_is_404`: không có dòng `confirmed` thì trả 404.

- [ ] **Step 2: Chạy, thấy fail**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_admin_page_review tests.test_chunk_inspection -v`
Kỳ vọng: fail do thiếu `summarize_pages` hoặc thiếu endpoint.

- [ ] **Step 3: Viết mã**

- Một hàm phụ chung cho bốn endpoint ghi, theo thứ tự:
  1. Lấy tài liệu (`_get_document_or_404`).
  2. Kiểm tra `.pdf` (422), file tồn tại (404), và số trang nằm trong PDF (404).
  3. Lấy khóa `_rebuild_lock` theo kiểu không chờ (409).
  4. Kiểm tra trang được phép sửa: dựa vào `list_document_chunks` của trang đó, hoặc dòng `page_reviews` sẵn có (422).
  5. Ghi hoặc xóa dòng `page_reviews` (chỉ `flush`).
  6. Gọi `reingest_document(db, document, action, f"{name} · Tr. {page}", current_user)`.
  7. Thả khóa.

  Nếu `reingest_document` ném lỗi thì trả 500 "Không thể nạp lại tài liệu; dữ liệu cũ vẫn được giữ". Hàm đó đã tự rollback.
- `original_text` lấy từ `read_page_ocr_text` lúc ghi.
- Việc nạp lại chạy qua `run_in_threadpool` hoặc endpoint `def` đồng bộ, theo cùng mẫu với endpoint upload, để không chặn event loop.

- [ ] **Step 4: Chạy, thấy pass**

Chạy: `PYTHONPATH=backend python -m unittest discover -s tests -t .`
Kỳ vọng: `OK` (1 test bỏ qua là có sẵn từ trước).

- [ ] **Step 5: Commit**

```bash
git add backend/admin.py backend/chunk_inspection.py tests/test_admin_page_review.py tests/test_chunk_inspection.py
git commit -m "feat(admin): page review API for confirming and correcting scanned pages"
```

---

### Task 6: Nguồn trong chat có `needs_review` và `is_scan`

**Files:**
- Modify: `backend/rag_chain.py`: `extract_sources` (dòng 944)
- Test: `tests/test_rag_retrieval.py`

**Interfaces:**
- Produces: mỗi nguồn có thêm `needs_review: bool` (có ít nhất một đoạn của trang đó mang `review_status == "needs_review"`) và `is_scan: bool` (phương thức thuộc `{"tesseract", "ppocrv6", "manual"}`).

- [ ] **Step 1: Viết test fail**

- `test_sources_mark_page_needing_review`: hai đoạn cùng trang 4, một đoạn có `review_status="needs_review"`. Nguồn trang 5 có `needs_review is True` và `is_scan is True`.
- `test_native_source_is_not_scan_and_not_flagged`: đoạn `native` cho `needs_review is False` và `is_scan is False`.

- [ ] **Step 2: Chạy, thấy fail**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_rag_retrieval -v`
Kỳ vọng: `KeyError: 'needs_review'`

- [ ] **Step 3: Sửa `extract_sources`.** Không đổi prompt và không đổi `format_docs`.

- [ ] **Step 4: Chạy, thấy pass**

Chạy: `PYTHONPATH=backend python -m unittest tests.test_rag_retrieval -v`
Kỳ vọng: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/rag_chain.py tests/test_rag_retrieval.py
git commit -m "feat(chat): mark sources from scanned pages that still need review"
```

---

### Task 7: Giao diện admin: trạng thái trang, xác nhận, sửa

**Files:**
- Modify: `frontend/src/types/index.ts` (dòng 7–8): thêm trường vào `DocumentChunk`; thêm `PageSummary`; thêm `needs_review_pages?: number` vào `Document`.
- Modify: `frontend/src/services/api.ts` (gần dòng 115): thêm 6 hàm.
- Create: `frontend/src/components/admin/PageReviewBar.tsx`: phần đầu của nhóm trang, gồm nhãn, lý do và nút.
- Create: `frontend/src/components/admin/PageEditor.tsx`: ô soạn thảo với nút "Lưu và nạp lại" / "Hủy".
- Modify: `frontend/src/components/admin/ChunkInspector.tsx`: dùng hai component trên trong mỗi nhóm trang; thêm bộ lọc "Chỉ trang cần đối chiếu"; dòng tóm tắt có thêm "· N trang cần đối chiếu".
- Modify: `frontend/src/components/admin/DocumentTable.tsx`: hiện nhãn hổ phách "N trang cần đối chiếu" khi `needs_review_pages > 0`.

**Interfaces:**
- Consumes: các endpoint ở Task 5.
- Produces, trong `api.ts`:
  - `getDocumentPages(filename): Promise<{ pages: PageSummary[]; needs_review: number }>`
  - `getPageText(filename, page): Promise<{ text: string; source: "correction" | "ocr" }>`
  - `savePageCorrection(filename, page, text)`
  - `removePageCorrection(filename, page)`
  - `confirmPage(filename, page)`
  - `unconfirmPage(filename, page)`

- [ ] **Step 1: Viết type, các hàm API và hai component**

Nội dung chữ cố định:
- Nhãn trạng thái: "Cần đối chiếu", "Đã xác nhận", "Đã sửa tay".
- Tên lý do: `low_confidence` là "Độ tin cậy thấp", `garbled_text` là "Chữ lỗi", `row_number_gap` là "Số thứ tự đứt quãng", `malformed_date` là "Ngày sai định dạng".
- Nút: "Trang này đúng", "Sửa trang", "Bỏ bản sửa", "Bỏ xác nhận", "Lưu và nạp lại", "Hủy".
- Dòng thông tin: "Bản scan · {đọc theo ô | Tesseract | sửa tay} · tin cậy 0,84". Số thập phân dùng dấu phẩy.

Sau mỗi thao tác thành công, gọi lại (invalidate) các query `document-chunks`, `document-pages` và `documents`. Trong lúc chờ thì khóa các nút. Khi lỗi, hiện `detail` của API.

- [ ] **Step 2: Build**

Chạy: `cd frontend && npm run build`
Kỳ vọng: `✓ built`, không có lỗi TypeScript.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/services/api.ts frontend/src/components/admin
git commit -m "feat(admin-ui): show page review status and confirm or correct scanned pages"
```

---

### Task 8: Giao diện chat: cảnh báo và mở trang gốc

**Files:**
- Modify: `frontend/src/types/index.ts`: `Source` có thêm `needs_review?: boolean; is_scan?: boolean`.
- Create: `frontend/src/components/chat/SourcePreviewModal.tsx`: modal xem PDF. Dùng `getDocumentPreview` sẵn có, tạo URL blob, `iframe src={url + "#page=" + page}`. Với DOCX thì không thêm `#page`.
- Modify: `frontend/src/components/chat/ChatMessage.tsx` (dòng 29–43 gom nguồn; 61–70 nhãn nguồn chính; 95–105 trang liên quan).

**Interfaces:**
- Consumes: `Source.needs_review` (Task 6), `getDocumentPreview(filename)` sẵn có.

- [ ] **Step 1: Sửa mã**

- Khi gom nguồn theo file, giữ thêm `reviewPages: number[]` cho các trang có `needs_review`.
- Nhãn nguồn chính và từng nhãn "trang liên quan" đổi thành `<button>` mở `SourcePreviewModal` ở đúng trang đó.
- Trang thuộc `reviewPages` có biểu tượng `WarningCircle` màu hổ phách, kèm `title` và `aria-label` đúng nguyên văn: "Trích từ bản scan chưa được kiểm tra, nên đối chiếu bản gốc".
- Câu trả lời cũ không có `needs_review` thì coi như `false`.

- [ ] **Step 2: Build**

Chạy: `cd frontend && npm run build`
Kỳ vọng: `✓ built`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/components/chat
git commit -m "feat(chat-ui): warn on unreviewed scan sources and open the cited PDF page"
```

---

### Task 9: Triển khai, kiểm tra trên dữ liệu thật, đánh giá

**Files:**
- Modify: `README.md`: thêm vào mục cập nhật/nâng cấp câu "Sau khi cập nhật lên bản có kiểm tra trang scan, cần tạo lại chỉ mục một lần để các đoạn hiện có được gắn trạng thái kiểm tra".
- Create: `experiments/evaluation/results_page_review_x3.json` (kết quả đánh giá).

- [ ] **Step 1: Build và tạo lại chỉ mục**

```bash
docker compose up -d --build backend frontend
docker cp tmp/rebuild_local.py edurag_backend:/tmp/rebuild_local.py
MSYS_NO_PATHCONV=1 docker exec -w /app/backend edurag_backend python /tmp/rebuild_local.py
docker compose restart backend
```

Kỳ vọng: `'success': True`

- [ ] **Step 2: Kiểm tra trạng thái trên dữ liệu thật**

Gọi `GET /admin/documents/{file}/pages` cho bốn tài liệu (hoặc chạy `summarize_pages` trong container). Kỳ vọng:
- File 1340-KH: trang 5 là `needs_review`, lý do có `row_number_gap` và `malformed_date`.
- File 1340-KH: trang 1–4 không có trạng thái.
- Ba tài liệu PDF có lớp chữ sẵn: không trang nào có trạng thái.

Nếu trang 1–4 bị đánh dấu thì sửa ở Task 1 trước khi đi tiếp. Đây là yêu cầu không cảnh báo thừa trong spec.

- [ ] **Step 3: Đi trọn một vòng trên giao diện**

Đăng nhập admin, vào màn Kiểm tra đoạn của file 1340-KH:
1. Trang 5 hiện "Cần đối chiếu".
2. Hỏi chatbot (tài khoản sinh viên) "Khoa Công nghệ thông tin dự Tuần định hướng ngày nào, ai phụ trách?". Nguồn có biểu tượng cảnh báo. Bấm nguồn thì mở PDF ở trang 5.
3. Bấm "Sửa trang", sửa "Hỏa học" thành "Hóa học", rồi "Lưu và nạp lại". Nhãn chuyển sang "Đã sửa tay".
4. Tạo lại toàn bộ chỉ mục (Step 1, lệnh `rebuild_local.py`). Trang 5 vẫn là `manual` và vẫn có "Hóa học".
5. Hỏi lại câu ở bước 2. Câu trả lời mới không còn cảnh báo.
6. Bấm "Bỏ bản sửa". Trang quay về "Cần đối chiếu".

- [ ] **Step 4: Chạy bộ đánh giá 28 câu**, 3 lần, theo `experiments/evaluation/README.md`. Cần Ollama `qwen3.5:9b` đang chạy.

Kỳ vọng: đúng giá trị ≥ 85,7% và đúng nguồn = 100%.

Nếu điểm giảm, làm theo spec mục 6.10: chỉ giữ xuống dòng cho trang có `ocr_model` kết thúc bằng `+tesseract-vie`, thêm test cho trường hợp này ở Task 2, rồi đo lại.

- [ ] **Step 5: Commit**

```bash
git add README.md experiments/evaluation/results_page_review_x3.json
git commit -m "docs: record page review rollout and evaluation results"
```
