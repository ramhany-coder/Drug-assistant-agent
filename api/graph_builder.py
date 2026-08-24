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
        """Wire nodes and edges and return the compiled graph."""
        graph = StateGraph(State)

        graph.add_node("translator_to_eng", self.agents["translator_to_eng"])
        graph.add_node("meta_data_extractor", self.agents["meta_data_extractor"])
        graph.add_node("meta_data_filter", self.agents["meta_data_filter"])
        graph.add_node("early_responser", self.agents["early_responser"])

        graph.add_edge(START, "translator_to_eng")
        graph.add_edge("translator_to_eng", "meta_data_extractor")
        graph.add_edge("meta_data_extractor", "meta_data_filter")
        graph.add_edge("meta_data_filter", "early_responser")
        graph.add_edge("early_responser", END)

        return graph.compile()
