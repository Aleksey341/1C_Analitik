from __future__ import annotations

from meeting_bridge.llm_client import LlmSettings


def test_detects_finish_reason_length():
    from meeting_bridge.quality_runtime import _needs_continuation

    assert _needs_continuation("Готовый фрагмент.", "length")
    assert not _needs_continuation("Готовый ответ.", "stop")


def test_fallback_detects_visible_cutoff_without_finish_reason():
    from meeting_bridge.quality_runtime import _needs_continuation

    broken = ("Подробная диагностика. " * 80) + "Сопоставьте направления в трёх точ"
    assert _needs_continuation(broken, None)


def test_trim_removes_only_broken_final_line():
    from meeting_bridge.quality_runtime import _trim_cutoff_fragment

    text = "## Шаг 4\nПроверка завершена.\n\n## Шаг 5\nСопоставьте направления в трёх точ"
    trimmed = _trim_cutoff_fragment(text)
    assert trimmed.endswith("## Шаг 5")
    assert "трёх точ" not in trimmed


def test_auto_continuation_merges_without_broken_fragment(monkeypatch):
    from meeting_bridge import quality_runtime

    calls = []
    responses = iter(
        [
            (
                "## Шаг 4\nПроверка завершена.\n\n## Шаг 5\n"
                "Сопоставьте направления в трёх точ",
                "length",
            ),
            (
                "Сопоставьте направления в трёх точках: расход, выпуск и база.\n\n"
                "## Итоговый порядок действий\n1. ОСВ.\n2. Статья расходов.\n3. Выпуск и НЗП.",
                "stop",
            ),
        ]
    )

    def fake_single(*, settings, system_prompt, user_content, retries=2):  # noqa: ANN001
        calls.append(user_content)
        return next(responses)

    monkeypatch.setattr(quality_runtime, "_single_chat_completion", fake_single)
    settings = LlmSettings(api_key="x", max_tokens=3000)
    result = quality_runtime.complete_with_auto_continue(
        settings=settings,
        system_prompt="system",
        user_content="сложный запрос",
    )

    assert len(calls) == 2
    assert "трёх точ\n" not in result
    assert "трёх точках" in result
    assert "Итоговый порядок действий" in result


def test_continuation_prompt_forbids_repeating_previous_sections():
    from meeting_bridge.quality_runtime import _continuation_prompt

    prompt = _continuation_prompt("исходный вопрос", "уже написанный ответ")
    assert "Не повторяй" in prompt
    assert "Доведи ответ до логического конца" in prompt
    assert "Не пиши вступление «Продолжение»" in prompt


def test_complex_auto_reply_raises_first_pass_budget(monkeypatch):
    from meeting_bridge import llm_client, quality_runtime

    captured: dict[str, int] = {}

    def fake_chat(*, settings, system_prompt, user_content, retries=2):  # noqa: ANN001
        captured["max_tokens"] = int(settings.max_tokens)
        return "Полный ответ."

    monkeypatch.setattr(llm_client, "_chat_completion", fake_chat)
    dialogue = (
        "[20:25:00] Я: 1С:ERP 2.5. После закрытия месяца на счёте 25 остался "
        "остаток, часть затрат 20 счёта осталась в НЗП, себестоимость выше плановой, "
        "БУ и НУ различаются. Почему это произошло? Дай пошаговую диагностику, "
        "что проверить, что подтверждает и что опровергает каждую гипотезу. "
        "Нужно проверить распределение, выпуск и закрытие месяца подробно."
    )
    settings = LlmSettings(api_key="x", max_tokens=3000)
    reply = quality_runtime.quality_ask_auto_reply(dialogue, settings)

    assert reply == "Полный ответ."
    assert captured["max_tokens"] >= 4800
