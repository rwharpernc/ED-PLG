# Changelog

All notable changes to ED-PLG are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.7.1]: #071---2026-07-13
[0.7.0]: #070---2026-07-13
[0.5.0]: #050---2025-06-30
