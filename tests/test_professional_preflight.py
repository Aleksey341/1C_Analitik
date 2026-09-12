from __future__ import annotations


def _problem_case() -> str:
    return (
        "1С:ERP 2.5. Мы перечислили аванс поставщику. После закрытия месяца остались "
        "60.01, 60.02 и 76.АВ, а в книге покупок часть авансового НДС восстановилась. "
        "Сформируй итоговый порядок проверки из 10 шагов."
    )


def test_detects_supplier_advance_subaccount_mismatch():
    from meeting_bridge.professional_preflight import (
        detect_professional_consistency_hints,
    )

    hints = detect_professional_consistency_hints(_problem_case())
    joined = "\n".join(hints)

    assert "76.АВ" in joined
    assert "76.ВА" in joined
    assert "выданным авансам" in joined


def test_detects_purchase_vs_sales_book_restoration_mismatch():
    from meeting_bridge.professional_preflight import (
        detect_professional_consistency_hints,
    )

    joined = "\n".join(detect_professional_consistency_hints(_problem_case()))

    assert "книгой покупок" in joined
    assert "книгу продаж" in joined
    assert "восстановление" in joined


def test_does_not_flag_76av_for_received_customer_advance():
    from meeting_bridge.professional_preflight import (
        detect_professional_consistency_hints,
    )

    text = (
        "Покупатель перечислил нам аванс. На 76.АВ отражен НДС с полученного аванса. "
        "Нужно проверить книгу продаж."
    )

    assert detect_professional_consistency_hints(text) == []


def test_exact_count_is_hard_constraint():
    from meeting_bridge.professional_preflight import detect_exact_count_hint

    hint = detect_exact_count_hint(
        "Сформируй итоговый порядок проверки из 10 шагов и укажи момент исправления."
    )

    assert hint is not None
    assert "ровно 10" in hint
    assert "пункт 11" in hint


def test_preflight_combines_domain_and_count_checks():
    from meeting_bridge.professional_preflight import build_professional_preflight

    block = build_professional_preflight(_problem_case())

    assert block is not None
    assert block.startswith("ПРОФЕССИОНАЛЬНАЯ ПРЕДПРОВЕРКА")
    assert "76.ВА" in block
    assert "книгу продаж" in block
    assert "ровно 10" in block
    assert "Несоответствие в условии" in block


def test_prepend_is_idempotent():
    from meeting_bridge.professional_preflight import prepend_professional_preflight

    base = "ТЕКУЩИЙ ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n" + _problem_case()
    once = prepend_professional_preflight(base, _problem_case())
    twice = prepend_professional_preflight(once, _problem_case())

    assert once == twice
    assert once.count("ПРОФЕССИОНАЛЬНАЯ ПРЕДПРОВЕРКА") == 1


def test_style_requires_input_validation_and_exact_format():
    from meeting_bridge.professional_preflight import PROFESSIONAL_PREFLIGHT_STYLE

    low = PROFESSIONAL_PREFLIGHT_STYLE.casefold()
    assert "проверка постановки задачи" in low
    assert "книга покупок/книга продаж" in low
    assert "несоответствие в условии" in low
    assert "ровно n" in low
    assert "не добавляй n+1" in low
