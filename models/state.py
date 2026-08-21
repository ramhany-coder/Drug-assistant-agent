from typing import Annotated , Optional
from typing_extensions import TypedDict
from langgraph.graph.message import Literal, add_messages
from pydantic import BaseModel


class State (BaseModel):
    query: Optional[str]
    user_language : Optional[str]
    eng_query : Optional[str]
    is_academic : Optional[bool]
    chat_hist : Annotated[list,add_messages]
    context : Optional[list]
    response : Optional[str]
    native_response : Optional[str]
    