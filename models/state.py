from typing import Annotated, Dict, List, Optional

from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class State(TypedDict):
    query: Optional[str]
    image: Optional[str]
    image_cleaned: Optional[str]
    image_redaction_mode: Optional[str]
    description: Optional[str]
    image_type: Optional[str]
    is_readable: Optional[bool]
    needs_clarification: Optional[bool]
    user_language: Optional[str]
    eng_query: Optional[str]
    commercial_name_en: Optional[str]
    commercial_name_ar: Optional[str]
    scientific_name: Optional[str]
    manufacturer: Optional[str]
    drug_class: Optional[str]
    route: Optional[str]
    price_egp: Optional[str]
    is_academic: Optional[bool]
    chat_hist: Annotated[list, add_messages]
    context: Optional[List[dict]]
    compound_mappings: Optional[List[dict]]
    response: Optional[str]
    native_response: Optional[str]
    stage_timings: Optional[Dict[str, float]]
