# Meeting Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows Python service that captures mic + WASAPI loopback, transcribes Russian speech locally (finals only), writes `live-transcript.md`, and exposes MCP tools so Cursor can start/stop sessions and read the transcript.

**Architecture:** One long-lived process hosts the MCP stdio server. `session_start` launches two capture threads (mic + loopback) feeding two sherpa-onnx online streams; finals are appended to `live-transcript.md` by a single writer. CLI `python -m meeting_bridge` shares the same session manager for offline testing without Cursor.

**Tech Stack:** Python 3.11–3.12 (prefer 3.12 venv if 3.13 lacks wheels), `PyAudioWPatch`, `sherpa-onnx`, `PyYAML`, `mcp` (FastMCP), `pytest`.

**Spec:** `docs/superpowers/specs/2026-08-12-meeting-bridge-design.md`

## Global Constraints

- Windows 10/11 only for v1
- Labels exactly: `Я:` and `Собеседник:`
- Write **final** STT utterances only (no partials in the file)
- Default transcript path: `live-transcript.md` at project root
- No raw audio saved to disk by default
- No overlay UI, no in-app LLM
- Capture library: **`PyAudioWPatch`** (WASAPI loopback). Spec mentioned `sounddevice`; that API does not expose loopback — this is an intentional correction
- STT model: Hugging Face `csukuangfj/sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16` (same RU Vosk streaming family as Secstant)
- Sample rate for STT: 16000 Hz mono float32
- Warn on start if mic and loopback resolve to the same device name/index
- MCP server name: `meeting-bridge`
- Commits only when the user explicitly asks during execution (skip plan “Commit” steps unless user says to commit)

## File map

| Path | Responsibility |
|------|----------------|
| `meeting_bridge/__init__.py` | Package version |
| `meeting_bridge/__main__.py` | CLI entry (`start` / `stop` / `devices` / `mcp`) |
| `meeting_bridge/config.py` | Load/validate `config.yaml` |
| `meeting_bridge/devices.py` | List mic + loopback devices; resolve by name substring |
| `meeting_bridge/writer.py` | Frontmatter + append lines + rotate at 2000 lines |
| `meeting_bridge/stt.py` | sherpa-onnx OnlineRecognizer wrapper; emit finals |
| `meeting_bridge/capture.py` | Dual-channel PyAudioWPatch capture → STT → writer |
| `meeting_bridge/session.py` | Thread-safe SessionManager start/stop/status |
| `meeting_bridge/mcp_server.py` | FastMCP tools |
| `config.yaml` | Default device names + paths |
| `scripts/download_model.py` | Download RU streaming model into `models/` |
| `requirements.txt` | Pinned deps |
| `README.md` | Install, model, Cursor `mcp.json` |
| `tests/test_config.py` | Config load/validate |
| `tests/test_writer.py` | Transcript writer + rotation |
| `tests/test_stt_finals.py` | Final-only filtering with fake recognizer |
| `tests/test_session.py` | Session lifecycle with mocked capture |
| `tests/test_devices.py` | Device list/resolve helpers (mocked) |
| `.gitignore` | `models/`, `venv/`, `live-transcript.md`, `__pycache__/` |

---

### Task 1: Scaffold + config

**Files:**
- Create: `meeting_bridge/__init__.py`
- Create: `meeting_bridge/config.py`
- Create: `config.yaml`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `AppConfig` dataclass; `load_config(path: Path | None = None) -> AppConfig`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
from pathlib import Path
import textwrap
import pytest
from meeting_bridge.config import load_config, AppConfig

def test_load_config_reads_yaml(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent("""\
        mic_device: "Mic A"
        speaker_device: "Speakers B"
        transcript_path: "live-transcript.md"
        model_dir: "models/sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16"
        sample_rate: 16000
        max_transcript_lines: 2000
    """), encoding="utf-8")
    cfg = load_config(p)
    assert isinstance(cfg, AppConfig)
    assert cfg.mic_device == "Mic A"
    assert cfg.speaker_device == "Speakers B"
    assert cfg.transcript_path == Path("live-transcript.md")
    assert cfg.sample_rate == 16000
    assert cfg.max_transcript_lines == 2000

def test_load_config_requires_devices(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text("transcript_path: x.md\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mic_device"):
        load_config(p)
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `pytest tests/test_config.py -v`  
Expected: FAIL (`ModuleNotFoundError` or import error)

- [ ] **Step 3: Implement scaffold + config**

```python
# meeting_bridge/__init__.py
__version__ = "0.1.0"
```

```python
# meeting_bridge/config.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

DEFAULT_MODEL_DIR = (
    "models/sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16"
)

@dataclass(frozen=True)
class AppConfig:
    mic_device: str
    speaker_device: str
    transcript_path: Path
    model_dir: Path
    sample_rate: int = 16000
    max_transcript_lines: int = 2000
    archive_dir: Path = Path("transcripts")

def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or Path("config.yaml")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not raw.get("mic_device"):
        raise ValueError("mic_device is required in config.yaml")
    if not raw.get("speaker_device"):
        raise ValueError("speaker_device is required in config.yaml")
    return AppConfig(
        mic_device=str(raw["mic_device"]),
        speaker_device=str(raw["speaker_device"]),
        transcript_path=Path(raw.get("transcript_path", "live-transcript.md")),
        model_dir=Path(raw.get("model_dir", DEFAULT_MODEL_DIR)),
        sample_rate=int(raw.get("sample_rate", 16000)),
        max_transcript_lines=int(raw.get("max_transcript_lines", 2000)),
        archive_dir=Path(raw.get("archive_dir", "transcripts")),
    )
```

```yaml
# config.yaml
mic_device: ""          # fill after `python -m meeting_bridge devices`
speaker_device: ""      # loopback / headphones output name
transcript_path: live-transcript.md
model_dir: models/sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16
sample_rate: 16000
max_transcript_lines: 2000
archive_dir: transcripts
```

```text
# requirements.txt
PyAudioWPatch>=0.2.12.6
sherpa-onnx>=1.10.0
PyYAML>=6.0
mcp>=1.9.0
numpy>=1.26
pytest>=8.0
```

```gitignore
# .gitignore
venv/
.venv/
__pycache__/
*.pyc
.pytest_cache/
models/
live-transcript.md
transcripts/
*.log
```

Note: empty device strings will fail `load_config` until filled — for tests use tmp configs; for local run fill after Task 2.

Update `config.yaml` defaults after first `devices` listing so `load_config` works, OR allow empty only when not starting session. For scaffold, change validation to allow empty strings in file but `SessionManager.start` rejects empty — adjust test:

Replace `test_load_config_requires_devices` with:

```python
def test_load_config_allows_empty_devices_for_bootstrap(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text("mic_device: ''\nspeaker_device: ''\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.mic_device == ""
    assert cfg.speaker_device == ""
```

And in `load_config` do **not** raise on empty devices (validation moves to session start).

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_config.py -v`  
Expected: PASS

---

### Task 2: Transcript writer

**Files:**
- Create: `meeting_bridge/writer.py`
- Create: `tests/test_writer.py`

**Interfaces:**
- Consumes: `AppConfig` fields `transcript_path`, `archive_dir`, `max_transcript_lines`
- Produces:
  - `class TranscriptWriter`
  - `start_session(mic: str, speaker: str, session_iso: str) -> Path`
  - `append(role: str, text: str, when: datetime | None = None) -> None`
  - `set_status(status: str) -> None`
  - `tail(n: int) -> str`
  - `path -> Path`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_writer.py
from datetime import datetime
from pathlib import Path
from meeting_bridge.writer import TranscriptWriter

def test_start_session_writes_frontmatter(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    w = TranscriptWriter(path, archive_dir=tmp_path / "archives", max_lines=2000)
    w.start_session(mic="Mic", speaker="Spk", session_iso="2026-08-12T21:45:00")
    text = path.read_text(encoding="utf-8")
    assert "session: 2026-08-12T21:45:00" in text
    assert "status: listening" in text
    assert "mic: Mic" in text
    assert "speaker: Spk" in text

def test_append_role_lines(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    w = TranscriptWriter(path, archive_dir=tmp_path / "archives", max_lines=2000)
    w.start_session(mic="M", speaker="S", session_iso="2026-08-12T21:45:00")
    w.append("Я", "Привет", when=datetime(2026, 8, 12, 21, 46, 2))
    w.append("Собеседник", "Здравствуйте", when=datetime(2026, 8, 12, 21, 46, 5))
    body = path.read_text(encoding="utf-8")
    assert "[21:46:02] Я: Привет" in body
    assert "[21:46:05] Собеседник: Здравствуйте" in body

def test_rotate_when_over_max_lines(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    archives = tmp_path / "archives"
    w = TranscriptWriter(path, archive_dir=archives, max_lines=5)
    w.start_session(mic="M", speaker="S", session_iso="2026-08-12T21:45:00")
    for i in range(10):
        w.append("Я", f"line-{i}", when=datetime(2026, 8, 12, 21, 46, i % 60))
    assert archives.exists()
    assert any(archives.iterdir())
    assert path.exists()

def test_tail_returns_last_n_lines(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    w = TranscriptWriter(path, archive_dir=tmp_path / "a", max_lines=2000)
    w.start_session(mic="M", speaker="S", session_iso="2026-08-12T21:45:00")
    w.append("Я", "one", when=datetime(2026, 8, 12, 21, 46, 1))
    w.append("Я", "two", when=datetime(2026, 8, 12, 21, 46, 2))
    tail = w.tail(1)
    assert "two" in tail
    assert "one" not in tail
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_writer.py -v`  
Expected: FAIL import

- [ ] **Step 3: Implement writer**

```python
# meeting_bridge/writer.py
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import shutil
import threading

class TranscriptWriter:
    def __init__(self, path: Path, archive_dir: Path, max_lines: int = 2000) -> None:
        self.path = path
        self.archive_dir = archive_dir
        self.max_lines = max_lines
        self._lock = threading.Lock()
        self._line_count = 0
        self._mic = ""
        self._speaker = ""
        self._session_iso = ""

    def start_session(self, mic: str, speaker: str, session_iso: str) -> Path:
        with self._lock:
            self._mic = mic
            self._speaker = speaker
            self._session_iso = session_iso
            self._line_count = 0
            self.path.parent.mkdir(parents=True, exist_ok=True)
            content = (
                "---\n"
                f"session: {session_iso}\n"
                "status: listening\n"
                f"mic: {mic}\n"
                f"speaker: {speaker}\n"
                "---\n\n"
            )
            self.path.write_text(content, encoding="utf-8")
            return self.path

    def set_status(self, status: str) -> None:
        with self._lock:
            if not self.path.exists():
                return
            text = self.path.read_text(encoding="utf-8")
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("status:"):
                    lines[i] = f"status: {status}"
                    break
            self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def append(self, role: str, text: str, when: datetime | None = None) -> None:
        text = text.strip()
        if not text:
            return
        when = when or datetime.now()
        line = f"[{when.strftime('%H:%M:%S')}] {role}: {text}\n"
        with self._lock:
            if self._line_count >= self.max_lines:
                self._rotate_unlocked()
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
            self._line_count += 1

    def tail(self, n: int) -> str:
        with self._lock:
            if not self.path.exists():
                return ""
            lines = self.path.read_text(encoding="utf-8").splitlines()
            body = [ln for ln in lines if ln.startswith("[")]
            return "\n".join(body[-n:])

    def _rotate_unlocked(self) -> None:
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = self.archive_dir / f"transcript-{stamp}.md"
        if self.path.exists():
            shutil.move(str(self.path), str(dest))
        content = (
            "---\n"
            f"session: {self._session_iso}\n"
            "status: listening\n"
            f"mic: {self._mic}\n"
            f"speaker: {self._speaker}\n"
            "---\n\n"
        )
        self.path.write_text(content, encoding="utf-8")
        self._line_count = 0
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_writer.py -v`  
Expected: PASS

---

### Task 3: Device listing + resolve

**Files:**
- Create: `meeting_bridge/devices.py`
- Create: `tests/test_devices.py`

**Interfaces:**
- Produces:
  - `list_audio_devices() -> dict` with keys `mic` and `loopback` (lists of `{index, name, hostapi, is_loopback}`)
  - `resolve_device(name_substring: str, kind: Literal["mic","loopback"]) -> dict`
  - Raises `LookupError` if not found
  - `same_device_warning(mic: dict, loopback: dict) -> str | None`

Implementation note: wrap `pyaudiowpatch` (`import pyaudiowatch as pyaudio` — package import is `pyaudiowpatch`). Use `WasapiLoopbackInput` / device flags from PyAudioWPatch docs. Tests mock the PyAudio instance.

- [ ] **Step 1: Write failing tests with mocks**

```python
# tests/test_devices.py
from meeting_bridge.devices import resolve_from_maps, same_device_warning

def test_resolve_mic_by_substring():
    mic = [{"index": 1, "name": "Головной телефон HONOR", "is_loopback": False}]
    loop = [{"index": 2, "name": "Наушники HONOR [Loopback]", "is_loopback": True}]
    got = resolve_from_maps("Honor", "mic", mic, loop)
    assert got["index"] == 1

def test_resolve_loopback_by_substring():
    mic = [{"index": 1, "name": "Головной телефон HONOR", "is_loopback": False}]
    loop = [{"index": 2, "name": "Наушники HONOR [Loopback]", "is_loopback": True}]
    got = resolve_from_maps("Наушники", "loopback", mic, loop)
    assert got["is_loopback"] is True

def test_same_device_warning():
    a = {"index": 1, "name": "Same Device"}
    b = {"index": 1, "name": "Same Device"}
    assert same_device_warning(a, b) is not None
    c = {"index": 2, "name": "Other"}
    assert same_device_warning(a, c) is None
```

Keep pure helpers `resolve_from_maps` / `same_device_warning` for unit tests; `list_audio_devices()` calls PyAudioWPatch and maps into the same shape.

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_devices.py -v`

- [ ] **Step 3: Implement**

```python
# meeting_bridge/devices.py
from __future__ import annotations
from typing import Any, Literal

DeviceInfo = dict[str, Any]

def same_device_warning(mic: DeviceInfo, loopback: DeviceInfo) -> str | None:
    if mic.get("index") == loopback.get("index") or mic.get("name") == loopback.get("name"):
        return (
            "Микрофон и собеседник указывают на одно устройство. "
            "Для собеседника выберите loopback наушников/динамиков."
        )
    return None

def resolve_from_maps(
    name_substring: str,
    kind: Literal["mic", "loopback"],
    mic: list[DeviceInfo],
    loopback: list[DeviceInfo],
) -> DeviceInfo:
    pool = mic if kind == "mic" else loopback
    needle = name_substring.casefold()
    for d in pool:
        if needle in str(d.get("name", "")).casefold():
            return d
    raise LookupError(f"No {kind} device matching {name_substring!r}")

def list_audio_devices() -> dict[str, list[DeviceInfo]]:
    import pyaudiowpatch as pyaudio  # type: ignore

    mic: list[DeviceInfo] = []
    loopback: list[DeviceInfo] = []
    p = pyaudio.PyAudio()
    try:
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            name = str(info.get("name", ""))
            max_in = int(info.get("maxInputChannels", 0))
            is_loop = bool(info.get("isLoopbackDevice", False)) or ("loopback" in name.casefold())
            if max_in <= 0:
                continue
            entry = {
                "index": i,
                "name": name,
                "hostapi": info.get("hostApi"),
                "is_loopback": is_loop,
                "defaultSampleRate": info.get("defaultSampleRate"),
            }
            if is_loop:
                loopback.append(entry)
            else:
                mic.append(entry)
    finally:
        p.terminate()
    return {"mic": mic, "loopback": loopback}

def resolve_device(name_substring: str, kind: Literal["mic", "loopback"]) -> DeviceInfo:
    maps = list_audio_devices()
    return resolve_from_maps(name_substring, kind, maps["mic"], maps["loopback"])
```

Verify PyAudioWPatch loopback flag name against installed package (`isLoopbackDevice` is used in PyAudioWPatch examples). Adjust if the real key differs after install.

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_devices.py -v`

- [ ] **Step 5: Manual smoke (optional)**

Run: `python -c "from meeting_bridge.devices import list_audio_devices; import json; print(json.dumps(list_audio_devices(), ensure_ascii=False, indent=2))"`  
Expected: non-empty `mic` and ideally non-empty `loopback` lists.

---

### Task 4: STT finals wrapper

**Files:**
- Create: `meeting_bridge/stt.py`
- Create: `tests/test_stt_finals.py`

**Interfaces:**
- Produces:
  - `class FinalOnlyTranscriber`
  - `__init__(model_dir: Path, sample_rate: int = 16000)`
  - `create_stream() -> StreamHandle` (opaque)
  - `accept_audio(stream, samples: np.ndarray) -> list[str]`  
    Returns zero or more **final** utterance strings (empty if only partial)

Design: keep last non-empty `get_result` text; when `is_endpoint(stream)` becomes true, emit that text and `reset(stream)`.

- [ ] **Step 1: Write failing test with fake recognizer**

```python
# tests/test_stt_finals.py
import numpy as np
from meeting_bridge.stt import FinalOnlyTranscriber

class FakeStream:
    pass

class FakeRecognizer:
    def __init__(self):
        self._ready = True
        self._text = ""
        self._endpoint = False
        self.reset_calls = 0

    def create_stream(self):
        return FakeStream()

    def is_ready(self, stream):
        return self._ready

    def decode_stream(self, stream):
        return None

    def get_result(self, stream):
        return self._text

    def is_endpoint(self, stream):
        return self._endpoint

    def reset(self, stream):
        self.reset_calls += 1
        self._text = ""
        self._endpoint = False

    def accept_waveform(self, stream, sample_rate, samples):
        return None

def test_emits_only_on_endpoint():
    fake = FakeRecognizer()
    t = FinalOnlyTranscriber.__new__(FinalOnlyTranscriber)
    t.sample_rate = 16000
    t.recognizer = fake
    stream = fake.create_stream()

    fake._text = "Привет"
    fake._endpoint = False
    assert t.accept_audio(stream, np.zeros(1600, dtype=np.float32)) == []

    fake._endpoint = True
    finals = t.accept_audio(stream, np.zeros(1600, dtype=np.float32))
    assert finals == ["Привет"]
    assert fake.reset_calls == 1
```

Wire `accept_audio` to call `accept_waveform` → decode loop → if endpoint and text: return `[text]` and reset.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `stt.py`**

```python
# meeting_bridge/stt.py
from __future__ import annotations
from pathlib import Path
import numpy as np

class FinalOnlyTranscriber:
    def __init__(self, model_dir: Path, sample_rate: int = 16000) -> None:
        import sherpa_onnx

        self.sample_rate = sample_rate
        model_dir = Path(model_dir)
        encoder = model_dir / "encoder.int8.onnx"
        decoder = model_dir / "decoder.int8.onnx"
        joiner = model_dir / "joiner.int8.onnx"
        tokens = model_dir / "tokens.txt"
        for p in (encoder, decoder, joiner, tokens):
            if not p.exists():
                raise FileNotFoundError(f"Missing model file: {p}")

        self.recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(tokens),
            encoder=str(encoder),
            decoder=str(decoder),
            joiner=str(joiner),
            num_threads=2,
            sample_rate=sample_rate,
            feature_dim=80,
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=0.5,
            rule2_min_trailing_silence=0.3,
            rule3_min_utterance_length=1.0,
            provider="cpu",
        )

    def create_stream(self):
        return self.recognizer.create_stream()

    def accept_audio(self, stream, samples: np.ndarray) -> list[str]:
        if samples.dtype != np.float32:
            samples = samples.astype(np.float32)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        self.recognizer.accept_waveform(stream, self.sample_rate, samples)
        while self.recognizer.is_ready(stream):
            self.recognizer.decode_stream(stream)
        finals: list[str] = []
        if self.recognizer.is_endpoint(stream):
            text = (self.recognizer.get_result(stream) or "").strip()
            self.recognizer.reset(stream)
            if text:
                finals.append(text)
        return finals
```

If `from_transducer` / `accept_waveform` signatures differ in installed `sherpa-onnx`, adjust to match package (check with `python -c "import sherpa_onnx,inspect; print(sherpa_onnx.OnlineRecognizer.from_transducer)"`). Common alternate: `stream.accept_waveform(sample_rate, samples)`.

- [ ] **Step 4: Run unit test — PASS**

Run: `pytest tests/test_stt_finals.py -v`

---

### Task 5: Model download script

**Files:**
- Create: `scripts/download_model.py`

**Interfaces:**
- Downloads HF repo snapshot into `models/sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16/`
- Required files: `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx`, `tokens.txt`

- [ ] **Step 1: Implement script**

```python
# scripts/download_model.py
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
OUT = Path("models/sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16")

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = OUT / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"skip {name}")
            continue
        url = f"{BASE}/{name}"
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
```

- [ ] **Step 2: Run download**

Run: `python scripts/download_model.py`  
Expected: `OK` and four files present.

---

### Task 6: Capture + session manager

**Files:**
- Create: `meeting_bridge/capture.py`
- Create: `meeting_bridge/session.py`
- Create: `tests/test_session.py`

**Interfaces:**
- Produces:
  - `class SessionManager`
  - `start(cfg: AppConfig, mic_override: str | None = None, speaker_override: str | None = None) -> dict`
  - `stop() -> dict`
  - `status() -> dict` with `state` (`listening`|`idle`), `transcript_path`, `mic`, `speaker`, `warning`
  - Internal: spawn two reader loops; each loop reads PCM → `FinalOnlyTranscriber.accept_audio` → `writer.append(role, text)`

Capture outline (PyAudioWPatch):

```python
# pseudocode for one channel
stream = p.open(
    format=pyaudio.paFloat32,
    channels=1,
    rate=sample_rate,
    input=True,
    input_device_index=device_index,
    frames_per_buffer=blocksize,
)
while running:
    data = stream.read(blocksize, exception_on_overflow=False)
    samples = np.frombuffer(data, dtype=np.float32)
    for text in transcriber.accept_audio(stt_stream, samples):
        writer.append(role, text)
```

Resample if device default rate ≠ 16000: simple linear resample with numpy, or open stream at device rate and resample chunks before STT.

- [ ] **Step 1: Write session tests with mocked DualCapture**

```python
# tests/test_session.py
from pathlib import Path
from meeting_bridge.config import AppConfig
from meeting_bridge.session import SessionManager

class FakeCapture:
    def __init__(self):
        self.started = False
        self.stopped = False
    def start(self, **kwargs):
        self.started = True
    def stop(self):
        self.stopped = True

def test_start_stop_status(tmp_path: Path, monkeypatch):
    cfg = AppConfig(
        mic_device="Mic",
        speaker_device="Spk",
        transcript_path=tmp_path / "live-transcript.md",
        model_dir=tmp_path / "model",
        archive_dir=tmp_path / "archives",
    )
    fake = FakeCapture()
    mgr = SessionManager(capture_factory=lambda **kw: fake)
    # bypass device resolve + model load by injecting resolved devices
    out = mgr.start(cfg, resolved_mic={"index": 0, "name": "Mic"}, resolved_loop={"index": 1, "name": "Spk"}, skip_stt=True)
    assert out["state"] == "listening"
    assert fake.started
    st = mgr.status()
    assert st["state"] == "listening"
    mgr.stop()
    assert fake.stopped
    assert mgr.status()["state"] == "idle"
```

Implement `SessionManager` so tests can inject `capture_factory` and skip real STT/device IO.

- [ ] **Step 2: Implement `capture.py` + `session.py`**

Keep capture class `DualCapture` with `start()` / `stop()` managing threads + PyAudio. On same-device, include warning string in status but still start (user may override).

`start()` must raise `ValueError` if `mic_device` or `speaker_device` empty.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_session.py tests/test_writer.py tests/test_config.py tests/test_devices.py tests/test_stt_finals.py -v`  
Expected: PASS

---

### Task 7: CLI + MCP server

**Files:**
- Create: `meeting_bridge/__main__.py`
- Create: `meeting_bridge/mcp_server.py`
- Create: `README.md`

**Interfaces — MCP tools (FastMCP):**

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("meeting-bridge")

@mcp.tool()
def list_audio_devices() -> dict: ...

@mcp.tool()
def session_start(mic_device: str | None = None, speaker_device: str | None = None) -> dict: ...

@mcp.tool()
def session_stop() -> dict: ...

@mcp.tool()
def session_status() -> dict: ...

@mcp.tool()
def transcript_tail(n: int = 30) -> str: ...
```

CLI:

```text
python -m meeting_bridge devices
python -m meeting_bridge start
python -m meeting_bridge stop   # if using a PID/lock file — OR document that stop is MCP-only when started via MCP
python -m meeting_bridge mcp    # run stdio MCP server
```

For CLI `start`: run capture in foreground until Ctrl+C (SIGINT → stop). For MCP: background threads inside server process.

Shared singleton:

```python
# meeting_bridge/session.py
MANAGER = SessionManager()
```

- [ ] **Step 1: Implement MCP + CLI**

```python
# meeting_bridge/mcp_server.py
from __future__ import annotations
from mcp.server.fastmcp import FastMCP
from meeting_bridge.config import load_config
from meeting_bridge.devices import list_audio_devices as _list
from meeting_bridge.session import MANAGER

mcp = FastMCP("meeting-bridge")

@mcp.tool()
def list_audio_devices() -> dict:
    """List microphone and WASAPI loopback devices."""
    return _list()

@mcp.tool()
def session_start(mic_device: str | None = None, speaker_device: str | None = None) -> dict:
    """Start dual-channel capture into live-transcript.md."""
    cfg = load_config()
    return MANAGER.start(cfg, mic_override=mic_device, speaker_override=speaker_device)

@mcp.tool()
def session_stop() -> dict:
    """Stop capture and set status idle."""
    return MANAGER.stop()

@mcp.tool()
def session_status() -> dict:
    """Return listening/idle, devices, transcript path."""
    return MANAGER.status()

@mcp.tool()
def transcript_tail(n: int = 30) -> str:
    """Return last N transcript lines."""
    return MANAGER.tail(n)

def main() -> None:
    mcp.run()
```

```python
# meeting_bridge/__main__.py
from __future__ import annotations
import argparse
import json
from meeting_bridge.config import load_config
from meeting_bridge.devices import list_audio_devices
from meeting_bridge.session import MANAGER

def main() -> None:
    parser = argparse.ArgumentParser(prog="meeting_bridge")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices")
    sub.add_parser("start")
    sub.add_parser("mcp")
    args = parser.parse_args()
    if args.cmd == "devices":
        print(json.dumps(list_audio_devices(), ensure_ascii=False, indent=2))
    elif args.cmd == "start":
        cfg = load_config()
        print(MANAGER.start(cfg))
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(MANAGER.stop())
    elif args.cmd == "mcp":
        from meeting_bridge.mcp_server import main as mcp_main
        mcp_main()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: README with Cursor mcp.json**

```markdown
# Meeting Bridge

Локальный мост созвона → `live-transcript.md` → Cursor.

## Setup

```powershell
cd "C:\Users\cobra\Desktop\Папки РС\Секстант"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/download_model.py
python -m meeting_bridge devices
```

Заполните `mic_device` и `speaker_device` в `config.yaml` подстроками из списка (для собеседника — **loopback** наушников).

## Cursor MCP

В `mcp.json` (Cursor Settings → MCP):

```json
{
  "mcpServers": {
    "meeting-bridge": {
      "command": "C:\\Users\\cobra\\Desktop\\Папки РС\\Секстант\\.venv\\Scripts\\python.exe",
      "args": ["-m", "meeting_bridge", "mcp"],
      "cwd": "C:\\Users\\cobra\\Desktop\\Папки РС\\Секстант"
    }
  }
}
```

Перезапустите MCP / Cursor. Инструменты: `session_start`, `session_stop`, `session_status`, `transcript_tail`, `list_audio_devices`.

## Usage

1. `session_start` (или `python -m meeting_bridge start`)
2. Созвон → смотрите `live-transcript.md`
3. В чате Cursor: «что ответить?»
4. `session_stop`
```

- [ ] **Step 3: Wire Cursor**

Add/merge the `meeting-bridge` entry into the user’s Cursor MCP config (path may be `%USERPROFILE%\.cursor\mcp.json`). Do not overwrite unrelated servers.

- [ ] **Step 4: End-to-end manual check**

1. Fill `config.yaml` devices  
2. `python -m meeting_bridge start`  
3. Speak into mic; play Russian speech in headphones  
4. Confirm lines `Я:` and `Собеседник:` appear in `live-transcript.md`  
5. Stop with Ctrl+C  
6. Restart Cursor MCP and call `session_status`

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Mic + loopback capture | 3, 6 |
| Local RU STT finals only | 4, 5 |
| `live-transcript.md` + roles | 2 |
| Rotate ~2000 lines | 2 |
| MCP start/stop/status/tail/devices | 7 |
| config.yaml + same-device warning | 1, 3, 6 |
| README + Cursor wiring | 7 |
| No overlay / no in-app LLM / no raw audio | Global constraints |

## Deviation from design doc

- Capture: **PyAudioWPatch** instead of `sounddevice` (loopback not available in sounddevice high-level API).
- Update design doc tech stack line when implementing Task 6/7.

## Self-review notes

- No TBD placeholders in tasks
- Writer / session / MCP share `TranscriptWriter.tail` and `MANAGER`
- STT constructor requires model files from Task 5 before real `start`
- Prefer Python 3.12 venv if 3.13 wheels fail for `sherpa-onnx` or `PyAudioWPatch`
