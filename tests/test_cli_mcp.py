from __future__ import annotations

import json
import sys
from types import SimpleNamespace


def test_devices_command_prints_json(monkeypatch, capsys) -> None:
    from meeting_bridge import __main__ as cli

    devices = {"mic": [{"name": "USB Mic"}], "loopback": []}
    monkeypatch.setattr(cli, "list_audio_devices", lambda: devices)
    monkeypatch.setattr(sys, "argv", ["meeting_bridge", "devices"])

    cli.main()

    assert json.loads(capsys.readouterr().out) == devices


def test_mcp_tools_delegate_to_shared_manager(monkeypatch) -> None:
    from meeting_bridge import mcp_server

    manager = SimpleNamespace(
        start=lambda cfg, mic_override=None, speaker_override=None: {
            "cfg": cfg,
            "mic": mic_override,
            "speaker": speaker_override,
        },
        stop=lambda: {"state": "idle"},
        status=lambda: {"state": "listening"},
        tail=lambda n: f"last {n}",
    )
    config = object()
    monkeypatch.setattr(mcp_server, "MANAGER", manager)
    monkeypatch.setattr(mcp_server, "load_config", lambda: config)
    monkeypatch.setattr(
        mcp_server,
        "_list",
        lambda: {"mic": [], "loopback": [{"name": "Speakers"}]},
    )

    assert mcp_server.list_audio_devices()["loopback"][0]["name"] == "Speakers"
    assert mcp_server.session_start("Mic", "Speakers") == {
        "cfg": config,
        "mic": "Mic",
        "speaker": "Speakers",
    }
    assert mcp_server.session_status() == {"state": "listening"}
    assert mcp_server.transcript_tail(7) == "last 7"
    assert mcp_server.session_stop() == {"state": "idle"}
