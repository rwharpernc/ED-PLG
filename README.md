# ED-PLG

**Elite Dangerous Pillage Ledger & Gear-tracker**

A lightweight [Elite Dangerous Market Connector](https://github.com/EDCD/EDMarketConnector) (EDMC) plugin for *Elite Dangerous: Odyssey*. ED-PLG tracks on-foot microresources — the components, items, and data you spend on suit and weapon upgrades — and tells you what you just looted, how much of it you now own, and whether you still have room to carry it.

**Author:** CMDR Mactavious  
**Version:** 0.7.2  
**License:** [MIT](LICENSE)

---

## What it does

When you loot a container on foot, ED-PLG announces it — in the EDMC panel, in the log, and (optionally) on an in-game overlay:

```
[Manufacturing Instructions] pillaged! New Inventory Total: 12
```

That total is the number that matters when you are deciding whether a pickup is worth a backpack slot, and it is *not* just what is in your backpack — see [How it works](#how-it-works) below.

- **Live inventory tracking** across your suit backpack, ship locker, and fleet carrier locker
- **Pillage notifications** on every pickup, with your new combined total
- **In-game overlay alerts** via [EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) (optional — the plugin works fine without it)
- **Inventory window** — a tabbed view of everything you hold, with capacity bars per category, so you can see at a glance how close your backpack is to full
- **Real names** for Frontier's internal resource IDs (`manufacturinginstructions` → *Manufacturing Instructions*)

**Deliberately out of scope:** ship engineering materials (Raw, Manufactured, Encoded) and commodity cargo. Those are separate game systems. ED-PLG deals only in Odyssey microresources — the stuff that upgrades your ground gear.

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
2. A curated override table in [names.py](plugin/names.py)
3. Names learned from `Name_Localised` earlier in this session or a previous one — the
   learned cache is persisted to EDMC's config and restored on the next launch
4. A title-cased fallback

Because the game supplies `Name_Localised` for essentially every resource whose label differs from its ID, the curated table rarely needs to grow. It exists to fix the cases the fallback mangles — acronyms like `rdx` → **RDX** — not to enumerate the game.

### Backpack capacity is guesswork (and why)

**The journal reports what is in your backpack, but never how much it holds.** There is no event, anywhere, that publishes your capacity. So ED-PLG can either hardcode the figures or show you nothing.

It hardcodes them, in [suit.py](plugin/suit.py), keyed by suit type and whether the *Extra Backpack Capacity* mod is fitted. Suit **grade does not affect capacity** — a Grade 5 Maverick carries exactly as much as a Grade 1 one.

| Suit | Goods (Item) | Assets (Component) | Data |
|------|--------------|--------------------|------|
| Maverick | 40 → **80** | 60 → **120** | 10 → **40** |
| Artemis | 20 → **40** | 40 → **80** | 10 → **20** |
| Dominator | 10 → **20** | 20 → **40** | 10 → **20** |
| Flight Suit | unknown | unknown | unknown |

*(base → with Extra Backpack Capacity)*

Where a capacity is unknown, the window shows a plain count and **no capacity bar** — it will not invent a limit and mislead you. If a figure disagrees with your game, the `CAPACITIES` table in `suit.py` is the one place to correct it.

### Fleet carrier data is late

Carrier locker contents do not appear in the journal at all. They come from Frontier's CAPI, which EDMC fetches on carrier events with a 15-minute throttle — so **carrier figures can lag the live game by 15–30 minutes**. Treat them as a recent snapshot, not a live readout. Data is cached per commander, so switching accounts never bleeds counts between CMDRs.

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
    ├── window.py
    ├── names.py
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

### The inventory window

Click **Inventory** on the ED-PLG panel:

| Tab | Contents |
|-----|----------|
| Backpack | What you are carrying, against your suit's capacity |
| Ship Locker | What is stowed in the ship (1000 per category) |
| Carrier Locker | Fleet carrier locker from CAPI, when available |

Each tab shows a total and capacity bar for **Assets**, **Goods**, and **Data**, then every resource you hold and its count. It updates live as you loot and can stay open while you play.

Because your suit sets your capacity, the heading names it and whether the capacity mod is fitted — for example `Suit: Maverick Suit (Grade 4) + Extra Backpack Capacity`.

### Overlay notifications

With an overlay plugin installed, each pickup draws a line in-game:

```
+1  Manufacturing Instructions: 13
+2  Circuit Board: 5
```

Up to five lines stack, newest first, each lasting 8 seconds. Looting the same item again **updates its existing line** instead of adding a duplicate, so a fast loot run does not spam the stack.

Every ED-PLG message uses the `edplg-` ID prefix, which means you can reposition the whole stack from ModernOverlay's controller by adding an `edplg-` prefix group. Do that rather than editing coordinates in `overlay.py` — your change will survive plugin updates.

If the overlay throws an error at any point, ED-PLG disables it for the session rather than letting it break inventory tracking. Tracking is the job; the overlay is a nicety.

### Settings

**File → Settings → ED-PLG**:

| Setting | Default | Description |
|---------|---------|-------------|
| Show pillage notifications on the in-game overlay | On | Greyed out when no overlay plugin is installed |

## Troubleshooting

The EDMC log is at `%TEMP%\EDMarketConnector.log` on Windows; search it for `EDPLG`. Python import and syntax errors surface there.

- **Plugin not listed / no panel** — Check the folder is named exactly `EDPLG` with the `.py` files directly inside (see the layout above), then restart EDMC.
- **Listed as disabled** — A folder name ending in `.disabled` is skipped by EDMC. Remove the suffix and restart.
- **Overlay messages not appearing** — Confirm EDMCModernOverlay is installed and running. In **File → Settings → ED-PLG**, a greyed-out checkbox means EDMC could not import `edmcoverlay` at all. If the box is enabled but nothing draws, search the log for `EDMCModernOverlay is not available to accept messages`.
- **Wrong backpack capacity** — Expected; the game never publishes capacity, so it is hardcoded. Fix the `CAPACITIES` table in `plugin/suit.py`.
- **Carrier numbers look stale** — Also expected. CAPI is throttled; see [Fleet carrier data is late](#fleet-carrier-data-is-late).

## Development

```bash
npm run build     # copies plugin/ → dist/EDPLG/, stripping __pycache__
```

The build script is a convenience, not a compiler — the plugin *is* its source. Edit `plugin/`, rebuild if you like, copy to EDMC, restart.

```
ED-PLG/
├── plugin/           # Python source — this is the plugin
├── docs/             # Specifications and credits
├── scripts/          # build.mjs
├── dist/EDPLG/       # Build output (gitignored)
├── CHANGELOG.md
├── LICENSE
└── README.md
```

Module map, in rough order of the data flow described above:

| File | Role |
|------|------|
| [load.py](plugin/load.py) | EDMC entry point; receives journal events and dispatches them |
| [inventory.py](plugin/inventory.py) | The three stores; applies baselines, deltas, and CAPI data |
| [suit.py](plugin/suit.py) | Current suit and the backpack capacity table |
| [names.py](plugin/names.py) | Internal ID → display name resolution |
| [ui.py](plugin/ui.py) | EDMC main-window panel and settings tab |
| [window.py](plugin/window.py) | The tabbed inventory window |
| [overlay.py](plugin/overlay.py) | In-game overlay client |

Dependencies point one way: `load.py` knows about everything; `ui.py` does not import `load.py` (the Inventory button is wired through a callback); `window.py` reads a `snapshot()` from the tracker rather than reaching into it.

The tracker, names, suit, overlay, and window modules can all be exercised **outside EDMC** by stubbing the `config` and `theme` modules in `sys.modules` and replaying real journal lines through the tracker — useful, since the alternative is flying to a settlement to test a one-line change.

See the [Technical Specification](docs/tech-spec.md) for the full API surface, event schemas, and handler behaviour.

## Known Limitations

Nearly all of these come from the same root cause: **the plugin can only know what the journal tells it.**

- **Backpack capacity is not published by the game** — hence the hardcoded table in `suit.py`. Flight Suit capacity is unknown and renders without a limit; reliable figures could not be sourced (see `TODO.md`), and the plugin won't guess.
- **Backpack contents may be incomplete if you log in already on foot** — the game does not always emit a full baseline in that case. ED-PLG can't fill the gap, but it does track whether a real baseline has arrived this session and will show "backpack pending first sync" in the panel and inventory window instead of presenting a possibly-stale zero as confirmed.
- **Some consumable changes have no journal event at all** (throwing a grenade, for instance), so those counts can drift until the next baseline.
- **Fleet carrier data lags 15–30 minutes** — CAPI, not journal, and throttled.
- Inventory tracking leans on EDMC's best-effort `BackPack` state; ED-PLG reconciles against it after every change, which corrects drift but inherits any gaps EDMC itself has.

See [Design Specification — Known Limitations](docs/design-spec.md#10-known-limitations) for the detail.

## Documentation

| Document | Description |
|----------|-------------|
| [Design Specification](docs/design-spec.md) | User experience, requirements, and event flow |
| [Technical Specification](docs/tech-spec.md) | API surface, modules, journal events, build system |
| [Attributions & Credits](docs/ATTRIBUTIONS.md) | Third-party references and acknowledgements |
| [Changelog](CHANGELOG.md) | Release history |

## Credits & License

ED-PLG is a fan-made tool by **CMDR Mactavious**. It is not affiliated with Frontier Developments or the EDMC development team.

Full credits — including EDMC, the Elite Dangerous Player Journal documentation, and EDCD/FDevIDs microresource data — are in [docs/ATTRIBUTIONS.md](docs/ATTRIBUTIONS.md).

Copyright (c) 2025 CMDR Mactavious. Released under the [MIT License](LICENSE).
