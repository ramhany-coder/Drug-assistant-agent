"""Loads a system prompt from its fenced block in prompts/<filename>.md.

Each file under prompts/ holds a title, a short description, a "## The prompt"
heading followed by one fenced ``` block (the text actually sent to the model),
and then worked cases / notes for a human reader. Only the fenced block is ever
sent to a model -- the rest is documentation and must never reach the LLM.
"""

import re
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

_PROMPT_SECTION_RE = re.compile(r"##\s*The prompt.*?```[\w-]*\n(.*?)\n```", re.DOTALL)


@lru_cache(maxsize=None)
def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    text = path.read_text(encoding="utf-8")

    match = _PROMPT_SECTION_RE.search(text)
    if not match:
        raise ValueError(f"{path} has no '## The prompt' fenced block")

    return match.group(1).strip()
