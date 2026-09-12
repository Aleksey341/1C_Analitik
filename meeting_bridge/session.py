from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import threading
from typing import Any

from meeting_bridge.capture import DualCapture
from meeting_bridge.config import AppConfig
from meeting_bridge.devices import DeviceInfo, resolve_device, same_device_warning
from meeting_bridge.stt import FinalOnlyTranscriber
from meeting_bridge.writer import TranscriptWriter

CaptureFactory = Callable[..., Any]


class SessionManager:
    def __init__(self, capture_factory: CaptureFactory = DualCapture) -> None:
        self._capture_factory = capture_factory
        self._lock = threading.RLock()
        self._state = "idle"
        self._transcript_path: str | None = None
        self._mic: str | None = None
        self._speaker: str | None = None
        self._warning: str | None = None
        self._error: str | None = None
        self._writer: TranscriptWriter | None = None
        self._capture: Any | None = None

    def start(
        self,
        cfg: AppConfig,
        mic_override: str | None = None,
        speaker_override: str | None = None,
        *,
        resolved_mic: DeviceInfo | None = None,
        resolved_loop: DeviceInfo | None = None,
        skip_stt: bool = False,
    ) -> dict[str, Any]:
        mic_query = mic_override if mic_override is not None else cfg.mic_device
        speaker_query = (
            speaker_override if speaker_override is not None else cfg.speaker_device
        )
        if not mic_query.strip():
            raise ValueError("mic_device must not be empty")
        if not speaker_query.strip():
            raise ValueError("speaker_device must not be empty")

        with self._lock:
            if self._state == "listening":
                return self._status_unlocked()

            mic = resolved_mic or resolve_device(mic_query, "mic")
            loopback = resolved_loop or resolve_device(speaker_query, "loopback")
            mic_name = str(mic.get("name", mic_query))
            speaker_name = str(loopback.get("name", speaker_query))
            warning = same_device_warning(mic, loopback)

            writer = TranscriptWriter(
                cfg.transcript_path,
                archive_dir=cfg.archive_dir,
                max_lines=cfg.max_transcript_lines,
            )
            writer.start_session(
                mic=mic_name,
                speaker=speaker_name,
                session_iso=datetime.now().isoformat(timespec="seconds"),
            )

            self._transcript_path = str(cfg.transcript_path)
            self._mic = mic_name
            self._speaker = speaker_name
            self._warning = warning
            self._error = None
            self._writer = writer

            capture: Any | None = None
            try:
                transcriber = (
                    None
                    if skip_stt
                    else FinalOnlyTranscriber(cfg.model_dir, cfg.sample_rate)
                )
                capture = self._capture_factory(
                    mic_device=mic,
                    loopback_device=loopback,
                    transcriber=transcriber,
                    writer=writer,
                    sample_rate=cfg.sample_rate,
                    on_error=self._on_capture_error,
                )
                capture.start()
            except BaseException:
                if capture is not None:
                    try:
                        capture.stop()
                    except BaseException:
                        pass
                writer.set_status("idle")
                self._capture = None
                self._state = "idle"
                raise

            self._capture = capture
            if self._state != "error":
                self._state = "listening"
            return self._status_unlocked()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            capture = self._capture
            writer = self._writer
        try:
            if capture is not None:
                capture.stop()
        finally:
            with self._lock:
                if writer is not None:
                    writer.set_status("idle")
                self._capture = None
                self._state = "idle"
        with self._lock:
            return self._status_unlocked()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status_unlocked()

    def tail(self, n: int) -> str:
        with self._lock:
            if self._writer is None:
                return ""
            return self._writer.tail(n)

    def append_line(self, role: str, text: str) -> None:
        """Append a line into the active transcript (or raise if no session writer)."""
        with self._lock:
            if self._writer is None:
                raise RuntimeError(
                    "Нет активной запись. Нажмите «Старт» или откройте сессию заново."
                )
            self._writer.append(role, text)

    def _on_capture_error(self, exc: BaseException) -> None:
        with self._lock:
            self._error = str(exc) or type(exc).__name__
            self._state = "error"
            if self._writer is not None:
                self._writer.set_status("error")

    def _capture_health_unlocked(self) -> dict[str, Any]:
        capture = self._capture
        if capture is None:
            return {}
        getter = getattr(capture, "audio_health", None)
        if not callable(getter):
            return {}
        try:
            return dict(getter())
        except Exception:  # noqa: BLE001
            return {}

    def _status_unlocked(self) -> dict[str, Any]:
        status: dict[str, Any] = {
            "state": self._state,
            "transcript_path": self._transcript_path,
            "mic": self._mic,
            "speaker": self._speaker,
            "warning": self._warning,
            "error": self._error,
        }
        audio_health = self._capture_health_unlocked()
        if audio_health:
            status["audio_health"] = audio_health
        return status


MANAGER = SessionManager()
