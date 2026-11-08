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
  "pages": [2],
  "should_refuse": false
}
```

- `expected_values`: danh sách nhóm. Mỗi nhóm đạt khi câu trả lời chứa **một** trong các cách viết, không phân biệt dấu và hoa thường.
- `forbidden`: giá trị dễ nhầm (cột hoặc dòng bên cạnh). Xuất hiện là sai.
- `pages`: số trang **bắt đầu từ 0** (trang 3 trong PDF thì ghi `2`), giống metadata của chunk.
- `document_filename` (tùy chọn): giới hạn tìm kiếm trong một tài liệu. Mặc định tìm trên toàn thư viện.

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

_(điền sau khi chạy `results_before.json` và `results_after.json`)_
