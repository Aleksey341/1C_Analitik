from __future__ import annotations

from meeting_bridge.capture import DualCapture


class _FakeAudio:
    def __init__(self, ok_channels: set[int]) -> None:
        self.ok_channels = ok_channels
        self.opened: list[int] = []

    def open(self, **kwargs):  # noqa: ANN003
        channels = int(kwargs["channels"])
        self.opened.append(channels)
        if channels not in self.ok_channels:
            raise OSError("[Errno -9998] Invalid number of channels")
        return object()


def test_channel_candidates_prefer_mono_for_virtual_mic():
    capture = DualCapture.__new__(DualCapture)
    device = {"name": "Altered Virtual", "maxInputChannels": 8, "is_loopback": False}
    assert capture._channel_candidates(device)[0] == 1
    assert 2 in capture._channel_candidates(device)


def test_open_input_stream_retries_channels():
    capture = DualCapture.__new__(DualCapture)
    fake = _FakeAudio(ok_channels={2})
    capture._audio = fake
    device = {
        "name": "Altered Virtual",
        "index": 3,
        "maxInputChannels": 8,
        "is_loopback": False,
    }
    stream, channels = capture._open_input_stream(
        type("M", (), {"paFloat32": 1})(),
        device=device,
        device_rate=48000,
        frames_per_buffer=4800,
    )
    assert stream is not None
    assert channels == 2
    assert fake.opened[0] == 1
    assert 2 in fake.opened
