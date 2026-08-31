import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LOW_CONFIDENCE_LOG_PATH = Path(__file__).resolve().parents[3] / "logs" / "low_confidence_queries.jsonl"

_PRICE_SORT_DIRECTIVES = {"asc", "desc"}


def is_price_sort_directive(expression: Optional[str]) -> bool:
    return bool(expression) and expression.strip().lower() in _PRICE_SORT_DIRECTIVES


def price_matches_filter(expression: Optional[str], price) -> bool:
    """True only for a comparison expression (<N, >N, N-M) that `price` satisfies.
    A sort directive (asc/desc) is never a filter match on its own -- callers sort
    by it separately via is_price_sort_directive, after the hard filters run."""
    if not expression or price is None:
        return False
    expression = expression.strip().lower()
    if expression in _PRICE_SORT_DIRECTIVES:
        return False

    bound_match = re.fullmatch(r"(<|>)(\d+(?:\.\d+)?)", expression)
    if bound_match:
        op, bound = bound_match.group(1), float(bound_match.group(2))
        return price < bound if op == "<" else price > bound

    range_match = re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", expression)
    if range_match:
        low, high = float(range_match.group(1)), float(range_match.group(2))
        return low <= price <= high

    return False


def matches_route(expected: Optional[str], actual) -> bool:
    """route is a closed enum, so this is exact (case-insensitive) membership, not
    fuzzy matching. No route filter requested always passes."""
    if not expected:
        return True
    return actual is not None and str(actual).strip().upper() == expected.strip().upper()


def log_low_confidence_query(field: str, query: str, best_score: Optional[float]) -> None:
    LOW_CONFIDENCE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "field": field,
        "query": query,
        "best_score": best_score,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    with LOW_CONFIDENCE_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
