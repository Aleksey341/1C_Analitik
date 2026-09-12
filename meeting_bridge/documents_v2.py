"""1C-focused local meeting protocol generation for UX v2.

This module intentionally works without internet/LLM so that a meeting can be
captured and summarized even when AI access is temporarily unavailable.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from meeting_bridge.documents import dialogue_markdown, read_dialogue_lines

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "НДС": ("ндс", "счет-фактур", "счёт-фактур", "книга покупок", "книга продаж", "вычет", "аванс"),
    "БУ / НУ / налог на прибыль": ("бухгалтер", "налогов", "бу ", "ну ", "прибыл", "пно", "пна", "оно", "она"),
    "Закрытие месяца и себестоимость": ("закрытие месяца", "закрыть месяц", "себестоим", "нзп", "20 счет", "25 счет", "26 счет", "90.08"),
    "Взаиморасчёты": ("60 счет", "62 счет", "76", "взаиморасчет", "взаиморасчёт", "дебитор", "кредитор", "аванс"),
    "Производство": ("производств", "этап производства", "заказ на производство", "выпуск", "спецификац", "ресурсная спецификац"),
    "ЗУП / зарплата / кадры": ("зуп", "зарплат", "начислен", "сотрудник", "кадр", "прием", "приём", "увольнен", "табель"),
    "ОС / НМА / лизинг": ("основн", "ос ", "амортиз", "модернизац", "лизинг", "нма", "капвлож"),
    "Закупки / продажи / склад": ("закуп", "продаж", "реализац", "поступлен", "склад", "номенклатур", "заказ клиента", "заказ поставщику"),
    "Отчётность и сверка": ("осв", "оборотно", "отчет", "отчёт", "сверк", "расхожд", "sap", "универсальный отчет", "универсальный отчёт"),
    "Права / ЭДО / интеграции": ("права", "роль", "эдо", "этрн", "интеграц", "обмен", "api", "загрузка", "выгрузка"),
    "Требования / доработка 1С": ("требован", "доработ", "разработ", "расширен", "тз", "техническое задание", "бизнес-процесс", "workflow"),
}

_DECISION_MARKERS = (
    "решили",
    "решено",
    "договорились",
    "согласовали",
    "делаем",
    "оставляем",
    "убираем",
    "нужно",
    "надо",
    "будем",
    "итог",
)

_ACTION_MARKERS = (
    "проверить",
    "уточнить",
    "настроить",
    "исправить",
    "доработать",
    "подготовить",
    "сверить",
    "отправить",
    "загрузить",
    "выгрузить",
    "перепровести",
    "протестировать",
    "показать",
    "согласовать",
)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text)
    out: list[str] = []
    for part in parts:
        chunk = " ".join(part.split()).strip(" -–—\t")
        if len(chunk) >= 18:
            out.append(chunk)
    if not out and text.strip():
        out.append(" ".join(text.split()).strip())
    return out


def extract_protocol_sections(
    rows: list[tuple[str, str, str]],
) -> dict[str, list]:
    """Extract 1C-oriented agenda, decisions, actions and open questions locally."""
    human_rows = [row for row in rows if row[1] not in {"ИИ", "Система"}]
    full = " ".join(text for _t, _role, text in human_rows)
    lower = full.casefold()

    agenda = [
        topic
        for topic, keys in _TOPIC_KEYWORDS.items()
        if any(key in lower for key in keys)
    ]
    if not agenda and human_rows:
        agenda = ["Рабочие вопросы по 1С"]

    candidates: list[tuple[int, str, str]] = []
    for _t, role, text in human_rows:
        for sentence in _sentences(text):
            s = sentence.casefold()
            score = 0
            if any(marker in s for marker in _DECISION_MARKERS):
                score += 4
            if any(marker in s for marker in _ACTION_MARKERS):
                score += 4
            if any(any(key in s for key in keys) for keys in _TOPIC_KEYWORDS.values()):
                score += 2
            if any(ch.isdigit() for ch in sentence):
                score += 1
            candidates.append((score, role, sentence))

    decisions: list[str] = []
    seen: set[str] = set()
    for score, role, sentence in sorted(candidates, key=lambda item: item[0], reverse=True):
        s = sentence.casefold()
        if score < 4 or not any(marker in s for marker in _DECISION_MARKERS):
            continue
        key = re.sub(r"\W+", " ", s)[:100]
        if key in seen:
            continue
        seen.add(key)
        decisions.append(f"{role}: {sentence}")
        if len(decisions) >= 8:
            break

    actions: list[tuple[str, str, str]] = []
    action_seen: set[str] = set()
    for score, role, sentence in sorted(candidates, key=lambda item: item[0], reverse=True):
        s = sentence.casefold()
        if score < 4 or not any(marker in s for marker in _ACTION_MARKERS):
            continue
        key = re.sub(r"\W+", " ", s)[:100]
        if key in action_seen:
            continue
        action_seen.add(key)
        task = sentence if len(sentence) <= 220 else sentence[:220].rstrip() + "…"
        actions.append((task, role or "—", "уточнить"))
        if len(actions) >= 8:
            break

    questions: list[str] = []
    question_seen: set[str] = set()
    for _t, role, text in human_rows:
        for sentence in _sentences(text):
            s = sentence.strip()
            low = s.casefold()
            is_question = "?" in s or low.startswith(("почему", "как ", "где ", "что ", "какой ", "какая ", "можно ли", "нужно ли"))
            if not is_question:
                continue
            key = re.sub(r"\W+", " ", low)[:100]
            if key in question_seen:
                continue
            question_seen.add(key)
            questions.append(f"{role}: {s}")
            if len(questions) >= 8:
                break
        if len(questions) >= 8:
            break

    if not decisions and human_rows:
        decisions = ["Явные решения не распознаны автоматически. Проверьте стенограмму."]
    if not actions and human_rows:
        actions = [("Проверить итоги встречи и зафиксировать следующие шаги", "Я", "уточнить")]

    return {
        "agenda": agenda,
        "decisions": decisions,
        "actions": actions,
        "questions": questions,
        "notes": [
            "Протокол сформирован локально без передачи стенограммы во внешний сервис.",
            "STT может искажать термины 1С, номера счетов и названия документов. Проверьте критичные формулировки.",
        ],
    }


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\-а-яА-ЯёЁ]+", "-", text.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return (cleaned[:60] or "protocol").lower()


def build_protocol(
    transcript_path: Path,
    archive_dir: Path,
    *,
    title: str = "",
    location: str = "",
) -> Path:
    """Create a 1C-oriented local Markdown protocol."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    rows = read_dialogue_lines(transcript_path)
    sections = extract_protocol_sections(rows)
    human_roles = sorted({role for _t, role, _text in rows if role not in {"ИИ", "Система"}})
    meeting_title = title.strip() or "Протокол встречи по 1С"
    started = rows[0][0] if rows else "—"
    ended = rows[-1][0] if rows else "—"
    date_str = datetime.now().strftime("%d.%m.%Y")

    agenda_lines = "\n".join(
        f"{i}. {item}" for i, item in enumerate(sections["agenda"], start=1)
    ) or "1. Рабочие вопросы по 1С"
    decision_lines = "\n".join(f"- {item}" for item in sections["decisions"])
    question_lines = "\n".join(f"- {item}" for item in sections["questions"]) or "- Явных открытых вопросов не распознано"
    note_lines = "\n".join(f"- {item}" for item in sections["notes"])
    action_table = "\n".join(
        f"| {i} | {task} | {owner} | {due} |"
        for i, (task, owner, due) in enumerate(sections["actions"], start=1)
    )

    content = (
        f"# {meeting_title}\n\n"
        f"## Реквизиты\n\n"
        f"| Поле | Значение |\n"
        f"|---|---|\n"
        f"| Дата | {date_str} |\n"
        f"| Время | {started} - {ended} |\n"
        f"| Канал | {location.strip() or 'онлайн / локальная запись'} |\n"
        f"| Участники | {', '.join(human_roles) or 'Я, Собеседник'} |\n\n"
        f"## Повестка\n\n{agenda_lines}\n\n"
        f"## Решения\n\n{decision_lines}\n\n"
        f"## Поручения и следующие шаги\n\n"
        f"| № | Что сделать | Ответственный | Срок |\n"
        f"|---|---|---|---|\n{action_table}\n\n"
        f"## Открытые вопросы\n\n{question_lines}\n\n"
        f"## Полная стенограмма\n\n{dialogue_markdown(rows)}\n"
        f"## Примечания\n\n{note_lines}\n\n"
        f"---\nСформировано 1С Аналитиком локально: {datetime.now().isoformat(timespec='seconds')}\n"
    )
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = archive_dir / f"protocol-{_slug(meeting_title)}-{stamp}.md"
    dest.write_text(content, encoding="utf-8")
    return dest
