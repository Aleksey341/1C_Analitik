from datetime import datetime
from pathlib import Path

from meeting_bridge.documents import build_protocol, read_dialogue_lines, save_dialogue_copy


def _sample_transcript(path: Path) -> None:
    path.write_text(
        "---\n"
        "session: 2026-08-13T10:00:00\n"
        "status: idle\n"
        "mic: Mic\n"
        "speaker: Spk\n"
        "---\n\n"
        "[10:00:01] Я: Добрый день\n"
        "[10:00:05] Собеседник: Давайте обсудим сроки\n"
        "[10:00:12] Я: Предлагаю сдать в пятницу\n",
        encoding="utf-8",
    )


def test_read_dialogue_lines(tmp_path: Path):
    src = tmp_path / "live-transcript.md"
    _sample_transcript(src)
    rows = read_dialogue_lines(src)
    assert len(rows) == 3
    assert rows[0] == ("10:00:01", "Я", "Добрый день")


def test_save_dialogue_copy(tmp_path: Path):
    src = tmp_path / "live-transcript.md"
    archive = tmp_path / "transcripts"
    _sample_transcript(src)
    dest = save_dialogue_copy(src, archive, title="Статус")
    assert dest.exists()
    text = dest.read_text(encoding="utf-8")
    assert "# Статус" in text
    assert "Добрый день" in text
    assert "Предлагаю сдать в пятницу" in text


def test_build_protocol(tmp_path: Path):
    src = tmp_path / "live-transcript.md"
    archive = tmp_path / "transcripts"
    _sample_transcript(src)
    dest = build_protocol(src, archive, title="Планерка")
    assert dest.exists()
    assert dest.name.startswith("protocol-")
    text = dest.read_text(encoding="utf-8")
    assert "# Планерка" in text
    assert "## Решения" in text
    assert "## Поручения" in text
    assert "Собеседник" in text
    assert "обсудим сроки" in text
    # Decisions/actions should be auto-filled, not empty placeholders only.
    assert "_Сформулируйте принятые решения_" not in text
    assert "| 1 |" in text


def test_extract_protocol_sections_finds_topics():
    from meeting_bridge.documents import extract_protocol_sections

    rows = [
        ("10:00:01", "Собеседник", "Если переезжать то надо стратегию на пятнадцать лет"),
        ("10:00:20", "Я", "Надо поработать ещё и искать айти проекты"),
        ("10:00:40", "Собеседник", "Поэтому переезд нет а по работе две мысли"),
    ]
    sections = extract_protocol_sections(rows)
    assert sections["agenda"]
    assert sections["decisions"]
    assert sections["actions"]
