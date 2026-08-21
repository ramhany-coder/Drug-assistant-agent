from models.state import State
from models.classifier import classifier_model
from langchain_core.messages import HumanMessage , SystemMessage
from agents.query_classifier.classifier_prompt import human_prompt_classifier,SYSTEM_PROMPT_CLASSIFIER
from llm.client import fallback_client , FALLBACK_ORDER


def classifier (state : State):
    query = state.get("eng_query")

    message = [
        SystemMessage(content=SYSTEM_PROMPT_CLASSIFIER),
        HumanMessage(content=human_prompt_classifier(query))
    ]

    result = fallback_client.constrained_invoke(message=message,fallback_order=FALLBACK_ORDER,constraine_model=classifier_model)

    return {
        "is_academic" : result
    }