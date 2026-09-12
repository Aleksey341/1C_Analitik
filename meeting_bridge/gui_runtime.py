"""Runtime-safe entry point and final user-facing polish for 1C Analitik UX v2."""
from __future__ import annotations

import customtkinter as ctk

from meeting_bridge import gui as legacy
from meeting_bridge import gui_v2
from meeting_bridge.session import MANAGER


class MeetingBridgeApp(gui_v2.MeetingBridgeApp):
    """UX v2 with safe Tk initialization and a quieter user-first first screen."""

    def _build(self) -> None:
        auto_reply_var = ctk.BooleanVar(value=True)
        spoken_mode_var = ctk.BooleanVar(value=False)
        self.auto_reply_var = auto_reply_var
        self.spoken_mode_var = spoken_mode_var
        super()._build()
        self.auto_reply_var = auto_reply_var
        self.spoken_mode_var = spoken_mode_var
        self._apply_user_first_polish()

    def _apply_user_first_polish(self) -> None:
        self.settings_btn.configure(
            text="⚙ Настройки",
            state="normal",
            fg_color=("gray70", "gray32"),
            hover_color=("gray60", "gray40"),
            text_color=("gray12", "gray95"),
            border_width=1,
            border_color=("gray58", "gray45"),
        )
        for widget in self._walk_widgets(self):
            try:
                if isinstance(widget, ctk.CTkLabel) and widget.cget("text") == "Тема встречи":
                    widget.configure(text="Тема встречи (необязательно)")
                    break
            except Exception:  # noqa: BLE001
                continue
        self.ai_question.configure(placeholder_text="Спросить 1С Аналитика…")
        self.ai_btn.configure(text="Отправить", width=90)
        self.assistant_box.configure(height=72)
        self.assistant_box.delete("1.0", "end")
        self.assistant_box.insert(
            "1.0",
            "Подсказка появится здесь во время встречи или после вашего вопроса.",
        )
        self.new_case_btn.configure(state="disabled")
        self.status_label.pack_forget()

    @staticmethod
    def _walk_widgets(widget):  # noqa: ANN001, ANN205
        for child in widget.winfo_children():
            yield child
            yield from MeetingBridgeApp._walk_widgets(child)

    def _show_activity(self, text: str) -> None:
        self.status_label.configure(text=text)
        if not self.status_label.winfo_manager():
            self.status_label.pack(anchor="w", padx=20, before=self.warn_label)

    def _hide_activity(self) -> None:
        if self.status_label.winfo_manager():
            self.status_label.pack_forget()

    def _show_assistant(self, text: str) -> None:
        if (text or "").strip():
            self.assistant_box.configure(height=165)
        super()._show_assistant(text)

    def _toggle_settings(self) -> None:
        """Opening settings also re-scans Windows audio after a hot-plug."""
        super()._toggle_settings()
        if self._settings_open and not self._meeting_active and not self._busy:
            self.refresh_devices()

    def start_session(self) -> None:
        """Give newly connected headphones one automatic re-scan before start."""
        mic = self.mic_combo.get().strip()
        speaker = self.speaker_combo.get().strip()
        if mic in ("", "—") or speaker in ("", "—") or "подключите" in speaker.casefold():
            self.refresh_devices()
        super().start_session()

    def _on_started(self, status: dict) -> None:
        super()._on_started(status)
        if status.get("state") == "listening":
            self.new_case_btn.configure(state="normal")
            self._show_activity("Слушаю встречу")

    def _on_stopped(self, status: dict) -> None:
        super()._on_stopped(status)
        self.new_case_btn.configure(state="disabled")
        self._show_activity("Встреча завершена")

    def ask_ai_reply(self) -> None:
        was_busy = self._busy or self._auto_busy
        super().ask_ai_reply()
        if not was_busy and self._busy:
            self._show_activity("1С Аналитик готовит ответ…")

    def _on_ai_ok(self, reply: str, path) -> None:  # noqa: ANN001
        super()._on_ai_ok(reply, path)
        if self._meeting_active:
            self._show_activity("Слушаю встречу")
        elif not self._finalized:
            self._hide_activity()

    def _on_ai_fail(self, exc: Exception) -> None:
        super()._on_ai_fail(exc)
        if self._meeting_active:
            self._show_activity("Слушаю встречу")
        elif not self._finalized:
            self._hide_activity()

    def _on_auto_ok(self, reply, path, peer_line: str) -> None:  # noqa: ANN001
        super()._on_auto_ok(reply, path, peer_line)
        if self._meeting_active:
            self._show_activity("Слушаю встречу")

    def _on_auto_fail(self, exc: Exception, peer_line: str) -> None:
        super()._on_auto_fail(exc, peer_line)
        if self._meeting_active:
            self._show_activity("Слушаю встречу")

    def _schedule_poll(self) -> None:
        super()._schedule_poll()
        state = MANAGER.status().get("state", "idle")
        if state == "listening":
            if self._auto_busy:
                self._show_activity("1С Аналитик анализирует реплику…")
            elif self._busy:
                self._show_activity("1С Аналитик готовит ответ…")
            else:
                self._show_activity("Слушаю встречу")
        elif self._finalized:
            self._show_activity("Встреча завершена")
        elif self._busy or self._auto_busy:
            self._show_activity("1С Аналитик готовит ответ…")
        else:
            self._hide_activity()


def main() -> None:
    legacy.ensure_project_cwd()
    MeetingBridgeApp().mainloop()
