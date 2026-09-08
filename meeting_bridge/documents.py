"""Save dialogues and build meeting protocol documents."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import shutil

_LINE_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s+([^:]+):\s*(.*)$")

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Переезд / релокация": ("переезд", "переезжать", "уех", "релок", "корея", "москв"),
    "Работа и рынок": ("работ", "рынк", "глобал", "офис", "удалён", "удален", "вакан"),
    "IT / смена профиля": ("айти", "it", "проект", "профил", "фриланс", "реланс"),
    "Семья": ("жен", "ребён", "ребенок", "декрет", "дочь", "семь"),
    "Автомобиль / техника": ("машин", "тачк", "бензин", "учёт", "учет", "техник"),
}

_DECISION_MARKERS = (
    "поэтому",
    "надо",
    "нужно",
    "решил",
    "решим",
    "давайте",
    "итог",
    "важно",
    "не вариант",
    "нельзя",
    "окей",
    "хорошо",
)

_ACTION_MARKERS = (
    "надо",
    "нужно",
    "сделать",
    "искать",
    "менять",
    "поработа",
    "подготов",
    "проверить",
    "узнать",
    "найти",
)


def read_dialogue_lines(transcript_path: Path) -> list[tuple[str, str, str]]:
    """Return list of (time, role, text) from a transcript file."""
    if not transcript_path.exists():
        return []
    from meeting_bridge.writer import iter_dialogue_blocks

    rows: list[tuple[str, str, str]] = []
    for block in iter_dialogue_blocks(transcript_path.read_text(encoding="utf-8")):
        first, _, rest = block.partition("\n")
        match = _LINE_RE.match(first.strip())
        if not match:
            continue
        text = match.group(3).strip()
        if rest.strip():
            text = f"{text}\n{rest}".strip() if text else rest.strip()
        rows.append((match.group(1), match.group(2).strip(), text))
    return rows


def dialogue_markdown(rows: list[tuple[str, str, str]]) -> str:
    if not rows:
        return "_Диалог пока пуст._\n"
    return "\n".join(f"**[{t}] {role}:** {text}" for t, role, text in rows) + "\n"


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text)
    out: list[str] = []
    for part in parts:
        chunk = " ".join(part.split()).strip(" -–—\t")
        if len(chunk) >= 25:
            out.append(chunk)
    if not out and text.strip():
        # Fallback: split long STT blobs by length.
        words = text.split()
        buf: list[str] = []
        for word in words:
            buf.append(word)
            if len(buf) >= 18:
                out.append(" ".join(buf))
                buf = []
        if buf:
            out.append(" ".join(buf))
    return out


def extract_protocol_sections(
    rows: list[tuple[str, str, str]],
) -> dict[str, list[str] | list[tuple[str, str, str]]]:
    """Derive agenda, decisions and actions from dialogue without an external LLM."""
    full = " ".join(text for _t, _role, text in rows)
    lower = full.casefold()

    agenda: list[str] = []
    for topic, keys in _TOPIC_KEYWORDS.items():
        if any(k in lower for k in keys):
            agenda.append(topic)
    if not agenda and rows:
        agenda = ["Обсуждение текущих вопросов"]

    scored: list[tuple[int, str, str]] = []
    for _t, role, text in rows:
        for sentence in _sentences(text):
            score = min(len(sentence), 220) // 20
            s_lower = sentence.casefold()
            if any(m in s_lower for m in _DECISION_MARKERS):
                score += 4
            if any(m in s_lower for m in _ACTION_MARKERS):
                score += 3
            if any(any(k in s_lower for k in keys) for keys in _TOPIC_KEYWORDS.values()):
                score += 2
            scored.append((score, role, sentence))

    scored.sort(key=lambda item: item[0], reverse=True)

    decisions: list[str] = []
    seen: set[str] = set()
    for score, role, sentence in scored:
        if score < 5:
            continue
        key = sentence[:80].casefold()
        if key in seen:
            continue
        seen.add(key)
        decisions.append(f"{role}: {sentence}")
        if len(decisions) >= 6:
            break
    if not decisions and rows:
        # Take the longest utterances as discussion outcomes.
        longest = sorted(rows, key=lambda r: len(r[2]), reverse=True)[:4]
        for _t, role, text in longest:
            snippet = text if len(text) <= 220 else text[:220].rstrip() + "…"
            decisions.append(f"{role}: {snippet}")

    actions: list[tuple[str, str, str]] = []
    for score, role, sentence in scored:
        s_lower = sentence.casefold()
        if not any(m in s_lower for m in _ACTION_MARKERS):
            continue
        key = sentence[:70].casefold()
        if key in seen and any(key in d.casefold() for d in decisions):
            # still allow as action if strongly action-like
            pass
        task = sentence if len(sentence) <= 160 else sentence[:160].rstrip() + "…"
        owner = role if role else "—"
        actions.append((task, owner, "уточнить"))
        if len(actions) >= 5:
            break
    if not actions and decisions:
        actions.append(
            (
                "Зафиксировать итоги разговора и следующие шаги",
                "Я",
                "на этой неделе",
            )
        )

    notes = [
        f"Автозаполнение по {len(rows)} репликам. Проверьте формулировки — речь распознана с ошибками STT."
    ]
    return {
        "agenda": agenda,
        "decisions": decisions,
        "actions": actions,
        "notes": notes,
    }


def save_dialogue_copy(
    transcript_path: Path,
    archive_dir: Path,
    title: str = "",
) -> Path:
    """Copy current transcript into archive_dir as a dated dialogue file."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_title = _slug(title) if title.strip() else "dialog"
    dest = archive_dir / f"{safe_title}-{stamp}.md"
    rows = read_dialogue_lines(transcript_path)
    meta_mic = meta_speaker = meta_session = ""
    if transcript_path.exists():
        raw = transcript_path.read_text(encoding="utf-8")
        for line in raw.splitlines():
            if line.startswith("session:"):
                meta_session = line.split(":", 1)[1].strip()
            elif line.startswith("mic:"):
                meta_mic = line.split(":", 1)[1].strip()
            elif line.startswith("speaker:"):
                meta_speaker = line.split(":", 1)[1].strip()

    heading = title.strip() or "Диалог"
    body = (
        f"# {heading}\n\n"
        f"- Сохранено: {datetime.now().isoformat(timespec='seconds')}\n"
        f"- Сессия: {meta_session or '—'}\n"
        f"- Микрофон: {meta_mic or '—'}\n"
        f"- Собеседник (loopback): {meta_speaker or '—'}\n"
        f"- Реплик: {len(rows)}\n\n"
        f"## Диалог\n\n"
        f"{dialogue_markdown(rows)}"
    )
    dest.write_text(body, encoding="utf-8")
    raw_dest = archive_dir / f"{safe_title}-{stamp}-raw.md"
    if transcript_path.exists():
        shutil.copy2(transcript_path, raw_dest)
    return dest


def build_protocol(
    transcript_path: Path,
    archive_dir: Path,
    *,
    title: str = "",
    location: str = "",
) -> Path:
    """Create a meeting protocol markdown with filled agenda/decisions/actions."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rows = read_dialogue_lines(transcript_path)
    sections = extract_protocol_sections(rows)
    by_role: dict[str, list[str]] = {}
    for _t, role, text in rows:
        by_role.setdefault(role, []).append(text)

    participants = ", ".join(sorted(by_role.keys())) or "Я, Собеседник"
    meeting_title = title.strip() or "Протокол совещания"
    started = rows[0][0] if rows else "—"
    ended = rows[-1][0] if rows else "—"
    date_str = datetime.now().strftime("%d.%m.%Y")

    role_blocks = []
    for role, texts in by_role.items():
        joined = " ".join(texts)
        excerpt = joined if len(joined) <= 800 else joined[:800].rstrip() + "…"
        role_blocks.append(f"### {role}\n\n{excerpt}\n")
    role_summary = "".join(role_blocks) if role_blocks else "_Нет реплик._\n"

    agenda_lines = "\n".join(
        f"{i}. {item}" for i, item in enumerate(sections["agenda"], start=1)
    ) or "1. Обсуждение текущих вопросов"

    decision_lines = "\n".join(
        f"- [x] {item}" for item in sections["decisions"]
    ) or "- [ ] _В диалоге явных решений не найдено — добавьте вручную_"

    action_rows = sections["actions"]
    if action_rows:
        action_table = "\n".join(
            f"| {i} | {task} | {owner} | {due} |"
            for i, (task, owner, due) in enumerate(action_rows, start=1)
        )
    else:
        action_table = "| 1 | _Добавьте поручение_ |  |  |"

    notes = "\n".join(f"- {n}" for n in sections["notes"])

    content = (
        f"# {meeting_title}\n\n"
        f"## Реквизиты\n\n"
        f"| Поле | Значение |\n"
        f"|------|----------|\n"
        f"| Дата | {date_str} |\n"
        f"| Время | {started} – {ended} |\n"
        f"| Место / канал | {location.strip() or 'онлайн / локальная запись'} |\n"
        f"| Участники | {participants} |\n"
        f"| Реплик в записи | {len(rows)} |\n\n"
        f"## Повестка\n\n"
        f"{agenda_lines}\n\n"
        f"## Кратко по участникам\n\n"
        f"{role_summary}\n"
        f"## Ход обсуждения (полный диалог)\n\n"
        f"{dialogue_markdown(rows)}\n"
        f"## Решения\n\n"
        f"{decision_lines}\n\n"
        f"## Поручения\n\n"
        f"| № | Поручение | Ответственный | Срок |\n"
        f"|---|-----------|---------------|------|\n"
        f"{action_table}\n\n"
        f"## Примечания\n\n"
        f"{notes}\n\n"
        f"---\n"
        f"Сформировано в Meeting Bridge: "
        f"{datetime.now().isoformat(timespec='seconds')}\n"
    )
    safe = _slug(meeting_title)
    dest = archive_dir / f"protocol-{safe}-{stamp}.md"
    dest.write_text(content, encoding="utf-8")
    return dest


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\-а-яА-ЯёЁ]+", "-", text.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return (cleaned[:60] or "doc").lower()
