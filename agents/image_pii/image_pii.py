import base64
import io
import logging

from PIL import Image

from config import settings
from models.state import State
from agents.image_pii.helpers import _get_image_pii_engine

logger = logging.getLogger(__name__)


def _decode_data_uri(image: str) -> bytes | None:
    """Decode a "data:<mime>;base64,<payload>" string to raw bytes, or None
    if `image` isn't one. A plain URL is intentionally NOT fetched here: this
    node runs inside the API backend, so downloading a caller-supplied URL
    server-side would be a request-forgery (SSRF) risk for a path nothing in
    this app currently produces (streamlit_app.py always uploads a base64
    data URI) -- an unsupported source is blocked, never fetched or forwarded
    unredacted."""
    if not image.startswith("data:") or ";base64," not in image:
        return None

    _, _, payload = image.partition(";base64,")
    try:
        return base64.b64decode(payload)
    except Exception:
        return None


def image_pii(state: State) -> dict:
    """Redact PII (faces, text-based identifiers found via OCR + NER) from an
    incoming image before it ever reaches image_describer's vision LLM call.

    Writes `image_cleaned` (a redacted "data:image/jpeg;base64,..." URI, or
    None) and `image_redaction_mode` describing what happened. Always fails
    closed: any missing input, unsupported source, unavailable engine, or
    redaction error blocks the image (image_cleaned=None) rather than risking
    an unredacted image reaching the LLM.
    """
    image = state.get("image")
    if not image:
        return {"image_cleaned": None, "image_redaction_mode": "no_image"}

    if not settings.ENABLE_IMAGE_PII:
        return {"image_cleaned": image, "image_redaction_mode": "disabled"}

    image_bytes = _decode_data_uri(image)
    if image_bytes is None:
        logger.error("image_pii: unsupported image source (not a base64 data URI); blocking.")
        return {"image_cleaned": None, "image_redaction_mode": "blocked_unsupported_source"}

    image_redactor = _get_image_pii_engine()
    if image_redactor is None:
        # Fail closed: never forward an unredacted image to the vision LLM.
        return {"image_cleaned": None, "image_redaction_mode": "blocked_no_redactor"}

    try:
        pil_image = Image.open(io.BytesIO(image_bytes))

        redacted = image_redactor.redact(image=pil_image, fill="black")
        if redacted.mode != "RGB":
            # JPEG can't encode alpha; RGBA/P/etc inputs (e.g. PNG screenshots)
            # would otherwise raise here and fall into the fail-closed branch.
            redacted = redacted.convert("RGB")

        buffer = io.BytesIO()
        redacted.save(buffer, format="JPEG")
        clean_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return {
            "image_cleaned": f"data:image/jpeg;base64,{clean_b64}",
            "image_redaction_mode": "presidio_redacted",
        }
    except Exception as e:
        logger.error("image_pii: redaction failed, blocking image: %s", e)
        return {"image_cleaned": None, "image_redaction_mode": "blocked_after_error"}
