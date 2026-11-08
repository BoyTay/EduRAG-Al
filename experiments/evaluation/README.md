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

## Kết quả trước/sau

Model `qwen3.5:9b`, 28 câu, chạy trên máy cục bộ (GPU 8 GB). Tiêu chí chấm được giữ cố định từ trước khi chạy lần đầu, không nới ra sau khi thấy kết quả.

| Chỉ số | Trước (2026-11-08) | Sau |
|---|---|---|
| Đúng giá trị | 78,6% (22/28) | |
| Đúng nguồn/trang | 100% | |
| Từ chối sai | 0% | |
| Bỏ sót từ chối | 0% | |
| Thời gian p50 / p95 | 6,8 s / 10,6 s | |
| simple_table | 88% (7/8) | |
| wrapped_rows | 67% (2/3) | |
| page_continuation | 67% (2/3) | |
| prose_layout | 100% (3/3) | |
| labels | 67% (2/3) | |
| ocr_scan | 50% (2/4) | |
| refusal | 100% (4/4) | |

Các câu sai ở lần "trước":

| Case | Câu trả lời | Nguyên nhân |
|---|---|---|
| `poor_ethnic_cost_docs` | Liệt kê hồ sơ của *hỗ trợ học tập* (phụ lục 3) thay vì *hỗ trợ chi phí học tập* (phụ lục 2) | Đọc bảng: ô hồ sơ bị vỡ thành nhiều đoạn, mất liên kết với đối tượng |
| `highland_allowance` | "140 đồng mỗi tháng" (đúng là 140.000) | Mất số khi diễn đạt; cần xem lại sau khi sửa nhãn cột |
| `master_math_duration` | "2 hoặc 4 năm" | Mô hình trộn dòng của bảng ngành đại học |
| `orphan_social_allowance` | Đúng 100.000 nhưng nêu thêm mức 140.000 của đối tượng khác | Mô hình thêm dòng lân cận (chấm sai theo tiêu chí `forbidden`) |
| `orientation_budget_small`, `orientation_budget_large` | Nêu cả hai mức 5 và 7 triệu | Mô hình liệt kê cả mục thay vì trả lời đúng mức được hỏi |

Lưu ý khi đọc số: tiêu chí `forbidden` chấm sai cả khi câu trả lời nêu thêm giá trị của dòng hoặc đối tượng khác, kể cả khi giá trị được hỏi là đúng. Nghĩa là bộ đo này đo cả **độ chính xác** (không lẫn thông tin), không chỉ "có nhắc tới đáp án".
