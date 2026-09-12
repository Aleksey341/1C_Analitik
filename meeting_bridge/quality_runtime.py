"""Runtime quality contract for professional 1C Analitik answers.

This module augments the existing expert prompt and adds a resilient completion
runtime for long diagnostic answers. It is installed by desktop entry points
before the GUI starts.
"""
from __future__ import annotations

from dataclasses import replace
import json
import time
import urllib.error
import urllib.request

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

_MAX_CONTINUATIONS = 3
_CONTINUATION_TAIL_CHARS = 9000
_ORIGINAL_REQUEST_CHARS = 16000
_INSTALLED = False


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


def _looks_cut_off(text: str) -> bool:
    """Fallback when a compatible gateway omits ``finish_reason``."""
    value = (text or "").rstrip()
    if len(value) < 800:
        return False
    if value.upper() == "SKIP":
        return False
    last_line = value.splitlines()[-1].strip() if value.splitlines() else value
    if last_line.startswith("#"):
        return True
    return value[-1] not in ".!?…;)]}\"'`|"


def _needs_continuation(text: str, finish_reason: str | None) -> bool:
    reason = (finish_reason or "").casefold()
    if reason == "length":
        return True
    if reason == "stop":
        return False
    if reason:
        return False
    return _looks_cut_off(text)


def _trim_cutoff_fragment(text: str) -> str:
    """Remove only the visibly broken final line before asking for continuation."""
    value = (text or "").rstrip()
    if not value:
        return value
    lines = value.splitlines()
    if not lines:
        return value
    last = lines[-1].strip()
    if not last:
        return value
    if last.endswith((".", "!", "?", "…", ";", ")", "]", "}", "|", "```")):
        return value
    if last.startswith("#") or len(last) >= 8:
        return "\n".join(lines[:-1]).rstrip()
    return value


def _strip_continuation_preamble(text: str) -> str:
    value = (text or "").strip()
    lines = value.splitlines()
    if lines and lines[0].strip().casefold() in {
        "продолжение",
        "продолжение:",
        "продолжаю",
        "продолжаю:",
    }:
        return "\n".join(lines[1:]).lstrip()
    return value


def _merge_without_duplicate(base: str, extra: str) -> str:
    base = (base or "").rstrip()
    extra = _strip_continuation_preamble(extra)
    if not base:
        return extra
    if not extra:
        return base

    base_lines = base.splitlines()
    extra_lines = extra.splitlines()
    max_overlap = min(10, len(base_lines), len(extra_lines))
    overlap = 0
    for size in range(max_overlap, 0, -1):
        left = [line.strip() for line in base_lines[-size:]]
        right = [line.strip() for line in extra_lines[:size]]
        if left == right:
            overlap = size
            break
    if overlap:
        extra = "\n".join(extra_lines[overlap:]).lstrip()
    if not extra:
        return base
    return base + "\n\n" + extra


def _single_chat_completion(
    *,
    settings: llm_client.LlmSettings,
    system_prompt: str,
    user_content: str,
    retries: int = 2,
) -> tuple[str, str | None]:
    """One OpenAI-compatible request, preserving ``finish_reason``."""
    api_key = llm_client.resolve_api_key(settings)
    if not api_key:
        raise RuntimeError(
            "Не задан API-ключ нейросети.\n\n"
            "В config.yaml укажите llm.api_key или переменную окружения "
            f"{settings.api_key_env}."
        )

    max_tokens = llm_client.fit_max_tokens(
        system_prompt, user_content, int(settings.max_tokens)
    )
    sys_tok = llm_client.estimate_tokens(system_prompt)
    user_tok = llm_client.estimate_tokens(user_content)
    payload = {
        "model": settings.model,
        "reasoning_effort": "none",
        "max_completion_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    url = f"{settings.base_url.rstrip('/')}/chat/completions"
    last_http: urllib.error.HTTPError | None = None
    last_detail = ""

    for attempt in range(retries + 1):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            try:
                body = llm_client._urlopen_json(
                    request,
                    timeout=settings.timeout_sec,
                    verify=settings.ssl_verify,
                )
            except urllib.error.URLError as exc:
                if settings.ssl_verify and llm_client._is_ssl_cert_error(exc):
                    body = llm_client._urlopen_json(
                        request,
                        timeout=settings.timeout_sec,
                        verify=False,
                    )
                else:
                    raise
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_http = exc
            last_detail = detail
            if exc.code == 429 and attempt < retries:
                if llm_client._is_request_too_large(detail):
                    match = llm_client._TPM_REQUESTED_RE.search(detail)
                    if match:
                        requested = int(match.group(1))
                        limit = int(match.group(2))
                        overflow = requested - limit + 200
                        max_tokens = max(
                            256,
                            int(payload["max_completion_tokens"]) - overflow,
                        )
                    else:
                        max_tokens = max(
                            256,
                            int(payload["max_completion_tokens"]) // 2,
                        )
                    payload["max_completion_tokens"] = max_tokens
                    continue
                time.sleep(llm_client._retry_after_seconds(exc, detail))
                continue
            raise RuntimeError(
                llm_client._format_http_error(
                    exc.code,
                    detail,
                    system_tokens=sys_tok,
                    user_tokens=user_tok,
                    max_tokens=int(payload["max_completion_tokens"]),
                )
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Не удалось связаться с LLM (сеть/SSL).\n"
                f"{exc.reason}\n\n"
                "Если ошибка про certificate/SSL - в config.yaml поставьте "
                "llm.ssl_verify: false (обход проверки сертификата)."
            ) from exc
    else:
        assert last_http is not None
        raise RuntimeError(
            llm_client._format_http_error(
                last_http.code,
                last_detail,
                system_tokens=sys_tok,
                user_tokens=user_tok,
                max_tokens=int(payload["max_completion_tokens"]),
            )
        ) from last_http

    try:
        choice = body["choices"][0]
        content = choice["message"]["content"]
        finish_reason = choice.get("finish_reason")
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Неожиданный ответ LLM: {body!r}") from exc
    text = str(content).strip()
    if not text:
        raise RuntimeError("Нейросеть вернула пустой ответ.")
    return text, str(finish_reason) if finish_reason is not None else None


def _continuation_prompt(original_user_content: str, answer: str) -> str:
    request_tail = original_user_content[-_ORIGINAL_REQUEST_CHARS:]
    answer_tail = answer[-_CONTINUATION_TAIL_CHARS:]
    return (
        "ИСХОДНЫЙ ЗАПРОС И КОНТЕКСТ (хвост, достаточный для продолжения):\n"
        f"{request_tail}\n\n"
        "УЖЕ СФОРМИРОВАННЫЙ ОТВЕТ (последняя часть):\n"
        f"{answer_tail}\n\n"
        "Ответ был оборван по техническому лимиту. Продолжи СТРОГО с места, "
        "где остановился смысл. Не повторяй уже написанные причины, шаги, таблицы "
        "или заголовки. Если последний фрагмент оборван, восстанови только этот "
        "фрагмент и продолжай дальше. Доведи ответ до логического конца. Обязательно "
        "заверши итоговым порядком действий. Не пиши вступление «Продолжение»."
    )


def complete_with_auto_continue(
    *,
    settings: llm_client.LlmSettings,
    system_prompt: str,
    user_content: str,
    retries: int = 2,
) -> str:
    """Return one complete answer, automatically continuing when it is truncated."""
    text, finish_reason = _single_chat_completion(
        settings=settings,
        system_prompt=system_prompt,
        user_content=user_content,
        retries=retries,
    )
    if not _needs_continuation(text, finish_reason):
        return text

    answer = _trim_cutoff_fragment(text)
    current_finish = finish_reason
    for _index in range(_MAX_CONTINUATIONS):
        if not _needs_continuation(answer, current_finish):
            break
        continuation_settings = replace(
            settings,
            max_tokens=min(max(2200, int(settings.max_tokens)), 3200),
        )
        extra, current_finish = _single_chat_completion(
            settings=continuation_settings,
            system_prompt=system_prompt,
            user_content=_continuation_prompt(user_content, answer),
            retries=retries,
        )
        if _needs_continuation(extra, current_finish):
            extra = _trim_cutoff_fragment(extra)
        answer = _merge_without_duplicate(answer, extra)

    return answer.strip()


def quality_ask_auto_reply(dialogue: str, settings: llm_client.LlmSettings) -> str | None:
    """Auto reply with a larger first-pass budget for complex diagnostics."""
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
        "Не дублируй один и тот же материал в разделах «Причины» и «Что проверить»: "
        "лучше объединяй гипотезу сразу с проверкой и доказательствами.\n"
        "Если явно просят одну фразу/слово/пункт - соблюдай формат."
    )
    user_content, current, format_guard = llm_client._build_user_packet(
        dialogue,
        manual_question="",
        instruction=instruction,
        max_context_lines=int(settings.max_context_lines),
    )

    complex_case = is_complex_diagnostic_request(dialogue) or is_complex_diagnostic_request(current)
    if complex_case:
        max_tokens = min(max(int(settings.max_tokens), 4800), 6000)
    else:
        max_tokens = min(int(settings.max_tokens), 1200)
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
    """Install quality prompt and resilient completion into the user-facing GUI."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from meeting_bridge import gui_v2

    if QUALITY_RESPONSE_STYLE not in gui_v2._RESPONSE_STYLE:
        gui_v2._RESPONSE_STYLE = (
            gui_v2._RESPONSE_STYLE.rstrip() + "\n\n" + QUALITY_RESPONSE_STYLE
        )

    llm_client._chat_completion = complete_with_auto_continue
    gui_v2.ask_auto_reply = quality_ask_auto_reply
