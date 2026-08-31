"""Loads the academic monograph dataset and indexes it for compound matching.

Monograph files live at data/<doc_number>.json (e.g. data/10.json), one list of
records per source formulary PDF. Only numeric-stem files are picked up, so
data/EDA_Names.json, data/EDA_Names_mapped.json and data/egyptian-drugs.json (the
commercial catalogue) are excluded automatically, and future doc files
(data/1.json .. data/9.json) are picked up with no code change once they exist.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

from agents.compound_mapper.compound_aliases import canonicalize

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

MATCHED_FIELDS = ("name", "generic_name", "abbreviation")


def _load_academic_records(data_dir: Path = DATA_DIR) -> List[dict]:
    records: List[dict] = []
    for path in sorted(data_dir.glob("*.json")):
        if not path.stem.isdigit():
            continue
        with path.open("r", encoding="utf-8") as f:
            records.extend(json.load(f))
    return records


class AcademicIndex:
    """Normalised lookup over name/generic_name/abbreviation for exact and fuzzy
    matching, plus the set of valid generic_name values used to reject a
    hallucinated mapping."""

    def __init__(self, records: List[dict]):
        self.records = records
        self.by_generic_name: Dict[str, dict] = {
            r["generic_name"]: r for r in records if r.get("generic_name")
        }
        self.valid_generic_names = set(self.by_generic_name.keys())

        self._exact: Dict[str, List[dict]] = {}
        self._fuzzy_universe: List[Tuple[str, dict]] = []
        seen_pairs = set()

        for record in records:
            for field in MATCHED_FIELDS:
                raw_value = record.get(field)
                if not raw_value:
                    continue
                key = canonicalize(raw_value)
                if not key:
                    continue

                record_id = record.get("id", id(record))
                pair = (key, record_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                self._exact.setdefault(key, []).append(record)
                self._fuzzy_universe.append((key, record))

    def exact(self, query: str) -> List[dict]:
        return self._exact.get(canonicalize(query), [])

    def fuzzy_candidates(
        self, query: str, limit: int = 8, score_cutoff: float = 40.0
    ) -> List[Tuple[dict, float]]:
        """Top `limit` unique records whose normalised name/generic_name/abbreviation
        is closest to `query`, each paired with its best score."""
        key = canonicalize(query)
        if not key or not self._fuzzy_universe:
            return []

        choices = [choice for choice, _ in self._fuzzy_universe]
        matches = process.extract(
            key, choices, scorer=fuzz.WRatio, limit=limit * 3, score_cutoff=score_cutoff
        )

        candidates: List[Tuple[dict, float]] = []
        seen_ids = set()
        for _choice, score, index in matches:
            record = self._fuzzy_universe[index][1]
            record_id = record.get("id", id(record))
            if record_id in seen_ids:
                continue
            seen_ids.add(record_id)
            candidates.append((record, score))
            if len(candidates) >= limit:
                break

        return candidates


def _build_index() -> AcademicIndex:
    return AcademicIndex(_load_academic_records())


ACADEMIC_INDEX = _build_index()
