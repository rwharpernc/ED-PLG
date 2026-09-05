# ED-PLG Technical Specification

**Version:** 1.1.0  
**Author:** CMDR Bocheaux  
**Last updated:** 2026-09-05

## 1. Overview

ED-PLG is a **package plugin** for Elite Dangerous Market Connector. It implements
the EDMC Python 3 plugin API (`plugin_start3`) and processes journal events
delivered through `journal_entry()`.

| Property | Value |
|----------|-------|
| Plugin folder name | `EDPLG` (must match for EDMC logging) |
| Internal display name | `ED-PLG` (returned from `plugin_start3`) |
| Brand name | `ED Pillage & Payload` — main-panel title only (`ui.PANEL_TITLE`); every technical identifier above stays `ED-PLG`/`EDPLG` |
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
│   ├── cargo.py            # VehicleState + ship/SRV cargo capacity
│   ├── suit.py             # SuitState + backpack capacity table
│   ├── overlay.py          # PillageOverlay (EDMCModernOverlay client)
│   ├── sound.py            # PillageSound (optional pickup beep, winsound)
│   ├── window.py           # Tabbed inventory Toplevel
│   ├── names.py            # ID → display name mapping
│   ├── names_fdevids.py    # Generated: FDevIDs microresource names (do not hand-edit)
│   ├── update.py           # Self-update (GitHub Releases check + stage)
│   └── ui.py               # Tkinter panel + settings tab
├── scripts/build.mjs       # Copies plugin/ → dist/EDPLG/
├── scripts/update-names.mjs # Regenerates names_fdevids.py from FDevIDs (network; not part of build)
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
| `plugin_start3(plugin_dir: str) -> str` | `load.py` | Initialisation; returns `"ED-PLG"`. Also runs `update.check_applied_update()` and kicks off `update.UpdateManager`'s background check - see §14. |
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
from ttkHyperlinkLabel import HyperlinkLabel  # Version/update link (ui.py)
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
| `LoadGame` | Full baseline sync from `state` (backpack + ship locker); set commander; check ship locker capacity warnings. |
| `Start` | Same as `LoadGame` (EDMC started while game running). |
| `Backpack` | Parse journal/JSON baseline; sync backpack from `state`. |
| `Resupply` | Same handler as `Backpack`. |
| `ShipLocker` | Parse locker baseline; sync ship locker from `state`; check ship locker capacity warnings (see §8). |
| `SuitLoadout` | Record suit + mods; sync backpack from `state` (disembark / on-foot start). |
| `SwitchSuitLoadout` | Same handler as `SuitLoadout`. |
| `BackpackChange` | Apply deltas; log pillage, update panel, and send overlay for `Added` items. |
| `CarrierDecommission` | Drop cached carrier locker for the commander. |
| `Embark` | `VehicleState.apply_embark` — `SRV: true` → vehicle becomes `srv`, else `ship` (see §6.1a). |
| `Disembark` | `VehicleState.apply_disembark` — vehicle becomes `foot` regardless of which vehicle was exited. |
| `LaunchSRV` | `VehicleState.apply_launch_srv` — vehicle becomes `srv`; records `SRVType`/`SRVType_Localised` for the cargo bar's label/capacity lookup. |
| `DockSRV` | `VehicleState.apply_dock_srv` — vehicle becomes `ship`; clears the recorded SRV type. |

Every handled event ends by calling `window.refresh()` (no-op unless the
inventory window is open) and `_refresh_panel_bars(state)` (see §6.6),
regardless of which branch above handled it — this keeps every main-panel bar
current after any event, not just the ones that changed a given store.

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
| `Cargo` | `{ commodity: count }` for whichever hold (ship or SRV) is currently active — read by `cargo.py` for the main-panel Cargo bar's current total. Values only; commodity names are never surfaced (see design-spec §2 Out of scope). |
| `CargoCapacity` | Ship's cargo-hold capacity, set by EDMC from `Loadout` events — read by `cargo.py` while the vehicle is `ship`. |

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
    def ship_locker_capacity_warnings() -> List[Tuple[str, int, int]]
    def snapshot() -> Dict[str, InventoryStore]
    @property backpack_baseline_seen -> bool
```

`backpack_baseline_seen` is `True` once a real `Backpack`/`Resupply` event has
been applied this session, and is reset to `False` on `LoadGame`/`Start`
(`sync_all_from_state`), matching when EDMC itself clears `state['BackPack']`.
Callers (`load.py`, `window.py`) use it to distinguish "confirmed empty
backpack" from "no baseline received yet" — see
[Design Specification §11](./design-spec.md#11-known-limitations).

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
    def apply_suit_loadout(entry, cmdr=None) -> None
    def capacities(cmdr=None) -> Dict[str, int]   # {} when unknown; merges overrides for cmdr
    @property known / has_capacity_mod / display_name

def default_capacity(suit_key, has_capacity_mod) -> Dict[str, int]
def known_loadouts_for(cmdr) -> Dict[str, dict]
def record_loadout(cmdr, loadout_id, *, name, suit_key, grade, has_capacity_mod) -> None
def set_override(cmdr, loadout_id, category, value) -> None   # value=None clears
def load_overrides() -> None
def save_overrides() -> None
```

`capacities()` returns an empty dict for suits with no table entry and no
override. Callers must treat a missing category as "unknown" and render a
bare count — never a guess. See "Per-loadout capacity overrides" above for
the override mechanism.

### 6.3 `overlay.py` — `PillageOverlay`

```python
class PillageOverlay:
    @property available -> bool          # an overlay module was importable
    @property is_modern_overlay -> bool  # provider identifies as EDMCModernOverlay (vs. legacy EDMCOverlay)
    def set_enabled(enabled: bool) -> None
    def set_bars_enabled(enabled: bool) -> None
    def set_position(x: int, y: int) -> None   # clamped to MAX_ORIGIN_X/Y
    def set_anchor(anchor: Optional[str]) -> None   # ModernOverlay-only; re-registers the plugin group
    def notify(internal_name: str, text: str, *, colour: str = COLOUR, ttl: int = TTL_SECONDS) -> None
    def render_capacity_bars(values: Mapping[str, Tuple[str, int, int, str]]) -> None
    def clear() -> None
    def clear_capacity_bars() -> None
```

| Constant | Value | Meaning |
|----------|-------|---------|
| `ID_PREFIX` | `edplg-pillage-` | Pillage-line message IDs; groupable in ModernOverlay |
| `CAPACITY_ID_PREFIX` | `edplg-locker-` | Capacity-bar element IDs (`{label,track,fill,value}-{category}`) |
| `MAX_LINES` | 5 | Pillage stack depth |
| `TTL_SECONDS` | 8 | Default per-line lifetime |
| `COLOUR` | `#ffbf00` | Fallback pillage line colour (categories not in `CATEGORY_COLOURS`, and non-category callers like the locker warning) |
| `CATEGORY_COLOURS` | Component `#4fc3f7` / Item `#81c784` / Data `#ba68c8` | Per-category pillage line colour, also reused for that category's capacity-bar row |
| `DEFAULT_ORIGIN_X` / `DEFAULT_ORIGIN_Y` | 900 / 120 | Default overlay origin |
| `MAX_ORIGIN_X` / `MAX_ORIGIN_Y` | 1280 / 960 | Legacy virtual screen bounds; `set_position()` clamps to these |
| `LINE_HEIGHT` | 18 | Pillage row spacing |
| `CAPACITY_BAR_GAP` | 8 | Px between the pillage stack's bottom and the capacity panel |
| `CAPACITY_ROW_HEIGHT` / `CAPACITY_LABEL_WIDTH` / `CAPACITY_BAR_WIDTH` / `CAPACITY_BAR_HEIGHT` / `CAPACITY_VALUE_GAP` | 16 / 60 / 140 / 10 / 8 | Capacity panel layout (px) |
| `CAPACITY_TRACK_COLOUR` | `#555555` | Capacity bar's empty-track outline colour |
| `CAPACITY_TTL` | 3600 | Capacity bar element TTL — long enough to look persistent between `ShipLocker` syncs, not a fade like pillage lines |

**Pillage lines** (unchanged mechanics from before, now with category colour):
the client is created lazily on first `notify()`/`render_capacity_bars()` call.
Lines are held as `(internal_name, text, expiry, colour)`, newest first; a call
with an `internal_name` matching a live line replaces it rather than appending
— pillage calls key on the resource's internal name, other callers (e.g. the
ship locker capacity warning, §8) use their own distinct key so they don't
collide with item pickups. `colour` defaults to `COLOUR`; `load.py` passes
`overlay.CATEGORY_COLOURS.get(category, overlay.COLOUR)` for both pillage
notifications and the locker-capacity warning override. Rows vacated by expiry
are blanked by sending empty text (the legacy clear idiom). The origin
defaults to `(DEFAULT_ORIGIN_X, DEFAULT_ORIGIN_Y)` and is only ever changed via
`set_position()`, which `load.py` calls with `ui.overlay_position()` at startup
and after Settings is saved (see §6.6).

**Capacity bars**: `render_capacity_bars({category: (label, total, capacity,
colour), ...})` draws (or refreshes) a fixed-size panel — one row per
`TRACKED_CATEGORIES` entry present in `values` — below the pillage stack. Each
row is four elements sent via the legacy client: a text label, an outline-only
`send_shape(shape="rect", fill="")` track, a filled `send_shape` bar scaled to
`total/capacity` (or cleared via `send_raw({"id": ...})` — the documented
legacy-clear idiom — when `total` is 0), and a `"total/capacity"` text value.
Row count and element IDs are fixed (`TRACKED_CATEGORIES` never changes at
runtime), so `clear_capacity_bars()` can blank every element deterministically
without needing to track what was last rendered. `load.py`'s
`_refresh_locker_capacity_bars()` is the only caller, invoked on every
`ShipLocker` sync and once per commander session; it always passes all three
categories with ship locker's flat `SHIP_LOCKER_CAPACITY` (never `None`), so
the "unknown capacity" path in `render_capacity_bars` (`capacity` falsy →
`total/capacity` becomes bare `total`, no fill) is reachable but currently
unused — kept general enough that a future backpack-bars caller (which *can*
have an unknown per-suit capacity) can reuse it unchanged.

**Failure isolation**: a pillage-line send failure (`_send_text` with
`feature="pillage"`) drops the client and disables `_enabled` — the original,
conservative behaviour. A capacity-bars send failure (`_send_shape`/`_send_clear`,
or `_send_text` with `feature="bars"`, e.g. a provider without `send_shape`)
only disables `_bars_enabled`, leaving already-working pillage lines on the
same client untouched.

**ModernOverlay plugin-group registration** (`_register_plugin_group`, called
once per successful `_connect()` and again whenever `set_anchor()` changes the
anchor): best-effort only, gated on `is_modern_overlay` (checks
`edmcoverlay.MODERN_OVERLAY_IDENTITY`, exported by ModernOverlay's
`edmcoverlay` shim — absent or a different `plugin` value means legacy
EDMCOverlay, and this is skipped entirely). When gated in, it attempts
`from overlay_plugin.overlay_api import define_plugin_group` — an internal
ModernOverlay module, not the documented-by-example legacy `edmcoverlay`
surface the rest of this file targets — and registers a background panel
(`background_color`/`background_border_color`/`background_border_width`)
anchored (`id_prefix_group_anchor`) to `ui.overlay_anchor()` (default `"ne"`),
covering both `ID_PREFIX` and `CAPACITY_ID_PREFIX`. Any exception (missing
module, changed signature, whatever) is caught and logged at `debug`, leaving
ED-PLG drawing plain positioned elements exactly as it did before this
existed. **This has not been validated against a live ModernOverlay
install** — see `TODO.md`'s Overlay follow-ups.

### 6.3.1 `sound.py` — `PillageSound`

```python
class PillageSound:
    @property available -> bool          # winsound importable (Windows only)
    def set_enabled(enabled: bool) -> None
    def play() -> None
```

Optional, off by default. `play()` calls `winsound.MessageBeep(winsound.MB_ICONASTERISK)`
when enabled and available; `load.py` calls it once per `BackpackChange` that produced
at least one announced pillage message (not once per item), so a multi-item loot pull
beeps once. `winsound` is a Python stdlib module but Windows-only, so `available` is
`False` on other platforms — mirrors `PillageOverlay.available`'s "optional dependency
degrades silently" shape rather than adding a real dependency. Any exception from
`winsound` disables the feature for the session, same as the overlay.

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

**Filter box.** A single `ttk.Entry` above the notebook, bound via
`tk.StringVar.trace_add("write", ...)` to `InventoryWindow.refresh()` — every
keystroke re-runs the normal refresh path rather than patching the tree in place.
`_LocationTab.update()` takes the filter text and applies it only to which rows are
inserted into the `Treeview` (a case-insensitive substring match against
`display_name()`); the per-category totals and capacity bars are computed from the
unfiltered `store` first, so they always reflect the true contents. Filter state is
per-window (not persisted) and applies across all three tabs simultaneously.

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

**Capacity highlighting.** Each category's progress bar and total label recolour
based on `total` vs. `capacity`, reusing `inventory.WARNING_THRESHOLD` (0.9) so the
visual cue lines up with when the ship locker overlay warning (§8) would fire:

| State | Threshold | Bar style | Label colour |
|-------|-----------|-----------|--------------|
| Normal | `< capacity * 0.9` | `EDPLG.Horizontal.TProgressbar` | Theme default (`_default_label_colour()`, looked up fresh each refresh) |
| Near capacity | `>= capacity * 0.9` | `EDPLG.Near.Horizontal.TProgressbar` | `#c07000` (amber) |
| At/over capacity | `>= capacity` | `EDPLG.Full.Horizontal.TProgressbar` | `#c0392b` (red) |

`_LocationTab._set_capacity_level()` applies this on every `update()` call, so a
category clears back to normal as soon as its count drops back under threshold —
there is no separate "rearm" state to track, unlike the overlay warning's
once-per-crossing debounce. A category with unknown capacity (e.g. the carrier
locker) always renders normal.

### 6.5 `names.py`

```python
DISPLAY_NAMES: Dict[str, str]   # canonical_id → display label (curated overrides/additions)
_LEARNED_NAMES: Dict[str, str]  # canonical_id → Name_Localised, persisted across sessions
canonicalise(name: str) -> str
remember(internal_name, localised_name) -> None
display_name(internal_name, localised_name=None) -> str
load_learned_names() -> None    # seed _LEARNED_NAMES from EDMC config (plugin_start3)
save_learned_names() -> None    # persist _LEARNED_NAMES to EDMC config (plugin_stop)
```

Resolution order: explicit `localised_name` → `DISPLAY_NAMES` (curated) →
`FDEVIDS_DISPLAY_NAMES` (generated, from `names_fdevids.py`) → `_LEARNED_NAMES` →
title-cased fallback. `remember()` ignores unresolved `$Token;` placeholders.

`_LEARNED_NAMES` is persisted as JSON under the `edplg_learned_names` config key,
loaded once in `plugin_start3` and saved once in `plugin_stop` — the same
load-once/save-on-close pattern `window.py` uses for geometry, rather than
writing on every `remember()` call.

Canonicalisation: `name.lower().replace(" ", "")` — matches EDMC monitor.

`DISPLAY_NAMES` is now small and deliberately so: it exists only for internal
names ED-PLG has seen (or expects) in-game that `names_fdevids.py` doesn't (yet)
carry under that exact symbol. A key present in both wins from `DISPLAY_NAMES` —
remove an entry once the generated table picks it up.

### 6.5.1 `names_fdevids.py` — generated FDevIDs table

```python
FDEVIDS_DISPLAY_NAMES: Dict[str, str]   # canonical_id → English name, from FDevIDs
```

Generated by `scripts/update-names.mjs` (`npm run update-names`), which fetches
[`EDCD/FDevIDs`'s `microresources.csv`](https://raw.githubusercontent.com/EDCD/FDevIDs/master/microresources.csv),
keeps only rows whose `category` column is `Component`, `Item`, or `Data` (the
`Consumable` rows are out of `TRACKED_CATEGORIES`, see §2), canonicalises each
`symbol` the same way `names.canonicalise()` does, and writes the `symbol → English
name` mapping sorted by key for stable diffs. The file carries a header noting it is
generated and should not be hand-edited.

This is **not** part of `npm run build` — it is a separate, explicit, network-touching
maintenance script a maintainer runs occasionally, after which the regenerated file
is committed like any other source change. The running plugin only ever reads the
committed file; it never fetches anything itself, keeping the "no pip install / no
network at runtime" property intact.

### 6.6 `ui.py`

Thread-safe UI updates (called only from `journal_entry` on main thread):

```python
create_plugin_app(parent: tk.Frame, on_show_inventory: Callable[[], None]) -> tk.Frame
create_prefs(parent: nb.Notebook, overlay_available: bool, sound_available: bool, is_modern_overlay: bool, cmdr: str) -> nb.Frame
overlay_enabled() -> bool
overlay_position() -> Tuple[int, int]           # clamped to MAX_ORIGIN_X/Y
overlay_bars_enabled() -> bool                   # ship locker capacity bars toggle (default off)
overlay_anchor() -> str                          # ModernOverlay panel anchor; defaulted if unset/invalid
sound_enabled() -> bool
message_format() -> str                          # raw template, defaulted if unset
format_pillage_message(item: str, total: int) -> str  # rendered, falls back to default on a bad template
announced_categories() -> FrozenSet[str]         # categories that get a pillage notification
save_prefs(cmdr: str) -> bool
set_status(message: str) -> None
set_last_event(message: str) -> None
set_inventory_levels(rows: List[Tuple[str, str, int, Optional[int]]]) -> None  # (key, label, total, capacity)
run_on_main_thread(callback) -> None
set_update_downloading(version: str) -> None
set_update_downloaded(version: str) -> None
set_update_applied(version: str) -> None
```

`create_plugin_app` builds a header row holding *only* the title (always
visible, click anywhere to toggle collapse) and a content frame (status line,
bars, last-event line, version line) that's `grid_remove()`d entirely while
collapsed — `edplg_panel_collapsed` persists the choice. `PANEL_TITLE` is the
brand name plus its technical abbreviation (`"ED Pillage & Payload
(ED-PLG)"`), matching the title-line convention this developer uses across
their other EDMC plugins - "ED-PLG" itself is unaffected by the brand and
stays the folder name, config key prefix (`edplg_*`), and `plugin_start3`
return value (see §1); only this display string changed.
`_update_header_text()` renders it bare
(`f"{arrow} {PANEL_TITLE}"`, no trailing colon or status) since nothing else
shares that line. The live status label moved from the header into the
content frame's first row (grid row 0, ahead of the bars at row 1) for the
same reason.

Every container above the individual bar canvases — `header`, `_content_frame`,
the `bars` frame, each bar `row` — is `grid()`-ed with `sticky="w"`, never
`"ew"`: a frame stretched wider than its packed/gridded children exposes its
own background in the leftover space, and that background doesn't reliably
follow EDMC's `theme.update()` walk either, which is what produced a stray
white box trailing the title line in practice before this fix.

`set_inventory_levels` updates the four bar rows (`BAR_ORDER = ("backpack",
"ship_locker", "fleet_carrier_locker", "cargo")`) from `load.py`'s
`_refresh_panel_bars`. A key omitted from `rows` — `"fleet_carrier_locker"`
while no fleet carrier is confirmed for this commander, or `"cargo"` while on
foot with no vehicle — has its row hidden via `grid_remove()` rather than
left showing a stale or zeroed value; a later `grid()` (bare, no args)
restores it to its original row index, so hiding and reshowing a row can
never reorder the fixed `BAR_ORDER` sequence the way `pack_forget()`/`pack()`
would (re-appending after whatever else happens to be packed at the time).
Every bar row is bound to `on_show_inventory` — there is no separate button.

Each bar is a plain `tk.Canvas` (`_BAR_WIDTH` x `_BAR_HEIGHT`), redrawn by
`_draw_bar(canvas, total, capacity, colour)` on every update: a background
rectangle in a theme-appropriate track colour fully covers the canvas,
outlined in that bar's own signature `colour`; a fill rectangle on top, sized to
`total/capacity`, uses that same `colour` (or `_BAR_FULL_COLOUR` red at or
over capacity). `colour` comes from `BAR_COLOURS[key]` (`ui.set_inventory_levels`
and `_build_bars`'s initial draw both look it up, falling back to
`_BAR_DEFAULT_COLOUR` for an unrecognised key) — Backpack blue, Ship Locker
green, Carrier Locker violet, Cargo orange, so every bar reads as distinctly
"its own bar" via the outline even at 0%, rather than a flat gray box. This
replaced an earlier `ttk.Progressbar`-based implementation that rendered as
an oversized, unthemed white box in practice — a `ttk` widget's native theme
chrome doesn't reliably follow EDMC's `theme.update()` walk the way plain
`tk` widgets do, whereas a canvas's own explicit background plus
fully-covering rectangles look correct regardless.

`_bar_track_color()` derives the track colour from `_frame`'s own live,
already-`theme.update()`-coloured background - reading it back via
`winfo_rgb()` and shifting it a fixed amount toward black or white depending
on its luminance (same technique `window.py`'s `_stripe_colour()` uses for
its Treeview row shading) - rather than branching on `theme.active ==
theme.THEME_DEFAULT`. An earlier version used that enum comparison directly
(matching EDMMM's own approach) but it silently evaluated as "always light"
in practice, which is what produced light-gray/white bars under EDMC's Dark
theme; reading a widget's own resolved colour back can't be wrong the way
guessing at an internal theme constant can. Because bars are first drawn in
`_build_bars()` before `theme.update(_frame)` has run, `create_plugin_app`
redraws every bar once more immediately after that call, so the very first
paint already reflects the real background rather than the pre-theme
default. Bar/label
widths (`_BAR_NAME_WIDTH`, `_BAR_VALUE_WIDTH`, `_BAR_WIDTH`) are fixed
regardless of label length or count magnitude, per this developer's standing
rule that nothing in a `plugin_app` frame may let variable content widen
EDMC's main window. Bar rows are `grid()`-ed with `sticky="w"` (natural
content width) rather than stretched to fill the panel, so no row ever
exposes a large blank trailing area to whatever background happens to sit
behind it.

Uses `theme.update(frame)` for EDMC dark/light theme consistency. `ui.py` does not
import `load.py`; opening the inventory window from a bar click is wired via the
`on_show_inventory` callback to keep the dependency one-way. `ui.py` does import `update.py` (for
`CONFIG_AUTO_UPDATE`/`RELEASES_PAGE_URL`) and `overlay.py` (for the
`DEFAULT_ORIGIN_*`/`MAX_ORIGIN_*` constants only — it never touches the overlay
client itself), one-way dependencies in the other direction: neither `update.py`
nor `overlay.py` imports `ui.py`. See §14 for the last four functions.

`announced_categories()` reads a JSON list from config; an unset key (empty string)
means "not configured" and returns every `TRACKED_CATEGORIES` entry, while an
explicitly saved `"[]"` means the commander muted all of them — the JSON encoding
is what makes that distinction representable (a comma-joined string would collapse
both cases to `""`). `load.py` calls it per `BackpackChange` and ship-locker-capacity
check; a category not in the returned set is still tracked and counted, only its
notification (log line, overlay, panel) is skipped.

`overlay_anchor()` validates against `overlay.VALID_OVERLAY_ANCHORS`-equivalent
`ui.VALID_OVERLAY_ANCHORS` (the nine ModernOverlay anchors), falling back to
`DEFAULT_OVERLAY_ANCHOR` ("ne") for an unset or unrecognised value; `save_prefs`
applies the same validation before writing, so an invalid Settings-tab entry is
silently ignored (leaving the previously stored value) rather than persisted.
The anchor `Entry` field in Settings is only enabled when `is_modern_overlay` is
true — on legacy EDMCOverlay it's disabled with a hint that positioning is via
X/Y instead (`_build_overlay_bars`).

Config keys:

| Key | Type | Purpose |
|-----|------|---------|
| `edplg_overlay_enabled` | bool | Overlay toggle (default on) |
| `edplg_overlay_x` / `edplg_overlay_y` | int | Overlay origin (default 900 / 120) |
| `edplg_overlay_bars_enabled` | bool | Ship locker capacity bars on the overlay (default **off**) |
| `edplg_overlay_anchor` | str | ModernOverlay panel anchor (default `"ne"`) |
| `edplg_sound_enabled` | bool | Pickup notification sound (default **off**) |
| `edplg_message_format` | str | Pillage message template (default if empty) |
| `edplg_announce_categories` | str (JSON list) | Categories that get a pillage notification (unset = all) |
| `edplg_window_geometry` | str | Inventory window position/size |
| `edplg_auto_update` | bool | Auto-update toggle (default **off** - opt-in) |
| `edplg_last_version` | str | Internal - see §14, `check_applied_update()` |
| `edplg_panel_collapsed` | bool | Main-panel collapsed state (default expanded) |

### 6.7 `load.py` — event dispatch

`journal_entry()` delegates to `_dispatch()` and then calls `window.refresh()` and
`_refresh_panel_bars(state)` in a `finally` block, so the window and main-panel
bars both track state even if a handler raises, and stay current after *any*
event rather than only the ones each function's own branch handles.

`_refresh_panel_bars(state)` builds up to four `(key, label, total, capacity)`
rows described in §6.6 from `_tracker.snapshot()`, `_suit.capacities()`, and
`_vehicle.cargo_bar(state)` (see §6.9), and passes them to
`ui.set_inventory_levels()`. The backpack row's capacity is `None` unless
`_suit.capacities()` has an entry for every `TRACKED_CATEGORIES` member (a
partial suit-capacity table would otherwise understate the true capacity).
The `fleet_carrier_locker` row is included only when
`_tracker.fleet_carrier_callsign` is set - real CAPI locker data has been
seen for this commander - rather than unconditionally at 0; see §6.6's
carrier-gating note for why an unset callsign is a reliable enough "no
carrier" signal. `_on_commander_session()` calls `_vehicle.reset()` before
resyncing, since a fresh journal file replays its own Embark/LaunchSRV
history from scratch and any vehicle state carried over from a previous
session would otherwise be stale.

`journal_entry()` also caches its `state` argument into module-level
`_last_state` before dispatching. `capi_fleetcarrier()` - a separate EDMC
callback invoked asynchronously on its own, with no `state` parameter of its
own - calls `_refresh_panel_bars(_last_state)` after applying (or clearing)
carrier data for the active commander, using that cached value; without this
the Carrier Locker row would only appear (or update) on the *next* journal
event after CAPI data actually arrived, rather than as soon as it does.

Pillage message format:

```python
ui.format_pillage_message(label, combined_total)   # log + panel, configurable template
f"+{delta}  {label}: {combined_total}"              # overlay - fixed, not configurable
```

`combined_total` = backpack + ship locker + carrier locker count for the resource.
The overlay line stays a fixed short form regardless of the configured template, so
it keeps fitting the overlay's stack.

`_handle_backpack_change()` and `_warn_ship_locker_capacity()` both filter their
per-category iteration through `ui.announced_categories()` before logging/notifying
- items in a muted category are still applied to `InventoryTracker` (counts and
`sync_backpack_from_state` are unconditional), only the notification is skipped.
`_sound.play()` fires once per `BackpackChange` that produced at least one announced
pillage message (not once per item). Both `_overlay.notify()` calls (pillage and
locker warning) pass `colour=overlay.CATEGORY_COLOURS.get(category, overlay.COLOUR)`.

`_refresh_locker_capacity_bars()` builds `{category: (label, total, capacity,
colour)}` from the current tracker snapshot and `SHIP_LOCKER_CAPACITY`, and calls
`_overlay.render_capacity_bars()` (a cheap no-op when bars are disabled). Called
from `_on_commander_session()` (so the panel appears as soon as EDMC has ship
locker state, not only after the next transfer), the `ShipLocker` branch of
`_dispatch()`, and `prefs_changed()` (so toggling the bars checkbox on redraws
immediately rather than waiting for the next `ShipLocker` event).

Return value: last pillage message string (displayed in EDMC status area) or `None`.

### 6.8 `update.py` — self-update

See §14 for the full mechanics. Public surface:

```python
current_version() -> str
check_applied_update() -> Optional[str]
UpdateManager(plugin_dir: str, on_ready: Callable[[str], None], on_downloading: Optional[Callable[[str], None]] = None)
UpdateManager.check_async() -> None
CONFIG_AUTO_UPDATE: str   # "edplg_auto_update"
RELEASES_PAGE_URL: str    # imported by ui.py for its Settings-tab link
```

No Tkinter dependency; `check_async()` reads `CONFIG_AUTO_UPDATE` via `config`
directly rather than through `ui.py`, so this module never imports `ui.py`.

### 6.9 `cargo.py` — `VehicleState`

```python
VEHICLE_SHIP = "ship"
VEHICLE_FOOT = "foot"
VEHICLE_SRV = "srv"
SRV_INFO: Dict[str, Tuple[str, Optional[int]]]   # fuzzy-match key -> (display name, capacity or None)

class VehicleState:
    def apply_embark(entry) -> None       # SRV: true/false -> srv/ship
    def apply_disembark(entry) -> None    # always -> foot
    def apply_launch_srv(entry) -> None   # -> srv; records SRVType(_Localised)
    def apply_dock_srv(entry) -> None     # -> ship; clears recorded SRV type
    def reset() -> None                   # back to the LoadGame/Start default (ship)
    def cargo_bar(state) -> Optional[Tuple[str, int, Optional[int]]]  # (label, total, capacity) or None on foot
    @property vehicle -> str
```

No Tkinter dependency; pure state machine, independent of `inventory.py` (a
deliberately separate ledger — see design-spec §2/§12). `cargo_bar`'s `total`
is `sum(state['Cargo'].values())`, the same field for either vehicle, since
`Cargo.json` (and therefore EDMC's `state['Cargo']`) reflects whichever hold is
currently active. `capacity` for `ship` comes from `state['CargoCapacity']`
(only if it's a positive int — a ship not yet reporting a `Loadout` this
session has no key at all); for `srv` it comes from `SRV_INFO`, matched by a
case-insensitive substring search against `SRVType_Localised` (preferred) or
`SRVType` — an unrecognised type returns `("SRV", None)` rather than raising or
guessing. `SRV_INFO` currently has confirmed capacities for `scarab` (4) and
`scorpion` (2); `rhino` has a display name only (`None` capacity) — see
design-spec §11 for why.

`load.py` holds one module-level `_vehicle: VehicleState` instance, hooked to
`Embark`/`Disembark`/`LaunchSRV`/`DockSRV` in `_dispatch()` and reset in
`_on_commander_session()` (see §6.7).

## 7. Suit Backpack Capacity

The journal reports backpack **contents** but never backpack **capacity**, so the
figures below are game data hardcoded in `suit.py`. In-game wording maps to journal
categories as: **Goods → `Item`**, **Assets → `Component`**, **Data → `Data`**.

Capacity depends on the suit type and on the *Extra Backpack Capacity* engineering
mod (`suit_backpackcapacity` in `SuitMods`). Suit **grade does not affect capacity**.

| Suit | `SuitName` prefix | Goods (Item) | Assets (Component) | Data |
|------|-------------------|--------------|--------------------|------|
| Maverick | `utilitysuit` | 40 → **80** | 60 → **120** | 20 → **40** |
| Artemis | `explorationsuit` | 20 → **40** | 40 → **80** | 10 → **20** |
| Dominator | `tacticalsuit` | 10 → **20** | 20 → **40** | 10 → **20** |
| Flight Suit | `flightsuit` | unknown | unknown | unknown |

*(base → modded)*

Base and modded values are stored explicitly rather than computed with a multiplier.
Every category currently happens to double when *Extra Backpack Capacity* is fitted,
but that's an observation, not a guarantee the plugin relies on — a future suit (or a
Frontier rebalance) isn't assumed to follow the same ratio.

A suit with a `None` table entry yields `capacities() == {}`, and the window renders
counts with no limit. This is deliberate — see
[Design Specification §7](./design-spec.md#7-suit-backpack-capacity).

### Per-loadout capacity overrides

The table above can't capture *Extra Backpack Capacity*'s engineering grade
(only presence/absence), and has no entry for the Flight Suit. Commanders can
correct individual categories from the Settings tab, per owned suit loadout:

- Persisted as JSON under EDMC config key `edplg_suit_overrides`, shaped as
  `{cmdr: {loadout_id: record}}`, where `loadout_id` is the journal's
  `LoadoutID` (stringified) and `record` is:

  ```python
  {
      "name": str,               # LoadoutName, e.g. "Exo 3 NVG"
      "suit_key": str,           # "explorationsuit", etc.
      "grade": Optional[int],
      "has_capacity_mod": bool,
      "overrides": Dict[str, int],  # category -> commander-entered capacity
  }
  ```

- `suit.record_loadout()` upserts the identity fields (`name`/`suit_key`/
  `grade`/`has_capacity_mod`) every time a `SuitLoadout`/`SwitchSuitLoadout`
  event is processed, preserving any existing `overrides` — this is what
  populates the Settings tab's list without a manual "add suit" step.
- `SuitState.capacities(cmdr)` merges: hardcoded table default, then any
  per-category override for the current loadout on top
  (`{**default, **overrides}`). A category absent from `overrides` keeps
  falling back to the table (or stays unknown, e.g. an un-overridden Flight
  Suit category).
- `suit.load_overrides()` / `suit.save_overrides()` mirror the load/save
  pattern already used for learned resource names in `names.py`.

Other capacities:

| Store | Capacity | Source |
|-------|----------|--------|
| Ship locker | 1000 per category | Game-documented cap |
| Carrier locker | Not modelled | No published microresource cap |

Commodity cargo tonnage is a different game system and is deliberately absent from
the plugin.

## 8. Ship Locker Capacity Warning

`InventoryTracker.ship_locker_capacity_warnings()` compares each tracked
category's ship locker total against `SHIP_LOCKER_CAPACITY[category] *
WARNING_THRESHOLD` (0.9, i.e. 900/1000):

- Crossing at/over threshold, not already warned this "episode" → yields
  `(category, total, capacity)` and marks the category warned.
- Dropping back under threshold → clears the warned mark, rearming a future
  crossing (e.g. after offloading via a ship or an Apex shuttle).
- Already warned and still over threshold → yields nothing (no repeat spam).

Called from `load.py` after every ship locker sync — the `ShipLocker` event
branch and `_on_commander_session` (covers `LoadGame`/`Start`) — via a
`_warn_ship_locker_capacity()` helper that logs each warning
(`logger.warning`) and sends it to the overlay:

```python
_overlay.notify(
    f"__locker_full_{category}",
    f"⚠ Ship Locker {label}: {total}/{capacity} — nearing capacity",
    colour=LOCKER_WARNING_COLOUR,  # "#ff3030", distinct from pillage amber
    ttl=LOCKER_WARNING_TTL,        # 20s, longer than a pillage line's 8s
)
```

An Apex shuttle's "Manage Items" screen is a remote proxy into the same ship
locker a commander's own ship uses — not a separate storage pool — so it
updates through the same `ShipLocker` journal event this already hooks; no
Apex-specific handling exists or is needed.

## 9. Build System

```bash
npm run build         # scripts/build.mjs
npm run package       # scripts/build.mjs, then scripts/package.mjs
npm run update-names  # scripts/update-names.mjs (maintenance only, see below)
```

`scripts/build.mjs`:

1. Deletes `dist/EDPLG/`.
2. Recursively copies `plugin/` → `dist/EDPLG/`.
3. Skips `__pycache__` and `.pyc` files.

`scripts/package.mjs` (requires a prior build) reads `__version__` from
`plugin/__init__.py` and zips `dist/EDPLG/` to `dist/EDPLG-v<version>.zip` via
`Compress-Archive`, zipping the `EDPLG` folder itself (not just its contents) so
extracting the archive drops a ready-to-copy `EDPLG/` folder straight into the EDMC
plugins directory. This is the artefact attached to GitHub releases.

No transpilation or bundling — EDMC loads Python source directly.

`scripts/update-names.mjs` is a separate maintenance step, deliberately **not**
run as part of `build`/`package`: it fetches FDevIDs' `microresources.csv` (the
only network access anywhere in this repo's tooling) and regenerates
`plugin/names_fdevids.py` (see §6.5.1). `build`/`package` stay offline and
reproducible; a maintainer runs `update-names` occasionally and commits the
regenerated file like any other change.

### Installation path (Windows)

```
%LOCALAPPDATA%\EDMarketConnector\plugins\EDPLG\
```

Copy the entire `dist/EDPLG` folder. Restart EDMC.

## 10. Versioning

Semantic versioning in:

- `plugin/__init__.py` → `__version__`
- `package.json` → `version` (build metadata only)

EDMC reads `__version__` if present for plugin registry compatibility.

## 11. Testing Checklist

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
   the capacity bars match §7, and looting updates the window live. Fill a
   category to 90%+ of capacity and confirm its bar/total turn amber, then to
   100%+ and confirm red; drop back under 90% and confirm it clears to normal.
8. Confirm resources absent from `DISPLAY_NAMES` still show proper names (learned
   from `Name_Localised`) rather than title-cased IDs.
9. Board ship and transfer items; confirm ship locker sync on `ShipLocker`.
10. Fill a ship locker category to 900+/1000 (or lower `WARNING_THRESHOLD`
    temporarily for testing); confirm one red overlay warning appears and it
    does not repeat on further syncs while still over threshold. Offload
    below 900, then refill past it; confirm it warns again.
11. Disable the overlay in settings; confirm no further overlay lines are drawn.
12. Verify log entries in `%TEMP%\EDMarketConnector.log`.
13. In the Inventory window, type into the **Filter** box; confirm only matching
    rows remain on all three tabs while totals/bars stay unchanged, and **Clear**
    restores the full list.
14. In Settings, change the **Pillage message** template (e.g. add `{total}` twice
    or an unknown placeholder); confirm valid templates apply and an invalid one
    falls back to the default rather than erroring. Enable **Play a sound on
    pickup** and confirm a beep plays on the next pickup (Windows only).
15. In Settings, uncheck one category under **Announce pickups for**; loot that
    category and confirm no log/overlay/panel notification appears, but the
    Inventory window and combined totals still reflect the pickup. Re-check it.
16. Set a custom **Overlay position** X/Y in Settings; confirm the overlay stack
    redraws at the new origin on the next pickup.
17. Loot one resource from each category (Assets/Goods/Data); confirm each
    pillage line draws in its own colour (`overlay.CATEGORY_COLOURS`) rather
    than one flat colour.
18. Enable **Show ship locker capacity bars on the overlay**; confirm a
    three-row panel (Assets/Goods/Data — label, bar, total/1000) appears below
    the pillage stack and updates on the next `ShipLocker` sync. Disable the
    checkbox and confirm the panel is actually removed, not just stops
    updating.
19. With EDMCModernOverlay specifically installed (not legacy EDMCOverlay),
    set an **Overlay panel anchor** and confirm (this is the unvalidated
    part — see `TODO.md`) whether ED-PLG's elements actually get a
    background panel anchored there via ModernOverlay's controller, or
    whether the attempt silently no-ops. Record the result either way.
20. Click the main panel's title; confirm it collapses to just the header
    line (bars, last-event, and version lines all hidden), the arrow flips
    to `▸`, and the choice survives an EDMC restart. Click again to expand
    and confirm the arrow flips back to `▾`.
21. With EDMC's Odyssey save docked in a ship, confirm the panel shows a
    "Ship Cargo" bar matching the ship's actual hold (`used/capacity`).
    Launch an SRV (Scarab or Scorpion) and confirm the bar relabels to
    `"<Type> Cargo"` with that vehicle's known capacity; get out on foot and
    confirm the bar disappears entirely (not just zeroed); get back in and
    confirm it reappears correctly labelled.
22. Fill the Backpack, Ship Locker, or Cargo bar to capacity and confirm it
    turns red on the main panel; confirm clicking any bar (not just the old
    button's former location) opens the inventory window.

Non-game verification: `suit.py`, `cargo.py`, `names.py`, `names_fdevids.py`,
`inventory.py`, `overlay.py`, `sound.py`, and `window.py` can be exercised
outside EDMC by stubbing the `config` and `theme` modules in `sys.modules` and
replaying real journal lines through the tracker.

## 12. Dependencies

| Dependency | Required for | Notes |
|------------|--------------|-------|
| EDMC 5.x | Runtime | Provides Python, Tkinter, journal monitor |
| EDMCModernOverlay | Optional | In-game overlay; legacy EDMCOverlay also works. Absent = feature disabled, plugin still loads |
| `overlay_plugin.overlay_api` (ModernOverlay-internal) | Optional, best-effort | Plugin-group registration (§6.3) only; not the documented legacy `edmcoverlay` surface, unvalidated live, any failure degrades to plain positioned elements |
| `winsound` (stdlib) | Optional | Pickup notification sound; Windows-only, so unavailable elsewhere. Absent = checkbox disabled, plugin still loads |
| Node.js 18+ | Build only | `npm run build`, `npm run package`, `npm run update-names` |
| GitHub Releases API | Optional (auto-update, off by default) | `update.py`'s only *runtime* network call - see §14 |
| EDCD/FDevIDs `microresources.csv` | Maintenance only | `scripts/update-names.mjs`'s only network call - see §6.5.1. Not fetched at build or runtime |

No pip dependencies. Plugin uses only Python stdlib + EDMC-provided modules,
even with auto-update enabled (`update.py` uses `urllib`/`zipfile`, not a pip
package). No npm dependencies either — `scripts/*.mjs` use only Node's stdlib
(`fs`, `https`, `path`, `child_process`).

## 13. References

- [Design Specification](./design-spec.md)
- [Attributions & Credits](./ATTRIBUTIONS.md)
- [EDMC PLUGINS.md](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md)
- [EDCD/FDevIDs microresources.csv](https://github.com/EDCD/FDevIDs)

## 14. Self-Update (`update.py`)

`UpdateManager.check_async()` is called once, from `plugin_start3`. It's a
no-op if either the `edplg_auto_update` config setting (**opt-in, default
off**, toggled from the Settings tab) is off, or a `disable-auto-update.txt`
file exists directly in `plugin_dir` — a hardcoded escape hatch for a folder
being actively hand-edited (e.g. local development), independent of and not
visible in Settings.

Otherwise it spawns a daemon thread that:

1. **GETs** `https://api.github.com/repos/rwharpernc/ED-PLG/releases/latest`
   (skips draft/prerelease responses) and compares its `tag_name` against
   `plugin.__version__`, both parsed as plain `(major, minor, patch)` integer
   tuples. A newer *or equal* remote version is a no-op.
2. If newer, calls `on_downloading(version)`, then **downloads** the first
   `.zip` release asset to `plugin_dir/updates/`.
3. **Backs up** the current plugin folder to a timestamped zip in
   `plugin_dir/backups/` (walking `plugin_dir`, excluding `updates/`,
   `backups/`, and `__pycache__/`), then trims backups down to the 3 most
   recent.
4. **Extracts** the downloaded zip over `plugin_dir`, stripping the top-level
   `EDPLG/` folder the release zip is packaged with (see
   `scripts/package.mjs`) — so files land directly in `plugin_dir`.
5. Calls `on_ready(version)` (the callback passed to `UpdateManager.__init__`).

Both `on_downloading` and `on_ready` are plain callbacks handed to
`UpdateManager.__init__`; `load.py` wraps each in a lambda that calls
`ui.run_on_main_thread(...)`, which marshals onto the Tk main thread via
`frame.after(0, ...)` before touching any widget, since `update.py` itself
has no Tkinter dependency and runs entirely off the main thread up to this
point.

Nothing here reloads running code — Python already has the old modules
loaded in memory for this process. The staged files only take effect the
*next* time EDMC starts.

### 14.1 Update status UI

**The plugin version lives only in the Settings tab.** `create_prefs` builds
a static `ttkHyperlinkLabel.HyperlinkLabel` (`ED-PLG v{__version__}`, linking
to `update.RELEASES_PAGE_URL`) once, at creation, and nothing ever touches it
again — no color, no text changes, regardless of update state.

The main panel keeps one `ui._version_label` (created empty and
`grid_remove()`d immediately, on its own row below the status/last-event
rows) purely for a one-time "Updated to vX.Y.Z" confirmation. It's driven by
a module-level `ui._version_state` tuple (`kind`, `version`), applied by
`ui._apply_version_state()`:

| Kind | Main-panel label | Set by |
|------|-------------------|--------|
| `normal` | hidden (`grid_remove()`) | default / after the "updated" message clears |
| `downloading` | hidden - tracked, not shown | `ui.set_update_downloading`, from `UpdateManager`'s `on_downloading` |
| `downloaded` | hidden - tracked, not shown | `ui.set_update_downloaded`, from `on_ready` |
| `updated` | `Updated to vX.Y.Z`, green `#2e7d32`, `grid()`ed back in | `ui.set_update_applied`, from `plugin_start3` |

`downloading`/`downloaded` still update `_version_state` (so `update.py`'s
own `logger.info` calls remain the only record of them) but
`_apply_version_state()` deliberately renders nothing for either — a design
choice to keep the main panel visually quiet, not an oversight.

`update.check_applied_update()` detects the `updated` case: it reads the
`edplg_last_version` config value written on the *previous* run, compares it
to `plugin.__version__`, and rewrites it to the current version every run. A
mismatch (and a non-empty previous value, so this doesn't fire on a
first-ever install) means a staged update just took effect on this restart,
and `plugin_start3` calls `ui.set_update_applied(version)` immediately —
before `plugin_app` has created any widget, since `_apply_version_state()`
is a no-op until `_version_label` exists, and `create_plugin_app` calls it
again at the end of widget construction to pick up whatever state is
already current.

The `updated` state doesn't stay up indefinitely: `_apply_version_state()`
schedules `_clear_updated_state()` via
`_version_label.after(_UPDATED_MESSAGE_DURATION_MS, ...)` (15s) the first
time it applies an `updated` kind, guarded by `_updated_clear_scheduled` so
a second call doesn't schedule a duplicate timer. When it fires, it reverts
`_version_state` to `("normal", None)` and re-applies, which
`grid_remove()`s the label.
