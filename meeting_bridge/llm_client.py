"""OpenAI-compatible LLM client for in-app meeting replies."""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

from meeting_bridge.expert_prompt import (
    DEFAULT_AUTO_SYSTEM_PROMPT,
    DEFAULT_SPOKEN_SYSTEM_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
)

# Re-export for config.py and tests.
__all__ = [
    "DEFAULT_AUTO_SYSTEM_PROMPT",
    "DEFAULT_SPOKEN_SYSTEM_PROMPT",
    "DEFAULT_SYSTEM_PROMPT",
    "LlmSettings",
    "ask_auto_reply",
    "ask_meeting_reply",
    "build_ssl_context",
    "detect_explicit_format",
    "detect_multipart_hint",
    "estimate_tokens",
    "extract_current_user_turn",
    "fit_max_tokens",
    "is_multipart_request",
    "parse_auto_reply_content",
    "resolve_api_key",
    "wants_spoken_reply",
    "write_llm_debug_log",
]

_RETRY_AFTER_RE = re.compile(r"try again in ([0-9]+(?:\.[0-9]+)?)s", re.I)


@dataclass(frozen=True)
class LlmSettings:
    enabled: bool = True
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    model: str = "gpt-4o"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    auto_system_prompt: str = DEFAULT_AUTO_SYSTEM_PROMPT
    spoken_system_prompt: str = DEFAULT_SPOKEN_SYSTEM_PROMPT
    timeout_sec: int = 120
    max_context_lines: int = 40
    max_tokens: int = 1000
    auto_reply: bool = False
    auto_reply_pause_sec: float = 4.0
    # Отвечать и на реплики «Я:» (удобно, когда вопросы диктуете сами).
    auto_reply_on_me: bool = True
    # Режим короткой реплики для созвона (2–4 предложения).
    spoken_mode: bool = False
    # False — обход битых/прокси-сертификатов (антивирус, корпоративный MITM).
    ssl_verify: bool = True


def wants_spoken_reply(user_question: str, *, spoken_mode: bool = False) -> bool:
    if spoken_mode:
        return True
    q = user_question.casefold()
    triggers = (
        "что ответить",
        "что сказать",
        "как ответить",
        "как сказать",
        "реплика",
        "вслух",
    )
    return any(t in q for t in triggers)


def _latest_user_text(dialogue: str, user_question: str = "") -> str:
    """Full current user turn (not only the last «?» sentence)."""
    if user_question.strip():
        return user_question.strip()
    _context, current = extract_current_user_turn(dialogue)
    return current


_BLOCK_HEAD_RE = re.compile(
    r"^\[(\d{2}):(\d{2}):(\d{2})\]\s+([^:]+):\s*(.*)$"
)


def _block_role_and_body(block: str) -> tuple[str | None, str]:
    lines = block.splitlines()
    if not lines:
        return None, ""
    match = _BLOCK_HEAD_RE.match(lines[0])
    if not match:
        return None, block
    role = match.group(4).strip()
    first = match.group(5)
    rest = "\n".join(lines[1:])
    if rest:
        body = f"{first}\n{rest}" if first else rest
    else:
        body = first
    return role, body


def extract_current_user_turn(dialogue: str) -> tuple[str, str]:
    """Split dialogue into ``(context, current_request)``.

    Current request = trailing contiguous human blocks of the same role
    (``Я`` / ``Собеседник``), after skipping trailing ``ИИ`` answers.
    Never splits a block by ``?`` / ``.`` / newlines — the whole turn goes through.
    Consecutive same-role finals (STT pause between questions) are merged.
    """
    from meeting_bridge.writer import iter_dialogue_blocks

    blocks = iter_dialogue_blocks(dialogue)
    if not blocks:
        return "", ""

    end = len(blocks)
    while end > 0:
        role, _body = _block_role_and_body(blocks[end - 1])
        if role == "ИИ":
            end -= 1
            continue
        break
    if end == 0:
        return dialogue.strip(), ""

    role, _body = _block_role_and_body(blocks[end - 1])
    if role not in ("Я", "Собеседник"):
        return "\n\n".join(blocks[:end]).strip(), ""

    start = end - 1
    while start > 0:
        prev_role, _prev_body = _block_role_and_body(blocks[start - 1])
        if prev_role != role:
            break
        start -= 1

    current_blocks = blocks[start:end]
    context_blocks = blocks[:start] + blocks[end:]
    bodies = [_block_role_and_body(b)[1].strip() for b in current_blocks]
    current = "\n".join(b for b in bodies if b).strip()
    context = "\n\n".join(context_blocks).strip()
    return context, current


def write_llm_debug_log(
    *,
    raw_dialogue: str,
    current_user_block: str,
    llm_user_content: str,
    path: Path | None = None,
) -> Path:
    """Temporary diagnostic log proving the request is not truncated."""
    log_path = path or Path("llm-debug.log")
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    text = (
        f"===== {stamp} =====\n"
        f"RAW DIALOGUE:\n{raw_dialogue}\n\n"
        f"CURRENT USER BLOCK:\n{current_user_block}\n\n"
        f"LLM USER CONTENT:\n{llm_user_content}\n\n"
    )
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        pass
    return log_path


def is_multipart_request(text: str) -> bool:
    """Heuristic: multi-question / multi-task user message."""
    raw = text or ""
    q = raw.casefold()
    if not q.strip():
        return False
    question_marks = raw.count("?") + raw.count("？")
    if question_marks >= 2:
        return True
    numbered = 0
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s[0].isdigit() and ("." in s[:4] or ")" in s[:4] or ":" in s[:4]):
            numbered += 1
        elif s[:2] in ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."):
            numbered += 1
    if numbered >= 2:
        return True
    cues = (
        "вопросы:",
        "вопрос 1",
        "вопрос 2",
        "дополнительн",
        "нужно ли",
        "правильно ли",
    )
    hits = sum(1 for c in cues if c in q)
    if hits >= 2 and len(raw) > 400:
        return True
    if "вопросы помощнику" in q or "вопросы:" in q:
        return True
    return False


def detect_explicit_format(text: str) -> str | None:
    """Return a hard format reminder only for EXPLICIT format commands."""
    q = (text or "").casefold()
    if not q:
        return None
    # Multi-part professional cases always win over short-format heuristics.
    if is_multipart_request(text):
        return None
    if (
        "ответь одной фразой" in q
        or "ответь одну фразу" in q
        or "одной фразой" in q
        or "одну фразу" in q
        or "одним предложением" in q
    ):
        return (
            "ЖЁСТКИЙ ФОРМАТ: ровно ОДНО предложение. "
            "Без разделов ВЫВОД/ПОЧЕМУ/ГДЕ ПРОВЕРИТЬ/КАК ДОКАЗАТЬ/ЧТО ДЕЛАТЬ/РИСК. "
            "Без повтора предыдущего разбора."
        )
    if (
        "ответь одним словом" in q
        or "одним словом" in q
        or "одно слово" in q
    ):
        return (
            "ЖЁСТКИЙ ФОРМАТ: ровно ОДНО слово. "
            "Без пояснений и без диагностического шаблона."
        )
    if "только вывод" in q or "дай только вывод" in q:
        return (
            "ЖЁСТКИЙ ФОРМАТ: только вывод, без объяснений и без шаблона разделов."
        )
    if "ответь только на" in q or "ответь на пункт" in q or "только на вопрос" in q:
        return (
            "ЖЁСТКИЙ ФОРМАТ: ответь только на указанный пункт/вопрос, "
            "без разбора остальных."
        )
    if "коротко" in q and (
        "ответь" in q or "ответ" in q or q.strip().startswith("коротко")
    ):
        return (
            "ЖЁСТКИЙ ФОРМАТ: краткий ответ без полного диагностического шаблона."
        )
    # Only EXPLICIT yes/no command — never bare «правильно ли…?»
    if (
        "ответь только да или нет" in q
        or "ответь да или нет" in q
        or "только да или нет" in q
    ):
        return "ЖЁСТКИЙ ФОРМАТ: только «Да» или «Нет», без пояснений."
    return None


def detect_multipart_hint(text: str) -> str | None:
    if not is_multipart_request(text):
        return None
    return (
        "МНОГОЧАСТНЫЙ ЗАПРОС: ответь на ВСЕ части текущего сообщения. "
        "Нельзя ответить только на последний вопрос. "
        "Вопрос вида «Правильно ли…?» внутри кейса — это обычный пункт, "
        "а НЕ команда «ответь только да/нет». "
        "Сначала краткий общий вывод, затем ответы по номерам."
    )

def detect_period_vs_allocation_hint(text: str) -> str | None:
    """Steer away from 'состояние партии' when the question is about period."""
    q = (text or "").casefold()
    if "период" not in q:
        return None
    if not any(x in q for x in ("корректир", "стоимост", "признан")):
        return None
    return (
        "СОДЕРЖАНИЕ (критично): вопрос про ПЕРИОД признания (А), не про распределение (Б).\n"
        "Главный факт для периода: существовала ли окончательная стоимость уже на "
        "отчётную дату и лишь подтверждена позже, либо обязательство возникло в новом "
        "периоде. Состояние партии = только «куда отнести сумму», НЕ период.\n"
        "Запрещено отвечать: «состояние партии на момент УПД».\n"
        "Образец одной фразы: «Главный факт — существовала ли окончательная стоимость "
        "8,6 млн ₽ уже на 31 декабря и была лишь подтверждена январским УПД, либо "
        "обязательство по этой стоимости возникло только в январе.»\n"
        "Проверка: если изменить этот факт, изменится ли вывод о периоде? "
        "Если факт влияет только на распределение — он не главный."
    )


def _compact_dialogue_for_short_reply(dialogue: str, *, max_blocks: int = 6) -> str:
    """Keep recent context but drop long prior AI dumps that bias the model."""
    blocks = [b for b in dialogue.split("\n\n") if b.strip()]
    filtered: list[str] = []
    for block in blocks:
        head = block.splitlines()[0] if block else ""
        if "] ИИ:" in head and len(block) > 600:
            continue
        filtered.append(block)
    if not filtered:
        return dialogue.strip()
    if len(filtered) > max_blocks:
        filtered = filtered[-max_blocks:]
    return "\n\n".join(filtered)


def resolve_api_key(settings: LlmSettings) -> str:
    if settings.api_key.strip():
        return settings.api_key.strip()
    env_name = settings.api_key_env.strip() or "OPENAI_API_KEY"
    # Частая ошибка: ключ вставили в api_key_env вместо имени переменной.
    if env_name.startswith(("sk-", "sk-proj-", "gsk_", "xai-")):
        return env_name
    return (os.environ.get(env_name) or "").strip()


def parse_auto_reply_content(content: str) -> str | None:
    """Return reply text, or None when model chooses SKIP."""
    text = (content or "").strip()
    if not text:
        return None
    first = text.splitlines()[0].strip()
    if first.upper() == "SKIP" or text.upper() == "SKIP":
        return None
    if first.upper().startswith("SKIP ") or first.upper().startswith("SKIP:"):
        return None
    return text


def build_ssl_context(*, verify: bool) -> ssl.SSLContext:
    if not verify:
        return ssl._create_unverified_context()
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _is_ssl_cert_error(exc: BaseException) -> bool:
    text = str(exc).upper()
    return "CERTIFICATE" in text or "SSL" in text


def _urlopen_json(request: urllib.request.Request, *, timeout: int, verify: bool) -> dict:
    context = build_ssl_context(verify=verify)
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def _retry_after_seconds(exc: urllib.error.HTTPError, detail: str) -> float:
    header = exc.headers.get("Retry-After") if exc.headers else None
    if header:
        try:
            return max(1.0, float(header))
        except ValueError:
            pass
    match = _RETRY_AFTER_RE.search(detail)
    if match:
        return max(1.0, float(match.group(1)))
    return 20.0


# TPM soft budget for gpt-4o tier ~30k. OpenAI counts input + max_tokens.
_DEFAULT_TPM_BUDGET = 29_500
# Cyrillic-heavy text ≈ 2.55–2.7 chars/token; slightly conservative.
_CHARS_PER_TOKEN = 2.55

_TPM_REQUESTED_RE = re.compile(
    r"Requested\s+(\d+).*?Limit\s+(\d+)",
    re.IGNORECASE | re.DOTALL,
)


def estimate_tokens(text: str) -> int:
    """Rough token estimate for RU/EN mixed prompts (no tiktoken dependency)."""
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def fit_max_tokens(
    system_prompt: str,
    user_content: str,
    desired: int,
    *,
    tpm_budget: int = _DEFAULT_TPM_BUDGET,
    minimum: int = 256,
) -> int:
    """Clamp max_tokens so input+output reservation stays under TPM budget."""
    used = estimate_tokens(system_prompt) + estimate_tokens(user_content)
    room = int(tpm_budget) - used
    if room <= 0:
        # Вход уже на грани/сверх бюджета — всё равно пробуем короткий ответ.
        return minimum
    return max(minimum, min(int(desired), room)) if room >= minimum else room


def _is_request_too_large(detail: str) -> bool:
    low = detail.lower()
    return "request too large" in low or "must be reduced" in low


def _format_http_error(
    code: int,
    detail: str,
    *,
    system_tokens: int | None = None,
    user_tokens: int | None = None,
    max_tokens: int | None = None,
) -> str:
    if code == 403 and (
        "does not have access to model" in detail
        or "model_not_found" in detail
    ):
        model = ""
        match = re.search(r"model '([^']+)'", detail)
        if match:
            model = match.group(1)
        project = ""
        match = re.search(r"Project '([^']+)'", detail)
        if match:
            project = match.group(1)
        bits = [
            f"Нет доступа к модели «{model or 'указанной'}» (HTTP 403).",
        ]
        if project:
            bits.append(f"Проект OpenAI: {project}.")
        bits.append(
            "В platform.openai.com → Project → Limits / Models "
            "включите эту модель для проекта ключа, "
            "либо в config.yaml смените llm.model "
            "(например gpt-4o-mini)."
        )
        return " ".join(bits)
    if code == 429:
        if _is_request_too_large(detail):
            sizes = ""
            if system_tokens is not None and user_tokens is not None and max_tokens is not None:
                total = system_tokens + user_tokens + max_tokens
                sizes = (
                    f"Оценка: system≈{system_tokens}, user≈{user_tokens}, "
                    f"max_tokens={max_tokens}, сумма≈{total}. "
                )
            return (
                "Запрос слишком большой для лимита TPM (HTTP 429). "
                f"{sizes}"
                "Пауза не поможет — нужен меньший промпт/кейс или меньший max_tokens. "
                f"Детали: {detail[:220]}"
            )
        wait = 20.0
        match = _RETRY_AFTER_RE.search(detail)
        if match:
            wait = float(match.group(1))
        return (
            f"Лимит OpenAI (HTTP 429, TPM). Подождите ~{int(wait) + 1} с и повторите. "
            "Между тяжёлыми запросами нужна пауза (лимит тарифа ~30k TPM). "
            f"Детали: {detail[:220]}"
        )
    return f"LLM HTTP {code}: {detail[:500]}"


def _chat_completion(
    *,
    settings: LlmSettings,
    system_prompt: str,
    user_content: str,
    retries: int = 2,
) -> str:
    api_key = resolve_api_key(settings)
    if not api_key:
        raise RuntimeError(
            "Не задан API-ключ нейросети.\n\n"
            "В config.yaml укажите llm.api_key или переменную окружения "
            f"{settings.api_key_env}."
        )

    max_tokens = fit_max_tokens(
        system_prompt, user_content, int(settings.max_tokens)
    )
    sys_tok = estimate_tokens(system_prompt)
    user_tok = estimate_tokens(user_content)

    payload = {
        "model": settings.model,
        "reasoning_effort": "none",
        "max_completion_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    base = settings.base_url.rstrip("/")
    url = f"{base}/chat/completions"

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
                body = _urlopen_json(
                    request, timeout=settings.timeout_sec, verify=settings.ssl_verify
                )
            except urllib.error.URLError as exc:
                # Антивирус/прокси часто ломают цепочку сертификатов.
                if settings.ssl_verify and _is_ssl_cert_error(exc):
                    body = _urlopen_json(
                        request, timeout=settings.timeout_sec, verify=False
                    )
                else:
                    raise
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_http = exc
            last_detail = detail
            if exc.code == 429 and attempt < retries:
                if _is_request_too_large(detail):
                    # Shrink output reservation using API's Requested/Limit numbers.
                    match = _TPM_REQUESTED_RE.search(detail)
                    if match:
                        requested = int(match.group(1))
                        limit = int(match.group(2))
                        overflow = requested - limit + 200
                        max_tokens = max(256, int(payload["max_completion_tokens"]) - overflow)
                    else:
                        max_tokens = max(256, int(payload["max_completion_tokens"]) // 2)
                    payload["max_completion_tokens"] = max_tokens
                    continue
                time.sleep(_retry_after_seconds(exc, detail))
                continue
            raise RuntimeError(
                _format_http_error(
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
                "Если ошибка про certificate/SSL — в config.yaml поставьте "
                "llm.ssl_verify: false (обход проверки сертификата)."
            ) from exc
    else:
        assert last_http is not None
        raise RuntimeError(
            _format_http_error(
                last_http.code,
                last_detail,
                system_tokens=sys_tok,
                user_tokens=user_tok,
                max_tokens=int(payload["max_completion_tokens"]),
            )
        ) from last_http

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Неожиданный ответ LLM: {body!r}") from exc
    text = str(content).strip()
    if not text:
        raise RuntimeError("Нейросеть вернула пустой ответ.")
    return text



def _human_only_dialogue_context(text: str) -> str:
    """Keep human context after the latest case boundary; exclude previous AI answers."""
    from meeting_bridge.writer import iter_dialogue_blocks

    if not text.strip():
        return ""

    blocks = iter_dialogue_blocks(text)
    if not blocks:
        return text.strip()

    # Find the latest persistent case boundary.
    # GUI button writes:
    #   role = "System" (Russian)
    #   body = "New case" (Russian)
    #
    # A human phrase explicitly starting a new case is also a boundary.
    start_index = 0

    for index, block in enumerate(blocks):
        role, body = _block_role_and_body(block)

        button_boundary = (
            role == "\u0421\u0438\u0441\u0442\u0435\u043c\u0430"
            and body.strip().casefold()
            == "\u041d\u043e\u0432\u044b\u0439 \u043a\u0435\u0439\u0441".casefold()
        )

        human_boundary = (
            role in (
                "\u042f",
                "\u0421\u043e\u0431\u0435\u0441\u0435\u0434\u043d\u0438\u043a",
            )
            and _is_explicit_new_case(body)
        )

        if button_boundary:
            # The marker itself is not useful context.
            start_index = index + 1
        elif human_boundary:
            # Keep the human block because it can contain the new case facts.
            start_index = index

    kept = []

    for block in blocks[start_index:]:
        role, body = _block_role_and_body(block)

        # Never feed previous AI answers back to the model.
        if role == "\u0418\u0418":
            continue

        # Never send the GUI boundary marker to the model.
        if (
            role == "\u0421\u0438\u0441\u0442\u0435\u043c\u0430"
            and body.strip().casefold()
            == "\u041d\u043e\u0432\u044b\u0439 \u043a\u0435\u0439\u0441".casefold()
        ):
            continue

        kept.append(block)

    return "\n\n".join(kept).strip()

def _is_explicit_new_case(text: str) -> bool:
    """Return True only when the user explicitly starts a separate case/topic."""
    if not text.strip():
        return False

    # Case boundary should normally be stated near the beginning of the turn.
    head = text[:500].casefold()

    markers = (
        "\u043d\u043e\u0432\u044b\u0439 \u043a\u0435\u0439\u0441",
        "\u043d\u043e\u0432\u044b\u0439 \u043d\u0435\u0437\u0430\u0432\u0438\u0441\u0438\u043c\u044b\u0439 \u043a\u0435\u0439\u0441",
        "\u043d\u0430\u0447\u0438\u043d\u0430\u0435\u043c \u043d\u043e\u0432\u044b\u0439 \u043a\u0435\u0439\u0441",
        "\u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 \u043a\u0435\u0439\u0441",
        "\u0434\u0440\u0443\u0433\u043e\u0439 \u043a\u0435\u0439\u0441",
        "\u043d\u043e\u0432\u0430\u044f \u0442\u0435\u043c\u0430",
        "\u043d\u043e\u0432\u0430\u044f \u0437\u0430\u0434\u0430\u0447\u0430",
        "\u0434\u0440\u0443\u0433\u0430\u044f \u0437\u0430\u0434\u0430\u0447\u0430",
        "new case",
        "new independent case",
        "separate case",
        "new topic",
    )

    return any(marker in head for marker in markers)


def _build_user_packet(
    dialogue: str,
    *,
    manual_question: str = "",
    instruction: str = "",
    max_context_lines: int = 40,
) -> tuple[str, str, str | None]:
    """Build LLM user content with full current turn (never last-«?» only).

    Returns ``(user_content, current_user_block, format_guard)``.
    """
    context, current = extract_current_user_turn(dialogue)

    if manual_question.strip():
        current = manual_question.strip()

        # ??????? ?????? ???? ??????? ??????????????? ????????.
        # ?????? ????? ? ??? ???????? ?? ???????????.
        if _is_explicit_new_case(current):
            context = ""
        else:
            human_context = _human_only_dialogue_context(dialogue)
            if max_context_lines <= 0:
                context_lines = []
            else:
                context_lines = human_context.splitlines()[-max_context_lines:]
            context = "\n".join(context_lines).strip()
    else:
        if _is_explicit_new_case(current):
            context = ""
        else:
            human_context = _human_only_dialogue_context(context)
            if max_context_lines <= 0:
                context_lines = []
            else:
                context_lines = human_context.splitlines()[-max_context_lines:]
            context = "\n".join(context_lines).strip()

    from meeting_bridge.skills import build_skill_context

    # Route skills using both the current request and the already-cleaned
    # human context of the CURRENT case.
    #
    # `context` has already passed:
    # - persistent New Case boundary,
    # - previous-AI removal,
    # - max_context_lines limit.
    #
    # This lets a short follow-up such as "??????? ????? ???? ???????"
    # activate meeting skills from the actual meeting context without
    # reintroducing old-case or AI-answer contamination.
    skill_routing_text = "\n".join(
        part for part in (context, current) if part
    ).strip()

    skill_context = build_skill_context(skill_routing_text)

    format_guard = detect_explicit_format(current)
    multipart_hint = detect_multipart_hint(current)
    period_hint = detect_period_vs_allocation_hint(current)

    if format_guard and context:
        context = _compact_dialogue_for_short_reply(context)

    parts: list[str] = []

    if skill_context:
        parts.append(skill_context)
    if multipart_hint:
        parts.append(multipart_hint)
    if format_guard:
        parts.append(format_guard)
    if period_hint:
        parts.append(period_hint)

    default_instruction = (
        "Ответь на ВЕСЬ текущий запрос целиком. "
        "Если в нём несколько вопросов или пунктов — ответь на каждый. "
        "Не выдёргивай только последнее предложение или последний «?». "
        "Не сокращай до «да/нет», если пользователь явно не просил "
        "«ответь только да или нет»."
    )
    parts.append(
        "КОНТЕКСТ ДИАЛОГА (STT, возможны искажения):\n"
        f"{context if context else '(пусто)'}\n\n"
        "ТЕКУЩИЙ ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n"
        f"{current if current else '(пусто)'}\n\n"
        + (instruction if instruction else default_instruction)
    )
    user_content = "\n\n".join(parts)
    write_llm_debug_log(
        raw_dialogue=dialogue,
        current_user_block=current,
        llm_user_content=user_content,
    )
    return user_content, current, format_guard


def ask_meeting_reply(
    dialogue: str,
    settings: LlmSettings,
    *,
    user_question: str = "",
    spoken: bool | None = None,
) -> str:
    """Send dialogue to an OpenAI-compatible chat completions API (manual button)."""
    if not dialogue.strip() and not user_question.strip():
        raise ValueError("Диалог пуст — сначала запишите реплики.")

    use_spoken = (
        wants_spoken_reply(user_question, spoken_mode=settings.spoken_mode)
        if spoken is None
        else spoken
    )
    if use_spoken:
        system_prompt = settings.spoken_system_prompt
        max_tokens = min(int(settings.max_tokens), 700)
        instruction = (
            "Дай короткую реплику 2–4 предложения по ВСЕМУ текущему запросу. "
            "Если вопросов несколько — кратко затронь каждый, не только последний."
        )
    else:
        system_prompt = settings.system_prompt
        max_tokens = int(settings.max_tokens)
        instruction = (
            "Ответь на ВЕСЬ текущий запрос целиком как аналитику 1С:ERP. "
            "Если задан явный формат (одна фраза / одно слово / только вывод / "
            "конкретный пункт) — соблюдай его. "
            "Если вопросов несколько — ответь на каждый пункт, не только на последний. "
            "Не начинай с общего чек-листа."
        )

    user_content, _current, format_guard = _build_user_packet(
        dialogue,
        manual_question=user_question,
        instruction=instruction,
        max_context_lines=int(settings.max_context_lines),
    )
    if format_guard:
        max_tokens = min(max_tokens, 400)

    call_settings = settings
    if settings.max_tokens != max_tokens:
        call_settings = replace(settings, max_tokens=max_tokens)
    return _chat_completion(
        settings=call_settings,
        system_prompt=system_prompt,
        user_content=user_content,
    )


def ask_auto_reply(dialogue: str, settings: LlmSettings) -> str | None:
    """Autonomous participant reply. Returns None when model chooses SKIP."""
    if not dialogue.strip():
        raise ValueError("Диалог пуст — сначала запишите реплики.")

    instruction = (
        "Нужен ли сейчас ответ от участника «ИИ»?\n"
        "Ответь на ВЕСЬ текущий запрос целиком. "
        "Уверен → полный ответ. Вероятная трактовка → с оговоркой. "
        "Неясно → уточни. Нечего отвечать → SKIP.\n"
        "Если в текущем запросе несколько вопросов — ответь на все пункты, "
        "а не только на последний; не возвращай эхом текст вопроса.\n"
        "Вопрос «Правильно ли…?» внутри кейса — не команда «только да/нет».\n"
        "Если явно просят одну фразу/слово/пункт — соблюдай формат и "
        "НЕ используй разделы ВЫВОД/ПОЧЕМУ/ГДЕ ПРОВЕРИТЬ.\n"
        "Запрещён ответ, применимый к любой ИС без изменений."
    )
    user_content, _current, format_guard = _build_user_packet(
        dialogue,
        manual_question="",
        instruction=instruction,
        max_context_lines=int(settings.max_context_lines),
    )

    max_tokens = min(int(settings.max_tokens), 1200)
    if format_guard:
        max_tokens = min(max_tokens, 400)
    call_settings = replace(settings, max_tokens=max_tokens)
    raw = _chat_completion(
        settings=call_settings,
        system_prompt=settings.auto_system_prompt,
        user_content=user_content,
    )
    return parse_auto_reply_content(raw)




