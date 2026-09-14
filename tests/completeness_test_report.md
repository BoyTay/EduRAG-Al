# Báo cáo Kiểm thử Tính Hoàn Thiện Câu Trả Lời EduRAG AI

- **Thời gian kiểm thử**: `2026-09-15 01:13:31`
- **Mô hình LLM**: `Qwen2.5-7B` (Ollama)
- **Mô hình Embedding**: `AITeamVN/Vietnamese_Embedding`
- **Số tài liệu tham chiếu**: `4 tệp active`

## 1. Tổng quan Chỉ số Đạt chuẩn (Overview Metrics)

| Tổng số TC | Đạt (PASS) | Cảnh báo (WARN) | Không đạt (FAIL) | Tỷ lệ Đạt | Thời gian TB |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **1** | **0** | **0** | **100.0%** | **6.59s** |

## 2. Kết quả theo Phân nhóm Tài liệu (Group Breakdown)

| Nhóm kiểm thử | Độ ưu tiên | Tổng TC | PASS | WARN | FAIL | Tỷ lệ đạt |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **PDF Scan: 1340-KH-DHDL** | Ưu tiên 1 | 1 | 1 | 0 | 0 | **100.0%** |

---

## 3. Bảng Chi tiết Từng Ca Kiểm thử (Detailed Test Cases)

| Mã TC | Nhóm | Câu hỏi | Trạng thái | Điểm tương đồng | Lỗi / Cảnh báo ghi nhận |
|---|---|---|:---:|:---:|---|
| **TC-SCAN-04** | PDF Scan: 1340-KH-DHDL | Kế hoạch số 1340/KH-ĐHĐL được ban hành vào ngày tháng năm nào và do ai ban hành? | ✅ PASS | `0.096` | Thỏa mãn 6 trục tiêu chí |

---

## 4. Chi tiết Nội dung & Đánh giá 6 Trục (Rubric Inspection)

### TC-SCAN-04: Kế hoạch số 1340/KH-ĐHĐL được ban hành vào ngày tháng năm nào và do ai ban hành? — ✅ PASS

- **Nhóm**: `PDF Scan: 1340-KH-DHDL` (Độ ưu tiên: 1)
- **Thời gian xử lý**: `6.59s` | **Evidence Score**: `0.096`

**Kết quả kiểm tra 6 tiêu chuẩn:**
- **C1 (Độ bao phủ & Đầy đủ)**: ✅ Đạt
- **C2 (Toàn vẹn câu chữ)**: ✅ Đạt
- **C3 (Chống bịa đặt - Rule 14)**: ✅ Đạt
- **C4 (Chính xác dữ liệu & OCR)**: ✅ Đạt
- **C5 (Độ chính xác nguồn & trang)**: ✅ Đạt
- **C6 (Hội thoại tiếp nối / Từ chối)**: ✅ Đạt

**Nội dung câu trả lời của AI:**
> Kế hoạch số 1340/KH-ĐHĐL được ban hành vào ngày {. tháng 8 năm 2026, do Trường Đại học Đà Lạt ban hành.

**Trích dẫn nguồn:**
- File: `1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf` | Trang: `1` | Đoạn: `...`
- File: `1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf` | Trang: `3` | Đoạn: `...`
- File: `1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf` | Trang: `5` | Đoạn: `...`
- File: `1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf` | Trang: `4` | Đoạn: `...`
- File: `1340-KH-DHDL_Ke-hoach-Tuan-Dinh-huong-Tan-SV-K50_12082026.pdf` | Trang: `2` | Đoạn: `...`

---

## 5. Đánh giá & Khuyến nghị Tinh chỉnh Hệ thống (Actionable Insights)

> [!TIP]
> Ngưỡng `MIN_RELEVANCE_SCORE=0.30` hoạt động rất tốt với mô hình `AITeamVN/Vietnamese_Embedding`, không có câu hỏi hợp lệ nào bị từ chối sai.

> [!NOTE]
> Hệ thống tuân thủ 100% Rule 14: Không xuất hiện câu kết đạo đức, giáo điều hoặc tự sinh nghĩa vụ.
