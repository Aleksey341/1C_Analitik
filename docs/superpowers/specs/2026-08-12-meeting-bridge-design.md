# Meeting Bridge (Cursor) — Design Spec

**Date:** 2026-08-12  
**Status:** Approved 2026-08-12  
**Inspired by:** Secstant ([secstant.ru](https://secstant.ru/))  
**Scope choice:** Approach B → storage A → audio 2 → stack 1

## Goal

Build a Windows bridge that captures a live call (user + peer), transcribes Russian speech locally, and streams a clean transcript into the Cursor workspace so the agent can answer “what should I say?” from chat.

This is **not** a full Secstant clone: no overlay UI and no in-app LLM hints in v1. Hints come from Cursor chat.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Primary mode | Bridge to Cursor (B), not standalone overlay |
| Transcript delivery | Live markdown file `live-transcript.md` (A) |
| Interaction | File updates continuously; user asks for hints in chat when needed |
| Audio | Mic + system/loopback peer, labels `Я:` / `Собеседник:` |
| Architecture | Python service + thin MCP (approach 1) |
| STT output | Final utterances only (no partial drafts in the file) |

## Architecture

```text
[Microphone] ──┐
               ├─► WASAPI capture ─► sherpa-onnx STT (RU) ─► live-transcript.md
[Speakers] ────┘                                                      │
                                                                      ▼
                                                    Cursor reads file / answers in chat
                                                                      ▲
                                                    MCP start/stop/status/tail ──────┘
```

### Components

| Component | Responsibility |
|-----------|----------------|
| `capture` | Two audio streams: microphone + WASAPI loopback |
| `stt` | Local streaming ASR; emit only final utterances |
| `writer` | Append timestamped role lines to `live-transcript.md` |
| `mcp` | Session control + `transcript_tail` for the agent |
| Cursor | User asks in chat; agent reads transcript and responds |

## File format

Path: project root `live-transcript.md`.

On `session_start`: reset file (or rotate if oversized) and write frontmatter.

```markdown
---
session: 2026-08-12T21:45:00
status: listening
mic: Головной телефон HONOR
speaker: Наушники HONOR
---

[21:46:02] Я: Добрый день
[21:46:05] Собеседник: Расскажите о себе
[21:46:18] Я: Я занимаюсь...
```

### Writer rules

- Append only **final** STT results (stable end-of-utterance), not partial hypotheses.
- Role from channel: mic → `Я`, loopback → `Собеседник`.
- If file exceeds ~2000 lines, archive to `transcripts/` and start a new file.
- Do not persist raw audio to disk by default.

### Why finals only

Streaming STT emits changing drafts while speech continues. Writing partials would thrash the file and hurt readability. Finals appear ~0.3–1s after a pause; acceptable for “ask when needed” hints.

## MCP server: `meeting-bridge`

Transport: stdio, registered in Cursor `mcp.json`.

| Tool | Purpose |
|------|---------|
| `session_start` | Start capture; optional device overrides; return transcript path |
| `session_stop` | Stop capture; set `status: idle` |
| `session_status` | listening/idle, devices, path |
| `transcript_tail` | Last N lines of the transcript |
| `list_audio_devices` | Enumerate mic and loopback devices |

Primary agent path in chat: read `live-transcript.md` directly. MCP is for control and quick tail.

## Tech stack

| Layer | Choice |
|-------|--------|
| OS | Windows 10/11 |
| Language | Python 3.11+ |
| Capture | `PyAudioWPatch` (WASAPI mic + loopback; `sounddevice` does not expose loopback) |
| STT | `sherpa-onnx` + Russian streaming model (same family as Secstant) |
| MCP | Official Python MCP SDK |
| Config | `config.yaml` (device names, transcript path) |

### Example config

```yaml
mic_device: "Головной телефон HONOR"
speaker_device: "Наушники HONOR"
transcript_path: "live-transcript.md"
```

On start: warn if mic and speaker resolve to the same device (common Bluetooth pitfall).

### Launch flow

1. One-time: install deps, download model, add MCP to Cursor.
2. Before call: `session_start` (MCP or `python -m meeting_bridge start`).
3. During call: user asks in Cursor; agent reads `live-transcript.md`.
4. After: `session_stop`.

## MVP boundaries

### In scope (v1)

- Dual-channel capture (mic + loopback)
- Local RU STT, finals only
- `live-transcript.md` with role labels
- MCP tools listed above
- Device config + same-device warning
- README: install, model, Cursor MCP wiring

### Out of scope (v1)

- Overlay / auto-hints like Secstant
- In-app scenario prompts / role templates
- In-bridge cloud LLM
- Partial lines in the transcript file
- Non-Windows, packaged `.exe` installer
- Default raw audio recording

## Success criteria

On a real call (e.g. TrueConf/Zoom):

1. Both roles appear in `live-transcript.md` with correct attribution.
2. User asks Cursor “что ответить?” and the agent bases the reply on the latest transcript.
3. Start/stop via MCP (or CLI) works without restarting Cursor.

## Project layout (planned)

```text
meeting_bridge/
  __init__.py
  __main__.py
  capture.py
  stt.py
  writer.py
  mcp_server.py
  config.py
config.yaml
live-transcript.md          # runtime
transcripts/                # archives
docs/superpowers/specs/     # this doc
README.md
requirements.txt
```

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Bluetooth mic/speaker swapped or same device | Explicit device selection + startup warning |
| Loopback unavailable / Stereo Mix missing | Prefer WASAPI loopback on output device; document fallback |
| STT latency or accuracy | Start with small streaming RU model; allow model path in config |
| File lock / concurrent write | Single writer process; append + flush; agent read-only |
| Cursor not watching file live | Agent re-reads on each user ask; optional `transcript_tail` |

## Non-goals / ethics note

Tool is a personal meeting assistant (notes + on-demand coaching). Users are responsible for consent and policy compliance in their calls.
