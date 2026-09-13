# Báo cáo spike dependency PP-OCRv6 CPU

**Ngày thực hiện:** 13/09/2026  
**Phạm vi:** thử nghiệm dependency tách biệt, chưa tích hợp OCR vào mã nguồn production  
**Kết luận:** **ĐẠT CÓ ĐIỀU KIỆN** để chuyển sang giai đoạn triển khai

## 1. Phạm vi và nguyên tắc cô lập

Spike được thực hiện trong `experiments/ppocrv6_cpu/` bằng các Docker image riêng. Các container thử nghiệm không mount `data/`, SQLite hoặc ChromaDB, không gọi API backend và không thay đổi dữ liệu dự án.

Không thay đổi các file production sau:

- `backend/requirements.txt`;
- `Dockerfile.backend`;
- `docker-compose.yml`;
- `backend/admin.py`, các luồng upload, rebuild index và `scripts/build_index.py`.

Ảnh smoke được tạo ngay trong container, chỉ chứa bốn dòng tiếng Việt giả lập không nhạy cảm. Không sử dụng PDF thật của dự án.

## 2. Môi trường thử nghiệm

| Thành phần | Giá trị đã xác minh |
|---|---|
| Host/container runtime | Docker Desktop trên WSL2 |
| Base image | `python:3.11-slim` |
| Hệ điều hành trong image | Debian GNU/Linux trixie |
| Kiến trúc | `x86_64` |
| Python | `3.11.16` |
| glibc | `2.41` |
| CPU nhìn thấy trong container | 24 logical CPU |
| RAM nhìn thấy trong container | 12.103.828 kB, khoảng 11,54 GiB |
| Thiết bị Paddle | `cpu` |
| Concurrency OCR | 1 tiến trình, tuần tự |

Image backend làm mốc tương thích là `edurag_backend:latest`, kích thước 3.228.301.528 byte. Image spike độc lập có kích thước 517.947.706 byte; image ghép với backend có kích thước 3.673.876.062 byte. Phần OCR làm image backend tăng khoảng 445,6 MB trong spike này.

## 3. Bộ phiên bản đã thử

### 3.1. Bộ phiên bản chạy thành công

| Package | Phiên bản | Ghi chú |
|---|---:|---|
| Python | 3.11.16 | Từ `python:3.11-slim` |
| paddlepaddle | 3.3.0 | Wheel CPU `cp311`, nguồn chính thức PaddlePaddle |
| paddleocr | 3.7.0 | Có API PP-OCRv6 |
| paddlex | 3.7.2 | Dependency được PaddleOCR giải quyết |
| numpy | 2.3.5 | PaddleX yêu cầu `<2.4,>=1.24` |
| opencv-contrib-python | 4.10.0.84 | Được extra `paddlex[ocr-core]` ghim cứng |
| PyYAML | 6.0.2 | Được PaddleX 3.7.2 ghim cứng |
| kubernetes | 35.0.0 | Cần ghim để tương thích PyYAML 6.0.2 |

Trong image ghép với backend, các package chính sau cùng import thành công cùng PaddleOCR:

- FastAPI 0.141.1;
- LangChain 1.3.18, `langchain-core` 1.6.1, `langchain-community` 0.4.2;
- ChromaDB 1.5.9;
- Sentence Transformers 6.0.1;
- PyMuPDF 1.28.2;
- Torch 2.13.0+cu130;
- Pydantic 2.13.5.

`python -m pip check` trả về `No broken requirements found.` trong cả image độc lập và image ghép với backend.

### 3.2. Các tổ hợp hoặc cấu hình không đạt

| Thử nghiệm | Kết quả thực tế | Cách xử lý |
|---|---|---|
| `python:3.11-slim` không cài system package | Import dừng với `ImportError: libgomp.so.1: cannot open shared object file` | Bổ sung `libgomp1` |
| Chỉ bổ sung `libgomp1` | Import OpenCV dừng với `ImportError: libGL.so.1: cannot open shared object file`; `ldd` còn báo thiếu `libgthread-2.0.so.0` và `libglib-2.0.so.0` | Bổ sung `libgl1` và `libglib2.0-0` |
| PP-OCRv6 Small với MKLDNN mặc định | Lần `predict()` đầu thất bại tại oneDNN với `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]` | Khởi tạo với `enable_mkldnn=False` |
| Thay OpenCV bằng `opencv-contrib-python-headless==4.10.0.84` | `cv2` và `PaddleOCR` import được, `pip check` sạch; khi khởi tạo OCR, PaddleX báo thiếu dependency của `ocr-core` | Chưa dùng headless với bộ phiên bản này; giữ `opencv-contrib-python==4.10.0.84` |
| Chồng PaddleOCR trực tiếp lên backend có `kubernetes==36.0.3` | `pip check` báo Kubernetes cần `PyYAML>=6.0.3`, trong khi PaddleX yêu cầu `PyYAML==6.0.2` | Ghim `kubernetes==35.0.0`, phiên bản này chấp nhận `PyYAML>=5.4.1` |
| Cài toàn bộ requirements mở hiện tại cùng OCR trong một lần resolve | Resolver chọn Torch 2.14.0 và bắt đầu tải nhiều wheel CUDA 13; thử nghiệm được chủ động dừng vì không phù hợp mục tiêu CPU và quá tốn dung lượng | Dùng constraints/pin rõ ràng, không resolve lại toàn bộ dependency mở trong image spike |
| Dùng biến `PADDLEX_HOME` để đổi cache | Model vẫn được ghi vào `/root/.paddlex/official_models` | Dùng đúng biến `PADDLE_PDX_CACHE_HOME` |

Trong một số lần build, kho wheel PaddlePaddle/CDN bị timeout hoặc trả danh sách phiên bản rỗng tạm thời. Chạy lại cùng lệnh đã tải đúng wheel `paddlepaddle-3.3.0-cp311-cp311-linux_x86_64.whl`; đây là lỗi mạng/kho tải, không phải lỗi tương thích Python.

## 4. System packages cần thiết trên `python:3.11-slim`

Các package runtime đã được chứng minh cần cho cấu hình thành công:

```text
libgomp1
libgl1
libglib2.0-0
```

- `libgomp1` cung cấp OpenMP runtime cho Paddle/OpenCV.
- `libgl1` đáp ứng liên kết `libGL.so.1` của wheel OpenCV GUI.
- `libglib2.0-0` cung cấp các thư viện GLib/GThread mà `cv2` cần lúc import.
- `fonts-dejavu-core` chỉ được cài trong image spike để tạo ảnh fixture; không cần đưa vào backend production nếu backend không sinh ảnh kiểm thử.
- Không cần Tesseract, Poppler hoặc compiler riêng để chạy các wheel đã chọn. Cảnh báo thiếu `ccache` chỉ liên quan việc biên dịch extension, không cản trở inference.

## 5. Câu lệnh build và run

Chạy từ thư mục gốc repository:

```powershell
docker build -f experiments/ppocrv6_cpu/Dockerfile -t edurag-ppocrv6-cpu-spike .
docker volume create edurag_ppocrv6_spike_cache
docker run --rm --mount source=edurag_ppocrv6_spike_cache,target=/opt/ppocr-cache edurag-ppocrv6-cpu-spike
```

Xác minh container mới tái sử dụng cache khi không có mạng:

```powershell
docker run --rm --network none --mount source=edurag_ppocrv6_spike_cache,target=/opt/ppocr-cache edurag-ppocrv6-cpu-spike
```

Xác minh với dependency backend hiện tại:

```powershell
docker build -f experiments/ppocrv6_cpu/Dockerfile.backend-compat -t edurag-ppocrv6-backend-compat .
docker run --rm --network none --mount source=edurag_ppocrv6_spike_cache,target=/opt/ppocr-cache edurag-ppocrv6-backend-compat
docker run --rm --entrypoint python edurag-ppocrv6-backend-compat -m pip check
```

Các lệnh trên chỉ dùng image/volume thử nghiệm, không khởi động service production.

## 6. Cấu hình PP-OCRv6 Small đã dùng

```python
ocr = PaddleOCR(
    lang="vi",
    ocr_version="PP-OCRv6",
    text_detection_model_name="PP-OCRv6_small_det",
    text_recognition_model_name="PP-OCRv6_small_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    enable_mkldnn=False,
    device="cpu",
)
```

Một instance `PaddleOCR` được tạo và gọi `predict()` hai lần liên tiếp. Không khởi tạo lại model giữa hai lần gọi.

PaddleOCR phát cảnh báo rằng `lang` và `ocr_version` bị bỏ qua khi chỉ định model name cụ thể. Cấu hình vẫn truyền `lang="vi"` theo yêu cầu, nhưng việc khóa Small thực tế do hai model name; recognition model PP-OCRv6 Small xử lý được ảnh tiếng Việt thử nghiệm. Không nên diễn giải `lang` là cơ chế chọn một model tiếng Việt riêng trong cấu hình này.

## 7. Kết quả smoke test

### 7.1. Dữ liệu đầu vào

Fixture được sinh tạm thời với nội dung:

```text
QUY CHẾ ĐÀO TẠO
Điều 12. Sinh viên đăng ký học phần.
Ngày 13 tháng 09 năm 2026
Học phí: 1.250.000 đồng
```

File ảnh chỉ tồn tại trong container và không được đưa vào dữ liệu dự án.

### 7.2. Kết quả chức năng

Smoke test trả trạng thái `PASS`:

- 4 đoạn text;
- 4 confidence score;
- 4 polygon;
- 4 bounding box;
- confidence nhỏ nhất 0,947361;
- confidence trung bình 0,978334.

Text nhận dạng:

```text
QUY CH DÀO TAO
Điu 12. Sinh viên đăng ký hc phn.
Ngày 13 tháng 09 năm 2026
Hc phí: 1.250.000 đồng
```

Kết quả chứng minh pipeline trả đủ cấu trúc dữ liệu cần thiết, nhưng đồng thời cho thấy Small còn bỏ sót một số dấu tiếng Việt trên fixture. Đây không phải đánh giá CER/WER và chưa đủ căn cứ chọn cấu hình cuối.

## 8. Thời gian, RAM và model cache

Các số liệu dưới đây là một lần đo spike, không phải SLA:

| Kịch bản | Khởi tạo | OCR lần 1 | OCR lần 2 | RSS trước | RSS sau init | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| Image độc lập, cache trống | 10,015 s | 1,208 s | 1,170 s | 171,33 MB | 493,48 MB | 844,71 MB |
| Container mới, cache sẵn, `--network none` | 1,270 s | 1,212 s | 1,067 s | 172,18 MB | 463,37 MB | 812,71 MB |
| Image ghép backend, cache sẵn, `--network none` | 1,309 s | 1,147 s | 1,051 s | 906,25 MB | 1.195,04 MB | 1.541,89 MB |

RSS được lấy bằng `resource.getrusage()` trong tiến trình Python. Giá trị của image ghép backend cao hơn do môi trường dependency backend hiện tại; chưa thực hiện profiling để quy toàn bộ chênh lệch cho riêng package nào.

Cache model sau lần tải đầu là 31.534.062 byte, gồm:

- `PP-OCRv6_small_det`: 10.074.348 byte;
- `PP-OCRv6_small_rec`: 21.459.714 byte.

Đường dẫn trong container:

```text
/opt/ppocr-cache/official_models/PP-OCRv6_small_det
/opt/ppocr-cache/official_models/PP-OCRv6_small_rec
```

Đường dẫn mặc định nếu không cấu hình là `/root/.paddlex/official_models`. Biến môi trường hoạt động là:

```text
PADDLE_PDX_CACHE_HOME=/opt/ppocr-cache
```

Named volume dùng trong spike là `edurag_ppocrv6_spike_cache`; Docker engine báo mountpoint `/var/lib/docker/volumes/edurag_ppocrv6_spike_cache/_data`. Container thứ hai chạy với `--network none`, cache trước và sau đều bằng 31.534.062 byte, log xác nhận `Model files already exist. Using cached files.` Như vậy container restart/recreate có thể tái sử dụng model nếu mount cùng volume.

## 9. Xung đột dependency và tác động đến backend

### 9.1. Xung đột đã phát hiện

1. **PyYAML/Kubernetes:** PaddleX 3.7.2 ghim `PyYAML==6.0.2`, trong khi Kubernetes 36.0.3 yêu cầu `PyYAML>=6.0.3`. Ghim Kubernetes 35.0.0 giải quyết được xung đột và vẫn thỏa điều kiện `kubernetes>=28.1.0` của ChromaDB 1.5.9.
2. **NumPy:** PaddleX hạ NumPy từ 2.4.6 của backend hiện tại xuống 2.3.5. `pip check` và import Torch/LangChain/ChromaDB/Sentence Transformers/OpenCV/Paddle đều thành công. Chưa chạy full regression cho truy hồi RAG.
3. **OpenCV headless:** thay wheel GUI bằng headless làm dependency checker của PaddleX từ chối khởi tạo pipeline, dù import thành công. Không dùng headless trong lần triển khai đầu.
4. **MKLDNN/oneDNN:** cấu hình mặc định gây lỗi runtime với PaddlePaddle 3.3.0 và model Small; cần `enable_mkldnn=False`.
5. **Torch:** backend hiện có `torch 2.13.0+cu130`, `torch.version.cuda == 13.0`, nhưng `torch.cuda.is_available() == False`. Paddle CPU vẫn import và chạy cùng Torch. Đây không phải xung đột chức năng của spike, nhưng wheel CUDA làm image CPU lớn và cần xử lý trong một đợt khóa dependency riêng.

### 9.2. Không phát hiện xung đột nghiêm trọng trong phạm vi spike

- PaddleOCR import được cùng Torch, LangChain, ChromaDB và Sentence Transformers.
- `pip check` sạch sau khi ghim Kubernetes 35.0.0.
- Hai lần inference trên cùng instance thành công.
- Một container mới không có mạng vẫn khởi tạo và infer từ model cache.

Kết quả này chỉ là dependency/import smoke. Nó không thay thế kiểm thử endpoint backend, embedding, retrieval hoặc toàn bộ test suite.

## 10. Đề xuất chính xác cho giai đoạn triển khai

### 10.1. Requirements/constraints

Ở giai đoạn tích hợp, thêm constraints có phiên bản cố định thay vì để resolver chọn lại toàn bộ dải `>=`:

```text
paddleocr==3.7.0
paddlex[ocr-core]==3.7.2
opencv-contrib-python==4.10.0.84
numpy==2.3.5
PyYAML==6.0.2
kubernetes==35.0.0
```

Cài PaddlePaddle CPU riêng từ index chính thức:

```text
paddlepaddle==3.3.0
```

Không thêm đồng thời `opencv-python-headless` hoặc `opencv-contrib-python-headless`. Không nâng Kubernetes lên 36.x khi vẫn dùng PaddleX 3.7.2. Sau khi sửa requirements, phải tạo lock/constraints tái lập được và chạy lại test backend.

Không đổi Torch trong cùng commit tích hợp OCR để tránh mở rộng phạm vi. Tạo việc riêng để thay `torch>=2.3` bằng wheel CPU được ghim và kiểm chứng; spike này chỉ xác nhận wheel CUDA hiện tại không chặn Paddle CPU.

### 10.2. Dockerfile production

Thay đổi tối thiểu được đề xuất cho giai đoạn sau:

```dockerfile
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=1 \
    PADDLE_PDX_CACHE_HOME=/opt/ppocr-cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential curl libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
      --index-url https://www.paddlepaddle.org.cn/packages/stable/cpu/ \
      paddlepaddle==3.3.0 \
    && python -m pip install --no-cache-dir -r backend/requirements.txt \
    && python -m pip check
```

Đây là đề xuất, chưa áp dụng. Khi triển khai cần mount một named volume riêng vào `/opt/ppocr-cache`; không mount chung với ChromaDB, Hugging Face cache hoặc dữ liệu tài liệu. Model nên được tải trước khi đưa service vào môi trường cần chạy offline, hoặc có bước warm-up được kiểm soát. Không bake tài liệu hay OCR-result cache vào image.

Khởi tạo runtime phải giữ `device="cpu"`, `enable_mkldnn=False`, hai model name Small rõ ràng và tái sử dụng một instance thay vì tạo model cho mỗi trang/request.

## 11. Nội dung chưa thể xác minh

- Chưa có PDF scan fixture công khai/an toàn trong repository; chưa benchmark tài liệu thật.
- Chưa đo CER/WER, chưa dùng ground truth 30–50 trang và chưa so sánh Small với Medium.
- Chưa kiểm thử PDF scan khoảng 20 trang nên chưa đánh giá mục tiêu 120 giây, p50, p95 hoặc thời gian mỗi trang.
- Chưa kiểm thử trang trắng, trang có hình nhưng OCR thất bại, trang xoay, bảng và nhiều cột.
- Chưa đo confidence calibration hoặc ngưỡng quyết định giữ native text.
- Chưa chạy full backend/RAG regression sau khi NumPy và Kubernetes bị hạ phiên bản.
- Chưa kiểm tra image trên Linux host không dùng WSL2 hoặc kiến trúc khác `x86_64`.
- Chưa kiểm tra tính ổn định của nguồn tải model/wheel trong CI; đã quan sát timeout mạng tạm thời.
- Chưa triển khai hoặc xác minh cache kết quả OCR theo SHA-256; spike này chỉ kiểm chứng model cache PaddleX.
- Chưa đánh giá giải pháp headless khác hoặc patch dependency metadata; không đề xuất workaround chưa được upstream hỗ trợ.
- Chưa tích hợp OCR, chưa sửa rollback vector mồ côi và chưa thay đổi nghiệp vụ upload/rebuild.

## 12. Đánh giá điều kiện chuyển giai đoạn

| Điều kiện | Trạng thái | Bằng chứng |
|---|---|---|
| Container CPU build thành công | **Đạt** | Image độc lập và image ghép backend đều build thành công |
| Import `PaddleOCR` thành công | **Đạt** | Import độc lập và cùng dependency backend đều thành công |
| PP-OCRv6 Small chạy trên ảnh tiếng Việt với cấu hình CPU | **Đạt** | Model det/rec Small trả text, confidence, polygon và box |
| Cache model hoạt động qua container mới/restart | **Đạt** | Chạy `--network none`, cache không đổi và model được đọc từ volume |
| Không có xung đột nghiêm trọng với backend hiện tại | **Đạt có điều kiện** | Import và `pip check` sạch sau khi ghim Kubernetes 35.0.0; cần regression test khi tích hợp |

Spike đáp ứng cổng kỹ thuật để bắt đầu giai đoạn sửa mã nguồn chính bằng bộ phiên bản và cấu hình đã nêu. Điều kiện đi kèm là phải áp dụng constraints PyYAML/Kubernetes/NumPy, dùng OpenCV GUI cùng ba system package, tắt MKLDNN cho cấu hình đã thử và mount cache model riêng. Việc bắt đầu tích hợp không đồng nghĩa PP-OCRv6 Small đã đạt chất lượng cuối; lựa chọn Small/Medium vẫn phải dựa trên benchmark corpus thật ở giai đoạn kế tiếp.

## 13. File thử nghiệm tạo ra

```text
experiments/ppocrv6_cpu/
├── Dockerfile
├── Dockerfile.backend-compat
├── Dockerfile.headless-probe
├── Dockerfile.headless-smoke
├── Dockerfile.minimal
├── README.md
├── requirements-spike.txt
└── smoke_test.py

docs/spike_ppocrv6_cpu.md
```

Các Docker image và named volume chỉ là artifact cục bộ phục vụ tái hiện spike, không phải cấu hình production.
