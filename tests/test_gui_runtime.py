from __future__ import annotations

import inspect

from meeting_bridge import gui_runtime, gui_v2


def test_runtime_ui_wraps_v2_app():
    assert issubclass(gui_runtime.MeetingBridgeApp, gui_v2.MeetingBridgeApp)


def test_runtime_initializes_bound_vars_before_parent_build():
    source = inspect.getsource(gui_runtime.MeetingBridgeApp._build)
    parent_call = source.index("super()._build()")
    assert source.index("self.auto_reply_var = auto_reply_var") < parent_call
    assert source.index("self.spoken_mode_var = spoken_mode_var") < parent_call
    # The same widget-bound variables are restored after gui_v2's compatibility
    # assignments, so bootstrap and toggle handlers operate on the bound state.
    assert source.rindex("self.auto_reply_var = auto_reply_var") > parent_call
    assert source.rindex("self.spoken_mode_var = spoken_mode_var") > parent_call
