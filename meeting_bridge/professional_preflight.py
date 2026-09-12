"""Professional consistency checks for 1C Analitik user requests.

The checks are intentionally conservative. They do not replace the LLM's domain
reasoning; they add high-confidence warnings when the current request contains a
likely accounting/1C contradiction or an explicit output-count constraint.
"""
from __future__ import annotations

import re


_PREFLIGHT_MARKER = "ПРОФЕССИОНАЛЬНАЯ ПРЕДПРОВЕРКА"
_INSTALLED = False

PROFESSIONAL_PREFLIGHT_STYLE = r"""
8. Проверка постановки задачи до диагностики.
Перед основным ответом проверь внутреннюю непротиворечивость текущего запроса:
роль организации в операции, счет/субсчет, вид аванса, направление расчетов,
книга покупок/книга продаж, БУ/НУ/НДС, период хозяйственного факта и тип документа.
Не принимай профессиональный термин пользователя или STT как истинный только потому,
что он написан уверенно. Если видишь вероятное несоответствие, сначала коротко назови
его в блоке «Несоответствие в условии». Затем предложи наиболее вероятную трактовку.
Если от трактовки меняется решение и безопасно продолжить нельзя, задай один точный
уточняющий вопрос. Не молча подменяй исходное условие и не строй большой разбор на
противоречивой предпосылке.

9. Жесткое соблюдение явно заданного формата.
Если пользователь просит ровно N шагов, пунктов, строк или вариантов, дай ровно N.
Не добавляй N+1 как отдельный нумерованный «контрольный» шаг. Контроль результата,
риски и оговорки включай внутрь запрошенного количества либо после списка без новой
нумерации. Явное количество пользователя важнее привычного шаблона ответа.

10. Проверка гипотез без экспериментов в рабочей базе.
Не предлагай менять документы, аналитику, правила распределения, настройки, даты,
регламентные операции или движения в рабочей базе «на пробу», чтобы посмотреть,
изменится ли результат, а затем вернуть изменение обратно. Такой эксперимент может
исказить данные, зависимые расчеты и закрытые периоды и не является доказательством
причины. Сначала докажи гипотезу чтением отчетов, расшифровок, регистраторов,
движений, первичных документов и настроек. Если для подтверждения нужен проверочный
перерасчет или изменение данных, рекомендуй копию базы, тестовый контур или иной
изолированный стенд. В рабочей базе исправляй только подтвержденный первоисточник,
после фиксации исходного состояния, оценки зависимостей и понимания ожидаемого
результата. Не советуй «изменить и вернуть», «перепровести на пробу» или
«перенастроить и посмотреть» в PROD.

11. Сначала проверь природу счета или объекта учета.
Перед тем как объяснять остаток, сальдо, оборот или незакрытую сумму как нормальную,
сначала установи назначение соответствующего бухгалтерского счета или объекта учета:
может ли он в стандартной методологии иметь конечное сальдо после завершения
регламентного закрытия, где экономически должен оставаться НЗП и не перепутан ли
бухгалтерский счет с управленческим регистром, отчетом или другой аналитикой ERP.
Не нормализуй необычный остаток только потому, что существует НЗП или незавершенный
заказ. Сначала проверь, на каком именно счете/объекте это НЗП должно отражаться.

Для счета 25 это особенно важно: если речь именно о бухгалтерском счете 25
«Общепроизводственные расходы» после закрытия месяца, не называй его конечное сальдо
нормальным НЗП без проверки. В стандартной схеме счет 25 является
собирательно-распределительным и его расходы распределяются на производственные
счета/объекты затрат; обоснованное НЗП анализируется уже на соответствующих объектах
производственных затрат. Сначала проверь, действительно ли это БУ-счет 25, не
используется ли нетиповой план счетов/методология и почему сумма не распределилась.
""".strip()


def _norm(text: str) -> str:
    value = (text or "").casefold().replace("ё", "е")
    value = value.replace("–", "-").replace("—", "-")
    return " ".join(value.split())


def _supplier_advance_context(text: str) -> bool:
    q = _norm(text)
    buyer_side = any(
        marker in q
        for marker in (
            "поставщик",
            "поставщику",
            "перечислен аванс",
            "перечислены авансы",
            "выданный аванс",
            "выданные авансы",
            "аванс поставщику",
            "предоплата поставщику",
            "оплата поставщику",
        )
    )
    advance = "аванс" in q or "предоплат" in q
    return buyer_side and advance


def _account_25_closing_context(text: str) -> bool:
    """High-confidence trigger for an ending balance on BU account 25."""
    q = _norm(text)
    has_account_25 = bool(re.search(r"(?<!\d)25(?!\d)", q)) and any(
        marker in q for marker in ("счет", "счете", "счета", "осв")
    )
    has_balance = any(marker in q for marker in ("остат", "сальдо", "не закрыл", "не закрыт"))
    after_close = any(
        marker in q
        for marker in (
            "после закрытия",
            "закрытие месяца",
            "закрытия месяца",
            "закрыли месяц",
            "закрыт месяц",
            "конечное сальдо",
        )
    )
    return has_account_25 and has_balance and after_close


def detect_professional_consistency_hints(text: str) -> list[str]:
    """Return high-confidence domain warnings for the current request only."""
    q = _norm(text)
    hints: list[str] = []
    supplier_advance = _supplier_advance_context(text)

    has_76av = bool(re.search(r"(?<!\d)76\s*[.\-/ ]?\s*ав(?![а-я])", q))
    has_76va = bool(re.search(r"(?<!\d)76\s*[.\-/ ]?\s*ва(?![а-я])", q))

    if supplier_advance and has_76av and not has_76va:
        hints.append(
            "В условии указан 76.АВ в контексте аванса поставщику. Проверь субсчет: "
            "для НДС по выданным авансам обычно используется 76.ВА, тогда как 76.АВ "
            "относится к НДС по полученным авансам. Не строй диагностику на 76.АВ как "
            "на выданном авансе без явной проверки фактического субсчета в базе."
        )

    purchase_book = "книг" in q and "покуп" in q
    restore_vat = "восстанов" in q and ("ндс" in q or "аванс" in q)
    if supplier_advance and purchase_book and restore_vat:
        hints.append(
            "В условии восстановление НДС с выданного аванса связано с книгой покупок. "
            "Проверь направление: первоначальный вычет авансового НДС у покупателя "
            "связан с книгой покупок, а восстановление ранее принятого к вычету НДС "
            "при зачете аванса обычно отражается через книгу продаж. Если пользователь "
            "называет книгу покупок, сначала укажи несоответствие и проверь фактический "
            "регистр/отчет, а не принимай формулировку как доказанный факт."
        )

    if _account_25_closing_context(text):
        hints.append(
            "В условии есть конечный остаток по бухгалтерскому счету 25 после закрытия "
            "месяца. Сначала проверь природу счета: в стандартной методологии счет 25 "
            "является собирательно-распределительным и его конечное сальдо после "
            "завершенного закрытия не следует автоматически объяснять нормальным НЗП. "
            "НЗП может быть экономически обоснованным, но нужно установить, на каком "
            "производственном счете/объекте затрат оно должно оставаться. Проверь, что "
            "речь действительно о БУ-счете 25, а не об управленческом регистре/отчете, "
            "и нет ли нетиповой методологии или плана счетов. Только после этого "
            "диагностируй базу распределения, аналитику и регистратор остатка."
        )

    return hints


_EXACT_COUNT_PATTERNS = (
    re.compile(
        r"(?:сформируй|составь|дай|представь|подготовь|итогов\w*\s+порядок)"
        r".{0,120}?(?:из\s+|ровно\s+)?(\d{1,2})\s+(шаг(?:ов|а)?|пункт(?:ов|а)?)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"(?:порядок|список|план)\s+(?:проверки\s+)?из\s+(\d{1,2})\s+"
        r"(шаг(?:ов|а)?|пункт(?:ов|а)?)",
        re.IGNORECASE,
    ),
)


def detect_exact_count_hint(text: str) -> str | None:
    """Return an exact-count instruction only when the user explicitly asked for it."""
    raw = text or ""
    for pattern in _EXACT_COUNT_PATTERNS:
        match = pattern.search(raw)
        if not match:
            continue
        count = int(match.group(1))
        noun = match.group(2).casefold()
        if count <= 0 or count > 50:
            continue
        unit = "шагов" if "шаг" in noun else "пунктов"
        return (
            f"ЖЕСТКОЕ КОЛИЧЕСТВО: пользователь запросил ровно {count} {unit}. "
            f"Дай ровно {count} нумерованных {unit}; не добавляй пункт {count + 1}. "
            "Контроль результата и оговорки включи внутрь этих пунктов либо после списка "
            "без дополнительной нумерации."
        )
    return None


def build_professional_preflight(text: str) -> str | None:
    """Build an LLM-facing preflight block for the current request."""
    hints = detect_professional_consistency_hints(text)
    exact_count = detect_exact_count_hint(text)
    if not hints and not exact_count:
        return None

    lines = [
        _PREFLIGHT_MARKER + ":",
        "Перед основным ответом проверь постановку задачи, а не принимай все ее "
        "термины и предпосылки как истинные автоматически.",
    ]
    for hint in hints:
        lines.append("- " + hint)
    if exact_count:
        lines.append("- " + exact_count)
    lines.append(
        "Если предупреждение подтверждается, начни ответ с короткого блока "
        "«Несоответствие в условии» и только затем продолжай диагностику. Если от "
        "трактовки зависит решение и безопасно продолжить нельзя, задай один конкретный "
        "уточняющий вопрос. Не выдумывай исправление исходного условия молча."
    )
    return "\n".join(lines)


def prepend_professional_preflight(user_content: str, current_request: str) -> str:
    """Prepend preflight once; safe to call from both manual and auto pipelines."""
    if _PREFLIGHT_MARKER in (user_content or ""):
        return user_content
    block = build_professional_preflight(current_request)
    if not block:
        return user_content
    return block + "\n\n" + user_content


def install() -> None:
    """Install preflight into both manual and automatic AI request paths."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from meeting_bridge import gui_v2, llm_client

    if PROFESSIONAL_PREFLIGHT_STYLE not in gui_v2._RESPONSE_STYLE:
        gui_v2._RESPONSE_STYLE = (
            gui_v2._RESPONSE_STYLE.rstrip() + "\n\n" + PROFESSIONAL_PREFLIGHT_STYLE
        )

    original_build_user_packet = llm_client._build_user_packet

    def _build_user_packet_with_preflight(*args, **kwargs):  # noqa: ANN002, ANN003
        user_content, current, format_guard = original_build_user_packet(*args, **kwargs)
        user_content = prepend_professional_preflight(user_content, current)
        return user_content, current, format_guard

    llm_client._build_user_packet = _build_user_packet_with_preflight
