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

- [ ] Research and fill in Flight Suit backpack capacity (`CAPACITIES` in `plugin/suit.py`)
- [ ] Persist learned display names across sessions instead of relearning every login (`plugin/names.py`)
- [ ] Investigate detecting/mitigating incomplete backpack baseline when logging in already on foot

## Accepted limitations (not actionable)

- Fleet carrier CAPI lag (15–30 min, throttled by EDMC)
- Consumable count drift from journal events with no coverage (e.g. grenade throws)
