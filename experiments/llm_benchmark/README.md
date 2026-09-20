# EduRAG local LLM benchmark

So sánh các model Ollama bằng đúng retrieval, prompt và hậu xử lý của EduRAG.

## Chạy smoke benchmark

```powershell
$env:PYTHONPATH="backend"
python experiments/llm_benchmark/run_benchmark.py
```

Mặc định script chạy `qwen2.5:7b`, `qwen3.5:9b` và `gemma4:12b` ở
temperature `0.3`; lượt rà soát danh sách dùng temperature `0.0`.

Chạy một model hoặc một case:

```powershell
python experiments/llm_benchmark/run_benchmark.py --models qwen3.5:9b
python experiments/llm_benchmark/run_benchmark.py --case-id fact_exam_weight
python experiments/llm_benchmark/run_benchmark.py --models qwen3.5:9b --repeats 2
```

`results_smoke.json` chứa nguyên câu trả lời, thời gian, coverage của các ý bắt
buộc, chi tiết không được phép xuất hiện, nguồn/trang và kết quả từ chối. Điểm
tự nhiên và các lỗi suy diễn ngoài danh sách vẫn cần được duyệt thủ công trước
khi chọn model.
