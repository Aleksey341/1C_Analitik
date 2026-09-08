from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import numpy as np

from meeting_bridge.devices import DeviceInfo
from meeting_bridge.stt import FinalOnlyTranscriber
from meeting_bridge.writer import TranscriptWriter


class DualCapture:
    """Capture microphone and WASAPI loopback audio on separate threads."""

    def __init__(
        self,
        *,
        mic_device: DeviceInfo,
        loopback_device: DeviceInfo,
        transcriber: FinalOnlyTranscriber,
        writer: TranscriptWriter,
        sample_rate: int = 16000,
        blocksize: int = 1600,
        audio_module: Any | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        self.mic_device = mic_device
        self.loopback_device = loopback_device
        self.transcriber = transcriber
        self.writer = writer
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self._audio_module = audio_module
        self._on_error = on_error
        self._audio: Any | None = None
        self._streams: list[Any] = []
        self._readers: list[tuple[Any, int, int, str, Any]] = []
        self._threads: list[threading.Thread] = []
        self._running = threading.Event()
        self._lock = threading.RLock()
        self._error_lock = threading.Lock()
        self.last_error: BaseException | None = None

    def start(self) -> None:
        with self._lock:
            if self._running.is_set():
                return
            with self._error_lock:
                self.last_error = None

            audio_module = self._audio_module
            if audio_module is None:
                import pyaudiowpatch as audio_module  # type: ignore

            self._audio = audio_module.PyAudio()
            opened: list[Any] = []
            readers: list[tuple[Any, int, str, Any]] = []
            try:
                for device, role in (
                    (self.mic_device, "Я"),
                    (self.loopback_device, "Собеседник"),
                ):
                    device_rate = self._device_rate(device)
                    device_blocksize = max(
                        1, round(self.blocksize * device_rate / self.sample_rate)
                    )
                    stream, channels = self._open_input_stream(
                        audio_module,
                        device=device,
                        device_rate=device_rate,
                        frames_per_buffer=device_blocksize,
                    )
                    opened.append(stream)
                    readers.append(
                        (
                            stream,
                            device_rate,
                            channels,
                            role,
                            self.transcriber.create_stream(),
                        )
                    )
            except BaseException:
                self._close_audio(opened)
                raise

            self._streams = opened
            self._readers = readers
            self._running.set()
            self._threads = [
                threading.Thread(
                    target=self._reader_loop,
                    args=(stream, device_rate, channels, role, stt_stream),
                    name=f"meeting-bridge-{role}",
                    daemon=True,
                )
                for stream, device_rate, channels, role, stt_stream in readers
            ]
            for thread in self._threads:
                thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running.clear()
            streams = self._streams
            readers = self._readers
            threads = self._threads
            self._streams = []
            self._readers = []
            self._threads = []

            for thread in threads:
                if thread is not threading.current_thread():
                    thread.join(timeout=2)

            silence = np.zeros(max(1, round(self.sample_rate * 0.5)), dtype=np.float32)
            for _stream, _device_rate, _channels, role, stt_stream in readers:
                try:
                    input_finished = getattr(stt_stream, "input_finished", None)
                    if callable(input_finished):
                        input_finished()
                    for text in self.transcriber.accept_audio(stt_stream, silence):
                        self.writer.append(role, text)
                except BaseException as exc:
                    self._report_error(exc)

            for stream in streams:
                try:
                    stream.stop_stream()
                except (OSError, AttributeError):
                    pass
                try:
                    stream.close()
                except (OSError, AttributeError):
                    pass

            if self._audio is not None:
                try:
                    self._audio.terminate()
                except (OSError, AttributeError):
                    pass
                self._audio = None

    def _reader_loop(
        self,
        stream: Any,
        device_rate: int,
        channels: int,
        role: str,
        stt_stream: Any,
    ) -> None:
        device_blocksize = max(
            1, round(self.blocksize * device_rate / self.sample_rate)
        )
        while self._running.is_set():
            try:
                data = stream.read(device_blocksize, exception_on_overflow=False)
                samples = np.frombuffer(data, dtype=np.float32)
                if channels > 1:
                    usable = (len(samples) // channels) * channels
                    samples = samples[:usable].reshape(-1, channels).mean(axis=1)
                if device_rate != self.sample_rate:
                    samples = self._resample(samples, device_rate, self.sample_rate)
                for text in self.transcriber.accept_audio(stt_stream, samples):
                    self.writer.append(role, text)
            except BaseException as exc:
                if self._running.is_set():
                    self._report_error(exc)
                break

    def _report_error(self, exc: BaseException) -> None:
        with self._error_lock:
            if self.last_error is not None:
                return
            self.last_error = exc
        if self._on_error is not None:
            try:
                self._on_error(exc)
            except BaseException:
                pass

    def _device_rate(self, device: DeviceInfo) -> int:
        rate = int(float(device.get("defaultSampleRate") or self.sample_rate))
        if rate <= 0:
            raise ValueError(f"Invalid sample rate for device {device.get('name')!r}")
        return rate

    def _device_channels(self, device: DeviceInfo) -> int:
        """Preferred channel count (may still fail; use _open_input_stream)."""
        channels = int(device.get("maxInputChannels") or 1)
        if channels < 1:
            raise ValueError(f"Invalid channel count for device {device.get('name')!r}")
        # WASAPI loopback devices usually require stereo (2), not mono.
        if device.get("is_loopback") and channels < 2:
            channels = 2
        # Virtual/array mics often advertise many channels but only accept 1–2.
        if not device.get("is_loopback") and channels > 2:
            channels = 1
        return channels

    def _channel_candidates(self, device: DeviceInfo) -> list[int]:
        max_ch = max(1, int(device.get("maxInputChannels") or 1))
        preferred: list[int] = []
        if device.get("is_loopback"):
            preferred = [2, 1, min(max_ch, 2), max_ch]
        else:
            # Altered/virtual/array devices: try mono first, then stereo.
            preferred = [1, 2, min(2, max_ch), max_ch]
        out: list[int] = []
        for channels in preferred:
            if channels < 1:
                continue
            if channels > max(max_ch, 2):
                continue
            if channels not in out:
                out.append(channels)
        for channels in range(1, min(max_ch, 8) + 1):
            if channels not in out:
                out.append(channels)
        return out

    def _open_input_stream(
        self,
        audio_module: Any,
        *,
        device: DeviceInfo,
        device_rate: int,
        frames_per_buffer: int,
    ) -> tuple[Any, int]:
        assert self._audio is not None
        errors: list[str] = []
        for channels in self._channel_candidates(device):
            try:
                stream = self._audio.open(
                    format=audio_module.paFloat32,
                    channels=channels,
                    rate=device_rate,
                    input=True,
                    input_device_index=int(device["index"]),
                    frames_per_buffer=frames_per_buffer,
                )
                return stream, channels
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{channels}ch: {exc}")
        name = device.get("name", "?")
        detail = "; ".join(errors[:6]) or "unknown"
        raise OSError(
            f"Не удалось открыть устройство {name!r} "
            f"(rate={device_rate}). Пробовали каналы: {detail}. "
            "Выберите другой микрофон (Realtek/гарнитура) или Loopback наушников."
        )

    @staticmethod
    def _resample(
        samples: np.ndarray, source_rate: int, target_rate: int
    ) -> np.ndarray:
        if len(samples) == 0 or source_rate == target_rate:
            return samples.astype(np.float32, copy=False)
        target_length = max(1, round(len(samples) * target_rate / source_rate))
        source_positions = np.arange(len(samples), dtype=np.float64)
        target_positions = np.linspace(
            0, len(samples) - 1, target_length, dtype=np.float64
        )
        return np.interp(target_positions, source_positions, samples).astype(
            np.float32
        )

    def _close_audio(self, streams: list[Any]) -> None:
        for stream in streams:
            try:
                stream.close()
            except (OSError, AttributeError):
                pass
        if self._audio is not None:
            self._audio.terminate()
            self._audio = None
