"""Loads the academic monograph dataset.

Monograph files live at data/<doc_number>.json (e.g. data/10.json), one list of
records per source formulary PDF. Only numeric-stem files are picked up, so
data/EDA_Names.json, data/EDA_Names_mapped.json and data/egyptian-drugs.json (the
commercial catalogue) are excluded automatically, and future doc files
(data/1.json .. data/9.json) are picked up with no code change once they exist.

This module only loads and indexes by generic_name — it does no matching.
scripts/build_compound_map.py does its own normalised indexing (over
name/generic_name/abbreviation, via normalize_compound) for the build-time
matching cascade; that index is a build-time concern and doesn't belong here.
"""

import json
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_academic_records(data_dir: Path = DATA_DIR) -> List[dict]:
    records: List[dict] = []
    for path in sorted(data_dir.glob("*.json")):
        if not path.stem.isdigit():
            continue
        with path.open("r", encoding="utf-8") as f:
            records.extend(json.load(f))
    return records


class AcademicIndex:
    """Records indexed by generic_name, plus the set of valid generic_name values —
    used by retrieve_academic to attach a monograph to each resolved compound
    mapping, and by the build script to assert every mapped value is real."""

    def __init__(self, records: List[dict]):
        self.records = records
        self.by_generic_name: Dict[str, dict] = {
            r["generic_name"]: r for r in records if r.get("generic_name")
        }
        self.valid_generic_names = set(self.by_generic_name.keys())


def _build_index() -> AcademicIndex:
    return AcademicIndex(load_academic_records())


ACADEMIC_INDEX = _build_index()
