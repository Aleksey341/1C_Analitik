from pathlib import Path

import yaml

from meeting_bridge.config import load_config, save_config
from meeting_bridge.first_run import (
    _apply_managed_base_url,
    _is_managed_service,
    ensure_local_config,
)


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


def test_is_managed_service() -> None:
    assert _is_managed_service("https://example.vercel.app/api") is True
    assert _is_managed_service("https://api.openai.com/v1") is False


def test_managed_switch_clears_direct_openai_key(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "llm:\n"
        "  base_url: https://api.openai.com/v1\n"
        "  api_key: sk-test-secret-value\n",
        encoding="utf-8",
    )

    _apply_managed_base_url(cfg, "https://service.example/api")

    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert raw["llm"]["base_url"] == "https://service.example/api"
    assert raw["llm"]["api_key"] == ""


def test_managed_switch_keeps_existing_access_code(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "llm:\n"
        "  base_url: https://old.example/api\n"
        "  api_key: 1CA-existing-code\n",
        encoding="utf-8",
    )

    _apply_managed_base_url(cfg, "https://new.example/api")

    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert raw["llm"]["api_key"] == "1CA-existing-code"
