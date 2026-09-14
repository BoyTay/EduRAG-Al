"""Inspect model alphabet without modifying downloaded model files."""
from pathlib import Path
import unicodedata
import yaml

for tier in ("small", "medium"):
    path = Path(f"/opt/ppocr-cache/official_models/PP-OCRv6_{tier}_rec/inference.yml")
    chars = yaml.safe_load(path.read_text())["PostProcess"]["character_dict"]
    print(tier, "size", len(chars))
    for char in "ệữẳẵưỡờộấế":
        print(char, "NFC", char in chars, "NFD", unicodedata.normalize("NFD", char) in chars)
    print("combining", [ascii(x) for x in chars if any(unicodedata.combining(c) for c in str(x))][:30])
