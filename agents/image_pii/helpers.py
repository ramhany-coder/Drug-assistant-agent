import logging
import queue
import threading

from presidio_analyzer import AnalyzerEngine

try:
    from presidio_analyzer.nlp_engine import NlpEngineProvider
except Exception:
    NlpEngineProvider = None

try:
    from presidio_image_redactor import ImageAnalyzerEngine, ImageRedactorEngine
except Exception:
    ImageAnalyzerEngine = None
    ImageRedactorEngine = None

from config import settings
from model_manager import ensure_spacy_model_downloaded

logger = logging.getLogger(__name__)

# Building the ImageRedactorEngine loads a spaCy NLP pipeline, which can take
# a while (or hang outright if the model/network isn't available). Doing that
# at import time would block the whole process before any request is served,
# so it's built lazily in a background thread the first time redaction is
# actually needed, with a bounded wait per call.
_INIT_TIMEOUT_SECONDS = 15
_result_queue: "queue.Queue" = queue.Queue(maxsize=1)
_init_started = threading.Event()

# Distinguishes "not resolved yet" from "resolved to a permanent failure"
# (engine is None) -- both must be cacheable without re-blocking every call
# on a queue that already gave up its one item.
_UNSET = object()
_image_redactor_engine = _UNSET


def _init_worker() -> None:
    try:
        ensure_spacy_model_downloaded(settings.PII_SPACY_MODEL_NAME, settings.PII_SPACY_MODEL_DIR)

        if ImageRedactorEngine is None or ImageAnalyzerEngine is None:
            raise RuntimeError("presidio_image_redactor is not installed")

        # NlpEngineProvider lets the spaCy model be swapped via
        # settings.PII_SPACY_MODEL_NAME (e.g. "en_core_web_sm" on a
        # memory-constrained deployment); a bare AnalyzerEngine() always loads
        # Presidio's hardcoded default ("en_core_web_lg") regardless.
        if NlpEngineProvider is not None:
            nlp_engine = NlpEngineProvider(
                nlp_configuration={
                    "nlp_engine_name": "spacy",
                    "models": [
                        {"lang_code": "en", "model_name": settings.PII_SPACY_MODEL_NAME}
                    ],
                }
            ).create_engine()
            analyzer_engine = AnalyzerEngine(nlp_engine=nlp_engine)
        else:
            analyzer_engine = AnalyzerEngine()

        image_redactor = ImageRedactorEngine(ImageAnalyzerEngine(analyzer_engine=analyzer_engine))
        _result_queue.put(image_redactor)
    except Exception as e:
        logger.error("Image PII engine initialization failed: %s", e)
        _result_queue.put(None)


def _get_image_pii_engine():
    """Return the ImageRedactorEngine (or None), starting lazy init on first
    call. Waits up to _INIT_TIMEOUT_SECONDS; if init hasn't finished yet,
    returns None for this call without giving up permanently, so a
    slow-but-eventually-successful load still gets used on a later call."""
    global _image_redactor_engine
    if _image_redactor_engine is not _UNSET:
        return _image_redactor_engine

    if not _init_started.is_set():
        _init_started.set()
        threading.Thread(target=_init_worker, daemon=True).start()

    try:
        _image_redactor_engine = _result_queue.get(timeout=_INIT_TIMEOUT_SECONDS)
    except queue.Empty:
        logger.error(
            "Image PII engine still not ready after %ss; blocking the image for this call.",
            _INIT_TIMEOUT_SECONDS,
        )
        return None

    return _image_redactor_engine


def warm_up_image_pii_engine() -> None:
    """Force the image PII engine to initialize now instead of lazily on the
    first request. Meant to be called once during app startup (see
    api/app.py's lifespan) so any first-time model download happens there,
    not on a live user request."""
    _get_image_pii_engine()
