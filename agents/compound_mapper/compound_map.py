"""Runtime compound lookup. Pure dict reads against the build artefact at
data/generated/compound_map.json — no normalisation, no fuzzy, no fallback.
If a component isn't in the map, it is unmapped; that is a real answer, not a
prompt to guess. Rebuild the artefact (scripts/build_compound_map.py) to pick
up new academic data or alias-table edits.
"""

import json
from pathlib import Path
from typing import List, Optional, TypedDict

from agents.compound_mapper.normalize import split_scientific_name

MAP_PATH = Path(__file__).resolve().parents[2] / "data" / "generated" / "compound_map.json"


class MappedComponent(TypedDict):
    component: str
    generic_name: Optional[str]
    matched: bool


def _load_compound_map() -> dict:
    if not MAP_PATH.exists():
        return {}
    with MAP_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


COMPOUND_MAP = _load_compound_map()


def get_generic_names(scientific_name: Optional[str]) -> List[MappedComponent]:
    """One entry per component of scientific_name, in order. Unmapped components
    carry generic_name=None, matched=False rather than being dropped, so a
    caller can say which ingredient it has no information on."""
    return [
        {
            "component": component,
            "generic_name": COMPOUND_MAP.get(component),
            "matched": component in COMPOUND_MAP,
        }
        for component in split_scientific_name(scientific_name)
    ]
