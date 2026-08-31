FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .

# No system deps to compile here today (rapidfuzz, pydantic-core, uvicorn's
# httptools/uvloop, and pyarrow for streamlit all ship manylinux wheels) --
# unlike the Advanced-multi-model-Safety-Eng.-RAG-project sibling, this app
# has no torch/sentencepiece/hnswlib, so no build-essential stage is needed.
RUN pip install --prefix=/install -r requirements.txt

FROM python:3.12-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=/app/packages

WORKDIR /app

# curl/ca-certificates: container healthcheck only. tesseract-ocr: the image
# PII redactor (agents/image_pii) OCRs uploaded photos to find text-based
# identifiers before image_describer's vision LLM call ever sees them --
# pytesseract only wraps that CLI, it doesn't ship it.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tesseract-ocr \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install/lib/python3.12/site-packages /app/packages

COPY . .

# ANTHROPIC_API_KEY, GROQ_API, GPT_API, GEMINI_API are read via os.getenv in
# config.py (GROQ_API is validated at import time, the rest fail lazily on
# first use) -- supply them as env vars / secrets at deploy time, they are
# deliberately not baked into the image.
ENV PORT=8080

# config.py's own default (http://localhost:11434) resolves to this container
# itself, not the host running it -- host.docker.internal is reachable from a
# container out of the box on Docker Desktop (Windows/Mac); on native Linux
# Docker Engine it needs `--add-host=host.docker.internal:host-gateway` at
# `docker run` time. Override with a real Ollama host for other deployments.
ENV OLLAMA_PATH=http://host.docker.internal:11434

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "python -m uvicorn api.app:app --host 0.0.0.0 --port ${PORT}"]
