# Lỗi mất dấu OCR tiếng Việt — 14/09/2026

## Kết quả xác minh

File `1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf`
có 5 trang, không có native text. Đã đối chiếu ảnh trang 3 với kết quả
PP-OCRv6 Small và Medium trên cùng ảnh render 200 DPI, CPU, MKLDNN tắt.

- Small: `Dưi 150 ... (Năm triu đồng chãn)`; confidence trang 0,9763;
  thời gian từ khởi tạo đến kết quả 13,47 giây, dùng model cache sẵn có.
- Medium: `Dui 150 ... (Năm triu đng chăn)` và `... (Báy triu đng chn)`;
  confidence trang 0,9800; 53,12 giây gồm tải model và khởi tạo.
- Không so sánh tốc độ hai model từ các thời gian này vì trạng thái cache khác nhau.
- Cả hai bảng ký tự export `inference.yml` có 18.708 phần tử, không có
  nhiều ký tự như `ệ, ữ, ẳ, ẵ, ỡ, ờ, ộ, ấ, ế`, kể cả dạng NFD và dấu tổ hợp.
- Kiểm tra decoder thực tế của Small bằng `post_op.character` thiếu 88 ký tự
  trong bộ nguyên âm/dấu thanh và đ/Đ tiếng Việt mà backend yêu cầu.
- Đây là kết quả trên các artifact model đã tải trong môi trường này, không
  suy rộng thành kết luận mọi bản phát hành PP-OCRv6 đều có cùng lỗi.

Confidence cao và `lang="vi"` không chứng minh model xuất được đủ chữ tiếng Việt.
PaddleOCR còn cảnh báo bỏ qua `lang`/`ocr_version` khi chỉ định tên model cụ thể.
Không sửa bảng ký tự bằng cách chèn ký tự: chỉ số decoder phải khớp trọng số đã huấn luyện.

## Phương án đã chọn

- `latin_PP-OCRv5_mobile_rec` cũng không đạt kiểm tra vì decoder thiếu 90 ký tự
  tiếng Việt bắt buộc; không dùng artifact này để nạp dữ liệu.
- Chọn Tesseract 5.5.0 với gói `vie`, ảnh render 300 DPI, `OEM 1`, `PSM 6` và
  concurrency bằng 1 làm OCR mặc định cho tài liệu scan tiếng Việt.
- Trên đúng trang 3 của tài liệu kiểm tra, hai dòng kinh phí được nhận dạng đủ dấu:
  `5.000.000 (Năm triệu đồng chẵn)` và `7.000.000 (Bảy triệu đồng chẵn)`.
- Toàn bộ tài liệu 5 trang tạo 20 chunk trong 9,15 giây; lần chạy thứ hai dùng
  cache và cho nội dung chunk giống lần đầu.
- Kết quả này xác nhận lỗi cụ thể đã báo cáo, chưa thay thế benchmark CER/WER
  trên bộ ground truth 30–50 trang. Một số chữ nhỏ/tiêu đề vẫn có thể sai OCR.

## Thay đổi backend

- Dùng provider Tesseract tiếng Việt theo mặc định; PaddleOCR vẫn là tùy chọn.
- Cài `tesseract-ocr` và `tesseract-ocr-vie` trong image backend.
- Parse TSV để giữ text, confidence và bounding box; không ghi toàn văn OCR vào log.
- Fingerprint cache gồm provider, phiên bản engine, SHA-256 model, ngôn ngữ,
  PSM, OEM và phiên bản parser nên cache tự vô hiệu khi cấu hình thay đổi.
- Kiểm tra bảng ký tự decoder trước khi cho phép PaddleOCR chạy; báo lỗi cấu hình
  và số trang cho admin nếu artifact không hỗ trợ đủ tiếng Việt.
- Giữ native text ngắn nếu OCR thất bại, không làm mất nội dung đúng đã có.
- Cấu hình mặc định runtime là `OCR_PROVIDER=tesseract`, `OCR_DPI=300`.
- Backend production đã build và deploy; container healthy. Tesseract 5.5.0 và
  ngôn ngữ `vie` có trong container.
- Bộ kiểm thử hiện có đạt 51 test, trong đó 1 test quyền POSIX được bỏ qua trên Windows.
- Đã nạp lại 4 tài liệu bằng endpoint admin chính thức; collection active mới có
  349 chunk. Collection cũ chỉ được thay sau khi toàn bộ ingestion thành công.

## Hoàn tất dữ liệu hiện hữu

Nạp lại tài liệu qua `POST /admin/rebuild-index` có Bearer token admin và cơ chế
staging/active. Không dùng `scripts/build_index.py --reset` trong vận hành.
Index cũ chỉ được thay thế sau khi toàn bộ tài liệu nạp thành công; nếu OCR lỗi,
staging bị hủy và active index hiện tại được giữ nguyên.

Sau rebuild, câu hỏi về Khoa có 200 tân sinh viên trả đúng
`7.000.000 đồng chẵn` và badge trỏ đến tài liệu Tuần định hướng, trang 3.
Không vá từng câu trả lời hoặc tự đoán thêm dấu bằng LLM.

Các script tái hiện trong `experiments/ppocrv6_cpu/` đọc PDF ở mount read-only.
`verify_vietnamese_ingestion.py` kiểm tra ingestion và cache Tesseract;
`check_vietnamese_pdf.py` cùng `inspect_vietnamese_charset.py` chẩn đoán PaddleOCR.
Không script thử nghiệm nào mount database dự án.
