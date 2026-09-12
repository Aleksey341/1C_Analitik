"""Runtime-safe entry point and final user-facing polish for 1C Analitik UX v2."""
from __future__ import annotations

import customtkinter as ctk

from meeting_bridge import gui as legacy
from meeting_bridge import gui_v2
from meeting_bridge.config import load_config
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
        self.clear_btn = ctk.CTkButton(
            self.new_case_btn.master,
            text="Очистить",
            width=95,
            height=42,
            fg_color=("gray74", "gray30"),
            command=self.clear_transcript_and_hint,
        )
        self.clear_btn.pack(side="left", padx=(6, 0))
        self.status_label.pack_forget()

        self.audio_health_label = ctk.CTkLabel(
            self,
            text="",
            justify="left",
            font=ctk.CTkFont(size=12, weight="bold"),
        )

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

    def clear_transcript_and_hint(self) -> None:
        """Clear the current live transcript and assistant hint, keeping capture alive."""
        if self._busy or self._auto_busy:
            self.warn_label.configure(
                text="Дождитесь завершения текущего ответа 1С Аналитика, затем очистите окно."
            )
            return

        path = legacy.ROOT / load_config().transcript_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        except OSError as exc:
            self.warn_label.configure(text=f"Не удалось очистить стенограмму: {exc}")
            return

        self.transcript.delete("1.0", "end")
        self.assistant_box.configure(height=72)
        self.assistant_box.delete("1.0", "end")
        self._auto_watcher.reset()
        self._topic_types = frozenset()
        self._last_topic_block = ""
        self._topic_shift_pending = False
        self.warn_label.configure(text="Стенограмма и подсказка очищены.")

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
            self._render_audio_health(status)

    def _on_stopped(self, status: dict) -> None:
        super()._on_stopped(status)
        self.new_case_btn.configure(state="disabled")
        self._show_activity("Встреча завершена")
        self._hide_audio_health()

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

    def _show_audio_health(self, text: str, *, ok: bool) -> None:
        self.audio_health_label.configure(
            text=text,
            text_color=("#2e7d32", "#7bd88f") if ok else ("#9a4b16", "#f0a15e"),
        )
        if not self.audio_health_label.winfo_manager():
            self.audio_health_label.pack(anchor="w", padx=20, pady=(0, 2), before=self.warn_label)

    def _hide_audio_health(self) -> None:
        if self.audio_health_label.winfo_manager():
            self.audio_health_label.pack_forget()

    def _render_audio_health(self, status: dict) -> None:
        health = status.get("audio_health") or {}
        if not health:
            self._show_audio_health("Проверяю поступление звука…", ok=False)
            return

        mic = health.get("Я") or {}
        peer = health.get("Собеседник") or {}
        mic_chunks = int(mic.get("chunks") or 0)
        peer_chunks = int(peer.get("chunks") or 0)
        if min(mic_chunks, peer_chunks) < 5:
            self._show_audio_health("Проверяю поступление звука…", ok=False)
            return

        mic_ok = bool(mic.get("has_signal"))
        peer_ok = bool(peer.get("has_signal"))
        mic_text = "сигнал есть" if mic_ok else "нет сигнала"
        peer_text = "сигнал есть" if peer_ok else "нет сигнала"
        self._show_audio_health(
            f"🎤 Микрофон: {mic_text}   |   🔊 Собеседник: {peer_text}",
            ok=mic_ok and peer_ok,
        )

    def _schedule_poll(self) -> None:
        super()._schedule_poll()
        status = MANAGER.status()
        state = status.get("state", "idle")
        error = status.get("error")

        if state == "listening":
            self._render_audio_health(status)
            if self._auto_busy:
                self._show_activity("1С Аналитик анализирует реплику…")
            elif self._busy:
                self._show_activity("1С Аналитик готовит ответ…")
            else:
                self._show_activity("Слушаю встречу")
        elif state == "error":
            self._show_activity("Ошибка захвата звука")
            self._render_audio_health(status)
            if error:
                self.warn_label.configure(text=f"Ошибка звука: {error}")
        elif self._finalized:
            self._show_activity("Встреча завершена")
            self._hide_audio_health()
        elif self._busy or self._auto_busy:
            self._show_activity("1С Аналитик готовит ответ…")
            self._hide_audio_health()
        else:
            self._hide_activity()
            self._hide_audio_health()


def main() -> None:
    legacy.ensure_project_cwd()
    MeetingBridgeApp().mainloop()
