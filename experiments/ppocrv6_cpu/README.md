# PP-OCRv6 CPU dependency spike

Thư mục này chỉ phục vụ thử nghiệm dependency PP-OCRv6 Small trên CPU. Image
không được dùng làm backend production và không kết nối database, ChromaDB hay
thư mục `data/`.

Build từ repository root:

```powershell
docker build -f experiments/ppocrv6_cpu/Dockerfile -t edurag-ppocrv6-cpu-spike .
```

Kiểm tra tương thích với image backend hiện tại (không chạy backend):

```powershell
docker build -f experiments/ppocrv6_cpu/Dockerfile.backend-compat -t edurag-ppocrv6-backend-compat .
```

Probe headless chỉ dùng để kiểm tra import. Với PaddleOCR 3.7.0/PaddleX 3.7.2,
import thành công nhưng pipeline OCR từ chối khởi tạo vì dependency checker yêu
cầu đúng distribution `opencv-contrib-python`. `Dockerfile.headless-smoke` được
giữ lại để tái hiện kết quả thất bại này, không phải cấu hình đề xuất:

```powershell
docker build -f experiments/ppocrv6_cpu/Dockerfile.headless-probe -t edurag-ppocrv6-headless-probe .
docker build -f experiments/ppocrv6_cpu/Dockerfile.headless-smoke -t edurag-ppocrv6-headless-smoke .
docker run --rm edurag-ppocrv6-headless-smoke
```

Lần chạy đầu, lưu model vào cache tách biệt:

```powershell
docker volume create edurag_ppocrv6_spike_cache
docker run --rm --mount source=edurag_ppocrv6_spike_cache,target=/opt/ppocr-cache edurag-ppocrv6-cpu-spike
```

Chạy lại với cùng volume và tắt mạng để xác minh cache được tái sử dụng:

```powershell
docker run --rm --network none --mount source=edurag_ppocrv6_spike_cache,target=/opt/ppocr-cache edurag-ppocrv6-cpu-spike
```

Chạy smoke trên image tương thích với dependency backend hiện tại:

```powershell
docker run --rm --network none --mount source=edurag_ppocrv6_spike_cache,target=/opt/ppocr-cache edurag-ppocrv6-backend-compat
```

Không commit model cache hoặc output runtime.
