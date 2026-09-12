# Launch 1C Analitik GUI without a console window.
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG = ROOT / "gui-launch.log"


def _write_error(exc: BaseException) -> None:
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        LOG.write_text(text, encoding="utf-8")
    except OSError:
        pass


def _fail(exc: BaseException) -> None:
    _write_error(exc)
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        brief = str(exc)
        if len(brief) > 400:
            brief = brief[:400] + "…"
        messagebox.showerror(
            "1С Аналитик",
            "Не удалось запустить приложение.\n\n"
            f"{brief}\n\n"
            f"Подробности:\n{LOG}",
        )
        root.destroy()
    except Exception:
        pass


def _self_test() -> None:
    """Validate the installed bundle without opening any GUI."""
    from meeting_bridge.config import load_config, model_files_ready
    from meeting_bridge.quality_runtime import install as install_quality_runtime
    from meeting_bridge.skills import load_skills
    from meeting_bridge.version import __version__

    example = ROOT / "config.example.yaml"
    if not example.exists():
        raise RuntimeError("config.example.yaml is missing")

    cfg = load_config(example)
    model_dir = ROOT / cfg.model_dir
    if not model_files_ready(model_dir):
        raise RuntimeError(f"STT model is incomplete: {model_dir}")

    skills = load_skills()
    if len(skills) != 9:
        raise RuntimeError(f"Expected 9 analyst skills, found {len(skills)}")

    if getattr(sys, "frozen", False) and __version__ == "0.0.0-dev":
        raise RuntimeError("Packaged build version was not embedded")

    install_quality_runtime()
    import meeting_bridge.gui_runtime  # noqa: F401


if "--self-test" in sys.argv:
    try:
        _self_test()
    except Exception as exc:  # noqa: BLE001
        _write_error(exc)
        raise SystemExit(2) from exc
    raise SystemExit(0)


try:
    from meeting_bridge.first_run import ensure_first_run

    ensure_first_run(ROOT)

    import meeting_bridge.gui as legacy_gui
    from meeting_bridge.quality_runtime import install as install_quality_runtime

    install_quality_runtime()
    import meeting_bridge.gui_runtime as gui

    # Keep config, transcripts, scripts and bundled STT assets in install dir.
    legacy_gui.ROOT = ROOT
    gui.main()
except SystemExit:
    raise
except Exception as exc:  # noqa: BLE001
    _fail(exc)
    raise SystemExit(1) from exc
