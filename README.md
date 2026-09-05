# ED-PLG

**ED Pillage & Payload**

A lightweight [Elite Dangerous Market Connector](https://github.com/EDCD/EDMarketConnector) (EDMC) plugin for *Elite Dangerous: Odyssey*. ED-PLG tracks on-foot microresources — the components, items, and data you spend on suit and weapon upgrades — and tells you what you just looted, how much of it you now own, and whether you still have room to carry it. It also tracks your ship/SRV cargo hold ("payload"), so one panel covers everything you're carrying, on foot or in a vehicle.

**Author:** CMDR Bocheaux  
**Version:** 1.1.0  
**License:** [MIT](LICENSE)

---

## What it does

When you loot a container on foot, ED-PLG announces it — in the EDMC panel, in the log, and (optionally) on an in-game overlay:

```
[Manufacturing Instructions] pillaged! New Inventory Total: 12
```

That total is the number that matters when you are deciding whether a pickup is worth a backpack slot, and it is *not* just what is in your backpack — see [How it works](#how-it-works) below. The message's wording is configurable (see [Notification settings](#notification-settings) below).

- **Live inventory tracking** across your suit backpack, ship locker, and fleet carrier locker
- **Pillage notifications** on every pickup, with your new combined total — wording, a pickup sound, and which categories announce at all are all configurable
- **Collapsible main panel** — click the title to collapse the ED-PLG panel down to a single status line, or expand it back out; EDMC remembers your choice
- **At-a-glance capacity bars** on the main panel for Backpack, Ship Locker, and Carrier Locker, plus a fourth bar that tracks your current vehicle's cargo hold (ship, or SRV when deployed) — click any bar to open the full inventory window
- **In-game overlay alerts** via [EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) (optional — the plugin works fine without it)
- **Inventory window** — a tabbed view of everything you hold, with capacity bars per category, so you can see at a glance how close your backpack is to full
- **Ship locker capacity warning** — an in-game overlay alert when a ship locker category hits 90% full, so you're not caught having to drop loot before you can offload it (at your ship, or remotely via an Apex shuttle)
- **Real names** for Frontier's internal resource IDs (`manufacturinginstructions` → *Manufacturing Instructions*), covering essentially every Odyssey microresource via a table imported from [EDCD/FDevIDs](https://github.com/EDCD/FDevIDs)

**Deliberately out of scope:** ship engineering materials (Raw, Manufactured, Encoded) and commodity *trading* (names, prices, market data). ED-PLG's core is still Odyssey microresources — the stuff that upgrades your ground gear — but as of this release it also tracks ship/SRV **cargo tonnage** (used vs. capacity only, nothing about what's in the hold) since that matters for salvage and mining runs; see [Ship & SRV cargo](#ship--srv-cargo) below.

## Requirements

- [Elite Dangerous Market Connector](https://github.com/EDCD/EDMarketConnector/releases) 5.x
- *Elite Dangerous: Odyssey*

That is all. ED-PLG is pure Python and uses only the standard library plus what EDMC provides — **no `pip install`, and no separate Python installation** (EDMC bundles its own).

**Optional:**

- [EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) for in-game overlay alerts. The legacy `EDMCOverlay` also works. With neither installed, the overlay feature simply switches itself off and everything else runs normally.
- Node.js 18+ — **only** if you want to run the build script, which just copies files. You never need it to *use* the plugin.

## Installation

Installing means putting a folder named `EDPLG` into your EDMC plugins directory and restarting EDMC. Nothing is compiled.

### Step 1 — Find your plugins folder

Easiest: open EDMC, go to **File → Settings → Plugins**, and click **Open** next to *"Plugins folder"*.

Or navigate there yourself:

| Platform | Plugins folder |
|----------|----------------|
| Windows | `%LOCALAPPDATA%\EDMarketConnector\plugins` |
| macOS | `~/Library/Application Support/EDMarketConnector/plugins` |
| Linux | `~/.local/share/EDMarketConnector/plugins` |

> On Windows, paste `%LOCALAPPDATA%\EDMarketConnector\plugins` into the File Explorer address bar and press Enter.

### Step 2 — Put `EDPLG` in place

Download or `git clone` this repository, then copy the **`plugin/` folder** into your plugins directory and **rename it to `EDPLG`**.

That is the whole install. (If you have Node.js and prefer a folder that is already named correctly and stripped of `__pycache__`, run `npm run build` and copy `dist/EDPLG/` instead — the result is identical.)

The final layout must look like this:

```
<EDMC plugins folder>/
└── EDPLG/
    ├── __init__.py
    ├── load.py
    ├── inventory.py
    ├── suit.py
    ├── overlay.py
    ├── sound.py
    ├── window.py
    ├── names.py
    ├── names_fdevids.py
    ├── update.py
    └── ui.py
```

> **The folder name matters.** It must be exactly `EDPLG`, with the `.py` files sitting directly inside it. If you end up with `EDPLG/plugin/load.py`, move the files up a level. EDMC derives the plugin's logger name from the folder name, so a rename breaks logging.

### Step 3 — Restart and verify

1. Fully quit EDMC and start it again — plugins load only at launch.
2. You should see the **ED-PLG** panel on the EDMC main window, and **EDPLG** listed under *Enabled plugins* in **File → Settings → Plugins**.
3. With no game running the panel shows a neutral status. It changes to **Inventory synced** once you load a commander.

Nothing showing up? See [Troubleshooting](#troubleshooting).

## Usage

Launch Elite Dangerous and EDMC as usual, load your commander, and go raid something. Each pickup updates the panel, writes a line to the log, and draws an overlay message if you have an overlay plugin.

### The main panel

The panel's title line is just **▾ ED Pillage & Payload (ED-PLG)** — nothing else — and is clickable: it collapses everything below down to just that one line, or expands it back out. EDMC remembers whichever state you leave it in. (This spelled-out-name-plus-abbreviation title, with nothing else sharing its line, matches the convention used across this developer's other EDMC plugins.)

Expanded, the live status line ("Awaiting Odyssey loot…", "Inventory synced", …) sits directly below the title, followed by a bar for **Backpack** and **Ship Locker**, a fourth bar for whatever cargo hold you currently occupy (see [Ship & SRV cargo](#ship--srv-cargo)), and a **Carrier Locker** bar *only once ED-PLG has confirmed you actually own a fleet carrier* — a commander with no carrier never sees that row at all. Each bar has its own colour (Backpack blue, Ship Locker green, Carrier Locker violet, Cargo orange) and turns red once its store is completely full. **Click any bar** to open the full inventory window — there's no separate button.

### Ship & SRV cargo

The fourth main-panel bar tracks tonnage in whichever cargo hold applies to your current situation, and changes with it:

| You are... | Bar shows |
|---|---|
| In your ship | Ship cargo hold, used / total capacity |
| In a deployed SRV | The SRV's cargo hold, used / capacity (Scarab: 4t, Scorpion: 2t) |
| On foot, no vehicle | Bar is hidden — no cargo hold applies |

This is tonnage only — ED-PLG still has no idea what commodities are actually in the hold, and never will (see Scope above). The Rhino SRV (added 2026-09-02) shows its cargo count but not a capacity yet: Frontier describes its hold as expandable up to 24t, and there's no confirmed journal field for the actual fitted number yet, so ED-PLG shows what it knows rather than guessing.

### The inventory window

Click any bar on the ED-PLG panel:

| Tab | Contents |
|-----|----------|
| Backpack | What you are carrying, against your suit's capacity |
| Ship Locker | What is stowed in the ship (1000 per category) |
| Carrier Locker | Fleet carrier locker from CAPI, when available |

Each tab shows a total and capacity bar for **Assets**, **Goods**, and **Data**, then every resource you hold and its count. It updates live as you loot and can stay open while you play.

The **Filter** box above the tabs narrows the item listing on all three tabs to resources whose name contains what you type (case-insensitive) — the category totals and capacity bars stay unfiltered so you can still see the full picture while hunting for one resource. Clear it, or click **Clear**, to see everything again.

Because your suit sets your capacity, the heading names it and whether the capacity mod is fitted — for example `Suit: Maverick Suit (Grade 4) + Extra Backpack Capacity`.

### Overlay notifications

With an overlay plugin installed, each pickup draws a line in-game, coloured by category (blue Assets, green Goods, violet Data) so a fast loot run is scannable at a glance:

```
+1  Manufacturing Instructions: 13   (violet - Data)
+2  Circuit Board: 5                 (blue - Assets)
```

Up to five lines stack, newest first, each lasting 8 seconds. Looting the same item again **updates its existing line** instead of adding a duplicate, so a fast loot run does not spam the stack.

Every ED-PLG message uses the `edplg-` ID prefix, which means you can reposition the whole stack from ModernOverlay's controller by adding an `edplg-` prefix group. Alternatively, **File → Settings → ED-PLG** has an **Overlay position** X/Y field (default 900, 120, on the legacy overlay's 1280x960 virtual screen) if you'd rather set it directly without a ModernOverlay group.

If the overlay throws an error at any point, ED-PLG disables it for the session rather than letting it break inventory tracking. Tracking is the job; the overlay is a nicety.

### Ship locker capacity bars

**File → Settings → ED-PLG**'s **"Show ship locker capacity bars on the overlay"** (off by default) draws a small persistent panel below the pillage stack — one row per category (Assets/Goods/Data), each a bar and a `total/1000` reading in that category's colour — so you can see how full your ship locker is without opening the inventory window. It redraws whenever your ship locker changes, and stays up between updates rather than fading like a pillage line.

### ModernOverlay panel (experimental)

If you're running EDMCModernOverlay specifically (not the older EDMCOverlay), ED-PLG makes a best-effort attempt to register its own panel group — a background box behind the pillage stack and capacity bars, anchored to a screen corner via **"Overlay panel anchor"** in Settings (nw/n/ne/w/center/e/sw/s/se; default `ne`) — instead of relying only on the raw X/Y position. This uses an internal ModernOverlay API that hasn't been confirmed working end-to-end yet; if it doesn't do anything visible, ED-PLG still draws everything exactly as it would without it, just without the background panel. The anchor field is greyed out unless ModernOverlay is detected.

### Muting a category's notifications

**File → Settings → ED-PLG** has an **Announce pickups for** row with a checkbox per category (Assets, Goods, Data). Unchecking one silences that category's pillage notification — log line, overlay line, and the main-panel status — without affecting tracking: its counts still show up in the inventory window and count toward combined totals exactly as before. Useful if, say, you only care about being told about Data pickups and want Assets/Goods to stay quiet.

### Notification settings

**File → Settings → ED-PLG** also has:

- **Pillage message** — a template for the `[Manufacturing Instructions] pillaged! New Inventory Total: 12`-style message, using `{item}` and `{total}` placeholders. Leave it blank to reset to the default. An invalid template (e.g. an unknown placeholder) falls back to the default rather than breaking notifications.
- **Play a sound on pickup** — a short system beep alongside each pillage notification. Off by default; Windows-only (uses the standard library's `winsound`, so there's still nothing to `pip install`), and the checkbox is greyed out where it isn't available.

Both apply to the log line, panel status, and the message EDMC records as the "last event" — not the overlay's terser stack line, which stays fixed so it keeps fitting the overlay.

### Settings

**File → Settings → ED-PLG**:

| Setting | Default | Description |
|---------|---------|-------------|
| Automatically download updates | **Off** | Opt-in; see [Updates](#updates) below |
| Pillage message | Built-in default | `{item}`/`{total}` template; see [Notification settings](#notification-settings) above |
| Play a sound on pickup | **Off** | Windows-only; see [Notification settings](#notification-settings) above |
| Show pillage notifications on the in-game overlay | On | Greyed out when no overlay plugin is installed |
| Show ship locker capacity bars on the overlay | **Off** | See [Ship locker capacity bars](#ship-locker-capacity-bars) above |
| Overlay panel anchor | `ne` | ModernOverlay only, greyed out otherwise; see [ModernOverlay panel](#modernoverlay-panel-experimental) above |
| Overlay position (X / Y) | 900 / 120 | See [Overlay notifications](#overlay-notifications) above |
| Announce pickups for (Assets/Goods/Data) | All on | See [Muting a category's notifications](#muting-a-categorys-notifications) above |
| Suit Backpack Capacity | Unengineered default per suit | One editable row per suit loadout you've worn; see [Backpack capacity](#backpack-capacity-defaults-plus-your-own-numbers) above |

## Updates

**Off by default — this is opt-in, not opt-out.** Turn on "Automatically download updates" in **File → Settings → ED-PLG** if you want it: once per EDMC launch, the plugin then checks GitHub for a newer release and, if there is one, downloads and stages it automatically — it takes effect the next time you restart EDMC. Nothing is sent in that check beyond the request itself (no telemetry, no inventory data).

The plugin version lives only in the Settings tab (a static link to the [latest release on GitHub](https://github.com/rwharpernc/ED-PLG/releases/latest)) — the main panel stays silent about it except for one thing: right after a staged update takes effect, it briefly shows "Updated to vX.Y.Z" for a few seconds, then goes back to showing nothing there.

A backup of your current install is kept (the 3 most recent, in `backups/` inside the plugin folder) before each update is applied, in case anything goes wrong.

If you turn it on for a copy you're actively hand-editing (developing, not just running it), drop an empty `disable-auto-update.txt` file directly in the plugin folder — that disables auto-update for that install regardless of the Settings checkbox, so a background check can't clobber in-progress work.

## Troubleshooting

The EDMC log is at `%TEMP%\EDMarketConnector.log` on Windows; search it for `EDPLG`. Python import and syntax errors surface there.

- **Plugin not listed / no panel** — Check the folder is named exactly `EDPLG` with the `.py` files directly inside (see the layout above), then restart EDMC.
- **Listed as disabled** — A folder name ending in `.disabled` is skipped by EDMC. Remove the suffix and restart.
- **Overlay messages not appearing** — Confirm EDMCModernOverlay is installed and running. In **File → Settings → ED-PLG**, a greyed-out checkbox means EDMC could not import `edmcoverlay` at all. If the box is enabled but nothing draws, search the log for `EDMCModernOverlay is not available to accept messages`.
- **Wrong backpack capacity** — Expected for an engineered suit or the Flight Suit; the game never publishes capacity, so unengineered defaults are hardcoded. Enter the correct number for that specific loadout in **File → Settings → ED-PLG**.
- **Carrier numbers look stale** — Also expected. CAPI is throttled; see [Fleet carrier data is late](#fleet-carrier-data-is-late).

## How it works

### ED-PLG never touches the game

The plugin does not read your game files, inject anything, or talk to Elite Dangerous at all. It is a passive listener sitting behind EDMC:

```
Elite Dangerous  →  writes journal files  →  EDMC tails them  →  ED-PLG reacts
```

EDMC watches the game's journal (the event log Frontier writes to disk as you play), parses each event, and hands it to every installed plugin. ED-PLG implements EDMC's plugin callbacks — chiefly `journal_entry()` — and updates its own counts from what it is given. Everything you see in the panel, window, and overlay is derived from that stream.

This is why the plugin is read-only and safe by construction, and also why it can only know what the journal chooses to report. Most of the [limitations](#known-limitations) below trace back to that one fact.

### Three stores, one total

ED-PLG keeps three separate ledgers, because the game does:

| Store | Source | Notes |
|-------|--------|-------|
| **Backpack** | Journal | What you are carrying on foot. Capacity depends on your suit. |
| **Ship locker** | Journal | What is stowed in the ship. 1000 per category. |
| **Carrier locker** | Frontier CAPI | Your fleet carrier's locker, if you have one. Lags the live game. |

The number in a pillage message — *"New Inventory Total: 12"* — is the **sum of all three**. That is the question you actually want answered when a container pops open: *do I already have enough of this?* Not *how many are in my backpack right now?* If you are ever confused why the announced total exceeds what your backpack could possibly hold, this is why. The Inventory window breaks the same data back out per location.

Ship/SRV cargo (see [Ship & SRV cargo](#ship--srv-cargo)) is a separate, fourth ledger tracked purely for its own bar — it is never included in a pillage total, since cargo tonnage and Odyssey microresources are unrelated game systems that happen to share a panel.

### Baselines and deltas

Two kinds of journal event drive the counts, and they work differently:

- **Baseline events** (`LoadGame`, `Backpack`, `ShipLocker`, `SuitLoadout`, …) carry a *full* listing. ED-PLG throws away its counts and rebuilds them from scratch. These fire when you log in, disembark, board, or resupply.
- **Delta events** (`BackpackChange`) carry only *what changed* — "+1 Manufacturing Instructions". ED-PLG applies the change to its running counts, and this is the only event that triggers a pillage announcement.

Deltas are fast but can drift if one is ever missed. So after processing every `BackpackChange`, ED-PLG **reconciles against EDMC's own inventory state** rather than trusting its arithmetic ([load.py:244](plugin/load.py#L244)). The delta tells you what to *announce*; EDMC's state decides what is *true*. Errors cannot accumulate across a session.

### Categories

The game's UI and its journal use different words for the same three things. ED-PLG speaks journal internally and shows you the in-game labels:

| In game | Journal / code | Example |
|---------|----------------|---------|
| Assets | `Component` | Circuit Board |
| Goods | `Item` | Health Pack |
| Data | `Data` | Manufacturing Instructions |

Consumables (grenades, energy cells) are counted internally to keep the backpack model honest, but never announced as pillage — you did not loot them, you were issued them.

### Resource names

Frontier's journal identifies resources by internal ID (`manufacturinginstructions`). Display names are resolved in this order:

1. `Name_Localised` from the journal event — the game's own label, correct and localised
2. A small curated override table in [names.py](plugin/names.py)
3. A generated table imported from [EDCD/FDevIDs](https://github.com/EDCD/FDevIDs)' `microresources.csv` ([names_fdevids.py](plugin/names_fdevids.py)) — covers essentially every Component/Item/Data microresource in the game
4. Names learned from `Name_Localised` earlier in this session or a previous one — the
   learned cache is persisted to EDMC's config and restored on the next launch
5. A title-cased fallback

The generated table (step 3) does the heavy lifting — it's refreshed from FDevIDs by running `npm run update-names` (a maintenance step, not part of the normal build; see [For Developers](#for-developers) below) and committed like any other change, so the *running* plugin never touches the network for it. The curated table (step 2) stays small on purpose: it only covers internal names ED-PLG has seen in-game that FDevIDs doesn't (yet) list.

### Backpack capacity: defaults plus your own numbers

**The journal reports what is in your backpack, but never how much it holds.** There is no event, anywhere, that publishes your capacity. So ED-PLG hardcodes the unengineered defaults, in [suit.py](plugin/suit.py), keyed by suit type and whether the *Extra Backpack Capacity* mod is fitted. Suit **grade does not affect capacity** on its own — a Grade 5 Maverick carries exactly as much as a Grade 1 one *unless* Extra Backpack Capacity is engineered onto it, and the journal only reports whether that mod is present, not which grade.

| Suit | Goods (Item) | Assets (Component) | Data |
|------|--------------|--------------------|------|
| Maverick | 40 → **80** | 60 → **120** | 20 → **40** |
| Artemis | 20 → **40** | 40 → **80** | 10 → **20** |
| Dominator | 10 → **20** | 20 → **40** | 10 → **20** |
| Flight Suit | unknown | unknown | unknown |

*(base → with Extra Backpack Capacity)*

Because engineering grade isn't visible to the plugin, and the Flight Suit has no known figure at all, **File → Settings → ED-PLG** lists every suit loadout you've been seen wearing, with an editable capacity field per category, pre-filled with the default above. Leave a field alone if it's right; update it if that specific loadout is engineered (or otherwise holds a different amount) — the Inventory window's capacity bar for that loadout then uses your number instead of the default. Where no default exists (Flight Suit) and you haven't entered one either, the window shows a plain count and **no capacity bar** rather than inventing a limit.

### Fleet carrier data is late

Carrier locker contents do not appear in the journal at all. They come from Frontier's CAPI, which EDMC fetches on carrier events with a 15-minute throttle — so **carrier figures can lag the live game by 15–30 minutes**. Treat them as a recent snapshot, not a live readout. Data is cached per commander, so switching accounts never bleeds counts between CMDRs.

### Ship locker capacity warning

The ship locker caps at 1000 per category. Fill one while out looting and you can be forced to drop items rather than store them — whether you're offloading at your own ship, or remotely via an Apex shuttle's "Manage Items" screen (which isn't separate storage — it's a proxy into the same locker your ship uses).

When a category (Assets, Goods, or Data) reaches 90% of capacity (900/1000), ED-PLG sends a red, longer-lived overlay warning distinct from ordinary pillage notifications, and logs it. It won't repeat while you stay over 90%, but it rearms — so if you offload and later refill past 90% again, you'll get warned again. Requires the in-game overlay to be installed and enabled; it also always logs to `EDMarketConnector.log` either way.

## Known Limitations

Nearly all of these come from the same root cause: **the plugin can only know what the journal tells it.**

- **Backpack capacity is not published by the game** — hence the hardcoded default table in `suit.py`, which can't reflect *Extra Backpack Capacity*'s engineering grade or the Flight Suit (no known default at all). Correct it per suit loadout in **File → Settings → ED-PLG** rather than guessing.
- **Backpack contents may be incomplete if you log in already on foot** — the game does not always emit a full baseline in that case. ED-PLG can't fill the gap, but it does track whether a real baseline has arrived this session and will show "backpack pending first sync" in the panel and inventory window instead of presenting a possibly-stale zero as confirmed.
- **Some consumable changes have no journal event at all** (throwing a grenade, for instance), so those counts can drift until the next baseline.
- **Fleet carrier data lags 15–30 minutes** — CAPI, not journal, and throttled.
- Inventory tracking leans on EDMC's best-effort `BackPack` state; ED-PLG reconciles against it after every change, which corrects drift but inherits any gaps EDMC itself has.
- **Rhino SRV cargo capacity is unknown** — brand new at the time of writing (2026-09-02), with no confirmed journal field for its fitted capacity. Its bar shows a current count with no `/capacity`, rather than a guessed number, until that's confirmed.
- **SRV type is matched fuzzily** (a case-insensitive substring match against whatever the journal reports for `SRVType`/`SRVType_Localised`, since the exact raw values aren't documented) — the safe failure mode is an unrecognised SRV falling back to a generic "SRV Cargo" bar with no capacity, never a wrong number.

See [Design Specification — Known Limitations](docs/design-spec.md#11-known-limitations) for the detail.

## For Developers

```bash
npm run build         # copies plugin/ → dist/EDPLG/, stripping __pycache__
npm run package       # does the above, then zips it to dist/EDPLG-v<version>.zip
npm run update-names  # regenerates plugin/names_fdevids.py from FDevIDs (maintenance, needs network)
```

The build script is a convenience, not a compiler — the plugin *is* its source. Edit `plugin/`, rebuild if you like, copy to EDMC, restart. `npm run package`'s zip is the same artifact published on the Releases page. `update-names` is the one exception: it's a separate, occasional maintenance step (not run by `build`/`package`) that hits the network to pull the latest FDevIDs data — see [Resource names](#resource-names) above.

```
ED-PLG/
├── plugin/           # Python source — this is the plugin
├── docs/             # Specifications and credits
├── scripts/          # build.mjs, package.mjs, update-names.mjs
├── dist/EDPLG/       # Build output (gitignored)
├── CHANGELOG.md
├── LICENSE
└── README.md
```

Module map, in rough order of the data flow described above:

| File | Role |
|------|------|
| [load.py](plugin/load.py) | EDMC entry point; receives journal events and dispatches them |
| [inventory.py](plugin/inventory.py) | The three microresource stores; applies baselines, deltas, and CAPI data |
| [cargo.py](plugin/cargo.py) | Ship/SRV vehicle tracking and cargo-hold capacity — a separate ledger from inventory.py |
| [suit.py](plugin/suit.py) | Current suit and the backpack capacity table |
| [names.py](plugin/names.py) | Internal ID → display name resolution |
| [names_fdevids.py](plugin/names_fdevids.py) | Generated: FDevIDs microresource names — do not hand-edit; regenerate with `npm run update-names` |
| [ui.py](plugin/ui.py) | EDMC main-window panel and settings tab |
| [window.py](plugin/window.py) | The tabbed inventory window |
| [overlay.py](plugin/overlay.py) | In-game overlay client |
| [sound.py](plugin/sound.py) | Optional pickup notification sound (Windows `winsound`) |
| [update.py](plugin/update.py) | Checks GitHub Releases and self-updates (see [Updates](#updates) above) |

Dependencies point one way: `load.py` knows about everything; `ui.py` does not import `load.py` (opening the inventory window from a bar click is wired through a callback, same as the button it replaced); `window.py` reads a `snapshot()` from the tracker rather than reaching into it.

**Auto-update is off by default, but can still overwrite a local test install if you've turned it on for that copy.** A plugin folder dropped into your EDMC plugins directory for testing looks, to `update.py`, exactly like a real install - if "Automatically download updates" is enabled there and the local build is older than the latest GitHub Release, EDMC will download and stage that release over your hand-edited files on its next restart. Drop an empty `disable-auto-update.txt` file in the plugin folder to override the checkbox unconditionally if you want it on elsewhere while still hand-editing this copy.

The tracker, names, suit, cargo, overlay, sound, and window modules can all be exercised **outside EDMC** by stubbing the `config` and `theme` modules in `sys.modules` and replaying real journal lines through the tracker — useful, since the alternative is flying to a settlement to test a one-line change.

See the [Technical Specification](docs/tech-spec.md) for the full API surface, event schemas, and handler behaviour.

## Documentation

| Document | Description |
|----------|-------------|
| [Design Specification](docs/design-spec.md) | User experience, requirements, and event flow |
| [Technical Specification](docs/tech-spec.md) | API surface, modules, journal events, build system |
| [Attributions & Credits](docs/ATTRIBUTIONS.md) | Third-party references and acknowledgements |
| [Changelog](CHANGELOG.md) | Release history |

## Credits & License

ED-PLG is a fan-made tool by **CMDR Bocheaux**. It is not affiliated with Frontier Developments or the EDMC development team.

Full credits — including EDMC, the Elite Dangerous Player Journal documentation, and EDCD/FDevIDs microresource data — are in [docs/ATTRIBUTIONS.md](docs/ATTRIBUTIONS.md).

Copyright (c) 2025 CMDR Bocheaux. Released under the [MIT License](LICENSE).
