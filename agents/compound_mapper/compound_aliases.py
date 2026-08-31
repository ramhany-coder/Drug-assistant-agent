"""Editable data tables for normalising compound names before matching.

Both tables are plain data, not logic, so the gap log in
logs/unmapped_compounds.jsonl can be used to extend them without touching the
matching pipeline in matcher.py.
"""

import re

SALT_SUFFIXES = {
    "sulphate", "sulfate", "hydrochloride", "hcl", "sodium", "potassium",
    "calcium", "maleate", "besylate", "mesylate", "tartrate", "fumarate",
    "citrate", "acetate", "phosphate", "succinate", "dihydrate",
    "trihydrate", "monohydrate", "anhydrous",
}

# normalise both sides through this before comparing
ALIASES = {
    "acetaminophen": "paracetamol", "albuterol": "salbutamol",
    "epinephrine": "adrenaline", "rifampin": "rifampicin",
    "cyclosporine": "ciclosporin", "glyburide": "glibenclamide",
    "lidocaine": "lignocaine", "furosemide": "frusemide",
    "vitamin c": "ascorbic acid", "vitamin b12": "cyanocobalamin",
    "vitamin b1": "thiamine", "vitamin b6": "pyridoxine",
    "vitamin d3": "cholecalciferol", "vitamin a": "retinol",
}

_WHITESPACE_RE = re.compile(r"\s+")


def canonicalize(text: str) -> str:
    """Lowercase, collapse whitespace, apply ALIASES, strip a trailing salt/hydrate
    suffix, then re-apply ALIASES — so the same function, run on a query token and on
    every index field, lands both sides on the same string regardless of which one
    carried the salt form or the alternate spelling."""
    if not text:
        return ""

    normalized = _WHITESPACE_RE.sub(" ", text.strip().lower())
    normalized = ALIASES.get(normalized, normalized)

    tokens = normalized.split(" ")
    while len(tokens) > 1 and tokens[-1] in SALT_SUFFIXES:
        tokens.pop()
    stripped = " ".join(tokens)
    stripped = ALIASES.get(stripped, stripped)

    return stripped
