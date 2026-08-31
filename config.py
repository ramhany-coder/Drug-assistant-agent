import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    GEMINI_API = os.getenv("GEMINI_API")
    GROQ_API = os.getenv("GROQ_API")
    OLLAMA_PATH = os.getenv("OLLAMA_PATH", "http://localhost:11434")
    GPT_API = os.getenv("GPT_API")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # Image PII redaction (agents/image_pii), gates the image_describer node.
    # Defaults target Streamlit Community Cloud's free tier (~1GB RAM): the
    # "sm" spaCy pipeline has no word vectors (~13MB) vs "lg" (~560MB, more
    # accurate NER). Override PII_SPACY_MODEL_NAME for a higher-memory host.
    ENABLE_IMAGE_PII = os.getenv("ENABLE_IMAGE_PII", "true").lower() == "true"
    PII_SPACY_MODEL_NAME = os.getenv("PII_SPACY_MODEL_NAME", "en_core_web_sm")
    # Not where the model weights actually live (spaCy installs itself into
    # site-packages) -- just where the "already downloaded" completion marker
    # is recorded, mirroring this repo's models/<name> convention. Never
    # commit this directory: a stale marker with no matching site-packages
    # install makes ensure_spacy_model_downloaded skip a download it still
    # needs to do.
    PII_SPACY_MODEL_DIR = os.getenv("PII_SPACY_MODEL_DIR", "models/pii_spacy")
    # Runs the (first-run-only) model download/check at FastAPI startup
    # (api/app.py's lifespan) instead of on the first live request.
    WARM_UP_PII_ON_STARTUP = os.getenv("WARM_UP_PII_ON_STARTUP", "true").lower() == "true"


settings = Settings()

# GROQ_API is the only credential llm/client.py's FALLBACK_ORDER currently
# exercises (see the comment there: "Groq only for now -- anthropic/gpt
# creds not configured") -- log at import time instead of letting it fail
# silently several calls deep inside the first LLM invocation.
if not settings.GROQ_API:
    logger.error("GROQ_API is not set (check your .env or deployment secrets).")
