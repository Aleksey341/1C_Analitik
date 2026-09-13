from __future__ import annotations

import inspect

from meeting_bridge import gui_runtime, gui_v2


def test_runtime_ui_wraps_v2_app():
    assert issubclass(gui_runtime.MeetingBridgeApp, gui_v2.MeetingBridgeApp)


def test_duration_text_is_stable_for_live_timer():
    assert gui_runtime._duration_text(0) == "00:00:00"
    assert gui_runtime._duration_text(65) == "00:01:05"
    assert gui_runtime._duration_text(3661) == "01:01:01"


def test_transcript_block_parser_keeps_role_time_and_multiline_body():
    stamp, role, body = gui_runtime._parse_block(
        "[13:05:02] Собеседник: Почему не закрылся 25 счёт?\nПродолжение вопроса"
    )
    assert stamp == "13:05:02"
    assert role == "Собеседник"
    assert "25 счёт" in body
    assert "Продолжение" in body


def test_cockpit_has_three_user_states_and_one_common_question_bar():
    build = inspect.getsource(gui_runtime.MeetingBridgeApp._build)
    pre = inspect.getsource(gui_runtime.MeetingBridgeApp._build_pre_meeting)
    live = inspect.getsource(gui_runtime.MeetingBridgeApp._build_live_workspace)
    summary = inspect.getsource(gui_runtime.MeetingBridgeApp._build_summary)
    ask = inspect.getsource(gui_runtime.MeetingBridgeApp._build_ask_bar)
    assert "self.pre_frame" in build
    assert "self.live_frame" in build
    assert "self.summary_frame" in build
    assert "Начать встречу" in pre
    assert "СТЕНОГРАММА" in live
    assert "ПОДСКАЗКА 1С АНАЛИТИКА" in live
    assert "Встреча завершена" in summary
    assert "Спросить 1С Аналитика…" in ask


def test_live_workspace_is_two_column_cockpit():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp._build_live_workspace)
    assert 'grid_columnconfigure(0, weight=1, uniform="workspace")' in source
    assert 'grid_columnconfigure(1, weight=1, uniform="workspace")' in source
    assert "self.transcript_panel.grid" in source
    assert "self.assistant_panel.grid" in source


def test_compact_mode_hides_transcript_and_keeps_assistant():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp._apply_compact_layout)
    assert 'self.geometry("440x720")' in source
    assert "self.transcript_panel.grid_remove()" in source
    assert 'self.assistant_panel.grid(row=0, column=0' in source
    assert 'self.geometry("1080x760")' in source


def test_readiness_is_user_facing_not_technical_controls():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp._update_readiness)
    assert '"Микрофон"' in source
    assert '"Звук собеседника"' in source
    assert '"Распознавание"' in source
    assert '"ИИ"' in source


def test_transcript_visualization_separates_human_roles_and_hides_ai_duplicates():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp._render_transcript_blocks)
    assert 'role == "ИИ"' in source
    assert 'role == "Собеседник"' in source
    assert 'role == "Я"' in source
    assert '"peer_head"' in source
    assert '"me_head"' in source


def test_assistant_highlights_live_answer_sections():
    heading = inspect.getsource(gui_runtime.MeetingBridgeApp._assistant_heading)
    render = inspect.getsource(gui_runtime.MeetingBridgeApp._show_assistant)
    assert "Что сказать сейчас" in heading
    assert "Что проверить в 1С" in heading
    assert "Что уточнить" in heading
    assert "Разбор" in heading
    assert "assistant_box" in render


def test_summary_has_metrics_tabs_and_local_protocol():
    build = inspect.getsource(gui_runtime.MeetingBridgeApp._build_summary)
    finalize = inspect.getsource(gui_runtime.MeetingBridgeApp._finalize)
    tabs = inspect.getsource(gui_runtime.MeetingBridgeApp._show_summary_tab)
    for label in ("Длительность", "Реплики", "Решения", "Задачи", "Вопросы"):
        assert label in build
    assert "build_protocol" in finalize
    assert "extract_protocol_sections" in finalize
    assert "Протокол сформирован локально" in finalize
    assert "overview" in tabs and "transcript" in tabs


def test_clear_button_clears_persisted_transcript_hint_and_ai_context():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp.clear_transcript_and_hint)
    assert 'path.write_text("", encoding="utf-8")' in source
    assert 'self.transcript.delete("1.0", "end")' in source
    assert 'self.assistant_box.delete("1.0", "end")' in source
    assert "self._auto_watcher.reset()" in source
    assert "self._topic_types = frozenset()" in source
    assert "self._busy or self._auto_busy" in source


def test_activity_status_is_contextual_and_live_timer_updates():
    poll = inspect.getsource(gui_runtime.MeetingBridgeApp._schedule_poll)
    started = inspect.getsource(gui_runtime.MeetingBridgeApp._on_started)
    stopped = inspect.getsource(gui_runtime.MeetingBridgeApp._on_stopped)
    assert "Слушаю встречу" in started
    assert "Встреча завершена" in stopped
    assert "анализирует реплику" in poll
    assert "self._update_timer()" in poll


def test_opening_settings_rescans_hotplugged_audio_devices():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp._toggle_settings)
    assert "self.refresh_devices()" in source
    assert "self._settings_open" in source


def test_start_rescans_when_loopback_is_missing():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp.start_session)
    assert "self.refresh_devices()" in source
    assert "подключите" in source
    assert "super().start_session()" in source


def test_live_audio_health_is_visible_and_capture_errors_are_not_hidden():
    render = inspect.getsource(gui_runtime.MeetingBridgeApp._render_audio_health)
    poll = inspect.getsource(gui_runtime.MeetingBridgeApp._schedule_poll)
    assert "Микрофон" in render
    assert "Собеседник" in render
    assert "сигнал есть" in render
    assert "нет сигнала" in render
    assert "Ошибка звука" in poll
