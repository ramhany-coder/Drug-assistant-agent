from typing import Optional

from pydantic import BaseModel, model_validator


class query_merger_model(BaseModel):
    merged_query: Optional[str] = None
    needs_clarification: bool

    @model_validator(mode="after")
    def _clarification_matches_merged_query(self):
        if self.needs_clarification and self.merged_query is not None:
            raise ValueError("needs_clarification=True must not carry a merged_query")
        if not self.needs_clarification and self.merged_query is None:
            raise ValueError("needs_clarification=False requires a merged_query")
        return self
