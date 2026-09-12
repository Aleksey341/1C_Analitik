from __future__ import annotations

import argparse
import json
import time

from meeting_bridge.config import load_config
from meeting_bridge.devices import list_audio_devices
from meeting_bridge.session import MANAGER


def main() -> None:
    parser = argparse.ArgumentParser(prog="meeting_bridge")
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    subparsers.add_parser("devices", help="list microphones and loopback devices")
    subparsers.add_parser("start", help="capture until Ctrl+C")
    subparsers.add_parser("mcp", help="run the stdio MCP server")
    subparsers.add_parser("gui", help="open desktop window")
    args = parser.parse_args()

    if args.cmd == "devices":
        print(json.dumps(list_audio_devices(), ensure_ascii=False, indent=2))
    elif args.cmd == "start":
        print(json.dumps(MANAGER.start(load_config()), ensure_ascii=False, indent=2))
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(json.dumps(MANAGER.stop(), ensure_ascii=False, indent=2))
    elif args.cmd == "mcp":
        from meeting_bridge.mcp_server import main as mcp_main

        mcp_main()
    elif args.cmd == "gui":
        from meeting_bridge.professional_preflight import install as install_professional_preflight
        from meeting_bridge.quality_runtime import install as install_quality_runtime

        install_quality_runtime()
        install_professional_preflight()
        from meeting_bridge.gui_runtime import main as gui_main

        gui_main()


if __name__ == "__main__":
    main()
