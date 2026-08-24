from pydantic import BaseModel


class translator_model (BaseModel):
    eng_query : str
    user_language : str