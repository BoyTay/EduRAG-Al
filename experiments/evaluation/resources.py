"""Đo tài nguyên khi chạy bộ đánh giá (mục 6 của đề tài: tài nguyên sử dụng).

- Tiến trình đánh giá chạy cùng pipeline với backend (embedding, reranker, Chroma),
  nên RAM/CPU của nó đại diện cho phần backend.
- LLM chạy trong Ollama (tiến trình riêng): đọc dung lượng model và phần nằm trên
  VRAM qua `/api/ps`, cộng VRAM toàn GPU qua `nvidia-smi`.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import urllib.request
from statistics import fmean
from typing import Any, Callable, Optional

MB = 1024 * 1024
NVIDIA_QUERY = ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"]


def parse_nvidia_smi(output: str) -> Optional[dict[str, Any]]:
    """Dòng đầu của `nvidia-smi --query-gpu=name,memory.total,memory.used` (MiB)."""
    for line in (output or "").splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            return {"gpu_name": parts[0], "gpu_mem_total_mb": int(parts[1]), "gpu_mem_used_mb": int(parts[2])}
    return None


def read_gpu() -> Optional[dict[str, Any]]:
    try:
        result = subprocess.run(NVIDIA_QUERY, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_nvidia_smi(result.stdout) if result.returncode == 0 else None


def parse_ollama_ps(payload: dict[str, Any], model: str) -> Optional[dict[str, Any]]:
    """Thông tin model đang nạp trong Ollama; None nếu model chưa nạp."""
    for item in payload.get("models") or []:
        if item.get("name") != model and item.get("model") != model:
            continue
        size = int(item.get("size") or 0)
        vram = int(item.get("size_vram") or 0)
        details = item.get("details") or {}
        return {
            "model": model,
            "size_mb": round(size / MB),
            "vram_mb": round(vram / MB),
            "gpu_share": round(vram / size, 3) if size else 0.0,
            "parameter_size": details.get("parameter_size"),
            "quantization": details.get("quantization_level"),
            "context_length": item.get("context_length"),
        }
    return None


def read_ollama_model(base_url: str, model: str) -> Optional[dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/ps", timeout=5) as response:
            return parse_ollama_ps(json.loads(response.read()), model)
    except (OSError, ValueError):
        return None


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    gpu = [sample["gpu_mem_used_mb"] for sample in samples if sample.get("gpu_mem_used_mb") is not None]
    cpu = [sample["cpu_percent"] for sample in samples]
    return {
        "samples": len(samples),
        "peak_rss_mb": max((sample["rss_mb"] for sample in samples), default=0.0),
        "mean_cpu_percent": round(fmean(cpu), 1) if cpu else 0.0,
        "peak_cpu_percent": max(cpu, default=0.0),
        "peak_gpu_mem_used_mb": max(gpu) if gpu else None,
    }


def process_sampler(pid: Optional[int] = None, with_gpu: bool = True) -> Callable[[], dict[str, Any]]:
    """Hàm lấy một mẫu RAM/CPU của tiến trình (mặc định: tiến trình hiện tại) và VRAM."""
    import psutil

    process = psutil.Process(pid or os.getpid())
    process.cpu_percent(None)  # lần đầu luôn trả 0; gọi mồi để mẫu sau có ý nghĩa

    def sample() -> dict[str, Any]:
        gpu = read_gpu() if with_gpu else None
        return {
            "rss_mb": round(process.memory_info().rss / MB, 1),
            # Chia cho số lõi để 100% = dùng hết CPU của máy.
            "cpu_percent": round(process.cpu_percent(None) / (psutil.cpu_count() or 1), 1),
            "gpu_mem_used_mb": gpu["gpu_mem_used_mb"] if gpu else None,
        }

    return sample


class ResourceMonitor:
    """Lấy mẫu tài nguyên ở luồng nền trong suốt khối `with`."""

    def __init__(self, interval: float = 0.5, sample_fn: Optional[Callable[[], dict[str, Any]]] = None):
        self.interval = interval
        self._sample_fn = sample_fn
        self.samples: list[dict[str, Any]] = []
        self.errors = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.samples.append(self._sample_fn())
            except Exception:  # noqa: BLE001 - một mẫu lỗi (vd. nvidia-smi treo) không được dừng việc đo
                self.errors += 1
            self._stop.wait(self.interval)

    def __enter__(self) -> "ResourceMonitor":
        if self._sample_fn is None:
            self._sample_fn = process_sampler()
        self._thread = threading.Thread(target=self._run, name="resource-monitor", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def summary(self) -> dict[str, Any]:
        return {**summarize_samples(self.samples), "sample_errors": self.errors}


def system_info() -> dict[str, Any]:
    import psutil

    gpu = read_gpu()
    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor() or platform.machine(),
        "cpu_logical_cores": psutil.cpu_count(),
        "ram_total_mb": round(psutil.virtual_memory().total / MB),
        "gpu_name": gpu["gpu_name"] if gpu else None,
        "gpu_mem_total_mb": gpu["gpu_mem_total_mb"] if gpu else None,
    }
