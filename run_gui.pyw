# Launch Meeting Bridge GUI without a console window.
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG = ROOT / "gui-launch.log"


def _fail(exc: BaseException) -> None:
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        LOG.write_text(text, encoding="utf-8")
    except OSError:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        # Avoid dumping huge / binary-looking text into MsgBox; keep it short ASCII-safe.
        brief = str(exc)
        if len(brief) > 400:
            brief = brief[:400] + "…"
        messagebox.showerror(
            "Meeting Bridge",
            "Не удалось запустить окно.\n\n"
            f"{brief}\n\n"
            f"Подробности:\n{LOG}",
        )
        root.destroy()
    except Exception:
        pass


try:
    from meeting_bridge.gui import main

    main()
except Exception as exc:  # noqa: BLE001
    _fail(exc)
    raise SystemExit(1) from exc
