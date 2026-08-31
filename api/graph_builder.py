"""Builds and compiles the LangGraph state machine from a map of agents.

The graph topology is described in one place so new agents/edges can be
added without touching the callers (endpoints.py, workflow.py).
"""

from typing import Any, Callable, Dict

from langgraph.graph import StateGraph, START, END

from models.state import State


class GraphBuilder:
    """Assembles the drug-database pipeline graph from named agent callables."""

    def __init__(self, agents: Dict[str, Callable]) -> None:
        self.agents = agents

    def build(self) -> Any:
        """Wire nodes and edges and return the compiled graph.

        meta_data_extractor branches on whether it already extracted a
        scientific_name directly: if so, the commercial catalogue never needs to
        be consulted and compound_mapper runs immediately. Otherwise
        meta_data_filter (commercial retrieval) runs first, and compound_mapper
        reads scientific_name off whatever rows it matched — or is skipped
        entirely if it matched nothing, straight to early_responser with empty
        content.
        """
        graph = StateGraph(State)

        graph.add_node("translator_to_eng", self.agents["translator_to_eng"])
        graph.add_node("meta_data_extractor", self.agents["meta_data_extractor"])
        graph.add_node("meta_data_filter", self.agents["meta_data_filter"])
        graph.add_node("compound_mapper", self.agents["compound_mapper"])
        graph.add_node("retrieve_academic", self.agents["retrieve_academic"])
        graph.add_node("early_responser", self.agents["early_responser"])

        graph.add_edge(START, "translator_to_eng")
        graph.add_edge("translator_to_eng", "meta_data_extractor")

        graph.add_conditional_edges(
            "meta_data_extractor",
            lambda state: "compound_mapper" if state.get("scientific_name") else "meta_data_filter",
            {"compound_mapper": "compound_mapper", "meta_data_filter": "meta_data_filter"},
        )
        graph.add_conditional_edges(
            "meta_data_filter",
            lambda state: "compound_mapper" if state.get("context") else "early_responser",
            {"compound_mapper": "compound_mapper", "early_responser": "early_responser"},
        )

        graph.add_edge("compound_mapper", "retrieve_academic")
        graph.add_edge("retrieve_academic", "early_responser")
        graph.add_edge("early_responser", END)

        return graph.compile()
