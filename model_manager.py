"""Local-cache-first spaCy model loading.

Presidio's image PII redactor (agents/image_pii) needs a spaCy NLP pipeline
installed to run NER over OCR'd image text. Unlike a Hugging Face Hub model,
a spaCy pipeline is an ordinary pip package -- "downloading" it means
pip-installing its wheel into site-packages, not writing files under
`models/`. This module makes that happen at most once per environment by
recording completion under a marker directory, so a later restart (in the
same container/venv) skips both the network call and the pip-install check.
"""
import logging
from pathlib import Path

import spacy

logger = logging.getLogger(__name__)

# Presence of this marker is what "already downloaded" means -- see
# ensure_spacy_model_downloaded for why it's re-checked against the actual
# installed package instead of being trusted blindly.
_DOWNLOAD_COMPLETE_MARKER = ".download_complete"


def is_model_present(marker_dir: str | Path) -> bool:
    return (Path(marker_dir) / _DOWNLOAD_COMPLETE_MARKER).is_file()


def ensure_spacy_model_downloaded(model_name: str, marker_dir: str | Path) -> None:
    """Ensure the spaCy pipeline `model_name` is installed, downloading it
    (via spaCy's own installer) only if it isn't already.

    The marker directory is trusted only together with a live
    `spacy.util.is_package` check: a marker surviving without its matching
    site-packages install (e.g. a fresh container reusing an old volume, or
    the marker directory accidentally committed to git) would otherwise skip
    a download it still needs to do.
    """
    path = Path(marker_dir)

    if is_model_present(path) and spacy.util.is_package(model_name):
        return

    if not spacy.util.is_package(model_name):
        logger.info("spaCy model '%s' not found, downloading...", model_name)
        from spacy.cli import download as spacy_download

        spacy_download(model_name)
        logger.info("spaCy model '%s' downloaded", model_name)

    path.mkdir(parents=True, exist_ok=True)
    (path / _DOWNLOAD_COMPLETE_MARKER).touch()
