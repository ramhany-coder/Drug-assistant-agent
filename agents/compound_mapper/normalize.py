"""Pure string normalisation for compound matching. No I/O, no matching logic —
just the deterministic transform that lets a raw commercial-catalogue token and
a raw academic-record field land on the same string when they name the same
molecule.

normalize_compound always runs the full pipeline, including salt stripping —
so an index built by normalizing academic-record fields and a query normalized
the same way already meet on salt-stripped ground. That is why the matching
cascade in scripts/build_compound_map.py has no separate "strip salts on the
index side" step: it would just repeat this function's step 6 on data that
already went through it.
"""

import re
from typing import List, Optional

from agents.compound_mapper.compound_aliases import ALIASES, SALT_SUFFIXES, UNITS

_PAREN_RE = re.compile(r"\(([^)]*)\)")
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9\s-]")

_UNITS_PATTERN = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
_STRENGTH_RE = re.compile(
    rf"\s+\d+(?:\.\d+)?\s*(?:{_UNITS_PATTERN})?\.?\s*$", re.IGNORECASE
)


def _apply_aliases(text: str) -> str:
    text = ALIASES.get(text, text)
    tokens = [ALIASES.get(token, token) for token in text.split(" ")]
    return " ".join(tokens)


def _strip_salts(text: str) -> str:
    tokens = text.split(" ")
    while len(tokens) > 1 and tokens[-1] in SALT_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_compound(s: Optional[str]) -> str:
    """Lowercase -> drop parenthetical content -> strip trailing strength ->
    strip punctuation -> apply aliases -> strip trailing salt/hydrate suffix
    (repeated) -> collapse whitespace. Pure and side-effect free."""
    if not s:
        return ""

    text = _WHITESPACE_RE.sub(" ", s.strip().lower())
    text = _WHITESPACE_RE.sub(" ", _PAREN_RE.sub(" ", text)).strip()
    text = _STRENGTH_RE.sub("", text).strip()
    text = _WHITESPACE_RE.sub(" ", _PUNCT_RE.sub("", text)).strip()
    text = _apply_aliases(text)
    text = _strip_salts(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def extract_parenthetical(s: Optional[str]) -> Optional[str]:
    """The text inside the first '(...)' group, e.g. "ACETAMINOPHEN" out of
    "PARACETAMOL(ACETAMINOPHEN)" — the second candidate string normalize_compound's
    docstring refers to. None if there is no parenthetical."""
    if not s:
        return None
    match = _PAREN_RE.search(s)
    return match.group(1).strip() or None if match else None


def split_scientific_name(s: Optional[str]) -> List[str]:
    """Split on '+', trim each part, drop empties, deduplicate preserving order.
    Returns the raw components as they appear — normalisation happens per
    component afterwards, at matching time."""
    if not s:
        return []

    seen = set()
    components: List[str] = []
    for raw_part in s.split("+"):
        part = raw_part.strip()
        if not part or part in seen:
            continue
        seen.add(part)
        components.append(part)

    return components
