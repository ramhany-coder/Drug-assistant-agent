import logging
import time
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.translatore_to_eng.translator import translator_to_eng
from agents.meta_data_fiter.query_extractor.extractor import meta_data_extractor
from agents.meta_data_fiter.agent.meta_data_filter import meta_data_filter
from agents.compound_mapper.compound_mapper import compound_mapper
from agents.retreivale.agent import retrieve_academic
from agents.early_responser.early_responser import early_responser
from api.workflow import run_pipeline, PipelineStageError

router = APIRouter()
logger = logging.getLogger("pipeline")


def _run_stage(name: str, fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Time a single-stage call; log and raise a 500 with the stage name + latency on failure."""
    start = time.perf_counter()
    try:
        result = fn()
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("[api] stage '%s' failed after %.2fs: %s", name, elapsed, e)
        raise HTTPException(
            status_code=500,
            detail={
                "failed_stage": name,
                "stage_latency_seconds": round(elapsed, 3),
                "error": str(e),
            },
        )

    elapsed = time.perf_counter() - start
    logger.info("[api] stage '%s' completed in %.2fs", name, elapsed)
    result = dict(result)
    result["latency_seconds"] = round(elapsed, 3)
    return result


# ---- stage 1: translator ----

class TranslateRequest(BaseModel):
    query: str


class TranslateResponse(BaseModel):
    eng_query: str
    user_language: str
    latency_seconds: float


@router.post("/translate", response_model=TranslateResponse)
def translate(payload: TranslateRequest):
    return _run_stage("translator_to_eng", lambda: translator_to_eng({"query": payload.query}))


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
    latency_seconds: float


@router.post("/extract", response_model=ExtractResponse)
def extract(payload: ExtractRequest):
    return _run_stage("meta_data_extractor", lambda: meta_data_extractor({"eng_query": payload.eng_query}))


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
    latency_seconds: float


@router.post("/filter", response_model=FilterResponse)
def filter_metadata(payload: FilterRequest):
    return _run_stage("meta_data_filter", lambda: meta_data_filter(payload.model_dump()))


# ---- stage 3b: compound mapper ----

class CompoundMapperRequest(BaseModel):
    scientific_name: Optional[str] = None
    context: List[Dict[str, Any]] = []


class CompoundMapperResponse(BaseModel):
    compound_mappings: List[Dict[str, Any]] = []
    latency_seconds: float


@router.post("/map_compounds", response_model=CompoundMapperResponse)
def map_compounds(payload: CompoundMapperRequest):
    return _run_stage("compound_mapper", lambda: compound_mapper(payload.model_dump()))


# ---- stage 3c: academic retrieval ----

class RetrieveAcademicRequest(BaseModel):
    compound_mappings: List[Dict[str, Any]] = []


class RetrieveAcademicResponse(BaseModel):
    context: List[Dict[str, Any]] = []
    latency_seconds: float


@router.post("/retrieve_academic", response_model=RetrieveAcademicResponse)
def retrieve_academic_endpoint(payload: RetrieveAcademicRequest):
    return _run_stage("retrieve_academic", lambda: retrieve_academic(payload.model_dump()))


# ---- stage 4: early responder ----

class RespondRequest(BaseModel):
    eng_query: str
    user_language: str
    context: List[Dict[str, Any]] = []
    chat_hist: List[Any] = []


class RespondResponse(BaseModel):
    response: Optional[str] = None
    is_academic: bool = False
    latency_seconds: float


@router.post("/respond", response_model=RespondResponse)
def respond(payload: RespondRequest):
    return _run_stage("early_responser", lambda: early_responser(payload.model_dump()))


# ---- full pipeline ----

class PipelineRequest(BaseModel):
    query: str
    chat_hist: List[Any] = []


class PipelineResponse(BaseModel):
    eng_query: Optional[str] = None
    user_language: Optional[str] = None
    extracted: Dict[str, Any]
    context: List[Dict[str, Any]]
    compound_mappings: List[Dict[str, Any]] = []
    response: Optional[str] = None
    is_academic: bool = False
    stage_timings: Dict[str, float] = {}
    total_latency_seconds: float


@router.post("/pipeline/run", response_model=PipelineResponse)
def run_full_pipeline(payload: PipelineRequest):
    try:
        return run_pipeline(payload.query, payload.chat_hist)
    except PipelineStageError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "failed_stage": e.stage,
                "stage_latency_seconds": round(e.elapsed, 3),
                "completed_stage_timings": e.stage_timings,
                "state": e.state,
                "error": str(e.original),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
