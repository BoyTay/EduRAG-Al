# Kết quả smoke test RAG trên PDF scan — 14/09/2026

## 1. Phạm vi chạy

- Giao diện thật: `http://localhost:3000/chat`.
- Backend Docker CPU và active Chroma collection hiện tại.
- Tài liệu: `1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf`.
- Số vector tại thời điểm khởi động: 349; truy vấn mục tiêu dùng 20–30 ứng viên và 6–8 chunk ngữ cảnh.
- Đã chạy 11 lượt gồm dữ kiện trực tiếp, câu tổng hợp, ranh giới số, trách nhiệm, câu không dấu, tiền đề sai, ngoài phạm vi và hội thoại đa lượt.
- Chưa chạy toàn bộ S-01 đến S-29, chưa lặp ba lần các ca ổn định và chưa thử khóa `document_filename` sang tài liệu khác.

Quy ước: **Đạt** là đáp án và trang chính đúng; **Đạt một phần** là dữ kiện chính đúng nhưng thiếu ý, câu chữ lỗi, chưa đính chính tiền đề hoặc nguồn UI gây hiểu nhầm.

## 2. Kết quả từng ca

| Ca | Câu hỏi rút gọn | Kết quả thực tế | Trang chính | Thời gian backend | Kết luận |
|---|---|---|---:|---:|---|
| S-02 | Tuần định hướng diễn ra từ ngày nào đến ngày nào? | 24/8/2026 đến hết 28/8/2026 | 1 | 7,934 giây | Đạt |
| S-04 | Có bắt buộc tham gia không? | Bắt buộc tham gia đầy đủ các hoạt động | 1 | 1,953 giây | Đạt |
| S-07 | Được hướng dẫn những nội dung gì? | Trả đủ bốn nhóm và bao phủ các ý chính của mục NỘI DUNG | 2 | 21,902 giây | Đạt |
| S-13 | Được trang bị kỹ năng nào? | Có tự học, nghiên cứu, thuyết trình, giao tiếp, làm việc nhóm, quản lý thời gian/tài chính | 2 | 2,663 giây | Đạt một phần |
| S-21 | Đúng 150 tân sinh viên được bao nhiêu? | 7.000.000 đồng chẵn | 3 | 2,226 giây | Đạt |
| S-27 | Hạn gửi chương trình chi tiết? | Trước 11h00 ngày 20/8/2026 | 4 | 2,051 giây | Đạt |
| S-29 | Trách nhiệm tân sinh viên? | Nêu thực hiện kế hoạch, đầy đủ, đúng giờ, lắng nghe và ghi chép | 4 | 3,151 giây | Đạt một phần |
| G-05 | Mỗi sinh viên được phát 7 triệu, đúng không? | Từ chối trả lời vì không có thông tin phù hợp | 3 | 1,988 giây | Đạt một phần |
| G-03 | Học phí học kỳ I khóa 50? | Từ chối vì không có thông tin phù hợp | 4 được UI hiển thị | 1,897 giây | Đạt một phần |
| P-01 | Câu không dấu về mức dưới 150 | Trả đúng 5.000.000 đồng chẵn | 3 | 2,187 giây | Đạt |
| M-02 | Hỏi tiếp: còn đúng 150 thì sao? | Hiểu ngữ cảnh trước và trả 7.000.000 đồng | 3 | 2,069 giây | Đạt |

Tổng hợp: **7/11 đạt**, **4/11 đạt một phần**, không có ca nào trả sai ngày, số tiền hoặc ranh giới 150. Tỷ lệ đạt hoàn toàn là 63,6%, chưa đạt ngưỡng đề xuất 90% để kết luận ổn định cho demo.

## 3. Các lỗi đã tái hiện

### RAG-01 — Câu kỹ năng thiếu ý

- Ca: S-13.
- Thiếu: khả năng thích nghi với môi trường mới và kỹ năng sống tự lập.
- Dữ kiện còn lại đúng và nguồn chính đúng trang 2.
- Phân loại ban đầu: generation hoặc retrieval coverage. Cần kiểm tra các chunk trang 2 được đưa vào context trước khi quyết định sửa prompt.

### OCR-01 — Câu trách nhiệm bị nhiễu chữ tiếng Việt

- Ca: S-29.
- Đoạn lỗi thực tế: `quy chế, suy định, sống như quyền lợi và nghĩa vụ của sinh viên`.
- Câu đúng về nghĩa phải liên quan đến `quy chế, quy định, cũng như quyền lợi và nghĩa vụ`.
- Các nghĩa vụ chính vẫn được trả đúng, nhưng câu chữ không chấp nhận được cho bản demo.
- Phân loại ban đầu: OCR/index contamination hoặc model sao chép từ context lỗi. Cần đọc trực tiếp text chunk trang 4; không nên chữa bằng danh sách thay thế từ cố định ở output.

### RAG-02 — Tiền đề sai chỉ bị từ chối, chưa được đính chính

- Ca: G-05.
- Hệ thống không đồng ý với tiền đề sai, nhưng chưa nói rõ 7.000.000 đồng là kinh phí Nhà trường hỗ trợ **Khoa tổ chức**, không phải khoản phát cho mỗi sinh viên.
- Phân loại ban đầu: generation/guardrail. Context đã tìm đúng trang 3.

### CIT-01 — Câu từ chối vẫn hiển thị nguồn không hỗ trợ

- Ca: G-03.
- Nội dung từ chối là đúng, nhưng UI vẫn hiện trang 4 và `+ 6 trang liên quan`.
- Đây không phải bằng chứng cho mức học phí và dễ khiến người dùng hiểu rằng câu trả lời được trích từ trang 4.
- Phân loại: citation/UI. Khi `insufficient_context=true` hoặc dùng câu từ chối chuẩn, nên ẩn toàn bộ source badges.

### CIT-02 — Danh sách trang liên quan quá rộng

- Các câu số tiền chỉ cần trang 3 nhưng UI có lúc hiện thêm 6–7 trang liên quan.
- Trang chính đúng, tuy nhiên nguồn phụ làm giảm khả năng kiểm chứng.
- Phân loại: citation/UI. Chỉ nên hiển thị trang vượt ngưỡng hỗ trợ trực tiếp, giới hạn 2–3 trang và không trộn trang từ tài liệu không đóng góp cho câu trả lời.

## 4. Hiệu năng quan sát

- p50: 2,187 giây.
- p95 nội suy trên 11 lượt: 14,918 giây.
- Chậm nhất: S-07, 21,902 giây.
- S-07 sinh câu trả lời lần đầu chỉ có bốn bullet, thực hiện một lần rewrite rồi vẫn thiếu; backend sau đó dùng source-gated fallback. Đây là nguyên nhân ca này chậm rõ rệt.
- Các lượt còn lại nằm trong khoảng 1,897–7,934 giây.

Mẫu hiện còn nhỏ nên các số p50/p95 chỉ dùng làm đường cơ sở vòng đầu, chưa phải kết luận hiệu năng production.

## 5. Quan sát vận hành riêng

Log trước vòng smoke có một lần `GET /health` trả 500 do ChromaDB báo `disk I/O error`; backend sau đó khởi động lại, nạp thành công collection 349 vector và phục vụ toàn bộ 11 lượt chat với HTTP 200. Lỗi này chưa tái hiện trong vòng smoke nhưng cần kiểm tra volume/lock của Chroma nếu xuất hiện lại.

## 6. Kết luận và thứ tự xử lý

Kết luận hiện tại: **đạt có điều kiện, chưa đủ ổn định để chốt demo**.

Ưu tiên khắc phục:

1. Đối chiếu text OCR/chunk trang 4 để loại lỗi `suy định, sống như` từ dữ liệu gốc rồi rebuild bằng `POST /admin/rebuild-index`.
2. Bổ sung kiểm tra bao phủ cho câu hỏi theo nhóm kỹ năng, không chỉ câu hỏi tổng hợp toàn bộ nội dung.
3. Yêu cầu câu có tiền đề sai vừa từ chối vừa đính chính bằng dữ kiện nguồn.
4. Ẩn nguồn khi từ chối và siết ngưỡng/giới hạn trang liên quan.
5. Sau khi sửa, chạy lại S-13, S-29, G-03, G-05; sau đó mới chạy toàn bộ 29 ca và vòng lặp ổn định.

## 7. Vòng xác minh sau sửa OCR-01 và S-29

Thực hiện ngày 14/09/2026 trên Docker CPU sau khi build lại backend và gọi luồng rebuild chính thức từ trang quản trị.

- Rebuild thành công 4 tài liệu, tổng cộng 349 đoạn vector.
- Active collection mới: `edurag_rebuild_a197cbdace6e4c85828939c050a18e00`.
- Tài liệu Tuần định hướng được tạo lại thành 20 đoạn.
- Chunk trang 4 đã chứa đúng và đủ ba trách nhiệm của tân sinh viên; không còn `suy định, sống như`.
- Hỏi lại trên giao diện: `Tân sinh viên có trách nhiệm gì khi tham gia Tuần định hướng?`.
- Kết quả trả đủ ba ý: thực hiện nghiêm túc; tham gia đầy đủ, đúng giờ, lắng nghe và ghi chép; tích cực giao lưu và đặt câu hỏi.
- Nguồn chính hiển thị đúng tài liệu Tuần định hướng, trang 4.

Kết luận ca S-29 sau sửa: **Đạt**. Nguyên nhân OCR-01 được xác nhận là cấu hình phân đoạn trang của Tesseract và nhiễu con dấu màu. Cấu hình mới dùng PSM 6 và tiền xử lý ảnh theo kênh sáng nhất trước OCR; thay đổi cache fingerprint buộc dữ liệu cũ được tạo lại khi rebuild.

Các ca S-13, G-03 và G-05 vẫn giữ nguyên trạng thái trong bảng trên vì chưa được kiểm thử lại ở vòng này.
