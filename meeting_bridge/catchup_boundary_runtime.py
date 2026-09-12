"""Live catch-up boundary for autonomous meeting replies.

When speech arrives while an AI answer is already being generated, the next
catch-up request must treat only the newly arrived human turns as the current
request. Earlier turns remain context and must not be answered again.
"""
from __future__ import annotations

import re
import threading

from meeting_bridge.auto_reply import parse_transcript_role
from meeting_bridge.config import load_config
from meeting_bridge.llm_client import resolve_api_key
from meeting_bridge.session import MANAGER
from meeting_bridge.writer import iter_dialogue_blocks

_INSTALLED = False
_BLOCK_HEAD_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]\s+([^:]+):\s*(.*)$")
_HUMAN_ROLES = {"Я", "Собеседник"}


def _block_head(block: str) -> str:
    lines = (block or "").splitlines()
    return lines[0].strip() if lines else ""


def _block_role_and_body(block: str) -> tuple[str | None, str]:
    lines = (block or "").splitlines()
    if not lines:
        return None, ""
    match = _BLOCK_HEAD_RE.match(lines[0].strip())
    if not match:
        return None, block.strip()
    role = match.group(4).strip()
    first = match.group(5).strip()
    rest = "\n".join(lines[1:]).strip()
    if first and rest:
        return role, f"{first}\n{rest}"
    return role, first or rest


def build_catchup_dialogue(
    blocks: list[str],
    *,
    after_peer_line: str,
    max_context_blocks: int = 40,
) -> str:
    """Build a synthetic dialogue whose current request is only new live speech.

    ``after_peer_line`` is the transcript head that was current when the previous
    LLM request started. Every human block after that boundary is folded into one
    synthetic current turn. Older human blocks remain ordinary context. Previous
    AI answers are deliberately not copied into the synthetic current turn.
    """
    if not blocks:
        return ""

    boundary = (after_peer_line or "").strip()
    boundary_index = -1
    if boundary:
        for index, block in enumerate(blocks):
            if _block_head(block) == boundary:
                boundary_index = index

    if boundary_index < 0:
        limit = max(1, int(max_context_blocks))
        return "\n\n".join(blocks[-limit:])

    new_turns: list[tuple[str, str]] = []
    for block in blocks[boundary_index + 1 :]:
        role, body = _block_role_and_body(block)
        if role in _HUMAN_ROLES and body.strip():
            new_turns.append((role, body.strip()))

    if not new_turns:
        limit = max(1, int(max_context_blocks))
        return "\n\n".join(blocks[-limit:])

    # Keep the already-handled request and older human facts only as context.
    # The LLM packet builder will independently remove prior AI answers.
    limit = max(1, int(max_context_blocks))
    context_blocks = blocks[: boundary_index + 1]
    if len(context_blocks) >= limit:
        context_blocks = context_blocks[-(limit - 1) :] if limit > 1 else []

    lines = [
        "НОВЫЕ РЕПЛИКИ, ПОЯВИВШИЕСЯ ВО ВРЕМЯ ПРЕДЫДУЩЕГО ОТВЕТА:",
    ]
    for role, body in new_turns:
        body_one = body.replace("\n", " ").strip()
        lines.append(f"{role}: {body_one}")
    lines.extend(
        [
            "",
            "Ответь только на эти новые реплики. Предыдущие реплики выше используй "
            "только как контекст. Не повторяй уже обработанный вопрос и его подробную "
            "диагностику, если новые реплики прямо этого не требуют.",
        ]
    )

    latest_role = new_turns[-1][0]
    synthetic = f"[00:00:00] {latest_role}: " + "\n".join(lines)
    return "\n\n".join([*context_blocks, synthetic]).strip()


def install() -> None:
    """Install request-boundary-aware catch-up into the runtime GUI."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from meeting_bridge import gui_runtime, gui_v2

    cls = gui_runtime.MeetingBridgeApp
    original_queue = cls._queue_live_catchup

    def _queue_live_catchup_with_boundary(self, path, answered_peer_line: str):  # noqa: ANN001
        queued = original_queue(self, path, answered_peer_line)
        if queued:
            # Save the exact request snapshot boundary. The existing watcher stores
            # only the newest catch-up trigger, which is insufficient to separate
            # already-answered speech from speech that arrived during generation.
            self._auto_watcher.catchup_after_peer_line = (
                answered_peer_line or ""
            ).strip()
        return queued

    def _maybe_auto_reply_with_boundary(self) -> None:
        if self._busy or self._auto_busy or not bool(self.auto_reply_var.get()):
            return
        if MANAGER.status().get("state") != "listening":
            return

        cfg = load_config()
        if not cfg.llm.enabled or not cfg.llm.auto_reply or not resolve_api_key(cfg.llm):
            return

        path = gui_v2._root() / cfg.transcript_path
        if not path.exists():
            return
        blocks = iter_dialogue_blocks(path.read_text(encoding="utf-8"))
        heads = [b.splitlines()[0] if b else b for b in blocks]
        decision = self._auto_watcher.observe(
            heads,
            pause_sec=float(cfg.llm.auto_reply_pause_sec),
            reply_on_me=bool(cfg.llm.auto_reply_on_me),
        )
        if not decision.should_request:
            return

        if decision.reason == "catch_up":
            boundary = getattr(self._auto_watcher, "catchup_after_peer_line", "")
            dialogue = build_catchup_dialogue(
                blocks,
                after_peer_line=boundary,
                max_context_blocks=int(cfg.llm.max_context_lines),
            )
            # Consume this boundary. If still newer speech arrives while this catch-up
            # answer is running, _queue_live_catchup will write a new boundary using
            # the current catch-up trigger.
            self._auto_watcher.catchup_after_peer_line = ""
        else:
            dialogue = "\n\n".join(blocks[-cfg.llm.max_context_lines :])

        peer = decision.peer_line
        self._auto_busy = True
        self.warn_label.configure(
            text=(
                "1С Аналитик анализирует новые реплики…"
                if decision.reason == "catch_up"
                else "1С Аналитик анализирует последнюю реплику…"
            )
        )
        settings = self._enhanced_llm(cfg)

        def worker() -> None:
            try:
                # Use gui_v2.ask_auto_reply deliberately: quality_runtime patches
                # this symbol with the professional long-answer implementation.
                reply = gui_v2.ask_auto_reply(dialogue, settings)
                self.after(
                    0,
                    lambda r=reply, p=peer: self._on_auto_ok(r, path, p),
                )
            except Exception as exc:  # noqa: BLE001
                self.after(
                    0,
                    lambda e=exc, p=peer: self._on_auto_fail(e, p),
                )

        threading.Thread(target=worker, daemon=True).start()

    cls._queue_live_catchup = _queue_live_catchup_with_boundary
    cls._maybe_auto_reply = _maybe_auto_reply_with_boundary
