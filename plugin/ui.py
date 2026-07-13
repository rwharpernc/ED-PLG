"""Tkinter UI for ED-PLG."""

from __future__ import annotations

from typing import Callable, Optional

import tkinter as tk

import myNotebook as nb
from config import config
from theme import theme

CONFIG_OVERLAY_ENABLED = "edplg_overlay_enabled"

_frame: Optional[tk.Frame] = None
_status_label: Optional[tk.Label] = None
_last_event_label: Optional[tk.Label] = None
_overlay_var: Optional[tk.BooleanVar] = None


def create_plugin_app(
    parent: tk.Frame,
    on_show_inventory: Callable[[], None],
) -> tk.Frame:
    """Create the main-window frame for EDMC."""
    global _frame, _status_label, _last_event_label

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

    theme.update(_frame)
    return _frame


def create_prefs(parent: nb.Notebook, overlay_available: bool) -> nb.Frame:
    """Create the ED-PLG tab in EDMC's settings window."""
    global _overlay_var

    frame = nb.Frame(parent)
    frame.columnconfigure(0, weight=1)

    _overlay_var = tk.BooleanVar(value=overlay_enabled())

    nb.Checkbutton(
        frame,
        text="Show pillage notifications on the in-game overlay",
        variable=_overlay_var,
        state=tk.NORMAL if overlay_available else tk.DISABLED,
    ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 0))

    hint = (
        "Requires EDMCModernOverlay (or EDMCOverlay)."
        if overlay_available
        else "Install EDMCModernOverlay to enable this."
    )
    nb.Label(frame, text=hint).grid(row=1, column=0, sticky=tk.W, padx=10, pady=(2, 10))

    return frame


def overlay_enabled() -> bool:
    return bool(config.get_bool(CONFIG_OVERLAY_ENABLED, default=True))


def save_prefs() -> bool:
    """Persist settings from the prefs tab; returns the new overlay state."""
    if _overlay_var is not None:
        config.set(CONFIG_OVERLAY_ENABLED, _overlay_var.get())
    return overlay_enabled()


def set_status(message: str) -> None:
    if _status_label is not None:
        _status_label["text"] = message


def set_last_event(message: str) -> None:
    if _last_event_label is not None:
        _last_event_label["text"] = message
        _last_event_label["foreground"] = "green"
