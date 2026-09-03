"""In-game overlay notifications via EDMCModernOverlay (legacy edmcoverlay API)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, List, Optional, Tuple

from config import appname

try:
    from EDMCOverlay import edmcoverlay  # EDMCModernOverlay, legacy EDMCOverlay
except ImportError:
    try:
        import edmcoverlay  # type: ignore
    except ImportError:
        edmcoverlay = None  # type: ignore

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

# Message IDs share the "edplg-" prefix so EDMCModernOverlay can group and
# reposition them from its controller.
ID_PREFIX = "edplg-pillage-"

MAX_LINES = 5
TTL_SECONDS = 8
# Legacy overlay coordinates are on a 1280x960 virtual screen.
MAX_ORIGIN_X = 1280
MAX_ORIGIN_Y = 960
DEFAULT_ORIGIN_X = 900
DEFAULT_ORIGIN_Y = 120
LINE_HEIGHT = 18
COLOUR = "#ffbf00"
TEXT_SIZE = "normal"


class PillageOverlay:
    """Renders a short stack of recent pillage lines on the game overlay."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._enabled = True
        # (internal_name, text, expiry, colour) — newest first.
        self._lines: List[Tuple[str, str, float, str]] = []
        self._rendered_rows = 0
        self._origin_x = DEFAULT_ORIGIN_X
        self._origin_y = DEFAULT_ORIGIN_Y

    @property
    def available(self) -> bool:
        return edmcoverlay is not None

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled and not enabled:
            self.clear()
        self._enabled = enabled

    def set_position(self, x: int, y: int) -> None:
        """Move where the pillage stack draws, clamped to the legacy overlay's virtual screen."""
        self._origin_x = max(0, min(MAX_ORIGIN_X, x))
        self._origin_y = max(0, min(MAX_ORIGIN_Y, y))

    def notify(
        self,
        internal_name: str,
        text: str,
        *,
        colour: str = COLOUR,
        ttl: int = TTL_SECONDS,
    ) -> None:
        """
        Push a line, replacing any live line keyed by the same internal_name.

        Pillage notifications key on the resource's internal name; other
        callers (e.g. ship locker capacity warnings) use their own distinct
        key so they don't collide with or get replaced by item pickups.
        """
        if not self._enabled:
            return

        client = self._connect()
        if client is None:
            return

        now = time.monotonic()
        self._lines = [line for line in self._lines if line[0] != internal_name]
        self._lines.insert(0, (internal_name, text, now + ttl, colour))
        self._prune(now)
        self._render(client, now)

    def clear(self) -> None:
        client = self._client
        self._lines = []
        if client is None:
            return
        for row in range(self._rendered_rows):
            self._send(client, row, "", ttl=1)
        self._rendered_rows = 0

    def _prune(self, now: float) -> None:
        self._lines = [line for line in self._lines if line[2] > now][:MAX_LINES]

    def _render(self, client: Any, now: float) -> None:
        for row, (_name, text, expiry, colour) in enumerate(self._lines):
            ttl = max(1, int(round(expiry - now)))
            self._send(client, row, text, ttl=ttl, colour=colour)

        # Blank any rows left over from a previous, taller render.
        for row in range(len(self._lines), self._rendered_rows):
            self._send(client, row, "", ttl=1)

        self._rendered_rows = len(self._lines)

    def _send(self, client: Any, row: int, text: str, *, ttl: int, colour: str = COLOUR) -> None:
        try:
            client.send_message(
                f"{ID_PREFIX}{row}",
                text,
                colour,
                self._origin_x,
                self._origin_y + row * LINE_HEIGHT,
                ttl=ttl,
                size=TEXT_SIZE,
            )
        except Exception:
            logger.exception("Overlay send failed; disabling overlay for this session")
            self._client = None
            self._enabled = False

    def _connect(self) -> Optional[Any]:
        if self._client is not None:
            return self._client
        if edmcoverlay is None:
            logger.debug("No overlay plugin installed; skipping overlay notification")
            return None

        try:
            self._client = edmcoverlay.Overlay()
        except Exception:
            logger.exception("Could not create overlay client")
            return None

        logger.info("Overlay client ready (EDMCModernOverlay / edmcoverlay)")
        return self._client
