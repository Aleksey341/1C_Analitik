from __future__ import annotations

import inspect

from meeting_bridge.auto_reply import AutoReplyWatcher
from meeting_bridge.catchup_boundary_runtime import build_catchup_dialogue
from meeting_bridge.llm_client import extract_current_user_turn


def _me(sec: int, text: str) -> str:
    return f"[22:08:{sec:02d}] Я: {text}"


def _peer(sec: int, text: str) -> str:
    return f"[22:08:{sec:02d}] Собеседник: {text}"


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


def test_catchup_packet_makes_only_new_turns_the_current_request():
    first = _me(9, "почему после закрытия месяца остался счет 25")
    second = _me(24, "перепроведем месяц должно исправиться")
    third = _me(33, "60.01 и 60.02 сходятся по общей сумме значит все нормально")
    blocks = [first, second, third, _ai(42, "подробный ответ про счет 25")]

    dialogue = build_catchup_dialogue(
        blocks,
        after_peer_line=first,
        max_context_blocks=40,
    )
    context, current = extract_current_user_turn(dialogue)

    assert "счет 25" in context
    assert "почему после закрытия" not in current
    assert "перепроведем месяц" in current
    assert "60.01 и 60.02" in current
    assert "Ответь только на эти новые реплики" in current


def test_catchup_packet_keeps_all_new_human_roles_after_boundary():
    first = _me(9, "первый вопрос")
    second = _peer(20, "а если просто перепровести")
    third = _me(25, "и сверка по общей сумме сходится")
    blocks = [first, second, third, _ai(35)]

    dialogue = build_catchup_dialogue(
        blocks,
        after_peer_line=first,
        max_context_blocks=40,
    )
    _context, current = extract_current_user_turn(dialogue)

    assert "Собеседник: а если просто перепровести" in current
    assert "Я: и сверка по общей сумме сходится" in current
    assert "первый вопрос" not in current


def test_catchup_packet_falls_back_safely_when_boundary_is_missing():
    blocks = [_me(9, "первый вопрос"), _me(20, "новый вопрос")]

    dialogue = build_catchup_dialogue(
        blocks,
        after_peer_line="[00:00:00] Я: отсутствующая граница",
        max_context_blocks=40,
    )

    assert dialogue == "\n\n".join(blocks)


def test_runtime_queues_catchup_and_boundary_runtime_focuses_next_request():
    from meeting_bridge.gui_runtime import MeetingBridgeApp
    from meeting_bridge.catchup_boundary_runtime import install

    manual = inspect.getsource(MeetingBridgeApp._on_ai_ok)
    automatic = inspect.getsource(MeetingBridgeApp._on_auto_ok)
    helper = inspect.getsource(MeetingBridgeApp._queue_live_catchup)
    boundary_install = inspect.getsource(install)

    assert "_queue_live_catchup" in manual
    assert "_queue_live_catchup" in automatic
    assert "queue_catchup" in helper
    assert "latest == answered" in helper
    assert "catchup_after_peer_line" in boundary_install
    assert "build_catchup_dialogue" in boundary_install
    assert 'decision.reason == "catch_up"' in boundary_install
