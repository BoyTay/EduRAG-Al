# Table Extraction Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đo được độ đúng của EduRAG trên câu hỏi về bảng, sửa 4 lỗi đọc bảng của PyMuPDF, có số liệu trước/sau, và cho admin một trang kiểm tra dữ liệu đã nạp.

**Architecture:** Bộ đánh giá (`experiments/evaluation/`) gọi trực tiếp `RAGChain` như benchmark hiện có. Phần chấm điểm là module thuần, có test. Bốn luật đọc bảng nằm trong `backend/document_ingestion.py`, mỗi luật là một hàm nhỏ, có test trên PDF tổng hợp. Module `backend/chunk_inspection.py` dùng chung cho script xuất chunk và endpoint admin. Frontend thêm một khung chia đôi trong trang quản trị.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy/SQLite, ChromaDB, PyMuPDF, unittest; React 19 + TypeScript + Vite + Tailwind 4 + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-11-08-table-extraction-quality-design.md`

## Global Constraints

- Chạy cục bộ, LLM < 10B (`qwen3.5:9b`). Giữ PyMuPDF làm bộ đọc chính. Không thêm model hay thư viện nặng vào `backend/requirements.txt`.
- Luật đọc bảng phải tổng quát theo hình dạng bảng. Cấm điều kiện theo tên file hoặc số trang.
- Bảng đang đúng (chuẩn đầu ra, quy đổi bậc, xếp loại qua 2 trang, xếp hạng năm học) phải cho **cùng output**. 5 test bảng hiện có trong `tests/test_document_ingestion.py` phải tiếp tục qua.
- Đáp án chuẩn lấy **từ PDF gốc**, không từ output hệ thống. PDF sai thì đáp án vẫn theo PDF, lỗi nguồn ghi vào README đánh giá.
- Không đổi embedding, LLM, prompt, ngưỡng từ chối. Không cho sửa tay chunk.
- Test dùng `unittest`, chạy bằng `PYTHONPATH=backend python -m unittest ...` từ gốc repo. PDF test tạo bằng PyMuPDF, không đọc `data/`.
- Sau khi đổi code nạp phải tạo lại chỉ mục (`POST /admin/rebuild-index`) trước khi đo lại.
- Commit kết thúc bằng dòng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Làm trên nhánh `feat/table-extraction-quality`, tạo từ HEAD hiện tại (`docs/readme-docker-quickstart`, vì README trỏ tới `experiments/evaluation/` nằm trên nhánh này).

## Review Focus

1. **Bảng kéo dài 3 trang trở lên:** phần thứ ba vẫn mang tiêu đề cột của phần đầu → test ở Task 5.
2. **Ô gộp dọc hợp lệ ở cột đầu** (kiểu "Đạt" bao nhiều dòng, dòng đủ ô) không được coi là dòng vỡ và bị gộp → test ở Task 4.
3. **Tài liệu không có chunk trong Chroma** (vừa upload lỗi, hoặc chưa rebuild) → endpoint trả `chunks: []`, không 500. Tên không có trong DB → 404 → test ở Task 9.
4. **Trang OCR hoặc DOCX không có metadata bảng/trang** → luật gắn cờ và frontend không lỗi khi thiếu khóa → test ở Task 9, kiểm tay ở Task 10.
5. **Ollama tắt giữa lúc chạy đánh giá** → case ghi `case_error`, chạy tiếp. Phần tổng hợp loại case lỗi khỏi tỉ lệ nhưng báo số lượng → test ở Task 1.

---

### Task 1: Module chấm điểm và script chạy đánh giá

**Files:**
- Create: `experiments/evaluation/__init__.py` (rỗng), `experiments/evaluation/scoring.py`, `experiments/evaluation/run_eval.py`, `experiments/evaluation/README.md`
- Test: `tests/test_evaluation_scoring.py`
- Commit kèm: spec và plan trong `docs/superpowers/`

**Interfaces:**
- Produces (`scoring.py`):
  - `fold(text: str) -> str`: bỏ dấu, casefold (như `_fold` của benchmark).
  - `load_cases(path: Path) -> list[dict]`: đọc JSON. Raise `ValueError` nêu `id` nếu case thiếu khóa bắt buộc `id, category, question, expected_values, forbidden, source_filename, pages, should_refuse`, hoặc `id` trùng.
  - `score_case(case: dict, answer: str, sources: list[dict], refusal_reason: str | None, elapsed: float) -> dict`: trả về `{"case_id", "category", "value_ok", "missing_values", "forbidden_found", "source_ok", "refusal_detected", "refusal_ok", "elapsed_seconds", "status": "ok"}`.
  - `summarize(records: list[dict]) -> dict`: trả về `{"total", "errors", "value_accuracy", "source_accuracy", "false_refusal_rate", "missed_refusal_rate", "p50_seconds", "p95_seconds", "by_category": {cat: value_accuracy}}`.
- Quy tắc chấm:
  - `expected_values` là `list[list[str]]`; mỗi nhóm đạt nếu có một biến thể xuất hiện trong `fold(answer)`.
  - `value_ok` khi mọi nhóm đạt **và** không có nhóm `forbidden` nào xuất hiện.
  - `source_ok` khi có source cùng `filename == source_filename` và `page ∈ pages` (pages 0-based như metadata).
  - `refusal_detected = refusal_reason is not None`.
  - Case `should_refuse=true`: `value_ok = source_ok = refusal_detected`.
  - Record `status == "case_error"` bị loại khỏi mọi tỉ lệ và đếm vào `errors`.
  - p50/p95 theo `statistics.quantiles(n=100)`; ít hơn 2 mẫu thì lấy chính giá trị đó.

- [ ] **Step 1: Tạo nhánh** `git switch -c feat/table-extraction-quality`
- [ ] **Step 2: Viết test thất bại** trong `tests/test_evaluation_scoring.py` (thêm `experiments/evaluation` vào `sys.path` ở đầu file):
  - `test_value_ok_requires_every_group_and_ignores_accents`: case `expected_values=[["5.5-6.5","5,5-6,5"],["IELTS"]]`, answer `"IELTS 5,5-6,5 tương đương bậc 4"` → `value_ok is True`.
  - `test_forbidden_value_fails_case`: `forbidden=[["4.0-5.0"]]`, answer chứa cả `5.5-6.5` và `4.0-5.0` → `value_ok is False`, `forbidden_found == [["4.0-5.0"]]`.
  - `test_source_ok_needs_same_file_and_page`: sources `[{"filename":"A.pdf","page":2}]`, case `source_filename="A.pdf", pages=[2]` → True; `pages=[3]` → False.
  - `test_refusal_case_scores_on_refusal_only`: `should_refuse=True`, `refusal_reason="low_score=0.1"` → `value_ok and source_ok and refusal_ok`.
  - `test_summarize_excludes_errors_and_reports_count`: 3 record ok (2 đúng) + 1 `{"status":"case_error"}` → `errors == 1`, `value_accuracy == round(2/3, 4)`.
  - `test_false_refusal_rate_counts_refusals_on_answerable_cases`: 4 case `should_refuse=False`, 1 bị từ chối → `false_refusal_rate == 0.25`.
  - `test_load_cases_rejects_duplicate_ids_and_missing_keys`: hai trường hợp đều `assertRaises(ValueError)` và message chứa `id`.
- [ ] **Step 3: Chạy** `PYTHONPATH=backend python -m unittest tests.test_evaluation_scoring -v`. Kỳ vọng: FAIL vì `ModuleNotFoundError: scoring`.
- [ ] **Step 4: Viết `scoring.py`** theo Interfaces.
- [ ] **Step 5: Chạy lại.** Kỳ vọng: 7 test PASS.
- [ ] **Step 6: Viết `run_eval.py`.**
  - CLI: `--cases` (mặc định `experiments/evaluation/table_cases.json`), `--output` (bắt buộc), `--case-id` (lặp được), `--timeout` (180).
  - Gọi `RAGChain().initialize()`, rồi `await asyncio.wait_for(chain.achat(question, document_filename=case.get("document_filename")), timeout)`.
  - Exception thì ghi `{"case_id", "category", "status": "case_error", "error": repr(exc)}` và chạy tiếp.
  - Ghi JSON `{"started_at", "model": LLM_MODEL, "results": [...], "summary": summarize(...)}` sau mỗi case, cuối cùng in summary dạng bảng.
  - Lấy `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` mặc định "1" như benchmark.
- [ ] **Step 7: Viết `README.md`.** Mục đích, cách chạy (`$env:PYTHONPATH="backend"; python experiments/evaluation/run_eval.py --output experiments/evaluation/results_before.json`), ý nghĩa từng chỉ số, mục "Lỗi của tài liệu nguồn" (email Phòng QLĐT ↔ Phòng CT&CTSV bị đảo ở Sổ tay tr. 60), và mục "Kết quả trước/sau" để trống.
- [ ] **Step 8: Commit** `git add experiments/evaluation tests/test_evaluation_scoring.py docs/superpowers && git commit -m "feat(eval): add table evaluation scoring and runner"`

### Task 2: Module đọc chunk dùng chung và script xuất chunk

**Files:**
- Create: `backend/chunk_inspection.py`, `experiments/evaluation/dump_chunks.py`, `experiments/evaluation/audit_tables.py`
- Test: `tests/test_chunk_inspection.py`

**Interfaces:**
- Produces (`chunk_inspection.py`):
  - `list_document_chunks(collection, filename: str) -> list[dict]`: gọi `collection.get(where={"filename": filename}, include=["documents", "metadatas"])`, trả list sắp theo `(chunk_index or 0, page or 0)`. Mỗi item: `{"id", "content", "page", "extraction_method", "table_index", "table_row", "table_caption", "table_continued", "flags"}`. Khóa thiếu thì là `None` (riêng `table_continued` là `False`).
  - `flag_chunk(content: str, metadata: dict) -> list[str]`, các cờ theo thứ tự:
    - `"generic_label"` nếu khớp `r"\bCột \d+:"`;
    - `"too_short"` nếu là chunk bảng (`extraction_method == "native_table"`) và `len(content) < 25`;
    - `"long_label"` nếu chunk bảng có một phần (tách theo `"; "`, phần trước dấu `:` đầu tiên, bỏ caption `[...]` ở đầu) dài hơn 60 ký tự.
- `dump_chunks.py --filename X [--output path]`: mở collection đang hoạt động bằng `rag_chain.get_vector_store()`, in mỗi chunk dạng `p{page+1} [{method}] {flags} | {content}`.
- `audit_tables.py <output.txt>`: chính script kiểm tra ngày 2026-11-08 (bảng thô ↔ đoạn sẽ lập chỉ mục cho mọi PDF trong `DATA_PATH`), dùng để so trước/sau ở Task 8.

- [ ] **Step 1: Viết test thất bại** với `FakeCollection.get` trả dict cố định:
  - `test_chunks_sorted_by_chunk_index`: metadatas chunk_index 2, 0, 1 → nội dung trả về theo thứ tự 0, 1, 2.
  - `test_missing_metadata_keys_become_none`: metadata chỉ có `{"filename": "a.docx"}` → `page is None`, `table_continued is False`, `flags == []`.
  - `test_flags_generic_label_short_and_long_label`: ba chunk native_table: `"Cột 2: x"` → chứa `"generic_label"`; `"TT: 1"` → `"too_short"`; `"Một nhãn rất dài ... (61 ký tự): giá trị"` → `"long_label"`.
  - `test_caption_prefix_is_not_a_long_label`: `"[Xếp loại học tập theo học kỳ, năm học hoặc điểm trung bình chung tích lũy] Xếp loại: Đạt - Giỏi; Thang điểm 4: Từ 3,20 đến 3,59"` → `flags == []`.
  - `test_empty_collection_returns_empty_list`: `get` trả `{"ids": [], "documents": [], "metadatas": []}` → `[]`.
- [ ] **Step 2: Chạy** `PYTHONPATH=backend python -m unittest tests.test_chunk_inspection -v`. Kỳ vọng: FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Viết `chunk_inspection.py`.**
- [ ] **Step 4: Chạy lại.** Kỳ vọng: 5 PASS.
- [ ] **Step 5: Viết `dump_chunks.py` và `audit_tables.py`.** Bản `audit_tables.py` cũ ở scratchpad của phiên trước, viết lại vào repo, đọc `DATA_PATH` từ env.
- [ ] **Step 6: Kiểm tra bằng tay:**
  - `PYTHONPATH=backend python experiments/evaluation/dump_chunks.py --filename So_tay_sinh_vien.pdf --output experiments/evaluation/chunks_before_so_tay.txt` chạy không lỗi, có dòng `p51`.
  - Chạy tương tự cho `1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf` và đọc phần OCR. Ghi nhận xét (dấu tiếng Việt, bảng trong file scan) vào README mục "Kiểm chứng chunk thật".
- [ ] **Step 7: Commit** `git commit -m "feat(eval): add shared chunk inspection and dump/audit scripts"` (không commit các file `chunks_*.txt`; thêm `experiments/evaluation/chunks_*.txt` vào `.gitignore`).

### Task 3: Bộ câu hỏi và kết quả "trước"

**Files:**
- Create: `experiments/evaluation/table_cases.json`, `experiments/evaluation/results_before.json`
- Modify: `experiments/evaluation/README.md`
- Test: `tests/test_evaluation_scoring.py` (thêm 1 test)

**Interfaces:**
- Consumes: `load_cases`, `run_eval.py` (Task 1).
- Produces: `table_cases.json` theo schema Task 1. `category` thuộc `{"simple_table", "wrapped_rows", "page_continuation", "prose_layout", "labels", "ocr_scan", "refusal"}`.

Số lượng: 8 `simple_table`, 3 cho mỗi loại `wrapped_rows`, `page_continuation`, `prose_layout`, `labels`, 4 `ocr_scan`, 4 `refusal` (tổng 28). Câu hỏi viết như sinh viên hỏi thật, không chép tiêu đề bảng.

Giá trị đã thấy trong lần kiểm tra (đối chiếu lại với ảnh trang trước khi dùng):

| Câu hỏi gợi ý | Giá trị | File / trang (1-based) |
|---|---|---|
| IELTS bao nhiêu thì tương đương bậc 4? | 5.5-6.5 | Chuan_dau_ra… / 3 |
| Hệ cử nhân ngành khác cần chuẩn ngoại ngữ bậc mấy? | 3/6 | Chuan_dau_ra… / 2 |
| GPA thang 4 bao nhiêu thì xếp loại giỏi? | 3,20 đến 3,59 | So_tay / 30 |
| Tích lũy bao nhiêu tín chỉ thì là sinh viên năm hai? | 35 đến dưới 70 | So_tay / 30 |
| Thạc sĩ Toán giải tích học mấy năm? | 2 | So_tay / 12 |
| SV dân tộc thiểu số hộ nghèo được hỗ trợ chi phí học tập bao nhiêu? | 60% mức lương cơ sở; 10 tháng | So_tay / 49 |
| SV dân tộc thiểu số vùng cao được trợ cấp bao nhiêu mỗi tháng? | 140.000 | So_tay / 50 |
| SV dân tộc rất ít người được hỗ trợ học tập bao nhiêu? | 100% mức lương cơ sở | So_tay / 49 |
| Đoàn trường có bao nhiêu chi đoàn? | 159 | So_tay / 52 |
| Số điện thoại Phòng Tài chính? | 0263. 3820566 | So_tay / 60 |
| Email khoa Công nghệ thông tin? | it@dlu.edu.vn | So_tay / 61 |

- [ ] **Step 1: Soạn `table_cases.json`.** Với mỗi câu, mở trang PDF bằng PyMuPDF (`page.get_pixmap(dpi=110).save(...)`) và đọc ảnh để lấy giá trị. Không lấy từ chunk. Câu `ocr_scan` lấy từ file 1340. Câu `refusal` hỏi điều tài liệu không có (ví dụ học phí ngành Y, lịch thi IELTS tại trường). Đặt `forbidden` là giá trị cột hoặc dòng bên cạnh dễ nhầm.
- [ ] **Step 2: Viết test** `test_table_cases_file_is_valid`: `load_cases(<repo>/experiments/evaluation/table_cases.json)` không raise, có đủ 28 case, mỗi category đạt số lượng ở trên.
- [ ] **Step 3: Chạy** `PYTHONPATH=backend python -m unittest tests.test_evaluation_scoring -v`. Kỳ vọng: 8 PASS.
- [ ] **Step 4: DỪNG — người làm đề tài rà từng câu hỏi và đáp án với PDF.** Sửa theo góp ý trước khi chạy.
- [ ] **Step 5: Chạy "trước"** với chỉ mục hiện tại và Ollama đang chạy: `$env:PYTHONPATH="backend"; python experiments/evaluation/run_eval.py --output experiments/evaluation/results_before.json`. Kỳ vọng: in summary, `errors == 0`.
- [ ] **Step 6: Ghi bảng summary và `by_category`** vào README mục "Kết quả trước/sau" (cột "Trước").
- [ ] **Step 7: Commit** `git commit -m "feat(eval): add 28 table cases and baseline results"`

### Task 4: Luật 1, gộp dòng vỡ

**Files:**
- Modify: `backend/document_ingestion.py` (`_native_table_documents`, khoảng dòng 397–546)
- Test: `tests/test_document_ingestion.py` (thêm vào `DocumentIngestionTests`, dùng `_grid`/`_write_cells`)

**Interfaces:**
- Produces: `_merge_wrapped_rows(rows: list[list[str]], column_count: int) -> list[list[str]]`.
  - Chỉ áp dụng cho **bảng đánh số**, tức tiêu đề cột đầu chuẩn hóa thuộc `{"tt", "stt"}`.
  - Dòng có ô đầu trống được nối vào dòng trước: mỗi ô có chữ nối vào cùng cột bằng một dấu cách.
  - Dòng đầu tiên của phần dữ liệu không có dòng trước thì giữ nguyên.
  - Gọi trên `rows[header_end:]` sau khi đã `normalize_text`.
- `state["last"]` thêm khóa `"last_number": str` (giá trị ô đầu của dòng cuối). Dòng đầu của phần tiếp (Task 5) có ô đầu trống thì được điền `last_number` và thêm metadata `table_row_continued=True`.

- [ ] **Step 1: Viết test thất bại:**
  - `test_wrapped_cell_lines_are_merged_into_their_numbered_row`: bảng 4 cột `TT | Doi tuong | Ho so | Ghi chu`; dòng `("1","Sinh vien khuyet tat","1. Don de nghi","Xet 1 lan")`, rồi `("","","(theo mau phu luc 1)","")`, `("","","2. Ban sao giay khai sinh","")`. Kỳ vọng: đúng 1 chunk `native_table`, chứa `Ho so: 1. Don de nghi (theo mau phu luc 1) 2. Ban sao giay khai sinh` và `Doi tuong: Sinh vien khuyet tat`.
  - `test_full_rows_with_blank_first_cell_in_unnumbered_table_are_not_merged`: bảng `Xep loai | Muc | Thang diem 4`; dòng `("Dat","Gioi","Tu 3,20 den 3,59")`, `("","Kha","Tu 2,50 den 3,19")`. Kỳ vọng: 2 chunk, chunk thứ hai chứa `Xep loai: Dat` (giữ hành vi ô gộp dọc).
- [ ] **Step 2: Chạy** `PYTHONPATH=backend python -m unittest tests.test_document_ingestion -v`. Kỳ vọng: test 1 FAIL (đếm được 3 chunk), test 2 PASS.
- [ ] **Step 3: Cài đặt `_merge_wrapped_rows`** và gọi trong `_native_table_documents`.
- [ ] **Step 4: Chạy lại cả file.** Kỳ vọng: mọi test PASS, gồm 5 test bảng cũ.
- [ ] **Step 5: Commit** `git commit -m "fix(ingestion): merge wrapped table rows into their numbered row"`

### Task 5: Luật 2, nối bảng qua trang

**Files:** như Task 4 (`_is_table_continuation`, phần chọn tiêu đề).

**Interfaces:**
- Consumes: `state["last"]` (có `last_number` từ Task 4).
- Thay đổi hành vi:
  - (a) Bảng **không có dòng tiêu đề**, tức ô đầu của dòng đầu là số hoặc trống và không có ô nào thuộc `{"tt", "stt"}`, nằm ở trang ngay sau và cùng số cột với bảng cuối trang trước → là phần tiếp, **kể cả khi** bảng trước không chạm đáy trang. Giữ `table.bbox[1] <= _CONTINUATION_TOP_PT` như cũ.
  - (b) Bảng không có dòng tiêu đề mà không nối được → **không** dùng dòng dữ liệu làm tiêu đề, dùng nhãn `Cột N` cho mọi cột và đưa mọi dòng vào dữ liệu.
  - `state["last"]` được giữ qua trang có bảng tiếp, nên chuỗi 3 trang nối được.

- [ ] **Step 1: Viết test thất bại:**
  - `test_headerless_table_continues_even_if_previous_ends_mid_page`: trang 1 có bảng `TT | Doi tuong | Muc ho tro` kết thúc ở y≈250 trên trang cao 420; trang 2 có bảng 3 cột ở đầu trang với dòng `("2","Sinh vien vung cao","140.000")`. Kỳ vọng: chunk chứa `Doi tuong: Sinh vien vung cao; Muc ho tro: 140.000`, `table_continued=True`, không có chuỗi `Sinh vien vung cao:` làm nhãn.
  - `test_three_page_table_keeps_first_header`: bảng 3 cột kéo qua 3 trang (trang 2, 3 không có tiêu đề). Kỳ vọng: chunk ở trang thứ 3 (page=2) có `Muc ho tro:`.
  - `test_unmatched_headerless_table_uses_generic_labels_not_data`: một trang duy nhất có bảng 3 cột bắt đầu bằng `("5","Alpha","Mot")`, `("6","Beta","Hai")`. Kỳ vọng: 2 chunk, một chunk chứa `Cột 2: Alpha`, không chunk nào có nhãn `Alpha:`.
- [ ] **Step 2: Chạy.** Kỳ vọng: 3 test mới FAIL.
- [ ] **Step 3: Cài đặt** theo (a)(b).
- [ ] **Step 4: Chạy cả file.** Kỳ vọng: mọi test PASS. Riêng `test_table_with_its_own_header_on_next_page_is_not_a_continuation` vẫn qua.
- [ ] **Step 5: Commit** `git commit -m "fix(ingestion): continue headerless tables across pages without using data as headers"`

### Task 6: Luật 3, nhận diện bảng giả

**Files:** như Task 4.

**Interfaces:**
- Produces: `_looks_like_prose_layout(rows: list[list[str]], column_count: int) -> bool`. Trả `True` khi `column_count == 2` và ít nhất 70% dòng không rỗng chỉ có đúng một ô có chữ.
- Khi `True`: bảng bị bỏ qua (không tạo tài liệu, **không** thêm `bbox` vào `bounds`), để chữ còn nằm trong phần văn xuôi của `_native_text_outside_tables`.

- [ ] **Step 1: Viết test thất bại:**
  - `test_two_column_text_layout_stays_as_prose`: lưới 2 cột, 6 dòng, chỉ cột trái có chữ, là một câu bị ngắt dòng `"Doan truong la co so Doan"`, `"tuong duong cap huyen"`, … Kỳ vọng: không chunk `native_table`; có chunk `native` chứa `Doan truong la co so Doan tuong duong cap huyen`.
  - `test_real_two_column_table_is_kept`: bảng 2 cột 4 dòng, mọi dòng đủ 2 ô (`Nganh | Chuan dau ra`, `Ngon ngu Anh | 5/6`, …). Kỳ vọng: 3 chunk `native_table`, có `Chuan dau ra: 5/6`.
- [ ] **Step 2: Chạy.** Kỳ vọng: test 1 FAIL, test 2 PASS.
- [ ] **Step 3: Cài đặt.**
- [ ] **Step 4: Chạy cả file.** Kỳ vọng: PASS hết.
- [ ] **Step 5: Commit** `git commit -m "fix(ingestion): treat two-column text layouts as prose"`

### Task 7: Luật 4, giữ nhãn (dòng tiêu đề kiểu tên bảng, dòng dài)

**Files:** như Task 4, cộng `_load_pdf_pages` (truyền `settings.chunk_size`).

**Interfaces:**
- Signature mới: `_native_table_documents(page, file_path, page_index, state=None, max_chars: int = 700)`. `_load_pdf_pages` truyền `max_chars=settings.chunk_size`.
- **Dòng tên bảng:**
  - Bảng ≥3 cột mà một dòng chỉ có ô đầu có chữ, các ô còn lại trống, là dòng tên bảng.
  - Ở dòng 0 thì text thành `caption` và dòng sau là tiêu đề.
  - Ở giữa bảng thì bắt đầu nhóm mới: caption mới, dòng ngay sau là tiêu đề mới. Bản thân dòng tên bảng không tạo chunk.
- **Dòng dài:**
  - `_split_long_row(identity: str, parts: list[str], max_chars: int) -> list[str]`.
  - `identity` = `prefix` (caption) + ô đầu có nhãn (`TT: 3`) + ô thứ hai có nhãn, cắt còn ≤120 ký tự kèm `…`.
  - Các `parts` còn lại được xếp tham lam vào từng mảnh `identity + "; " + ...`.
  - Một `part` dài hơn chỗ trống thì cắt tại khoảng trắng gần nhất, phần sau mang nhãn `"<nhãn> (tiếp): "`.
  - Mọi mảnh ≤ `max_chars`. Chunk nối tiếp có metadata `table_row_part` (1, 2, …).

- [ ] **Step 1: Viết test thất bại:**
  - `test_full_width_title_row_becomes_caption_and_next_row_is_header`: bảng 5 cột, dòng 0 `("CAC PHONG BAN CAN LIEN HE","","","","")`, dòng 1 `("STT","Ten phong","So dien thoai","Email","Ghi chu")`, dòng 2 `("3","Phong Tai chinh","0263. 3820566","phongtaichinh@dlu.edu.vn","Hoc phi")`. Kỳ vọng: chunk chứa `[CAC PHONG BAN CAN LIEN HE]`, `So dien thoai: 0263. 3820566` và `Email: phongtaichinh@dlu.edu.vn`, không chứa `" - "`.
  - `test_mid_table_title_row_starts_new_header_group`: tiếp bảng trên, thêm dòng `("KHOA CAN LIEN HE","","","","")`, `("STT","Khoa","So dien thoai","Email","Ghi chu")`, `("2","Cong nghe thong tin","0263. 3552540","it@dlu.edu.vn","")`. Kỳ vọng: chunk khoa CNTT chứa `[KHOA CAN LIEN HE]` và `Khoa: Cong nghe thong tin`.
  - `test_long_row_is_split_with_identity_on_every_part`: dòng `TT=2`, `Doi tuong="Nguoi co cong ..."` (~200 ký tự), `Ho so=` ~1500 ký tự; `settings.chunk_size=700`. Kỳ vọng: mọi chunk của dòng có `len <= 700`, đều chứa `TT: 2` và `Doi tuong: Nguoi co cong`; nối phần sau các nhãn lại thì chứa toàn bộ text hồ sơ gốc (so sau khi bỏ khoảng trắng).
- [ ] **Step 2: Chạy.** Kỳ vọng: 3 test mới FAIL.
- [ ] **Step 3: Cài đặt.**
- [ ] **Step 4: Chạy toàn bộ test:** `PYTHONPATH=backend python -m unittest discover -s tests -p "test_*.py"`. Kỳ vọng: PASS hết.
- [ ] **Step 5: Commit** `git commit -m "fix(ingestion): keep column labels for title rows and long rows"`

### Task 8: Tạo lại chỉ mục và đo "sau"

**Files:**
- Create: `experiments/evaluation/results_after.json`
- Modify: `experiments/evaluation/README.md`

- [ ] **Step 1: So sánh nạp trước/sau** bằng `python experiments/evaluation/audit_tables.py experiments/evaluation/audit_after.txt`, đối chiếu tr. 45–61 với bản audit cũ. Kỳ vọng: không còn `HỒ SƠ: mẫu phụ lục 2)` đứng riêng, tr. 52–58 không còn chunk `native_table`, danh bạ có nhãn `Số điện thoại:`. Các bảng tr. 2–3 (Chuẩn đầu ra), 29–30 cho text y hệt bản cũ.
- [ ] **Step 2: Rebuild chỉ mục.** `docker compose up --build -d` rồi gọi `POST /admin/rebuild-index` bằng token admin (hoặc nút "Tạo lại chỉ mục" trong trang quản trị). Kỳ vọng: response có `total_chunks > 0`.
- [ ] **Step 3: Chạy "sau"** với cùng `table_cases.json`: `python experiments/evaluation/run_eval.py --output experiments/evaluation/results_after.json`.
- [ ] **Step 4: Điền cột "Sau"** vào README. Liệt kê case vẫn sai kèm nguyên nhân (đọc bảng, truy hồi, hay LLM). Không sửa đáp án để khớp kết quả.
- [ ] **Step 5: Commit** `git commit -m "docs(eval): record before/after table extraction results"`

### Task 9: Backend cho trang kiểm tra

**Files:**
- Modify: `backend/db.py` (cột `reviewed_at DateTime`, `reviewed_by String(100)` trong `DocumentMetadata`, và migration trong `init_db` theo mẫu `document_migrations`), `backend/admin.py` (2 endpoint, thêm 2 trường vào `get_documents`)
- Test: `tests/test_chunk_inspection.py` (thêm lớp `InspectionEndpointTests`, gọi thẳng hàm endpoint như `tests/test_admin_ingestion.py`, dùng SQLite tạm và `admin.set_rag_chain(FakeRag)`)

**Interfaces:**
- Consumes: `list_document_chunks` (Task 2), `normalize_document_filename`, `require_admin`.
- Produces:
  - `GET /admin/documents/{filename}/chunks` → `get_document_chunks(filename, db, _admin) -> {"filename", "chunks": [...], "total": int, "flagged": int}`. 404 `"Không tìm thấy tài liệu"` nếu không có trong `document_metadata`. Collection không có chunk thì `chunks: []`.
  - `POST /admin/documents/{filename}/review`, body `{"reviewed": bool}` → `set_document_review(...) -> {"filename", "reviewed_at": str|None, "reviewed_by": str|None}`. `reviewed_at` dùng `as_utc_iso`, `reviewed_by = current_user["email"]`. `false` thì xóa cả hai.
  - `GET /admin/documents` thêm `reviewed_at`, `reviewed_by`.

- [ ] **Step 1: Viết test thất bại:**
  - `test_chunks_endpoint_returns_sorted_chunks_and_flag_count`
  - `test_chunks_endpoint_unknown_document_is_404`
  - `test_chunks_endpoint_document_without_chunks_returns_empty`
  - `test_review_sets_and_clears_reviewer`
  - `test_chunks_endpoint_rejects_path_in_filename`: `"../x.pdf"` → 400
  - `test_init_db_adds_review_columns_to_old_table`: tạo bảng `document_metadata` kiểu cũ không có cột, gọi `init_db`, kiểm tra cột tồn tại.
- [ ] **Step 2: Chạy** `PYTHONPATH=backend python -m unittest tests.test_chunk_inspection -v`. Kỳ vọng: FAIL.
- [ ] **Step 3: Cài đặt.**
- [ ] **Step 4: Chạy toàn bộ test.** Kỳ vọng: PASS hết.
- [ ] **Step 5: Commit** `git commit -m "feat(admin): expose document chunks and review status"`

### Task 10: Frontend, khung kiểm tra dữ liệu nạp

**Files:**
- Create: `frontend/src/components/admin/ChunkInspector.tsx`
- Modify: `frontend/src/types/index.ts` (`DocumentChunk`, thêm `reviewed_at?`, `reviewed_by?` vào `Document`), `frontend/src/services/api.ts` (`getDocumentChunks(filename): Promise<{chunks: DocumentChunk[]; total: number; flagged: number}>`, `setDocumentReview(filename, reviewed: boolean)`), `frontend/src/components/admin/DocumentTable.tsx` (prop `onInspect(document)`, nút "Kiểm tra", huy hiệu "Đã kiểm tra"), `frontend/src/pages/AdminDashboard.tsx` (giữ `inspecting: Document | null`, render `ChunkInspector`)

**Interfaces:**
- `DocumentChunk = { id: string; content: string; page: number | null; extraction_method: string | null; table_index: number | null; table_row: number | null; table_caption: string | null; table_continued: boolean; flags: string[] }`
- `ChunkInspector({ document, onClose }: { document: Document; onClose: () => void })`
  - Khung toàn màn hình chia đôi (≥1024px), xếp dọc ở màn hẹp.
  - Trái: iframe PDF từ `URL.createObjectURL(await getDocumentPreview(filename))` + `#page=N`, N đổi khi bấm một nhóm trang bên phải. DOCX: hiện thông báo "Xem trước trang chỉ hỗ trợ PDF".
  - Phải:
    - Chunk nhóm theo `page` (`null` → nhóm "Không rõ trang").
    - Chunk `native_table` hiển thị dạng danh sách `nhãn | giá trị` (tách `"; "` rồi `":"` đầu tiên). Chunk khác hiển thị text.
    - Chunk có `flags` được viền cảnh báo và có nhãn tiếng Việt: `generic_label` → "Thiếu nhãn cột", `too_short` → "Quá ngắn", `long_label` → "Nhãn bất thường".
    - Bộ lọc "Chỉ hiện chunk nghi lỗi". Nút "Đánh dấu đã kiểm tra" / "Bỏ đánh dấu" gọi `setDocumentReview` rồi invalidate query `["documents"]`.

- [ ] **Step 1: Nạp skill `design-taste-frontend`** (`.agents/skills/design-taste-frontend/SKILL.md`) và đọc `DocumentModal.tsx`, `PreviewDrawer.tsx` để dùng cùng token màu, khoảng cách, icon Phosphor.
- [ ] **Step 2: Thêm types và api.**
- [ ] **Step 3: Viết `ChunkInspector.tsx`** và nối vào `DocumentTable` và `AdminDashboard`.
- [ ] **Step 4: Kiểm tra build:** `cd frontend && npm run build`. Kỳ vọng: không lỗi TypeScript.
- [ ] **Step 5: Kiểm tra tay** bằng skill `run` hoặc `docker compose up --build -d`. Mở Sổ tay → Kiểm tra, bấm nhóm p51 thì PDF nhảy trang 51, lọc nghi lỗi hoạt động, đánh dấu xong thấy huy hiệu trong bảng. Mở một DOCX và file scan 1340, không lỗi giao diện.
- [ ] **Step 6: Commit** `git commit -m "feat(admin-ui): add ingestion chunk inspector"`

### Task 11 (tùy chọn): Thử `pymupdf4llm` trên tr. 45–61

**Files:** Create `experiments/table_spike/compare_pymupdf4llm.py` (thư mục thử, không đưa vào backend).

- [ ] **Step 1:** Cài `pip install pymupdf4llm` vào môi trường cục bộ (không sửa `requirements.txt`). Chạy `pymupdf4llm.to_markdown(path, pages=list(range(44, 61)))` và ghi ra file.
- [ ] **Step 2:** So với `audit_after.txt` theo 4 loại lỗi, ghi thời gian chạy. Viết 5–10 dòng kết luận vào `experiments/evaluation/README.md` mục "So sánh thư viện".
- [ ] **Step 3: Commit** `git commit -m "docs(eval): compare pymupdf4llm on complex tables"`
