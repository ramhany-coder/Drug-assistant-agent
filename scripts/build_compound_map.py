"""Offline build for the compound map. Run once per data update:

    python scripts/build_compound_map.py

Computes, once, the mapping from every raw ingredient string the commercial
catalogue uses to the academic dataset's generic_name, and writes it to
data/generated/. Runtime (agents/compound_mapper/compound_map.py) only ever
reads that artefact — it never re-runs this cascade.

THE MATCHING CASCADE, per distinct component, first hit wins:
  1. exact match of the normalised component against the normalised index
  2. exact match of the parenthetical alternative (e.g. "ACETAMINOPHEN" out of
     "PARACETAMOL(ACETAMINOPHEN)")
  3. fuzzy (rapidfuzz.fuzz.ratio) — candidate only, never auto-accepted; a
     score >= 97 goes to review_queue.json, not the map.

The index is built by normalize_compound over name/generic_name/abbreviation,
which already salt-strips both sides identically, so there is no separate
"strip salts on the index side" step — normalize_compound is the only place
that happens, for both the query and the index. Combination records (name
contains '+') are skipped entirely: they must never resolve a single-ingredient
component, whether via exact or fuzzy match.
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rapidfuzz import fuzz, process

from agents.compound_mapper.academic_index import load_academic_records
from agents.compound_mapper.normalize import (
    extract_parenthetical,
    normalize_compound,
    split_scientific_name,
)
COMMERCIAL_PATH = ROOT / "data" / "egyptian-drugs.json"
OUT_DIR = ROOT / "data" / "generated"

FUZZY_REVIEW_SCORE = 97


def build_match_index(records: List[dict]) -> Dict[str, dict]:
    """normalize_compound(field) -> record, over name/generic_name/abbreviation.
    Skips combination records (name contains '+') so a single ingredient can
    never resolve to a multi-ingredient record."""
    index: Dict[str, dict] = {}
    for record in records:
        name = record.get("name") or ""
        if "+" in name:
            continue
        for field in ("name", "generic_name", "abbreviation"):
            raw = record.get(field)
            if not raw:
                continue
            key = normalize_compound(raw)
            if not key or key in index:
                continue
            index[key] = record
    return index


def resolve_component(
    raw_component: str, index: Dict[str, dict], fuzzy_keys: List[str]
) -> Tuple[str, Optional[dict], Optional[float]]:
    """Returns (status, record, score). status is one of "mapped" (exact or
    parenthetical hit), "review" (fuzzy candidate >= FUZZY_REVIEW_SCORE), or
    "unmapped" (nothing cleared the bar)."""
    base = normalize_compound(raw_component)
    if base and base in index:
        return "mapped", index[base], None

    alt = extract_parenthetical(raw_component)
    if alt:
        alt_key = normalize_compound(alt)
        if alt_key and alt_key in index:
            return "mapped", index[alt_key], None

    if not base or not fuzzy_keys:
        return "unmapped", None, None

    match = process.extractOne(
        base, fuzzy_keys, scorer=fuzz.ratio, score_cutoff=FUZZY_REVIEW_SCORE
    )
    if match is None:
        return "unmapped", None, None

    matched_key, score, _ = match
    return "review", index[matched_key], score


def load_commercial_scientific_names(path: Path = COMMERCIAL_PATH) -> List[Optional[str]]:
    with path.open("r", encoding="utf-8") as f:
        products = json.load(f)
    return [p.get("scientific_name") for p in products]


def build() -> None:
    academic_records = load_academic_records()
    index = build_match_index(academic_records)
    fuzzy_keys = list(index.keys())

    scientific_names = load_commercial_scientific_names()

    component_product_counts: Counter = Counter()
    product_components: List[List[str]] = []
    for scientific_name in scientific_names:
        components = split_scientific_name(scientific_name)
        if not components:
            continue
        product_components.append(components)
        for component in components:
            component_product_counts[component] += 1

    compound_map: Dict[str, str] = {}
    review_queue: List[dict] = []
    unmapped: Dict[str, int] = {}

    for component, count in component_product_counts.items():
        status, record, score = resolve_component(component, index, fuzzy_keys)
        if status == "mapped":
            compound_map[component] = record["generic_name"]
        elif status == "review":
            review_queue.append(
                {
                    "component": component,
                    "candidate_generic_name": record["generic_name"],
                    "score": score,
                    "product_count": count,
                }
            )
        else:
            unmapped[component] = count

    unmapped_report = [
        {"component": component, "product_count": count}
        for component, count in sorted(unmapped.items(), key=lambda kv: kv[1], reverse=True)
    ]
    review_queue.sort(key=lambda entry: entry["product_count"], reverse=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "compound_map.json").open("w", encoding="utf-8") as f:
        json.dump(compound_map, f, ensure_ascii=False, indent=2, sort_keys=True)
    with (OUT_DIR / "unmapped_report.json").open("w", encoding="utf-8") as f:
        json.dump(unmapped_report, f, ensure_ascii=False, indent=2)
    with (OUT_DIR / "review_queue.json").open("w", encoding="utf-8") as f:
        json.dump(review_queue, f, ensure_ascii=False, indent=2)

    total_distinct = len(component_product_counts)
    fully_mapped_products = sum(
        1 for components in product_components if all(c in compound_map for c in components)
    )
    partially_mapped_products = sum(
        1
        for components in product_components
        if any(c in compound_map for c in components)
        and not all(c in compound_map for c in components)
    )
    total_products = len(product_components)

    print(f"distinct components: {total_distinct}")
    print(f"  mapped:   {len(compound_map)}")
    print(f"  unmapped: {len(unmapped_report)}")
    print(f"  in review: {len(review_queue)}")
    if total_products:
        print(
            f"products fully mapped: {fully_mapped_products}/{total_products} "
            f"({fully_mapped_products / total_products:.1%})"
        )
        print(
            f"products partially mapped: {partially_mapped_products}/{total_products} "
            f"({partially_mapped_products / total_products:.1%})"
        )


if __name__ == "__main__":
    build()
