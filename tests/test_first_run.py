from pathlib import Path

from meeting_bridge.config import load_config, save_config
from meeting_bridge.first_run import ensure_local_config


def test_ensure_local_config_copies_example(tmp_path: Path) -> None:
    example = tmp_path / "config.example.yaml"
    example.write_text(
        'mic_device: ""\n'
        'speaker_device: ""\n'
        'llm:\n'
        '  api_key: ""\n'
        '  model: gpt-5.6-sol\n',
        encoding="utf-8",
    )

    cfg = ensure_local_config(tmp_path)

    assert cfg == tmp_path / "config.yaml"
    assert cfg.exists()
    assert cfg.read_text(encoding="utf-8") == example.read_text(encoding="utf-8")


def test_save_config_stores_api_key_locally(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        'mic_device: ""\n'
        'speaker_device: ""\n'
        'llm:\n'
        '  api_key: ""\n'
        '  model: gpt-5.6-sol\n',
        encoding="utf-8",
    )

    save_config(llm_api_key="test-local-key", path=cfg)

    loaded = load_config(cfg)
    assert loaded.llm.api_key == "test-local-key"
