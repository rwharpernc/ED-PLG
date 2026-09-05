# ED-PLG

**ED Pillage & Payload**

A lightweight [Elite Dangerous Market Connector](https://github.com/EDCD/EDMarketConnector) (EDMC) plugin for *Elite Dangerous: Odyssey* that tracks the on-foot microresources you loot — components, items, and data — announces every pickup with your new combined total, and keeps an eye on your ship/SRV cargo hold too, so one panel covers everything you're carrying, on foot or in a vehicle. ED-PLG never touches the game itself; it only reads *Elite Dangerous*'s own journal files via EDMC, the same way EDMC does.

**Author:** R.W. Harper (CMDR Bocheaux)  
**Version:** 1.3.0  
**License:** [MIT](LICENSE)

---

## Features

- **Live inventory tracking** across your suit backpack, ship locker, and fleet carrier locker.
- **Pillage notifications** on every pickup, with your new combined total — wording, a pickup sound, and which categories announce at all are configurable.
- **Collapsible main panel with at-a-glance bars** — Backpack, Ship Locker, Carrier Locker, and your current vehicle's Cargo hold, colour-coded and click-to-open.
- **Ship & SRV cargo tracking** — a bar that automatically switches between your ship's cargo hold and whatever SRV you're driving, hidden entirely on foot.
- **In-game overlay** — pillage notifications and any of the four inventory bars, individually toggleable and colour-matched to the panel, via EDMCModernOverlay (or the older EDMCOverlay).
- **Inventory window** — a tabbed, filterable view of everything you hold, with a capacity bar per category.
- **Ship locker capacity warning** — an overlay alert the moment a category hits 90% full, so you're not caught having to drop loot.
- **Real resource names** for essentially every Odyssey microresource, imported from [EDCD/FDevIDs](https://github.com/EDCD/FDevIDs).
- **Self-update** — optional one-click updates from Settings; off by default.

## Table of Contents

- [Install](#install)
- [Updates](#updates)
- [Using ED-PLG](#using-ed-plg)
- [Three stores, one total](#three-stores-one-total)
- [Backpack capacity](#backpack-capacity)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [For Developers](#for-developers)
- [Learn More](#learn-more)

## Install

You don't need Node.js, Python, or any of this repo's source tree — just a release zip. Requires EDMC 5.x and *Elite Dangerous: Odyssey*; [EDMCModernOverlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) (or the older EDMCOverlay) is optional, only needed for in-game overlay alerts.

1. Download the latest `EDPLG-vX.Y.Z.zip` from the [Releases page](https://github.com/rwharpernc/ED-PLG/releases/latest).
2. Extract it, then copy the `EDPLG` folder it contains into your EDMC plugins folder: `%LOCALAPPDATA%\EDMarketConnector\plugins\EDPLG` on Windows (macOS: `~/Library/Application Support/EDMarketConnector/plugins`; Linux: `~/.local/share/EDMarketConnector/plugins`).
3. Restart EDMC.

You should see the **ED Pillage & Payload (ED-PLG)** panel on the EDMC main window. With no game running it shows a neutral status; it changes to **Inventory synced** once you load a commander. Nothing showing up? See [Troubleshooting](#troubleshooting).

After that first install, you can turn on auto-update from the Settings tab if you'd rather not track new releases yourself — see Updates below.

## Updates

**Off by default — this is opt-in, not opt-out.** Turn on "Automatically download updates" in **File → Settings → ED-PLG** if you want it: the plugin then checks GitHub for a newer release once per EDMC launch and, if there is one, downloads and stages it automatically — it takes effect the next time you restart EDMC. Nothing is sent in that check beyond the request itself (no telemetry, no inventory data). Your settings, per-suit capacity overrides, and learned resource names all live in EDMC's own configuration rather than the plugin folder, so they're untouched by any update, automatic or manual.

The plugin version lives only in the Settings tab (a static link to the [latest release on GitHub](https://github.com/rwharpernc/ED-PLG/releases/latest)) — the main panel stays silent about it except for one thing: right after a staged update takes effect, it briefly shows "Updated to vX.Y.Z" for a few seconds, then goes back to showing nothing there.

A backup of your current install is kept (the 3 most recent, in `backups/` inside the plugin folder) before each update is applied, in case anything goes wrong.

If you're hand-editing a copy of the plugin rather than just running it, drop an empty `disable-auto-update.txt` file directly in the plugin folder — that disables auto-update for that install regardless of the Settings checkbox, so a background check can't clobber in-progress work.

## Using ED-PLG

Launch Elite Dangerous and EDMC as usual, load your commander, and go raid something. Each pickup updates the panel, writes a line to the log, and draws an overlay message if you have an overlay plugin installed.

- **Main panel** — the title line (`▾ ED Pillage & Payload (ED-PLG)`) is clickable: it collapses everything below down to just that one line, or expands it back out — EDMC remembers your choice. Expanded, a live status line ("Awaiting Odyssey loot…", "Inventory synced", …) sits below the title, followed by four colour-coded bars: **Backpack** (blue) and **Ship Locker** (green) always shown, **Carrier Locker** (violet) only once ED-PLG has confirmed you actually own a fleet carrier, and **Cargo** (orange) for whichever hold applies to your current vehicle. Each bar turns red once its store is completely full. **Click any bar** to open the full inventory window — there's no separate button, and a reminder line at the bottom of the panel says so.
- **Ship & SRV cargo** — the Cargo bar tracks tonnage in whichever hold applies right now, and switches automatically: your ship's cargo hold while you're aboard it, an SRV's hold (Scarab 4t, Scorpion 2t) while you're driving one, and hidden entirely while you're on foot with no vehicle. This is tonnage only — ED-PLG has no idea what commodities are actually in the hold, and never will. The Rhino SRV shows a cargo count but not a capacity yet, since Frontier hasn't published its actual fitted number (see [Known Limitations](#known-limitations)).
- **Inventory window** (click any bar to open it) — one tab each for **Backpack**, **Ship Locker**, and **Carrier Locker** (Carrier Locker only appears once you're confirmed to own one, appearing or disappearing live if that changes mid-session), each with a total and capacity bar per category (**Assets**, **Goods**, **Data**) and every resource you hold, sorted by count. A **Filter** box above the tabs narrows the item list to names containing what you type, without touching the totals or bars. It updates live and can stay open while you play. The heading names your current suit and whether its capacity mod is fitted, e.g. `Suit: Maverick Suit (Grade 4) + Extra Backpack Capacity`.
- **Overlay notifications** — with an overlay plugin installed, each pickup draws a coloured line in-game (blue Assets, green Goods, violet Data), so a fast loot run is scannable at a glance. Up to five lines stack, newest first, each lasting 8 seconds; looting the same item again updates its existing line instead of piling up duplicates. Reposition the whole stack from ModernOverlay's controller (every message shares the `edplg-` prefix), or set an **Overlay position** X/Y directly in Settings. If the overlay ever throws an error, ED-PLG disables it for the session rather than letting it disrupt inventory tracking.
- **Overlay inventory bars** — Settings has a checkbox for each of the four main-panel bars, all off by default. Checking one draws that bar on the overlay too — colour-matched to the panel, with the same `used/capacity` reading — and, like the panel, Carrier Locker and Cargo only actually appear when they're relevant (a confirmed carrier; a vehicle whose cargo hold applies).
- **ModernOverlay panel (experimental)** — if you're running EDMCModernOverlay specifically, ED-PLG makes a best-effort attempt to draw a background panel behind the pillage stack and bars, anchored to a screen corner (**Overlay panel anchor** in Settings). This hasn't been confirmed working end-to-end yet; if it doesn't do anything visible, everything else still draws exactly as it would without it.
- **Muting a category's notifications** — an **Announce pickups for** checkbox row (Assets, Goods, Data) in Settings. Unchecking one silences that category's pillage notification everywhere (log, overlay, panel) without affecting tracking — its counts still show up in the inventory window and count toward combined totals as always.
- **Notification settings** — a **Pillage message** template (`{item}`/`{total}` placeholders, falls back to the default on a blank or invalid template) and an optional **Play a sound on pickup** (Windows only).
- **Ship locker capacity warning** — when a category (Assets, Goods, or Data) reaches 90% of its 1000 cap, ED-PLG sends a red overlay warning distinct from ordinary pillage notifications (requires the overlay to be installed and enabled; always logs either way). It won't repeat while you stay over 90%, but rearms once you drop back under and cross it again — this fires whether you're offloading at your own ship or remotely via an Apex shuttle's "Manage Items" screen, which is a proxy into the same locker.
- **Settings tab**, in full:

  | Setting | Default | Notes |
  |---------|---------|-------|
  | Automatically download updates | Off | See [Updates](#updates) |
  | Pillage message | Built-in default | `{item}`/`{total}` template |
  | Play a sound on pickup | Off | Windows-only |
  | Show pillage notifications on the in-game overlay | On | Greyed out with no overlay plugin installed |
  | Show \[Backpack / Ship Locker / Carrier Locker / Cargo\] bar on the overlay | All off | One checkbox per bar |
  | Overlay panel anchor | `ne` | ModernOverlay only |
  | Overlay position (X / Y) | 900 / 120 | Legacy overlay's virtual screen |
  | Announce pickups for (Assets/Goods/Data) | All on | See Muting above |
  | Suit Backpack Capacity | Unengineered default per suit | One editable row per suit loadout you've worn — see [Backpack capacity](#backpack-capacity) |

## Three stores, one total

ED-PLG keeps three separate ledgers, because the game does: your **backpack** (what you're carrying on foot), your **ship locker** (stowed aboard your ship, 1000 per category), and your **fleet carrier locker** (if you have one — from Frontier's CAPI, which can lag the live game by 15–30 minutes, so treat it as a recent snapshot rather than a live readout).

The number in a pillage message — *"New Inventory Total: 12"* — is the **sum of all three**. That's the question that actually matters when a container pops open: *do I already have enough of this?*, not *how many are in my backpack right now?* If the announced total ever seems to exceed what your backpack could hold, this is why — the Inventory window breaks the same data back out per location. Ship/SRV cargo is a separate, fourth ledger tracked purely for its own bar; it's never included in a pillage total, since cargo tonnage and Odyssey microresources are unrelated game systems that just happen to share a panel.

## Backpack capacity

**The game reports what's in your backpack, but never how much it holds** — there's no in-game confirmation of this number anywhere. ED-PLG assumes the unengineered defaults below, based on suit type and whether the *Extra Backpack Capacity* mod is fitted. Suit **grade doesn't affect capacity** on its own — a Grade 5 suit carries exactly as much as a Grade 1 one unless Extra Backpack Capacity is engineered onto it.

| Suit | Goods (Item) | Assets (Component) | Data |
|------|--------------|--------------------|------|
| Maverick | 40 → **80** | 60 → **120** | 20 → **40** |
| Artemis | 20 → **40** | 40 → **80** | 10 → **20** |
| Dominator | 10 → **20** | 20 → **40** | 10 → **20** |
| Flight Suit | unknown | unknown | unknown |

*(base → with Extra Backpack Capacity)*

If a specific loadout is engineered (or otherwise holds a different amount) — or you're wearing the Flight Suit, which has no known default at all — **File → Settings → ED-PLG** lists every suit loadout you've been seen wearing with an editable capacity field per category, pre-filled with the default above. Update the number for that specific loadout and the inventory window's capacity bar uses it from then on. Where no default exists and you haven't entered one either, the window shows a plain count with no capacity bar, rather than inventing a limit.

## Known Limitations

Nearly all of these trace back to the same root cause: **the plugin can only know what the journal tells it.**

- **Backpack capacity isn't published by the game** — see [Backpack capacity](#backpack-capacity) above for the defaults and how to correct one.
- **Backpack contents may be incomplete if you log in already on foot** — the game doesn't always emit a full baseline in that case. ED-PLG shows "backpack pending first sync" in the panel and inventory window rather than presenting a possibly-stale zero as confirmed.
- **Some consumable changes have no journal event at all** (throwing a grenade, for instance), so those counts can drift until the next baseline.
- **Fleet carrier data can lag 15–30 minutes** — it comes from Frontier's CAPI, not the journal, and is throttled.
- **Rhino SRV cargo capacity is unconfirmed** — brand new at the time of writing, with no published journal field for its fitted capacity yet. Its bar shows a current count with no `/capacity` until that's confirmed, rather than a guessed number.
- **Main-panel bar track colour may still be wrong under EDMC's Dark theme, on some installs.** Purely cosmetic — every bar's value, colour-coded outline, and click-to-open-inventory behaviour are unaffected; only the track's own background colour is in question. See `TODO.md`'s Known Issues for the investigation so far.

## Troubleshooting

The EDMC log is at `%LOCALAPPDATA%\EDMarketConnector\logs\EDMarketConnector.log` on Windows (confirmed on EDMC 5.6.0 — older versions may have used `%TEMP%\EDMarketConnector.log` instead); search it for `EDPLG`.

- **Plugin not listed / no panel** — Check the folder is named exactly `EDPLG` with the `.py` files directly inside it, then restart EDMC.
- **Listed as disabled** — A folder name ending in `.disabled` is skipped by EDMC. Remove the suffix and restart.
- **No Settings tab, or a field doesn't do anything** — Please [report it](https://github.com/rwharpernc/ED-PLG/issues) with the relevant log excerpt; a few real bugs of exactly this shape have already been found and fixed this way.
- **Overlay messages not appearing** — Confirm EDMCModernOverlay is installed and running. A greyed-out checkbox in Settings means EDMC couldn't import `edmcoverlay` at all; if the box is enabled but nothing draws, search the log for `EDMCModernOverlay is not available to accept messages`.
- **Wrong backpack capacity** — Expected for an engineered suit or the Flight Suit; see [Backpack capacity](#backpack-capacity) above.
- **Carrier numbers look stale** — Also expected; CAPI is throttled, see [Three stores, one total](#three-stores-one-total) above.

## For Developers

Building from source instead of using a release zip:

```bash
npm run build         # copies plugin/ → dist/EDPLG/, stripping __pycache__
npm run package       # does the above, then zips it to dist/EDPLG-v<version>.zip
npm run update-names  # regenerates plugin/names_fdevids.py from FDevIDs (maintenance, needs network)
```

Copy `dist/EDPLG` into your EDMC plugins folder the same way as the player steps above, then restart EDMC. `npm run package`'s zip is the same artifact published on the Releases page. `update-names` is a separate, occasional maintenance step (not run by `build`/`package`) that hits the network to pull the latest FDevIDs resource-name data — see the [Technical Specification](docs/tech-spec.md) (§6.5.1) for how that pipeline works.

There's no EDMC install available in this repo, so most of `plugin/`'s modules can't be imported standalone — `config`, `theme`, `myNotebook`, and `companion` are all provided by EDMC at runtime, not installable packages. Every module can still be exercised outside EDMC by stubbing those in `sys.modules` and replaying real journal lines through the tracker; `overlay.py`'s rendering additionally needs a fake `edmcoverlay` module (an `Overlay` class recording `send_message`/`send_shape`/`send_raw` calls into a list a test can assert against). See the [Technical Specification](docs/tech-spec.md) for the module layout, journal event schemas, and the full EDMC plugin API surface this plugin uses — that's the place to look for *how* any of this works internally, rather than here.

**Auto-update is off by default, but can still overwrite a local test install if you've turned it on for that copy.** A plugin folder dropped into your EDMC plugins directory for testing looks, to `update.py`, exactly like a real install — if "Automatically download updates" is enabled there and the local build is older than the latest GitHub Release, EDMC will download and stage that release over your hand-edited files on its next restart. Drop an empty `disable-auto-update.txt` file in the plugin folder to override the checkbox unconditionally if you want it on elsewhere while still hand-editing this copy.

## Learn More

- [`docs/design-spec.md`](docs/design-spec.md) — user experience, requirements, and event flow.
- [`docs/tech-spec.md`](docs/tech-spec.md) — architecture, module layout, journal event schemas, and the full EDMC plugin API surface used.
- [`docs/ATTRIBUTIONS.md`](docs/ATTRIBUTIONS.md) — sources for journal event fields, suit capacity data, and third-party references (EDMC is not affiliated with this plugin; *Elite Dangerous* and all related marks are trademarks of Frontier Developments plc).
- [`CHANGELOG.md`](CHANGELOG.md) — release history.
- [`TODO.md`](TODO.md) — open backlog items and known issues still being researched.
