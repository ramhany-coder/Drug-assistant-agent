"""Builds and compiles the LangGraph state machine from a map of agents.

The graph topology is described in one place so new agents/edges can be
added without touching the callers (endpoints.py, workflow.py).
"""

from typing import Any, Callable, Dict

from langgraph.graph import StateGraph, START, END

from agents.meta_data_fiter.agent.meta_data_filter import MAX_CONTEXT_ITEMS
from models.state import State


def _route_after_extractor(state: State) -> str:
    return "compound_mapper" if state.get("is_academic") and state.get("scientific_name") else "meta_data_filter"


def _route_after_filter(state: State) -> str:
    if not state.get("context"):
        return "early_responser"
    if state.get("is_academic"):
        return "compound_mapper"
    if (state.get("match_count") or 0) > MAX_CONTEXT_ITEMS:
        return "early_responser"
    return "product_cards"


class GraphBuilder:
    """Assembles the drug-database pipeline graph from named agent callables."""

    def __init__(self, agents: Dict[str, Callable]) -> None:
        self.agents = agents

    def build(self) -> Any:
        """Wire nodes and edges and return the compiled graph.

        A text-only query runs translator_to_eng -> meta_data_extractor as before.
        An image runs image_pii -> image_describer -> query_merger first: image_pii
        redacts PII from the photo (or blocks it closed) before it ever reaches the
        vision LLM, image_describer reads its output (image_cleaned) instead of the
        raw upload, and query_merger writes the merged result into eng_query so
        meta_data_extractor sees the same shape of input either way. If query_merger
        can't produce one (unreadable/blocked photo, no product in frame), it routes
        straight to END with a clarification response already set, instead of firing
        a search on an empty filter set.

        meta_data_extractor also sets is_academic: whether answering needs facts
        the catalogue fields can't hold (dose, interactions, side effects, ...).
        Only an academic query reads the academic monographs: if it already
        extracted a scientific_name, the commercial catalogue never needs to be
        consulted and compound_mapper runs immediately; otherwise
        meta_data_filter (commercial retrieval) runs first and compound_mapper
        reads scientific_name off whatever rows it matched.

        The responder (early_responser, an LLM call) is optional after
        meta_data_filter:
          - nothing matched                  -> early_responser, empty content
          - academic                         -> compound_mapper -> retrieve_academic
                                                -> early_responser
          - more than MAX_CONTEXT_ITEMS hit  -> early_responser, commercial rows only
          - otherwise                        -> product_cards (templated intro + the
                                                rows as cards, no LLM) -> END
        """
        graph = StateGraph(State)

        graph.add_node("translator_to_eng", self.agents["translator_to_eng"])
        graph.add_node("image_pii", self.agents["image_pii"])
        graph.add_node("image_describer", self.agents["image_describer"])
        graph.add_node("query_merger", self.agents["query_merger"])
        graph.add_node("meta_data_extractor", self.agents["meta_data_extractor"])
        graph.add_node("meta_data_filter", self.agents["meta_data_filter"])
        graph.add_node("compound_mapper", self.agents["compound_mapper"])
        graph.add_node("retrieve_academic", self.agents["retrieve_academic"])
        graph.add_node("early_responser", self.agents["early_responser"])
        graph.add_node("product_cards", self.agents["product_cards"])

        # An image with no caption skips the translator entirely (there is no text
        # to translate); an image with a caption, or a plain text query, both need
        # it -- the caption for its own translation, the text query as before.
        graph.add_conditional_edges(
            START,
            lambda state: "image_pii" if state.get("image") and not state.get("query") else "translator_to_eng",
            {"image_pii": "image_pii", "translator_to_eng": "translator_to_eng"},
        )
        # translator_to_eng is shared by the text-only path and the image+caption
        # path; only the presence of an image decides where it goes next.
        graph.add_conditional_edges(
            "translator_to_eng",
            lambda state: "image_pii" if state.get("image") else "meta_data_extractor",
            {"image_pii": "image_pii", "meta_data_extractor": "meta_data_extractor"},
        )
        graph.add_edge("image_pii", "image_describer")
        graph.add_edge("image_describer", "query_merger")
        graph.add_conditional_edges(
            "query_merger",
            lambda state: END if state.get("needs_clarification") else "meta_data_extractor",
            {END: END, "meta_data_extractor": "meta_data_extractor"},
        )

        graph.add_conditional_edges(
            "meta_data_extractor",
            _route_after_extractor,
            {"compound_mapper": "compound_mapper", "meta_data_filter": "meta_data_filter"},
        )
        graph.add_conditional_edges(
            "meta_data_filter",
            _route_after_filter,
            {
                "compound_mapper": "compound_mapper",
                "early_responser": "early_responser",
                "product_cards": "product_cards",
            },
        )

        graph.add_edge("compound_mapper", "retrieve_academic")
        graph.add_edge("retrieve_academic", "early_responser")
        graph.add_edge("early_responser", END)
        graph.add_edge("product_cards", END)

        return graph.compile()
