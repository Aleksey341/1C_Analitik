"""Runtime quality contract for professional 1C Analitik answers.

This module deliberately augments the existing expert prompt instead of replacing
it.  It is installed by the desktop entry points before the GUI starts.
"""
from __future__ import annotations

from dataclasses import replace

from meeting_bridge import llm_client


QUALITY_RESPONSE_STYLE = r"""
КАЧЕСТВО ПРОФЕССИОНАЛЬНОГО ОТВЕТА 1С - ОБЯЗАТЕЛЬНО

1. Граница фактов.
Используй только факты из текущего запроса, человеческого контекста и подключённых
skills. Не добавляй новые числа, сроки, периоды, документы, подразделения, суммы,
количество месяцев или результаты, которых пользователь не сообщал. Например,
если сказано «повторное закрытие месяца», нельзя превращать это в «повторное
закрытие пяти месяцев». Любой новый факт сначала должен быть помечен как гипотеза
или вопрос для проверки.

2. Работа с STT.
STT может искажать профессиональные термины. Если смысл восстанавливается с высокой
уверенностью из контекста, нормализуй термин молча и отвечай по существу. Не цитируй
искажённый STT и не выноси внутреннюю расшифровку распознавания в основной ответ.
Если неоднозначность действительно меняет решение, дай одну короткую оговорку
«Понимаю как ...» либо задай конкретный уточняющий вопрос. Не перегружай ответ
техническими рассуждениями о качестве STT.

3. Сложная диагностика 1С.
Если вопрос требует причин, пошаговой проверки, доказательства, сравнения БУ/НУ,
НЗП, себестоимости, закрытия месяца, распределения затрат или нескольких гипотез,
ответ должен быть прикладным. После короткого вывода пройди каждую существенную
гипотезу по схеме:
- Что открыть;
- Что сравнить;
- Подтверждает: какой конкретный признак подтверждает гипотезу;
- Опровергает: какой конкретный признак её исключает;
- Как исправить: только после подтверждения причины;
- Контроль результата: что должно измениться после исправления.

4. Конкретика в 1С.
Не уходи в формулировки «проверьте настройки», «проверьте регистры» или
«проверьте документы» без маршрута проверки. Называй конкретные пользовательские
объекты, отчёты, документы, операции и аналитики, когда уверен в их существовании
для указанной конфигурации. Если точное имя регистра или технического объекта
зависит от релиза, назови функциональный объект и прямо укажи, что точное имя
регистра может отличаться по релизу. Не используй эту оговорку как повод отказаться
от конкретных шагов в пользовательском интерфейсе 1С.

5. Маршрут диагностики.
Для итоговой суммы или остатка двигайся от результата к источнику:
отчёт/ОСВ -> расшифровка -> статья/аналитика -> правило или база распределения ->
документ/регистратор -> движения -> хозяйственный факт. Для НЗП отдельно установи,
является ли остаток экономически обоснованным незавершённым производством или
следствием неполной/ошибочной документальной цепочки. Для БУ и НУ сначала объясни
причину различия, а не пытайся механически выровнять суммы.

6. Факт, гипотеза, вывод.
Ясно отделяй подтверждённое от предполагаемого. Не формулируй причинность из одного
совпадения. Если данных недостаточно, укажи минимальный набор данных, который
разделит гипотезы. Не придумывай экономический эффект, проводки, регистры или
настройки.

7. Полнота без воды.
На сложный запрос ответь на все части. При ограничении длины сначала сохраняй
диагностическую последовательность и критерии подтверждения/опровержения, а затем
сокращай пояснения. Не обрывай ответ посреди пункта или предложения. Заверши
коротким порядком действий: что проверить первым, вторым и третьим, и что нельзя
менять до подтверждения причины.
""".strip()


_DIAGNOSTIC_MARKERS = (
    "почему",
    "причин",
    "гипотез",
    "диагност",
    "пошаг",
    "что провер",
    "что открыть",
    "подтвержд",
    "опроверг",
    "закрыти",
    "себестоим",
    "нзп",
    "распредел",
    "бу и ну",
    "бу/ну",
    "остаток",
)


def is_complex_diagnostic_request(dialogue: str) -> bool:
    """Return True for cases that need a full evidence-first diagnostic answer."""
    _context, current = llm_client.extract_current_user_turn(dialogue)
    text = (current or dialogue or "").strip()
    low = text.casefold()
    hits = sum(1 for marker in _DIAGNOSTIC_MARKERS if marker in low)
    if len(text) >= 450 and hits >= 2:
        return True
    if llm_client.is_multipart_request(text) and hits >= 2:
        return True
    return hits >= 5 and len(text) >= 220


def quality_ask_auto_reply(dialogue: str, settings: llm_client.LlmSettings) -> str | None:
    """Auto reply with a larger budget only for genuinely complex diagnostics."""
    if not dialogue.strip():
        raise ValueError("Диалог пуст - сначала запишите реплики.")

    instruction = (
        "Нужен ли сейчас ответ от участника «ИИ»?\n"
        "Ответь на ВЕСЬ текущий запрос целиком. Уверен -> полный ответ. "
        "Вероятная трактовка -> с оговоркой. Неясно -> уточни. "
        "Нечего отвечать -> SKIP.\n"
        "Для сложной диагностики обязательно дай конкретную последовательность "
        "проверки в 1С и для каждой существенной гипотезы укажи, что её "
        "подтверждает и что опровергает. Не добавляй факты, которых нет во входе.\n"
        "Если явно просят одну фразу/слово/пункт - соблюдай формат."
    )
    user_content, current, format_guard = llm_client._build_user_packet(
        dialogue,
        manual_question="",
        instruction=instruction,
        max_context_lines=int(settings.max_context_lines),
    )

    complex_case = is_complex_diagnostic_request(dialogue) or is_complex_diagnostic_request(current)
    cap = 2800 if complex_case else 1200
    max_tokens = min(int(settings.max_tokens), cap)
    if format_guard:
        max_tokens = min(max_tokens, 400)

    call_settings = replace(settings, max_tokens=max_tokens)
    raw = llm_client._chat_completion(
        settings=call_settings,
        system_prompt=settings.auto_system_prompt,
        user_content=user_content,
    )
    return llm_client.parse_auto_reply_content(raw)


def install() -> None:
    """Install the quality contract into the user-facing GUI runtime."""
    from meeting_bridge import gui_v2

    if QUALITY_RESPONSE_STYLE not in gui_v2._RESPONSE_STYLE:
        gui_v2._RESPONSE_STYLE = (
            gui_v2._RESPONSE_STYLE.rstrip() + "\n\n" + QUALITY_RESPONSE_STYLE
        )
    gui_v2.ask_auto_reply = quality_ask_auto_reply
