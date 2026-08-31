from agents.compound_mapper.academic_index import ACADEMIC_INDEX


def retrieve_academic(state):
    """Attaches each compound_mapper mapping to its monograph, so the responder can
    say which fact belongs to which ingredient instead of receiving merged records
    for a multi-ingredient product.

    Appends to whatever commercial rows meta_data_filter already put in `context`
    instead of replacing them — `context` has no LangGraph reducer, so returning it
    outright would silently drop the commercial catalogue rows (price, manufacturer,
    brand) right before the responder runs."""
    mappings = state.get("compound_mappings") or []

    academic_entries = [
        {
            "component": mapping.get("component"),
            "generic_name": mapping.get("generic_name"),
            "source_product": mapping.get("source_product"),
            "monograph": ACADEMIC_INDEX.by_generic_name.get(mapping["generic_name"])
            if mapping.get("generic_name")
            else None,
        }
        for mapping in mappings
    ]

    commercial_context = state.get("context") or []
    return {"context": commercial_context + academic_entries}
