import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "evaluation"))

from resources import (  # noqa: E402
    ResourceMonitor,
    parse_nvidia_smi,
    parse_ollama_ps,
    summarize_samples,
)

GIB = 1024 ** 3


class ParseNvidiaSmiTests(unittest.TestCase):
    def test_parses_first_gpu_name_total_and_used(self):
        output = "NVIDIA GeForce RTX 5060 Laptop GPU, 8151, 7556\n"
        self.assertEqual(
            parse_nvidia_smi(output),
            {"gpu_name": "NVIDIA GeForce RTX 5060 Laptop GPU", "gpu_mem_total_mb": 8151, "gpu_mem_used_mb": 7556},
        )

    def test_returns_none_for_empty_or_garbage_output(self):
        self.assertIsNone(parse_nvidia_smi(""))
        self.assertIsNone(parse_nvidia_smi("NVIDIA-SMI has failed"))


class ParseOllamaPsTests(unittest.TestCase):
    PAYLOAD = {"models": [{
        "name": "qwen3.5:9b", "size": 5 * GIB, "size_vram": 4 * GIB, "context_length": 6144,
        "details": {"parameter_size": "9.7B", "quantization_level": "Q4_K_M"},
    }]}

    def test_reports_size_vram_and_gpu_share_for_the_model(self):
        info = parse_ollama_ps(self.PAYLOAD, "qwen3.5:9b")
        self.assertEqual(info["size_mb"], 5120)
        self.assertEqual(info["vram_mb"], 4096)
        self.assertEqual(info["gpu_share"], 0.8)
        self.assertEqual(info["parameter_size"], "9.7B")
        self.assertEqual(info["quantization"], "Q4_K_M")
        self.assertEqual(info["context_length"], 6144)

    def test_returns_none_when_model_not_loaded(self):
        self.assertIsNone(parse_ollama_ps(self.PAYLOAD, "gemma4:12b"))
        self.assertIsNone(parse_ollama_ps({}, "qwen3.5:9b"))


class SummarizeSamplesTests(unittest.TestCase):
    def test_peaks_and_means(self):
        samples = [
            {"rss_mb": 900.0, "cpu_percent": 10.0, "gpu_mem_used_mb": 7000},
            {"rss_mb": 1500.0, "cpu_percent": 50.0, "gpu_mem_used_mb": 7600},
            {"rss_mb": 1200.0, "cpu_percent": 30.0, "gpu_mem_used_mb": None},
        ]
        summary = summarize_samples(samples)
        self.assertEqual(summary["samples"], 3)
        self.assertEqual(summary["peak_rss_mb"], 1500.0)
        self.assertEqual(summary["mean_cpu_percent"], 30.0)
        self.assertEqual(summary["peak_cpu_percent"], 50.0)
        self.assertEqual(summary["peak_gpu_mem_used_mb"], 7600)

    def test_no_gpu_samples_gives_none(self):
        summary = summarize_samples([{"rss_mb": 10.0, "cpu_percent": 1.0, "gpu_mem_used_mb": None}])
        self.assertIsNone(summary["peak_gpu_mem_used_mb"])

    def test_empty_samples(self):
        self.assertEqual(summarize_samples([])["samples"], 0)


class ResourceMonitorTests(unittest.TestCase):
    def test_collects_samples_in_background_until_stopped(self):
        calls = []

        def fake_sample():
            calls.append(1)
            return {"rss_mb": float(len(calls)), "cpu_percent": 5.0, "gpu_mem_used_mb": None}

        with ResourceMonitor(interval=0.01, sample_fn=fake_sample) as monitor:
            time.sleep(0.15)
        count = len(calls)
        time.sleep(0.05)
        self.assertGreaterEqual(count, 3)
        self.assertEqual(len(calls), count, "monitor phải dừng lấy mẫu sau khi thoát")
        self.assertEqual(monitor.summary()["peak_rss_mb"], float(count))

    def test_sampler_errors_do_not_stop_monitoring(self):
        state = {"n": 0}

        def flaky_sample():
            state["n"] += 1
            if state["n"] % 2:
                raise RuntimeError("nvidia-smi timeout")
            return {"rss_mb": 1.0, "cpu_percent": 1.0, "gpu_mem_used_mb": None}

        with ResourceMonitor(interval=0.01, sample_fn=flaky_sample) as monitor:
            time.sleep(0.1)
        self.assertGreaterEqual(monitor.summary()["samples"], 2)


if __name__ == "__main__":
    unittest.main()
