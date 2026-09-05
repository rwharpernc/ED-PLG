# Changelog

All notable changes to ED-PLG are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Collapsible main panel with at-a-glance inventory bars.** The panel
  title is now a click-to-collapse header (arrow + `ED-PLG:` + live status),
  collapsing down to that one line and remembering the choice across
  restarts. Expanded, it shows a bar each for Backpack, Ship Locker, and
  Carrier Locker, plus a fourth Cargo bar (see below) — clicking any bar
  opens the inventory window, replacing the old **Inventory** button.
- **Ship & SRV cargo-hold tracking (scope extension).** A new `cargo.py`
  module tracks which vehicle (ship, on foot, or SRV) the commander
  currently occupies from `Embark`/`Disembark`/`LaunchSRV`/`DockSRV` journal
  events, and reports that vehicle's cargo tonnage on the main panel's
  fourth bar: the ship's hold while in a ship, the SRV's hold (Scarab 4t,
  Scorpion 2t; Rhino shows a count but no capacity yet — see Known
  Limitations) while in one, and hidden entirely on foot with no vehicle.
  This is tonnage only — commodity identity, prices, and market data remain
  out of scope; see README's Scope section and design-spec §2/§12.

### Changed

- README/design-spec/tech-spec's "out of scope" wording narrowed from
  "commodity cargo" to "commodity identity, prices, and market data", to
  make room for the tonnage-only tracking above without re-opening the door
  to commodity trading features.

- **Richer overlay visuals, within EDMCModernOverlay's capabilities.**
  - Pillage lines are now coloured per category (blue Assets, green Goods,
    violet Data) instead of one flat colour, so a fast loot run is
    scannable at a glance (`overlay.CATEGORY_COLOURS`).
  - **Ship locker capacity bars** — an optional persistent panel below the
    pillage stack (one row per category: label, bar, `total/1000`),
    refreshed on every `ShipLocker` sync. Off by default; toggle in
    Settings. Backpack capacity bars were left out of this pass (ship
    locker's capacity is always known; backpack's isn't for every suit).
  - **ModernOverlay panel group (experimental).** When the connected
    provider identifies as EDMCModernOverlay specifically, ED-PLG makes a
    best-effort attempt to register its own background panel, anchored to
    a screen corner/edge (new **Overlay panel anchor** setting) instead of
    relying only on raw X/Y. This uses an internal ModernOverlay API
    outside the documented legacy `edmcoverlay` surface and has not been
    validated against a live install — any failure degrades silently to
    today's plain positioned elements. See `TODO.md`'s Overlay follow-ups.

## [1.1.0] - 2026-09-03

### Added

- **Comprehensive resource names, imported from FDevIDs.** A new
  `npm run update-names` maintenance script (`scripts/update-names.mjs`)
  fetches EDCD/FDevIDs' `microresources.csv` and regenerates
  `plugin/names_fdevids.py` (190 Component/Item/Data names, up from the
  ~50-entry hand-curated table) — not part of the ordinary build, so the
  plugin itself still never touches the network for it. `names.py`'s
  hand-curated `DISPLAY_NAMES` is trimmed to only the entries FDevIDs
  doesn't (yet) cover and now takes priority as an override rather than
  being the primary table.
- **Configurable pillage message and a pickup notification sound.** Settings
  now has a **Pillage message** template field (`{item}`/`{total}`
  placeholders, falling back to the default on a blank or invalid template)
  and a **Play a sound on pickup** checkbox (off by default; Windows-only via
  the standard library's `winsound`, greyed out elsewhere) (`ui.py`,
  `sound.py` (new), `load.py`).
- **Preferences for muting per-category notifications and overlay position.**
  Settings now has a checkbox per tracked category (Assets/Goods/Data)
  controlling whether that category's pickups get a pillage notification
  (log line, overlay line, panel status) — tracking and totals are
  unaffected either way — plus an overlay position X/Y field (default 900,
  120) as an alternative to repositioning via ModernOverlay's controller
  (`ui.py`, `overlay.py`, `load.py`).
- **Filter box in the inventory window.** A single box above the tabs
  narrows the item listing on all three tabs (Backpack/Ship Locker/Carrier
  Locker) to resources whose display name contains the typed text
  (case-insensitive); category totals and capacity bars stay unfiltered
  (`window.py`).
- **Auto-update, off by default (opt-in, not opt-out).** Once enabled in
  Settings, ED-PLG checks GitHub Releases once per EDMC start and, if a
  newer one exists, downloads and stages it over the current install
  (`update.py`), taking effect on EDMC's next restart. The plugin version
  now lives only in the Settings tab (a static link to the Releases
  page); the main panel stays silent about it except for a brief
  "Updated to vX.Y.Z" right after a staged update takes effect. A
  `disable-auto-update.txt` file in the plugin folder overrides the
  Settings checkbox unconditionally, for a hand-edited local copy. Uses
  stdlib `urllib`/`zipfile` only, not a pip package, keeping "no pip
  dependencies" true. Modeled on the same mechanism in EDPPMT/EDMMM,
  aligned to the same opt-in-off-by-default, Settings-only-version
  direction across all three.

## [1.0.0] - 2026-08-24

### Changed

- **First stable release.** No functional changes from 0.8.0-beta.3 — the
  beta cycle (per-loadout capacity overrides, ship locker capacity
  warnings, capacity highlighting) is considered validated, so the plugin
  drops its beta designation.

## [0.8.0-beta.3] - 2026-08-24

### Added

- **Capacity highlighting in the inventory window.** Each category's
  progress bar and total (Assets, Goods, Data — across all three tabs)
  now turns amber at the same 90% threshold that triggers the ship locker
  overlay warning, and red once the category is at or over capacity,
  clearing back to normal as the count drops back under threshold.

## [0.8.0-beta.2] - 2026-08-03

### Added

- **Ship locker capacity warning.** Filling a ship locker category (1000
  cap) while out looting can force dropping items rather than storing
  them — whether offloading at your own ship or remotely via an Apex
  shuttle's "Manage Items" screen (confirmed to be a proxy into the same
  locker, not separate storage, so no special-casing was needed for it).
  ED-PLG now sends a distinct, longer-lived red overlay warning — and
  logs it regardless of overlay availability — when a category (Assets,
  Goods, or Data) crosses 90% of capacity. It won't repeat while still
  over threshold, but rearms after dropping back under 90% so a later
  refill warns again.

## [0.8.0-beta.1] - 2026-08-03

### Added

- **Per-loadout backpack capacity overrides.** The hardcoded capacity table
  could only say whether *Extra Backpack Capacity* was fitted, not its
  engineering grade, and had no entry at all for the Flight Suit. **File →
  Settings → ED-PLG** now lists every suit loadout you've been seen wearing
  (auto-discovered from `SuitLoadout`/`SwitchSuitLoadout` events, keyed by
  the journal's `LoadoutID`), with an editable capacity field per category
  pre-filled with the unengineered default. Leave a field alone if it's
  right; update it if that specific loadout is engineered or otherwise
  holds a different amount. Saving a value that matches the default doesn't
  persist as an override, so future corrections to the built-in table still
  apply automatically.

### Fixed

- **Maverick Suit base Data capacity corrected from 10 to 20** (modded stays
  40). The previous figure predated this pass and didn't match verified
  in-game observation.

## [0.7.2] - 2026-08-02

### Added

- **Learned display names persist across sessions.** Names learned from
  `Name_Localised` (for resources not in the curated `DISPLAY_NAMES` table) are
  now saved to EDMC's config on shutdown and restored on the next launch,
  instead of being rebuilt from scratch every session.
- **"Backpack pending first sync" indicator.** EDMC only populates backpack
  state from a fresh `Backpack`/`Resupply` journal event, so a commander who
  logs in already on foot can see a zeroed-out backpack that isn't actually
  empty. ED-PLG now tracks whether a real baseline has been received this
  session and says so — in the panel status line and as a note on the
  Backpack tab of the inventory window — rather than presenting that zero as
  confirmed.

### Notes

- Flight Suit backpack capacity remains unknown. Reliable, verifiable figures
  could not be sourced during this pass; see `TODO.md`. The plugin continues
  to show a bare count with no capacity bar for it rather than guess.

## [0.7.1] - 2026-07-13

### Fixed

- **Inventory window rows collided.** `ttk.Treeview` keeps a fixed default row
  height regardless of the theme's font, so under EDMC's theme the text ran
  together. Row height is now derived from the font's line spacing
  (`linespace + 8`), so it scales with whatever font the theme applies.
- **Window too narrow.** Default size raised from 560×580 to 900×650, with a
  720×420 minimum. A geometry saved from an earlier version below the new minimum
  is grown to the default while keeping its on-screen position.

### Changed

- Tabs are easier to tell apart: wider padding, upper-case labels, and the
  selected tab is raised and bold. Each tab also repeats its location as a bold
  heading inside the panel (e.g. *"Ship Locker — stored aboard your ship"*), which
  stays readable regardless of how the platform renders the tab strip.
- Resource list is wider and easier to scan: alternating row shading (derived from
  the theme background, so it works in both dark and light), a wider stretching
  Resource column, and short category labels (Assets / Goods / Data).

## [0.7.0] - 2026-07-13

### Added

- **In-game overlay notifications.** Pillage pickups are drawn on the game
  overlay through [EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay)
  (or the legacy EDMCOverlay), showing the item and its new combined total:
  `+1  Manufacturing Instructions: 13`. Up to five recent lines are stacked,
  newest first; re-looting an item updates its existing line rather than adding
  a duplicate. Degrades to a no-op when no overlay plugin is installed.
- **Inventory window.** An `Inventory` button on the EDMC panel opens a tabbed
  window (Backpack / Ship Locker / Carrier Locker) listing every tracked
  resource with per-category totals and capacity bars, so you can decide whether
  a pickup is worth the backpack slot.
- **Suit tracking** (`suit.py`). `SuitLoadout` and `SwitchSuitLoadout` are read
  for `SuitName` and `SuitMods` to determine backpack capacity, including the
  doubling from the `suit_backpackcapacity` ("Extra Backpack Capacity") mod.
- **Settings tab** (`plugin_prefs` / `prefs_changed`) with a toggle for overlay
  notifications.
- **Learned display names.** `Name_Localised` from `Backpack`, `ShipLocker`,
  `BackpackChange`, and CAPI carrier data is cached at runtime, so resources
  absent from the `DISPLAY_NAMES` table still render with their proper in-game
  names instead of a title-cased internal ID.

### Notes

- Backpack capacity is **not** published in the journal. It is hardcoded per
  suit type in `suit.py`; the Flight Suit is unknown and shows counts without a
  capacity. See [Technical Specification §7](docs/tech-spec.md#7-suit-backpack-capacity).
- Fleet carrier locker support (CAPI `capi_fleetcarrier`, per-commander caching,
  `CarrierDecommission`) shipped in 0.6.x without a changelog entry; it is
  documented in the design and technical specifications as of this release.

## [0.5.0] - 2025-06-30

### Added

- Initial release of **ED-PLG** (Elite Dangerous Pillage Ledger & Gear-tracker).
- Real-time tracking of Odyssey on-foot microresources: Components, Items, and Data.
- Suit backpack and ship locker inventory baselines via journal events.
- Live `BackpackChange` interception with pillage logging:
  `[ITEM_NAME] pillaged! New Inventory Total: X`
- Tkinter UI panel integrated into the EDMC main window.
- Human-readable name mapping for Frontier internal microresource IDs.
- Build pipeline (`npm run build`) outputting a copy-ready `dist/EDPLG/` folder.
- Project documentation: README, technical specification, design specification,
  attributions, and MIT license.

### Notes

- Ship engineering materials (`Materials` event: Raw, Manufactured, Encoded) are
  intentionally excluded; this plugin focuses on Odyssey ground gear upgrades only.

[0.7.2]: #072---2026-08-02
[0.7.1]: #071---2026-07-13
[0.7.0]: #070---2026-07-13
[0.5.0]: #050---2025-06-30
