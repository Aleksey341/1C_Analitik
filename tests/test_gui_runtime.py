from __future__ import annotations

import inspect

from meeting_bridge import gui_runtime, gui_v2


def test_runtime_ui_wraps_v2_app():
    assert issubclass(gui_runtime.MeetingBridgeApp, gui_v2.MeetingBridgeApp)


def test_runtime_initializes_bound_vars_before_parent_build():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp._build)
    parent_call = source.index("super()._build()")
    assert source.index("self.auto_reply_var = auto_reply_var") < parent_call
    assert source.index("self.spoken_mode_var = spoken_mode_var") < parent_call
    assert source.rindex("self.auto_reply_var = auto_reply_var") > parent_call
    assert source.rindex("self.spoken_mode_var = spoken_mode_var") > parent_call


def test_first_screen_polish_hides_duplicate_ready_status():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp._apply_user_first_polish)
    assert "Тема встречи (необязательно)" in source
    assert "Спросить 1С Аналитика…" in source
    assert 'text="Отправить"' in source
    assert "self.status_label.pack_forget()" in source
    assert 'self.new_case_btn.configure(state="disabled")' in source


def test_clear_button_is_visible_on_main_screen():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp._apply_user_first_polish)
    assert 'text="Очистить"' in source
    assert "command=self.clear_transcript_and_hint" in source
    assert "self.clear_btn.pack" in source


def test_clear_button_clears_persisted_transcript_hint_and_ai_context():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp.clear_transcript_and_hint)
    assert 'path.write_text("", encoding="utf-8")' in source
    assert 'self.transcript.delete("1.0", "end")' in source
    assert 'self.assistant_box.delete("1.0", "end")' in source
    assert "self._auto_watcher.reset()" in source
    assert "self._topic_types = frozenset()" in source
    assert "self._busy or self._auto_busy" in source


def test_assistant_panel_expands_only_when_answer_arrives():
    initial = inspect.getsource(gui_runtime.MeetingBridgeApp._apply_user_first_polish)
    answer = inspect.getsource(gui_runtime.MeetingBridgeApp._show_assistant)
    assert "height=72" in initial
    assert "Подсказка появится здесь" in initial
    assert "height=165" in answer


def test_activity_status_is_contextual_not_duplicate_ready_text():
    poll = inspect.getsource(gui_runtime.MeetingBridgeApp._schedule_poll)
    started = inspect.getsource(gui_runtime.MeetingBridgeApp._on_started)
    stopped = inspect.getsource(gui_runtime.MeetingBridgeApp._on_stopped)
    assert "Слушаю встречу" in started
    assert "Встреча завершена" in stopped
    assert "Готов к работе" not in poll
    assert "анализирует реплику" in poll


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
