# OCR bảng scan: tìm ô bằng Paddle, đọc chữ bằng Tesseract

Thí nghiệm phục vụ mục 2 (làm sạch dữ liệu) và mục 6 (đánh giá) của đề tài. Câu hỏi đặt ra là trang **bảng scan** nên đọc bằng cách nào để chatbot trả lời đúng "đơn vị nào, ngày nào, ai phụ trách".

## Bối cảnh

- Trang 5 của `1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf` là bảng 15 dòng được **scan nằm ngang**. Trước đây OCR chỉ ra chuỗi rác.
- Đã thêm bước tự nhận hướng trang (Tesseract OSD). Sau khi xoay đúng, chế độ `psm 6` chỉ đọc được tiêu đề, vì chế độ này coi cả trang là một khối chữ.
- Không dùng phần **nhận dạng chữ** của PaddleOCR, vì PP-OCRv6 thiếu 88 ký tự tiếng Việt (xem `docs/ocr_vietnamese_charset_issue.md`). Ở đây chỉ dùng phần **phát hiện vùng chữ** của Paddle. Phần này không phụ thuộc bảng ký tự.

## Các cách được so sánh

| Cách | Mô tả |
|---|---|
| `psm6 (cũ)` | Tesseract coi cả trang là một khối chữ (mặc định trước đây) |
| `psm3` | Tesseract tự phân tích bố cục trang |
| `Paddle tìm ô + Tesseract đọc ô` | `PP-OCRv6_small_det` tìm từng ô chữ, Tesseract đọc từng ô (`psm 7`), các ô cùng hàng được nối bằng ` \| ` |
| `recognize_page (hệ thống chọn)` | Cách backend đang chạy: đọc `psm 6`. Nếu độ tin cậy dưới 0,85 thì thử `psm 3` và cách đọc theo ô, ưu tiên cách đọc theo ô trừ khi kém hơn 0,05 |

## Cách chấm

Đáp án chuẩn nằm trong `page5_table_truth.json`, được gõ tay từ ảnh trang chứ không lấy từ kết quả OCR. Có 4 chỉ số, mỗi chỉ số tính trên 15 dòng:

- **đơn vị** / **lãnh đạo**: tên có xuất hiện đúng trong văn bản OCR hay không.
- **đơn vị + lãnh đạo cùng dòng**, **đơn vị + ngày cùng dòng**: hai giá trị có nằm trên cùng một dòng chữ hay không. Đây là chỉ số quan trọng nhất cho RAG. Nếu tên đơn vị và tên lãnh đạo nằm rời nhau, chatbot không biết ai phụ trách khoa nào.

## Kết quả (14/11/2026, CPU, 300 DPI)

| Cách | Đơn vị | Lãnh đạo | Đơn vị + lãnh đạo cùng dòng | Đơn vị + ngày cùng dòng | Độ tin cậy | Thời gian |
|---|---|---|---|---|---|---|
| psm6 (cũ) | 0/15 | 0/15 | 0/15 | 0/15 | 0,75 | 0,5 s |
| psm3 | 10/15 | 6/15 | 4/15 | 6/15 | 0,83 | 0,9 s |
| **Paddle tìm ô + Tesseract đọc ô** | **14/15** | **15/15** | **14/15** | **13/15** | 0,84 | 6,2 s |
| recognize_page (hệ thống chọn) | 14/15 | 15/15 | 14/15 | 13/15 | 0,84 | 8,5 s |

Dữ liệu chi tiết, kể cả toàn văn OCR của từng cách, nằm trong `results_page5.json`.

Độ tin cậy đo trên các trang khác (chỉ có độ tin cậy, chưa có đáp án chuẩn):

| Trang | psm6 | psm3 | Đọc theo ô |
|---|---|---|---|
| Tuần định hướng, trang 1 (văn xuôi) | 0,93 | 0,94 | 0,93 (không chạy, vì trang đã trên ngưỡng 0,85) |
| Sổ tay sinh viên, trang 9 (poster) | 0,70 | 0,83 | 0,90 |
| Sổ tay sinh viên, trang 10 (sơ đồ tổ chức) | 0,57 | 0,64 | 0,76 |

## Hạn chế

- Kết quả chỉ đo trên **một trang bảng**, và đáp án do nhóm tự gõ. Đủ để thấy chênh lệch lớn, nhưng chưa đủ để khẳng định cho mọi loại bảng.
- **Ô gộp** (cột hội trường gộp 5 dòng) chỉ được gắn vào dòng giữa của nhóm. Các dòng còn lại không có tên hội trường.
- Còn lỗi ký tự lẻ: "Hỏa học" (đúng là "Hóa học"), "z7/8/2026", số thứ tự đọc thành "Á", "®".
- Trang bảng chậm hơn khoảng 3–4 lần (mỗi ô gọi Tesseract một lần). Trang văn xuôi không bị ảnh hưởng.

## Chạy lại

Thí nghiệm cần Tesseract (`vie`, `osd`) và PaddleOCR nên phải chạy trong container backend:

```bash
docker cp experiments/ocr_table_hybrid edurag_backend:/tmp/ocr_table_hybrid
MSYS_NO_PATHCONV=1 docker exec -w /app/backend edurag_backend \
  python /tmp/ocr_table_hybrid/compare_ocr.py \
  --pdf /app/data/1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf \
  --output /tmp/ocr_table_hybrid/results.json
docker cp edurag_backend:/tmp/ocr_table_hybrid/results.json experiments/ocr_table_hybrid/results_page5.json
```

Mã OCR thật nằm ở `backend/tesseract_service.py` và `backend/cell_detection.py`. Có thể tắt cách đọc theo ô bằng biến `OCR_CELL_DETECTOR=none`.
