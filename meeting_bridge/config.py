from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml

from meeting_bridge.llm_client import (
    DEFAULT_AUTO_SYSTEM_PROMPT,
    DEFAULT_SPOKEN_SYSTEM_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
    LlmSettings,
)

DEFAULT_MODEL_DIR = (
    "models/sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16"
)


@dataclass(frozen=True)
class AppConfig:
    mic_device: str
    speaker_device: str
    transcript_path: Path
    model_dir: Path
    sample_rate: int = 16000
    max_transcript_lines: int = 2000
    archive_dir: Path = Path("transcripts")
    llm: LlmSettings = LlmSettings()


def _parse_llm(raw: dict) -> LlmSettings:
    block = raw.get("llm") or {}
    if not isinstance(block, dict):
        block = {}
    # Промпты по умолчанию из кода (актуальные правила 1С:ERP).
    # Кастом из yaml только если llm.use_custom_prompts: true.
    use_custom = bool(block.get("use_custom_prompts", False))
    system_prompt = (
        str(block.get("system_prompt", DEFAULT_SYSTEM_PROMPT))
        if use_custom
        else DEFAULT_SYSTEM_PROMPT
    )
    auto_system_prompt = (
        str(block.get("auto_system_prompt", DEFAULT_AUTO_SYSTEM_PROMPT))
        if use_custom
        else DEFAULT_AUTO_SYSTEM_PROMPT
    )
    spoken_system_prompt = (
        str(block.get("spoken_system_prompt", DEFAULT_SPOKEN_SYSTEM_PROMPT))
        if use_custom
        else DEFAULT_SPOKEN_SYSTEM_PROMPT
    )
    return LlmSettings(
        enabled=bool(block.get("enabled", True)),
        base_url=str(block.get("base_url", "https://api.openai.com/v1")),
        api_key=str(block.get("api_key", "")),
        api_key_env=str(block.get("api_key_env", "OPENAI_API_KEY")),
        model=str(block.get("model", "gpt-4o")),
        system_prompt=system_prompt,
        auto_system_prompt=auto_system_prompt,
        spoken_system_prompt=spoken_system_prompt,
        timeout_sec=int(block.get("timeout_sec", 120)),
        max_context_lines=int(block.get("max_context_lines", 40)),
        auto_reply=bool(block.get("auto_reply", False)),
        auto_reply_pause_sec=float(block.get("auto_reply_pause_sec", 4.0)),
        auto_reply_on_me=bool(block.get("auto_reply_on_me", True)),
        spoken_mode=bool(block.get("spoken_mode", False)),
        max_tokens=int(block.get("max_tokens", 1000)),
        ssl_verify=bool(block.get("ssl_verify", True)),
    )


def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or Path("config.yaml")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return AppConfig(
        mic_device=str(raw.get("mic_device", "")),
        speaker_device=str(raw.get("speaker_device", "")),
        transcript_path=Path(raw.get("transcript_path", "live-transcript.md")),
        model_dir=Path(raw.get("model_dir", DEFAULT_MODEL_DIR)),
        sample_rate=int(raw.get("sample_rate", 16000)),
        max_transcript_lines=int(raw.get("max_transcript_lines", 2000)),
        archive_dir=Path(raw.get("archive_dir", "transcripts")),
        llm=_parse_llm(raw),
    )


def _default_llm_block() -> dict:
    return {
        "enabled": True,
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4o",
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "auto_system_prompt": DEFAULT_AUTO_SYSTEM_PROMPT,
        "spoken_system_prompt": DEFAULT_SPOKEN_SYSTEM_PROMPT,
        "timeout_sec": 120,
        "max_context_lines": 40,
        "auto_reply": False,
        "auto_reply_pause_sec": 4.0,
        "auto_reply_on_me": True,
        "spoken_mode": False,
        "max_tokens": 1000,
        "ssl_verify": True,
    }


def save_config(
    *,
    mic_device: str | None = None,
    speaker_device: str | None = None,
    llm_auto_reply: bool | None = None,
    llm_spoken_mode: bool | None = None,
    path: Path | None = None,
) -> Path:
    """Update selected fields in config.yaml, preserving other keys."""
    cfg_path = path or Path("config.yaml")
    raw: dict = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if mic_device is not None:
        raw["mic_device"] = mic_device
    if speaker_device is not None:
        raw["speaker_device"] = speaker_device
    raw.setdefault("transcript_path", "live-transcript.md")
    raw.setdefault("model_dir", DEFAULT_MODEL_DIR)
    raw.setdefault("sample_rate", 16000)
    raw.setdefault("max_transcript_lines", 2000)
    raw.setdefault("archive_dir", "transcripts")
    llm = raw.get("llm")
    if not isinstance(llm, dict):
        llm = _default_llm_block()
        raw["llm"] = llm
    else:
        for key, value in _default_llm_block().items():
            llm.setdefault(key, value)
    if llm_auto_reply is not None:
        llm["auto_reply"] = bool(llm_auto_reply)
    if llm_spoken_mode is not None:
        llm["spoken_mode"] = bool(llm_spoken_mode)
    cfg_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return cfg_path


def model_files_ready(model_dir: Path | None = None) -> bool:
    directory = Path(model_dir or DEFAULT_MODEL_DIR)
    required = (
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    )
    return all(
        (directory / name).exists() and (directory / name).stat().st_size > 0
        for name in required
    )
