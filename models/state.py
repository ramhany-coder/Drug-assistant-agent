from typing import Annotated , Optional
from typing_extensions import TypedDict
from langgraph.graph.message import Literal, add_messages
from pydantic import BaseModel


class State (BaseModel):
    query: Optional[str]
    user_language : Optional[str]
    eng_query : Optional[str]
    commercial_name_en : Optional[str] = None
    commercial_name_ar : Optional[str] = None
    scientific_name : Optional[str] = None
    manufacturer : Optional[str] = None
    drug_class : Optional[str] = None
    route : Optional[str] = None
    price_egp : Optional[str] = None
    is_academic : Optional[bool] = False
    chat_hist : Annotated[list,add_messages]
    context : Optional[list[str]]
    response : Optional[str]
    native_response : Optional[str]
    