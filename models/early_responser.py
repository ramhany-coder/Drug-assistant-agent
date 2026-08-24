from typing import Optional

from pydantic import BaseModel


class early_responser_model(BaseModel):
    response : Optional[str] = None
    is_academic : bool = False