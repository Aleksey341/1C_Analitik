"""Pure UX policy helpers for the autonomous 1C Analitik desktop shell."""
from __future__ import annotations

from collections.abc import Iterable


def readiness_summary(
    *,
    mic_ready: bool,
    speaker_ready: bool,
    model_ready: bool,
    ai_ready: bool,
) -> tuple[bool, str]:
    """Return readiness flag and a user-facing status without technical jargon."""
    missing: list[str] = []
    if not mic_ready:
        missing.append("микрофон")
    if not speaker_ready:
        missing.append("звук собеседника")
    if not model_ready:
        missing.append("распознавание речи")
    if not ai_ready:
        missing.append("доступ к ИИ")
    if not missing:
        return True, "● Готов к работе: звук, распознавание и ИИ доступны"
    return False, "Нужно настроить: " + ", ".join(missing)


def should_suggest_topic_shift(
    previous_types: Iterable[str],
    current_types: Iterable[str],
) -> bool:
    """Suggest a context boundary only for a conservative disjoint topic change."""
    previous = {str(item).strip() for item in previous_types if str(item).strip()}
    current = {str(item).strip() for item in current_types if str(item).strip()}
    return bool(previous and current and previous.isdisjoint(current))
