"""Tkinter UI for ED-PLG."""

from __future__ import annotations

import json
import logging
import os
from typing import Callable, Dict, FrozenSet, List, Optional, Tuple

import tkinter as tk
from tkinter import font as tkfont

import myNotebook as nb
from config import appname, config
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel

from . import __version__, suit
from .inventory import CATEGORY_SHORT, TRACKED_CATEGORIES
from .overlay import DEFAULT_ORIGIN_X, DEFAULT_ORIGIN_Y, MAX_ORIGIN_X, MAX_ORIGIN_Y
from .update import CONFIG_AUTO_UPDATE, RELEASES_PAGE_URL

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_OVERLAY_ENABLED = "edplg_overlay_enabled"
CONFIG_OVERLAY_X = "edplg_overlay_x"
CONFIG_OVERLAY_Y = "edplg_overlay_y"
CONFIG_OVERLAY_BARS_ENABLED = "edplg_overlay_bars_enabled"
CONFIG_OVERLAY_ANCHOR = "edplg_overlay_anchor"
CONFIG_SOUND_ENABLED = "edplg_sound_enabled"
CONFIG_MESSAGE_FORMAT = "edplg_message_format"
CONFIG_PANEL_COLLAPSED = "edplg_panel_collapsed"

# Main-panel section title, echoed in the collapsible header (see
# _update_header_text) - spelled-out brand name + abbreviation in parens, the
# same title-line convention as this developer's other EDMC plugins (e.g.
# EDMMM's "My Mission Manager (EDMMM)"). "ED-PLG" is the technical name
# (plugin folder, config key prefix, log namespace - see plugin_name below
# and load.py's plugin_start3 return value) and is unaffected by this brand
# name; only user-facing display text uses the new one.
PANEL_TITLE = "ED Pillage & Payload (ED-PLG)"

# Fixed order of the main-panel inventory bars. "fleet_carrier_locker" and
# "cargo" are conditional - see set_inventory_levels - and grid_remove()'d
# entirely when absent from the update rather than shown empty/stale.
BAR_ORDER: Tuple[str, ...] = ("backpack", "ship_locker", "fleet_carrier_locker", "cargo")
BAR_DEFAULT_LABELS: Dict[str, str] = {
    "backpack": "Backpack",
    "ship_locker": "Ship Locker",
    "fleet_carrier_locker": "Carrier Locker",
}

# Bar widget geometry - fixed pixel/character widths so a long label or a
# large count can never widen EDMC's main window (see the plugin_app sizing
# note in this repo's global instructions). Bars are drawn on a plain
# tk.Canvas rather than ttk.Progressbar - same approach as EDMMM's own
# progress bars (see its _progress_bar) - because a ttk widget's native theme
# chrome doesn't reliably follow EDMC's theme.update() the way plain tk
# widgets do, and a Canvas's own explicit background plus fully-covering
# rectangles sidestep that regardless of the active theme.
_BAR_NAME_WIDTH = 13
_BAR_VALUE_WIDTH = 13
_BAR_WIDTH = 80
_BAR_HEIGHT = 8

# Each bar gets its own signature colour rather than one flat fill for all
# four - Backpack/Ship Locker/Carrier Locker echo the category colours
# already used elsewhere in this plugin's overlay output (see
# overlay.CATEGORY_COLOURS), and Cargo gets the Elite accent orange since
# it's a ship/SRV concept rather than an on-foot microresource one.
BAR_COLOURS: Dict[str, str] = {
    "backpack": "#4fc3f7",
    "ship_locker": "#81c784",
    "fleet_carrier_locker": "#ba68c8",
    "cargo": "#ff8c0d",
}
_BAR_FULL_COLOUR = "#c0392b"
_BAR_DEFAULT_COLOUR = "#9e9e9e"
_BAR_TRACK_LIGHT = "#c0c4c7"
"""Fallback track colour if the live panel background can't be read at all
(see _bar_track_color) - deliberately never used under a normally-running
EDMC, just a safety net."""

# (key, label, total, capacity_or_None) for one main-panel bar row.
BarRow = Tuple[str, str, int, Optional[int]]

# The nine anchors ModernOverlay's plugin-group API accepts (see overlay.py's
# _register_plugin_group). Only meaningful when ModernOverlay is the active
# provider - see is_modern_overlay.
VALID_OVERLAY_ANCHORS = ("nw", "n", "ne", "w", "center", "e", "sw", "s", "se")
DEFAULT_OVERLAY_ANCHOR = "ne"

# JSON list of TRACKED_CATEGORIES entries whose pickups get a pillage
# notification (log line, overlay, panel status). Unset (empty string from
# config) means "not configured yet" -> every category is announced; an
# explicitly saved empty list ("[]") means the commander muted all of them.
CONFIG_ANNOUNCE_CATEGORIES = "edplg_announce_categories"

# Placeholders: {item} - resolved display name; {total} - combined total
# across backpack/ship locker/carrier locker after this pickup.
DEFAULT_MESSAGE_FORMAT = "[{item}] pillaged! New Inventory Total: {total}"

# Color for the main-panel "Updated to vX" HyperlinkLabel - the only state
# that widget ever shows text for (see _apply_version_state).
_UPDATED_COLOR = "#2e7d32"

# How long "Updated to vX" stays up on the main panel before hiding again -
# long enough to notice, short enough that you don't need to restart EDMC a
# second time just to clear it.
_UPDATED_MESSAGE_DURATION_MS = 15_000

_frame: Optional[tk.Frame] = None
_title_label: Optional[tk.Label] = None
_status_label: Optional[tk.Label] = None
_content_frame: Optional[tk.Frame] = None
_last_event_label: Optional[tk.Label] = None
_version_label: Optional[HyperlinkLabel] = None
_on_show_inventory: Optional[Callable[[], None]] = None
_bar_rows: Dict[str, Dict[str, tk.Widget]] = {}
_panel_collapsed: bool = False
_overlay_var: Optional[tk.BooleanVar] = None
_overlay_x_var: Optional[tk.StringVar] = None
_overlay_y_var: Optional[tk.StringVar] = None
_overlay_bars_var: Optional[tk.BooleanVar] = None
_overlay_anchor_var: Optional[tk.StringVar] = None
_auto_update_var: Optional[tk.BooleanVar] = None
_sound_var: Optional[tk.BooleanVar] = None
_message_format_var: Optional[tk.StringVar] = None
_announce_vars: Dict[str, tk.BooleanVar] = {}
_override_vars: Dict[Tuple[str, str], tk.StringVar] = {}
_override_defaults: Dict[Tuple[str, str], Optional[int]] = {}

# (kind, version) - kind is one of "normal", "downloading", "downloaded", "updated".
_version_state: tuple = ("normal", None)
_updated_clear_scheduled: bool = False


def create_plugin_app(
    parent: tk.Frame,
    on_show_inventory: Callable[[], None],
) -> tk.Frame:
    """
    Create the main-window frame for EDMC.

    Structure: a header row holding *only* the plugin title, always visible
    and doubling as the collapse toggle - the same click-to-collapse
    treatment, and the same bare-title-line content, as EDMMM's own panel -
    followed by a content frame (live status, inventory bars, last pickup,
    the one-time "Updated to vX" line) that's hidden entirely while
    collapsed, leaving only the title line showing.
    """
    global _frame, _title_label, _status_label, _content_frame
    global _last_event_label, _version_label, _on_show_inventory, _panel_collapsed

    _on_show_inventory = on_show_inventory
    _panel_collapsed = bool(config.get_bool(CONFIG_PANEL_COLLAPSED, default=False))

    _frame = tk.Frame(parent)
    _frame.columnconfigure(0, weight=1)

    # sticky="w" (not "ew") everywhere below: a frame stretched wider than its
    # own children exposes its own background, which doesn't reliably follow
    # EDMC's theme.update() the way its Label/Frame children's own colors do
    # - this showed up in practice as a stray white box trailing the title.
    # Sizing every container to its natural content width sidesteps that
    # regardless of the exact cause.
    header = tk.Frame(_frame, cursor="hand2")
    header.grid(row=0, column=0, sticky=tk.W)
    header.bind("<Button-1>", lambda _e: _toggle_collapsed())

    _title_label = tk.Label(header, font=_bold_font(header), cursor="hand2")
    _title_label.pack(side=tk.LEFT)
    _title_label.bind("<Button-1>", lambda _e: _toggle_collapsed())

    _content_frame = tk.Frame(_frame)
    _content_frame.grid(row=1, column=0, sticky=tk.W)

    _status_label = tk.Label(_content_frame, text="Awaiting Odyssey loot…", anchor=tk.W)
    _status_label.grid(row=0, column=0, sticky=tk.W)

    _build_bars(_content_frame)

    _last_event_label = tk.Label(_content_frame, text="", wraplength=420, justify=tk.LEFT)
    _last_event_label.grid(row=2, column=0, sticky=tk.W, pady=(2, 0))

    # The plugin version itself lives only in the Settings tab (see
    # create_prefs) - this row is reserved purely for the one-time
    # "Updated to vX" confirmation right after a staged update takes
    # effect (see _apply_version_state), so it starts hidden.
    _version_label = HyperlinkLabel(_content_frame, text="", url=RELEASES_PAGE_URL, underline=True)
    _version_label.grid(row=3, column=0, sticky=tk.W, pady=(2, 0))
    _version_label.grid_remove()
    _apply_version_state()

    _update_header_text()
    _apply_collapsed_state()

    theme.update(_frame)

    # Bars were first drawn (in _build_bars) before theme.update() had a
    # chance to colour _status_label - _bar_track_color() reads that label's
    # *current* background, so redraw now that it actually reflects the real
    # theme, rather than leaving the initial paint stuck on the pre-theme
    # guess until the first journal event calls set_inventory_levels().
    for key, widgets in _bar_rows.items():
        _draw_bar(widgets["bar"], 0, None, BAR_COLOURS.get(key, _BAR_DEFAULT_COLOUR))

    return _frame


def _bold_font(_widget: tk.Misc) -> Tuple[str, int, str]:
    try:
        base = tkfont.nametofont("TkDefaultFont")
        return (base.actual("family"), base.actual("size"), "bold")
    except Exception:
        logger.debug("Could not resolve the default font for the panel title", exc_info=True)
        return ("TkDefaultFont", 9, "bold")


def _bar_track_color() -> str:
    """
    A shade one step off the panel's actual current background - same
    derivation window.py's _stripe_colour uses for its Treeview row shading -
    so the track works correctly under Default, Dark, and Transparent alike
    without needing to detect *which* theme is active.

    Reads EDMC's own theme.current['background'] first - the exact value its
    theme.update()/_update_widget() assigns to every recoloured widget's
    background option (confirmed from EDMC's actual theme.py: 'grey4' for
    Dark/Transparent) - rather than inferring it by reading a widget back.
    Two earlier attempts did that: first a Frame's background (never
    actually touched by theme.update() - only Label/Button/Canvas are, a
    Frame just looks themed because its children cover it), then a Label's
    (which depends on EDMC's theme.apply() having already run against it by
    the moment we happen to read it, and in practice still read stale/
    default under Dark theme in the field, cause unconfirmed). Going to the
    dict directly removes that timing dependency; falling back to a Label's
    background only if theme.current isn't populated yet (e.g. reading it
    before EDMC's own theme.apply() has ever run at all).
    """
    base = None
    try:
        base = theme.current.get("background")
    except AttributeError:
        base = None

    reference = _status_label or _title_label
    if not base and reference is not None:
        try:
            base = reference.cget("background")
        except tk.TclError:
            base = None

    # Any live widget can resolve a colour spec via winfo_rgb() - it's just a
    # Tcl interpreter handle here, its own background is irrelevant to this
    # call - so _frame works even when there's no Label to read from yet.
    resolver = reference or _frame
    if not base or resolver is None:
        return _BAR_TRACK_LIGHT

    try:
        red16, green16, blue16 = resolver.winfo_rgb(base)
    except tk.TclError:
        return _BAR_TRACK_LIGHT

    red, green, blue = red16 // 256, green16 // 256, blue16 // 256
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    delta = 24 if luminance < 128 else -20

    def shift(value: int) -> int:
        return max(0, min(255, value + delta))

    return f"#{shift(red):02x}{shift(green):02x}{shift(blue):02x}"


def _draw_bar(canvas: tk.Canvas, total: int, capacity: Optional[int], colour: str) -> None:
    """
    (Re)draw one bar's track + fill rectangles, fully covering the canvas so
    nothing of the canvas's own background - or anything behind it - is ever
    visible, regardless of the active theme.

    `colour` is this bar's own signature colour (see BAR_COLOURS) - drawn as
    the track's outline even at 0% so every bar reads as distinctly "its own
    colour" rather than a flat gray box, and as the fill colour once there's
    something to show (overridden to red once at capacity).
    """
    canvas.delete("all")
    track = _bar_track_color()
    canvas.configure(background=track)
    canvas.create_rectangle(0, 0, _BAR_WIDTH - 1, _BAR_HEIGHT - 1, fill=track, outline=colour)

    if not capacity:
        return

    fraction = max(0.0, min(1.0, total / capacity))
    if fraction <= 0:
        return

    fill_colour = _BAR_FULL_COLOUR if total >= capacity else colour
    canvas.create_rectangle(0, 0, max(1, round(_BAR_WIDTH * fraction)), _BAR_HEIGHT, fill=fill_colour, outline="")


def _build_bars(parent: tk.Frame) -> None:
    """
    Create (but do not populate) one row per BAR_ORDER entry. Each row is
    click-to-open-inventory, same as the button it replaces.

    Rows are grid()-ed (one fixed row index per key, sticky=W - natural
    content width, never stretched to fill the panel) rather than packed:
    grid_remove()/grid() (see set_inventory_levels) restores a hidden row to
    its original position, where pack_forget()/pack() would instead re-append
    it after whatever's currently packed - reordering rows whenever one is
    hidden and later shown again (e.g. the Cargo row across a foot<->vehicle
    transition, or Carrier Locker once a carrier is first discovered).
    """
    global _bar_rows

    bars = tk.Frame(parent)
    bars.grid(row=1, column=0, sticky=tk.W, pady=(2, 2))
    _bar_rows = {}

    for grid_row, key in enumerate(BAR_ORDER):
        row = tk.Frame(bars, cursor="hand2")
        row.grid(row=grid_row, column=0, sticky=tk.W, pady=1)

        name_label = tk.Label(row, text=BAR_DEFAULT_LABELS.get(key, ""), width=_BAR_NAME_WIDTH, anchor=tk.W)
        name_label.pack(side=tk.LEFT)

        bar = tk.Canvas(
            row, width=_BAR_WIDTH, height=_BAR_HEIGHT,
            highlightthickness=0, borderwidth=0,
        )
        bar.pack(side=tk.LEFT, padx=(4, 4))

        value_label = tk.Label(row, text="", width=_BAR_VALUE_WIDTH, anchor=tk.W)
        value_label.pack(side=tk.LEFT)

        for widget in (row, name_label, bar, value_label):
            widget.bind("<Button-1>", _open_inventory)

        _bar_rows[key] = {"row": row, "name": name_label, "bar": bar, "value": value_label}
        _draw_bar(bar, 0, None, BAR_COLOURS.get(key, _BAR_DEFAULT_COLOUR))


def _open_inventory(_event=None) -> None:
    if _on_show_inventory is not None:
        _on_show_inventory()


def set_inventory_levels(rows: List[BarRow]) -> None:
    """
    Update the main-panel bars from (key, label, total, capacity) tuples.

    A key present in BAR_ORDER but absent from `rows` - "fleet_carrier_locker"
    while the commander owns no known fleet carrier, or "cargo" while on foot
    with no vehicle (see cargo.VehicleState.cargo_bar) - has its row hidden
    entirely rather than left stale or shown as an empty/zero reading.
    """
    if not _bar_rows:
        return

    present = {key: (label, total, capacity) for key, label, total, capacity in rows}

    for key in BAR_ORDER:
        widgets = _bar_rows.get(key)
        if widgets is None:
            continue

        row = widgets["row"]
        data = present.get(key)
        if data is None:
            row.grid_remove()
            continue

        label, total, capacity = data
        widgets["name"]["text"] = label
        widgets["value"]["text"] = f"{total}/{capacity}" if capacity else str(total)
        _draw_bar(widgets["bar"], total, capacity, BAR_COLOURS.get(key, _BAR_DEFAULT_COLOUR))
        row.grid()


def _update_header_text() -> None:
    if _title_label is None:
        return
    arrow = "▸" if _panel_collapsed else "▾"
    _title_label["text"] = f"{arrow} {PANEL_TITLE}"


def _toggle_collapsed() -> None:
    global _panel_collapsed
    _panel_collapsed = not _panel_collapsed
    config.set(CONFIG_PANEL_COLLAPSED, _panel_collapsed)
    _update_header_text()
    _apply_collapsed_state()


def _apply_collapsed_state() -> None:
    if _content_frame is None:
        return
    if _panel_collapsed:
        _content_frame.grid_remove()
    else:
        _content_frame.grid()


def run_on_main_thread(callback) -> None:
    """update.py's UpdateManager calls its on_downloading/on_ready
    callbacks from a background thread (network I/O) - marshal onto the
    frame's own event loop via after(0, ...) before touching any widget."""
    if _frame is not None and _frame.winfo_exists():
        _frame.after(0, callback)


def set_update_downloading(version: str) -> None:
    """An update is being downloaded in the background. Tracked but not
    currently rendered anywhere - see _apply_version_state."""
    global _version_state
    _version_state = ("downloading", version)
    _apply_version_state()


def set_update_downloaded(version: str) -> None:
    """An update has been staged and will apply on EDMC's next restart.
    Tracked but not currently rendered anywhere - see _apply_version_state."""
    global _version_state
    _version_state = ("downloaded", version)
    _apply_version_state()


def set_update_applied(version: str) -> None:
    """A staged update just took effect on this restart."""
    global _version_state
    _version_state = ("updated", version)
    _apply_version_state()


def _apply_version_state() -> None:
    """The main-panel version slot only ever shows text for the "updated"
    kind - "downloading"/"downloaded" are tracked (still logged by
    update.py itself) but deliberately produce no visible change here. The
    Settings tab's version label is fully static (see create_prefs) and is
    never touched by this function at all."""
    global _updated_clear_scheduled
    kind, version = _version_state
    if _version_label is None:
        return

    if kind == "updated" and version is not None:
        _version_label.configure(text=f"Updated to v{version}", url=RELEASES_PAGE_URL, foreground=_UPDATED_COLOR)
        _version_label.grid()
        if not _updated_clear_scheduled:
            _updated_clear_scheduled = True
            _version_label.after(_UPDATED_MESSAGE_DURATION_MS, _clear_updated_state)
    else:
        _version_label.grid_remove()


def _clear_updated_state() -> None:
    global _version_state, _updated_clear_scheduled
    _updated_clear_scheduled = False
    if _version_state[0] == "updated":
        _version_state = ("normal", None)
        try:
            _apply_version_state()
        except tk.TclError:
            pass  # Main window was closed before the timer fired.


def create_prefs(
    parent: nb.Notebook,
    overlay_available: bool,
    sound_available: bool,
    is_modern_overlay: bool,
    cmdr: str,
) -> nb.Frame:
    """Create the ED-PLG tab in EDMC's settings window."""
    global _overlay_var, _overlay_x_var, _overlay_y_var, _auto_update_var
    global _overlay_bars_var, _overlay_anchor_var
    global _sound_var, _message_format_var
    global _announce_vars, _override_vars, _override_defaults

    frame = nb.Frame(parent)
    frame.columnconfigure(0, weight=1)

    # Static - always shows the running version, regardless of auto-update
    # state (which only ever surfaces on the main panel, and only right
    # after an update is applied - see _apply_version_state).
    HyperlinkLabel(
        frame, text=f"ED-PLG v{__version__}", background=nb.Label().cget("background"), url=RELEASES_PAGE_URL, underline=True,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 2))

    _auto_update_var = tk.BooleanVar(value=config.get_bool(CONFIG_AUTO_UPDATE, default=False))
    nb.Checkbutton(
        frame,
        text="Automatically download updates (applied on EDMC's next restart)",
        variable=_auto_update_var,
    ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(0, 10))

    row = _build_output_format(frame, start_row=2)
    row = _build_sound_pref(frame, sound_available, start_row=row)

    _overlay_var = tk.BooleanVar(value=overlay_enabled())

    nb.Checkbutton(
        frame,
        text="Show pillage notifications on the in-game overlay",
        variable=_overlay_var,
        state=tk.NORMAL if overlay_available else tk.DISABLED,
    ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(10, 0))
    row += 1

    hint = (
        "Requires EDMCModernOverlay (or EDMCOverlay)."
        if overlay_available
        else "Install EDMCModernOverlay to enable this."
    )
    nb.Label(frame, text=hint).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(2, 10))
    row += 1

    row = _build_overlay_bars(frame, overlay_available, is_modern_overlay, start_row=row)
    row = _build_overlay_position(frame, start_row=row)
    row = _build_announce_categories(frame, start_row=row)

    _override_vars = {}
    _override_defaults = {}
    row = _build_capacity_overrides(frame, cmdr, start_row=row)

    return frame


def _build_output_format(frame: nb.Frame, *, start_row: int) -> int:
    """Add the configurable pillage-message format field."""
    global _message_format_var

    row = start_row
    nb.Label(frame, text="Pillage message:").grid(
        row=row, column=0, sticky=tk.W, padx=10, pady=(0, 2),
    )
    row += 1

    _message_format_var = tk.StringVar(value=message_format())
    nb.Entry(frame, textvariable=_message_format_var, width=55).grid(
        row=row, column=0, sticky=tk.W, padx=10,
    )
    row += 1

    nb.Label(
        frame,
        text="Placeholders: {item} (resource name), {total} (new combined total). Leave blank to reset to the default.",
        wraplength=440,
        justify=tk.LEFT,
    ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(2, 10))
    return row + 1


def _build_sound_pref(frame: nb.Frame, sound_available: bool, *, start_row: int) -> int:
    """Add the pickup notification-sound checkbox."""
    global _sound_var

    row = start_row
    _sound_var = tk.BooleanVar(value=sound_enabled())
    nb.Checkbutton(
        frame,
        text="Play a sound on pickup",
        variable=_sound_var,
        state=tk.NORMAL if sound_available else tk.DISABLED,
    ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 0))
    row += 1

    if not sound_available:
        nb.Label(frame, text="Not available on this platform.").grid(
            row=row, column=0, sticky=tk.W, padx=10, pady=(2, 10),
        )
        row += 1

    return row


def _build_overlay_bars(
    frame: nb.Frame,
    overlay_available: bool,
    is_modern_overlay: bool,
    *,
    start_row: int,
) -> int:
    """Add the ship locker capacity bars checkbox and (ModernOverlay-only) panel anchor field."""
    global _overlay_bars_var, _overlay_anchor_var

    row = start_row
    _overlay_bars_var = tk.BooleanVar(value=overlay_bars_enabled())
    nb.Checkbutton(
        frame,
        text="Show ship locker capacity bars on the overlay",
        variable=_overlay_bars_var,
        state=tk.NORMAL if overlay_available else tk.DISABLED,
    ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 0))
    row += 1

    nb.Label(
        frame,
        text="A small persistent panel below the pillage stack, refreshed whenever the ship locker changes.",
    ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(2, 10))
    row += 1

    anchor_row = nb.Frame(frame)
    anchor_row.grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 2))
    nb.Label(anchor_row, text="Overlay panel anchor:").pack(side=tk.LEFT)
    _overlay_anchor_var = tk.StringVar(value=overlay_anchor())
    nb.Entry(
        anchor_row, textvariable=_overlay_anchor_var, width=8,
        state=tk.NORMAL if is_modern_overlay else tk.DISABLED,
    ).pack(side=tk.LEFT, padx=(4, 0))
    row += 1

    anchor_hint = (
        f"One of: {', '.join(VALID_OVERLAY_ANCHORS)}. Registers ED-PLG as its own "
        "ModernOverlay panel (background + this anchor) instead of the raw X/Y "
        "position below; falls back to X/Y if that fails."
        if is_modern_overlay
        else "ModernOverlay-only (not detected) — position is set via X/Y below instead."
    )
    nb.Label(frame, text=anchor_hint, wraplength=440, justify=tk.LEFT).grid(
        row=row, column=0, sticky=tk.W, padx=10, pady=(0, 10),
    )
    return row + 1


def _build_overlay_position(frame: nb.Frame, *, start_row: int) -> int:
    """Add the in-game overlay's on-screen position fields (§overlay position)."""
    global _overlay_x_var, _overlay_y_var

    row = start_row
    x, y = overlay_position()
    _overlay_x_var = tk.StringVar(value=str(x))
    _overlay_y_var = tk.StringVar(value=str(y))

    position = nb.Frame(frame)
    position.grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 2))
    nb.Label(position, text="Overlay position — X:").pack(side=tk.LEFT)
    nb.Entry(position, textvariable=_overlay_x_var, width=6).pack(side=tk.LEFT, padx=(4, 10))
    nb.Label(position, text="Y:").pack(side=tk.LEFT)
    nb.Entry(position, textvariable=_overlay_y_var, width=6).pack(side=tk.LEFT, padx=(4, 0))
    row += 1

    nb.Label(
        frame,
        text=f"On the legacy overlay's virtual screen (0-{MAX_ORIGIN_X} x 0-{MAX_ORIGIN_Y}). "
        f"Default {DEFAULT_ORIGIN_X}, {DEFAULT_ORIGIN_Y}.",
    ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 10))
    return row + 1


def _build_announce_categories(frame: nb.Frame, *, start_row: int) -> int:
    """Add per-category checkboxes for which pickups get a pillage notification."""
    global _announce_vars

    row = start_row
    nb.Label(frame, text="Announce pickups for:").grid(
        row=row, column=0, sticky=tk.W, padx=10, pady=(0, 2),
    )
    row += 1

    enabled = announced_categories()
    _announce_vars = {}

    categories_row = nb.Frame(frame)
    categories_row.grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 10))
    for category in TRACKED_CATEGORIES:
        var = tk.BooleanVar(value=category in enabled)
        _announce_vars[category] = var
        nb.Checkbutton(categories_row, text=CATEGORY_SHORT[category], variable=var).pack(
            side=tk.LEFT, padx=(0, 12),
        )
    row += 1

    nb.Label(
        frame,
        text="Unchecked categories are still tracked and counted — only their log/overlay/panel pickup notification is muted.",
        wraplength=440,
        justify=tk.LEFT,
    ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 10))
    return row + 1


def _build_capacity_overrides(frame: nb.Frame, cmdr: str, *, start_row: int) -> int:
    """
    Add the per-loadout backpack capacity override section.

    Each row is a suit loadout the commander has been seen wearing (recorded
    from SuitLoadout/SwitchSuitLoadout journal events — see suit.py). Fields
    are pre-filled with the unengineered default for that suit; update a
    field only if that specific loadout is engineered (or otherwise holds a
    different amount than the default). Saving a value that matches the
    default is treated the same as leaving it alone — it does not fossilize
    into a stored override.
    """
    row = start_row
    nb.Label(
        frame,
        text="Suit Backpack Capacity",
    ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(14, 2))
    row += 1

    loadouts = suit.known_loadouts_for(cmdr) if cmdr else {}

    if not loadouts:
        nb.Label(
            frame,
            text=(
                "No suits recorded yet for this commander — wear a suit "
                "in-game, then reopen Settings."
            ),
        ).grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0, 10))
        return row + 1

    nb.Label(
        frame,
        text=(
            "Pre-filled with the unengineered default. If a suit is "
            "engineered — or otherwise holds a different amount — update "
            "the number to what you observe in-game."
        ),
        wraplength=440,
        justify=tk.LEFT,
    ).grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 6))
    row += 1

    for loadout_id, record in sorted(
        loadouts.items(), key=lambda kv: kv[1].get("name") or kv[0],
    ):
        row = _add_loadout_row(frame, row, loadout_id, record)

    return row


def _add_loadout_row(frame: nb.Frame, row: int, loadout_id: str, record: dict) -> int:
    suit_key = record.get("suit_key", "")
    suit_name = suit.SUIT_DISPLAY_NAMES.get(suit_key, suit_key or "Unknown suit")
    loadout_name = record.get("name") or ""
    label = f'{suit_name} — "{loadout_name}"' if loadout_name else suit_name

    nb.Label(frame, text=label).grid(
        row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(6, 0),
    )
    row += 1

    defaults = suit.default_capacity(suit_key, bool(record.get("has_capacity_mod")))
    overrides = record.get("overrides", {})

    fields = nb.Frame(frame)
    fields.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=20, pady=(0, 6))

    for col, category in enumerate(TRACKED_CATEGORIES):
        nb.Label(fields, text=f"{CATEGORY_SHORT[category]}:").grid(
            row=0, column=col * 3, sticky=tk.W, padx=(0 if col == 0 else 12, 4),
        )

        default_value = defaults.get(category)
        if category in overrides:
            initial = str(overrides[category])
        elif default_value is not None:
            initial = str(default_value)
        else:
            initial = ""

        var = tk.StringVar(value=initial)
        _override_vars[(loadout_id, category)] = var
        _override_defaults[(loadout_id, category)] = default_value
        nb.Entry(fields, textvariable=var, width=6).grid(row=0, column=col * 3 + 1, sticky=tk.W)

        if default_value is None:
            hint = nb.Label(fields, text="(no default — enter observed value)")
            hint.grid(row=0, column=col * 3 + 2, sticky=tk.W, padx=(4, 0))

    return row + 1


def overlay_enabled() -> bool:
    return bool(config.get_bool(CONFIG_OVERLAY_ENABLED, default=True))


def sound_enabled() -> bool:
    return bool(config.get_bool(CONFIG_SOUND_ENABLED, default=False))


def message_format() -> str:
    return config.get_str(CONFIG_MESSAGE_FORMAT) or DEFAULT_MESSAGE_FORMAT


def format_pillage_message(item: str, total: int) -> str:
    """Render the configured pillage message, falling back to the default on a bad template."""
    template = message_format()
    try:
        return template.format(item=item, total=total)
    except (KeyError, IndexError, ValueError):
        logger.warning("Invalid pillage message format %r; using the default", template)
        return DEFAULT_MESSAGE_FORMAT.format(item=item, total=total)


def overlay_position() -> Tuple[int, int]:
    """The in-game overlay's on-screen origin, clamped to its virtual screen."""
    x = config.get_int(CONFIG_OVERLAY_X, default=DEFAULT_ORIGIN_X)
    y = config.get_int(CONFIG_OVERLAY_Y, default=DEFAULT_ORIGIN_Y)
    return max(0, min(MAX_ORIGIN_X, x)), max(0, min(MAX_ORIGIN_Y, y))


def overlay_bars_enabled() -> bool:
    return bool(config.get_bool(CONFIG_OVERLAY_BARS_ENABLED, default=False))


def overlay_anchor() -> str:
    """ModernOverlay panel anchor; falls back to the default for an unset or invalid value."""
    raw = (config.get_str(CONFIG_OVERLAY_ANCHOR) or "").strip().lower()
    return raw if raw in VALID_OVERLAY_ANCHORS else DEFAULT_OVERLAY_ANCHOR


def announced_categories() -> FrozenSet[str]:
    """
    Categories whose pickups get a pillage notification (log line, overlay,
    panel status). Counts are always tracked for every category regardless
    of this setting — it only gates the notification.
    """
    raw = config.get_str(CONFIG_ANNOUNCE_CATEGORIES)
    if not raw:
        return frozenset(TRACKED_CATEGORIES)

    try:
        selected = json.loads(raw)
    except (TypeError, ValueError):
        return frozenset(TRACKED_CATEGORIES)

    if not isinstance(selected, list):
        return frozenset(TRACKED_CATEGORIES)

    return frozenset(category for category in selected if category in TRACKED_CATEGORIES)


def save_prefs(cmdr: str) -> bool:
    """Persist settings from the prefs tab; returns the new overlay state."""
    if _overlay_var is not None:
        config.set(CONFIG_OVERLAY_ENABLED, _overlay_var.get())
    if _auto_update_var is not None:
        config.set(CONFIG_AUTO_UPDATE, _auto_update_var.get())
    if _sound_var is not None:
        config.set(CONFIG_SOUND_ENABLED, _sound_var.get())
    if _message_format_var is not None:
        config.set(CONFIG_MESSAGE_FORMAT, _message_format_var.get().strip())
    if _overlay_bars_var is not None:
        config.set(CONFIG_OVERLAY_BARS_ENABLED, _overlay_bars_var.get())
    if _overlay_anchor_var is not None:
        anchor = _overlay_anchor_var.get().strip().lower()
        if anchor in VALID_OVERLAY_ANCHORS:
            config.set(CONFIG_OVERLAY_ANCHOR, anchor)
        elif anchor:
            logger.debug("Ignoring unrecognised overlay anchor %r", anchor)

    _save_overlay_position()
    _save_announce_categories()

    for (loadout_id, category), var in _override_vars.items():
        text = var.get().strip()
        if not text:
            suit.set_override(cmdr, loadout_id, category, None)
            continue

        try:
            value = int(text)
        except ValueError:
            logger.debug("Ignoring non-numeric capacity override %r for %s/%s", text, loadout_id, category)
            continue  # Leave the previously stored value untouched.

        if value <= 0:
            continue

        default_value = _override_defaults.get((loadout_id, category))
        if value == default_value:
            # Matches the (possibly pre-filled) default — don't fossilize it as an
            # explicit override, so a later correction to CAPACITIES isn't masked.
            suit.set_override(cmdr, loadout_id, category, None)
        else:
            suit.set_override(cmdr, loadout_id, category, value)

    suit.save_overrides()
    return overlay_enabled()


def _save_overlay_position() -> None:
    if _overlay_x_var is None or _overlay_y_var is None:
        return

    try:
        x = int(_overlay_x_var.get().strip())
        y = int(_overlay_y_var.get().strip())
    except ValueError:
        logger.debug("Ignoring non-numeric overlay position %r/%r", _overlay_x_var.get(), _overlay_y_var.get())
        return  # Leave the previously stored value untouched.

    config.set(CONFIG_OVERLAY_X, max(0, min(MAX_ORIGIN_X, x)))
    config.set(CONFIG_OVERLAY_Y, max(0, min(MAX_ORIGIN_Y, y)))


def _save_announce_categories() -> None:
    if not _announce_vars:
        return
    selected = [category for category, var in _announce_vars.items() if var.get()]
    config.set(CONFIG_ANNOUNCE_CATEGORIES, json.dumps(selected))


def set_status(message: str) -> None:
    if _status_label is not None:
        _status_label["text"] = message


def set_last_event(message: str) -> None:
    if _last_event_label is not None:
        _last_event_label["text"] = message
        _last_event_label["foreground"] = "green"
