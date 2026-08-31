from langchain_core.messages import HumanMessage, SystemMessage

from models.state import State
from models.image_describer import image_describer_model
from agents.image_describer.image_describer_prompt import (
    SYSTEM_PROMPT_IMAGE_DESCRIBER,
    human_prompt_image_describer,
)
from llm.client import fallback_client, FALLBACK_ORDER


def image_describer(state: State):
    image_cleaned = state.get("image_cleaned")
    eng_query = state.get("eng_query")

    if not image_cleaned:
        # image_pii blocked this image (or found nothing it could safely
        # redact) -- never fall back to the raw `image` field here, that
        # would defeat the PII filter entirely.
        return {
            "description": "This photo could not be processed and was blocked before analysis.",
            "image_type": "other_or_non_medicine",
            "is_readable": False,
        }

    message = [
        SystemMessage(content=SYSTEM_PROMPT_IMAGE_DESCRIBER),
        HumanMessage(content=[
            {"type": "text", "text": human_prompt_image_describer(eng_query)},
            {"type": "image_url", "image_url": {"url": image_cleaned}},
        ]),
    ]

    result = fallback_client.constrained_invoke(message, FALLBACK_ORDER, constraine_model=image_describer_model)

    return {
        "description": result["description"],
        "image_type": result["image_type"],
        "is_readable": result["is_readable"],
    }
