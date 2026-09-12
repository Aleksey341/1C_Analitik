from __future__ import annotations

import threading

import numpy as np

from meeting_bridge.capture import DualCapture
from meeting_bridge.session import SessionManager


def _bare_capture() -> DualCapture:
    capture = DualCapture.__new__(DualCapture)
    capture._signal_lock = threading.Lock()
    capture._audio_levels = {"Я": 0.0, "Собеседник": 0.0}
    capture._audio_peaks = {"Я": 0.0, "Собеседник": 0.0}
    capture._audio_chunks = {"Я": 0, "Собеседник": 0}
    return capture


def test_audio_health_distinguishes_real_signal_from_silence():
    capture = _bare_capture()
    capture._update_audio_health("Я", np.full(1600, 0.05, dtype=np.float32))
    capture._update_audio_health("Собеседник", np.zeros(1600, dtype=np.float32))

    health = capture.audio_health()
    assert health["Я"]["has_signal"] is True
    assert health["Я"]["level"] >= 0.049
    assert health["Я"]["chunks"] == 1
    assert health["Собеседник"]["has_signal"] is False
    assert health["Собеседник"]["chunks"] == 1


def test_session_status_exposes_capture_audio_health():
    class Capture:
        @staticmethod
        def audio_health():
            return {
                "Я": {"level": 0.02, "peak": 0.1, "chunks": 4, "has_signal": True},
                "Собеседник": {"level": 0.0, "peak": 0.0, "chunks": 4, "has_signal": False},
            }

    manager = SessionManager()
    manager._capture = Capture()
    manager._state = "listening"

    status = manager.status()
    assert status["audio_health"]["Я"]["has_signal"] is True
    assert status["audio_health"]["Собеседник"]["has_signal"] is False
