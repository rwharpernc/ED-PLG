"""
ED-PLG entry point for Elite Dangerous Market Connector.

Tracks Odyssey on-foot microresources (components, items, data) in the suit
backpack, ship locker, and fleet carrier locker, logging pillage events as
loot is acquired.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import tkinter as tk

from companion import CAPIData
from config import appname

from . import __version__
from .inventory import CATEGORY_SHORT, InventoryTracker
from .overlay import PillageOverlay
from .sound import PillageSound
from .suit import SuitState
from .update import UpdateManager, check_applied_update
from . import names
from . import suit
from . import ui
from . import window

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

# Ship locker capacity warning: distinct from pillage lines, so it gets its
# own colour and a longer TTL — missing it can mean being forced to drop
# loot rather than just missing a pickup notification.
LOCKER_WARNING_COLOUR = "#ff3030"
LOCKER_WARNING_TTL = 20

if not logger.hasHandlers():
    level = logging.INFO
    logger.setLevel(level)
    logger_channel = logging.StreamHandler()
    logger_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "%(module)s:%(lineno)d:%(funcName)s: %(message)s",
    )
    logger_formatter.default_time_format = "%Y-%m-%d %H:%M:%S"
    logger_formatter.default_msec_format = "%s.%03d"
    logger_channel.setFormatter(logger_formatter)
    logger.addHandler(logger_channel)

_tracker = InventoryTracker()
_overlay = PillageOverlay()
_sound = PillageSound()
_suit = SuitState()
_ui_frame: Optional[tk.Frame] = None
_updater: Optional[UpdateManager] = None
"""Kept alive purely so the background check thread's bound method holds a
live reference for its lifetime - not read again after plugin_start3."""


def plugin_start3(plugin_dir: str) -> str:
    """Load ED-PLG into EDMarketConnector."""
    global _updater
    logger.info("ED-PLG v%s starting from %s", __version__, plugin_dir)
    names.load_learned_names()
    suit.load_overrides()
    _overlay.set_enabled(ui.overlay_enabled())
    _overlay.set_position(*ui.overlay_position())
    _sound.set_enabled(ui.sound_enabled())
    if not _overlay.available:
        logger.info("No overlay plugin found; pillage overlay disabled")

    applied_version = check_applied_update()
    if applied_version is not None:
        logger.info("ED-PLG updated to v%s", applied_version)
        ui.set_update_applied(applied_version)

    _updater = UpdateManager(plugin_dir, on_ready=_on_update_ready, on_downloading=_on_update_downloading)
    _updater.check_async()

    return "ED-PLG"


def _on_update_downloading(version: str) -> None:
    # Called from the update-check background thread - marshal onto the Tk
    # main thread before touching any widgets.
    ui.run_on_main_thread(lambda: ui.set_update_downloading(version))


def _on_update_ready(version: str) -> None:
    # Called from the update-check background thread - marshal onto the Tk
    # main thread before touching any widgets.
    ui.run_on_main_thread(lambda: ui.set_update_downloaded(version))


def plugin_stop() -> None:
    """EDMarketConnector is closing."""
    names.save_learned_names()
    suit.save_overrides()
    _overlay.clear()
    window.close()
    logger.info("ED-PLG shutting down")


def plugin_app(parent: tk.Frame) -> tk.Frame:
    """Create ED-PLG widgets on the EDMC main window."""
    global _ui_frame
    _ui_frame = ui.create_plugin_app(parent, _show_inventory)
    return _ui_frame


def _show_inventory() -> None:
    if _ui_frame is not None:
        window.show(_ui_frame, _tracker, _suit)


def plugin_prefs(parent, cmdr: str, is_beta: bool):
    """Create the ED-PLG settings tab."""
    return ui.create_prefs(parent, _overlay.available, _sound.available, cmdr)


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """Settings were saved."""
    _overlay.set_enabled(ui.save_prefs(cmdr))
    _overlay.set_position(*ui.overlay_position())
    _sound.set_enabled(ui.sound_enabled())


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str,
    station: str,
    entry: Dict[str, Any],
    state: Dict[str, Any],
) -> Optional[str]:
    """Handle journal events for Odyssey inventory tracking."""
    try:
        return _dispatch(cmdr, entry, state)
    finally:
        # No-op unless the inventory window is open.
        window.refresh()


def _dispatch(
    cmdr: str,
    entry: Dict[str, Any],
    state: Dict[str, Any],
) -> Optional[str]:
    event = entry.get("event", "")

    if event in ("LoadGame", "Start"):
        _on_commander_session(cmdr, state, reason=event)
        return None

    if event in ("Backpack", "Resupply"):
        _tracker.apply_backpack_baseline(entry)
        _tracker.sync_backpack_from_state(state)
        logger.debug("Backpack baseline synced (%s)", event)
        ui.set_status("Backpack synced")
        return None

    if event == "ShipLocker":
        _tracker.apply_ship_locker_baseline(entry)
        _tracker.sync_ship_locker_from_state(state)
        logger.debug("Ship locker baseline synced")
        ui.set_status("Ship locker synced")
        _warn_ship_locker_capacity()
        return None

    if event in ("SuitLoadout", "SwitchSuitLoadout"):
        # Disembarking / starting on foot / changing loadout: the suit determines
        # backpack capacity, so record it alongside the backpack contents.
        _suit.apply_suit_loadout(entry, cmdr=cmdr)
        _tracker.sync_backpack_from_state(state)
        logger.debug(
            "Suit set to %s; backpack synced (%s)",
            _suit.display_name,
            event,
        )
        return None

    if event == "BackpackChange":
        return _handle_backpack_change(entry, state)

    if event == "CarrierDecommission":
        _tracker.clear_fleet_carrier_for_commander(cmdr)
        logger.info("Fleet carrier locker cleared for %s (decommission)", cmdr)
        ui.set_status(f"Carrier decommissioned ({cmdr})")
        return None

    return None


def capi_fleetcarrier(data: CAPIData) -> Optional[str]:
    """
    Receive fleet carrier CAPI data from EDMC (requires Frontier auth).

    EDMC fetches /fleetcarrier on CarrierBuy/CarrierStats (15 min throttle).
    Carrier locker data may lag the live game by 15–30 minutes.
    """
    request_cmdr = getattr(data, "request_cmdr", None)
    if not request_cmdr:
        logger.debug("Fleet carrier CAPI ignored: missing request_cmdr")
        return None

    callsign = _carrier_callsign(data)
    carrier_locker = data.get("carrierLocker")

    if not isinstance(carrier_locker, dict):
        _tracker.clear_fleet_carrier_for_commander(request_cmdr)
        logger.debug(
            "Fleet carrier CAPI has no locker for %s (callsign=%s)",
            request_cmdr,
            callsign,
        )
        if request_cmdr == _tracker.commander:
            ui.set_status(f"No carrier locker ({request_cmdr})")
        return None

    stack_count = _tracker.apply_fleet_carrier_locker(
        carrier_locker,
        callsign=callsign,
        cmdr=request_cmdr,
    )
    label = callsign or "carrier"

    if request_cmdr != _tracker.commander:
        logger.info(
            "Fleet carrier locker cached for %s (%s, %d stacks); active CMDR is %s",
            request_cmdr,
            label,
            stack_count,
            _tracker.commander,
        )
        return None

    logger.info(
        "Fleet carrier locker synced from CAPI (%s / %s): %d stack(s)",
        request_cmdr,
        label,
        stack_count,
    )
    ui.set_status(f"Carrier locker synced ({label}, {stack_count} stacks)")
    return None


def _on_commander_session(cmdr: str, state: Dict[str, Any], *, reason: str) -> None:
    switched = _tracker.set_commander(cmdr)
    _tracker.sync_all_from_state(state)
    _warn_ship_locker_capacity()

    # EDMC only (re)populates the backpack from a fresh Backpack/Resupply event,
    # and clears it on LoadGame. A commander already on foot when EDMC attaches
    # may not get one of those for a while, so say so rather than presenting the
    # zeroed-out backpack as a confirmed empty one.
    pending_note = (
        "" if _tracker.backpack_baseline_seen else " (backpack pending first sync)"
    )

    if switched:
        logger.info(
            "Commander switched to %s; journal inventory synced (%s)",
            cmdr,
            reason,
        )
        if _tracker.fleet_carrier_callsign:
            ui.set_status(
                f"{cmdr}: inventory synced "
                f"(carrier {_tracker.fleet_carrier_callsign} cached){pending_note}",
            )
        else:
            ui.set_status(f"{cmdr}: inventory synced (no carrier data yet){pending_note}")
    else:
        logger.info("Inventory baseline synced from EDMC state (%s)", reason)
        ui.set_status(f"Inventory synced{pending_note}")


def _warn_ship_locker_capacity() -> None:
    """
    Warn (log + overlay) for any ship locker category that just crossed
    InventoryTracker.WARNING_THRESHOLD of its capacity.

    Ship locker updates the same way whether a commander transfers items at
    their own ship or remotely via an Apex shuttle's "Manage Items" screen —
    both write through the same ShipLocker journal event this is called
    from — so no separate Apex-specific handling is needed.
    """
    announced_categories = ui.announced_categories()
    for category, total, capacity in _tracker.ship_locker_capacity_warnings():
        if category not in announced_categories:
            continue
        label = CATEGORY_SHORT[category]
        message = f"⚠ Ship Locker {label}: {total}/{capacity} — nearing capacity"
        logger.warning(message)
        _overlay.notify(
            f"__locker_full_{category}",
            message,
            colour=LOCKER_WARNING_COLOUR,
            ttl=LOCKER_WARNING_TTL,
        )


def _handle_backpack_change(
    entry: Dict[str, Any],
    state: Dict[str, Any],
) -> Optional[str]:
    pillage_messages = []
    announced_categories = ui.announced_categories()

    for label, internal_name, category, delta, _backpack_total in _tracker.apply_backpack_change(entry):
        # Counts are always tracked regardless of the announce-category prefs
        # (see ui.announced_categories) - only the pillage notification (log
        # line, overlay, panel) for a muted category is suppressed here.
        if category not in announced_categories:
            continue

        combined_total = _tracker.get_combined_total(internal_name, category)
        message = ui.format_pillage_message(label, combined_total)
        logger.info(message)
        pillage_messages.append(message)
        _overlay.notify(internal_name, f"+{delta}  {label}: {combined_total}")

    # Reconcile with EDMC state after processing journal deltas.
    _tracker.sync_backpack_from_state(state)

    if pillage_messages:
        _sound.play()
        ui.set_last_event(pillage_messages[-1])
        ui.set_status(f"+{len(pillage_messages)} item(s) pillaged")
        return pillage_messages[-1]

    return None


def _carrier_callsign(data: CAPIData) -> Optional[str]:
    name_block = data.get("name")
    if isinstance(name_block, dict):
        callsign = name_block.get("callsign")
        if isinstance(callsign, str) and callsign:
            return callsign
    return None
