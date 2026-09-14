# Kế hoạch kiểm thử câu hỏi RAG trên PDF scan EduRAG

**Ngày lập kế hoạch:** 14/09/2026  
**Trạng thái:** Đã thực hiện smoke test vòng 1 ngày 14/09/2026; bộ đánh giá đầy đủ S-01 đến S-29 và các lần lặp ổn định chưa thực hiện. Kết quả chi tiết được ghi tại `docs/ket_qua_smoke_pdf_scan_rag_2026-09-14.md`.

## 1. Mục tiêu

Kế hoạch này dùng nhiều dạng câu hỏi trên cùng một PDF scan để xác định câu trả lời của EduRAG có:

- Đúng dữ kiện, điều kiện áp dụng và mức độ bắt buộc trong văn bản.
- Đầy đủ với câu hỏi tổng hợp, không chỉ đúng một phần.
- Chỉ sử dụng nội dung có trong tài liệu, không suy diễn hoặc đồng ý với tiền đề sai.
- Chọn đúng tài liệu, đúng trang nguồn chính và không hiển thị quá nhiều trang không hỗ trợ câu trả lời.
- Ổn định khi diễn đạt lại câu hỏi hoặc hỏi tiếp trong cùng hội thoại.
- Giữ đúng chữ tiếng Việt, ngày tháng, số tiền và ranh giới số lượng sau OCR.

## 2. Phạm vi và dữ liệu thử nghiệm

### 2.1 Tài liệu chuẩn vòng đầu

- Tệp: `data/1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf`.
- Kích thước: 351.556 byte.
- SHA-256: `BB20A74ADB30DEE897DAC4FFE176E161F03C7F16E3C24443C7817667723D01AC`.
- Đặc điểm: PDF scan 5 trang, không có native text.
- Luồng nạp hiện tại: Tesseract 5.5.0, ngôn ngữ `vie`, 300 DPI; tài liệu đã tạo 20 chunk trong lần rebuild đã được ghi nhận.
- Cấu hình retrieval hiện tại: `RETRIEVAL_CANDIDATE_K=30`, `TOP_K=8`, `MIN_RELEVANCE_SCORE=0.30`.
- Model sinh câu trả lời: `qwen2.5:7b` qua Ollama.

Không thay đổi PDF, OCR cache, active collection hoặc cấu hình trong khi chạy một vòng benchmark. Nếu một yếu tố thay đổi, phải tạo vòng chạy mới và ghi lại phiên bản.

### 2.2 Ground truth cần chuẩn bị

Hai người trong nhóm nên đối chiếu trực tiếp từng trang PDF và duyệt một tệp ground truth trước khi chấm. Mỗi bản ghi gồm:

`id | question | variants | expected_facts | forbidden_facts | expected_document | primary_pages | answer_mode`

Quy ước `primary_pages` dùng số trang one-based như trên trình xem PDF. Ground truth không sao chép nguyên đoạn dài; chỉ lưu các dữ kiện cần có và dữ kiện không được xuất hiện.

## 3. Ma trận câu hỏi chính

### 3.1 Dữ kiện trực tiếp và điều kiện bắt buộc

| ID | Câu hỏi chuẩn | Dữ kiện bắt buộc trong câu trả lời | Trang chính dự kiến |
|---|---|---|---|
| S-01 | Kế hoạch này tổ chức hoạt động gì cho đối tượng nào? | Tuần định hướng; Tân sinh viên khóa 50; năm học 2026–2027 | 1 |
| S-02 | Tuần định hướng diễn ra từ ngày nào đến ngày nào? | Từ 24/8/2026 đến hết 28/8/2026 | 1 |
| S-03 | Đối tượng tham gia Tuần định hướng là ai? | Tất cả Tân sinh viên khóa 50 tuyển sinh năm 2026 | 1 |
| S-04 | Tân sinh viên khóa 50 có bắt buộc tham gia đầy đủ không? | Có; bắt buộc tham gia đầy đủ các hoạt động | 1 |
| S-05 | Mục đích của Tuần định hướng là gì? | Dấu ấn ban đầu; phương pháp/kỹ năng; giới thiệu ngành; gắn kết và câu lạc bộ | 1 |
| S-06 | Tuần định hướng được tổ chức ở đâu? | Theo danh sách phân bố kèm theo; không tự bịa tên địa điểm | 2 |

### 3.2 Câu hỏi tổng hợp mục NỘI DUNG

| ID | Câu hỏi chuẩn | Dữ kiện bắt buộc trong câu trả lời | Trang chính dự kiến |
|---|---|---|---|
| S-07 | Trong Tuần định hướng, tân sinh viên được hướng dẫn những nội dung gì? | Đủ 35 ý nguyên tử đã khai báo trong pipeline; trình bày thành 4 nhóm | 2 |
| S-08 | Phần giới thiệu về Khoa bao gồm những gì? | Tổng quan, tầm nhìn, sứ mệnh, cơ cấu, giảng viên, ngành/chương trình, định hướng nghề nghiệp | 2 |
| S-09 | Sinh viên được hướng dẫn sử dụng các hệ thống và nguồn thông tin nào? | Hệ thống CNTT, kênh truyền thông, thư viện, an toàn Internet/mạng xã hội | 2 |
| S-10 | Những chức năng học vụ và thủ tục nào được hướng dẫn? | Thời khóa biểu, lịch thi, đăng ký học phần, thủ tục hành chính | 2 |
| S-11 | Sinh viên được hướng dẫn liên hệ với những đơn vị nào? | Khoa, phòng chức năng, Đoàn–Hội | 2 |
| S-12 | Những quy chế và quy định nào được phổ biến? | Chương trình khóa 50, quy chế đào tạo đại học, bảo đảm chất lượng, công tác sinh viên | 2 |
| S-13 | Tân sinh viên được trang bị những kỹ năng nào? | Tự học, nghiên cứu, thuyết trình, giao tiếp, nhóm, quản lý thời gian/tài chính, thích nghi và tự lập | 2 |
| S-14 | Quy tắc văn hóa nào được phổ biến? | Quy tắc văn hóa ứng xử của người học; không thêm quy định trang phục nếu nguồn không nêu | 2 |
| S-15 | Có những hoạt động kết nối và hỗ trợ nào? | CCSSS, ngoại khóa, Đoàn–Hội, câu lạc bộ/đội nhóm, hỗ trợ, học bổng, hội nhập | 2 |
| S-16 | Nội dung định hướng nghề nghiệp gồm những gì? | Nghề nghiệp, thực tập và việc làm | 2 |
| S-17 | Sinh viên cần xây dựng mục tiêu và kế hoạch gì? | Mục tiêu học tập/rèn luyện học kỳ I; kế hoạch và cam kết tuân thủ | 2 |
| S-18 | Hoạt động giao lưu có thể có những đối tượng nào? | Cựu sinh viên, doanh nhân, nhà tuyển dụng, chuyên gia; giữ điều kiện “nếu có” khi cần | 2 |
| S-19 | Cuối phần nội dung, Khoa cần hỗ trợ giải quyết vấn đề gì? | Câu hỏi, khó khăn, vướng mắc; nội dung theo đặc thù ngành và điều kiện Khoa | 2 |

### 3.3 Số tiền và ranh giới số lượng

| ID | Câu hỏi chuẩn | Dữ kiện bắt buộc trong câu trả lời | Trang chính dự kiến |
|---|---|---|---|
| S-20 | Khoa có dưới 150 tân sinh viên được hỗ trợ bao nhiêu? | 5.000.000 đồng | 3 |
| S-21 | Khoa có đúng 150 tân sinh viên được hỗ trợ bao nhiêu? | 7.000.000 đồng; ranh giới “từ 150 trở lên” | 3 |
| S-22 | Khoa có 200 tân sinh viên được hỗ trợ bao nhiêu? | 7.000.000 đồng | 3 |
| S-23 | Khoản kinh phí hỗ trợ dùng cho những hạng mục nào? | Backdrop, trang trí, âm thanh, ánh sáng, văn nghệ, in ấn và quà nếu có | 3 |

Các câu S-20 đến S-23 phải kiểm tra riêng lỗi OCR mất dấu. Không chấp nhận các dạng `đồng/chăn`, `đồng/chãn` hoặc biến “đồng chẵn” thành đơn vị tính theo người/tháng.

### 3.4 Trách nhiệm tổ chức

| ID | Câu hỏi chuẩn | Dữ kiện bắt buộc trong câu trả lời | Trang chính dự kiến |
|---|---|---|---|
| S-24 | Phòng Công tác sinh viên có trách nhiệm gì? | Tổ chức/theo dõi, phối hợp thông báo, phổ biến quy chế, báo cáo tổng kết | 3 |
| S-25 | Phòng Quản lý đào tạo hỗ trợ nội dung gì? | Hướng dẫn xây dựng kịch bản quy chế đào tạo và xếp lịch | 3 |
| S-26 | Phòng Quản trị Cơ sở vật chất chuẩn bị gì? | Hội trường, âm thanh, ánh sáng, màn hình/máy chiếu, bàn ghế và hỗ trợ kỹ thuật | 3–4 |
| S-27 | Các Khoa phải gửi phân công trước thời điểm nào? | Trước 11h00 ngày 20/8/2026 | 4 |
| S-28 | Đoàn Thanh niên – Hội sinh viên phụ trách nội dung gì? | Infographic/video, giới thiệu tổ chức/CLB, hướng dẫn đăng ký và hoạt động hỗ trợ | 4 |
| S-29 | Tân sinh viên có trách nhiệm gì khi tham gia? | Thực hiện kế hoạch, đầy đủ, đúng giờ, tập trung, ghi chép; không thay bằng trách nhiệm của Khoa | 4 |

## 4. Biến thể câu hỏi và hội thoại đa lượt

Mỗi câu S-01 đến S-29 chạy thêm ít nhất một biến thể không làm thay đổi ý nghĩa:

- Viết không dấu hoặc thiếu một vài dấu: `duoi 150 tan sinh vien duoc ho tro bao nhieu`.
- Đảo trật tự câu: `Mức 7 triệu áp dụng khi Khoa có bao nhiêu tân sinh viên?`.
- Dùng từ đồng nghĩa: `lịch học` thay cho `thời khóa biểu`, `hỗ trợ tài chính` thay cho `kinh phí`.
- Chứa tiền đề sai: `Tuần định hướng diễn ra ngày 20/8/2026 đúng không?` — hệ thống phải sửa lại theo nguồn, không đồng ý.
- Yêu cầu đầy đủ: `Hãy liệt kê đầy đủ, không bỏ sót nội dung Tuần định hướng.` — cho phép câu trả lời dài hơn nhưng vẫn phải có nguồn.

Ca đa lượt dùng cùng `session_id`:

| ID | Chuỗi câu hỏi | Kết quả mong đợi |
|---|---|---|
| M-01 | “Đối tượng tham gia là ai?” → “Đối tượng đó có bắt buộc tham gia đầy đủ không?” | Lượt hai hiểu “đối tượng đó” là Tân sinh viên khóa 50 và trả lời nghĩa vụ đúng |
| M-02 | “Khoa có 200 sinh viên được bao nhiêu?” → “Mức đó áp dụng từ bao nhiêu sinh viên?” | Lượt hai hiểu “mức đó” là 7.000.000 đồng và nêu ranh giới từ 150 |
| M-03 | “Tuần định hướng diễn ra khi nào?” → “Các em cần làm gì khi tham gia?” | Lượt hai chuyển đúng từ thời gian sang trách nhiệm Tân sinh viên, không lấy trách nhiệm Khoa |

Mỗi chuỗi đa lượt phải chạy lại với `session_id` mới để xác nhận lịch sử cũ không rò sang phiên khác.

## 5. Giới hạn tài liệu và câu hỏi ngoài phạm vi

| ID | Câu hỏi/chế độ | Kết quả mong đợi |
|---|---|---|
| G-01 | S-07 với `document_filename` là tệp Tuần định hướng | Mọi nguồn trả về cùng filename đã chọn |
| G-02 | S-07 ở chế độ tìm toàn kho | Vẫn ưu tiên đúng tài liệu Tuần định hướng, không dùng Sổ tay hoặc Quy chế thay mục NỘI DUNG |
| G-03 | “Học phí học kỳ I của khóa 50 là bao nhiêu?” | Từ chối vì PDF này không có mức học phí |
| G-04 | “Hiệu trưởng hiện tại tên gì?” | Từ chối nếu phần OCR không cung cấp tên có thể xác minh |
| G-05 | “Mỗi sinh viên được nhận 7.000.000 đồng đúng không?” | Bác bỏ tiền đề; kinh phí hỗ trợ cho Khoa tổ chức, không phải cấp cho từng sinh viên |
| G-06 | Đặt `document_filename` sang một tài liệu khác rồi hỏi mức kinh phí | Không lấy dữ liệu từ PDF Tuần định hướng; từ chối nếu tài liệu được chọn không có dữ kiện |

## 6. Cách chạy

### 6.1 Chuẩn bị

1. Ghi lại commit, SHA-256 tài liệu, model Ollama và toàn bộ biến retrieval/OCR.
2. Xác nhận `GET /health` healthy và số vector không đổi trong suốt vòng chạy.
3. Sao lưu hoặc dùng database test riêng nếu tự động hóa; không ghi hàng loạt vào lịch sử vận hành thật.
4. Duyệt ground truth bởi người đọc trực tiếp PDF trước khi chấm.

### 6.2 Thứ tự thực hiện

1. **OCR integrity:** đối chiếu text quan trọng trên cả 5 trang, tập trung ngày, số tiền, dấu tiếng Việt, tên đơn vị và trang xoay.
2. **Direct QA:** chạy S-01 đến S-29, mỗi câu dùng phiên mới.
3. **Paraphrase:** chạy các biến thể có dấu, không dấu, đồng nghĩa và tiền đề sai.
4. **Multi-turn:** chạy M-01 đến M-03 với cùng phiên và kiểm tra cách ly phiên.
5. **Scope/refusal:** chạy G-01 đến G-06.
6. **Stability:** lặp lại các ca quan trọng S-02, S-04, S-07, S-13, S-21, S-27, S-29 và G-05 ba lần.
7. **Tổng hợp:** ghi lỗi theo tầng OCR, retrieval, generation, citation hoặc UI; không chỉ ghi chung là “AI trả lời sai”.

Không rebuild index giữa các lượt của cùng một vòng. Nếu cần sửa OCR/chunk/prompt rồi rebuild, xem đó là vòng benchmark mới.

## 7. Chấm điểm và dữ liệu cần ghi

Mỗi lượt chạy lưu:

`run_id | case_id | question | answer | sources | primary_page | retrieval_score | duration_ms | expected_facts_hit | unexpected_facts | verdict | notes`

Thang điểm đề xuất cho từng câu:

- **Đúng dữ kiện (0–2):** không sai ngày, số, đối tượng, điều kiện hoặc mức độ bắt buộc.
- **Đầy đủ (0–2):** bao phủ các `expected_facts`; S-07 tính recall trên 35 ý nguyên tử.
- **Có căn cứ (0–2):** không có thông tin ngoài các đoạn nguồn được gửi cho model.
- **Nguồn và trang (0–2):** tài liệu đúng, trang chính hỗ trợ trực tiếp câu trả lời.
- **Trình bày (0–1):** rõ ràng, không chèn tên file/nguồn vào nội dung, không có ký hiệu Markdown thừa.

Một lỗi được xếp **nghiêm trọng** nếu sai số tiền, ngày, ranh giới 150, đối tượng, nghĩa vụ bắt buộc; bịa dữ kiện; trả lời từ tài liệu khác khi đã khóa tài liệu; hoặc dẫn trang không chứa bằng chứng.

## 8. Ngưỡng kết luận đề xuất

Chỉ kết luận câu trả lời “ổn để demo” khi đồng thời đạt:

- Không có lỗi nghiêm trọng trong toàn bộ vòng chạy.
- S-07 đạt 35/35 ý trong cả ba lần lặp và vẫn đúng bốn nhóm.
- Ít nhất 90% lượt chạy đạt từ 8/9 điểm.
- Ít nhất 90% nguồn chính trỏ đúng trang ground truth.
- Tất cả câu ngoài phạm vi và tiền đề sai được từ chối hoặc đính chính phù hợp.
- Không có biến thể cùng nghĩa nào làm thay đổi số tiền, ngày, điều kiện hoặc nghĩa vụ.
- Ghi được p50, p95; ngưỡng độ trễ chấp nhận cuối cùng do nhóm dự án chốt sau vòng đầu.

Ngưỡng trên là tiêu chí đề xuất, chưa phải kết quả thực tế.

## 9. Phân loại lỗi và hướng xử lý

- **OCR:** text trong Chroma đã sai hoặc thiếu → sửa OCR/preprocessing rồi rebuild bằng `POST /admin/rebuild-index`.
- **Chunk/section:** text đúng nhưng ý bị chia hoặc lẫn mục kế tiếp → sửa metadata/section-aware chunking.
- **Retrieval:** chunk đúng tồn tại nhưng không vào context → điều chỉnh query expansion, candidate pool hoặc reranking.
- **Generation:** context đủ nhưng câu trả lời bỏ ý/suy diễn → điều chỉnh fact coverage, prompt hoặc fallback có bằng chứng.
- **Citation:** câu trả lời đúng nhưng trang chính sai → sửa support scoring và chọn nguồn chính.
- **UI:** API đúng nhưng giao diện cắt dòng, mất bullet hoặc hiển thị nguồn sai → sửa frontend, không chỉnh RAG để che lỗi UI.

Sau mỗi bản sửa, chạy lại toàn bộ nhóm ca liên quan và tối thiểu bộ regression S-02, S-04, S-07, S-13, S-21, S-27, S-29, G-01, G-05 và M-02.

## 10. Đầu ra của vòng kiểm thử

- Ground truth đã duyệt và version hóa.
- File kết quả thô của từng request, không chứa token đăng nhập.
- Báo cáo tổng hợp theo case, loại lỗi, điểm và độ trễ.
- Danh sách lỗi có câu hỏi tái hiện, câu trả lời thực tế, dữ kiện mong đợi và trang PDF.
- Kết luận: đạt để demo, đạt có điều kiện hoặc chưa đạt; không dùng nhận xét cảm tính thay số liệu.
