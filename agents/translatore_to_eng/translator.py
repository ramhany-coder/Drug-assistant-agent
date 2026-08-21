from models.state import State
from langchain_core.messages import HumanMessage , SystemMessage
from agents.translatore_to_eng.translator_prompt import SYSTEM_PROMPT_TRANSLATOR_TO_ENG , human_prompt_translator_to_eng
from llm.client import fallback_client ,FALLBACK_ORDER



def translator_to_eng (state:State):
    query = state.get("query")
    message = [
        SystemMessage(content=SYSTEM_PROMPT_TRANSLATOR_TO_ENG),
        HumanMessage(content=human_prompt_translator_to_eng(query))
    ]
    result = fallback_client.invoke(message,fallback_order=FALLBACK_ORDER)

    return{
        'eng_query':result
    }