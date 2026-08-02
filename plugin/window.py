"""Tabbed inventory window for ED-PLG."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Dict, Mapping, Optional

from config import appname, config
from theme import theme

from .inventory import InventoryTracker, TRACKED_CATEGORIES
from .names import display_name
from .suit import SuitState

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

CONFIG_GEOMETRY = "edplg_window_geometry"

# Ship locker holds up to 1000 of each category.
SHIP_LOCKER_CAPACITY: Dict[str, int] = {category: 1000 for category in TRACKED_CATEGORIES}

# Journal category -> in-game wording.
CATEGORY_LABELS: Dict[str, str] = {
    "Component": "Assets (Components)",
    "Item": "Goods (Items)",
    "Data": "Data",
}

# Short form, for the Category column.
CATEGORY_SHORT: Dict[str, str] = {
    "Component": "Assets",
    "Item": "Goods",
    "Data": "Data",
}

MIN_WIDTH = 720
MIN_HEIGHT = 420
DEFAULT_GEOMETRY = "900x650"

# key, tab label, in-window heading
TABS = (
    ("backpack", "  BACKPACK  ", "Backpack — carried on foot"),
    ("ship_locker", "  SHIP LOCKER  ", "Ship Locker — stored aboard your ship"),
    ("fleet_carrier_locker", "  CARRIER LOCKER  ", "Carrier Locker — from CAPI, may lag 15–30 min"),
)

# Styles are namespaced so they cannot disturb EDMC's own ttk widgets.
STYLE_TREE = "EDPLG.Treeview"
STYLE_NOTEBOOK = "EDPLG.TNotebook"
STYLE_TAB = "EDPLG.TNotebook.Tab"

_window: Optional["InventoryWindow"] = None


def _configure_styles(widget: tk.Misc) -> int:
    """
    Size the Treeview rows to the theme's actual font.

    ttk.Treeview keeps its default row height regardless of font, so under EDMC's
    theme the text collides. Derive the height from the font's line spacing and
    return it so the caller can size the window to match.
    """
    style = ttk.Style(widget)

    font = None
    try:
        font = tkfont.nametofont("TkDefaultFont")
        line_height = font.metrics("linespace")
    except Exception:
        logger.debug("Could not measure the theme font; using a default row height", exc_info=True)
        line_height = 16

    row_height = max(20, line_height + 8)

    style.configure(STYLE_TREE, rowheight=row_height)
    style.configure(f"{STYLE_TREE}.Heading", padding=(4, 4))
    style.configure(STYLE_NOTEBOOK, tabmargins=(4, 4, 4, 0))
    style.configure(STYLE_TAB, padding=(14, 7))

    # Make the selected tab unmistakable: raised, and bold where the font is known.
    if font is not None:
        bold = (font.actual("family"), font.actual("size"), "bold")
        style.map(STYLE_TAB, expand=[("selected", (1, 2, 1, 0))], font=[("selected", bold)])
    else:
        style.map(STYLE_TAB, expand=[("selected", (1, 2, 1, 0))])

    return row_height


def show(parent: tk.Misc, tracker: InventoryTracker, suit: SuitState) -> None:
    """Open the inventory window, or raise it if already open."""
    global _window

    if _window is not None and _window.alive:
        _window.refresh()
        _window.lift()
        return

    _window = InventoryWindow(parent, tracker, suit)


def refresh() -> None:
    """Update the window if it is open."""
    if _window is not None and _window.alive:
        _window.refresh()


def close() -> None:
    if _window is not None and _window.alive:
        _window.close()


def _restore_geometry() -> str:
    """
    Saved geometry, grown to the current minimum if it was saved when the window
    was smaller. Position is kept; an undersized saved width/height is discarded.
    """
    saved = config.get_str(CONFIG_GEOMETRY)
    if not saved:
        return DEFAULT_GEOMETRY

    size, sep, position = saved.partition("+")
    width, _, height = size.partition("x")

    try:
        too_small = int(width) < MIN_WIDTH or int(height) < MIN_HEIGHT
    except ValueError:
        logger.debug("Unparseable saved geometry %r; using the default", saved)
        return DEFAULT_GEOMETRY

    if not too_small:
        return saved

    # Keep where the user put it, but restore a usable size.
    return f"{DEFAULT_GEOMETRY}+{position}" if sep else DEFAULT_GEOMETRY


def _stripe_colour(widget: tk.Misc) -> str:
    """
    A row shade one step off the theme's Treeview background.

    Derived rather than hardcoded so it lands correctly under both EDMC's dark and
    light themes: dark backgrounds are lightened, light ones darkened.
    """
    style = ttk.Style(widget)
    base = (
        style.lookup(STYLE_TREE, "background")
        or style.lookup("Treeview", "background")
        or "#ffffff"
    )

    try:
        r16, g16, b16 = widget.winfo_rgb(base)
    except tk.TclError:
        logger.debug("Could not resolve the Treeview background %r", base, exc_info=True)
        return base

    red, green, blue = r16 // 256, g16 // 256, b16 // 256
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    delta = 20 if luminance < 128 else -16

    def shift(value: int) -> int:
        return max(0, min(255, value + delta))

    return f"#{shift(red):02x}{shift(green):02x}{shift(blue):02x}"


class InventoryWindow:
    """Toplevel with a tab per storage location."""

    def __init__(self, parent: tk.Misc, tracker: InventoryTracker, suit: SuitState) -> None:
        self._tracker = tracker
        self._suit = suit

        self._toplevel = tk.Toplevel(parent)
        self._toplevel.title("ED-PLG — Inventory")
        self._toplevel.protocol("WM_DELETE_WINDOW", self.close)
        self._toplevel.minsize(MIN_WIDTH, MIN_HEIGHT)

        row_height = _configure_styles(self._toplevel)
        self._toplevel.geometry(_restore_geometry())

        container = ttk.Frame(self._toplevel)
        container.pack(fill=tk.BOTH, expand=True)

        self._heading = ttk.Label(container, text="", anchor=tk.W)
        self._heading.pack(fill=tk.X, padx=10, pady=(10, 6))

        notebook = ttk.Notebook(container, style=STYLE_NOTEBOOK)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10)

        self._tabs: Dict[str, _LocationTab] = {}
        for key, tab_label, tab_heading in TABS:
            tab = _LocationTab(notebook, tab_heading, row_height)
            notebook.add(tab.frame, text=tab_label)
            self._tabs[key] = tab

        buttons = ttk.Frame(container)
        buttons.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Close", command=self.close).pack(side=tk.RIGHT)

        try:
            theme.update(self._toplevel)
        except Exception:
            logger.debug("Theme could not be applied to the inventory window", exc_info=True)

        self.refresh()

    @property
    def alive(self) -> bool:
        try:
            return bool(self._toplevel.winfo_exists())
        except tk.TclError:
            return False

    def lift(self) -> None:
        self._toplevel.deiconify()
        self._toplevel.lift()

    def refresh(self) -> None:
        if not self.alive:
            return

        snapshot = self._tracker.snapshot()
        self._heading["text"] = f"Suit: {self._suit.display_name}"

        capacities = {
            "backpack": self._suit.capacities(),
            "ship_locker": SHIP_LOCKER_CAPACITY,
            "fleet_carrier_locker": {},
        }

        # No fresh Backpack/Resupply event yet this session — commonly hit when
        # logging in already on foot. The counts below may be stale or zero
        # rather than a confirmed empty backpack; say so instead of guessing.
        backpack_note = (
            None
            if self._tracker.backpack_baseline_seen
            else "Not yet synced this session — loot, resupply, or disembark to refresh."
        )
        notes = {"backpack": backpack_note, "ship_locker": None, "fleet_carrier_locker": None}

        for key, tab in self._tabs.items():
            tab.update(snapshot.get(key, {}), capacities[key], note=notes[key])

    def close(self) -> None:
        if self.alive:
            config.set(CONFIG_GEOMETRY, self._toplevel.winfo_geometry())
            self._toplevel.destroy()


class _LocationTab:
    """Per-category totals plus an item listing for one storage location."""

    def __init__(self, parent: ttk.Notebook, heading: str, row_height: int) -> None:
        self.frame = ttk.Frame(parent)

        # Repeat the location inside the tab: the ttk tab strip is easy to misread,
        # this label never is.
        title = ttk.Label(self.frame, text=heading, anchor=tk.W)
        try:
            base = tkfont.nametofont("TkDefaultFont")
            title.configure(
                font=(base.actual("family"), base.actual("size") + 1, "bold"),
            )
        except Exception:
            logger.debug("Could not bold the tab heading", exc_info=True)
        title.pack(fill=tk.X, padx=10, pady=(10, 8))

        self._note = ttk.Label(self.frame, text="", anchor=tk.W, foreground="#c07000")
        self._note.pack(fill=tk.X, padx=10, pady=(0, 4))

        summary = ttk.Frame(self.frame)
        summary.pack(fill=tk.X, padx=10, pady=(0, 10))
        summary.columnconfigure(3, weight=1)

        self._bars: Dict[str, ttk.Progressbar] = {}
        self._totals: Dict[str, ttk.Label] = {}

        for row, category in enumerate(TRACKED_CATEGORIES):
            ttk.Label(summary, text=CATEGORY_LABELS[category], width=22, anchor=tk.W).grid(
                row=row, column=0, sticky=tk.W, pady=3,
            )
            bar = ttk.Progressbar(summary, maximum=100, length=220)
            bar.grid(row=row, column=1, padx=(6, 10), sticky=tk.W)
            total = ttk.Label(summary, text="0", width=22, anchor=tk.W)
            total.grid(row=row, column=2, sticky=tk.W)

            self._bars[category] = bar
            self._totals[category] = total

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10)

        table = ttk.Frame(self.frame)
        table.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._tree = ttk.Treeview(
            table,
            columns=("item", "category", "count"),
            show="headings",
            selectmode="none",
            style=STYLE_TREE,
        )
        self._tree.heading("item", text="Resource")
        self._tree.heading("category", text="Category")
        self._tree.heading("count", text="Held")
        self._tree.column("item", width=420, minwidth=220, anchor=tk.W, stretch=True)
        self._tree.column("category", width=140, minwidth=100, anchor=tk.W, stretch=False)
        self._tree.column("count", width=90, minwidth=70, anchor=tk.E, stretch=False)

        # Alternating row shading, so long lists stay readable.
        self._tree.tag_configure("odd", background=_stripe_colour(self._tree))

        scrollbar = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update(
        self,
        store: Mapping[str, Mapping[str, int]],
        capacities: Mapping[str, int],
        *,
        note: Optional[str] = None,
    ) -> None:
        self._note["text"] = note or ""

        for category in TRACKED_CATEGORIES:
            items = store.get(category, {})
            total = sum(items.values())
            capacity = capacities.get(category)

            if capacity:
                self._totals[category]["text"] = f"{total} / {capacity}"
                self._bars[category]["value"] = min(100, round(total * 100 / capacity))
            else:
                self._totals[category]["text"] = f"{total}  (capacity unknown)"
                self._bars[category]["value"] = 0

        self._tree.delete(*self._tree.get_children())

        rows = 0
        for category in TRACKED_CATEGORIES:
            items = store.get(category, {})
            for name, count in sorted(items.items(), key=lambda kv: (-kv[1], kv[0])):
                self._tree.insert(
                    "",
                    tk.END,
                    values=(display_name(name), CATEGORY_SHORT[category], count),
                    tags=("odd",) if rows % 2 else (),
                )
                rows += 1

        if rows == 0:
            self._tree.insert("", tk.END, values=("(nothing stored)", "", ""))
