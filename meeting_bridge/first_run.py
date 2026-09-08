"""First-run setup for the packaged Windows application."""
from __future__ import annotations

import shutil
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog

from meeting_bridge.config import load_config, save_config
from meeting_bridge.llm_client import resolve_api_key


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


def ensure_api_key(root: Path) -> bool:
    """Ask once for an OpenAI API key when none is configured.

    Returns True when a key is available either in config.yaml or through the
    configured environment variable. Cancelling the dialog is allowed; the app
    still opens, but AI reply features will remain unavailable until a key is
    configured.
    """
    cfg_path = ensure_local_config(root)
    cfg = load_config(cfg_path)
    if resolve_api_key(cfg.llm):
        return True

    window = tk.Tk()
    window.withdraw()
    try:
        key = simpledialog.askstring(
            "1С Аналитик — первый запуск",
            "Вставьте ваш OpenAI API key.\n\n"
            "Ключ сохраняется только на этом компьютере в config.yaml "
            "и не отправляется в GitHub.\n\n"
            "Можно нажать Отмена и настроить ключ позже, но функции ИИ "
            "до этого работать не будут.",
            parent=window,
            show="*",
        )
        if not key or not key.strip():
            messagebox.showwarning(
                "1С Аналитик",
                "API key не задан. Программа откроется, но «Ответ ИИ» и "
                "«Автоответ ИИ» будут недоступны до настройки ключа.",
                parent=window,
            )
            return False

        save_config(llm_api_key=key.strip(), path=cfg_path)
        messagebox.showinfo(
            "1С Аналитик",
            "API key сохранён локально. Можно начинать работу.",
            parent=window,
        )
        return True
    finally:
        window.destroy()


def ensure_first_run(root: Path) -> None:
    ensure_local_config(root)
    ensure_api_key(root)
