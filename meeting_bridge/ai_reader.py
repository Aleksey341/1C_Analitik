"""Keep the latest AI answer readable while the live transcript keeps moving."""
from __future__ import annotations

import re
from typing import Any

_AI_PREFIX_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s+ИИ:\s*", re.UNICODE)
_INSTALLED = False


def latest_ai_reply(blocks: list[str]) -> str:
    """Return the newest AI block without its transcript prefix."""
    for block in reversed(blocks):
        if _AI_PREFIX_RE.match(block):
            return _AI_PREFIX_RE.sub("", block, count=1).strip()
    return ""


def install_ai_reader(gui_module: Any) -> None:
    """Add a pinned, scrollable latest-answer panel to MeetingBridgeApp."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    import customtkinter as ctk

    App = gui_module.MeetingBridgeApp
    original_build = App._build
    original_bootstrap = App._bootstrap
    original_on_ai_ok = App._on_ai_ok
    original_on_auto_ok = App._on_auto_ok

    def set_reader_text(self, text: str) -> None:  # noqa: ANN001
        text = (text or "").strip()
        if not text:
            return
        if getattr(self, "_ai_reader_last_text", "") == text:
            return
        self._ai_reader_last_text = text
        reader = getattr(self, "ai_reader", None)
        if reader is None:
            return
        reader.delete("1.0", "end")
        reader.insert("1.0", text)
        reader.see("1.0")

    def copy_reader(self) -> None:  # noqa: ANN001
        text = getattr(self, "_ai_reader_last_text", "")
        if text:
            self._clipboard_set(text)
            self.warn_label.configure(text="Ответ ИИ скопирован.")

    def jump_to_live(self) -> None:  # noqa: ANN001
        try:
            self.transcript.see("end")
        except Exception:  # noqa: BLE001
            pass

    def sync_from_transcript(self) -> None:  # noqa: ANN001
        try:
            cfg = gui_module.load_config()
            path = gui_module.ROOT / cfg.transcript_path
            if not path.exists():
                return
            blocks = gui_module.iter_dialogue_blocks(path.read_text(encoding="utf-8"))
            text = latest_ai_reply(blocks)
            if text:
                set_reader_text(self, text)
        except Exception:  # noqa: BLE001
            pass

    def patched_build(self) -> None:  # noqa: ANN001
        original_build(self)
        self._ai_reader_last_text = ""

        panel = ctk.CTkFrame(
            self,
            border_width=1,
            border_color="#c45c26",
        )
        panel.pack(
            fill="x",
            padx=12,
            pady=(4, 6),
            before=self.status_label,
        )

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(
            header,
            text="Ответ ИИ — закреплён",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#c45c26",
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text="Не двигается, пока продолжается созвон",
            text_color=("gray40", "gray65"),
        ).pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            header,
            text="К диалогу",
            width=95,
            fg_color=("gray70", "gray35"),
            command=lambda: jump_to_live(self),
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            header,
            text="Копировать",
            width=95,
            fg_color=("gray70", "gray35"),
            command=lambda: copy_reader(self),
        ).pack(side="right")

        self.ai_reader = ctk.CTkTextbox(panel, height=135, wrap="word")
        self.ai_reader.pack(fill="x", padx=10, pady=(4, 10))
        self.ai_reader.insert(
            "1.0",
            "Здесь будет закреплён последний ответ ИИ. "
            "Новые реплики созвона не будут сдвигать этот текст.",
        )
        self._lock_readonly(self.ai_reader)
        self._enable_clipboard(self.ai_reader, allow_paste=False)

    def patched_bootstrap(self) -> None:  # noqa: ANN001
        original_bootstrap(self)
        sync_from_transcript(self)

    def patched_on_ai_ok(self, reply: str, path) -> None:  # noqa: ANN001
        set_reader_text(self, reply)
        original_on_ai_ok(self, reply, path)

    def patched_on_auto_ok(self, reply, path, peer_line) -> None:  # noqa: ANN001
        if reply:
            set_reader_text(self, reply)
        original_on_auto_ok(self, reply, path, peer_line)

    App._build = patched_build
    App._bootstrap = patched_bootstrap
    App._on_ai_ok = patched_on_ai_ok
    App._on_auto_ok = patched_on_auto_ok
