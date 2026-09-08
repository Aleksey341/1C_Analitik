from datetime import datetime
from pathlib import Path
import time

import numpy as np
import pytest

from meeting_bridge.capture import DualCapture
from meeting_bridge.config import AppConfig
from meeting_bridge.session import SessionManager


class FakeCapture:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self, **kwargs: object) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def make_config(tmp_path: Path, mic: str = "Mic", speaker: str = "Spk") -> AppConfig:
    return AppConfig(
        mic_device=mic,
        speaker_device=speaker,
        transcript_path=tmp_path / "live-transcript.md",
        model_dir=tmp_path / "model",
        archive_dir=tmp_path / "archives",
    )


def test_tail_returns_empty_when_idle() -> None:
    mgr = SessionManager(capture_factory=lambda **kwargs: FakeCapture())
    assert mgr.tail(5) == ""


def test_tail_returns_last_lines_after_append(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    writer_ref: list[object] = []

    def capture_factory(**kwargs: object) -> FakeCapture:
        writer_ref.append(kwargs["writer"])
        return FakeCapture()

    mgr = SessionManager(capture_factory=capture_factory)
    mgr.start(
        cfg,
        resolved_mic={"index": 0, "name": "Mic"},
        resolved_loop={"index": 1, "name": "Spk"},
        skip_stt=True,
    )

    writer = writer_ref[0]
    writer.append("Я", "one", when=datetime(2026, 8, 12, 21, 46, 1))
    writer.append("Я", "two", when=datetime(2026, 8, 12, 21, 46, 10))

    tail = mgr.tail(1)
    assert "two" in tail
    assert "one" not in tail

    mgr.stop()
    assert "one" in mgr.tail(10)
    assert "two" in mgr.tail(10)


def test_start_stop_status_without_live_audio(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    fake = FakeCapture()
    factory_kwargs: dict[str, object] = {}

    def capture_factory(**kwargs: object) -> FakeCapture:
        factory_kwargs.update(kwargs)
        return fake

    mgr = SessionManager(capture_factory=capture_factory)
    out = mgr.start(
        cfg,
        resolved_mic={"index": 0, "name": "Mic"},
        resolved_loop={"index": 1, "name": "Spk"},
        skip_stt=True,
    )

    assert out == {
        "state": "listening",
        "transcript_path": str(cfg.transcript_path),
        "mic": "Mic",
        "speaker": "Spk",
        "warning": None,
        "error": None,
    }
    assert fake.started
    assert factory_kwargs["mic_device"]["index"] == 0
    assert factory_kwargs["loopback_device"]["index"] == 1
    assert factory_kwargs["transcriber"] is None
    assert cfg.transcript_path.exists()

    assert mgr.status() == out
    stopped = mgr.stop()
    assert fake.stopped
    assert stopped["state"] == "idle"
    assert mgr.status()["state"] == "idle"
    assert "status: idle" in cfg.transcript_path.read_text(encoding="utf-8")


def test_capture_error_changes_session_state(tmp_path: Path) -> None:
    class FailingReaderCapture(FakeCapture):
        def __init__(self, on_error: object) -> None:
            super().__init__()
            self.on_error = on_error

        def start(self, **kwargs: object) -> None:
            super().start()
            self.on_error(OSError("audio device disconnected"))

    def capture_factory(**kwargs: object) -> FailingReaderCapture:
        return FailingReaderCapture(kwargs["on_error"])

    cfg = make_config(tmp_path)
    mgr = SessionManager(capture_factory=capture_factory)
    status = mgr.start(
        cfg,
        resolved_mic={"index": 0, "name": "Mic"},
        resolved_loop={"index": 1, "name": "Spk"},
        skip_stt=True,
    )

    assert status["state"] == "error"
    assert status["error"] == "audio device disconnected"
    assert "status: error" in cfg.transcript_path.read_text(encoding="utf-8")
    mgr.stop()


@pytest.mark.parametrize(
    ("mic", "speaker"),
    [
        ("", "Spk"),
        ("Mic", ""),
        ("   ", "Spk"),
        ("Mic", "   "),
    ],
)
def test_start_rejects_empty_device_names(
    tmp_path: Path, mic: str, speaker: str
) -> None:
    mgr = SessionManager(capture_factory=lambda **kwargs: FakeCapture())

    with pytest.raises(ValueError):
        mgr.start(make_config(tmp_path, mic=mic, speaker=speaker), skip_stt=True)


def test_overrides_resolve_devices_and_same_device_sets_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = make_config(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_resolve(name: str, kind: str) -> dict[str, object]:
        calls.append((name, kind))
        return {"index": 7, "name": f"{name} resolved"}

    monkeypatch.setattr("meeting_bridge.session.resolve_device", fake_resolve)
    mgr = SessionManager(capture_factory=lambda **kwargs: FakeCapture())

    out = mgr.start(
        cfg,
        mic_override="USB Mic",
        speaker_override="Headphones",
        skip_stt=True,
    )

    assert calls == [("USB Mic", "mic"), ("Headphones", "loopback")]
    assert out["mic"] == "USB Mic resolved"
    assert out["speaker"] == "Headphones resolved"
    assert out["warning"] is not None
    mgr.stop()


def test_start_failure_returns_manager_to_idle(tmp_path: Path) -> None:
    class FailingCapture(FakeCapture):
        def start(self, **kwargs: object) -> None:
            raise RuntimeError("capture failed")

    cfg = make_config(tmp_path)
    mgr = SessionManager(capture_factory=lambda **kwargs: FailingCapture())

    with pytest.raises(RuntimeError, match="capture failed"):
        mgr.start(
            cfg,
            resolved_mic={"index": 0, "name": "Mic"},
            resolved_loop={"index": 1, "name": "Spk"},
            skip_stt=True,
        )

    assert mgr.status()["state"] == "idle"
    assert "status: idle" in cfg.transcript_path.read_text(encoding="utf-8")


def test_dual_capture_reads_both_roles_and_resamples() -> None:
    class FakeStream:
        def __init__(self, sample_count: int) -> None:
            self._data = np.linspace(-1, 1, sample_count, dtype=np.float32).tobytes()
            self.closed = False

        def read(self, frames: int, exception_on_overflow: bool = False) -> bytes:
            if self._data:
                data, self._data = self._data, b""
                return data
            raise OSError("end of fake stream")

        def stop_stream(self) -> None:
            pass

        def close(self) -> None:
            self.closed = True

    class FakeAudio:
        def __init__(self) -> None:
            self.streams: list[FakeStream] = []
            self.terminated = False

        def open(self, **kwargs: object) -> FakeStream:
            stream = FakeStream(int(kwargs["frames_per_buffer"]))
            self.streams.append(stream)
            return stream

        def terminate(self) -> None:
            self.terminated = True

    audio = FakeAudio()

    class FakeAudioModule:
        paFloat32 = object()

        @staticmethod
        def PyAudio() -> FakeAudio:
            return audio

    class FakeTranscriber:
        def __init__(self) -> None:
            self.sample_lengths: list[int] = []

        def create_stream(self) -> object:
            return object()

        def accept_audio(self, stream: object, samples: np.ndarray) -> list[str]:
            self.sample_lengths.append(len(samples))
            return [] if np.all(samples == 0) else ["распознано"]

    class FakeWriter:
        def __init__(self) -> None:
            self.lines: list[tuple[str, str]] = []

        def append(self, role: str, text: str) -> None:
            self.lines.append((role, text))

    transcriber = FakeTranscriber()
    writer = FakeWriter()
    capture = DualCapture(
        mic_device={"index": 0, "name": "Mic", "defaultSampleRate": 16000},
        loopback_device={"index": 1, "name": "Spk", "defaultSampleRate": 8000},
        transcriber=transcriber,
        writer=writer,
        sample_rate=16000,
        blocksize=4,
        audio_module=FakeAudioModule,
    )

    capture.start()
    deadline = time.monotonic() + 1
    while len(writer.lines) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    capture.stop()

    assert sorted(writer.lines) == [
        ("Собеседник", "распознано"),
        ("Я", "распознано"),
    ]
    assert sorted(transcriber.sample_lengths) == [4, 4, 8000, 8000]
    assert audio.terminated
    assert all(stream.closed for stream in audio.streams)


def test_dual_capture_reports_reader_error() -> None:
    errors: list[BaseException] = []

    class FailingStream:
        def read(self, frames: int, exception_on_overflow: bool = False) -> bytes:
            raise OSError("reader failed")

        def stop_stream(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeAudio:
        def open(self, **kwargs: object) -> FailingStream:
            return FailingStream()

        def terminate(self) -> None:
            pass

    audio = FakeAudio()

    class FakeAudioModule:
        paFloat32 = object()

        @staticmethod
        def PyAudio() -> FakeAudio:
            return audio

    class FakeTranscriber:
        def create_stream(self) -> object:
            return object()

        def accept_audio(self, stream: object, samples: np.ndarray) -> list[str]:
            return []

    capture = DualCapture(
        mic_device={"index": 0, "name": "Mic", "defaultSampleRate": 16000},
        loopback_device={"index": 1, "name": "Spk", "defaultSampleRate": 16000},
        transcriber=FakeTranscriber(),
        writer=object(),
        audio_module=FakeAudioModule,
        on_error=errors.append,
    )

    capture.start()
    deadline = time.monotonic() + 1
    while not errors and time.monotonic() < deadline:
        time.sleep(0.01)
    capture.stop()

    assert isinstance(capture.last_error, OSError)
    assert str(capture.last_error) == "reader failed"
    assert errors and errors[0] is capture.last_error


def test_dual_capture_finalizes_stt_before_closing_audio() -> None:
    events: list[str] = []

    class FakeStream:
        def __init__(self) -> None:
            self.allow_read = True

        def read(self, frames: int, exception_on_overflow: bool = False) -> bytes:
            self.allow_read = False
            return np.zeros(frames, dtype=np.float32).tobytes()

        def stop_stream(self) -> None:
            events.append("audio-stop")

        def close(self) -> None:
            events.append("audio-close")

    class FakeAudio:
        def open(self, **kwargs: object) -> FakeStream:
            return FakeStream()

        def terminate(self) -> None:
            events.append("terminate")

    audio = FakeAudio()

    class FakeAudioModule:
        paFloat32 = object()

        @staticmethod
        def PyAudio() -> FakeAudio:
            return audio

    class FakeSttStream:
        def input_finished(self) -> None:
            events.append("input-finished")

    class FakeTranscriber:
        def create_stream(self) -> FakeSttStream:
            return FakeSttStream()

        def accept_audio(
            self, stream: FakeSttStream, samples: np.ndarray
        ) -> list[str]:
            if len(samples) == 8000:
                events.append("silence")
                return ["последняя фраза"]
            return []

    class FakeWriter:
        def append(self, role: str, text: str) -> None:
            events.append(f"write:{role}:{text}")

    capture = DualCapture(
        mic_device={"index": 0, "name": "Mic", "defaultSampleRate": 16000},
        loopback_device={"index": 1, "name": "Spk", "defaultSampleRate": 16000},
        transcriber=FakeTranscriber(),
        writer=FakeWriter(),
        sample_rate=16000,
        audio_module=FakeAudioModule,
    )
    capture.start()
    capture.stop()

    assert events.count("input-finished") == 2
    assert events.count("silence") == 2
    assert events.count("write:Я:последняя фраза") == 1
    assert events.count("write:Собеседник:последняя фраза") == 1
    assert max(i for i, event in enumerate(events) if event.startswith("write:")) < min(
        i for i, event in enumerate(events) if event == "audio-close"
    )
