from typing import Literal

from pydantic import BaseModel, model_validator


class image_describer_model(BaseModel):
    description: str
    image_type: Literal[
        "drug_package",
        "blister_strip",
        "bottle_or_ampoule",
        "prescription",
        "pharmacy_shelf",
        "other_or_non_medicine",
    ]
    is_readable: bool

    @model_validator(mode="after")
    def _unreadable_must_explain_why(self):
        if not self.is_readable and not self.description.strip():
            raise ValueError("is_readable=False requires a description of what blocks reading")
        return self
