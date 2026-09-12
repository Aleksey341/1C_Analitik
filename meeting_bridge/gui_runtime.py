"""Runtime-safe entry point for the autonomous 1C Analitik UI.

UX v2 builds its settings panel before the legacy bootstrap runs.  The settings
panel already needs the Tk variables used by auto-reply and response mode, so
create those variables before delegating to the v2 layout builder.
"""
from __future__ import annotations

import customtkinter as ctk

from meeting_bridge import gui as legacy
from meeting_bridge import gui_v2


class MeetingBridgeApp(gui_v2.MeetingBridgeApp):
    """UX v2 with Tk variables initialized before child widgets bind to them."""

    def _build(self) -> None:
        # At this point CTk itself has already been initialized by the legacy
        # constructor, but the overridden layout has not been built yet.
        # Keep these exact variable objects because the settings checkbox binds
        # to auto_reply_var while gui_v2._build() later creates replacement
        # variables for backward compatibility with the old UI.
        auto_reply_var = ctk.BooleanVar(value=True)
        spoken_mode_var = ctk.BooleanVar(value=False)
        self.auto_reply_var = auto_reply_var
        self.spoken_mode_var = spoken_mode_var

        super()._build()

        # Restore the variables that actual widgets are bound to.  Bootstrap,
        # polling and toggle handlers must all read/write the same objects.
        self.auto_reply_var = auto_reply_var
        self.spoken_mode_var = spoken_mode_var


def main() -> None:
    legacy.ensure_project_cwd()
    MeetingBridgeApp().mainloop()
