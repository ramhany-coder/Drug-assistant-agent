from models.state import State
from models.extractor import extractor_model
from langchain_core.messages import HumanMessage , SystemMessage
from agents.meta_data_fiter.query_extractor.extractor_prompt import human_prompt_extractor , SYSTEM_PROMPT_EXTRACTOR
from llm.client import fallback_client , FALLBACK_ORDER


def meta_data_extractor (state : State):
    query = state.get("eng_query")

    message = [
        SystemMessage(content=SYSTEM_PROMPT_EXTRACTOR),
        HumanMessage(content=human_prompt_extractor(query))
    ]

    result = fallback_client.constrained_invoke(message=message,fallback_order=FALLBACK_ORDER,constraine_model=extractor_model)

    return {
        "commercial_name_en" : result.commercial_name_en,
        "commercial_name_ar" : result.commercial_name_ar,
        "scientific_name" : result.scientific_name,
        "manufacturer" : result.manufacturer,
        "drug_class" : result.drug_class,
        "route" : result.route,
        "price_egp" : result.price_egp,
    }