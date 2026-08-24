import logging

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from api.endpoints import router

app = FastAPI(title="Egyptian Drug Database Pipeline API")

app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


# Run from the `data/` directory with:
#   uvicorn api.app:app --reload
