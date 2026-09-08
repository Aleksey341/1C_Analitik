"""First-run setup for the packaged Windows application."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog
import urllib.error
import urllib.request

import yaml

from meeting_bridge.config import load_config, save_config
from meeting_bridge.llm_client import resolve_api_key

SERVICE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/Aleksey341/1C_Analitik/main/service.json"
)
DEFAULT_MANAGED_BASE_URL = "https://1canalitik.vercel.app/api"


def ensure_local_config(root: Path) -> Path:
    """Create a writable local config.yaml on first launch."""
    cfg_path = root / "config.yaml"
    if cfg_path.exists():
        return cfg_path

    example = root / "config.example.yaml"
    if example.exists():
        shutil.copyfile(example, cfg_path)
    else:
        save_config(path=cfg_path)
    return cfg_path


def _managed_fallback() -> str:
    # Packaged users must not depend on access to raw.githubusercontent.com
    # just to discover the managed service URL.
    if getattr(sys, "frozen", False):
        return DEFAULT_MANAGED_BASE_URL
    return ""


def _discover_managed_base_url(timeout: float = 3.0) -> str:
    request = urllib.request.Request(
        SERVICE_MANIFEST_URL,
        headers={"User-Agent": "1C-Analitik-First-Run"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return _managed_fallback()

    url = str(payload.get("managed_base_url") or "").strip().rstrip("/")
    if not url.lower().startswith("https://"):
        return _managed_fallback()
    return url


def _apply_managed_base_url(cfg_path: Path, managed_base_url: str) -> None:
    if not managed_base_url:
        return

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    llm = raw.get("llm")
    if not isinstance(llm, dict):
        llm = {}
        raw["llm"] = llm

    previous = str(llm.get("base_url") or "").strip().rstrip("/")
    if previous == managed_base_url:
        return

    old_key = str(llm.get("api_key") or "").strip()
    llm["base_url"] = managed_base_url

    # Never forward an old direct OpenAI key to a newly enabled managed gateway.
    if old_key.startswith("sk-"):
        llm["api_key"] = ""

    cfg_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _is_managed_service(base_url: str) -> bool:
    url = (base_url or "").casefold()
    return bool(url) and "api.openai.com" not in url


def ensure_ai_access(root: Path) -> bool:
    """Ensure either a managed access code or direct OpenAI key is available."""
    cfg_path = ensure_local_config(root)

    managed_base_url = _discover_managed_base_url()
    if managed_base_url:
        _apply_managed_base_url(cfg_path, managed_base_url)

    cfg = load_config(cfg_path)
    if resolve_api_key(cfg.llm):
        return True

    managed = _is_managed_service(cfg.llm.base_url)
    window = tk.Tk()
    window.withdraw()
    try:
        if managed:
            prompt = (
                "Введите код доступа к 1С Аналитик.\n\n"
                "Код выдаёт администратор сервиса. OpenAI API key вам не нужен.\n\n"
                "Код сохраняется только на этом компьютере."
            )
            title = "1С Аналитик — вход"
            missing = (
                "Код доступа не задан. Программа откроется, но функции ИИ "
                "будут недоступны до ввода кода."
            )
            success = "Код доступа сохранён. Можно начинать работу."
        else:
            prompt = (
                "Вставьте ваш OpenAI API key.\n\n"
                "Ключ сохраняется только на этом компьютере в config.yaml "
                "и не отправляется в GitHub.\n\n"
                "Можно нажать Отмена и настроить ключ позже."
            )
            title = "1С Аналитик — первый запуск"
            missing = (
                "API key не задан. Программа откроется, но «Ответ ИИ» и "
                "«Автоответ ИИ» будут недоступны до настройки ключа."
            )
            success = "API key сохранён локально. Можно начинать работу."

        value = simpledialog.askstring(
            title,
            prompt,
            parent=window,
            show="*",
        )
        if not value or not value.strip():
            messagebox.showwarning(
                "1С Аналитик",
                missing,
                parent=window,
            )
            return False

        # The llm client uses Bearer auth for both modes. In managed mode this
        # field contains only the service access code, not an OpenAI secret.
        save_config(llm_api_key=value.strip(), path=cfg_path)
        messagebox.showinfo(
            "1С Аналитик",
            success,
            parent=window,
        )
        return True
    finally:
        window.destroy()


def ensure_first_run(root: Path) -> None:
    ensure_local_config(root)
    ensure_ai_access(root)
