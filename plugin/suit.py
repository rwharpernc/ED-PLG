"""Current suit tracking and backpack capacity.

The journal never reports backpack capacity, so it is hardcoded here per suit
type and looked up from the SuitName / SuitMods fields of SuitLoadout and
SwitchSuitLoadout. In-game the categories are called Goods (journal: Item),
Assets (journal: Component) and Data.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

# Suit mod that raises backpack capacity ("Extra Backpack Capacity").
BACKPACK_CAPACITY_MOD = "suit_backpackcapacity"

SUIT_DISPLAY_NAMES: Dict[str, str] = {
    "explorationsuit": "Artemis Suit",
    "tacticalsuit": "Dominator Suit",
    "utilitysuit": "Maverick Suit",
    "flightsuit": "Flight Suit",
}

# Backpack capacity per suit type, by journal category.
# "base" = unmodified, "modded" = suit_backpackcapacity fitted.
# None means the capacity is unknown; the UI then shows a plain count with no
# limit rather than guessing.
CapacityMap = Dict[str, int]
SuitCapacities = Dict[str, CapacityMap]

CAPACITIES: Dict[str, Optional[SuitCapacities]] = {
    # Maverick
    "utilitysuit": {
        "base": {"Item": 40, "Component": 60, "Data": 10},
        "modded": {"Item": 80, "Component": 120, "Data": 40},
    },
    # Artemis
    "explorationsuit": {
        "base": {"Item": 20, "Component": 40, "Data": 10},
        "modded": {"Item": 40, "Component": 80, "Data": 20},
    },
    # Dominator
    "tacticalsuit": {
        "base": {"Item": 10, "Component": 20, "Data": 10},
        "modded": {"Item": 20, "Component": 40, "Data": 20},
    },
    "flightsuit": None,
}


class SuitState:
    """Tracks the suit the commander is currently wearing."""

    def __init__(self) -> None:
        self._suit_key: Optional[str] = None
        self._localised: Optional[str] = None
        self._grade: Optional[int] = None
        self._mods: tuple = ()

    @property
    def known(self) -> bool:
        return self._suit_key is not None

    @property
    def has_capacity_mod(self) -> bool:
        return BACKPACK_CAPACITY_MOD in self._mods

    @property
    def display_name(self) -> str:
        if self._suit_key is None:
            return "No suit data yet"

        name = SUIT_DISPLAY_NAMES.get(self._suit_key, self._suit_key)
        if self._grade:
            name = f"{name} (Grade {self._grade})"
        if self.has_capacity_mod:
            name = f"{name} + Extra Backpack Capacity"
        return name

    def apply_suit_loadout(self, entry: Mapping[str, Any]) -> None:
        """Read SuitName / SuitMods from a SuitLoadout or SwitchSuitLoadout event."""
        suit_name = str(entry.get("SuitName", "")).lower()
        if not suit_name:
            return

        self._suit_key, self._grade = _split_suit_name(suit_name)
        mods = entry.get("SuitMods", [])
        self._mods = tuple(str(mod).lower() for mod in mods) if isinstance(mods, list) else ()

    def capacities(self) -> CapacityMap:
        """Backpack capacity per category; missing keys mean unknown."""
        if self._suit_key is None:
            return {}

        table = CAPACITIES.get(self._suit_key)
        if table is None:
            return {}

        return dict(table["modded"] if self.has_capacity_mod else table["base"])


def _split_suit_name(suit_name: str) -> tuple:
    """"explorationsuit_class3" -> ("explorationsuit", 3)."""
    key, _, suffix = suit_name.partition("_class")
    try:
        grade = int(suffix) if suffix else None
    except ValueError:
        grade = None
    return key, grade
