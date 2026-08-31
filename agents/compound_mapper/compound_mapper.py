from typing import List, Optional, Tuple

from agents.compound_mapper.compound_map import get_generic_names
from agents.compound_mapper.unmapped_log import log_unmapped


def _scientific_names_to_map(state) -> List[Tuple[str, Optional[str]]]:
    """Return (scientific_name, source_product) pairs to map: the extractor's direct
    scientific_name on the direct path, or the deduplicated scientific_name values off
    the matched commercial rows on the retrieval path. A scientific_name repeated
    across several rows is mapped once, attributed to the first row it appeared on."""
    direct = state.get("scientific_name")
    if direct:
        return [(direct, None)]

    pairs: List[Tuple[str, Optional[str]]] = []
    seen = set()
    for row in state.get("context") or []:
        scientific_name = row.get("scientific_name")
        if not scientific_name or scientific_name in seen:
            continue
        seen.add(scientific_name)
        pairs.append((scientific_name, row.get("commercial_name_en")))

    return pairs


def compound_mapper(state):
    """Pure dict-lookup mapping (see compound_map.get_generic_names) — no LLM, no
    fuzzy matching at runtime. A component absent from the build artefact is
    reported as unmatched rather than guessed at, and logged so
    logs/unmapped_compounds.jsonl can drive the next data update."""
    scientific_name_sources = _scientific_names_to_map(state)
    if not scientific_name_sources:
        return {"compound_mappings": []}

    mappings = []
    for scientific_name, source_product in scientific_name_sources:
        for entry in get_generic_names(scientific_name):
            if not entry["matched"]:
                log_unmapped(entry["component"], source_product)
            mappings.append(
                {
                    "component": entry["component"],
                    "generic_name": entry["generic_name"],
                    "matched": entry["matched"],
                    "source_product": source_product,
                }
            )

    return {"compound_mappings": mappings}
