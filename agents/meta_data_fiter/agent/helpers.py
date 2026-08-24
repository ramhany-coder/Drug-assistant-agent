import json
import re
from pathlib import Path
DRUG_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "egyptian-drugs.json"


def _tokenize(value):
    if value is None:
        return set()
    return {token.upper() for token in re.findall(r"\w+", str(value))}


def _matches_price(expression, price):
    if price is None:
        return False
    expression = expression.strip().lower()
    if expression in ("asc", "desc"):
        return True

    bound_match = re.fullmatch(r"(<|>)(\d+(?:\.\d+)?)", expression)
    if bound_match:
        op, bound = bound_match.group(1), float(bound_match.group(2))
        return price < bound if op == "<" else price > bound

    range_match = re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", expression)
    if range_match:
        low, high = float(range_match.group(1)), float(range_match.group(2))
        return low <= price <= high

    return False


def _load_drugs():
    with open(DRUG_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)