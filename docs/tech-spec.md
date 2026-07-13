# ED-PLG Technical Specification

**Version:** 0.7.0  
**Author:** CMDR Mactavious  
**Last updated:** 2026-07-13

## 1. Overview

ED-PLG is a **package plugin** for Elite Dangerous Market Connector. It implements
the EDMC Python 3 plugin API (`plugin_start3`) and processes journal events
delivered through `journal_entry()`.

| Property | Value |
|----------|-------|
| Plugin folder name | `EDPLG` (must match for EDMC logging) |
| Internal display name | `ED-PLG` (returned from `plugin_start3`) |
| Language | Python 3.9+ (bundled with EDMC) |
| UI framework | Tkinter (via EDMC main window) |
| Build output | `dist/EDPLG/` |

## 2. Repository Layout

```
ED-PLG/
├── plugin/                 # Source — deployed to dist/EDPLG/
│   ├── __init__.py         # __version__
│   ├── load.py             # EDMC callbacks (entry point)
│   ├── inventory.py        # InventoryTracker
│   ├── suit.py             # SuitState + backpack capacity table
│   ├── overlay.py          # PillageOverlay (EDMCModernOverlay client)
│   ├── window.py           # Tabbed inventory Toplevel
│   ├── names.py            # ID → display name mapping
│   └── ui.py               # Tkinter panel + settings tab
├── scripts/build.mjs       # Copies plugin/ → dist/EDPLG/
├── docs/                   # Specifications and attributions
├── dist/EDPLG/             # Build artefact (gitignored)
├── LICENSE                 # MIT
├── CHANGELOG.md
└── README.md
```

## 3. EDMC Plugin API Surface

### 3.1 Implemented callbacks

| Function | Module | Description |
|----------|--------|-------------|
| `plugin_start3(plugin_dir: str) -> str` | `load.py` | Initialisation; returns `"ED-PLG"`. |
| `plugin_stop() -> None` | `load.py` | Shutdown hook; clears overlay and closes the window. |
| `plugin_app(parent: tk.Frame) -> tk.Frame` | `load.py` | Creates main-window UI frame. |
| `plugin_prefs(parent, cmdr, is_beta) -> nb.Frame` | `load.py` | Creates the settings tab. |
| `prefs_changed(cmdr, is_beta) -> None` | `load.py` | Persists settings. |
| `journal_entry(...) -> Optional[str]` | `load.py` | Processes journal events. |
| `capi_fleetcarrier(data: CAPIData) -> Optional[str]` | `load.py` | Reads carrier locker from CAPI. |

### 3.2 Not implemented

- `cmdr_data` — no commander CAPI integration.
- `dashboard_entry` — `Status.json` is not read.
- `journal_entry_cqc` — CQC/Arena sessions ignored.

### 3.3 Allowed EDMC imports

```python
from companion import CAPIData      # Fleet carrier CAPI typing (load.py)
from config import appname          # Logger naming
from config import config           # Settings + window geometry persistence
from theme import theme             # UI theming (ui.py, window.py)
import myNotebook as nb             # Settings tab widgets (ui.py)
```

No other core EDMC modules are imported. Inventory data is read from the
`state` dict passed into `journal_entry()`, not from `monitor` directly.

### 3.4 Optional third-party integration

```python
try:
    from EDMCOverlay import edmcoverlay   # EDMCModernOverlay
except ImportError:
    try:
        import edmcoverlay                # legacy / alternative shim
    except ImportError:
        edmcoverlay = None                # feature disabled, plugin still loads
```

EDMCModernOverlay ships an `EDMCOverlay/edmcoverlay.py` compatibility layer
exposing the legacy `Overlay` class, so ED-PLG codes against the legacy API and
works with either overlay plugin. The import is resolved from EDMC's plugins
directory at load time; a missing overlay is a supported configuration.

## 4. Logging

Logger setup follows [PLUGINS.md](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md):

```python
plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")
```

- `plugin_name` **must** equal the plugin folder name (`EDPLG`).
- Pillage events: `logger.info(...)`.
- Baseline sync: `logger.info(...)` / `logger.debug(...)`.

Log destination: `%TEMP%\EDMarketConnector.log` (Windows).

## 5. Journal Events

### 5.1 Handled events

| Event | Handler behaviour |
|-------|-------------------|
| `LoadGame` | Full baseline sync from `state` (backpack + ship locker); set commander. |
| `Start` | Same as `LoadGame` (EDMC started while game running). |
| `Backpack` | Parse journal/JSON baseline; sync backpack from `state`. |
| `Resupply` | Same handler as `Backpack`. |
| `ShipLocker` | Parse locker baseline; sync ship locker from `state`. |
| `SuitLoadout` | Record suit + mods; sync backpack from `state` (disembark / on-foot start). |
| `SwitchSuitLoadout` | Same handler as `SuitLoadout`. |
| `BackpackChange` | Apply deltas; log pillage, update panel, and send overlay for `Added` items. |
| `CarrierDecommission` | Drop cached carrier locker for the commander. |

Every handled event ends by calling `window.refresh()`, which is a no-op unless the
inventory window is open.

### 5.2 BackpackChange schema

```json
{
  "timestamp": "2025-06-30T12:00:00Z",
  "event": "BackpackChange",
  "Added": [
    {
      "Name": "manufacturinginstructions",
      "Name_Localised": "Manufacturing Instructions",
      "Count": 1,
      "Type": "Data"
    }
  ],
  "Removed": []
}
```

Processing rules:

- `Type` maps to category: `Component`, `Item`, `Data` (Consumable ignored for output).
- `Name` is canonicalised before storage.
- `Added` with `Count > 0` triggers pillage log line.
- `Removed` updates internal counts only.

### 5.3 SuitLoadout schema

```json
{
  "timestamp": "2026-07-13T14:54:33Z",
  "event": "SuitLoadout",
  "SuitID": 1833402702722211,
  "SuitName": "explorationsuit_class3",
  "SuitName_Localised": "$ExplorationSuit_Class1_Name;",
  "SuitMods": [ "suit_backpackcapacity", "suit_nightvision" ],
  "LoadoutID": 4293000001,
  "LoadoutName": "Exo 3 NVG",
  "Modules": []
}
```

Processing rules:

- `SuitName` is split on `_class` into a suit key and grade (`explorationsuit`, `3`).
  Grade does not affect capacity.
- `SuitMods` is scanned for `suit_backpackcapacity`, which selects the modded row of
  the capacity table.
- `SuitName_Localised` is **ignored**: Frontier emits an unresolved `$Token;`
  placeholder here, so display names come from `SUIT_DISPLAY_NAMES` instead.

### 5.4 EDMC state keys used

From the `state` dict in `journal_entry()`:

| Key | Usage |
|-----|-------|
| `BackPack` | Dict of `{ Component, Item, Data, Consumable }` → `{ name: count }`. |
| `Component` | Ship locker components. |
| `Item` | Ship locker items. |
| `Data` | Ship locker data. |

Ship engineering keys (`Raw`, `Manufactured`, `Encoded`) are **not** read.

### 5.5 CAPI fleet carrier

`capi_fleetcarrier(data)` reads `data["carrierLocker"]`, whose `assets` / `goods` /
`data` sections map to the journal's `Component` / `Item` / `Data` categories.
Entries expose `name`, `locName`, and `quantity`. Results are cached per
`data.request_cmdr`, and only applied to the live store when that commander is the
active one.

## 6. Module Reference

### 6.1 `inventory.py` — `InventoryTracker`

```python
class InventoryTracker:
    def sync_all_from_state(state) -> None
    def sync_backpack_from_state(state) -> None
    def sync_ship_locker_from_state(state) -> None
    def apply_backpack_baseline(entry) -> None
    def apply_ship_locker_baseline(entry) -> None
    def apply_backpack_change(entry) -> Iterable[Tuple[str, str, int, int]]
    def apply_fleet_carrier_locker(carrier_locker, *, callsign, cmdr) -> int
    def clear_fleet_carrier_for_commander(cmdr) -> None
    def set_commander(cmdr) -> bool
    def get_combined_total(internal_name, category) -> int
    def snapshot() -> Dict[str, InventoryStore]
```

`apply_backpack_change` yields `(display_label, internal_name, delta, backpack_total)`
for each **Added** tracked item.

`snapshot()` returns a deep copy keyed `backpack` / `ship_locker` /
`fleet_carrier_locker` — the read model for `window.py`.

Tracked categories constant:

```python
TRACKED_CATEGORIES = ("Component", "Item", "Data")
```

All journal and CAPI parsing paths call `names.remember()` with the entry's
`Name_Localised` / `locName`, populating the learned-name cache as a side effect.

### 6.2 `suit.py` — `SuitState`

```python
BACKPACK_CAPACITY_MOD = "suit_backpackcapacity"
SUIT_DISPLAY_NAMES: Dict[str, str]              # suit key → "Maverick Suit"
CAPACITIES: Dict[str, Optional[SuitCapacities]] # suit key → {"base": {...}, "modded": {...}}

class SuitState:
    def apply_suit_loadout(entry) -> None
    def capacities() -> Dict[str, int]   # {} when unknown
    @property known / has_capacity_mod / display_name
```

`capacities()` returns an empty dict for suits with no table entry. Callers must
treat a missing category as "unknown" and render a bare count — never a guess.

### 6.3 `overlay.py` — `PillageOverlay`

```python
class PillageOverlay:
    @property available -> bool          # an overlay module was importable
    def set_enabled(enabled: bool) -> None
    def notify(internal_name: str, text: str) -> None
    def clear() -> None
```

| Constant | Value | Meaning |
|----------|-------|---------|
| `ID_PREFIX` | `edplg-pillage-` | Message IDs; groupable in ModernOverlay |
| `MAX_LINES` | 5 | Stack depth |
| `TTL_SECONDS` | 8 | Per-line lifetime |
| `ORIGIN_X` / `ORIGIN_Y` | 900 / 120 | Legacy 1280×960 virtual screen |
| `LINE_HEIGHT` | 18 | Row spacing |

Behaviour: the client is created lazily on first `notify()`. Lines are held as
`(internal_name, text, expiry)`, newest first; a repeat pickup of the same resource
replaces its line rather than appending. Rows vacated by expiry are blanked by
sending empty text (the legacy clear idiom). Any exception from the overlay client
disables the feature for the session rather than propagating into `journal_entry`.

### 6.4 `window.py` — inventory window

```python
show(parent, tracker: InventoryTracker, suit: SuitState) -> None
refresh() -> None      # no-op when closed
close() -> None
```

Module-level singleton `Toplevel`; `show()` raises the existing window rather than
opening a second. A `ttk.Notebook` holds one `_LocationTab` per store, each with a
`ttk.Progressbar` + total per category and a `ttk.Treeview` of resources.

`SHIP_LOCKER_CAPACITY` is 1000 per category. The carrier locker has no published
microresource cap and shows totals without one.

**Sizing.** Default 900×650, minimum 720×420. Geometry persists to `config` under
`edplg_window_geometry`; `_restore_geometry()` discards a saved size below the
minimum (keeping its position), so an upgrade cannot strand the user with a window
smaller than the current layout needs.

**Styling.** `_configure_styles()` registers `EDPLG.`-prefixed ttk styles so EDMC's
own widgets are untouched. `ttk.Treeview` uses a fixed default row height regardless
of font, which collides under EDMC's theme, so `rowheight` is computed from
`TkDefaultFont`'s `linespace + 8` (minimum 20). Tab padding is widened and the
selected tab is raised and bold; each tab additionally repeats its location as a bold
in-panel heading, so the active location is legible even where the ttk tab strip is
not. Row striping is derived from the resolved Treeview background — lightened when
dark, darkened when light — rather than hardcoded, so it holds up in both themes.

### 6.5 `names.py`

```python
DISPLAY_NAMES: Dict[str, str]   # canonical_id → display label (curated)
_LEARNED_NAMES: Dict[str, str]  # canonical_id → Name_Localised seen this session
canonicalise(name: str) -> str
remember(internal_name, localised_name) -> None
display_name(internal_name, localised_name=None) -> str
```

Resolution order: explicit `localised_name` → `DISPLAY_NAMES` → `_LEARNED_NAMES` →
title-cased fallback. `remember()` ignores unresolved `$Token;` placeholders.

Canonicalisation: `name.lower().replace(" ", "")` — matches EDMC monitor.

### 6.6 `ui.py`

Thread-safe UI updates (called only from `journal_entry` on main thread):

```python
create_plugin_app(parent: tk.Frame, on_show_inventory: Callable[[], None]) -> tk.Frame
create_prefs(parent: nb.Notebook, overlay_available: bool) -> nb.Frame
overlay_enabled() -> bool
save_prefs() -> bool
set_status(message: str) -> None
set_last_event(message: str) -> None
```

Uses `theme.update(frame)` for EDMC dark/light theme consistency. `ui.py` does not
import `load.py`; the Inventory button is wired via the `on_show_inventory` callback
to keep the dependency one-way.

Config keys:

| Key | Type | Purpose |
|-----|------|---------|
| `edplg_overlay_enabled` | bool | Overlay toggle (default on) |
| `edplg_window_geometry` | str | Inventory window position/size |

### 6.7 `load.py` — event dispatch

`journal_entry()` delegates to `_dispatch()` and then calls `window.refresh()` in a
`finally` block, so the window tracks state even if a handler raises.

Pillage message format:

```python
f"[{label}] pillaged! New Inventory Total: {combined_total}"     # log + panel
f"+{delta}  {label}: {combined_total}"                           # overlay
```

`combined_total` = backpack + ship locker + carrier locker count for the resource.

Return value: last pillage message string (displayed in EDMC status area) or `None`.

## 7. Suit Backpack Capacity

The journal reports backpack **contents** but never backpack **capacity**, so the
figures below are game data hardcoded in `suit.py`. In-game wording maps to journal
categories as: **Goods → `Item`**, **Assets → `Component`**, **Data → `Data`**.

Capacity depends on the suit type and on the *Extra Backpack Capacity* engineering
mod (`suit_backpackcapacity` in `SuitMods`). Suit **grade does not affect capacity**.

| Suit | `SuitName` prefix | Goods (Item) | Assets (Component) | Data |
|------|-------------------|--------------|--------------------|------|
| Maverick | `utilitysuit` | 40 → **80** | 60 → **120** | 10 → **40** |
| Artemis | `explorationsuit` | 20 → **40** | 40 → **80** | 10 → **20** |
| Dominator | `tacticalsuit` | 10 → **20** | 20 → **40** | 10 → **20** |
| Flight Suit | `flightsuit` | unknown | unknown | unknown |

*(base → modded)*

Base and modded values are stored explicitly rather than computed with a multiplier,
because the multiplier is not uniform: most categories double, but Maverick Data is
listed as 10 → 40.

A suit with a `None` table entry yields `capacities() == {}`, and the window renders
counts with no limit. This is deliberate — see
[Design Specification §7](./design-spec.md#7-suit-backpack-capacity).

Other capacities:

| Store | Capacity | Source |
|-------|----------|--------|
| Ship locker | 1000 per category | Game-documented cap |
| Carrier locker | Not modelled | No published microresource cap |

Commodity cargo tonnage is a different game system and is deliberately absent from
the plugin.

## 8. Build System

```bash
npm run build
```

`scripts/build.mjs`:

1. Deletes `dist/EDPLG/`.
2. Recursively copies `plugin/` → `dist/EDPLG/`.
3. Skips `__pycache__` and `.pyc` files.

No transpilation or bundling — EDMC loads Python source directly.

### Installation path (Windows)

```
%LOCALAPPDATA%\EDMarketConnector\plugins\EDPLG\
```

Copy the entire `dist/EDPLG` folder. Restart EDMC.

## 9. Versioning

Semantic versioning in:

- `plugin/__init__.py` → `__version__`
- `package.json` → `version` (build metadata only)

EDMC reads `__version__` if present for plugin registry compatibility.

## 10. Testing Checklist

Manual verification steps for releases:

1. Build plugin and copy to EDMC plugins folder.
2. Start EDMC with Odyssey save loaded.
3. Confirm "Inventory synced" in UI after `LoadGame`.
4. Disembark at a settlement; confirm backpack sync on `SuitLoadout`.
5. Loot a container; confirm `[Item] pillaged!` in log and UI.
6. Confirm the overlay line `+1  <Item>: <total>` appears in-game and expires
   after 8 seconds; loot the same item again and confirm the line updates in place
   rather than duplicating.
7. Open the **Inventory** window; confirm the suit heading matches the worn suit,
   the capacity bars match §7, and looting updates the window live.
8. Confirm resources absent from `DISPLAY_NAMES` still show proper names (learned
   from `Name_Localised`) rather than title-cased IDs.
9. Board ship and transfer items; confirm ship locker sync on `ShipLocker`.
10. Disable the overlay in settings; confirm no further overlay lines are drawn.
11. Verify log entries in `%TEMP%\EDMarketConnector.log`.

Non-game verification: `suit.py`, `names.py`, `inventory.py`, `overlay.py`, and
`window.py` can be exercised outside EDMC by stubbing the `config` and `theme`
modules in `sys.modules` and replaying real journal lines through the tracker.

## 11. Dependencies

| Dependency | Required for | Notes |
|------------|--------------|-------|
| EDMC 5.x | Runtime | Provides Python, Tkinter, journal monitor |
| EDMCModernOverlay | Optional | In-game overlay; legacy EDMCOverlay also works. Absent = feature disabled, plugin still loads |
| Node.js 18+ | Build only | `npm run build` |

No pip dependencies. Plugin uses only Python stdlib + EDMC-provided modules.

## 12. References

- [Design Specification](./design-spec.md)
- [Attributions & Credits](./ATTRIBUTIONS.md)
- [EDMC PLUGINS.md](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md)
- [EDCD/FDevIDs microresources.csv](https://github.com/EDCD/FDevIDs)
