from agents.meta_data_fiter.agent.helpers import _load_drugs,_tokenize,_matches_price

MAX_CONTEXT_ITEMS = 40


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
    if chunks is None :
        return {"is_academic":True}

    # Cap what gets forwarded to the responder so a broad match can't overflow the LLM's context window.
    return {"context": chunks[:MAX_CONTEXT_ITEMS]}
