import numpy as np

from meeting_bridge.stt import FinalOnlyTranscriber


class FakeStream:
    def __init__(self):
        self.accepted_audio = []

    def accept_waveform(self, sample_rate, samples):
        self.accepted_audio.append((sample_rate, samples))


class FakeRecognizer:
    def __init__(self):
        self._ready = True
        self._text = ""
        self._endpoint = False
        self.decode_calls = 0
        self.reset_calls = 0

    def create_stream(self):
        return FakeStream()

    def is_ready(self, stream):
        ready = self._ready
        self._ready = False
        return ready

    def decode_stream(self, stream):
        self.decode_calls += 1

    def get_result(self, stream):
        return self._text

    def is_endpoint(self, stream):
        return self._endpoint

    def reset(self, stream):
        self.reset_calls += 1
        self._text = ""
        self._endpoint = False


def make_transcriber(fake):
    transcriber = FinalOnlyTranscriber.__new__(FinalOnlyTranscriber)
    transcriber.sample_rate = 16000
    transcriber.recognizer = fake
    return transcriber


def test_emits_only_on_endpoint():
    fake = FakeRecognizer()
    transcriber = make_transcriber(fake)
    stream = fake.create_stream()

    fake._text = "Привет"
    assert transcriber.accept_audio(
        stream, np.zeros((1600, 2), dtype=np.float64)
    ) == []
    assert stream.accepted_audio[0][0] == 16000
    assert stream.accepted_audio[0][1].dtype == np.float32
    assert stream.accepted_audio[0][1].shape == (1600,)
    assert fake.decode_calls == 1

    fake._ready = True
    fake._endpoint = True
    finals = transcriber.accept_audio(stream, np.zeros(1600, dtype=np.float32))

    assert finals == ["Привет"]
    assert fake.reset_calls == 1


def test_keeps_last_non_empty_result_until_endpoint():
    fake = FakeRecognizer()
    transcriber = make_transcriber(fake)
    stream = fake.create_stream()

    fake._text = "Сохранённый результат"
    assert transcriber.accept_audio(stream, np.zeros(160, dtype=np.float32)) == []

    fake._ready = True
    fake._text = ""
    fake._endpoint = True

    assert transcriber.accept_audio(stream, np.zeros(160, dtype=np.float32)) == [
        "Сохранённый результат"
    ]
    assert fake.reset_calls == 1


def test_force_flushes_partial_when_endpoint_detection_never_fires():
    fake = FakeRecognizer()
    transcriber = make_transcriber(fake)
    transcriber.force_flush_sec = 0.2
    stream = fake.create_stream()

    fake._text = "Проверяем закрытие месяца"
    emitted = []
    for _ in range(3):
        fake._ready = True
        emitted.extend(
            transcriber.accept_audio(stream, np.zeros(1600, dtype=np.float32))
        )

    assert emitted == ["Проверяем закрытие месяца"]
    assert fake.reset_calls == 1
