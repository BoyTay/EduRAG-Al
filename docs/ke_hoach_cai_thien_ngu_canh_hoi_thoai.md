# Kế hoạch cải thiện nhận diện ngữ cảnh hội thoại EduRAG

## 1. Mục tiêu và phạm vi

Ngăn câu hỏi độc lập bị kéo sang chủ đề của lượt trước, đồng thời giữ khả năng trả lời câu hỏi tiếp nối thực sự cần ngữ cảnh. Tình huống kiểm thử trọng tâm: sau câu hỏi về TOEIC tương đương Bậc 4, người dùng hỏi Điểm A trên thang điểm 4 là mấy; hệ thống phải truy hồi quy định về điểm học phần, không tiếp tục truy hồi bảng chuẩn ngoại ngữ.

Phạm vi gồm chọn ngữ cảnh cho truy hồi, chọn lịch sử đưa vào prompt và kiểm thử hội thoại đa lượt. Không đổi model, embedding, temperature, cấu trúc bảng SQLite hay giao diện trong đợt đầu. Không thay đổi cơ chế giới hạn `document_filename` do người dùng chọn hoặc lọc tài liệu còn hiệu lực.

## 2. Hiện trạng có căn cứ

- **Đã có mã:** `POST /chat` lấy tối đa 4 lượt gần nhất của đúng tài khoản và `session_id` rồi truyền vào `RAGChain.achat()` (`backend/main.py`). Lịch sử được lưu cùng nguồn trả lời trong `ChatHistory` (`backend/db.py`).
- **Đã có mã:** `build_retrieval_query()` ghép câu trước vào mọi câu hỏi khi có lịch sử; điều kiện độ dài dưới 20 ký tự chỉ đổi cách ghép, không quyết định có cần ngữ cảnh hay không (`backend/rag_chain.py`). Cùng lịch sử đó còn được đưa vào prompt tạo câu trả lời.
- **Đã có mã:** nút chat mới ở frontend tạo `sessionId` mới; API chat gửi `session_id` và có thể gửi `document_filename` (`frontend/src/stores/chatStore.ts`, `frontend/src/services/api.ts`).
- **Chưa xác minh:** chưa có bộ kiểm thử hồi quy riêng cho chuyển chủ đề giữa hai lượt trong cùng một session. Bộ kiểm thử hiện có có ca tiếp nối nhưng không chứng minh câu hỏi độc lập sẽ bỏ qua lượt trước.
- **Đề xuất:** phân loại nhu cầu ngữ cảnh trước truy hồi; chỉ chuyển phần thông tin còn thiếu từ lượt trước sang câu hỏi hiện tại khi cần.

## 3. Hành vi mong muốn

| Loại lượt hỏi | Ví dụ | Truy hồi và prompt mong muốn |
|---|---|---|
| Câu độc lập | Sau câu TOEIC, hỏi Điểm A tương ứng thang điểm 4 là mấy? | Chỉ dùng câu hiện tại để truy hồi; không đưa nội dung TOEIC vào prompt trả lời. |
| Tiếp nối rõ ràng | Sau câu về thời gian Tuần định hướng, hỏi Còn địa điểm tổ chức ở đâu? | Bổ sung đối tượng Tuần định hướng từ lượt trước; truy hồi lại tài liệu, không dùng câu trả lời cũ làm bằng chứng. |
| Tiếp nối có chủ đề mới | Sau câu về chuẩn đầu ra tiếng Anh, hỏi Còn điều kiện tin học thì sao? | Giữ khung chuẩn đầu ra nhưng ưu tiên chủ đề tin học mới; không kéo các ngưỡng tiếng Anh sang câu trả lời. |
| Thiếu tham chiếu | Hỏi Còn nữa không? khi không có lượt trước phù hợp | Yêu cầu làm rõ, không chọn một tài liệu ngẫu nhiên. |
| Hỏi theo một tài liệu | Người dùng chọn `document_filename` | Tôn trọng phạm vi tài liệu đã chọn; không tự đổi file theo lịch sử. |

Việc cùng xuất hiện số 4 không chứng minh hai câu cùng chủ đề: Bậc 4 ngoại ngữ và thang điểm 4 học phần phải được xử lý như hai khái niệm khác nhau.

## 4. Thiết kế xử lý đề xuất

1. **Phân loại lượt hỏi trước retrieval:** hàm thuần, có thể kiểm thử độc lập, trả một trong ba trạng thái `independent`, `follow_up`, `needs_clarification`. Không dùng độ dài ký tự làm tiêu chí duy nhất. Nhận diện tham chiếu thiếu đối tượng như đó, này, trường hợp ấy, còn bao nhiêu, ở đâu; đồng thời kiểm tra câu hiện tại đã nêu rõ đối tượng/thuộc tính hay chưa. Chủ đề được nêu rõ trong câu hiện tại phải có ưu tiên cao hơn từ nối chung như còn. Khởi đầu bằng quy tắc xác định, chưa thêm một lượt gọi LLM chỉ để phân loại.
2. **Tạo truy vấn phù hợp từng trạng thái:** `independent` dùng nguyên câu hiện tại; `follow_up` tạo câu hỏi tự đủ nghĩa bằng cách bổ sung duy nhất đối tượng hoặc thuộc tính bị lược từ lượt liên quan gần nhất, không nối nguyên văn toàn bộ câu trước. Nếu không xác định được tham chiếu đáng tin cậy, chuyển sang `needs_clarification`. Không lấy nội dung câu trả lời cũ làm sự thật; mọi đáp án vẫn phải được xác nhận từ tài liệu truy hồi mới.
3. **Giới hạn ngữ cảnh đưa vào prompt:** câu độc lập không nhận lịch sử cũ trong prompt; câu tiếp nối chỉ nhận phần lịch sử cần để hiểu tham chiếu. Truyền cùng quyết định phân loại cho cả bước truy hồi và bước tạo câu trả lời, tránh trường hợp truy hồi đúng tài liệu nhưng model lại diễn giải theo chủ đề cũ. Giữ giới hạn độ dài và quyền sở hữu session hiện có.
4. **Giữ ranh giới nguồn và quyền:** nếu dùng nguồn của lượt trước làm gợi ý chọn tài liệu, chỉ dùng metadata nguồn đã lưu trong `ChatHistory`, kiểm tra file còn active và vẫn thuộc phạm vi truy cập; không tự động khóa theo file cũ khi câu hiện tại nêu chủ đề mới. `document_filename` do người dùng chọn luôn ưu tiên hơn gợi ý từ lịch sử.
5. **Phương án sau kiểm thử:** nếu các quy tắc còn phân loại sai nhiều câu diễn đạt tự nhiên, đánh giá thêm bước viết lại câu hỏi bằng model hiện có ở cấu hình ổn định. Chỉ triển khai khi có bộ ca chuẩn và chứng minh cải thiện; không đưa lời giải này vào đợt đầu theo mặc định.

## 5. Công việc và tiêu chí nghiệm thu

| Mã | Công việc và đầu ra | Phụ thuộc | Ưu tiên | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| CTX-01 | Bổ sung ca hồi quy độc lập, tiếp nối, đổi chủ đề, thiếu tham chiếu và hỏi theo tài liệu trong `tests/test_rag_retrieval.py` | Không | Cao | Các ca hiện tái hiện được lỗi hoặc khóa hành vi mong muốn; dữ liệu mong đợi có nguồn rõ ràng. |
| CTX-02 | Tách logic phân loại và viết lại câu hỏi khỏi `build_retrieval_query()` | CTX-01 | Cao | Câu độc lập không chứa từ khóa của lượt trước; câu tiếp nối tự đủ nghĩa mà không chép nguyên câu cũ. |
| CTX-03 | Dùng cùng quyết định để chọn lịch sử cho retrieval và prompt trong `RAGChain.achat()` | CTX-02 | Cao | Chuyển chủ đề không mang lịch sử TOEIC vào prompt; tiếp nối vẫn hiểu đúng tham chiếu. |
| CTX-04 | Kiểm tra `POST /chat` với session thuộc đúng tài khoản, `document_filename`, file inactive và câu mơ hồ | CTX-03 | Cao | Không lộ lịch sử khác tài khoản/session; không vượt phạm vi tài liệu đã chọn; câu thiếu tham chiếu được yêu cầu làm rõ. |
| CTX-05 | Chạy bộ unit test, bộ câu hỏi RAG hiện có và kiểm thử thực tế trên Docker | CTX-04 | Cao | Không hồi quy các ca tiếp nối; trường hợp Điểm A trích đúng tài liệu/quy định nếu có nguồn, nếu không có thì từ chối đúng cách. |

Không đặt tỷ lệ chính xác hoặc thời hạn hoàn thành trước khi có bộ ca kiểm thử và kết quả chạy tương ứng.

## 6. Bộ ca kiểm thử tối thiểu

- Câu TOEIC Bậc 4 → Điểm A thang 4: xác nhận truy vấn lượt hai không chứa TOEIC/Bậc 4; nguồn không bị giữ ở tài liệu chuẩn ngoại ngữ chỉ vì lượt trước.
- Câu thời gian Tuần định hướng → Còn địa điểm ở đâu?: xác nhận đối tượng được bổ sung và câu trả lời có nguồn về địa điểm.
- Câu chuẩn đầu ra tiếng Anh → Còn tin học thì sao?: xác nhận giữ đúng khung chuẩn đầu ra nhưng đổi thuộc tính cần truy hồi.
- Câu độc lập ngắn nhưng đủ nghĩa, và câu dài nhưng còn đại từ chỉ định: chứng minh không phân loại chỉ theo độ dài.
- Câu Còn nữa không? ở session mới; câu hỏi sau một lượt bị từ chối; câu hỏi sau khi đổi sang session khác: không tự tạo tham chiếu giả.
- Hỏi theo `document_filename`, tài liệu chuyển inactive giữa hai lượt, hai tài khoản dùng `session_id` giống nhau: không vượt bộ lọc truy hồi và không dùng nguồn đã hết hiệu lực.
- Đối chiếu đáp án, file nguồn và trang; kiểm tra số lần gọi model để không phát sinh lượt gọi phân loại ngoài dự kiến.

## 7. Điều kiện hoàn tất

Lỗi chuyển từ TOEIC sang Điểm A không còn tái hiện ở cùng session; các câu tiếp nối hợp lệ vẫn trả lời được; câu mơ hồ được yêu cầu làm rõ hoặc từ chối phù hợp; bộ lọc tài liệu, session và quyền truy cập không hồi quy. Chỉ kết luận đạt sau khi kiểm thử tự động và thử trên backend đang chạy, không dựa vào một câu trả lời đúng đơn lẻ.
