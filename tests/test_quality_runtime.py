from __future__ import annotations

from meeting_bridge.llm_client import LlmSettings


def _complex_dialogue() -> str:
    return (
        "[20:25:00] Я: 1С:ERP 2.5. После закрытия месяца на счёте 25 остался "
        "существенный остаток, часть затрат 20 счёта осталась в НЗП, фактическая "
        "себестоимость выше плановой, а БУ и НУ различаются. Закрытие прошло без "
        "красных ошибок. По одному подразделению выпуск был, по другому не было. "
        "Дай пошаговую диагностику: для каждой причины укажи, что открыть в 1С, "
        "что сравнить, что подтверждает гипотезу, что её опровергает и как исправить "
        "без искажения хозяйственных операций. Назови конкретные объекты там, где "
        "уверен, и отдельно объясни, как отличить корректное НЗП от ошибки распределения."
    )


def test_quality_style_forbids_invented_facts_and_stt_noise():
    from meeting_bridge.quality_runtime import QUALITY_RESPONSE_STYLE

    assert "не добавляй новые числа" in QUALITY_RESPONSE_STYLE.casefold()
    assert "пять месяцев" in QUALITY_RESPONSE_STYLE
    assert "не цитируй искажённый STT" in QUALITY_RESPONSE_STYLE
    assert "Понимаю как" in QUALITY_RESPONSE_STYLE


def test_quality_style_requires_proof_for_each_hypothesis():
    from meeting_bridge.quality_runtime import QUALITY_RESPONSE_STYLE

    for phrase in (
        "Что открыть",
        "Что сравнить",
        "Подтверждает",
        "Опровергает",
        "Как исправить",
    ):
        assert phrase in QUALITY_RESPONSE_STYLE
    assert "конкретные пользовательские объекты" in QUALITY_RESPONSE_STYLE
    assert "точное имя регистра" in QUALITY_RESPONSE_STYLE


def test_complex_diagnostic_detection():
    from meeting_bridge.quality_runtime import is_complex_diagnostic_request

    assert is_complex_diagnostic_request(_complex_dialogue())
    assert not is_complex_diagnostic_request("[10:00:00] Я: Что такое НЗП?")


def test_complex_auto_reply_gets_full_output_budget(monkeypatch):
    from meeting_bridge import llm_client
    from meeting_bridge.quality_runtime import quality_ask_auto_reply

    captured: dict[str, int | str] = {}

    def fake_chat(*, settings, system_prompt, user_content, retries=2):  # noqa: ANN001
        captured["max_tokens"] = int(settings.max_tokens)
        captured["user_content"] = user_content
        return "Полный диагностический ответ"

    monkeypatch.setattr(llm_client, "_chat_completion", fake_chat)
    settings = LlmSettings(api_key="x", max_tokens=3000)

    reply = quality_ask_auto_reply(_complex_dialogue(), settings)

    assert reply == "Полный диагностический ответ"
    assert captured["max_tokens"] >= 2400
    assert "ТЕКУЩИЙ ЗАПРОС ПОЛЬЗОВАТЕЛЯ" in str(captured["user_content"])


def test_simple_auto_reply_keeps_compact_budget(monkeypatch):
    from meeting_bridge import llm_client
    from meeting_bridge.quality_runtime import quality_ask_auto_reply

    captured: dict[str, int] = {}

    def fake_chat(*, settings, system_prompt, user_content, retries=2):  # noqa: ANN001
        captured["max_tokens"] = int(settings.max_tokens)
        return "Коротко"

    monkeypatch.setattr(llm_client, "_chat_completion", fake_chat)
    settings = LlmSettings(api_key="x", max_tokens=3000)

    assert quality_ask_auto_reply("[10:00:00] Я: Что такое НЗП?", settings) == "Коротко"
    assert captured["max_tokens"] <= 1200
