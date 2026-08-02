# ED-PLG — Backlog

Open work identified from a feature review against `docs/design-spec.md` §11
("Future Considerations") and the documented known limitations. Not committed
to any version; pick items up as desired.

## Features (design-spec §11)

- [ ] Configurable output format or notification sounds
- [ ] Search / filter box in the inventory window
- [ ] Highlight resources that are at or near capacity
- [ ] Import full microresource name table from FDevIDs at build time
- [ ] Preferences for filtering tracked categories and overlay position

## Fixable gaps

- [BLOCKED] Research and fill in Flight Suit backpack capacity (`CAPACITIES` in `plugin/suit.py`).
  Web research was inconclusive: the Fandom wiki (the likely authoritative source) blocked
  automated fetches, and the only numbers surfaced via search were AI-summarized figures for
  the *Maverick* suit that contradict this plugin's own already-verified Maverick table —
  meaning they aren't trustworthy either. Per the plugin's "never guess" rule (design-spec §7),
  no value was hardcoded. Needs a real in-game observation (grade doesn't matter) from someone
  who owns an unmodified Flight Suit — Extra Backpack Capacity is moot since the Flight Suit
  cannot be engineered.
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
