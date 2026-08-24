from models.early_responser import early_responser_model
from langchain_core.messages import SystemMessage , HumanMessage
from agents.early_responser.early_responser_prompt import SYSTEM_PROMPT_EARLY_RESPONSER , human_prompt_early_responser
from llm.client import fallback_client , FALLBACK_ORDER

def early_responser (state):
    query = state.get("eng_query")
    language = state.get("user_language")
    content = state.get("context")
    chat_history = state.get("chat_hist")


    message = [SystemMessage(content=SYSTEM_PROMPT_EARLY_RESPONSER),
               HumanMessage(content=human_prompt_early_responser(query=query,
                                                                 user_language=language,
                                                                 content=content,
                                                                 chat_history=chat_history))]

    result = fallback_client.constrained_invoke(message,FALLBACK_ORDER,constraine_model=early_responser_model)

    return {
        "response":result["response"],
        "is_academic":result["is_academic"]
    }