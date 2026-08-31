from typing import List, Optional

from pydantic import BaseModel, ValidationInfo, model_validator


class CompoundMapping(BaseModel):
    component: str
    generic_name: Optional[str] = None
    matched: bool
    source_product: Optional[str] = None

    @model_validator(mode="after")
    def _generic_name_matches_matched_flag(self):
        if self.matched and self.generic_name is None:
            raise ValueError(
                f"matched=True requires a generic_name for component '{self.component}'"
            )
        if not self.matched and self.generic_name is not None:
            raise ValueError(
                f"matched=False must not carry a generic_name for component '{self.component}'"
            )
        return self


class CompoundMapperModel(BaseModel):
    mappings: List[CompoundMapping]

    @model_validator(mode="after")
    def _generic_names_are_in_the_academic_index(self, info: ValidationInfo):
        context = info.context or {}
        valid_generic_names = context.get("valid_generic_names")
        if valid_generic_names is None:
            return self

        for mapping in self.mappings:
            if mapping.matched and mapping.generic_name not in valid_generic_names:
                raise ValueError(
                    f"generic_name '{mapping.generic_name}' for component "
                    f"'{mapping.component}' does not exist in the academic index "
                    "— refusing a hallucinated mapping"
                )
        return self
