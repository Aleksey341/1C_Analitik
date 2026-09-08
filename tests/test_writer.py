from datetime import datetime
from pathlib import Path

from meeting_bridge.writer import TranscriptWriter


def test_start_session_writes_frontmatter(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    w = TranscriptWriter(path, archive_dir=tmp_path / "archives", max_lines=2000)
    w.start_session(mic="Mic", speaker="Spk", session_iso="2026-08-12T21:45:00")
    text = path.read_text(encoding="utf-8")
    assert "session: 2026-08-12T21:45:00" in text
    assert "status: listening" in text
    assert "mic: Mic" in text
    assert "speaker: Spk" in text


def test_append_role_lines(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    w = TranscriptWriter(path, archive_dir=tmp_path / "archives", max_lines=2000)
    w.start_session(mic="M", speaker="S", session_iso="2026-08-12T21:45:00")
    w.append("Я", "Привет", when=datetime(2026, 8, 12, 21, 46, 2))
    w.append("Собеседник", "Здравствуйте", when=datetime(2026, 8, 12, 21, 46, 5))
    body = path.read_text(encoding="utf-8")
    assert "[21:46:02] Я: Привет" in body
    assert "[21:46:05] Собеседник: Здравствуйте" in body


def test_rotate_when_over_max_lines(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    archives = tmp_path / "archives"
    w = TranscriptWriter(
        path, archive_dir=archives, max_lines=5, merge_gap_sec=0
    )
    w.start_session(mic="M", speaker="S", session_iso="2026-08-12T21:45:00")
    for i in range(10):
        w.append("Я", f"line-{i}", when=datetime(2026, 8, 12, 21, 46, i % 60))
    assert archives.exists()
    assert any(archives.iterdir())
    assert path.exists()


def test_tail_returns_last_n_lines(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    w = TranscriptWriter(
        path, archive_dir=tmp_path / "a", max_lines=2000, merge_gap_sec=0
    )
    w.start_session(mic="M", speaker="S", session_iso="2026-08-12T21:45:00")
    w.append("Я", "one", when=datetime(2026, 8, 12, 21, 46, 1))
    w.append("Я", "two", when=datetime(2026, 8, 12, 21, 46, 2))
    tail = w.tail(1)
    assert "two" in tail
    assert "one" not in tail


def test_tail_returns_empty_for_non_positive_n(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    w = TranscriptWriter(path, archive_dir=tmp_path / "a", max_lines=2000)
    w.start_session(mic="M", speaker="S", session_iso="2026-08-12T21:45:00")
    w.append("Я", "one", when=datetime(2026, 8, 12, 21, 46, 1))

    assert w.tail(0) == ""
    assert w.tail(-1) == ""


def test_merges_same_role_within_gap(tmp_path: Path):
    path = tmp_path / "live-transcript.md"
    w = TranscriptWriter(
        path, archive_dir=tmp_path / "a", max_lines=2000, merge_gap_sec=2.5
    )
    w.start_session(mic="M", speaker="S", session_iso="2026-08-12T21:45:00")
    w.append("Собеседник", "давайте я", when=datetime(2026, 8, 12, 21, 46, 1))
    w.append("Собеседник", "представлю вам", when=datetime(2026, 8, 12, 21, 46, 2))
    w.append("Я", "ок", when=datetime(2026, 8, 12, 21, 46, 5))
    body = path.read_text(encoding="utf-8")
    assert "[21:46:02] Собеседник: давайте я представлю вам" in body
    assert "[21:46:05] Я: ок" in body
    assert body.count("Собеседник:") == 1
