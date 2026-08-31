"""Editable data tables for normalising compound names before matching.

These are plain data, not logic — see normalize.py for the pipeline that
consumes them. The gap log in logs/unmapped_compounds.jsonl and
data/generated/review_queue.json are the work queues for extending these
tables; an accepted review_queue entry becomes an ALIASES line here, then the
map is rebuilt (never hand-edited).
"""

SALT_SUFFIXES = {
    "sulphate", "sulfate", "hydrochloride", "hcl", "sodium", "potassium",
    "calcium", "magnesium", "maleate", "besylate", "mesylate", "tartrate",
    "fumarate", "citrate", "acetate", "phosphate", "succinate", "nitrate",
    "bromide", "chloride", "dihydrate", "trihydrate", "monohydrate",
    "anhydrous", "micronized",
}

UNITS = {"mg", "g", "gm", "mcg", "ug", "ml", "iu", "meq", "%"}

# applied to BOTH sides (academic index fields and commercial components)
# after lowercasing, whole-string first, then token-wise — see normalize.py
ALIASES = {
    "acetaminophen": "paracetamol", "albuterol": "salbutamol",
    "epinephrine": "adrenaline", "norepinephrine": "noradrenaline",
    "rifampin": "rifampicin", "cyclosporine": "ciclosporin",
    "glyburide": "glibenclamide", "lidocaine": "lignocaine",
    "furosemide": "frusemide", "amoxycillin": "amoxicillin",
    "cefalexin": "cephalexin",
    "vitamin c": "ascorbic acid", "vitamin b1": "thiamine",
    "vitamin b2": "riboflavin", "vitamin b6": "pyridoxine",
    "vitamin b12": "cyanocobalamin", "vitamin a": "retinol",
    "vitamin d": "cholecalciferol", "vitamin d3": "cholecalciferol",
    "vitamin e": "tocopherol", "vitamin k": "phytomenadione",
}
