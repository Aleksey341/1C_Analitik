from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import shutil
import threading

_LINE_RE = re.compile(
    r"^\[(\d{2}):(\d{2}):(\d{2})\]\s+([^:]+):\s*(.*)$"
)


def iter_dialogue_blocks(raw: str) -> list[str]:
    """Collect transcript entries, keeping multiline AI replies as one block.

    A block starts with ``[HH:MM:SS] Role:``; following lines until the next
    timestamped role line belong to the same entry (markdown answers, lists).
    """
    blocks: list[str] = []
    current: str | None = None
    for ln in raw.splitlines():
        if ln.startswith("["):
            if current is not None:
                blocks.append(current.rstrip())
            current = ln
        elif current is not None:
            current += "\n" + ln
    if current is not None:
        blocks.append(current.rstrip())
    return blocks


def append_transcript_line(
    path: Path, role: str, text: str, when: datetime | None = None
) -> None:
    """Append a role line to transcript file even without an active SessionManager writer."""
    text = text.strip()
    if not text:
        return
    when = when or datetime.now()
    # Keep internal newlines so markdown answers stay readable in the file/UI.
    line = f"[{when.strftime('%H:%M:%S')}] {role}: {text}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "---\n"
            f"session: {when.isoformat(timespec='seconds')}\n"
            "status: idle\n"
            "---\n\n",
            encoding="utf-8",
        )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()


def read_recent_dialogue(path: Path, max_lines: int = 40) -> str:
    if not path.exists():
        return ""
    body = iter_dialogue_blocks(path.read_text(encoding="utf-8"))
    return "\n\n".join(body[-max_lines:])


class TranscriptWriter:
    def __init__(
        self,
        path: Path,
        archive_dir: Path,
        max_lines: int = 2000,
        merge_gap_sec: float = 2.5,
    ) -> None:
        self.path = path
        self.archive_dir = archive_dir
        self.max_lines = max_lines
        self.merge_gap_sec = merge_gap_sec
        self._lock = threading.Lock()
        self._line_count = 0
        self._mic = ""
        self._speaker = ""
        self._session_iso = ""
        self._last_role: str | None = None
        self._last_when: datetime | None = None

    def start_session(self, mic: str, speaker: str, session_iso: str) -> Path:
        with self._lock:
            self._mic = mic
            self._speaker = speaker
            self._session_iso = session_iso
            self._line_count = 0
            self._last_role = None
            self._last_when = None
            self.path.parent.mkdir(parents=True, exist_ok=True)
            content = (
                "---\n"
                f"session: {session_iso}\n"
                "status: listening\n"
                f"mic: {mic}\n"
                f"speaker: {speaker}\n"
                "---\n\n"
            )
            self.path.write_text(content, encoding="utf-8")
            return self.path

    def set_status(self, status: str) -> None:
        with self._lock:
            if not self.path.exists():
                return
            text = self.path.read_text(encoding="utf-8")
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("status:"):
                    lines[i] = f"status: {status}"
                    break
            self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def append(self, role: str, text: str, when: datetime | None = None) -> None:
        text = text.strip()
        if not text:
            return
        when = when or datetime.now()
        with self._lock:
            if self._should_merge_unlocked(role, when):
                self._merge_into_last_line_unlocked(text, when)
                self._last_when = when
                return

            if self._line_count >= self.max_lines:
                self._rotate_unlocked()
            line = f"[{when.strftime('%H:%M:%S')}] {role}: {text}\n"
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
            self._line_count += 1
            self._last_role = role
            self._last_when = when

    def tail(self, n: int) -> str:
        if n <= 0:
            return ""
        with self._lock:
            if not self.path.exists():
                return ""
            body = iter_dialogue_blocks(self.path.read_text(encoding="utf-8"))
            return "\n\n".join(body[-n:])

    def _should_merge_unlocked(self, role: str, when: datetime) -> bool:
        if self._last_role != role or self._last_when is None:
            return False
        gap = (when - self._last_when).total_seconds()
        return 0 <= gap <= self.merge_gap_sec

    def _merge_into_last_line_unlocked(self, text: str, when: datetime) -> None:
        raw = self.path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        for i in range(len(lines) - 1, -1, -1):
            match = _LINE_RE.match(lines[i])
            if not match:
                continue
            old_text = match.group(5).strip()
            # Avoid duplicating if model repeats a growing hypothesis fragment.
            if text.startswith(old_text) and len(text) > len(old_text):
                merged = text
            elif old_text.endswith(text):
                merged = old_text
            else:
                merged = f"{old_text} {text}".strip()
            stamp = when.strftime("%H:%M:%S")
            role = match.group(4)
            lines[i] = f"[{stamp}] {role}: {merged}"
            self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
        # No body line yet — fall back to append-like write.
        line = f"[{when.strftime('%H:%M:%S')}] {self._last_role}: {text}\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
        self._line_count += 1

    def _rotate_unlocked(self) -> None:
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = self.archive_dir / f"transcript-{stamp}.md"
        if self.path.exists():
            shutil.move(str(self.path), str(dest))
        content = (
            "---\n"
            f"session: {self._session_iso}\n"
            "status: listening\n"
            f"mic: {self._mic}\n"
            f"speaker: {self._speaker}\n"
            "---\n\n"
        )
        self.path.write_text(content, encoding="utf-8")
        self._line_count = 0
        self._last_role = None
        self._last_when = None
