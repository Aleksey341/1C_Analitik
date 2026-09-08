from pathlib import Path
import textwrap
from meeting_bridge.config import load_config, AppConfig, save_config, model_files_ready


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
    assert cfg.llm.model == "gpt-4o"
    assert cfg.llm.enabled is True
    assert cfg.llm.auto_reply is False
    assert cfg.llm.auto_reply_pause_sec == 4.0
    assert cfg.llm.max_tokens == 1000


def test_save_config_updates_auto_reply(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "mic_device: ''\nspeaker_device: ''\nllm:\n  api_key: secret\n",
        encoding="utf-8",
    )
    save_config(llm_auto_reply=True, path=p)
    cfg = load_config(p)
    assert cfg.llm.auto_reply is True
    assert cfg.llm.api_key == "secret"


def test_load_config_allows_empty_devices_for_bootstrap(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text("mic_device: ''\nspeaker_device: ''\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.mic_device == ""
    assert cfg.speaker_device == ""


def test_save_config_updates_devices(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "mic_device: ''\nspeaker_device: ''\ntranscript_path: live-transcript.md\n",
        encoding="utf-8",
    )
    save_config(mic_device="Mic X", speaker_device="Loop Y", path=p)
    cfg = load_config(p)
    assert cfg.mic_device == "Mic X"
    assert cfg.speaker_device == "Loop Y"
    assert cfg.transcript_path == Path("live-transcript.md")


def test_model_files_ready_false_when_missing(tmp_path: Path):
    assert model_files_ready(tmp_path / "missing") is False
