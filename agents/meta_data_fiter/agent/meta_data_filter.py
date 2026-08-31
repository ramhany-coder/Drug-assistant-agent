from agents.meta_data_fiter.agent.helpers import (
    is_price_sort_directive,
    log_low_confidence_query,
    matches_route,
    price_matches_filter,
)
from agents.meta_data_fiter.engine_registry import get_commercial_engine

MAX_CONTEXT_ITEMS = 10

# A hard filter (route or a price comparison) narrows the catalogue first, so the
# search engine only needs to search within it; the same behaviour is achieved
# cheaply here by pulling more candidates per field and filtering afterwards,
# rather than rebuilding a BM25 index over an arbitrary per-request subset.
_SEARCH_TOP_K = MAX_CONTEXT_ITEMS
_SEARCH_TOP_K_WITH_HARD_FILTER = MAX_CONTEXT_ITEMS * 3

TEXT_FIELDS = (
    "commercial_name_en",
    "commercial_name_ar",
    "scientific_name",
    "manufacturer",
    "drug_class",
)


def meta_data_filter(state):
    engine = get_commercial_engine()

    text_filters = {field: state.get(field) for field in TEXT_FIELDS}
    text_filters = {field: value for field, value in text_filters.items() if value}

    route = state.get("route")
    price_expression = state.get("price_egp")
    price_is_filter = bool(price_expression) and not is_price_sort_directive(price_expression)
    has_hard_filter = bool(route) or price_is_filter

    seen_records = set()
    matched_records = []

    def _consider(record):
        if not matches_route(route, record.get("route")):
            return
        if price_is_filter and not price_matches_filter(price_expression, record.get("price_egp")):
            return
        key = tuple(sorted(record.items()))
        if key in seen_records:
            return
        seen_records.add(key)
        matched_records.append(record)

    if text_filters:
        # commercial_name_en and scientific_name both filled with the same token
        # (the extractor unsure whether it named a brand or an ingredient) is
        # handled for free here: each filled field runs its own lookup and the
        # results are OR'd together (via _consider's dedup) rather than requiring
        # every field to match the same record.
        top_k = _SEARCH_TOP_K_WITH_HARD_FILTER if has_hard_filter else _SEARCH_TOP_K
        for field, value in text_filters.items():
            # exact_match is a deterministic, no-scoring lookup -- cheap, and
            # exactly right for a correctly-spelled query. The hybrid BM25 +
            # RapidFuzz search only runs at all when that finds nothing, so a
            # well-formed query never pays for fuzzy matching it doesn't need.
            hits = engine.exact_match(value, top_k=top_k)
            if not hits:
                # candidates_limit (search()'s own stage-1 BM25 cut per field)
                # defaults to 30 -- lower than top_k here -- so it must be raised
                # too, or it bottlenecks recall before top_k ever gets a chance
                # to matter.
                hits = engine.search(value, top_k=top_k, candidates_limit=top_k)
                if not hits:
                    log_low_confidence_query(field, value, engine.best_score(value))
            for hit in hits:
                _consider(hit["record"])
    elif has_hard_filter:
        for record in engine.records:
            _consider(record)
    else:
        return {"context": []}

    if price_expression and is_price_sort_directive(price_expression):
        reverse = price_expression.strip().lower() == "desc"
        with_price = [r for r in matched_records if r.get("price_egp") is not None]
        without_price = [r for r in matched_records if r.get("price_egp") is None]
        with_price.sort(key=lambda r: r["price_egp"], reverse=reverse)
        matched_records = with_price + without_price

    # Cap what gets forwarded to the responder so a broad match can't overflow the LLM's context window.
    return {"context": matched_records[:MAX_CONTEXT_ITEMS]}
