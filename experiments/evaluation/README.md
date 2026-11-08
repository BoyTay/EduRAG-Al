# Đánh giá EduRAG trên câu hỏi về bảng

Bộ câu hỏi kiểm thử phục vụ mục 6 của đề tài: đo **độ đúng giá trị**, **đúng nguồn/trang**, **cơ chế từ chối** và **thời gian phản hồi** của chatbot. Trọng tâm là dữ liệu dạng bảng trong PDF. Đáp án chuẩn được lấy từ PDF gốc rồi người làm đề tài đối chiếu lại, không lấy từ output của hệ thống.

## Thành phần

| File | Vai trò |
|---|---|
| `table_cases.json` | Bộ câu hỏi và đáp án chuẩn |
| `scoring.py` | Hàm chấm điểm (có test: `tests/test_evaluation_scoring.py`) |
| `run_eval.py` | Chạy bộ câu hỏi qua đúng pipeline RAG và ghi kết quả JSON |
| `dump_chunks.py` | Xuất các chunk thực tế đang lưu trong Chroma của một tài liệu |
| `audit_tables.py` | Đối chiếu bảng thô trong PDF với đoạn text sẽ được lập chỉ mục |
| `resources.py` | Đo RAM, CPU, VRAM và thông tin model Ollama trong lúc chạy (có test: `tests/test_evaluation_resources.py`) |

## Cách chạy

Cần Ollama đang chạy với `qwen3.5:9b`, chỉ mục trong `chroma_db/` và model embedding/reranker đã có trong cache Hugging Face.

```powershell
$env:PYTHONPATH = "backend"
python experiments/evaluation/run_eval.py --output experiments/evaluation/results_before.json
# Chạy một câu:
python experiments/evaluation/run_eval.py --output tmp/one.json --case-id fee_disabled_support
```

## Cấu trúc một câu hỏi

```json
{
  "id": "ielts_level4",
  "category": "simple_table",
  "question": "IELTS bao nhiêu thì tương đương bậc 4?",
  "expected_values": [["5.5-6.5", "5,5-6,5", "5.5 - 6.5"]],
  "forbidden": [["4.0-5.0"], ["7.0-8.0"]],
  "source_filename": "Chuan_dau_ra_ngoai_ngu_tin_hoc.pdf",
  "pages": [3],
  "should_refuse": false
}
```

- `expected_values`: danh sách nhóm. Mỗi nhóm đạt khi câu trả lời chứa **một** trong các cách viết, không phân biệt dấu và hoa thường.
- `forbidden`: giá trị dễ nhầm (cột hoặc dòng bên cạnh). Xuất hiện là sai.
- `pages`: số trang **bắt đầu từ 1**, đúng như trong trình xem PDF và như nguồn chatbot hiển thị.
- `document_filename` (tùy chọn): giới hạn tìm kiếm trong một tài liệu. Mặc định tìm trên toàn thư viện.

## Nguồn của đáp án chuẩn

Đáp án được lấy **trước khi** chatbot được hỏi bất kỳ câu nào, và người làm đề tài đã rà lại toàn bộ (2026-11-08):

| Case | Nguồn |
|---|---|
| Chuẩn đầu ra, xếp loại, xếp hạng năm học, thạc sĩ, miễn giảm học phí, Đoàn, danh bạ | Lớp chữ gốc của PDF (text layer), đọc bằng PyMuPDF trước mọi bước xử lý của EduRAG |
| Hỗ trợ chi phí học tập, hỗ trợ học tập, trợ cấp xã hội, khu nội trú | Ảnh chụp trang PDF (Sổ tay tr. 49, 50, 51, 58) |
| Kinh phí Tuần định hướng | Ảnh chụp trang 3 của Kế hoạch 1340 (bản scan) |
| Ngày diễn ra, hạn gửi phân công | Chữ OCR của Kế hoạch 1340, người làm đề tài đối chiếu với bản giấy |

## Ý nghĩa chỉ số

| Chỉ số | Cách tính |
|---|---|
| `value_accuracy` | Tỉ lệ câu đúng: đủ mọi nhóm giá trị, không có giá trị cấm, không từ chối. Với câu cần từ chối thì đúng khi hệ thống từ chối |
| `source_accuracy` | Tỉ lệ câu trích dẫn đúng tài liệu và đúng trang |
| `false_refusal_rate` | Tỉ lệ từ chối sai trên các câu tài liệu có đáp án |
| `missed_refusal_rate` | Tỉ lệ vẫn trả lời trên các câu tài liệu không có đáp án |
| `p50_seconds`, `p95_seconds` | Thời gian phản hồi trung vị và phân vị 95 |
| `errors` | Số câu lỗi khi chạy (ví dụ Ollama tắt). Bị loại khỏi các tỉ lệ trên |

## Lỗi của tài liệu nguồn

- **Sổ tay sinh viên, trang 60 (danh bạ):** email của Phòng Quản lý đào tạo (`Phongcongtacsinhvien@dlu.edu.vn`) và Phòng Chính trị và Công tác sinh viên (`phongquanlydaotao@dlu.edu.vn`) bị đảo cho nhau ngay trong PDF. Hệ thống đọc đúng PDF nên sẽ lặp lại lỗi này. Đáp án chuẩn theo PDF và cần báo Khoa sửa tài liệu gốc.

## Kiểm chứng chunk thật

Chạy ngày 2026-11-08 trên chỉ mục đang hoạt động (`edurag_rebuild_ad7ea27c…`):

- **Sổ tay sinh viên:** 435 chunk, trong đó 237 chunk bảng và **95 chunk bị gắn cờ nghi lỗi**. Chunk đang lưu khớp đúng với output của code nạp hiện tại, nên lỗi ở tr. 45–61 (dòng vỡ, nhãn cột lấy từ dòng dữ liệu, danh bạ không nhãn) có thật trong chỉ mục. Ví dụ tr. 51: `1. Đơn xin nhận trợ cấp xã hội 2. Bản sao chứng thực giấy giám định sức khỏe của hội: đồng Y khoa (có ghi rõ tỷ lệ`.
- **Kế hoạch 1340 (PDF scan, Tesseract):** 20 chunk.
  - Trang 1–4 (văn bản) đọc tốt. Có lỗi dấu nhỏ như `Tư do`, `KÉ HOẠCH`, `ĐÓI TƯỢNG`, `Tô chức`, nhưng ngày tháng và số tiền giữ đúng (24/8/2026–28/8/2026; 5.000.000 và 7.000.000 đồng; hạn 11h00 ngày 20/8/2026).
  - **Trang 5 là bảng phân bổ, OCR ra chữ rác hoàn toàn** (`š|š|š|…`). Mọi câu hỏi về bảng này hiện không thể trả lời đúng. Đây là giới hạn của OCR trên bảng scan, nằm ngoài phạm vi sửa bộ đọc bảng PDF gốc.

## Tài nguyên sử dụng

Đo ngày 2026-11-08 bằng `run_eval.py --repeats 3` (84 lượt hỏi, lấy mẫu mỗi 0,5 giây, 760 mẫu), file `results_resources_x3.json`.

**Máy đo:** laptop Intel thế hệ 13 (24 luồng), RAM 24 GB, GPU NVIDIA RTX 5060 Laptop 8 GB. Model embedding và reranker chạy trên **CPU** (torch bản CPU, giống image Docker). GPU chỉ dành cho LLM trong Ollama.

| Thành phần | Mức dùng |
|---|---|
| LLM `qwen3.5:9b` (9,7B tham số, Q4_K_M, ngữ cảnh 6144) | 5,2 GB, nằm **100% trên GPU** |
| VRAM toàn GPU lúc cao nhất | 7,4 / 8,0 GB (gồm cả phần màn hình và ứng dụng khác dùng) |
| RAM tiến trình RAG sau khi nạp embedding + reranker | 1,1 GB |
| RAM tiến trình RAG lúc cao nhất khi trả lời | 3,6 GB |
| RAM container backend lúc nghỉ (`docker stats`) | 1,1 GB |
| RAM container frontend (Nginx) | 19 MB |
| CPU tiến trình RAG (trung bình / đỉnh, % toàn máy) | 35% / 72% |
| Thời gian phản hồi p50 / p95 | 5,4 s / 7,0 s |
| Đúng giá trị / đúng nguồn ở lượt đo này | 88,1% / 100% |

**Cách hiểu:**
- RAM tăng từ 1,1 GB lên 3,6 GB khi trả lời, do reranker `bge-reranker-v2-m3` chấm tới 12 đoạn mỗi câu hỏi trên CPU. Có thể tắt reranker (`RERANKER_MODEL=` để trống) để giảm RAM và CPU, đổi lại độ chính xác thấp hơn ở câu tra cứu trong bảng.
- `LLM_NUM_CTX=6144` được chọn để model nằm gọn trong GPU 8 GB (100% trên GPU). Ngữ cảnh 8192 làm khoảng 12% model tràn sang CPU và chậm hơn (ghi chú trong `rag_chain.py`).
- Cấu hình tối thiểu suy ra: GPU 8 GB VRAM và RAM 16 GB là đủ chạy toàn bộ hệ thống cục bộ. Máy không có GPU vẫn chạy được nhưng Ollama sẽ dùng CPU và phản hồi chậm hơn nhiều; con số này chưa được đo.

## Kết quả trước/sau

Model `qwen3.5:9b` (nhiệt độ 0,3), 28 câu, mỗi câu chạy **3 lần** trên cùng máy cục bộ (GPU 8 GB), tổng 84 lượt mỗi bên. Tiêu chí chấm được giữ cố định từ trước khi chạy lần đầu, không nới ra sau khi thấy kết quả.

- **Trước:** chỉ mục `edurag_rebuild_ad7ea27c…` (bộ đọc bảng cũ), file `results_before_x3.json`.
- **Sau:** chỉ mục `edurag_rebuild_edead44a…` (bộ đọc bảng mới, PyMuPDF 1.28 trong Docker), file `results_after_x3.json`.

| Chỉ số | Trước | Sau |
|---|---|---|
| **Đúng giá trị** | **78,6% (66/84)** | **85,7% (72/84)** |
| Đúng nguồn/trang (cả 28 câu) | 98,8% | 100% |
| Đúng nguồn/trang (24 câu có đáp án) | 100% | 100% |
| Từ chối sai (câu có đáp án mà từ chối) | 0% | 0% |
| Bỏ sót từ chối (câu không có đáp án mà vẫn trả lời) | 8,3% | 0% |
| Thời gian p50 / p95 | 5,3 s / 7,4 s | 5,6 s / 8,7 s |
| simple_table | 83% | 75% |
| wrapped_rows | 56% | 89% |
| page_continuation | 78% | 100% |
| prose_layout | 78% | 89% |
| labels | 67% | 100% |
| ocr_scan | 83% | 67% |
| refusal | 92% | 100% |

Chunk nghi lỗi của Sổ tay sinh viên (đếm bằng `dump_chunks.py`): **95/435 → 6/338**.

Thay đổi theo từng câu (số lần đúng trên 3 lần chạy):

| Case | Trước | Sau | Ghi chú |
|---|---|---|---|
| `poor_ethnic_cost_docs` | 0 | 3 | Ô hồ sơ không còn vỡ dòng nên không lẫn với *hỗ trợ học tập* |
| `highland_allowance` | 0 | 3 | Trước trả lời "140 đồng"; nay nhãn "Mức hỗ trợ (đ/tháng)" đi kèm giá trị |
| `poor_household_review` | 1 | 3 | Bảng trợ cấp xã hội tr. 51 không còn vỡ thành 26 mảnh |
| `dorm_capacity` | 1 | 2 | Trang giới thiệu khu nội trú trở lại thành văn xuôi |
| `refuse_ielts_exam_schedule` | 2 | 3 | |
| `gpa_excellent` | 2 | 0 | Bảng xếp loại **không đổi** và nguồn giống hệt; câu trả lời "từ 3,60 trở lên" đúng ý nhưng thiếu cận trên "4,00" nên bị chấm sai theo tiêu chí |
| `orientation_budget_small` / `_large` | 2 / 3 | 1 / 2 | File scan 1340 không bị thay đổi (OCR); dao động do mô hình liệt kê cả hai mức |
| `master_math_duration` | 0 | 0 | Mô hình vẫn trộn "2 hoặc 4 năm" từ bảng ngành đại học: lỗi diễn đạt, không phải lỗi đọc bảng |

**Cách đọc số liệu:**
- Chênh lệch ở `simple_table` và `ocr_scan` nằm ở các bảng và trang **không bị thay đổi** (đã đối chiếu: output nạp của các bảng này giống hệt bản cũ). Đây là dao động của LLM ở nhiệt độ 0,3, không phải hệ quả của việc sửa bộ đọc bảng. Vì vậy phải chạy lặp, một lượt đo đơn lẻ không đủ để kết luận.
- Các nhóm mà bộ đọc bảng nhắm tới (`wrapped_rows`, `page_continuation`, `labels`, `prose_layout`) đều tăng.
- Tiêu chí `forbidden` chấm sai cả khi câu trả lời nêu thêm giá trị của dòng hoặc đối tượng khác, kể cả khi giá trị được hỏi là đúng. Bộ đo này đo cả **độ chính xác** (không lẫn thông tin), không chỉ "có nhắc tới đáp án".
- `source_accuracy` của câu cần từ chối được tính là đúng khi hệ thống từ chối, vì vậy có thêm dòng "24 câu có đáp án" để đọc riêng.
- Lượt đo "sau" đầu tiên (chạy 1 lần) bị bỏ: image Docker khi đó dùng PyMuPDF 2.1, bản này tách chữ tiếng Việt trong ô bảng ("Si nh viên"). Image hiện đã ghim PyMuPDF < 2.0 (`Dockerfile.backend`), có test `test_pymupdf_major_version_is_below_2` chặn tái diễn. `backend/requirements.txt` vẫn ghi `pymupdf>=1.24.0`; khi cài ngoài Docker phải tự giữ bản 1.x.

Lượt đo đơn lẻ đầu tiên của bộ đọc bảng cũ (`results_before.json`) cho 78,6% (22/28), khớp với kết quả chạy lặp.
