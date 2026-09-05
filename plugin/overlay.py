"""In-game overlay notifications via EDMCModernOverlay (legacy edmcoverlay API)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

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
CAPACITY_ID_PREFIX = "edplg-locker-"

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

# Pillage-line colour per journal category (Component/Item/Data), so the
# stack is scannable by category at a glance rather than one flat colour.
# Falls back to COLOUR for anything not listed here.
CATEGORY_COLOURS: Dict[str, str] = {
    "Component": "#4fc3f7",  # Assets - blue
    "Item": "#81c784",       # Goods - green
    "Data": "#ba68c8",       # Data - violet
}

# The four inventory bars the main panel (ui.py) and this overlay can both
# show - same keys, same colours, same fixed order - each independently
# togglable on the overlay via Settings (see ui.overlay_enabled_bars()).
# Canonical home for these constants is here rather than ui.py so overlay.py
# doesn't need to import from ui.py (ui.py already imports overlay.py's
# position constants - this keeps that same one-way dependency direction).
BAR_ORDER: Tuple[str, ...] = ("backpack", "ship_locker", "fleet_carrier_locker", "cargo")
BAR_COLOURS: Dict[str, str] = {
    "backpack": "#4fc3f7",
    "ship_locker": "#81c784",
    "fleet_carrier_locker": "#ba68c8",
    "cargo": "#ff8c0d",
}
BAR_DEFAULT_LABELS: Dict[str, str] = {
    "backpack": "Backpack",
    "ship_locker": "Ship Locker",
    "fleet_carrier_locker": "Carrier Locker",
    "cargo": "Cargo",
}

# Inventory bars: a persistent (long-TTL, refreshed on every relevant
# journal event) row per BAR_ORDER entry present in a render_bars() call,
# below the pillage stack.
CAPACITY_BAR_GAP = 8            # px between the pillage stack and the bars
CAPACITY_ROW_HEIGHT = 16
CAPACITY_LABEL_WIDTH = 100       # fits "Carrier Locker", the longest label
CAPACITY_BAR_WIDTH = 140
CAPACITY_BAR_HEIGHT = 10
CAPACITY_VALUE_GAP = 8
CAPACITY_TRACK_COLOUR = "#555555"
# Long enough to look persistent between updates; refreshed well before this
# on any further activity.
CAPACITY_TTL = 3600


class PillageOverlay:
    """Renders a short stack of recent pillage lines on the game overlay."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._enabled = True
        self._bars_broken = False
        # (internal_name, text, expiry, colour) — newest first.
        self._lines: List[Tuple[str, str, float, str]] = []
        self._rendered_rows = 0
        self._rendered_bar_keys: FrozenSet[str] = frozenset()
        self._origin_x = DEFAULT_ORIGIN_X
        self._origin_y = DEFAULT_ORIGIN_Y
        self._anchor: Optional[str] = None
        self._group_registered = False

    @property
    def available(self) -> bool:
        return edmcoverlay is not None

    @property
    def is_modern_overlay(self) -> bool:
        """Whether the connected provider identifies itself as EDMCModernOverlay
        (vs. the original EDMCOverlay) - gates ModernOverlay-only features like
        plugin-group registration (see _register_plugin_group)."""
        if edmcoverlay is None:
            return False
        identity = getattr(edmcoverlay, "MODERN_OVERLAY_IDENTITY", None)
        return bool(identity) and identity.get("plugin") == "EDMCModernOverlay"

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled and not enabled:
            self.clear()
        self._enabled = enabled

    def set_position(self, x: int, y: int) -> None:
        """Move where the pillage stack (and capacity bars below it) draw,
        clamped to the legacy overlay's virtual screen."""
        self._origin_x = max(0, min(MAX_ORIGIN_X, x))
        self._origin_y = max(0, min(MAX_ORIGIN_Y, y))

    def set_anchor(self, anchor: Optional[str]) -> None:
        """
        ModernOverlay-only: which screen corner/edge its controller should
        anchor ED-PLG's panel group to, instead of (or alongside) the raw
        pixel position above. Re-registers the plugin group with the new
        anchor; a no-op wherever ModernOverlay's grouping API isn't available.
        """
        self._anchor = anchor
        self._group_registered = False
        if self._client is not None:
            self._register_plugin_group()

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

    def render_bars(self, rows: List[Tuple[str, str, int, Optional[int]]]) -> None:
        """
        Draw (or refresh) the inventory-bars panel below the pillage stack:
        one row per (key, label, total, capacity) tuple in `rows` - the same
        shape (and, for whichever keys are present, the exact same data) as
        `ui.set_inventory_levels()` uses for the main panel's bars - coloured
        via `BAR_COLOURS[key]`.

        Persistent (long TTL) rather than fading like pillage lines — the
        caller re-renders after every journal event to keep it current, so a
        quiet stretch just means a slightly stale (not blank) reading.

        A key from a previous call that's absent from `rows` (the commander
        toggled that bar off in Settings, or it's a conditional bar - Carrier
        Locker/Cargo - no longer applicable) is actively cleared rather than
        left showing a stale value; passing an empty list clears everything.
        """
        if self._bars_broken:
            return

        client = self._connect()
        if client is None:
            return

        base_y = self._origin_y + MAX_LINES * LINE_HEIGHT + CAPACITY_BAR_GAP
        bar_x = self._origin_x + CAPACITY_LABEL_WIDTH

        visible = [row for row in rows if row[0] in BAR_ORDER]
        drawn_keys = set()

        for display_row, (key, label, total, capacity) in enumerate(visible):
            colour = BAR_COLOURS.get(key, COLOUR)
            row_y = base_y + display_row * CAPACITY_ROW_HEIGHT
            drawn_keys.add(key)

            self._send_text(client, f"label-{key}", label, self._origin_x, row_y, colour=colour)
            self._send_shape(
                client, f"track-{key}", "rect",
                colour=CAPACITY_TRACK_COLOUR, fill="",
                x=bar_x, y=row_y, w=CAPACITY_BAR_WIDTH, h=CAPACITY_BAR_HEIGHT,
                thickness=1,
            )

            fraction = max(0.0, min(1.0, total / capacity)) if capacity else 0.0
            fill_width = max(1, round(CAPACITY_BAR_WIDTH * fraction)) if total > 0 else 0
            if fill_width > 0:
                self._send_shape(
                    client, f"fill-{key}", "rect",
                    colour=colour, fill=colour,
                    x=bar_x, y=row_y, w=fill_width, h=CAPACITY_BAR_HEIGHT,
                )
            else:
                self._send_clear(client, f"fill-{key}")

            value_text = f"{total}/{capacity}" if capacity else str(total)
            self._send_text(
                client, f"value-{key}", value_text,
                bar_x + CAPACITY_BAR_WIDTH + CAPACITY_VALUE_GAP, row_y - 3,
                colour=colour,
            )

        for key in self._rendered_bar_keys - drawn_keys:
            for part in ("label", "track", "fill", "value"):
                self._send_clear(client, f"{part}-{key}")

        self._rendered_bar_keys = frozenset(drawn_keys)

    def clear_bars(self) -> None:
        client = self._client
        if client is None or not self._rendered_bar_keys:
            self._rendered_bar_keys = frozenset()
            return
        for key in self._rendered_bar_keys:
            for part in ("label", "track", "fill", "value"):
                self._send_clear(client, f"{part}-{key}")
        self._rendered_bar_keys = frozenset()

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
        self._send_text(
            client, str(row), text, self._origin_x, self._origin_y + row * LINE_HEIGHT,
            colour=colour, ttl=ttl, id_prefix=ID_PREFIX, feature="pillage",
        )

    def _send_text(
        self,
        client: Any,
        key: str,
        text: str,
        x: int,
        y: int,
        *,
        colour: str,
        ttl: int = CAPACITY_TTL,
        id_prefix: str = CAPACITY_ID_PREFIX,
        feature: str = "bars",
    ) -> None:
        try:
            client.send_message(f"{id_prefix}{key}", text, colour, x, y, ttl=ttl, size=TEXT_SIZE)
        except Exception:
            self._on_send_failed(feature)

    def _send_shape(
        self,
        client: Any,
        key: str,
        shape: str,
        *,
        colour: str,
        fill: str,
        x: int,
        y: int,
        w: int,
        h: int,
        thickness: Optional[int] = None,
    ) -> None:
        kwargs: Dict[str, Any] = {}
        if thickness is not None:
            kwargs["thickness"] = thickness
        try:
            client.send_shape(
                f"{CAPACITY_ID_PREFIX}{key}", shape,
                color=colour, fill=fill, x=x, y=y, w=w, h=h, ttl=CAPACITY_TTL,
                **kwargs,
            )
        except Exception:
            self._on_send_failed("bars")

    def _send_clear(self, client: Any, key: str) -> None:
        try:
            client.send_raw({"id": f"{CAPACITY_ID_PREFIX}{key}"})
        except Exception:
            self._on_send_failed("bars")

    def _on_send_failed(self, feature: str) -> None:
        """
        A pillage-line failure disables the overlay entirely (drops the
        client so the next call retries a fresh connection) — the original,
        conservative behaviour. A capacity-bars failure (e.g. a provider
        without `send_shape`) only disables bars, leaving pillage lines
        (already working on this same client) untouched.
        """
        logger.exception("Overlay send failed (%s); disabling for this session", feature)
        if feature == "pillage":
            self._client = None
            self._enabled = False
        else:
            self._bars_broken = True

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
        self._register_plugin_group()
        return self._client

    def _register_plugin_group(self) -> None:
        """
        Best-effort: register ED-PLG as its own ModernOverlay plugin group
        (background panel, anchored corner) instead of relying purely on raw
        pixel positioning. This is undocumented-by-example territory beyond
        ModernOverlay's developer notes and hasn't been validated against a
        live install - any failure (missing module, changed signature,
        legacy EDMCOverlay) is swallowed and simply leaves ED-PLG drawing
        plain positioned lines exactly as before.
        """
        if self._group_registered or not self.is_modern_overlay:
            return
        self._group_registered = True

        try:
            from overlay_plugin.overlay_api import define_plugin_group

            define_plugin_group(
                plugin_group="ED-PLG",
                matching_prefixes=[ID_PREFIX, CAPACITY_ID_PREFIX],
                id_prefix_group="pillage",
                id_prefixes=[ID_PREFIX, CAPACITY_ID_PREFIX],
                id_prefix_group_anchor=self._anchor or "ne",
                background_color="#14141ecc",
                background_border_color=COLOUR,
                background_border_width=2,
            )
            logger.info("Registered ED-PLG's ModernOverlay plugin group (anchor=%s)", self._anchor or "ne")
        except Exception:
            logger.debug("Could not register ED-PLG's ModernOverlay plugin group", exc_info=True)
