"""Map Frontier internal microresource IDs to human-readable display names."""

from __future__ import annotations

from typing import Dict, Optional

# Upgrade-relevant Odyssey microresources (Component, Item, Data).
# Extend this dict as new resources are discovered in-game.
# Keys are canonicalised (lowercase, no spaces) Frontier internal names.
DISPLAY_NAMES: Dict[str, str] = {
    # Components
    "weaponcomponent": "Weapon Component",
    "healthmonitor": "Health Monitor",
    "powerconverter": "Power Converter",
    "powerregulator": "Power Regulator",
    "largecapacitypowerregulator": "Power Regulator",
    "oxygenicbacteria": "Oxygenic Bacteria",
    "epinephrine": "Epinephrine",
    "carbonfibreplating": "Carbon Fibre Plating",
    "graphene": "Graphene",
    "microelectrode": "Micro Electrode",
    "opticalfibre": "Optical Fibre",
    "ionisedgas": "Ionised Gas",
    "epoxyadhesive": "Epoxy Adhesive",
    "rdx": "RDX",
    "metalcoil": "Metal Coil",
    "microsupercapacitor": "Micro Supercapacitor",
    "microthrusters": "Micro Thrusters",
    "microswarmmissiles": "Micro Swarm Missiles",
    "microhydraulics": "Micro Hydraulics",
    "microthermalcooler": "Micro Thermal Cooler",
    "microtransmitter": "Micro Transmitter",
    "microweavefiltering": "Micro Weave Filtering",
    "thermalcoolingunits": "Thermal Cooling Units",
    "viscoelasticpolymer": "Viscoelastic Polymer",
    # Items
    "suitschematic": "Suit Schematic",
    "weaponschematic": "Weapon Schematic",
    "settlementdefenceplans": "Settlement Defence Plans",
    "reactivearmour": "Reactive Armour",
    "stabilisingcompound": "Stabilising Compound",
    "energyconverter": "Energy Converter",
    "electromagneticcoil": "Electromagnetic Coil",
    "memorychip": "Memory Chip",
    "personalcomputer": "Personal Computer",
    "datamaterial": "Data Material",
    # Data
    "manufacturinginstructions": "Manufacturing Instructions",
    "biologicaldata": "Biological Data",
    "weaponexperimentals": "Weapon Experimentals",
    "weaponblueprint": "Weapon Blueprint",
    "suitblueprint": "Suit Blueprint",
    "weaponinstructions": "Weapon Instructions",
    "suitinstructions": "Suit Instructions",
    "settlementprospects": "Settlement Prospects",
    "settlementplans": "Settlement Plans",
    "geneticrepairmeds": "Genetic Repair Meds",
    "combatantperformance": "Combatant Performance",
    "compositionalanalysis": "Compositional Analysis",
    "networkarchitecture": "Network Architecture",
    "networksecurity": "Network Security",
    "reactoroutputreview": "Reactor Output Review",
    "reactorbalancingreport": "Reactor Balancing Report",
    "radiationreport": "Radiation Report",
    "spectralanalysisdata": "Spectral Analysis Data",
}


# Display names learned from Name_Localised at runtime, for resources not listed
# in DISPLAY_NAMES. Rebuilt each session from the journal.
_LEARNED_NAMES: Dict[str, str] = {}


def canonicalise(name: str) -> str:
    """Match EDMC's canonicalisation: lowercase with no spaces."""
    return name.lower().replace(" ", "")


def remember(internal_name: str, localised_name: Optional[str]) -> None:
    """
    Learn a display name the journal told us about.

    Backpack / ShipLocker / BackpackChange entries carry Name_Localised for any
    resource whose display name differs from its internal ID, so the game itself
    supplies names for resources missing from DISPLAY_NAMES. Frontier's
    unresolved "$Token;" placeholders are ignored.
    """
    if not localised_name:
        return

    key = canonicalise(internal_name)
    label = localised_name.strip()
    if not key or not label or label.startswith("$"):
        return

    _LEARNED_NAMES[key] = label


def display_name(
    internal_name: str,
    localised_name: Optional[str] = None,
) -> str:
    """
    Resolve a journal item name to a human-readable label.

    Prefers the journal's Name_Localised when present, then our mapping, then a
    name learned from an earlier journal entry, then a title-cased fallback
    derived from the internal ID.
    """
    if localised_name:
        return localised_name

    key = canonicalise(internal_name)
    if key in DISPLAY_NAMES:
        return DISPLAY_NAMES[key]
    if key in _LEARNED_NAMES:
        return _LEARNED_NAMES[key]

    # Fallback: split camelCase-ish internal IDs into words.
    return internal_name.replace("_", " ").title()
