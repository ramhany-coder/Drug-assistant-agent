from pydantic import BaseModel


class early_responser_model(BaseModel):
    response : str
    is_academic : bool = False