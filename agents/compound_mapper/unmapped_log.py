"""Appends every component the mapper could not resolve to logs/unmapped_compounds.jsonl.
That file is how compound_aliases.ALIASES grows over time."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "unmapped_compounds.jsonl"


def log_unmapped(component: str, source_product: Optional[str]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "component": component,
        "source_product": source_product,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
