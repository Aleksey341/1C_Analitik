"""Decide when to fire an autonomous LLM reply during a live meeting."""
from __future__ import annotations

from dataclasses import dataclass
import re
import time

_LINE_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]\s+([^:]+):\s*(.*)$")


def parse_transcript_role(line: str) -> str | None:
    match = _LINE_RE.match(line.strip())
    return match.group(4).strip() if match else None


def latest_trigger_line(body_lines: list[str], roles: set[str]) -> str | None:
    trigger: str | None = None
    for line in body_lines:
        role = parse_transcript_role(line)
        if role in roles:
            trigger = line
    return trigger


@dataclass(frozen=True)
class AutoReplyDecision:
    should_request: bool
    peer_line: str = ""
    reason: str = ""


class AutoReplyWatcher:
    """Debounce speech and decide when an auto LLM call is due."""

    def __init__(self) -> None:
        self.answered_peer_line: str = ""
        self.pending_peer_line: str = ""
        self.pending_since: float | None = None
        self.in_flight: bool = False

    def reset(self) -> None:
        self.answered_peer_line = ""
        self.pending_peer_line = ""
        self.pending_since = None
        self.in_flight = False

    def mark_answered(self, peer_line: str) -> None:
        self.answered_peer_line = peer_line
        self.pending_peer_line = ""
        self.pending_since = None
        self.in_flight = False

    def observe(
        self,
        body_lines: list[str],
        *,
        pause_sec: float,
        now: float | None = None,
        reply_on_me: bool = True,
    ) -> AutoReplyDecision:
        now = time.monotonic() if now is None else now
        if self.in_flight:
            return AutoReplyDecision(False, reason="in_flight")
        if not body_lines:
            return AutoReplyDecision(False, reason="empty")

        roles = {"Собеседник"}
        if reply_on_me:
            roles.add("Я")

        trigger = latest_trigger_line(body_lines, roles)
        if trigger is None:
            return AutoReplyDecision(False, reason="no_trigger")
        if trigger == self.answered_peer_line:
            return AutoReplyDecision(
                False, peer_line=trigger, reason="already_answered"
            )

        last_role = parse_transcript_role(body_lines[-1])
        if last_role == "ИИ":
            self.answered_peer_line = trigger
            self.pending_peer_line = ""
            self.pending_since = None
            return AutoReplyDecision(False, peer_line=trigger, reason="ai_already")

        # Раньше «Я» отменял автоответ. Теперь при reply_on_me реплики «Я» — тоже триггер.
        if last_role == "Я" and not reply_on_me:
            self.pending_peer_line = ""
            self.pending_since = None
            return AutoReplyDecision(
                False, peer_line=trigger, reason="user_speaking"
            )

        if last_role not in roles:
            return AutoReplyDecision(False, peer_line=trigger, reason="other_role")

        # Ждём паузу после последней реплики-триггера (чтобы успела дописаться 2-я часть вопроса).
        last_line = body_lines[-1]
        if last_line != self.pending_peer_line:
            self.pending_peer_line = last_line
            self.pending_since = now
            return AutoReplyDecision(
                False, peer_line=last_line, reason="debounce_start"
            )

        elapsed = 0.0 if self.pending_since is None else (now - self.pending_since)
        if elapsed >= pause_sec:
            # Сразу занимаем слот — иначе ручной «Ответ ИИ» и автоответ
            # могут уйти параллельно на одну и ту же реплику.
            self.in_flight = True
            return AutoReplyDecision(True, peer_line=last_line, reason="ready")
        return AutoReplyDecision(False, peer_line=last_line, reason="waiting")
