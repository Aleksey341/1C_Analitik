from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from meeting_bridge.config import load_config
from meeting_bridge.devices import list_audio_devices as _list
from meeting_bridge.session import MANAGER

mcp = FastMCP("meeting-bridge")


@mcp.tool()
def list_audio_devices() -> dict:
    """List microphone and WASAPI loopback devices."""
    return _list()


@mcp.tool()
def session_start(
    mic_device: str | None = None,
    speaker_device: str | None = None,
) -> dict:
    """Start dual-channel capture into live-transcript.md."""
    cfg = load_config()
    return MANAGER.start(
        cfg,
        mic_override=mic_device,
        speaker_override=speaker_device,
    )


@mcp.tool()
def session_stop() -> dict:
    """Stop capture and set status idle."""
    return MANAGER.stop()


@mcp.tool()
def session_status() -> dict:
    """Return listening/idle, devices, transcript path."""
    return MANAGER.status()


@mcp.tool()
def transcript_tail(n: int = 30) -> str:
    """Return last N transcript lines."""
    return MANAGER.tail(n)


def main() -> None:
    mcp.run()
