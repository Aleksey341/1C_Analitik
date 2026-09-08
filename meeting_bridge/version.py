"""Application version exposed to the packaged updater."""
from __future__ import annotations

try:
    from meeting_bridge._build_version import __version__  # type: ignore
except Exception:  # source checkout / local development
    __version__ = "0.0.0-dev"
