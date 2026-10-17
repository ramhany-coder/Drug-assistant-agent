"""Which nodes a text query passes through, with every agent replaced by a stub --
so the routing in GraphBuilder.build is checked without any LLM or catalogue."""

import pytest

from agents.meta_data_fiter.agent.meta_data_filter import MAX_CONTEXT_ITEMS
from api.graph_builder import GraphBuilder

NODES = (
    "translator_to_eng",
    "image_pii",
    "image_describer",
    "query_merger",
    "meta_data_extractor",
    "meta_data_filter",
    "compound_mapper",
    "retrieve_academic",
    "early_responser",
    "product_cards",
)

ROW = {"commercial_name_en": "PANADOL EXTRA", "scientific_name": "PARACETAMOL", "price_egp": 20.0}


def _run(extracted, filtered=None):
    """Run a text query through the graph; return the node names visited, in order."""
    visited = []

    def stub(name, update):
        def node(state):
            visited.append(name)
            return update
        return node

    updates = {name: {"response": name} for name in NODES}
    updates["translator_to_eng"] = {"eng_query": "q", "user_language": "english"}
    updates["meta_data_extractor"] = extracted
    updates["meta_data_filter"] = filtered or {"context": [], "match_count": 0}

    graph = GraphBuilder({name: stub(name, updates[name]) for name in NODES}).build()
    graph.invoke({"query": "q", "chat_hist": [], "image": None})
    return visited


def _rows(count):
    return {"context": [ROW] * min(count, MAX_CONTEXT_ITEMS), "match_count": count}


@pytest.mark.parametrize("count", [1, MAX_CONTEXT_ITEMS])
def test_non_academic_with_few_matches_ends_on_cards_without_the_responder(count):
    visited = _run({"commercial_name_en": "PANADOL", "is_academic": False}, _rows(count))
    assert visited[-1] == "product_cards"
    assert "early_responser" not in visited
    assert "compound_mapper" not in visited


def test_non_academic_with_more_than_the_cap_goes_to_the_responder_without_academic_data():
    visited = _run({"commercial_name_en": "PANADOL", "is_academic": False}, _rows(MAX_CONTEXT_ITEMS + 1))
    assert visited[-2:] == ["meta_data_filter", "early_responser"]
    assert "product_cards" not in visited


def test_academic_runs_academic_retrieval_then_the_responder():
    visited = _run({"commercial_name_en": "PANADOL", "is_academic": True}, _rows(2))
    assert visited[-4:] == ["meta_data_filter", "compound_mapper", "retrieve_academic", "early_responser"]


def test_academic_with_scientific_name_skips_the_catalogue():
    visited = _run({"scientific_name": "PARACETAMOL", "is_academic": True})
    assert "meta_data_filter" not in visited
    assert visited[-3:] == ["compound_mapper", "retrieve_academic", "early_responser"]


def test_non_academic_with_scientific_name_searches_the_catalogue():
    visited = _run({"scientific_name": "PARACETAMOL", "is_academic": False}, _rows(3))
    assert "meta_data_filter" in visited
    assert visited[-1] == "product_cards"


def test_no_matches_goes_to_the_responder():
    visited = _run({"commercial_name_en": "NOTHING", "is_academic": False})
    assert visited[-2:] == ["meta_data_filter", "early_responser"]
