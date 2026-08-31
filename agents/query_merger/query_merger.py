from langchain_core.messages import HumanMessage, SystemMessage

from models.state import State
from models.query_merger import query_merger_model
from agents.query_merger.query_merger_prompt import (
    SYSTEM_PROMPT_QUERY_MERGER,
    human_prompt_query_merger,
)
from llm.client import fallback_client, FALLBACK_ORDER

DEFAULT_LANGUAGE = "egyptian_arabic"

CLARIFICATION_TEMPLATES = {
    "english": "I couldn't read that photo clearly enough to help: {reason} "
               "Could you resend a clearer, well-lit photo of the front of the box?",
    "egyptian_arabic": "معرفتش أقرا الصورة كويس: {reason} "
                        "ممكن تبعت صورة تانية أوضح لواجهة العلبة في إضاءة كويسة؟",
    "msa": "لم أتمكن من قراءة الصورة بوضوح: {reason} "
           "من فضلك أرسل صورة أوضح للواجهة الأمامية للعلبة في إضاءة جيدة.",
    "arabizi": "ma3raftesh a2ra el sora kwayes: {reason} "
               "mumken teb3at sora tanya awda7 lewag'het el 3elba fe ida2a kwaysa?",
}


def _clarification_message(description, user_language):
    template = CLARIFICATION_TEMPLATES.get(user_language, CLARIFICATION_TEMPLATES["english"])
    return template.format(reason=description or "the details on it were not legible.")


def query_merger(state: State):
    description = state.get("description")
    image_type = state.get("image_type")
    is_readable = state.get("is_readable")
    eng_query = state.get("eng_query")
    chat_history = state.get("chat_hist")
    user_language = state.get("user_language") or DEFAULT_LANGUAGE

    message = [
        SystemMessage(content=SYSTEM_PROMPT_QUERY_MERGER),
        HumanMessage(content=human_prompt_query_merger(
            description=description,
            image_type=image_type,
            is_readable=is_readable,
            eng_query=eng_query,
            chat_history=chat_history,
        )),
    ]

    result = fallback_client.constrained_invoke(message, FALLBACK_ORDER, constraine_model=query_merger_model)

    if result["needs_clarification"]:
        return {
            "needs_clarification": True,
            "user_language": user_language,
            "response": _clarification_message(description, user_language),
            "is_academic": False,
        }

    return {
        "needs_clarification": False,
        "user_language": user_language,
        "eng_query": result["merged_query"],
    }
