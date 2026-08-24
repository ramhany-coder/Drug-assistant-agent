from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.translatore_to_eng.translator import translator_to_eng
from agents.meta_data_fiter.query_extractor.extractor import meta_data_extractor
from agents.meta_data_fiter.agent.meta_data_filter import meta_data_filter
from agents.early_responser.early_responser import early_responser
from api.workflow import run_pipeline

router = APIRouter()


# ---- stage 1: translator ----

class TranslateRequest(BaseModel):
    query: str


class TranslateResponse(BaseModel):
    eng_query: str
    user_language: str


@router.post("/translate", response_model=TranslateResponse)
def translate(payload: TranslateRequest):
    try:
        return translator_to_eng({"query": payload.query})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- stage 2: metadata extractor ----

class ExtractRequest(BaseModel):
    eng_query: str


class ExtractResponse(BaseModel):
    commercial_name_en: Optional[str] = None
    commercial_name_ar: Optional[str] = None
    scientific_name: Optional[str] = None
    manufacturer: Optional[str] = None
    drug_class: Optional[str] = None
    route: Optional[str] = None
    price_egp: Optional[str] = None


@router.post("/extract", response_model=ExtractResponse)
def extract(payload: ExtractRequest):
    try:
        return meta_data_extractor({"eng_query": payload.eng_query})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- stage 3: metadata filter ----

class FilterRequest(BaseModel):
    commercial_name_en: Optional[str] = None
    commercial_name_ar: Optional[str] = None
    scientific_name: Optional[str] = None
    manufacturer: Optional[str] = None
    drug_class: Optional[str] = None
    route: Optional[str] = None
    price_egp: Optional[str] = None


class FilterResponse(BaseModel):
    context: List[Dict[str, Any]] = []
    is_academic: Optional[bool] = None


@router.post("/filter", response_model=FilterResponse)
def filter_metadata(payload: FilterRequest):
    try:
        return meta_data_filter(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- stage 4: early responder ----

class RespondRequest(BaseModel):
    eng_query: str
    user_language: str
    context: List[Dict[str, Any]] = []
    chat_hist: List[Any] = []


class RespondResponse(BaseModel):
    response: Optional[str] = None
    is_academic: bool = False


@router.post("/respond", response_model=RespondResponse)
def respond(payload: RespondRequest):
    try:
        return early_responser(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- full pipeline ----

class PipelineRequest(BaseModel):
    query: str
    chat_hist: List[Any] = []


class PipelineResponse(BaseModel):
    eng_query: Optional[str] = None
    user_language: Optional[str] = None
    extracted: Dict[str, Any]
    context: List[Dict[str, Any]]
    response: Optional[str] = None
    is_academic: bool = False


@router.post("/pipeline/run", response_model=PipelineResponse)
def run_full_pipeline(payload: PipelineRequest):
    try:
        return run_pipeline(payload.query, payload.chat_hist)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
