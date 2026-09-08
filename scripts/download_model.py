"""Download RU streaming sherpa-onnx model (Vosk-small family)."""
from pathlib import Path
import urllib.request
import sys

BASE = (
    "https://huggingface.co/csukuangfj/"
    "sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16/resolve/main"
)
FILES = [
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "joiner.int8.onnx",
    "tokens.txt",
]
# HF main branch publishes decoder.onnx (not decoder.int8.onnx).
REMOTE = {"decoder.int8.onnx": "decoder.onnx"}
OUT = Path("models/sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = OUT / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"skip {name}")
            continue
        remote = REMOTE.get(name, name)
        url = f"{BASE}/{remote}"
        print(f"download {url}")
        urllib.request.urlretrieve(url, dest)
        print(f"saved {dest} ({dest.stat().st_size} bytes)")
    missing = [n for n in FILES if not (OUT / n).exists()]
    if missing:
        print("MISSING:", missing, file=sys.stderr)
        return 1
    print("OK", OUT.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
