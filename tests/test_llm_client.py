from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from meeting_bridge.auto_reply import AutoReplyWatcher
from meeting_bridge.llm_client import (
    LlmSettings,
    ask_auto_reply,
    ask_meeting_reply,
    parse_auto_reply_content,
    resolve_api_key,
)
from meeting_bridge.writer import append_transcript_line, read_recent_dialogue


def test_wants_spoken_reply_triggers():
    from meeting_bridge.llm_client import wants_spoken_reply

    assert wants_spoken_reply("что ответить собеседнику?")
    assert wants_spoken_reply("", spoken_mode=True)
    assert not wants_spoken_reply("разбери расхождение себестоимости")


def test_resolve_api_key_prefers_inline():
    settings = LlmSettings(api_key="sk-inline", api_key_env="OPENAI_API_KEY")
    assert resolve_api_key(settings) == "sk-inline"


def test_resolve_api_key_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    settings = LlmSettings(api_key="", api_key_env="OPENAI_API_KEY")
    assert resolve_api_key(settings) == "sk-env"


def test_resolve_api_key_when_pasted_into_env_field():
    settings = LlmSettings(api_key="", api_key_env="sk-proj-ABC123")
    assert resolve_api_key(settings) == "sk-proj-ABC123"


def test_ask_meeting_reply_posts_chat_completions(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings = LlmSettings(api_key="", model="gpt-test", base_url="https://example.com/v1")

    response_body = {
        "choices": [{"message": {"content": "Предлагаю сказать так: согласен."}}]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_body).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch(
        "meeting_bridge.llm_client.urllib.request.urlopen", return_value=mock_resp
    ) as mocked:
        text = ask_meeting_reply(
            "[10:00:00] Я: привет\n[10:00:05] Собеседник: как дела?",
            settings,
            user_question="Что ответить?",
        )

    assert "согласен" in text
    req = mocked.call_args[0][0]
    assert req.full_url == "https://example.com/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer sk-test"
    payload = json.loads(req.data.decode("utf-8"))
    assert payload["model"] == "gpt-test"
    assert "привет" in payload["messages"][1]["content"]


def test_ask_meeting_reply_requires_key():
    with pytest.raises(RuntimeError, match="API-ключ"):
        ask_meeting_reply(
            "диалог", LlmSettings(api_key="", api_key_env="MISSING_KEY_XYZ")
        )


def test_parse_auto_reply_skip():
    assert parse_auto_reply_content("SKIP") is None
    assert parse_auto_reply_content("skip") is None
    assert parse_auto_reply_content("SKIP\nлишнее") is None
    assert parse_auto_reply_content("Да, согласен.") == "Да, согласен."


def test_ssl_cert_error_retries_without_verify(monkeypatch: pytest.MonkeyPatch):
    import ssl
    import urllib.error

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings = LlmSettings(api_key="", base_url="https://example.com/v1", ssl_verify=True)

    response_body = {"choices": [{"message": {"content": "Ок."}}]}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_body).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    calls: list[bool] = []

    def fake_urlopen(req, timeout=60, context=None):
        verify = getattr(context, "check_hostname", True) and (
            getattr(context, "verify_mode", ssl.CERT_REQUIRED) != ssl.CERT_NONE
        )
        calls.append(bool(verify))
        if verify:
            raise urllib.error.URLError(
                ssl.SSLCertVerificationError("certificate has expired")
            )
        return mock_resp

    with patch(
        "meeting_bridge.llm_client.urllib.request.urlopen", side_effect=fake_urlopen
    ):
        text = ask_meeting_reply("[10:00:00] Собеседник: привет", settings)

    assert text == "Ок."
    assert calls == [True, False]


def test_ask_auto_reply_returns_none_on_skip(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings = LlmSettings(api_key="", base_url="https://example.com/v1")
    response_body = {"choices": [{"message": {"content": "SKIP"}}]}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_body).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch(
        "meeting_bridge.llm_client.urllib.request.urlopen", return_value=mock_resp
    ):
        assert ask_auto_reply("[10:00:00] Собеседник: угу", settings) is None


def test_append_and_read_recent_dialogue(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    append_transcript_line(path, "Я", "первая")
    append_transcript_line(path, "Собеседник", "вторая")
    append_transcript_line(path, "ИИ", "третья")
    dialogue = read_recent_dialogue(path, max_lines=2)
    assert "первая" not in dialogue
    assert "вторая" in dialogue
    assert "ИИ" in dialogue


def test_multiline_ai_reply_kept_as_one_block(tmp_path: Path):
    from meeting_bridge.writer import iter_dialogue_blocks

    path = tmp_path / "live-transcript.md"
    append_transcript_line(
        path,
        "ИИ",
        "Вступление.\n\n### Часть 1\n- пункт\n\n### Часть 2\n- ещё",
    )
    raw = path.read_text(encoding="utf-8")
    blocks = iter_dialogue_blocks(raw)
    assert len(blocks) == 1
    assert "### Часть 1" in blocks[0]
    assert "### Часть 2" in blocks[0]
    recent = read_recent_dialogue(path, max_lines=5)
    assert "### Часть 2" in recent


def test_auto_reply_watcher_debounce_and_cancel():
    w = AutoReplyWatcher()
    peer = "[10:00:01] Собеседник: какой статус?"
    d1 = w.observe([peer], pause_sec=2.5, now=100.0, reply_on_me=False)
    assert d1.reason == "debounce_start"
    assert not d1.should_request

    d2 = w.observe([peer], pause_sec=2.5, now=101.0, reply_on_me=False)
    assert d2.reason == "waiting"
    assert not d2.should_request

    d3 = w.observe([peer], pause_sec=2.5, now=103.0, reply_on_me=False)
    assert d3.should_request
    assert d3.peer_line == peer

    # Без reply_on_me реплика «Я» отменяет автоответ на собеседника.
    w2 = AutoReplyWatcher()
    w2.observe([peer], pause_sec=2.5, now=100.0, reply_on_me=False)
    cancel = w2.observe(
        [peer, "[10:00:05] Я: сейчас расскажу"],
        pause_sec=2.5,
        now=101.0,
        reply_on_me=False,
    )
    assert cancel.reason == "user_speaking"
    assert not cancel.should_request


def test_auto_reply_watcher_answers_my_question_when_enabled():
    w = AutoReplyWatcher()
    mine = "[10:00:01] Я: почему отрицательные остатки?"
    w.observe([mine], pause_sec=2.0, now=1.0, reply_on_me=True)
    ready = w.observe([mine], pause_sec=2.0, now=4.0, reply_on_me=True)
    assert ready.should_request
    assert ready.peer_line == mine


def test_auto_reply_watcher_waits_for_second_part():
    w = AutoReplyWatcher()
    part1 = "[10:00:01] Я: первый вопрос про нзп"
    part2 = "[10:00:20] Я: и второе как отличить партии"
    w.observe([part1], pause_sec=3.0, now=1.0, reply_on_me=True)
    # Новая часть сбрасывает debounce.
    mid = w.observe([part1, part2], pause_sec=3.0, now=2.0, reply_on_me=True)
    assert mid.reason == "debounce_start"
    ready = w.observe([part1, part2], pause_sec=3.0, now=6.0, reply_on_me=True)
    assert ready.should_request
    assert ready.peer_line == part2


def test_auto_reply_watcher_no_repeat_after_mark():
    w = AutoReplyWatcher()
    peer = "[10:00:01] Собеседник: вопрос?"
    w.observe([peer], pause_sec=1.0, now=1.0, reply_on_me=False)
    ready = w.observe([peer], pause_sec=1.0, now=3.0, reply_on_me=False)
    assert ready.should_request
    assert w.in_flight
    # Пока in_flight — повторный poll не стартует второй запрос.
    blocked = w.observe([peer], pause_sec=1.0, now=4.0, reply_on_me=False)
    assert blocked.reason == "in_flight"
    w.mark_answered(peer)
    again = w.observe([peer], pause_sec=1.0, now=10.0, reply_on_me=False)
    assert again.reason == "already_answered"
    assert not again.should_request


def test_literal_commands_block_in_system_prompt():
    from meeting_bridge.expert_prompt import DEFAULT_SYSTEM_PROMPT

    assert "АПЕЛЬСИН-731" in DEFAULT_SYSTEM_PROMPT
    assert "Ответь только одним словом" in DEFAULT_SYSTEM_PROMPT
    assert "Ограничение формата действует только для ТЕКУЩЕГО сообщения" in DEFAULT_SYSTEM_PROMPT


def test_multipart_and_echo_guards_in_system_prompt():
    from meeting_bridge.expert_prompt import DEFAULT_SYSTEM_PROMPT

    assert "МНОГОЧАСТНЫЕ ВОПРОСЫ" in DEFAULT_SYSTEM_PROMPT
    assert "не отвечай только на последний вопрос" in DEFAULT_SYSTEM_PROMPT
    assert 'вопрос вида "Правильно ли...?" сам по себе НЕ означает' in DEFAULT_SYSTEM_PROMPT


def test_inventory_adjustment_period_guard_in_system_prompt():
    from meeting_bridge.expert_prompt import DEFAULT_SYSTEM_PROMPT

    assert "ПЕРИОД И РАСПРЕДЕЛЕНИЕ СУММЫ — РАЗНЫЕ ВОПРОСЫ" in DEFAULT_SYSTEM_PROMPT
    assert "ДАТА ДОКУМЕНТА ≠ АВТОМАТИЧЕСКИ ДАТА ФАКТА" in DEFAULT_SYSTEM_PROMPT
    assert "ПОСЛЕДУЮЩИЕ СОБЫТИЯ И ИЗМЕНЕНИЕ УСЛОВИЙ" in DEFAULT_SYSTEM_PROMPT
    assert "условия уже существовали на отчётную дату" in DEFAULT_SYSTEM_PROMPT


def test_diagnostic_chain_not_checklist_in_system_prompt():
    from meeting_bridge.expert_prompt import DEFAULT_SYSTEM_PROMPT

    assert "ДИАГНОСТИЧЕСКАЯ ЦЕПОЧКА 1С" in DEFAULT_SYSTEM_PROMPT
    assert "Что этот факт подтверждает?" in DEFAULT_SYSTEM_PROMPT
    assert "Что этот факт исключает?" in DEFAULT_SYSTEM_PROMPT
    assert 'Не используй слово "восстановление НДС"' in DEFAULT_SYSTEM_PROMPT


def test_fx_advances_block_in_system_prompt():
    from meeting_bridge.expert_prompt import DEFAULT_SYSTEM_PROMPT

    assert "АВАНСЫ В ИНОСТРАННОЙ ВАЛЮТЕ" in DEFAULT_SYSTEM_PROMPT
    assert "какой объект реально переоценивается" in DEFAULT_SYSTEM_PROMPT
    assert "Если переоцениваемого объекта нет" in DEFAULT_SYSTEM_PROMPT
    assert "дату таможенной декларации" in DEFAULT_SYSTEM_PROMPT


def test_bu_nu_vat_and_document_date_blocks_in_system_prompt():
    from meeting_bridge.expert_prompt import DEFAULT_SYSTEM_PROMPT

    assert "БУ, НУ И НДС — ТРИ ОТДЕЛЬНЫХ КОНТУРА" in DEFAULT_SYSTEM_PROMPT
    assert "НДС — НАЗЫВАЙ ТОЧНЫЙ МЕХАНИЗМ" in DEFAULT_SYSTEM_PROMPT
    assert "восстановлением авансового НДС" in DEFAULT_SYSTEM_PROMPT
    assert "обратной реализацией" in DEFAULT_SYSTEM_PROMPT
    assert "НЕ ВЫДУМЫВАЙ ОБЪЕКТЫ 1С" in DEFAULT_SYSTEM_PROMPT
    assert "ЕСЛИ В КЕЙСЕ ЕСТЬ АВАНС — ПРОВЕРЬ НДС ОТДЕЛЬНО" in DEFAULT_SYSTEM_PROMPT
    assert "ОС, РЕМОНТ И КАПИТАЛЬНЫЕ ВЛОЖЕНИЯ" in DEFAULT_SYSTEM_PROMPT


def test_explicit_format_priority_in_system_prompt():
    from meeting_bridge.expert_prompt import DEFAULT_SYSTEM_PROMPT

    assert "МНОГОЧАСТНЫЕ ВОПРОСЫ" in DEFAULT_SYSTEM_PROMPT
    assert "КАК РАБОТАТЬ С ТЕКСТОМ И STT" in DEFAULT_SYSTEM_PROMPT
    assert "ВНУТРЕННЯЯ ПРОВЕРКА ПЕРЕД ОТВЕТОМ" in DEFAULT_SYSTEM_PROMPT
    assert DEFAULT_SYSTEM_PROMPT.index("КАК РАБОТАТЬ С ТЕКСТОМ И STT") < DEFAULT_SYSTEM_PROMPT.index(
        "МНОГОЧАСТНЫЕ ВОПРОСЫ"
    )
    assert "ПЕРИОД И РАСПРЕДЕЛЕНИЕ СУММЫ — РАЗНЫЕ ВОПРОСЫ" in DEFAULT_SYSTEM_PROMPT
    assert '→ сначала только "Да" или "Нет"' not in DEFAULT_SYSTEM_PROMPT
    assert "→ сначала только «Да» или «Нет»" not in DEFAULT_SYSTEM_PROMPT


def test_system_prompt_v2_is_compact():
    from meeting_bridge.expert_prompt import DEFAULT_SYSTEM_PROMPT
    from meeting_bridge.llm_client import estimate_tokens

    # v2 должен быть в разы компактнее прежних ~25k токенов.
    assert len(DEFAULT_SYSTEM_PROMPT) < 25_000
    assert estimate_tokens(DEFAULT_SYSTEM_PROMPT) < 10_000


def test_detect_explicit_format_one_phrase():
    from meeting_bridge.llm_client import detect_explicit_format

    guard = detect_explicit_format(
        "Какой факт самый важный для периода? Ответь одной фразой."
    )
    assert guard is not None
    assert "ОДНО предложение" in guard
    assert detect_explicit_format("Разбери кейс полностью") is None


def test_detect_explicit_format_ignores_bare_yes_no_question():
    from meeting_bridge.llm_client import detect_explicit_format, detect_multipart_hint

    case = (
        "1. Что произошло?\n"
        "2. Как проверить в ERP?\n"
        "3. Какие нормы?\n"
        "4. Куда отнести сумму?\n"
        "5. Нужно ли трогать декабрь?\n"
        "6. Правильно ли это делать сразу?\n"
    )
    assert detect_explicit_format(case) is None
    assert detect_multipart_hint(case) is not None
    assert detect_explicit_format("Ответь только да или нет.") is not None


def test_detect_period_vs_allocation_hint():
    from meeting_bridge.llm_client import detect_period_vs_allocation_hint

    hint = detect_period_vs_allocation_hint(
        "Какой факт самый важный для определения правильного периода "
        "корректировки стоимости? Ответь одной фразой."
    )
    assert hint is not None
    assert "ПЕРИОД" in hint
    assert "8,6 млн" in hint
    assert "состояние партии" in hint.casefold()
    assert detect_period_vs_allocation_hint("Как настроить регистр?") is None


def test_compact_dialogue_skips_bulky_ai():
    from meeting_bridge.llm_client import _compact_dialogue_for_short_reply

    case = "[10:00:00] Собеседник: длинный кейс про запасы"
    bulky = "[10:00:01] ИИ: " + ("ВЫВОД: состояние партии. " * 80)
    ask = (
        "[10:00:02] Я: Какой факт важен для периода корректировки стоимости? "
        "Ответь одной фразой."
    )
    raw = "\n\n".join([case, bulky, ask])
    compact = _compact_dialogue_for_short_reply(raw, max_blocks=6)
    assert ask in compact
    assert case in compact
    assert "ВЫВОД: состояние партии." not in compact


def test_extract_current_user_turn_merges_consecutive_questions():
    from meeting_bridge.llm_client import extract_current_user_turn

    dialogue = (
        "[10:00:00] Собеседник: привет\n"
        "[10:00:01] Я: Сколько будет 2+2?\n"
        "[10:00:02] Я: Сколько будет 3+3?\n"
        "[10:00:03] Я: Сколько будет 4+4?"
    )
    context, current = extract_current_user_turn(dialogue)
    assert "привет" in context
    assert "2+2" in current
    assert "3+3" in current
    assert "4+4" in current
    assert current.count("?") == 3


def test_extract_current_user_turn_keeps_multiline_block():
    from meeting_bridge.llm_client import extract_current_user_turn

    dialogue = (
        "[10:00:01] Я: Сколько будет 2+2?\n"
        "Сколько будет 3+3?\n"
        "Сколько будет 4+4?"
    )
    _context, current = extract_current_user_turn(dialogue)
    assert "2+2" in current and "3+3" in current and "4+4" in current


def test_build_user_packet_sends_all_three_math_questions(tmp_path: Path):
    from meeting_bridge.llm_client import _build_user_packet

    dialogue = (
        "[10:00:01] Я: Сколько будет 2+2?\n"
        "[10:00:02] Я: Сколько будет 3+3?\n"
        "[10:00:03] Я: Сколько будет 4+4?"
    )
    log = tmp_path / "llm-debug.log"
    # Monkeypatch log path via writing after build — inspect content directly.
    user_content, current, _fg = _build_user_packet(dialogue)
    assert "ТЕКУЩИЙ ЗАПРОС ПОЛЬЗОВАТЕЛЯ" in user_content
    assert "2+2" in user_content
    assert "3+3" in user_content
    assert "4+4" in user_content
    assert "2+2" in current and "3+3" in current and "4+4" in current
    # Must not look like only the last question was sent.
    assert user_content.index("2+2") < user_content.index("4+4")
    _ = log


def test_build_user_packet_manual_question_not_truncated():
    from meeting_bridge.llm_client import _build_user_packet

    dialogue = "[10:00:01] Я: старый текст"
    manual = "Ответь на все три пункта:\n1. Столица России?\n2. Столица Франции?\n3. Столица Италии?"
    user_content, current, _fg = _build_user_packet(
        dialogue, manual_question=manual
    )
    assert current == manual
    assert "Столица России" in user_content
    assert "Столица Франции" in user_content
    assert "Столица Италии" in user_content


def test_ask_meeting_reply_user_content_includes_all_questions(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings = LlmSettings(api_key="", model="gpt-test", base_url="https://example.com/v1")
    captured: dict[str, str] = {}

    def fake_chat(*, settings, system_prompt, user_content, retries=2):  # noqa: ANN001
        captured["user_content"] = user_content
        return "4 / 6 / 8"

    monkeypatch.setattr("meeting_bridge.llm_client._chat_completion", fake_chat)
    dialogue = (
        "[10:00:01] Я: Сколько будет 2+2?\n"
        "[10:00:02] Я: Сколько будет 3+3?\n"
        "[10:00:03] Я: Сколько будет 4+4?"
    )
    reply = ask_meeting_reply(dialogue, settings)
    assert reply == "4 / 6 / 8"
    content = captured["user_content"]
    assert "2+2" in content and "3+3" in content and "4+4" in content
    assert "ТЕКУЩИЙ ЗАПРОС ПОЛЬЗОВАТЕЛЯ" in content


def test_fit_max_tokens_keeps_request_under_tpm_budget():
    from meeting_bridge.expert_prompt import DEFAULT_SYSTEM_PROMPT
    from meeting_bridge.llm_client import estimate_tokens, fit_max_tokens

    user = "Кейс " * 2000  # крупный пользовательский текст
    fitted = fit_max_tokens(DEFAULT_SYSTEM_PROMPT, user, desired=1000)
    total = (
        estimate_tokens(DEFAULT_SYSTEM_PROMPT)
        + estimate_tokens(user)
        + fitted
    )
    assert fitted <= 1000
    assert fitted >= 1
    assert total <= 29_500
    # После сжатия v2 для крупного кейса ответный бюджет ~1000 должен проходить.
    assert fitted == 1000


def test_format_http_error_request_too_large():
    from meeting_bridge.llm_client import _format_http_error

    msg = _format_http_error(
        429,
        'Request too large for gpt-4o ... Requested 30982. Limit 30000.',
        system_tokens=25000,
        user_tokens=3000,
        max_tokens=3500,
    )
    assert "слишком большой" in msg
    assert "Пауза не поможет" in msg
    assert "system≈25000" in msg


def test_format_http_error_model_access_forbidden():
    from meeting_bridge.llm_client import _format_http_error

    msg = _format_http_error(
        403,
        (
            '{"error":{"message":"Project \'proj_ABC\' does not have access '
            "to model 'gpt-4o'\",\"code\":\"model_not_found\"}}"
        ),
    )
    assert "Нет доступа к модели «gpt-4o»" in msg
    assert "proj_ABC" in msg
    assert "gpt-4o-mini" in msg

