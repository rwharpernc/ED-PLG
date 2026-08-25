"""Tkinter UI for ED-PLG."""

from __future__ import annotations

import logging
import os
from typing import Callable, Dict, Optional, Tuple

import tkinter as tk

import myNotebook as nb
from config import appname, config
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel

from . import __version__, suit
from .inventory import CATEGORY_SHORT, TRACKED_CATEGORIES
from .update import CONFIG_AUTO_UPDATE, RELEASES_PAGE_URL

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_OVERLAY_ENABLED = "edplg_overlay_enabled"

# Color for the main-panel "Updated to vX" HyperlinkLabel - the only state
# that widget ever shows text for (see _apply_version_state).
_UPDATED_COLOR = "#2e7d32"

# How long "Updated to vX" stays up on the main panel before hiding again -
# long enough to notice, short enough that you don't need to restart EDMC a
# second time just to clear it.
_UPDATED_MESSAGE_DURATION_MS = 15_000

_frame: Optional[tk.Frame] = None
_status_label: Optional[tk.Label] = None
_last_event_label: Optional[tk.Label] = None
_version_label: Optional[HyperlinkLabel] = None
_overlay_var: Optional[tk.BooleanVar] = None
_auto_update_var: Optional[tk.BooleanVar] = None
_override_vars: Dict[Tuple[str, str], tk.StringVar] = {}
_override_defaults: Dict[Tuple[str, str], Optional[int]] = {}

# (kind, version) - kind is one of "normal", "downloading", "downloaded", "updated".
_version_state: tuple = ("normal", None)
_updated_clear_scheduled: bool = False


def create_plugin_app(
    parent: tk.Frame,
    on_show_inventory: Callable[[], None],
) -> tk.Frame:
    """Create the main-window frame for EDMC."""
    global _frame, _status_label, _last_event_label, _version_label

    _frame = tk.Frame(parent)
    _frame.columnconfigure(1, weight=1)

    title = tk.Label(_frame, text="ED-PLG:")
    title.grid(row=0, column=0, sticky=tk.W, padx=(0, 4))

    _status_label = tk.Label(_frame, text="Awaiting Odyssey loot…")
    _status_label.grid(row=0, column=1, sticky=tk.W)

    inventory_button = tk.Button(_frame, text="Inventory", command=on_show_inventory)
    inventory_button.grid(row=0, column=2, sticky=tk.E, padx=(4, 0))

    _last_event_label = tk.Label(_frame, text="", wraplength=420, justify=tk.LEFT)
    _last_event_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))

    # The plugin version itself lives only in the Settings tab (see
    # create_prefs) - this row is reserved purely for the one-time
    # "Updated to vX" confirmation right after a staged update takes
    # effect (see _apply_version_state), so it starts hidden.
    _version_label = HyperlinkLabel(_frame, text="", url=RELEASES_PAGE_URL, underline=True)
    _version_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
    _version_label.grid_remove()
    _apply_version_state()

    theme.update(_frame)
    return _frame


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


def create_prefs(parent: nb.Notebook, overlay_available: bool, cmdr: str) -> nb.Frame:
    """Create the ED-PLG tab in EDMC's settings window."""
    global _overlay_var, _auto_update_var, _override_vars, _override_defaults

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

    _overlay_var = tk.BooleanVar(value=overlay_enabled())

    nb.Checkbutton(
        frame,
        text="Show pillage notifications on the in-game overlay",
        variable=_overlay_var,
        state=tk.NORMAL if overlay_available else tk.DISABLED,
    ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=(10, 0))

    hint = (
        "Requires EDMCModernOverlay (or EDMCOverlay)."
        if overlay_available
        else "Install EDMCModernOverlay to enable this."
    )
    nb.Label(frame, text=hint).grid(row=3, column=0, sticky=tk.W, padx=10, pady=(2, 10))

    _override_vars = {}
    _override_defaults = {}
    row = _build_capacity_overrides(frame, cmdr, start_row=4)

    return frame


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


def save_prefs(cmdr: str) -> bool:
    """Persist settings from the prefs tab; returns the new overlay state."""
    if _overlay_var is not None:
        config.set(CONFIG_OVERLAY_ENABLED, _overlay_var.get())
    if _auto_update_var is not None:
        config.set(CONFIG_AUTO_UPDATE, _auto_update_var.get())

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


def set_status(message: str) -> None:
    if _status_label is not None:
        _status_label["text"] = message


def set_last_event(message: str) -> None:
    if _last_event_label is not None:
        _last_event_label["text"] = message
        _last_event_label["foreground"] = "green"
