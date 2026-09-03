# ED-PLG — Backlog

Open work identified from a feature review against `docs/design-spec.md` §11
("Future Considerations") and the documented known limitations. Not committed
to any version; pick items up as desired.

## Features (design-spec §11)

- [ ] Import full microresource name table from FDevIDs at build time
- [x] Configurable output format or notification sounds. Settings now has a
  **Pillage message** template field (`{item}`/`{total}` placeholders) and a
  **Play a sound on pickup** checkbox (Windows-only, via stdlib `winsound`;
  `plugin/sound.py`, `plugin/ui.py`, `plugin/load.py`). Shipped in 1.1.0
  (unreleased).
- [x] Preferences for filtering tracked categories and overlay position.
  Settings now has an Assets/Goods/Data checkbox row (muting a category's
  pillage notification without stopping tracking) and an overlay position
  X/Y field (`plugin/ui.py`, `plugin/overlay.py`, `plugin/load.py`). Shipped
  in 1.1.0 (unreleased).
- [x] Search / filter box in the inventory window. A single filter box above
  the tabs (`plugin/window.py`) narrows the item listing on all three tabs to
  resources whose display name contains the typed text; category totals and
  capacity bars stay unfiltered. Shipped in 1.1.0 (unreleased).

## Fixable gaps

- [x] Highlight resources that are at or near capacity. The inventory window
  (`plugin/window.py`) now colours each category's progress bar and total
  label amber at the same 90% `WARNING_THRESHOLD` used for ship locker
  overlay warnings, and red once the category is at or over capacity;
  clears back to normal once the count drops back under threshold.

- [x] Flight Suit backpack capacity, and per-suit capacity accuracy in general. Rather than
  keep researching a single hardcoded figure, added a Settings-tab control (`plugin/ui.py`,
  `plugin/suit.py`) letting a commander enter their own observed capacity per owned suit
  loadout (keyed by journal `LoadoutID`), pre-filled with the unengineered default and left
  untouched unless it's wrong for that specific loadout. This also covers *Extra Backpack
  Capacity*'s engineering grade, which the journal never reports and the old hardcoded table
  couldn't represent. Shipped in 0.8.0-beta.1.
- [x] Persist learned display names across sessions instead of relearning every login
  (`plugin/names.py` — `load_learned_names()`/`save_learned_names()`, wired into
  `plugin_start3`/`plugin_stop` in `plugin/load.py`). Shipped in 0.7.2.
- [x] Investigate detecting/mitigating incomplete backpack baseline when logging in already on
  foot. Root cause confirmed: EDMC only populates `state['BackPack']` from a fresh
  `Backpack`/`Resupply` event and clears it on `LoadGame`, so it can't be fixed from inside
  ED-PLG. Mitigated instead: `InventoryTracker.backpack_baseline_seen` tracks whether a real
  baseline has arrived this session, and the panel/inventory window now say "pending first
  sync" rather than presenting a possibly-stale zero as confirmed. Shipped in 0.7.2.

## Accepted limitations (not actionable)

- Fleet carrier CAPI lag (15–30 min, throttled by EDMC)
- Consumable count drift from journal events with no coverage (e.g. grenade throws)
