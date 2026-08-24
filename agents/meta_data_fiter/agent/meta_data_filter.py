import json
import re
from pathlib import Path

from agents.meta_data_fiter.query_extractor.extractor import meta_data_extractor

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


def meta_data_filter(state):

    filters = {
        "commercial_name_en": state.get("commercial_name_en"),
        "commercial_name_ar": state.get("commercial_name_ar"),
        "scientific_name": state.get("scientific_name"),
        "manufacturer": state.get("manufacturer"),
        "drug_class": state.get("drug_class"),
        "route": state.get("route"),
    }
    filters = {key: value for key, value in filters.items() if value is not None}
    price_egp = state.get("price_egp")

    chunks = []
    for drug in _load_drugs():
        text_matched = any(
            _tokenize(value) & _tokenize(drug.get(key))
            for key, value in filters.items()
        )
        price_matched = price_egp is not None and _matches_price(price_egp, drug.get("price_egp"))

        if text_matched or price_matched:
            chunks.append(drug)

    return chunks
