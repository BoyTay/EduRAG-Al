# Đánh giá EduRAG (nội dung 6 của đề tài)

Bộ kiểm thử gồm **59 câu**: 48 câu trong `cases_eval.json` (tài liệu Tuần định hướng, mã S/P/M/G theo
`docs/ke_hoach_kiem_thu_cau_hoi_pdf_scan.md`) và 11 câu trong `../llm_benchmark/cases.json` (Sổ tay sinh viên,
Quy chế đào tạo, Chuẩn đầu ra).

| Nhóm | Mã | Số câu |
|---|---|---:|
| Dữ kiện trực tiếp, số tiền, ngày | S-01…S-06, S-20…S-22, S-27 | 10 |
| Câu tổng hợp theo mục | S-07…S-19, S-23 | 14 |
| Trách nhiệm đơn vị | S-24…S-26, S-28, S-29 | 5 |
| Biến thể (không dấu, đảo câu, đồng nghĩa, tiền đề sai) | P-01…P-10 | 10 |
| Hội thoại nhiều lượt + kiểm tra cách ly phiên | M-01…M-03 | 3 |
| Khóa tài liệu, ngoài phạm vi, tiền đề sai | G-01…G-06 | 6 |
| Bộ cũ (Sổ tay, Quy chế, Chuẩn đầu ra) | – | 11 |

## Chỉ số

- **Độ liên quan:** tỷ lệ ý bắt buộc xuất hiện, không chứa chi tiết cấm, điểm truy xuất, từ chối đúng câu ngoài phạm vi.
- **Tính đúng nguồn:** trang chính đúng, trang đúng nằm trong nguồn trích, không lẫn tài liệu khác, không hiện nguồn khi từ chối.
- **Thời gian phản hồi:** p50, p95, lớn nhất, theo từng nhóm câu hỏi.
- **Tài nguyên:** đỉnh RAM backend, RAM Ollama, VRAM GPU trong lúc trả lời (cần `pip install psutil`; VRAM cần `nvidia-smi`).

## Chạy

```powershell
pip install psutil
$env:PYTHONPATH="backend;experiments/llm_benchmark"
python experiments/evaluation/run_eval.py                 # 1 vòng, dùng cấu hình ứng dụng
python experiments/evaluation/run_eval.py --repeats 3     # 3 vòng để lấy độ ổn định
python experiments/evaluation/run_eval.py --case-id S-07  # một câu
python experiments/evaluation/run_eval.py --report-only experiments/evaluation/results_eval.json
```

Kết quả thô: `results_eval.json`. Báo cáo tổng hợp: `bao_cao_danh_gia.md`.

## Lưu ý

- Cần nạp đúng tài liệu vào ChromaDB trước khi chạy (PDF Tuần định hướng, Sổ tay sinh viên, Quy chế, Chuẩn đầu ra).
  Không rebuild index giữa các vòng của cùng một đợt đo.
- Ground truth của `cases_eval.json` lấy từ bảng trong kế hoạch kiểm thử, đánh dấu `draft_from_plan_needs_pdf_review`.
  Phải đối chiếu từng câu với PDF rồi mới dùng số liệu trong báo cáo.
- Kết luận tự động dựa trên từ khóa và trang nguồn; câu có `note` (S-07, P-05, G-05) cần chấm tay thêm.
- Tiêu chí "ổn để demo" theo mục 8 của kế hoạch: không lỗi nghiêm trọng, ≥ 90% lượt đạt, ≥ 90% trang chính đúng.
