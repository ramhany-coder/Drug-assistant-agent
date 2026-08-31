import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# Importing api.endpoints pulls in every agent module. The image PII engine
# (agents/image_pii/helpers.py) and the commercial search engine
# (agents/meta_data_fiter/engine_registry.py) are both lazy, though, so their
# warm_up_* calls are what make first-use costs (a model download-if-missing
# check; a ~6s index build or ~1.3s cache load) happen at startup instead of
# blocking the first live request.
from api.endpoints import router
from agents.image_pii.helpers import warm_up_image_pii_engine
from agents.meta_data_fiter.engine_registry import warm_up_commercial_engine
from config import settings

logger = logging.getLogger("api.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Startup: loading commercial search index (cache/, rebuilds if data changed)...")
    warm_up_commercial_engine()
    logger.info("Commercial search index ready.")

    if settings.ENABLE_IMAGE_PII and settings.WARM_UP_PII_ON_STARTUP:
        logger.info("Startup: verifying local image-PII model (downloads only if missing)...")
        warm_up_image_pii_engine()
        logger.info("Image PII model check complete.")
    else:
        logger.info(
            "Skipping image-PII warm-up at startup (disabled or WARM_UP_PII_ON_STARTUP=False); "
            "it will load lazily on first use instead, if enabled."
        )
    yield


app = FastAPI(title="Egyptian Drug Database Pipeline API", lifespan=lifespan)

app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


# Run from the `data/` directory with:
#   uvicorn api.app:app --reload
