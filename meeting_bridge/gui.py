"""Desktop GUI for Meeting Bridge — configure devices and start/stop capture."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk

from meeting_bridge.auto_reply import AutoReplyWatcher, latest_trigger_line
from meeting_bridge.config import load_config, model_files_ready, save_config
from meeting_bridge.devices import list_audio_devices
from meeting_bridge.documents import build_protocol, save_dialogue_copy
from meeting_bridge.llm_client import ask_auto_reply, ask_meeting_reply, resolve_api_key
from meeting_bridge.session import MANAGER
from meeting_bridge.writer import (
    append_transcript_line,
    iter_dialogue_blocks,
    read_recent_dialogue,
)

_BLOCK_ROLE_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s+([^:]+):")

ROOT = Path(__file__).resolve().parent.parent


def ensure_project_cwd() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


class MeetingBridgeApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ensure_project_cwd()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Meeting Bridge")
        self.minsize(720, 560)
        self.after(50, self._place_on_primary)
        self.after(100, self._force_front)

        self._mic_map: dict[str, dict] = {}
        self._loop_map: dict[str, dict] = {}
        self._poll_after: str | None = None
        self._busy = False
        self._auto_watcher = AutoReplyWatcher()
        self._auto_busy = False

        self._build()
        self.after(100, self._bootstrap)

    def _place_on_primary(self) -> None:
        self.update_idletasks()
        try:
            import ctypes

            user32 = ctypes.windll.user32
            sw = int(user32.GetSystemMetrics(0))
            sh = int(user32.GetSystemMetrics(1))
            w, h = 900, 700
            x = max(40, (sw - w) // 2)
            y = max(40, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.update_idletasks()
            hwnd_top = ctypes.windll.user32.GetParent(int(self.winfo_id()))
            if hwnd_top == 0:
                hwnd_top = int(self.winfo_id())
            ctypes.windll.user32.MoveWindow(hwnd_top, x, y, w, h, True)
        except Exception:  # noqa: BLE001
            self.geometry("900x700+80+60")

    def _force_front(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(1000, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except Exception:  # noqa: BLE001
            pass

    def _build(self) -> None:
        pad = {"padx": 12, "pady": 6}

        header = ctk.CTkLabel(
            self,
            text="Meeting Bridge",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        header.pack(anchor="w", padx=16, pady=(16, 4))

        hint = ctk.CTkLabel(
            self,
            text="Можно диктовать (Старт) или вставить вопрос в поле ниже → «В диалог» / «Ответ ИИ».",
            text_color=("gray30", "gray70"),
            justify="left",
        )
        hint.pack(anchor="w", padx=16, pady=(0, 4))

        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkLabel(title_row, text="Тема встречи").pack(side="left", padx=(4, 8))
        self.title_entry = ctk.CTkEntry(
            title_row, placeholder_text="Например: Еженедельный статус", width=420
        )
        self.title_entry.pack(side="left", fill="x", expand=True, padx=4)

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(form, text="Микрофон (Я)").grid(row=0, column=0, sticky="w", **pad)
        self.mic_combo = ctk.CTkComboBox(form, values=["—"], width=520)
        self.mic_combo.grid(row=0, column=1, sticky="ew", **pad)

        ctk.CTkLabel(form, text="Собеседник (loopback)").grid(
            row=1, column=0, sticky="w", **pad
        )
        self.speaker_combo = ctk.CTkComboBox(form, values=["—"], width=520)
        self.speaker_combo.grid(row=1, column=1, sticky="ew", **pad)
        form.grid_columnconfigure(1, weight=1)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=4)

        self.refresh_btn = ctk.CTkButton(
            btns, text="Устройства", width=110, command=self.refresh_devices
        )
        self.refresh_btn.pack(side="left", padx=3)

        self.save_cfg_btn = ctk.CTkButton(
            btns, text="Сохранить настройки", width=150, command=self.save_devices
        )
        self.save_cfg_btn.pack(side="left", padx=3)

        self.start_btn = ctk.CTkButton(
            btns, text="Старт", width=90, command=self.start_session
        )
        self.start_btn.pack(side="left", padx=3)

        self.stop_btn = ctk.CTkButton(
            btns,
            text="Стоп",
            width=90,
            fg_color=("gray70", "gray35"),
            command=self.stop_session,
        )
        self.stop_btn.pack(side="left", padx=3)

        self.model_btn = ctk.CTkButton(
            btns, text="Модель STT", width=110, command=self.download_model
        )
        self.model_btn.pack(side="left", padx=3)

        docs = ctk.CTkFrame(self, fg_color="transparent")
        docs.pack(fill="x", padx=12, pady=(0, 4))

        self.save_dialog_btn = ctk.CTkButton(
            docs, text="Сохранить диалог", width=150, command=self.save_dialogue
        )
        self.save_dialog_btn.pack(side="left", padx=3)

        self.protocol_btn = ctk.CTkButton(
            docs, text="Сделать протокол", width=150, command=self.make_protocol
        )
        self.protocol_btn.pack(side="left", padx=3)

        self.open_folder_btn = ctk.CTkButton(
            docs, text="Папка сохранений", width=150, command=self.open_archive_folder
        )
        self.open_folder_btn.pack(side="left", padx=3)

        self.clear_btn = ctk.CTkButton(
            docs,
            text="Очистить окно",
            width=120,
            fg_color=("gray70", "gray35"),
            command=self.clear_view,
        )
        self.clear_btn.pack(side="left", padx=3)

        ai_row = ctk.CTkFrame(self, fg_color="transparent")
        ai_row.pack(fill="x", padx=12, pady=(4, 0))
        self.auto_reply_var = ctk.BooleanVar(value=False)
        self.auto_reply_check = ctk.CTkCheckBox(
            ai_row,
            text="Автоответ ИИ",
            variable=self.auto_reply_var,
            command=self._on_auto_reply_toggle,
            width=140,
        )
        self.auto_reply_check.pack(side="left", padx=(3, 8))
        self.spoken_mode_var = ctk.BooleanVar(value=False)
        self.spoken_mode_check = ctk.CTkCheckBox(
            ai_row,
            text="Вслух",
            variable=self.spoken_mode_var,
            command=self._on_spoken_mode_toggle,
            width=70,
        )
        self.spoken_mode_check.pack(side="left", padx=(0, 8))
        self.ai_question = ctk.CTkEntry(
            ai_row,
            placeholder_text="Вопрос к ИИ (необязательно): что ответить / разбор…",
        )
        self.ai_question.pack(side="left", fill="x", expand=True, padx=(3, 6))
        self.ai_btn = ctk.CTkButton(
            ai_row,
            text="Ответ ИИ",
            width=120,
            command=self.ask_ai_reply,
        )
        self.ai_btn.pack(side="left", padx=3)
        self.new_case_btn = ctk.CTkButton(
            ai_row,
            text="\u041d\u043e\u0432\u044b\u0439 \u043a\u0435\u0439\u0441",
            width=110,
            fg_color=("gray70", "gray35"),
            command=self.start_new_case,
        )
        self.new_case_btn.pack(side="left", padx=3)

        self.status_label = ctk.CTkLabel(
            self, text="Статус: стоп", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.status_label.pack(anchor="w", padx=16, pady=(4, 2))

        self.warn_label = ctk.CTkLabel(self, text="", text_color="#c45c26")
        self.warn_label.pack(anchor="w", padx=16)

        insert_hdr = ctk.CTkFrame(self, fg_color="transparent")
        insert_hdr.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(insert_hdr, text="Вставить в диалог").pack(side="left", padx=(4, 8))
        self.insert_role = ctk.CTkComboBox(
            insert_hdr, values=["Я", "Собеседник"], width=130
        )
        self.insert_role.set("Я")
        self.insert_role.pack(side="left", padx=3)
        self.insert_btn = ctk.CTkButton(
            insert_hdr,
            text="В диалог",
            width=100,
            command=lambda: self.insert_into_dialogue(),
        )
        self.insert_btn.pack(side="left", padx=3)
        self.insert_and_ask_btn = ctk.CTkButton(
            insert_hdr,
            text="В диалог + Ответ ИИ",
            width=150,
            command=lambda: self.insert_and_ask_ai(),
        )
        self.insert_and_ask_btn.pack(side="left", padx=3)
        self.paste_btn = ctk.CTkButton(
            insert_hdr,
            text="Из буфера",
            width=100,
            fg_color=("gray70", "gray35"),
            command=self.paste_clipboard_into_insert,
        )
        self.paste_btn.pack(side="left", padx=3)
        ctk.CTkLabel(
            insert_hdr,
            text="Ctrl+V / Ctrl+Enter",
            text_color=("gray40", "gray60"),
        ).pack(side="left", padx=8)

        self.insert_box = ctk.CTkTextbox(self, height=90, wrap="word")
        self.insert_box.pack(fill="x", padx=12, pady=(4, 0))
        self.insert_box.bind("<Control-Return>", self._on_insert_shortcut)
        self.insert_box.bind("<Control-KP_Enter>", self._on_insert_shortcut)
        self._enable_clipboard(self.insert_box)
        self._enable_clipboard(self.ai_question)
        self._enable_clipboard(self.title_entry)

        ctk.CTkLabel(self, text="Диалог встречи").pack(anchor="w", padx=16, pady=(8, 0))
        # state=normal: иначе на disabled Text не работает выделение и Ctrl+C.
        self.transcript = ctk.CTkTextbox(self, wrap="word")
        self.transcript.pack(fill="both", expand=True, padx=12, pady=(4, 16))
        self._configure_transcript_tags()
        self._lock_readonly(self.transcript)
        self._enable_clipboard(self.transcript, allow_paste=False)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bootstrap(self) -> None:
        self.refresh_devices()
        cfg = load_config()
        self.auto_reply_var.set(bool(cfg.llm.auto_reply))
        self.spoken_mode_var.set(bool(cfg.llm.spoken_mode))
        if not model_files_ready(cfg.model_dir):
            self.warn_label.configure(
                text="Модель STT не найдена — нажмите «Модель STT»."
            )
        self._schedule_poll()

    def _on_auto_reply_toggle(self) -> None:
        enabled = bool(self.auto_reply_var.get())
        save_config(llm_auto_reply=enabled)
        if not enabled:
            self._auto_watcher.reset()
            self.warn_label.configure(text="Автоответ ИИ выключен.")
            return
        if not resolve_api_key(load_config().llm):
            self.auto_reply_var.set(False)
            save_config(llm_auto_reply=False)
            messagebox.showwarning(
                "Автоответ",
                "Сначала укажите llm.api_key в config.yaml.",
            )
            return
        self.warn_label.configure(
            text="Автоответ включён: после реплики собеседника ИИ ответит сам (или SKIP)."
        )

    def _on_spoken_mode_toggle(self) -> None:
        enabled = bool(self.spoken_mode_var.get())
        save_config(llm_spoken_mode=enabled)
        if enabled:
            self.warn_label.configure(
                text="Режим «Вслух»: короткие реплики 2–4 предложения для созвона."
            )
        else:
            self.warn_label.configure(
                text="Полный разбор для аналитика 1С:ERP (можно писать «что ответить»)."
            )

    def refresh_devices(self) -> None:
        try:
            devices = list_audio_devices()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Устройства", f"Не удалось получить список:\n{exc}")
            return

        mic_names = [str(d["name"]) for d in devices.get("mic", [])]
        loop_names = [str(d["name"]) for d in devices.get("loopback", [])]
        self._mic_map = {str(d["name"]): d for d in devices.get("mic", [])}
        self._loop_map = {str(d["name"]): d for d in devices.get("loopback", [])}

        self.mic_combo.configure(values=mic_names or ["—"])
        self.speaker_combo.configure(values=loop_names or ["—"])

        cfg = load_config()
        self._select_combo(self.mic_combo, mic_names, cfg.mic_device)
        self._select_combo(self.speaker_combo, loop_names, cfg.speaker_device)

    @staticmethod
    def _select_combo(combo: ctk.CTkComboBox, names: list[str], preferred: str) -> None:
        if not names:
            combo.set("—")
            return
        if preferred:
            for name in names:
                if preferred.casefold() in name.casefold() or name.casefold() in preferred.casefold():
                    combo.set(name)
                    return

        def score(name: str) -> tuple:
            n = name.casefold()
            bad = (
                ("переназначение" in n)
                or ("remap" in n)
                or ("primary sound capture" in n)
                or ("altered" in n)
                or ("набор микрофонов" in n)
            )
            good = any(
                k in n
                for k in (
                    "headphone",
                    "headset",
                    "науш",
                    "микрофон",
                    "mic",
                    "honor",
                    "realtek",
                    "loopback",
                )
            )
            return (0 if bad else 1, 1 if good else 0, name)

        ranked = sorted(names, key=score, reverse=True)
        combo.set(ranked[0])

    def save_devices(self) -> None:
        mic = self.mic_combo.get().strip()
        speaker = self.speaker_combo.get().strip()
        if mic in ("", "—") or speaker in ("", "—"):
            messagebox.showwarning("Сохранить", "Выберите микрофон и loopback собеседника.")
            return
        save_config(mic_device=mic, speaker_device=speaker)
        self.warn_label.configure(text="Настройки устройств сохранены.")

    def start_session(self) -> None:
        if self._busy:
            return
        mic = self.mic_combo.get().strip()
        speaker = self.speaker_combo.get().strip()
        if mic in ("", "—") or speaker in ("", "—"):
            messagebox.showwarning("Старт", "Выберите микрофон и устройство собеседника.")
            return
        cfg = load_config()
        if not model_files_ready(cfg.model_dir):
            messagebox.showwarning(
                "Модель",
                "Сначала скачайте модель распознавания речи («Модель STT»).",
            )
            return

        save_config(mic_device=mic, speaker_device=speaker)
        self._busy = True
        self.status_label.configure(text="Статус: загрузка модели…")
        self.start_btn.configure(state="disabled")
        self.warn_label.configure(text="")

        def worker() -> None:
            try:
                self.after(
                    0,
                    lambda: self.status_label.configure(text="Статус: загрузка модели…"),
                )
                cfg2 = load_config()
                resolved_mic = self._mic_map.get(mic)
                resolved_loop = self._loop_map.get(speaker)
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text="Статус: открытие устройств…"
                    ),
                )
                status = MANAGER.start(
                    cfg2,
                    mic_override=mic,
                    speaker_override=speaker,
                    resolved_mic=resolved_mic,
                    resolved_loop=resolved_loop,
                )
                self.after(0, lambda s=status: self._on_started(s))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self._on_start_failed(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_started(self, status: dict) -> None:
        self._busy = False
        self.start_btn.configure(state="normal")
        state = status.get("state", "listening")
        labels = {"listening": "слушаю", "idle": "стоп", "error": "ошибка"}
        self.status_label.configure(text=f"Статус: {labels.get(state, state)}")
        warning = status.get("warning") or ""
        err = status.get("error")
        if err:
            self.warn_label.configure(text=f"Ошибка: {err}")
        else:
            self.warn_label.configure(
                text=warning
                or "Говорите с паузами — реплики появляются в окне диалога."
            )
        self._auto_watcher.reset()
        self._refresh_transcript()

    def _on_start_failed(self, exc: Exception) -> None:
        self._busy = False
        self.start_btn.configure(state="normal")
        self.status_label.configure(text="Статус: ошибка")
        self.warn_label.configure(text=str(exc))
        messagebox.showerror(
            "Старт",
            "Не удалось начать захват.\n\n"
            f"{exc}\n\n"
            "Для собеседника нужен Loopback (наушники/динамики).\n"
            "Микрофон: Realtek или гарнитура — не «Набор микрофонов» / "
            "Altered Virtual Audio, если пишет Invalid number of channels.",
        )

    def stop_session(self) -> None:
        if self._busy:
            return
        self._busy = True

        def worker() -> None:
            try:
                status = MANAGER.stop()
                self.after(0, lambda: self._on_stopped(status))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self._on_stop_failed(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_stopped(self, status: dict) -> None:
        self._busy = False
        self._auto_watcher.reset()
        self.status_label.configure(text=f"Статус: {status.get('state', 'idle')}")
        self._refresh_transcript()

    def _on_stop_failed(self, exc: Exception) -> None:
        self._busy = False
        messagebox.showerror("Стоп", str(exc))

    def download_model(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.status_label.configure(text="Статус: скачивание модели…")
        self.model_btn.configure(state="disabled")

        def worker() -> None:
            try:
                script = ROOT / "scripts" / "download_model.py"
                proc = subprocess.run(
                    [sys.executable, str(script)],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode != 0:
                    detail = (proc.stderr or proc.stdout or "").strip()
                    raise RuntimeError(detail or "Скачивание завершилось с ошибкой")
                self.after(0, self._on_model_ok)
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self._on_model_fail(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_model_ok(self) -> None:
        self._busy = False
        self.model_btn.configure(state="normal")
        self.status_label.configure(text="Статус: модель готова")
        self.warn_label.configure(text="")
        messagebox.showinfo("Модель", "Модель успешно скачана.")

    def _on_model_fail(self, exc: Exception) -> None:
        self._busy = False
        self.model_btn.configure(state="normal")
        self.status_label.configure(text="Статус: ошибка модели")
        messagebox.showerror("Модель", str(exc))

    def _meeting_title(self) -> str:
        return self.title_entry.get().strip()

    def save_dialogue(self) -> None:
        cfg = load_config()
        src = ROOT / cfg.transcript_path
        if not src.exists() or not iter_dialogue_blocks(src.read_text(encoding="utf-8")):
            messagebox.showwarning("Диалог", "Пока нет реплик для сохранения.")
            return
        try:
            dest = save_dialogue_copy(
                src, ROOT / cfg.archive_dir, title=self._meeting_title()
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Сохранить диалог", str(exc))
            return

        also = filedialog.asksaveasfilename(
            title="Дополнительно сохранить копию как…",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Все файлы", "*.*")],
            initialfile=dest.name,
        )
        if also:
            Path(also).write_text(dest.read_text(encoding="utf-8"), encoding="utf-8")

        self.warn_label.configure(text=f"Диалог сохранён: {dest}")
        if messagebox.askyesno("Диалог сохранён", f"Файл:\n{dest}\n\nОткрыть?"):
            self._open_path(dest)

    def make_protocol(self) -> None:
        cfg = load_config()
        src = ROOT / cfg.transcript_path
        if not src.exists() or not iter_dialogue_blocks(src.read_text(encoding="utf-8")):
            messagebox.showwarning("Протокол", "Сначала запишите диалог (Старт → речь → Стоп).")
            return
        try:
            dest = build_protocol(
                src,
                ROOT / cfg.archive_dir,
                title=self._meeting_title() or "Протокол совещания",
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Протокол", str(exc))
            return

        self.warn_label.configure(text=f"Протокол сохранён: {dest.name}")
        if messagebox.askyesno(
            "Протокол готов",
            f"Файл создан:\n{dest}\n\n"
            "Повестка, решения и поручения заполнены автоматически из диалога.\n"
            "Проверьте формулировки — STT может ошибаться.\n\n"
            "Открыть протокол?",
        ):
            self._open_path(dest)

    def open_archive_folder(self) -> None:
        cfg = load_config()
        folder = ROOT / cfg.archive_dir
        folder.mkdir(parents=True, exist_ok=True)
        self._open_path(folder)

    def start_new_case(self) -> None:
        """Create a persistent AI-context boundary without deleting the transcript."""
        if self._busy or self._auto_busy:
            messagebox.showwarning(
                "\u041d\u043e\u0432\u044b\u0439 \u043a\u0435\u0439\u0441",
                "\u0414\u043e\u0436\u0434\u0438\u0442\u0435\u0441\u044c "
                "\u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0438\u044f "
                "\u0442\u0435\u043a\u0443\u0449\u0435\u0433\u043e "
                "\u0437\u0430\u043f\u0440\u043e\u0441\u0430 \u043a \u0418\u0418.",
            )
            return

        cfg = load_config()
        path = ROOT / cfg.transcript_path

        try:
            self._append_dialogue_line(
                "\u0421\u0438\u0441\u0442\u0435\u043c\u0430",
                "\u041d\u043e\u0432\u044b\u0439 \u043a\u0435\u0439\u0441",
                path,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "\u041d\u043e\u0432\u044b\u0439 \u043a\u0435\u0439\u0441",
                str(exc),
            )
            return

        self._auto_watcher.reset()

        try:
            self.ai_question.delete(0, "end")
        except Exception:  # noqa: BLE001
            pass

        self.warn_label.configure(
            text=(
                "\u041d\u043e\u0432\u044b\u0439 \u043a\u0435\u0439\u0441: "
                "\u043f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0439 "
                "\u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u0418\u0418 "
                "\u043e\u0442\u0441\u0435\u0447\u0451\u043d, "
                "\u0441\u0442\u0435\u043d\u043e\u0433\u0440\u0430\u043c\u043c\u0430 "
                "\u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0430."
            )
        )
        self._refresh_transcript()

    def clear_view(self) -> None:
        self.transcript.delete("1.0", "end")

    def _on_insert_shortcut(self, _event=None):  # noqa: ANN001
        self.insert_into_dialogue()
        return "break"

    @staticmethod
    def _clipboard_target(widget):  # noqa: ANN001
        if hasattr(widget, "_textbox"):
            return widget._textbox
        if hasattr(widget, "_entry"):
            return widget._entry
        return widget

    def _lock_readonly(self, widget) -> None:  # noqa: ANN001
        """Allow selection/copy but block typing into transcript."""
        tgt = self._clipboard_target(widget)

        def block_edit(event):  # noqa: ANN001
            if int(getattr(event, "state", 0)) & 0x4:  # Control
                return None
            if str(getattr(event, "keysym", "")) in {
                "Left",
                "Right",
                "Up",
                "Down",
                "Home",
                "End",
                "Prior",
                "Next",
                "Shift_L",
                "Shift_R",
                "Control_L",
                "Control_R",
                "Alt_L",
                "Alt_R",
                "Escape",
                "Tab",
            }:
                return None
            return "break"

        tgt.bind("<Key>", block_edit)

    def _clipboard_get(self) -> str:
        try:
            self.update_idletasks()
        except tk.TclError:
            pass
        for typ in ("CF_UNICODETEXT", "UTF8_STRING", "STRING"):
            try:
                data = self.clipboard_get(type=typ)
                if data:
                    return str(data)
            except tk.TclError:
                continue
        try:
            data = self.clipboard_get()
            if data:
                return str(data)
        except tk.TclError:
            pass
        try:
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            CF_UNICODETEXT = 13
            if not user32.OpenClipboard(None):
                return ""
            try:
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    return ""
                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    return ""
                try:
                    return ctypes.wstring_at(ptr)
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
        except Exception:  # noqa: BLE001
            return ""

    def _clipboard_set(self, text: str) -> bool:
        if not text:
            return False
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            return True
        except tk.TclError:
            pass
        try:
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002
            data = text.encode("utf-16-le") + b"\x00\x00"
            if not user32.OpenClipboard(None):
                return False
            try:
                user32.EmptyClipboard()
                handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                if not handle:
                    return False
                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    return False
                try:
                    ctypes.memmove(ptr, data, len(data))
                finally:
                    kernel32.GlobalUnlock(handle)
                if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                    return False
                return True
            finally:
                user32.CloseClipboard()
        except Exception:  # noqa: BLE001
            return False

    def _paste_into_widget(self, widget, text: str | None = None) -> bool:  # noqa: ANN001
        data = text if text is not None else self._clipboard_get()
        if not data:
            return False
        tgt = self._clipboard_target(widget)
        try:
            if tgt.tag_ranges("sel"):
                tgt.delete("sel.first", "sel.last")
        except (tk.TclError, AttributeError):
            try:
                if bool(tgt.selection_present()):
                    tgt.delete("sel.first", "sel.last")
            except (tk.TclError, AttributeError):
                pass
        try:
            tgt.insert("insert", data)
        except tk.TclError:
            try:
                tgt.insert(tk.INSERT, data)
            except tk.TclError:
                return False
        try:
            tgt.focus_set()
        except tk.TclError:
            pass
        return True

    def _copy_from_widget(self, widget) -> bool:  # noqa: ANN001
        tgt = self._clipboard_target(widget)
        text = ""
        try:
            if tgt.tag_ranges("sel"):
                text = tgt.get("sel.first", "sel.last")
        except (tk.TclError, AttributeError):
            try:
                text = tgt.selection_get()
            except tk.TclError:
                text = ""
        if not text:
            return False
        return self._clipboard_set(text)

    def _select_all_widget(self, widget) -> None:  # noqa: ANN001
        tgt = self._clipboard_target(widget)
        try:
            if hasattr(widget, "_textbox"):
                tgt.tag_add("sel", "1.0", "end-1c")
                tgt.mark_set("insert", "1.0")
                tgt.see("insert")
            else:
                tgt.select_range(0, "end")
                tgt.icursor("end")
        except tk.TclError:
            pass

    def _enable_clipboard(self, widget, *, allow_paste: bool = True) -> None:  # noqa: ANN001
        """Ctrl+C/V on RU layout: keysyms are «с»/«м», bind by Windows keycode."""
        import time

        last_clip_at = [0.0]

        def do_paste(_event=None):  # noqa: ANN001
            if not allow_paste:
                return "break"
            now = time.monotonic()
            if now - last_clip_at[0] < 0.08:
                return "break"
            if self._paste_into_widget(widget):
                last_clip_at[0] = now
                return "break"
            return None

        def do_copy(_event=None):  # noqa: ANN001
            now = time.monotonic()
            if now - last_clip_at[0] < 0.08:
                return "break"
            if self._copy_from_widget(widget):
                last_clip_at[0] = now
                return "break"
            return None

        def do_select_all(_event=None):  # noqa: ANN001
            self._select_all_widget(widget)
            return "break"

        def on_ctrl_key(event):  # noqa: ANN001
            # Windows keycodes: C=67, V=86, A=65 regardless of RU/EN layout.
            keycode = getattr(event, "keycode", None)
            keysym = str(getattr(event, "keysym", "")).casefold()
            if keycode in (67, 0x43) or keysym in ("c", "с"):
                return do_copy(event)
            if keycode in (86, 0x56) or keysym in ("v", "м", "m"):
                return do_paste(event)
            if keycode in (65, 0x41) or keysym in ("a", "ф"):
                return do_select_all(event)
            return None

        def on_context(event):  # noqa: ANN001
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(
                label="Копировать",
                command=lambda: self._copy_from_widget(widget),
            )
            if allow_paste:
                menu.add_command(
                    label="Вставить",
                    command=lambda: self._paste_into_widget(widget),
                )
            menu.add_command(
                label="Выделить всё",
                command=lambda: self._select_all_widget(widget),
            )
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        tgt = self._clipboard_target(widget)
        for seq in ("<Control-c>", "<Control-C>", "<<Copy>>"):
            widget.bind(seq, do_copy)
            tgt.bind(seq, do_copy)
        for seq in ("<Control-a>", "<Control-A>"):
            widget.bind(seq, do_select_all)
            tgt.bind(seq, do_select_all)
        if allow_paste:
            for seq in (
                "<Control-v>",
                "<Control-V>",
                "<Shift-Insert>",
                "<<Paste>>",
            ):
                widget.bind(seq, do_paste)
                tgt.bind(seq, do_paste)
        widget.bind("<Control-KeyPress>", on_ctrl_key)
        tgt.bind("<Control-KeyPress>", on_ctrl_key)
        widget.bind("<Button-3>", on_context)
        tgt.bind("<Button-3>", on_context)

    def paste_clipboard_into_insert(self) -> None:
        if self._paste_into_widget(self.insert_box):
            self.warn_label.configure(text="Текст из буфера вставлен в поле.")
            return
        messagebox.showwarning(
            "Буфер",
            "Не удалось прочитать буфер обмена.\n"
            "Скопируйте текст ещё раз и нажмите «Из буфера», "
            "либо Ctrl+V / Shift+Insert / ПКМ → Вставить.",
        )

    def _insert_box_text(self) -> str:
        return self.insert_box.get("1.0", "end-1c").strip()

    def _append_dialogue_line(self, role: str, text: str, path: Path) -> None:
        try:
            MANAGER.append_line(role, text)
        except RuntimeError:
            append_transcript_line(path, role, text)

    def insert_into_dialogue(self, *, clear_box: bool = True) -> bool:
        text = self._insert_box_text()
        if not text:
            messagebox.showwarning("В диалог", "Вставьте или введите текст вопроса.")
            return False
        role = self.insert_role.get().strip() or "Я"
        if role not in ("Я", "Собеседник", "ИИ"):
            role = "Я"
        cfg = load_config()
        path = ROOT / cfg.transcript_path
        try:
            self._append_dialogue_line(role, text, path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("В диалог", str(exc))
            return False
        if clear_box:
            self.insert_box.delete("1.0", "end")
        self.warn_label.configure(text=f"Добавлено в диалог как «{role}:».")
        self._refresh_transcript()
        return True

    def insert_and_ask_ai(self) -> None:
        if not self.insert_into_dialogue(clear_box=True):
            return
        self.ask_ai_reply()

    def _append_ai_line(self, reply: str, path: Path) -> None:
        try:
            MANAGER.append_line("ИИ", reply)
        except RuntimeError:
            append_transcript_line(path, "ИИ", reply)

    def _transcript_trigger_heads(self, path: Path) -> list[str]:
        if not path.exists():
            return []
        body = iter_dialogue_blocks(path.read_text(encoding="utf-8"))
        return [b.splitlines()[0] if b else b for b in body]

    def _mark_auto_answered_for_path(self, path: Path) -> None:
        """После ручного ответа ИИ не даём автоответу повторить тот же триггер."""
        heads = self._transcript_trigger_heads(path)
        roles = {"Собеседник", "Я"}
        trigger = latest_trigger_line(heads, roles)
        if trigger:
            self._auto_watcher.mark_answered(trigger)

    def ask_ai_reply(self) -> None:
        if self._busy or self._auto_busy:
            return
        cfg = load_config()
        if not cfg.llm.enabled:
            messagebox.showwarning("ИИ", "LLM отключён в config.yaml (llm.enabled).")
            return
        if not resolve_api_key(cfg.llm):
            messagebox.showwarning(
                "ИИ",
                "Не задан API-ключ нейросети.\n\n"
                "В config.yaml укажите llm.api_key\n"
                f"или переменную окружения {cfg.llm.api_key_env}.\n\n"
                "Подойдут OpenAI, OpenRouter, Groq и другие OpenAI-compatible API "
                "(поменяйте llm.base_url и llm.model).",
            )
            return

        path = ROOT / cfg.transcript_path
        dialogue = read_recent_dialogue(path, cfg.llm.max_context_lines)
        if not dialogue.strip():
            messagebox.showwarning(
                "ИИ",
                "Диалог пуст. Сначала запишите реплики (Старт) или вставьте текст в live-transcript.md.",
            )
            return

        question = self.ai_question.get().strip()
        save_config(llm_spoken_mode=bool(self.spoken_mode_var.get()))
        cfg = load_config()

        self._busy = True
        # Пока идёт ручной запрос — автоответ по этой же реплике не стартует.
        self._mark_auto_answered_for_path(path)
        self._auto_watcher.in_flight = True
        self.ai_btn.configure(state="disabled")
        self.status_label.configure(text="Статус: запрос к ИИ…")
        mode = "короткая реплика" if cfg.llm.spoken_mode else "разбор аналитика"
        self.warn_label.configure(text=f"Ждём ответ нейросети ({mode})…")

        def worker() -> None:
            try:
                reply = ask_meeting_reply(
                    dialogue,
                    cfg.llm,
                    user_question=question,
                    spoken=bool(self.spoken_mode_var.get()),
                )
                self.after(0, lambda r=reply: self._on_ai_ok(r, path))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self._on_ai_fail(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_ok(self, reply: str, path: Path) -> None:
        try:
            self._append_ai_line(reply, path)
        except Exception as exc:  # noqa: BLE001
            self._busy = False
            self._auto_watcher.in_flight = False
            self.ai_btn.configure(state="normal")
            messagebox.showerror("ИИ", f"Ответ получен, но не записан в диалог:\n{exc}")
            self.status_label.configure(text="Статус: ошибка записи")
            return
        self._mark_auto_answered_for_path(path)
        self._busy = False
        self._auto_watcher.in_flight = False
        self.ai_btn.configure(state="normal")
        self.warn_label.configure(text="Ответ ИИ добавлен в диалог.")
        self._refresh_transcript()
        status = MANAGER.status().get("state", "idle")
        labels = {"listening": "слушаю", "idle": "стоп", "error": "ошибка"}
        self.status_label.configure(text=f"Статус: {labels.get(status, status)}")

    def _on_ai_fail(self, exc: Exception) -> None:
        self._busy = False
        self._auto_watcher.in_flight = False
        self.ai_btn.configure(state="normal")
        self.status_label.configure(text="Статус: ошибка ИИ")
        self.warn_label.configure(text=str(exc)[:200])
        messagebox.showerror("ИИ", str(exc))

    def _maybe_auto_reply(self) -> None:
        if self._busy or self._auto_busy:
            return
        if not bool(self.auto_reply_var.get()):
            return
        status = MANAGER.status()
        if status.get("state") != "listening":
            return

        cfg = load_config()
        if not cfg.llm.enabled or not cfg.llm.auto_reply:
            return
        if not resolve_api_key(cfg.llm):
            return

        path = ROOT / cfg.transcript_path
        if not path.exists():
            return
        body = iter_dialogue_blocks(path.read_text(encoding="utf-8"))
        decision = self._auto_watcher.observe(
            # watcher сравнивает «последнюю строку»; для multiline берём первую
            # физическую строку блока + хвост как отдельные строки не нужны —
            # передаём компактный список: одна строка на блок (первая линия).
            [b.splitlines()[0] if b else b for b in body],
            pause_sec=float(cfg.llm.auto_reply_pause_sec),
            reply_on_me=bool(cfg.llm.auto_reply_on_me),
        )
        if not decision.should_request:
            return

        dialogue = "\n\n".join(body[-cfg.llm.max_context_lines :])
        peer_line = decision.peer_line
        self._auto_busy = True
        # in_flight уже выставлен в observe(reason=ready)
        self.warn_label.configure(text="Автоответ: думаю…")

        def worker() -> None:
            try:
                reply = ask_auto_reply(dialogue, cfg.llm)
                self.after(
                    0,
                    lambda r=reply, p=peer_line: self._on_auto_ok(r, path, p),
                )
            except Exception as exc:  # noqa: BLE001
                self.after(
                    0,
                    lambda e=exc, p=peer_line: self._on_auto_fail(e, p),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_auto_ok(self, reply: str | None, path: Path, peer_line: str) -> None:
        self._auto_busy = False
        self._auto_watcher.mark_answered(peer_line)
        if reply is None:
            self.warn_label.configure(text="Автоответ: пропуск (SKIP).")
            return
        try:
            self._append_ai_line(reply, path)
        except Exception as exc:  # noqa: BLE001
            self.warn_label.configure(text=f"Автоответ: не записан — {exc}")
            return
        self.warn_label.configure(text="Автоответ ИИ добавлен в диалог.")
        self._refresh_transcript()

    def _on_auto_fail(self, exc: Exception, peer_line: str) -> None:
        self._auto_busy = False
        self._auto_watcher.in_flight = False
        msg = str(exc)
        # 429: не крутить автоответ по той же реплике каждые 4 секунды.
        if "429" in msg or "TPM" in msg or "Лимит OpenAI" in msg:
            if peer_line:
                self._auto_watcher.mark_answered(peer_line)
            self.warn_label.configure(
                text=(msg[:160] + " — автоответ по этой реплике остановлен.")
            )
            return
        # Сброс debounce — повторим после новой паузы, не помечаем answered.
        self._auto_watcher.pending_peer_line = ""
        self._auto_watcher.pending_since = None
        self.warn_label.configure(text=f"Автоответ ошибка: {msg[:180]}")
        _ = peer_line

    def _open_path(self, path: Path) -> None:
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            subprocess.Popen(["explorer.exe", str(path)])

    def _schedule_poll(self) -> None:
        self._refresh_transcript()
        self._maybe_auto_reply()
        status = MANAGER.status()
        state = status.get("state", "idle")
        err = status.get("error")
        if err and state == "error":
            self.status_label.configure(text=f"Статус: ошибка — {err}")
        elif not self._busy and not self._auto_busy:
            labels = {"listening": "слушаю", "idle": "стоп", "error": "ошибка"}
            self.status_label.configure(text=f"Статус: {labels.get(state, state)}")
        self._poll_after = self.after(500, self._schedule_poll)

    @staticmethod
    def _block_role(block: str) -> str | None:
        match = _BLOCK_ROLE_RE.match(block)
        return match.group(1).strip() if match else None

    def _configure_transcript_tags(self) -> None:
        # Тот же тёплый оранжевый, что у статусных сообщений («Ответ ИИ добавлен…»).
        fg = "#c45c26"
        self.transcript.tag_config("ai", foreground=fg, background="")

    def _render_transcript_blocks(self, blocks: list[str]) -> None:
        self._configure_transcript_tags()
        self.transcript.delete("1.0", "end")
        for i, block in enumerate(blocks):
            if i:
                self.transcript.insert("end", "\n\n")
            start = self.transcript.index("end-1c")
            self.transcript.insert("end", block)
            if self._block_role(block) == "ИИ":
                end = self.transcript.index("end-1c")
                self.transcript.tag_add("ai", start, end)

    def _refresh_transcript(self) -> None:
        cfg = load_config()
        path = ROOT / cfg.transcript_path
        blocks: list[str] = []
        if path.exists():
            blocks = iter_dialogue_blocks(path.read_text(encoding="utf-8"))
        text = "\n\n".join(blocks)
        current = self.transcript.get("1.0", "end-1c")
        if text != current:
            at_end = self.transcript.yview()[1] >= 0.95
            self._render_transcript_blocks(blocks)
            if at_end:
                self.transcript.see("end")

    def _on_close(self) -> None:
        if self._poll_after is not None:
            try:
                self.after_cancel(self._poll_after)
            except Exception:  # noqa: BLE001
                pass
        try:
            if MANAGER.status().get("state") == "listening":
                MANAGER.stop()
        except Exception:  # noqa: BLE001
            pass
        self.destroy()


def main() -> None:
    ensure_project_cwd()
    app = MeetingBridgeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
