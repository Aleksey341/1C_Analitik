from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

StreamHandle = Any


class FinalOnlyTranscriber:
    def __init__(self, model_dir: Path, sample_rate: int = 16000) -> None:
        import sherpa_onnx

        self.sample_rate = sample_rate
        self.force_flush_sec = 3.0
        self._last_text_by_stream: dict[int, str] = {}
        self._samples_with_text_by_stream: dict[int, int] = {}

        model_dir = Path(model_dir)
        encoder = model_dir / "encoder.int8.onnx"
        decoder = model_dir / "decoder.int8.onnx"
        joiner = model_dir / "joiner.int8.onnx"
        tokens = model_dir / "tokens.txt"
        for path in (encoder, decoder, joiner, tokens):
            if not path.exists():
                raise FileNotFoundError(f"Missing model file: {path}")

        self.recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(tokens),
            encoder=str(encoder),
            decoder=str(decoder),
            joiner=str(joiner),
            num_threads=2,
            sample_rate=sample_rate,
            feature_dim=80,
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=1.2,
            rule2_min_trailing_silence=0.8,
            rule3_min_utterance_length=1.2,
            provider="cpu",
        )

    def create_stream(self) -> StreamHandle:
        stream = self.recognizer.create_stream()
        stream_id = id(stream)
        self._last_text_by_stream[stream_id] = ""
        self._samples_with_text_by_stream[stream_id] = 0
        return stream

    def accept_audio(
        self, stream: StreamHandle, samples: np.ndarray
    ) -> list[str]:
        if samples.dtype != np.float32:
            samples = samples.astype(np.float32)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)

        stream.accept_waveform(self.sample_rate, samples)
        while self.recognizer.is_ready(stream):
            self.recognizer.decode_stream(stream)

        text = (self.recognizer.get_result(stream) or "").strip()
        text_by_stream = getattr(self, "_last_text_by_stream", None)
        if text_by_stream is None:
            text_by_stream = {}
            self._last_text_by_stream = text_by_stream
        samples_by_stream = getattr(self, "_samples_with_text_by_stream", None)
        if samples_by_stream is None:
            samples_by_stream = {}
            self._samples_with_text_by_stream = samples_by_stream

        stream_id = id(stream)
        if text:
            text_by_stream[stream_id] = text

        cached = text_by_stream.get(stream_id, "")
        if cached:
            samples_by_stream[stream_id] = samples_by_stream.get(stream_id, 0) + len(samples)
        else:
            samples_by_stream[stream_id] = 0

        endpoint = self.recognizer.is_endpoint(stream)
        force_flush_sec = float(getattr(self, "force_flush_sec", 3.0) or 3.0)
        force_flush_samples = max(1, round(self.sample_rate * force_flush_sec))
        forced = bool(cached) and samples_by_stream.get(stream_id, 0) >= force_flush_samples

        if not endpoint and not forced:
            return []

        final = text_by_stream.pop(stream_id, "")
        samples_by_stream[stream_id] = 0
        self.recognizer.reset(stream)
        return [final] if final else []
