"""User-first autonomous UI for 1C Analitik."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tkinter import messagebox
import sys
import threading

import customtkinter as ctk

from meeting_bridge import gui as legacy
from meeting_bridge.config import load_config, model_files_ready, save_config
from meeting_bridge.documents import read_dialogue_lines, save_dialogue_copy
from meeting_bridge.documents_v2 import build_protocol, extract_protocol_sections
from meeting_bridge.llm_client import ask_auto_reply, ask_meeting_reply, resolve_api_key
from meeting_bridge.session import MANAGER
from meeting_bridge.skills import infer_task_types
from meeting_bridge.updater import download_installer, fetch_latest_release, is_newer, launch_installer
from meeting_bridge.ux_logic import readiness_summary, should_suggest_topic_shift
from meeting_bridge.writer import iter_dialogue_blocks, read_recent_dialogue


def _root() -> Path:
    return legacy.ROOT


_RESPONSE_STYLE = """
Если текущий запрос не требует строгого формата, начинай с «Что сказать сейчас»:
2-4 коротких предложения для живого созвона. Затем дай «Разбор», «Что проверить
в 1С» и при необходимости «Что уточнить». Не выдумывай объекты 1С, цифры и
доказательства. Явный формат пользователя имеет приоритет над этой структурой.
""".strip()


class MeetingBridgeApp(legacy.MeetingBridgeApp):
    def __init__(self) -> None:
        self._meeting_active = False
        self._settings_open = False
        self._finalized = False
        self._last_protocol: Path | None = None
        self._topic_types: frozenset[str] = frozenset()
        self._last_topic_block = ""
        self._topic_shift_pending = False
        self._update_release = None
        super().__init__()
        self.title("1С Аналитик")
        self.minsize(760, 620)

    # ---------- UI ----------
    def _build(self) -> None:
        self.configure(fg_color=("#f4f6f8", "#0f141d"))
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 4))
        col = ctk.CTkFrame(header, fg_color="transparent")
        col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col, text="1С Аналитик", font=ctk.CTkFont(size=25, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(col, text="Слушает встречу, фиксирует и подсказывает.", text_color=("gray35", "gray70")).pack(anchor="w")
        self.settings_btn = ctk.CTkButton(header, text="⚙ Настройки", width=115, fg_color=("gray78", "gray28"), command=self._toggle_settings)
        self.settings_btn.pack(side="right")

        self.readiness_label = ctk.CTkLabel(self, text="Проверяем готовность…", font=ctk.CTkFont(size=13, weight="bold"))
        self.readiness_label.pack(anchor="w", padx=20, pady=(2, 8))

        topic = ctk.CTkFrame(self, fg_color="transparent")
        topic.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(topic, text="Тема встречи").pack(side="left", padx=(2, 8))
        self.title_entry = ctk.CTkEntry(topic, placeholder_text="Например: закрытие месяца / сверка / НДС")
        self.title_entry.pack(side="left", fill="x", expand=True)
        self._enable_clipboard(self.title_entry)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 6))
        self.session_btn = ctk.CTkButton(actions, text="Начать встречу", height=42, font=ctk.CTkFont(size=15, weight="bold"), command=self._toggle_meeting)
        self.session_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._session_fg = self.session_btn.cget("fg_color")
        self._session_hover = self.session_btn.cget("hover_color")
        self.start_btn = self.session_btn
        self.new_case_btn = ctk.CTkButton(actions, text="Новая тема", width=115, height=42, fg_color=("gray74", "gray30"), command=self.start_new_case)
        self.new_case_btn.pack(side="left")

        self.status_label = ctk.CTkLabel(self, text="Готов к работе", font=ctk.CTkFont(size=13, weight="bold"))
        self.status_label.pack(anchor="w", padx=20)
        self.warn_label = ctk.CTkLabel(self, text="", text_color=("#9a4b16", "#f0a15e"), justify="left", wraplength=840)
        self.warn_label.pack(anchor="w", padx=20, pady=(0, 6))

        self.settings_frame = ctk.CTkFrame(self)
        self._build_settings()

        ai = ctk.CTkFrame(self, border_width=1, border_color="#c45c26")
        ai.pack(fill="x", padx=16, pady=(4, 8))
        ctk.CTkLabel(ai, text="Подсказка 1С Аналитика", font=ctk.CTkFont(size=15, weight="bold"), text_color="#c45c26").pack(anchor="w", padx=12, pady=(9, 3))
        self.assistant_box = ctk.CTkTextbox(ai, height=145, wrap="word")
        self.assistant_box.pack(fill="x", padx=12, pady=(3, 11))
        self.assistant_box.insert("1.0", "Здесь появится короткий ответ для созвона и подробный разбор.")
        self._lock_readonly(self.assistant_box)
        self._enable_clipboard(self.assistant_box, allow_paste=False)

        ask = ctk.CTkFrame(self, fg_color="transparent")
        ask.pack(fill="x", padx=16, pady=(0, 8))
        self.ai_question = ctk.CTkEntry(ask, placeholder_text="Спросить 1С Аналитика…")
        self.ai_question.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.ai_question.bind("<Return>", lambda _e: self._ask_from_entry())
        self._enable_clipboard(self.ai_question)
        self.ai_btn = ctk.CTkButton(ask, text="Спросить ИИ", width=110, command=self._ask_from_entry)
        self.ai_btn.pack(side="left")

        ctk.CTkLabel(self, text="Стенограмма встречи", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=18)
        self.transcript = ctk.CTkTextbox(self, wrap="word")
        self.transcript.pack(fill="both", expand=True, padx=16, pady=(3, 12))
        self._configure_transcript_tags()
        self._lock_readonly(self.transcript)
        self._enable_clipboard(self.transcript, allow_paste=False)

        self.artifacts_frame = ctk.CTkFrame(self)
        self.artifact_text = ctk.CTkLabel(self.artifacts_frame, text="", justify="left")
        self.artifact_text.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        ctk.CTkButton(self.artifacts_frame, text="Открыть протокол", width=120, command=self._open_protocol).pack(side="right", padx=(4, 8), pady=8)
        self.open_folder_btn = ctk.CTkButton(self.artifacts_frame, text="Папка", width=75, fg_color=("gray74", "gray30"), command=self.open_archive_folder)
        self.open_folder_btn.pack(side="right", padx=4, pady=8)

        self.auto_reply_var = ctk.BooleanVar(value=True)
        self.spoken_mode_var = ctk.BooleanVar(value=False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_settings(self) -> None:
        f = self.settings_frame
        ctk.CTkLabel(f, text="Настройки звука", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 5))
        ctk.CTkLabel(f, text="Микрофон").grid(row=1, column=0, sticky="w", padx=12, pady=5)
        self.mic_combo = ctk.CTkComboBox(f, values=["—"], command=lambda _v: self._persist_devices())
        self.mic_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f, text="Звук собеседника").grid(row=2, column=0, sticky="w", padx=12, pady=5)
        self.speaker_combo = ctk.CTkComboBox(f, values=["—"], command=lambda _v: self._persist_devices())
        self.speaker_combo.grid(row=2, column=1, sticky="ew", padx=6, pady=5)
        self.refresh_btn = ctk.CTkButton(f, text="Обновить устройства", width=140, fg_color=("gray74", "gray30"), command=self.refresh_devices)
        self.refresh_btn.grid(row=1, column=2, rowspan=2, padx=(6, 12), pady=5)
        self.auto_reply_check = ctk.CTkCheckBox(f, text="Автоматически подсказывать после реплики", variable=self.auto_reply_var, command=self._on_auto_reply_toggle)
        self.auto_reply_check.grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 4))
        self.model_btn = ctk.CTkButton(f, text="Распознавание речи готово", width=210, state="disabled", fg_color=("gray74", "gray30"), command=self.download_model)
        self.model_btn.grid(row=4, column=0, columnspan=2, sticky="w", padx=12, pady=(5, 10))
        self.update_btn = ctk.CTkButton(f, text="Обновлений нет", width=150, state="disabled", fg_color=("gray74", "gray30"), command=self._install_update)
        self.update_btn.grid(row=4, column=2, sticky="e", padx=(6, 12), pady=(5, 10))
        f.grid_columnconfigure(1, weight=1)

    def _toggle_settings(self) -> None:
        self._settings_open = not self._settings_open
        if self._settings_open:
            self.settings_frame.pack(fill="x", padx=16, pady=(0, 8), after=self.warn_label)
            self.settings_btn.configure(text="Скрыть настройки")
        else:
            self.settings_frame.pack_forget()
            self.settings_btn.configure(text="⚙ Настройки")

    def refresh_devices(self) -> None:
        super().refresh_devices()
        self._persist_devices()

    def _persist_devices(self) -> None:
        mic = self.mic_combo.get().strip()
        speaker = self.speaker_combo.get().strip()
        if mic not in ("", "—") and speaker not in ("", "—"):
            save_config(mic_device=mic, speaker_device=speaker)
        self._update_readiness()

    def _update_readiness(self) -> None:
        try:
            cfg = load_config()
            model_ok = model_files_ready(_root() / cfg.model_dir)
            mic_ok = self.mic_combo.get().strip() not in ("", "—")
            speaker_ok = self.speaker_combo.get().strip() not in ("", "—")
            ai_ok = bool(resolve_api_key(cfg.llm))
        except Exception:
            return
        ready, text = readiness_summary(mic_ready=mic_ok, speaker_ready=speaker_ok, model_ready=model_ok, ai_ready=ai_ok)
        self.readiness_label.configure(text=text, text_color=("#2e7d32", "#7bd88f") if ready else ("#9a4b16", "#f0a15e"))
        self.model_btn.configure(state="disabled" if model_ok else "normal", text="Распознавание речи готово" if model_ok else "Восстановить распознавание речи")

    def _on_auto_reply_toggle(self) -> None:
        enabled = bool(self.auto_reply_var.get())
        if enabled and not resolve_api_key(load_config().llm):
            self.auto_reply_var.set(False)
            save_config(llm_auto_reply=False)
            self.warn_label.configure(text="Автоподсказки недоступны: сначала войдите по коду доступа.")
            return
        save_config(llm_auto_reply=enabled)
        self._auto_watcher.reset()
        self.warn_label.configure(text="Автоподсказки включены." if enabled else "Автоподсказки выключены. Используйте «Спросить ИИ».")

    def _toggle_meeting(self) -> None:
        if MANAGER.status().get("state") == "listening" or self._meeting_active:
            self.stop_session()
        else:
            self._finalized = False
            self.start_session()

    def _on_started(self, status: dict) -> None:
        super()._on_started(status)
        if status.get("state") == "listening":
            self._meeting_active = True
            self.session_btn.configure(text="Завершить встречу", fg_color=("#b23a31", "#9b332c"), hover_color=("#9e312a", "#842b26"))
            self.status_label.configure(text="Слушаю встречу")
        self._update_readiness()

    def _on_stopped(self, status: dict) -> None:
        super()._on_stopped(status)
        self._meeting_active = False
        self.session_btn.configure(text="Начать встречу", fg_color=self._session_fg, hover_color=self._session_hover)
        self.status_label.configure(text="Встреча завершена")
        self._finalize()

    def start_new_case(self) -> None:
        if self._busy or self._auto_busy:
            messagebox.showwarning("Новая тема", "Дождитесь завершения текущего ответа 1С Аналитика.", parent=self)
            return
        path = _root() / load_config().transcript_path
        try:
            self._append_dialogue_line("Система", "Новый кейс", path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Новая тема", str(exc), parent=self)
            return
        self._auto_watcher.reset()
        self.ai_question.delete(0, "end")
        self._topic_types = frozenset()
        self._last_topic_block = ""
        self._topic_shift_pending = False
        self.warn_label.configure(text="Новая тема: предыдущий AI-контекст отделён, стенограмма сохранена.")
        self._refresh_transcript()

    @staticmethod
    def _enhanced_llm(cfg):  # noqa: ANN001
        llm = cfg.llm
        return replace(llm, spoken_mode=False, system_prompt=llm.system_prompt + "\n\n" + _RESPONSE_STYLE, auto_system_prompt=llm.auto_system_prompt + "\n\n" + _RESPONSE_STYLE)

    def _ask_from_entry(self) -> None:
        if self._busy or self._auto_busy:
            return
        question = self.ai_question.get().strip()
        if not question:
            self.warn_label.configure(text="Введите вопрос для 1С Аналитика.")
            return
        path = _root() / load_config().transcript_path
        try:
            self._append_dialogue_line("Я", question, path)
        except Exception as exc:  # noqa: BLE001
            self.warn_label.configure(text=f"Не удалось добавить вопрос: {exc}")
            return
        self.ai_question.delete(0, "end")
        self._refresh_transcript()
        self.ask_ai_reply()

    def ask_ai_reply(self) -> None:
        if self._busy or self._auto_busy:
            return
        cfg = load_config()
        if not cfg.llm.enabled or not resolve_api_key(cfg.llm):
            self.warn_label.configure(text="Нет доступа к ИИ. Перезапустите приложение и введите код доступа.")
            return
        path = _root() / cfg.transcript_path
        dialogue = read_recent_dialogue(path, cfg.llm.max_context_lines)
        if not dialogue.strip():
            self.warn_label.configure(text="Пока нет реплик для анализа.")
            return
        self._busy = True
        self._mark_auto_answered_for_path(path)
        self._auto_watcher.in_flight = True
        self.ai_btn.configure(state="disabled")
        self.status_label.configure(text="1С Аналитик готовит ответ…")
        settings = self._enhanced_llm(cfg)

        def worker() -> None:
            try:
                reply = ask_meeting_reply(dialogue, settings, user_question="", spoken=False)
                self.after(0, lambda r=reply: self._on_ai_ok(r, path))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self._on_ai_fail(e))
        threading.Thread(target=worker, daemon=True).start()

    def _maybe_auto_reply(self) -> None:
        if self._busy or self._auto_busy or not bool(self.auto_reply_var.get()):
            return
        if MANAGER.status().get("state") != "listening":
            return
        cfg = load_config()
        if not cfg.llm.enabled or not cfg.llm.auto_reply or not resolve_api_key(cfg.llm):
            return
        path = _root() / cfg.transcript_path
        if not path.exists():
            return
        body = iter_dialogue_blocks(path.read_text(encoding="utf-8"))
        decision = self._auto_watcher.observe([b.splitlines()[0] if b else b for b in body], pause_sec=float(cfg.llm.auto_reply_pause_sec), reply_on_me=bool(cfg.llm.auto_reply_on_me))
        if not decision.should_request:
            return
        dialogue = "\n\n".join(body[-cfg.llm.max_context_lines :])
        peer = decision.peer_line
        self._auto_busy = True
        self.warn_label.configure(text="1С Аналитик анализирует последнюю реплику…")
        settings = self._enhanced_llm(cfg)

        def worker() -> None:
            try:
                reply = ask_auto_reply(dialogue, settings)
                self.after(0, lambda r=reply, p=peer: self._on_auto_ok(r, path, p))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc, p=peer: self._on_auto_fail(e, p))
        threading.Thread(target=worker, daemon=True).start()

    def _show_assistant(self, text: str) -> None:
        text = (text or "").strip()
        if text:
            self.assistant_box.delete("1.0", "end")
            self.assistant_box.insert("1.0", text)
            self.assistant_box.see("1.0")

    def _on_ai_ok(self, reply: str, path: Path) -> None:
        self._show_assistant(reply)
        super()._on_ai_ok(reply, path)

    def _on_auto_ok(self, reply: str | None, path: Path, peer_line: str) -> None:
        if reply:
            self._show_assistant(reply)
        super()._on_auto_ok(reply, path, peer_line)

    def _check_topic_shift(self) -> None:
        if not self._meeting_active:
            return
        try:
            path = _root() / load_config().transcript_path
            blocks = iter_dialogue_blocks(path.read_text(encoding="utf-8")) if path.exists() else []
            human = [b for b in blocks if self._block_role(b) in {"Я", "Собеседник"}]
            if not human or human[-1] == self._last_topic_block:
                return
            self._last_topic_block = human[-1]
            current = infer_task_types(human[-1])
            if not current:
                return
            if not self._topic_shift_pending and should_suggest_topic_shift(self._topic_types, current):
                self._topic_shift_pending = True
                self.warn_label.configure(text="Похоже, началась другая тема. Нажмите «Новая тема», чтобы ИИ не смешивал контексты.")
            elif not self._topic_shift_pending:
                self._topic_types = frozenset(set(self._topic_types).union(current))
        except Exception:  # noqa: BLE001
            pass

    def _finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True
        cfg = load_config()
        src = _root() / cfg.transcript_path
        if not src.exists() or not iter_dialogue_blocks(src.read_text(encoding="utf-8")):
            return
        try:
            save_dialogue_copy(src, _root() / cfg.archive_dir, title=self._meeting_title())
            self._last_protocol = build_protocol(src, _root() / cfg.archive_dir, title=self._meeting_title() or "Протокол встречи по 1С")
            sections = extract_protocol_sections(read_dialogue_lines(src))
        except Exception as exc:  # noqa: BLE001
            self.warn_label.configure(text=f"Встреча сохранена, но протокол не сформирован: {exc}")
            return
        self.artifact_text.configure(text=f"✓ Стенограмма  ✓ Протокол   Решений: {len(sections['decisions'])}   Задач: {len(sections['actions'])}   Вопросов: {len(sections['questions'])}")
        self.artifacts_frame.pack(fill="x", padx=16, pady=(0, 12), before=self.transcript)
        self.warn_label.configure(text="Встреча завершена. Стенограмма и протокол сохранены автоматически.")

    def _open_protocol(self) -> None:
        if self._last_protocol and self._last_protocol.exists():
            self._open_path(self._last_protocol)

    def _check_updates(self) -> None:
        if not getattr(sys, "frozen", False):
            return
        def worker() -> None:
            release = fetch_latest_release()
            if release and is_newer(release.version):
                self.after(0, lambda r=release: self._show_update(r))
        threading.Thread(target=worker, daemon=True).start()

    def _show_update(self, release) -> None:  # noqa: ANN001
        self._update_release = release
        self.update_btn.configure(state="normal", text=f"Обновить до {release.version}")
        self.warn_label.configure(text=f"Доступна версия {release.version}. Обновить можно после встречи в настройках.")

    def _install_update(self) -> None:
        if self._meeting_active:
            self.warn_label.configure(text="Завершите встречу перед обновлением.")
            return
        release = self._update_release
        if release is None:
            return
        self.update_btn.configure(state="disabled", text="Скачиваем обновление…")
        def worker() -> None:
            try:
                launch_installer(download_installer(release))
                self.after(0, self.destroy)
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self._update_failed(e))
        threading.Thread(target=worker, daemon=True).start()

    def _update_failed(self, exc: Exception) -> None:
        self.update_btn.configure(state="normal", text=f"Обновить до {self._update_release.version}" if self._update_release else "Обновить")
        self.warn_label.configure(text=f"Не удалось установить обновление: {exc}")

    def _bootstrap(self) -> None:
        super()._bootstrap()
        self.spoken_mode_var.set(False)
        save_config(llm_spoken_mode=False)
        self._update_readiness()
        self.after(1200, self._check_updates)

    def _schedule_poll(self) -> None:
        super()._schedule_poll()
        self._check_topic_shift()
        if not self._busy and not self._auto_busy:
            state = MANAGER.status().get("state", "idle")
            self.status_label.configure(text="Слушаю встречу" if state == "listening" else "Готов к работе")

    def _on_close(self) -> None:
        if MANAGER.status().get("state") == "listening":
            try:
                MANAGER.stop()
                self._meeting_active = False
                self._finalize()
            except Exception:  # noqa: BLE001
                pass
        super()._on_close()


def main() -> None:
    legacy.ensure_project_cwd()
    MeetingBridgeApp().mainloop()
