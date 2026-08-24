from typing import Any, Dict, List, Optional

from agents.translatore_to_eng.translator import translator_to_eng
from agents.meta_data_fiter.query_extractor.extractor import meta_data_extractor
from agents.meta_data_fiter.agent.meta_data_filter import meta_data_filter
from agents.early_responser.early_responser import early_responser

from api.graph_builder import GraphBuilder


def default_agent_map() -> Dict[str, Any]:
    """Return the default mapping of node name -> agent callable."""
    return {
        "translator_to_eng": translator_to_eng,
        "meta_data_extractor": meta_data_extractor,
        "meta_data_filter": meta_data_filter,
        "early_responser": early_responser,
    }


graph = GraphBuilder(default_agent_map()).build()


def run_pipeline(query: str, chat_hist: Optional[List[Any]] = None) -> Dict[str, Any]:
    """Runs the compiled graph: translator -> extractor -> filter -> responder."""
    initial_state = {"query": query, "chat_hist": chat_hist or []}

    final_state = graph.invoke(initial_state)

    return {
        "eng_query": final_state.get("eng_query"),
        "user_language": final_state.get("user_language"),
        "extracted": {
            "commercial_name_en": final_state.get("commercial_name_en"),
            "commercial_name_ar": final_state.get("commercial_name_ar"),
            "scientific_name": final_state.get("scientific_name"),
            "manufacturer": final_state.get("manufacturer"),
            "drug_class": final_state.get("drug_class"),
            "route": final_state.get("route"),
            "price_egp": final_state.get("price_egp"),
        },
        "context": final_state.get("context", []),
        "response": final_state.get("response"),
        "is_academic": final_state.get("is_academic", False),
    }
