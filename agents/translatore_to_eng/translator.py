from models.translator import translator_model
from langchain_core.messages import HumanMessage , SystemMessage
from agents.translatore_to_eng.translator_prompt import SYSTEM_PROMPT_TRANSLATOR_TO_ENG , human_prompt_translator_to_eng
from llm.client import fallback_client ,FALLBACK_ORDER



def translator_to_eng (state):
    query = state.get("query")
    message = [
        SystemMessage(content=SYSTEM_PROMPT_TRANSLATOR_TO_ENG),
        HumanMessage(content=human_prompt_translator_to_eng(query))
    ]
    result = fallback_client.constrained_invoke(message,FALLBACK_ORDER,constraine_model=translator_model)

    return{
        'eng_query':result.eng_query,
        'user_language':result.user_language
    }