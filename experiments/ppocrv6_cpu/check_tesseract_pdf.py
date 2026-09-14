"""Read-only page OCR with Vietnamese Tesseract; images stay in memory."""
import argparse
import subprocess
import time
import pymupdf as fitz

parser = argparse.ArgumentParser()
parser.add_argument("pdf")
parser.add_argument("--page", type=int, default=3)
parser.add_argument("--dpi", type=int, default=200)
parser.add_argument("--lang", default="vie")
args = parser.parse_args()
with fitz.open(args.pdf) as pdf:
    png = pdf[args.page - 1].get_pixmap(dpi=args.dpi).tobytes("png")
started = time.perf_counter()
result = subprocess.run(
    ["tesseract", "stdin", "stdout", "-l", args.lang, "--psm", "3"],
    input=png, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
)
print(result.stdout.decode("utf-8"))
print("SECONDS", round(time.perf_counter() - started, 2))
