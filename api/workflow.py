import logging
import time
from typing import Any, Callable, Dict, List, Optional

from agents.translatore_to_eng.translator import translator_to_eng
from agents.image_pii.image_pii import image_pii
from agents.image_describer.image_describer import image_describer
from agents.query_merger.query_merger import query_merger
from agents.meta_data_fiter.query_extractor.extractor import meta_data_extractor
from agents.meta_data_fiter.agent.meta_data_filter import meta_data_filter
from agents.compound_mapper.compound_mapper import compound_mapper
from agents.retreivale.agent import retrieve_academic
from agents.early_responser.early_responser import early_responser

from api.graph_builder import GraphBuilder

logger = logging.getLogger("pipeline")


def _normalize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Reshape a graph state (partial or complete) into the API's response shape."""
    return {
        "eng_query": state.get("eng_query"),
        "user_language": state.get("user_language"),
        "description": state.get("description"),
        "image_type": state.get("image_type"),
        "image_redaction_mode": state.get("image_redaction_mode"),
        "is_readable": state.get("is_readable"),
        "needs_clarification": state.get("needs_clarification"),
        "extracted": {
            "commercial_name_en": state.get("commercial_name_en"),
            "commercial_name_ar": state.get("commercial_name_ar"),
            "scientific_name": state.get("scientific_name"),
            "manufacturer": state.get("manufacturer"),
            "drug_class": state.get("drug_class"),
            "route": state.get("route"),
            "price_egp": state.get("price_egp"),
        },
        "context": state.get("context", []),
        "compound_mappings": state.get("compound_mappings", []),
        "response": state.get("response"),
        "is_academic": state.get("is_academic", False),
    }


class PipelineStageError(Exception):
    """Raised when a graph node fails. Carries the failing stage's name, how long it
    ran before failing, the latencies of every stage that completed before it, and a
    snapshot of the state as it stood going into the failing stage — so callers can
    tell exactly where the gap happened and what data led to it, without re-reading
    server logs."""

    def __init__(
        self,
        stage: str,
        elapsed: float,
        stage_timings: Dict[str, float],
        state: Dict[str, Any],
        original: Exception,
    ) -> None:
        self.stage = stage
        self.elapsed = elapsed
        self.stage_timings = stage_timings
        self.state = state
        self.original = original
        super().__init__(f"stage '{stage}' failed after {elapsed:.2f}s: {original}")


def _timed(name: str, fn: Callable) -> Callable:
    """Wrap an agent callable so its latency is recorded into state, and any failure
    is logged with the stage name, elapsed time, the timings of prior stages, and the
    state going into that stage."""

    def wrapper(state):
        start = time.perf_counter()
        try:
            result = fn(state)
        except Exception as e:
            elapsed = time.perf_counter() - start
            prior_timings = dict(state.get("stage_timings") or {})
            state_snapshot = _normalize_state(dict(state))
            logger.error(
                "[pipeline] failed at stage '%s' after %.2fs - completed stages: %s - "
                "state going in: %s - error: %s",
                name, elapsed, prior_timings, state_snapshot, e,
            )
            raise PipelineStageError(name, elapsed, prior_timings, state_snapshot, e) from e

        elapsed = time.perf_counter() - start
        timings = dict(state.get("stage_timings") or {})
        timings[name] = round(elapsed, 3)
        logger.info("[pipeline] stage '%s' completed in %.2fs", name, elapsed)

        result = dict(result)
        result["stage_timings"] = timings
        return result

    return wrapper


def default_agent_map() -> Dict[str, Any]:
    """Return the default mapping of node name -> timed agent callable."""
    return {
        "translator_to_eng": _timed("translator_to_eng", translator_to_eng),
        "image_pii": _timed("image_pii", image_pii),
        "image_describer": _timed("image_describer", image_describer),
        "query_merger": _timed("query_merger", query_merger),
        "meta_data_extractor": _timed("meta_data_extractor", meta_data_extractor),
        "meta_data_filter": _timed("meta_data_filter", meta_data_filter),
        "compound_mapper": _timed("compound_mapper", compound_mapper),
        "retrieve_academic": _timed("retrieve_academic", retrieve_academic),
        "early_responser": _timed("early_responser", early_responser),
    }


graph = GraphBuilder(default_agent_map()).build()


# query_merger and early_responser only use chat_hist to resolve pronouns/follow-ups
# ("and the price?"), which only ever point at the last exchange or two -- so keeping
# the full session history in every prompt just burns tokens for no retrieval benefit.
MAX_CHAT_HISTORY_MESSAGES = 10


def run_pipeline(
    query: Optional[str] = None,
    chat_hist: Optional[List[Any]] = None,
    image: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs the compiled graph: translator -> extractor -> filter -> responder, or,
    when `image` is given, image_describer -> query_merger first (see
    GraphBuilder.build). `image` is a data URI ("data:image/jpeg;base64,...") or a
    plain URL the vision model can fetch; `query` doubles as the photo's caption.

    Raises PipelineStageError (see above) if any stage fails."""
    trimmed_hist = (chat_hist or [])[-MAX_CHAT_HISTORY_MESSAGES:]
    initial_state = {"query": query, "chat_hist": trimmed_hist, "image": image}
    start = time.perf_counter()

    try:
        final_state = graph.invoke(initial_state)
    except PipelineStageError as e:
        total_elapsed = time.perf_counter() - start
        logger.error(
            "[pipeline] aborted after %.2fs total - failed stage: '%s'",
            total_elapsed, e.stage,
        )
        raise

    total_elapsed = time.perf_counter() - start
    logger.info(
        "[pipeline] completed in %.2fs - stage_timings=%s",
        total_elapsed, final_state.get("stage_timings"),
    )

    return {
        **_normalize_state(final_state),
        "stage_timings": final_state.get("stage_timings", {}),
        "total_latency_seconds": round(total_elapsed, 3),
    }
