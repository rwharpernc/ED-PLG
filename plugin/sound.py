"""Optional notification sound for pillage pickups.

Uses the stdlib-only `winsound` module (Windows), so this stays true to "no
pip dependencies" the same way overlay.py stays optional when no overlay
plugin is installed — the checkbox is simply unavailable on other platforms.
"""

from __future__ import annotations

import logging
import os

from config import appname

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

try:
    import winsound  # stdlib, Windows-only
except ImportError:
    winsound = None  # type: ignore


class PillageSound:
    """Plays a short system sound on pickup, when enabled and available."""

    def __init__(self) -> None:
        self._enabled = False

    @property
    def available(self) -> bool:
        return winsound is not None

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def play(self) -> None:
        if not self._enabled or winsound is None:
            return
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            logger.exception("Notification sound failed; disabling for this session")
            self._enabled = False
