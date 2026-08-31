"""Builds/loads the commercial-catalogue MedicineSearchEngine once per process
and reuses it for every request. Building it from scratch costs ~6s (BM25 + n-gram
indexing across 25k+ records x 5 fields); loading a cached copy costs ~1.3s.
Persisted to cache/, keyed by a hash of data/egyptian-drugs.json, and rebuilt
automatically the first time that file's content changes.

Mirrors agents/image_pii/helpers.py's lazy-singleton shape: meta_data_filter calls
get_commercial_engine(), which builds/loads on first use so streamlit_app.py (which
imports the graph directly and never runs FastAPI's lifespan) still only pays that
cost once. api/app.py's lifespan calls warm_up_commercial_engine() so a live API
server pays it at startup instead of on the first live request.
"""

import hashlib
import logging
import pickle
from pathlib import Path

from agents.meta_data_fiter.search_engine import MedicineSearchEngine

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = _ROOT / "data" / "egyptian-drugs.json"
CACHE_DIR = _ROOT / "cache"

COMMERCIAL_SEARCH_FIELDS = [
    "commercial_name_en",
    "commercial_name_ar",
    "scientific_name",
    "manufacturer",
    "drug_class",
]

# Bump whenever MedicineSearchEngine's pickled shape changes (a new
# _field_index key, a changed default like min_score, ...) -- otherwise a cache
# built by an older version of the code gets loaded as-is and crashes or
# silently behaves like the old version, since the cache key is only a hash of
# the *data* file, which hasn't changed.
_SCHEMA_VERSION = 2

_UNSET = object()
_commercial_engine = _UNSET


def _source_hash() -> str:
    return hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()[:16]


def _cache_path(source_hash: str) -> Path:
    return CACHE_DIR / f"commercial_engine_v{_SCHEMA_VERSION}_{source_hash}.pkl"


def _build_and_cache(cache_path: Path) -> MedicineSearchEngine:
    engine = MedicineSearchEngine(search_fields=COMMERCIAL_SEARCH_FIELDS)
    engine.load_data(str(DATA_PATH))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Only one cache file should exist at a time -- an old one is dead weight
    # once the source file it was keyed to no longer matches.
    for stale in CACHE_DIR.glob("commercial_engine_*.pkl"):
        stale.unlink(missing_ok=True)
    with cache_path.open("wb") as f:
        pickle.dump(engine, f)

    return engine


def get_commercial_engine() -> MedicineSearchEngine:
    """Return the process-wide commercial search engine, building/loading it on
    the first call. Every call after the first returns the same in-memory object
    immediately -- meta_data_filter calls this on every request, but the actual
    load/build work happens at most once per process."""
    global _commercial_engine
    if _commercial_engine is not _UNSET:
        return _commercial_engine

    cache_path = _cache_path(_source_hash())
    if cache_path.exists():
        logger.info("Loading cached commercial search index from %s", cache_path)
        try:
            with cache_path.open("rb") as f:
                _commercial_engine = pickle.load(f)
            return _commercial_engine
        except Exception:
            # Belt-and-suspenders alongside _SCHEMA_VERSION: a corrupted or
            # otherwise-incompatible cache file should trigger a rebuild, not
            # take the whole app down.
            logger.exception("Cached index at %s failed to load -- rebuilding", cache_path)

    logger.info("No usable cache -- building commercial search index from %s", DATA_PATH)
    _commercial_engine = _build_and_cache(cache_path)
    return _commercial_engine


def warm_up_commercial_engine() -> None:
    """Force the commercial search engine to load/build now instead of lazily on
    the first request. Meant to be called once during app startup (see
    api/app.py's lifespan)."""
    get_commercial_engine()
