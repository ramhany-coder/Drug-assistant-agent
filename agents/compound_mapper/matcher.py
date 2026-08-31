"""Deterministic component splitting and matching. The LLM only ever sees what
survives this pipeline — see compound_mapper.py for how the residue is handed off."""

import re
from typing import List, Optional, TypedDict

from agents.compound_mapper.academic_index import ACADEMIC_INDEX

FUZZY_ACCEPT_SCORE = 92
CANDIDATE_LIMIT = 8

_PAREN_RE = re.compile(r"\(([^)]*)\)")
_STRENGTH_RE = re.compile(
    r"\s+[\d.]+\s*(MG|MCG|G|GM|ML|IU|%|GRAMS?|MEQ)S?\.?\s*$", re.IGNORECASE
)
_WHITESPACE_RE = re.compile(r"\s+")


class ComponentInfo(TypedDict):
    component: str
    query_terms: List[str]


class MatchOutcome(TypedDict):
    component: str
    matched: Optional[bool]  # None = unresolved, needs the LLM
    generic_name: Optional[str]
    candidates: List[dict]


def split_components(scientific_name: Optional[str]) -> List[ComponentInfo]:
    """Split on '+', strip trailing strengths, and pull out a parenthetical alias
    (e.g. "PARACETAMOL(ACETAMINOPHEN)") as an extra query term without keeping it in
    the displayed component label."""
    if not scientific_name:
        return []

    parsed: List[ComponentInfo] = []
    for raw_part in scientific_name.split("+"):
        part = raw_part.strip()
        if not part:
            continue

        alias_match = _PAREN_RE.search(part)
        alias_term = alias_match.group(1).strip() if alias_match else None

        base = _PAREN_RE.sub("", part).strip()
        base = _STRENGTH_RE.sub("", base).strip()
        base = _WHITESPACE_RE.sub(" ", base)
        if not base:
            continue

        query_terms = [base]
        if alias_term:
            query_terms.append(alias_term)

        parsed.append({"component": base, "query_terms": query_terms})

    return parsed


def match_component(component_info: ComponentInfo) -> MatchOutcome:
    """Exact match, then fuzzy match at a high-confidence threshold, then hand back
    an unresolved outcome carrying candidates for the LLM to choose from."""
    component = component_info["component"]

    for term in component_info["query_terms"]:
        exact = ACADEMIC_INDEX.exact(term)
        if len(exact) == 1:
            return {
                "component": component,
                "matched": True,
                "generic_name": exact[0]["generic_name"],
                "candidates": [],
            }
        if len(exact) > 1:
            # Ambiguous exact match (e.g. a combination record shares a name token) —
            # let the LLM disambiguate using the candidate set below.
            break

    seen_ids = set()
    candidates: List[tuple] = []
    for term in component_info["query_terms"]:
        for record, score in ACADEMIC_INDEX.fuzzy_candidates(term, limit=CANDIDATE_LIMIT):
            record_id = record.get("id", id(record))
            if record_id in seen_ids:
                continue
            seen_ids.add(record_id)
            candidates.append((record, score))

    candidates.sort(key=lambda pair: pair[1], reverse=True)

    if candidates and candidates[0][1] >= FUZZY_ACCEPT_SCORE:
        top_score = candidates[0][1]
        top_matches = [record for record, score in candidates if score == top_score]
        if len(top_matches) == 1:
            return {
                "component": component,
                "matched": True,
                "generic_name": top_matches[0]["generic_name"],
                "candidates": [],
            }

    if not candidates:
        return {
            "component": component,
            "matched": False,
            "generic_name": None,
            "candidates": [],
        }

    return {
        "component": component,
        "matched": None,
        "generic_name": None,
        "candidates": [record for record, _score in candidates[:CANDIDATE_LIMIT]],
    }
