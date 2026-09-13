"""Runtime cockpit UI for 1C Analitik.

The presentation layer is intentionally isolated here. Audio capture, local STT,
transcript persistence, skill selection, LLM orchestration and protocol
generation continue to live in their existing modules.
"""
from __future__ import annotations

import re
import time

import customtkinter as ctk

from meeting_bridge import gui as legacy
from meeting_bridge import gui_v2
from meeting_bridge.auto_reply import latest_trigger_line
from meeting_bridge.config import load_config, model_files_ready
from meeting_bridge.documents import read_dialogue_lines, save_dialogue_copy
from meeting_bridge.documents_v2 import build_protocol, extract_protocol_sections
from meeting_bridge.llm_client import resolve_api_key
from meeting_bridge.session import MANAGER
from meeting_bridge.writer import iter_dialogue_blocks

AMBER = "#F5A623"
AMBER_SOFT = "#FFD08A"
GREEN = "#6FD08C"
BLUE = "#74B9FF"
RED = "#D65C5C"
BG = "#0E131B"
PANEL = "#151B24"
PANEL_ALT = "#10161F"
BORDER = "#2A3442"
TEXT = "#F4F7FB"
MUTED = "#8D99A8"

_BLOCK_RE = re.compile(
    r"^\[(?P<time>\d{2}:\d{2}:\d{2})\]\s+(?P<role>[^:]+):\s?(?P<body>[\s\S]*)$"
)


def _duration_text(seconds: float | int) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _parse_block(block: str) -> tuple[str, str, str]:
    match = _BLOCK_RE.match((block or "").strip())
    if not match:
        return "", "", (block or "").strip()
    return (
        match.group("time"),
        match.group("role").strip(),
        match.group("body").strip(),
    )


class MeetingBridgeApp(gui_v2.MeetingBridgeApp):
    """Three-state workspace: before meeting, live cockpit and meeting summary."""

    def __init__(self) -> None:
        self._compact_mode = False
        self._meeting_started_at: float | None = None
        self._last_meeting_duration = 0
        self._last_transcript_render_key: tuple[str, ...] = ()
        self._last_sections: dict[str, list] = {}
        self._last_rows: list[tuple[str, str, str]] = []
        self._summary_tab = "overview"
        self._manual_request_peer_line = ""
        super().__init__()
        self.title("1С Аналитик")
        self.minsize(420, 560)

    # ---------- window and shell ----------
    def _place_on_primary(self) -> None:
        self.update_idletasks()
        try:
            import ctypes

            user32 = ctypes.windll.user32
            sw = int(user32.GetSystemMetrics(0))
            sh = int(user32.GetSystemMetrics(1))
            w, h = 1080, 760
            x = max(24, (sw - w) // 2)
            y = max(24, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:  # noqa: BLE001
            self.geometry("1080x760+60+40")

    def _build(self) -> None:
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=BG)

        # Tk variables must exist before settings widgets bind to them.
        self.auto_reply_var = ctk.BooleanVar(value=True)
        self.spoken_mode_var = ctk.BooleanVar(value=False)

        self._build_topbar()
        self.warn_label = ctk.CTkLabel(
            self,
            text="",
            text_color=AMBER_SOFT,
            justify="left",
            anchor="w",
            wraplength=980,
            font=ctk.CTkFont(size=12),
        )
        self.warn_label.pack(fill="x", padx=18, pady=(0, 4))

        self.settings_frame = ctk.CTkFrame(
            self,
            fg_color=PANEL,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )
        self._build_settings()
        self._style_settings()

        self.pre_frame = self._build_pre_meeting()
        self.live_frame = self._build_live_workspace()
        self.summary_frame = self._build_summary()

        self.ask_frame = self._build_ask_bar()
        self.ask_frame.pack(side="bottom", fill="x", padx=18, pady=(4, 14))

        # Compatibility attributes still used by inherited lifecycle methods.
        self.artifacts_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.artifact_text = ctk.CTkLabel(self.artifacts_frame, text="")
        self.open_folder_btn = ctk.CTkButton(
            self.artifacts_frame,
            text="Папка",
            command=self.open_archive_folder,
        )

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._show_pre_meeting()
        self.after_idle(self._populate_recent_meetings)

    def _build_topbar(self) -> None:
        top = ctk.CTkFrame(self, fg_color=PANEL_ALT, corner_radius=0, height=72)
        top.pack(fill="x")
        top.pack_propagate(False)

        brand = ctk.CTkFrame(top, fg_color="transparent")
        brand.pack(side="left", fill="y", padx=(18, 8), pady=9)
        self.brand_title = ctk.CTkLabel(
            brand,
            text="1С Аналитик",
            text_color=TEXT,
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self.brand_title.pack(anchor="w")
        self.brand_subtitle = ctk.CTkLabel(
            brand,
            text="Помощник аналитика 1С",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.brand_subtitle.pack(anchor="w")

        controls = ctk.CTkFrame(top, fg_color="transparent")
        controls.pack(side="right", fill="y", padx=14, pady=13)
        self.readiness_label = ctk.CTkLabel(
            controls,
            text="Проверяем готовность…",
            text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.readiness_label.pack(side="left", padx=(0, 10))
        self.status_label = ctk.CTkLabel(
            controls,
            text="● Готов",
            text_color=GREEN,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.status_label.pack(side="left", padx=(0, 10))

        self.compact_btn = ctk.CTkButton(
            controls,
            text="▯ Компактный",
            width=112,
            height=34,
            fg_color=PANEL,
            hover_color="#202A37",
            border_width=1,
            border_color=BORDER,
            command=self._toggle_compact,
        )
        self.compact_btn.pack(side="left", padx=4)

        self.settings_btn = ctk.CTkButton(
            controls,
            text="⚙ Настройки",
            width=108,
            height=34,
            fg_color=PANEL,
            hover_color="#202A37",
            border_width=1,
            border_color=BORDER,
            command=self._toggle_settings,
        )
        self.settings_btn.pack(side="left", padx=4)

    def _style_settings(self) -> None:
        self.settings_frame.configure(fg_color=PANEL, border_color=BORDER)
        for widget in (self.refresh_btn, self.model_btn, self.update_btn):
            widget.configure(fg_color="#202A37", hover_color="#2A3646")
        self.auto_reply_check.configure(
            fg_color=AMBER,
            hover_color="#D98F1F",
            border_color=BORDER,
        )

    def _build_pre_meeting(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")

        hero = ctk.CTkFrame(
            frame,
            fg_color=PANEL,
            border_width=1,
            border_color=BORDER,
            corner_radius=18,
        )
        hero.pack(fill="x", padx=18, pady=(8, 10))

        ctk.CTkLabel(
            hero,
            text="Готовы к встрече",
            text_color=AMBER_SOFT,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(
            hero,
            text="Тема встречи",
            text_color=TEXT,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(8, 5))

        self.title_entry = ctk.CTkEntry(
            hero,
            placeholder_text="Например: закрытие месяца / НДС / сверка",
            height=42,
            fg_color=PANEL_ALT,
            border_color=BORDER,
        )
        self.title_entry.pack(fill="x", padx=20)
        self._enable_clipboard(self.title_entry)

        chips = ctk.CTkFrame(hero, fg_color="transparent")
        chips.pack(fill="x", padx=20, pady=(14, 12))
        self.mic_chip = self._chip(chips, "… Микрофон")
        self.peer_chip = self._chip(chips, "… Звук собеседника")
        self.stt_chip = self._chip(chips, "… Распознавание")
        self.ai_chip = self._chip(chips, "… ИИ")

        self.session_btn = ctk.CTkButton(
            hero,
            text="▶  Начать встречу",
            height=48,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=AMBER,
            hover_color="#D98F1F",
            text_color="#1A1205",
            command=self._toggle_meeting,
        )
        self.session_btn.pack(fill="x", padx=20, pady=(4, 20))
        self._session_fg = self.session_btn.cget("fg_color")
        self._session_hover = self.session_btn.cget("hover_color")
        self.start_btn = self.session_btn

        recent = ctk.CTkFrame(
            frame,
            fg_color=PANEL,
            border_width=1,
            border_color=BORDER,
            corner_radius=16,
        )
        recent.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        ctk.CTkLabel(
            recent,
            text="Последние встречи",
            text_color=TEXT,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(14, 6))
        self.recent_list = ctk.CTkFrame(recent, fg_color="transparent")
        self.recent_list.pack(fill="x", padx=12, pady=(0, 12))
        return frame

    @staticmethod
    def _chip(parent, text: str):  # noqa: ANN001
        label = ctk.CTkLabel(
            parent,
            text=text,
            text_color=MUTED,
            fg_color=PANEL_ALT,
            corner_radius=10,
            padx=10,
            pady=6,
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        label.pack(side="left", padx=(0, 7))
        return label

    def _build_live_workspace(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")

        live_header = ctk.CTkFrame(frame, fg_color="transparent")
        live_header.pack(fill="x", padx=18, pady=(4, 7))
        left = ctk.CTkFrame(live_header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        self.live_state_label = ctk.CTkLabel(
            left,
            text="● Идёт встреча",
            text_color=GREEN,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.live_state_label.pack(side="left")
        self.timer_label = ctk.CTkLabel(
            left,
            text="00:00:00",
            text_color=TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.timer_label.pack(side="left", padx=(12, 0))
        self.live_topic_label = ctk.CTkLabel(
            left,
            text="",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.live_topic_label.pack(side="left", padx=(14, 0))

        self.new_case_btn = ctk.CTkButton(
            live_header,
            text="Новая тема",
            width=100,
            height=34,
            fg_color=PANEL,
            hover_color="#202A37",
            border_width=1,
            border_color=BORDER,
            command=self.start_new_case,
        )
        self.new_case_btn.pack(side="right", padx=(6, 0))
        self.new_case_btn.configure(state="disabled")

        self.live_end_btn = ctk.CTkButton(
            live_header,
            text="■ Завершить",
            width=108,
            height=34,
            fg_color="#8F3636",
            hover_color="#753030",
            command=self.stop_session,
        )
        self.live_end_btn.pack(side="right")

        self.audio_health_label = ctk.CTkLabel(
            frame,
            text="Проверяю звук…",
            text_color=MUTED,
            anchor="w",
            justify="left",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.audio_health_label.pack(fill="x", padx=20, pady=(0, 5))

        workspace = ctk.CTkFrame(frame, fg_color="transparent")
        workspace.pack(fill="both", expand=True, padx=18, pady=(0, 6))
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=1, uniform="workspace")
        workspace.grid_columnconfigure(1, weight=1, uniform="workspace")
        self.live_workspace = workspace

        self.transcript_panel = ctk.CTkFrame(
            workspace,
            fg_color=PANEL,
            border_width=1,
            border_color=BORDER,
            corner_radius=16,
        )
        self.transcript_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        transcript_head = ctk.CTkFrame(self.transcript_panel, fg_color="transparent")
        transcript_head.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            transcript_head,
            text="СТЕНОГРАММА",
            text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left")
        self.clear_btn = ctk.CTkButton(
            transcript_head,
            text="Очистить",
            width=74,
            height=28,
            fg_color="transparent",
            hover_color="#202A37",
            border_width=1,
            border_color=BORDER,
            command=self.clear_transcript_and_hint,
        )
        self.clear_btn.pack(side="right")

        self.transcript = ctk.CTkTextbox(
            self.transcript_panel,
            wrap="word",
            fg_color=PANEL,
            border_width=0,
        )
        self.transcript.pack(fill="both", expand=True, padx=10, pady=(2, 10))
        self._configure_cockpit_transcript_tags()
        self._lock_readonly(self.transcript)
        self._enable_clipboard(self.transcript, allow_paste=False)

        self.assistant_panel = ctk.CTkFrame(
            workspace,
            fg_color=PANEL,
            border_width=1,
            border_color="#5A4729",
            corner_radius=16,
        )
        self.assistant_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(
            self.assistant_panel,
            text="ПОДСКАЗКА 1С АНАЛИТИКА",
            text_color=AMBER_SOFT,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(11, 5))

        self.assistant_box = ctk.CTkTextbox(
            self.assistant_panel,
            wrap="word",
            fg_color=PANEL,
            border_width=0,
        )
        self.assistant_box.pack(fill="both", expand=True, padx=11, pady=(0, 11))
        self._configure_assistant_tags()
        self.assistant_box.insert(
            "1.0",
            "Подсказка появится здесь во время встречи или после вашего вопроса.",
        )
        self._lock_readonly(self.assistant_box)
        self._enable_clipboard(self.assistant_box, allow_paste=False)
        return frame

    def _build_ask_bar(self):
        frame = ctk.CTkFrame(
            self,
            fg_color=PANEL,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )
        self.ai_question = ctk.CTkEntry(
            frame,
            placeholder_text="Спросить 1С Аналитика…",
            height=40,
            fg_color=PANEL_ALT,
            border_color=BORDER,
        )
        self.ai_question.pack(side="left", fill="x", expand=True, padx=(10, 7), pady=9)
        self.ai_question.bind("<Return>", lambda _e: self._ask_from_entry())
        self._enable_clipboard(self.ai_question)

        self.ai_btn = ctk.CTkButton(
            frame,
            text="Отправить →",
            width=105,
            height=40,
            fg_color=AMBER,
            hover_color="#D98F1F",
            text_color="#1A1205",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._ask_from_entry,
        )
        self.ai_btn.pack(side="right", padx=(0, 10), pady=9)
        return frame

    def _build_summary(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")

        card = ctk.CTkFrame(
            frame,
            fg_color=PANEL,
            border_width=1,
            border_color=BORDER,
            corner_radius=18,
        )
        card.pack(fill="both", expand=True, padx=18, pady=(7, 8))
        ctk.CTkLabel(
            card,
            text="Встреча завершена",
            text_color=TEXT,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 2))
        self.summary_subtitle = ctk.CTkLabel(
            card,
            text="Строим итог встречи…",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.summary_subtitle.pack(anchor="w", padx=18)

        metrics = ctk.CTkFrame(card, fg_color="transparent")
        metrics.pack(fill="x", padx=18, pady=(14, 10))
        self.summary_metric_labels: dict[str, ctk.CTkLabel] = {}
        for key, title in (
            ("duration", "Длительность"),
            ("replicas", "Реплики"),
            ("decisions", "Решения"),
            ("actions", "Задачи"),
            ("questions", "Вопросы"),
        ):
            box = ctk.CTkFrame(metrics, fg_color=PANEL_ALT, corner_radius=11)
            box.pack(side="left", fill="x", expand=True, padx=(0, 7))
            value = ctk.CTkLabel(
                box,
                text="0",
                text_color=AMBER_SOFT if key not in {"duration", "replicas"} else TEXT,
                font=ctk.CTkFont(size=18, weight="bold"),
            )
            value.pack(pady=(8, 0))
            ctk.CTkLabel(
                box,
                text=title,
                text_color=MUTED,
                font=ctk.CTkFont(size=10),
            ).pack(pady=(0, 8))
            self.summary_metric_labels[key] = value

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 10))
        self.open_protocol_btn = ctk.CTkButton(
            actions,
            text="Открыть протокол",
            fg_color=AMBER,
            hover_color="#D98F1F",
            text_color="#1A1205",
            command=self._open_protocol,
        )
        self.open_protocol_btn.pack(side="left")
        self.open_folder_btn_summary = ctk.CTkButton(
            actions,
            text="Папка встреч",
            fg_color=PANEL_ALT,
            hover_color="#202A37",
            border_width=1,
            border_color=BORDER,
            command=self.open_archive_folder,
        )
        self.open_folder_btn_summary.pack(side="left", padx=7)
        ctk.CTkButton(
            actions,
            text="Новая встреча",
            fg_color=PANEL_ALT,
            hover_color="#202A37",
            border_width=1,
            border_color=BORDER,
            command=self._reset_for_new_meeting,
        ).pack(side="right")

        tabs = ctk.CTkFrame(card, fg_color="transparent")
        tabs.pack(fill="x", padx=18, pady=(0, 7))
        self.summary_tab_buttons: dict[str, ctk.CTkButton] = {}
        for key, title in (
            ("overview", "Итоги"),
            ("decisions", "Решения"),
            ("actions", "Задачи"),
            ("questions", "Вопросы"),
            ("transcript", "Стенограмма"),
        ):
            btn = ctk.CTkButton(
                tabs,
                text=title,
                height=30,
                fg_color=PANEL_ALT,
                hover_color="#202A37",
                border_width=1,
                border_color=BORDER,
                command=lambda k=key: self._show_summary_tab(k),
            )
            btn.pack(side="left", padx=(0, 5))
            self.summary_tab_buttons[key] = btn

        self.summary_box = ctk.CTkTextbox(
            card,
            wrap="word",
            fg_color=PANEL_ALT,
            border_width=1,
            border_color=BORDER,
        )
        self.summary_box.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self._lock_readonly(self.summary_box)
        self._enable_clipboard(self.summary_box, allow_paste=False)
        return frame

    # ---------- state switching ----------
    def _show_pre_meeting(self) -> None:
        self.live_frame.pack_forget()
        self.summary_frame.pack_forget()
        if not self.pre_frame.winfo_manager():
            self.pre_frame.pack(fill="both", expand=True)
        self.status_label.configure(text="● Готов", text_color=GREEN)
        self.after_idle(self._populate_recent_meetings)

    def _show_live_workspace(self) -> None:
        self.pre_frame.pack_forget()
        self.summary_frame.pack_forget()
        if not self.live_frame.winfo_manager():
            self.live_frame.pack(fill="both", expand=True)
        topic = self._meeting_title() or "Встреча без названия"
        self.live_topic_label.configure(text=topic)
        self.status_label.configure(text="● Встреча", text_color=GREEN)
        self._apply_compact_layout()

    def _show_summary(self) -> None:
        self.pre_frame.pack_forget()
        self.live_frame.pack_forget()
        if not self.summary_frame.winfo_manager():
            self.summary_frame.pack(fill="both", expand=True)
        self.status_label.configure(text="● Завершено", text_color=MUTED)
        self._show_summary_tab("overview")

    def _reset_for_new_meeting(self) -> None:
        if self._busy or self._auto_busy:
            return
        self._finalized = False
        self._last_protocol = None
        self._last_sections = {}
        self._last_rows = []
        self._last_meeting_duration = 0
        self.timer_label.configure(text="00:00:00")
        self.summary_subtitle.configure(text="")
        self.title_entry.delete(0, "end")
        self.warn_label.configure(text="")
        self.clear_transcript_and_hint()
        self._show_pre_meeting()

    # ---------- compact mode ----------
    def _toggle_compact(self) -> None:
        self._compact_mode = not self._compact_mode
        self._apply_compact_layout()

    def _apply_compact_layout(self) -> None:
        if self._compact_mode:
            self.compact_btn.configure(text="▣ Полный")
            self.brand_subtitle.pack_forget()
            self.readiness_label.pack_forget()
            self.geometry("440x720")
            if self.live_frame.winfo_manager():
                self.transcript_panel.grid_remove()
                self.assistant_panel.grid(row=0, column=0, sticky="nsew", padx=0)
                self.live_workspace.grid_columnconfigure(0, weight=1)
                self.live_workspace.grid_columnconfigure(1, weight=0)
                self.new_case_btn.pack_forget()
        else:
            self.compact_btn.configure(text="▯ Компактный")
            if not self.brand_subtitle.winfo_manager():
                self.brand_subtitle.pack(anchor="w")
            if not self.readiness_label.winfo_manager():
                self.readiness_label.pack(side="left", padx=(0, 10))
            if self.live_frame.winfo_manager():
                self.transcript_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
                self.assistant_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
                self.live_workspace.grid_columnconfigure(0, weight=1)
                self.live_workspace.grid_columnconfigure(1, weight=1)
                if not self.new_case_btn.winfo_manager():
                    self.new_case_btn.pack(side="right", padx=(6, 0))
            self.geometry("1080x760")

    def _toggle_settings(self) -> None:
        if self._compact_mode and not self._settings_open:
            self._compact_mode = False
            self._apply_compact_layout()
        super()._toggle_settings()
        if self._settings_open and not self._meeting_active and not self._busy:
            self.refresh_devices()

    # ---------- readiness ----------
    def _update_readiness(self) -> None:
        super()._update_readiness()
        try:
            cfg = load_config()
            model_ok = model_files_ready(legacy.ROOT / cfg.model_dir)
            mic_ok = self.mic_combo.get().strip() not in ("", "—")
            speaker = self.speaker_combo.get().strip()
            speaker_ok = speaker not in ("", "—") and "подключите" not in speaker.casefold()
            ai_ok = bool(resolve_api_key(cfg.llm))
        except Exception:  # noqa: BLE001
            return
        self._set_chip(self.mic_chip, "Микрофон", mic_ok)
        self._set_chip(self.peer_chip, "Звук собеседника", speaker_ok)
        self._set_chip(self.stt_chip, "Распознавание", model_ok)
        self._set_chip(self.ai_chip, "ИИ", ai_ok)

    @staticmethod
    def _set_chip(label, text: str, ok: bool) -> None:  # noqa: ANN001
        label.configure(
            text=f"{'✓' if ok else '!'} {text}",
            text_color=GREEN if ok else AMBER_SOFT,
            fg_color="#122019" if ok else "#261D12",
        )

    def _populate_recent_meetings(self) -> None:
        if not hasattr(self, "recent_list"):
            return
        for child in self.recent_list.winfo_children():
            child.destroy()
        try:
            cfg = load_config()
            folder = legacy.ROOT / cfg.archive_dir
            files = sorted(
                folder.glob("protocol-*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:3]
        except Exception:  # noqa: BLE001
            files = []
        if not files:
            ctk.CTkLabel(
                self.recent_list,
                text="Здесь появятся автоматически сохранённые протоколы встреч.",
                text_color=MUTED,
                anchor="w",
            ).pack(fill="x", padx=6, pady=8)
            return
        for path in files:
            name = path.stem.removeprefix("protocol-").replace("-", " ")
            if len(name) > 58:
                name = name[:55].rstrip() + "…"
            btn = ctk.CTkButton(
                self.recent_list,
                text=name,
                anchor="w",
                height=34,
                fg_color=PANEL_ALT,
                hover_color="#202A37",
                border_width=1,
                border_color=BORDER,
                command=lambda p=path: self._open_path(p),
            )
            btn.pack(fill="x", padx=4, pady=3)

    # ---------- activity and audio ----------
    def _show_activity(self, text: str) -> None:
        lowered = text.casefold()
        color = RED if "ошиб" in lowered else (
            AMBER_SOFT if "готовит" in lowered or "анализ" in lowered else GREEN
        )
        self.status_label.configure(text=f"● {text}", text_color=color)

    def _hide_activity(self) -> None:
        if not self._meeting_active and not self._finalized:
            self.status_label.configure(text="● Готов", text_color=GREEN)

    def _show_audio_health(self, text: str, *, ok: bool) -> None:
        self.audio_health_label.configure(
            text=text,
            text_color=GREEN if ok else AMBER_SOFT,
        )

    def _hide_audio_health(self) -> None:
        self.audio_health_label.configure(text="")

    def _render_audio_health(self, status: dict) -> None:
        health = status.get("audio_health") or {}
        if not health:
            self._show_audio_health("Проверяю звук…", ok=False)
            return
        mic = health.get("Я") or {}
        peer = health.get("Собеседник") or {}
        mic_chunks = int(mic.get("chunks") or 0)
        peer_chunks = int(peer.get("chunks") or 0)
        if min(mic_chunks, peer_chunks) < 5:
            self._show_audio_health("Проверяю звук…", ok=False)
            return
        mic_ok = bool(mic.get("has_signal"))
        peer_ok = bool(peer.get("has_signal"))
        self._show_audio_health(
            f"🎤 Микрофон: {'сигнал есть' if mic_ok else 'нет сигнала'}   ·   "
            f"🔊 Собеседник: {'сигнал есть' if peer_ok else 'нет сигнала'}",
            ok=mic_ok and peer_ok,
        )

    # ---------- visual transcript ----------
    def _configure_cockpit_transcript_tags(self) -> None:
        text = self.transcript._textbox
        text.tag_configure("peer_head", foreground=BLUE, font=("Segoe UI", 10, "bold"))
        text.tag_configure("me_head", foreground=GREEN, font=("Segoe UI", 10, "bold"))
        text.tag_configure("system_head", foreground=MUTED, font=("Segoe UI", 9, "bold"))
        text.tag_configure("body", foreground=TEXT, spacing3=7)
        text.tag_configure("system_body", foreground=MUTED, spacing3=6)

    def _render_transcript_blocks(self, blocks: list[str]) -> None:
        self.transcript.delete("1.0", "end")
        visible = 0
        for block in blocks:
            stamp, role, body = _parse_block(block)
            if role == "ИИ":
                continue
            if visible:
                self.transcript.insert("end", "\n")
            visible += 1
            if role == "Собеседник":
                tag = "peer_head"
            elif role == "Я":
                tag = "me_head"
            else:
                tag = "system_head"
            head = role or "Система"
            if stamp:
                head += f" · {stamp[:5]}"
            self.transcript.insert("end", head + "\n", tag)
            self.transcript.insert(
                "end",
                (body or "…") + "\n",
                "system_body" if role == "Система" else "body",
            )
        if not visible:
            self.transcript.insert(
                "end",
                "Стенограмма появится здесь после начала разговора.",
                "system_body",
            )

    def _refresh_transcript(self) -> None:
        cfg = load_config()
        path = legacy.ROOT / cfg.transcript_path
        blocks: list[str] = []
        if path.exists():
            blocks = iter_dialogue_blocks(path.read_text(encoding="utf-8"))
        key = tuple(blocks)
        if key == self._last_transcript_render_key:
            return
        at_end = self.transcript.yview()[1] >= 0.95
        self._last_transcript_render_key = key
        self._render_transcript_blocks(blocks)
        if at_end:
            self.transcript.see("end")

    # ---------- structured assistant ----------
    def _configure_assistant_tags(self) -> None:
        text = self.assistant_box._textbox
        text.tag_configure(
            "hero", foreground=AMBER_SOFT, font=("Segoe UI", 12, "bold"), spacing1=5, spacing3=5
        )
        text.tag_configure(
            "heading", foreground=TEXT, font=("Segoe UI", 10, "bold"), spacing1=9, spacing3=4
        )
        text.tag_configure("body", foreground=TEXT, spacing3=4)
        text.tag_configure("muted", foreground=MUTED)

    @staticmethod
    def _assistant_heading(line: str) -> tuple[str, str] | None:
        clean = re.sub(r"^[#*\-\s]+|[*:\s]+$", "", line or "").strip()
        low = clean.casefold()
        if low.startswith("что сказать сейчас"):
            return "hero", "Что сказать сейчас"
        if low.startswith("что проверить"):
            return "heading", "Что проверить в 1С"
        if low.startswith("что уточнить"):
            return "heading", "Что уточнить"
        if low.startswith("разбор") or low.startswith("почему"):
            return "heading", "Разбор"
        return None

    def _show_assistant(self, text: str) -> None:
        payload = (text or "").strip()
        if not payload:
            return
        self.assistant_box.delete("1.0", "end")
        seen_heading = False
        for raw in payload.splitlines():
            heading = self._assistant_heading(raw)
            if heading:
                if seen_heading:
                    self.assistant_box.insert("end", "\n")
                tag, title = heading
                self.assistant_box.insert("end", title + "\n", tag)
                seen_heading = True
                continue
            clean = raw.strip()
            if not clean:
                self.assistant_box.insert("end", "\n")
                continue
            self.assistant_box.insert("end", clean + "\n", "body")
        self.assistant_box.see("1.0")

    # ---------- meeting lifecycle ----------
    def start_session(self) -> None:
        mic = self.mic_combo.get().strip()
        speaker = self.speaker_combo.get().strip()
        if mic in ("", "—") or speaker in ("", "—") or "подключите" in speaker.casefold():
            self.refresh_devices()
        super().start_session()

    def _on_started(self, status: dict) -> None:
        super()._on_started(status)
        if status.get("state") == "listening":
            self._meeting_started_at = time.monotonic()
            self._last_meeting_duration = 0
            self.new_case_btn.configure(state="normal")
            self._show_live_workspace()
            self._show_activity("Слушаю встречу")
            self._render_audio_health(status)

    def _on_stopped(self, status: dict) -> None:
        if self._meeting_started_at is not None:
            self._last_meeting_duration = max(
                0, int(time.monotonic() - self._meeting_started_at)
            )
        self._meeting_started_at = None
        super()._on_stopped(status)
        self.new_case_btn.configure(state="disabled")
        self._hide_audio_health()
        self._show_activity("Встреча завершена")

    def _update_timer(self) -> None:
        if self._meeting_started_at is None:
            return
        self.timer_label.configure(
            text=_duration_text(time.monotonic() - self._meeting_started_at)
        )

    def _finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True
        cfg = load_config()
        src = legacy.ROOT / cfg.transcript_path
        if not src.exists() or not iter_dialogue_blocks(src.read_text(encoding="utf-8")):
            self.warn_label.configure(text="Встреча завершена, но в стенограмме нет реплик.")
            self._show_summary()
            return
        try:
            save_dialogue_copy(
                src,
                legacy.ROOT / cfg.archive_dir,
                title=self._meeting_title(),
            )
            self._last_protocol = build_protocol(
                src,
                legacy.ROOT / cfg.archive_dir,
                title=self._meeting_title() or "Протокол встречи по 1С",
            )
            rows = read_dialogue_lines(src)
            sections = extract_protocol_sections(rows)
        except Exception as exc:  # noqa: BLE001
            self.warn_label.configure(
                text=f"Встреча сохранена, но протокол не сформирован: {exc}"
            )
            self._show_summary()
            return

        self._last_rows = rows
        self._last_sections = sections
        human_rows = [row for row in rows if row[1] not in {"ИИ", "Система"}]
        self.summary_metric_labels["duration"].configure(
            text=_duration_text(self._last_meeting_duration)
        )
        self.summary_metric_labels["replicas"].configure(text=str(len(human_rows)))
        self.summary_metric_labels["decisions"].configure(
            text=str(len(sections["decisions"]))
        )
        self.summary_metric_labels["actions"].configure(
            text=str(len(sections["actions"]))
        )
        self.summary_metric_labels["questions"].configure(
            text=str(len(sections["questions"]))
        )
        self.summary_subtitle.configure(
            text="✓ Стенограмма сохранена   ✓ Протокол сформирован локально"
        )
        self.warn_label.configure(
            text="Встреча завершена. Стенограмма и протокол сохранены автоматически."
        )
        self._show_summary()
        self._populate_recent_meetings()

    # ---------- summary tabs ----------
    def _show_summary_tab(self, key: str) -> None:
        self._summary_tab = key
        for tab_key, btn in self.summary_tab_buttons.items():
            btn.configure(
                fg_color="#2B251A" if tab_key == key else PANEL_ALT,
                border_color=AMBER if tab_key == key else BORDER,
                text_color=AMBER_SOFT if tab_key == key else TEXT,
            )

        sections = self._last_sections
        if key == "overview":
            agenda = sections.get("agenda") or ["Рабочие вопросы по 1С"]
            text = "Повестка\n\n" + "\n".join(f"• {item}" for item in agenda)
            text += (
                "\n\nПротокол сформирован локально. Критичные термины 1С и номера "
                "счетов стоит проверить по стенограмме."
            )
        elif key == "decisions":
            items = sections.get("decisions") or ["Явные решения не распознаны."]
            text = "\n\n".join(f"• {item}" for item in items)
        elif key == "actions":
            actions = sections.get("actions") or []
            text = "\n\n".join(
                f"{i}. {task}\n   Ответственный: {owner} · Срок: {due}"
                for i, (task, owner, due) in enumerate(actions, start=1)
            ) or "Явные задачи не распознаны."
        elif key == "questions":
            items = sections.get("questions") or ["Явных открытых вопросов не распознано."]
            text = "\n\n".join(f"• {item}" for item in items)
        else:
            human = [
                f"{stamp}  {role}\n{text}"
                for stamp, role, text in self._last_rows
                if role not in {"ИИ", "Система"}
            ]
            text = "\n\n".join(human) or "Стенограмма пуста."

        self.summary_box.delete("1.0", "end")
        self.summary_box.insert("1.0", text)
        self.summary_box.see("1.0")

    # ---------- existing live AI catch-up ----------
    def _latest_human_trigger(self, path) -> str:  # noqa: ANN001
        try:
            heads = self._transcript_trigger_heads(path)
        except Exception:  # noqa: BLE001
            return ""
        return latest_trigger_line(heads, {"Я", "Собеседник"}) or ""

    def _queue_live_catchup(self, path, answered_peer_line: str) -> bool:  # noqa: ANN001
        if not self._meeting_active or not bool(self.auto_reply_var.get()):
            return False
        if MANAGER.status().get("state") != "listening":
            return False

        latest = self._latest_human_trigger(path)
        answered = (answered_peer_line or "").strip()
        if not latest or not answered or latest == answered:
            return False

        self._auto_watcher.answered_peer_line = answered
        self._auto_watcher.queue_catchup(latest)
        self.warn_label.configure(
            text="Во время ответа появились новые реплики. 1С Аналитик сразу их проверит."
        )
        return True

    def clear_transcript_and_hint(self) -> None:
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

        self._last_transcript_render_key = ()
        self.transcript.delete("1.0", "end")
        self.transcript.insert(
            "1.0",
            "Стенограмма появится здесь после начала разговора.",
            "system_body",
        )
        self.assistant_box.delete("1.0", "end")
        self.assistant_box.insert(
            "1.0",
            "Подсказка появится здесь во время встречи или после вашего вопроса.",
            "muted",
        )
        self._auto_watcher.reset()
        self._topic_types = frozenset()
        self._last_topic_block = ""
        self._topic_shift_pending = False
        self.warn_label.configure(text="Стенограмма и подсказка очищены.")

    def ask_ai_reply(self) -> None:
        path = legacy.ROOT / load_config().transcript_path
        request_peer_line = self._latest_human_trigger(path)
        was_busy = self._busy or self._auto_busy
        super().ask_ai_reply()
        if not was_busy and self._busy:
            self._manual_request_peer_line = request_peer_line
            self._show_activity("1С Аналитик готовит ответ…")

    def _on_ai_ok(self, reply: str, path) -> None:  # noqa: ANN001
        request_peer_line = self._manual_request_peer_line
        super()._on_ai_ok(reply, path)
        catchup = self._queue_live_catchup(path, request_peer_line)
        self._manual_request_peer_line = ""
        if self._meeting_active:
            self._show_activity(
                "Есть новые реплики, готовлю следующую подсказку…"
                if catchup
                else "Слушаю встречу"
            )
        elif not self._finalized:
            self._hide_activity()

    def _on_ai_fail(self, exc: Exception) -> None:
        request_peer_line = self._manual_request_peer_line
        path = legacy.ROOT / load_config().transcript_path
        super()._on_ai_fail(exc)
        catchup = self._queue_live_catchup(path, request_peer_line)
        self._manual_request_peer_line = ""
        if self._meeting_active:
            self._show_activity(
                "Есть новые реплики, готовлю следующую подсказку…"
                if catchup
                else "Слушаю встречу"
            )
        elif not self._finalized:
            self._hide_activity()

    def _on_auto_ok(self, reply, path, peer_line: str) -> None:  # noqa: ANN001
        super()._on_auto_ok(reply, path, peer_line)
        catchup = self._queue_live_catchup(path, peer_line)
        if self._meeting_active:
            self._show_activity(
                "Есть новые реплики, готовлю следующую подсказку…"
                if catchup
                else "Слушаю встречу"
            )

    def _on_auto_fail(self, exc: Exception, peer_line: str) -> None:
        path = legacy.ROOT / load_config().transcript_path
        super()._on_auto_fail(exc, peer_line)
        catchup = self._queue_live_catchup(path, peer_line)
        if self._meeting_active:
            self._show_activity(
                "Есть новые реплики, готовлю следующую подсказку…"
                if catchup
                else "Слушаю встречу"
            )

    def _schedule_poll(self) -> None:
        super()._schedule_poll()
        status = MANAGER.status()
        state = status.get("state", "idle")
        error = status.get("error")
        self._update_timer()

        if state == "listening":
            self._render_audio_health(status)
            if self._auto_busy:
                self._show_activity("1С Аналитик анализирует реплику…")
            elif self._busy:
                self._show_activity("1С Аналитик готовит ответ…")
            elif self._auto_watcher.catchup_peer_line:
                self._show_activity("Есть новые реплики, готовлю следующую подсказку…")
            else:
                self._show_activity("Слушаю встречу")
        elif state == "error":
            self._show_activity("Ошибка звука")
            self._render_audio_health(status)
            if error:
                self.warn_label.configure(
                    text=f"Не слышу звук корректно: {error}. Откройте «Настройки»."
                )
        elif self._finalized:
            self.status_label.configure(text="● Завершено", text_color=MUTED)
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
