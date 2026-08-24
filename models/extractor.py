from pydantic import BaseModel


class extractor_model (BaseModel):
    commercial_name_en : str | None = None
    commercial_name_ar : str | None = None
    scientific_name : str | None = None
    manufacturer : str | None = None
    drug_class : str | None = None
    route : str | None = None
    price_egp : str | None = None