from __future__ import annotations

import inspect

from meeting_bridge.auto_reply import AutoReplyWatcher


def _me(sec: int, text: str) -> str:
    return f"[22:08:{sec:02d}] Я: {text}"


def _ai(sec: int, text: str = "старый ответ") -> str:
    return f"[22:08:{sec:02d}] ИИ: {text}"


def test_catchup_fires_immediately_after_stale_ai_reply():
    watcher = AutoReplyWatcher()
    first = _me(9, "почему остался счет 25")
    second = _me(24, "перепроведем месяц")
    third = _me(33, "60.01 и 60.02 сходятся значит все нормально")

    watcher.mark_answered(first)
    watcher.queue_catchup(third)

    decision = watcher.observe(
        [first, second, third, _ai(42)],
        pause_sec=4.0,
        now=100.0,
        reply_on_me=True,
    )

    assert decision.should_request is True
    assert decision.reason == "catch_up"
    assert decision.peer_line == third
    assert watcher.in_flight is True


def test_catchup_uses_newest_turn_if_more_speech_arrived_after_queueing():
    watcher = AutoReplyWatcher()
    first = _me(9, "первый вопрос")
    queued = _me(24, "новая реплика")
    newest = _me(33, "еще более новая реплика")

    watcher.mark_answered(first)
    watcher.queue_catchup(queued)

    decision = watcher.observe(
        [first, queued, _ai(30), newest],
        pause_sec=4.0,
        now=100.0,
        reply_on_me=True,
    )

    assert decision.should_request is True
    assert decision.reason == "catch_up"
    assert decision.peer_line == newest


def test_historical_ai_reply_does_not_retrigger_without_explicit_catchup():
    watcher = AutoReplyWatcher()
    human = _me(9, "старый вопрос")

    decision = watcher.observe(
        [human, _ai(20)],
        pause_sec=4.0,
        now=100.0,
        reply_on_me=True,
    )

    assert decision.should_request is False
    assert decision.reason == "ai_already"
    assert watcher.answered_peer_line == human


def test_runtime_queues_catchup_after_manual_and_auto_completions():
    from meeting_bridge.gui_runtime import MeetingBridgeApp

    manual = inspect.getsource(MeetingBridgeApp._on_ai_ok)
    automatic = inspect.getsource(MeetingBridgeApp._on_auto_ok)
    helper = inspect.getsource(MeetingBridgeApp._queue_live_catchup)

    assert "_queue_live_catchup" in manual
    assert "_queue_live_catchup" in automatic
    assert "queue_catchup" in helper
    assert "latest == answered" in helper
