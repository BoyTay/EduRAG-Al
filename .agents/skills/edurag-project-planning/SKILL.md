---
name: edurag-project-planning
description: Phân tích mã nguồn EduRAG và viết hoặc cập nhật kế hoạch triển khai bằng tiếng Việt, gồm chức năng, kiến trúc, RAG, bảo mật, kiểm thử và Docker. Sử dụng khi cần tạo tài liệu kế hoạch Markdown bám sát trạng thái thực tế của dự án.
---

# EduRAG Project Planning

## Mục tiêu

Tạo tài liệu kế hoạch triển khai EduRAG bằng tiếng Việt, rõ ràng, có căn cứ từ mã nguồn và có thể sử dụng độc lập như tài liệu chính thức của dự án.

## Đầu vào

- Mã nguồn EduRAG trong workspace hiện tại.
- Yêu cầu cụ thể của người dùng.
- Tài liệu định dạng tham khảo nếu người dùng cung cấp.

Nếu thiếu thông tin không ảnh hưởng đến việc khảo sát, tiếp tục làm và ghi nội dung cần xác nhận ở cuối tài liệu.

## Quy tắc sử dụng tài liệu tham khảo

Nếu có tài liệu tham khảo, chỉ dùng tài liệu đó trong quá trình làm việc để xác định:

- Thứ tự các phần.
- Mức độ chi tiết.
- Cách trình bày trang, kiến trúc, API, bảo mật, kiểm thử và Docker.
- Loại bảng, sơ đồ và danh sách cần sử dụng.

Tài liệu đầu ra phải đứng độc lập. Không đưa vào đầu ra:

- Tên hoặc vai trò của người cung cấp tài liệu tham khảo.
- Các câu như “đã đọc mẫu”, “căn cứ theo mẫu” hoặc “bám sát mẫu”.
- Phần mô tả quá trình khảo sát hay đối chiếu.
- Mục hoặc phụ lục kiểm tra mức độ giống tài liệu tham khảo.
- Nội dung, công nghệ hoặc tính năng không thuộc EduRAG.

## Khảo sát dự án

Đọc các phần liên quan trực tiếp đến kế hoạch:

- `README` và file dependency.
- Route, page, layout, component, store và API client của frontend.
- Endpoint, schema, model dữ liệu và phân quyền của backend.
- Quy trình upload, cập nhật, xóa và xem trước tài liệu.
- Chunking, embedding, retrieval, prompt, nguồn trích dẫn và lịch sử hội thoại.
- Dockerfile, Compose, Nginx, biến cấu hình và volume.
- Test, CI và tài liệu vận hành nếu có.

Bỏ qua dependency đã cài, cache, model tải về, vector database và dữ liệu vận hành, trừ khi người dùng yêu cầu kiểm tra chúng.

Không hiển thị giá trị mật khẩu, token, API key, SMTP credential hoặc dữ liệu cá nhân. Nếu phát hiện secret trong repository, chỉ ghi vị trí và hành động cần xử lý.

## Xác định hiện trạng

Đối với mỗi chức năng, kiểm tra implementation thực tế và dùng một trong các trạng thái:

- **Đã có mã:** tìm thấy phần triển khai tương ứng.
- **Đã kiểm thử:** có kết quả kiểm thử hoặc chạy thực tế được xác nhận.
- **Chưa xác minh:** có mã hoặc cấu hình nhưng chưa đủ kết quả để kết luận chạy đúng.
- **Chưa triển khai:** không tìm thấy implementation trong phạm vi đã khảo sát.
- **Đề xuất:** công việc mới cần thực hiện.

Tập trung các trạng thái vào một bảng hiện trạng. Hạn chế lặp lại cụm “chưa xác minh” trong mọi phần của tài liệu.

Không coi có mã là đã kiểm thử. Không suy ra số người dùng, độ chính xác, độ trễ, phần trăm hoàn thành hoặc môi trường triển khai nếu chưa có kết quả tương ứng.

## Các điểm phải kiểm tra với EduRAG

- Role người dùng đã được triển khai thực tế.
- Quyền truy cập từng endpoint và từng trang.
- Định dạng tài liệu được hỗ trợ và cách xử lý PDF scan.
- Upload trùng tên, rollback và chunk cũ.
- Trạng thái hiệu lực của tài liệu trong retrieval.
- Hỏi đáp giới hạn trong một tài liệu.
- Ngưỡng từ chối câu hỏi không liên quan.
- Cách chọn nguồn chính và trang trích dẫn.
- Việc đưa lịch sử hội thoại vào retrieval và prompt.
- Khởi động Ollama, embedding model, ChromaDB và Docker.

Không coi việc lưu lịch sử là đã có hội thoại đa lượt. Không coi việc hiển thị nguồn là đã bảo đảm nội dung trả lời chính xác.

## Viết tài liệu

Ưu tiên bố cục người dùng yêu cầu. Nếu không có bố cục cụ thể, sử dụng:

1. Tổng quan dự án.
2. Trạng thái triển khai.
3. Phong cách thiết kế.
4. Cấu trúc các trang và chức năng.
5. Kiến trúc kỹ thuật.
6. Cây thư mục frontend và backend.
7. API endpoints.
8. Dependencies.
9. Kiến trúc bảo mật.
10. Luồng xử lý RAG.
11. Kế hoạch kiểm thử.
12. Docker và phương án triển khai.
13. Các giai đoạn tiếp theo.
14. Tiêu chí nghiệm thu và sản phẩm bàn giao.
15. Nội dung cần xác nhận.

### Trang và chức năng

Mỗi trang nên mô tả:

- Route và quyền truy cập.
- Mục đích.
- Thành phần giao diện chính.
- Hành động của người dùng.
- API hoặc dữ liệu liên quan.
- Trạng thái triển khai và giới hạn đáng chú ý.

### API

Trình bày bảng gồm:

`Method | Endpoint | Quyền truy cập | Chức năng`

Không gộp nhiều endpoint khác mục đích vào cùng một dòng.

### Kế hoạch công việc

Mỗi công việc dự kiến cần có:

`Mã | Công việc và đầu ra | Phụ thuộc | Ưu tiên | Thời lượng dự kiến | Tiêu chí nghiệm thu`

Không tự đặt ngày bắt đầu, hạn hoàn thành, người phụ trách hoặc phần trăm tiến độ. Dùng chữ “dự kiến” với thời lượng chưa được thống nhất.

### Kiểm thử RAG

Bao gồm tối thiểu:

- Câu hỏi có đáp án trực tiếp trong tài liệu.
- Câu hỏi ngoài phạm vi.
- Câu hỏi tiếp nối cần ngữ cảnh hội thoại.
- Câu hỏi giới hạn trong một tài liệu.
- Tài liệu active và inactive.
- PDF text, PDF scan và DOCX.
- Nạp lại hoặc xóa tài liệu.
- Độ đúng của nội dung, nguồn và trang.

Mỗi ca kiểm thử cần có dữ liệu đầu vào, kết quả mong đợi và cách xác minh. Không bịa kết quả đo hoặc đáp án chuẩn khi chưa có tài liệu nguồn được duyệt.

## Cách viết

- Viết tiếng Việt tự nhiên, phù hợp tài liệu đồ án CNTT.
- Đi thẳng vào nội dung dự án.
- Dùng bảng cho API, trạng thái, kiểm thử và kế hoạch công việc.
- Dùng Mermaid khi sơ đồ giúp giải thích kiến trúc hoặc luồng RAG.
- Giữ nguyên tên công nghệ, route, file, hàm và class cần thiết.
- Chỉ đưa đường dẫn mã nguồn khi giúp chứng minh một nhận định.
- Không biến tài liệu thành nhật ký làm việc hoặc báo cáo audit mã nguồn.
- Không thêm lời nhắc rằng tài liệu được tạo bởi AI.
- Không thêm phần tổng kết đối chiếu với tài liệu tham khảo.

## Phạm vi thao tác

Khi người dùng chỉ yêu cầu lập kế hoạch, chỉ tạo hoặc cập nhật file tài liệu. Không sửa mã nguồn, cài dependency, chạy migration, rebuild index, xóa dữ liệu, triển khai hoặc push Git.

Chỉ chạy kiểm tra khi cần xác minh nhận định và thao tác đó không thay đổi dữ liệu vận hành. Không tuyên bố một kiểm tra thành công nếu chưa chạy và chưa có kết quả.

## Rà soát trước khi bàn giao

Kiểm tra rằng:

- Tất cả chức năng và công nghệ đều thuộc EduRAG hiện tại.
- Hiện trạng không bị trình bày thành kế hoạch tương lai và ngược lại.
- Kết quả kiểm thử không bị suy đoán.
- Role, route, endpoint và đường dẫn được ghi đúng.
- Không có secret hoặc dữ liệu cá nhân.
- Không còn câu chữ nói về quá trình đọc, khảo sát hoặc đối chiếu tài liệu tham khảo.
- Tài liệu có thể được đọc độc lập mà không cần biết nó được tạo ra như thế nào.

Sau khi hoàn thành, trả về đường dẫn file, tóm tắt các phần chính và danh sách thông tin cần người dùng bổ sung.
