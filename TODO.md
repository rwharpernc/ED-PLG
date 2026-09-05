# ED-PLG — Backlog

Open work identified from a feature review against `docs/design-spec.md` §11
("Future Considerations") and the documented known limitations. Not committed
to any version; pick items up as desired.

## Features (design-spec §11)

- [x] Richer overlay visuals within EDMCModernOverlay's capabilities:
  per-category pillage line colours, an optional persistent ship locker
  capacity panel (bars via `send_shape`, off by default), and a best-effort
  ModernOverlay plugin-group registration (background panel + anchor,
  falling back to plain positioned lines wherever it's unavailable)
  (`plugin/overlay.py`, `plugin/ui.py`, `plugin/load.py`). Shipped in 1.2.0
  (landed after 1.1.0 shipped); see follow-ups below.
- [x] Import full microresource name table from FDevIDs at build time. A new
  `npm run update-names` script (`scripts/update-names.mjs`) fetches
  EDCD/FDevIDs' `microresources.csv` and regenerates
  `plugin/names_fdevids.py` (190 names) as a maintenance step separate from
  the ordinary build; `names.py`'s hand-curated table is now a small
  override on top of it. Shipped in 1.1.0.
- [x] Configurable output format or notification sounds. Settings now has a
  **Pillage message** template field (`{item}`/`{total}` placeholders) and a
  **Play a sound on pickup** checkbox (Windows-only, via stdlib `winsound`;
  `plugin/sound.py`, `plugin/ui.py`, `plugin/load.py`). Shipped in 1.1.0.
- [x] Preferences for filtering tracked categories and overlay position.
  Settings now has an Assets/Goods/Data checkbox row (muting a category's
  pillage notification without stopping tracking) and an overlay position
  X/Y field (`plugin/ui.py`, `plugin/overlay.py`, `plugin/load.py`). Shipped
  in 1.1.0.
- [x] Search / filter box in the inventory window. A single filter box above
  the tabs (`plugin/window.py`) narrows the item listing on all three tabs to
  resources whose display name contains the typed text; category totals and
  capacity bars stay unfiltered. Shipped in 1.1.0.

## Known issues (research needed)

- [ ] **Main-panel bar track colour still wrong under EDMC's Dark theme, on
  at least one real install, despite four fix attempts.** Symptom: the
  bar's track (the part behind the coloured outline/fill) renders light
  instead of matching the panel's dark background — see README's Known
  Limitations for the user-facing note. What's been tried, in order, each
  disproven by the next real-environment test:
  1. Branch on `theme.active == theme.THEME_DEFAULT` (mirroring EDMMM) —
     silently always evaluated as "light".
  2. Read a `tk.Frame`'s resolved `background` back — assumed
     `theme.update()` recolours bare Frames; it doesn't (only Label/
     Button/Canvas-shaped widgets are, per EDMC's actual `theme.py`).
  3. Read a `tk.Label`'s resolved `background` back instead — assumed
     EDMC's `theme.update()` had already recoloured that specific widget
     by the time `_bar_track_color()` asked.
  4. Read `theme.current['background']` directly (the dict EDMC's own
     theming populates - correct in principle, confirmed from source) and
     retry redrawing a few times via `root.after()` (0.5s/1.5s/3s/6s)
     in case EDMC's `theme.apply()` hadn't run yet at panel-creation time.
     A diagnostic log line (`_bar_track_color`, still present, bounded to
     ~60 lines per session) confirmed `theme.current` genuinely was empty
     a full second after `plugin_start3` on one real Dark-theme install,
     and the retry mechanism was verified (via a test that reproduces the
     exact failure) to self-correct *that specific* scenario — but the bug
     was still reported after this fix shipped, on a different session.
  - **Next steps for whoever picks this up**: get another
    `Bar track colour diagnostic` log excerpt from the *still-broken*
    session specifically (not just the first line - all of them, to see
    whether `theme.current` ever populates, and whether the retries are
    even firing) — Instructions → open
    `%LOCALAPPDATA%\EDMarketConnector\logs\EDMarketConnector.log`,
    search for `Bar track colour diagnostic`. Also worth checking: does
    the *inventory window's* `ttk.Progressbar` (a completely different
    widget/mechanism, `window.py`) render correctly under the same Dark
    theme, on the same install? If it does, the bug is specific to this
    panel's Canvas approach or its timing; if it doesn't either, the
    problem may be somewhere upstream (EDMC version quirk, a different
    theme variant, a second monitor/DPI scaling interaction, etc.) rather
    than anything in `_bar_track_color()`'s logic at all.
  - Deliberately left in its current (partially-mitigated, not fully
    fixed) state rather than continuing to guess — see commit history on
    `plugin/ui.py`'s `_bar_track_color`/`_redraw_bars_only` for the full
    account of what's been tried.

## Overlay follow-ups (not yet done)

- [ ] Validate the ModernOverlay plugin-group registration (`overlay.py`'s
  `_register_plugin_group`) against a live EDMCModernOverlay install —
  implemented from its developer docs alone, not yet confirmed to actually
  produce a background panel/anchor in-game. If the API shape is wrong,
  either fix the call or drop the feature; it degrades safely either way.
- [x] Backpack capacity bars on the overlay (ship locker only in the
  original pass). Generalised the single ship-locker checkbox into four
  independent per-bar toggles (Backpack/Ship Locker/Carrier
  Locker/Cargo — `overlay.render_bars`, `ui._build_overlay_bars`), computed
  from the exact same rows the main panel's bars use so the two can never
  disagree. Backpack's unknown-per-suit capacity (the original blocker)
  just renders as a bare count with no fill, same as the main panel already
  does for it. An existing install's saved ship-locker preference migrates
  forward as that toggle's own default.

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

Kept in sync with README's Known Limitations section — anything listed there
that isn't tracked as an actionable item elsewhere in this file belongs here
too.

- Fleet carrier CAPI lag (15–30 min, throttled by EDMC)
- Consumable count drift from journal events with no coverage (e.g. grenade throws)
- Backpack capacity is not journal-reported; hardcoded unengineered defaults
  in `suit.py` can't reflect *Extra Backpack Capacity*'s engineering grade or
  the Flight Suit (no known default at all) — mitigated via per-loadout
  Settings overrides (see the Fixable-gaps entry above), not fixable at the
  source.
- Inventory tracking leans on EDMC's best-effort `BackPack` state; ED-PLG
  reconciles against it after every change, which corrects drift but
  inherits any gaps EDMC itself has.
- Rhino SRV cargo capacity is unconfirmed (brand new as of 2026-09-02, no
  documented journal field yet for its actual fitted capacity) — shows a
  count with no `/capacity` until that's confirmed against a real journal
  entry; see design-spec §11.
- SRV type matching (`cargo.py`) is a fuzzy case-insensitive substring
  search against undocumented raw journal values, by design — the safe
  failure mode for an unrecognised SRV is a generic label with unknown
  capacity, never a wrong number.
