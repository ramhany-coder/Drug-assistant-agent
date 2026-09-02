from llm.fallback import FallBack

PRIMARY_ROUTER = "anthropic"
PRIMARY_MODEL = "claude-sonnet-5"

SECONDARY_ROUTER = "groq"
SECONDARY_MODEL = "openai/gpt-oss-120b"

TERTIARY_ROUTER = "gpt"
TERTIARY_MODEL = "gpt-4o-mini"

OLLAMA_ROUTER = "ollama"
OLLAMA_MODEL = "llama3.2:1b"

FALLBACK_ORDER = [SECONDARY_ROUTER]  # Groq only for now -- anthropic/gpt creds not configured


fallback_kwargs = {
    f"llm_{PRIMARY_ROUTER}": PRIMARY_MODEL,
    f"llm_{SECONDARY_ROUTER}": SECONDARY_MODEL,
    f"llm_{TERTIARY_ROUTER}": TERTIARY_MODEL,
    f"llm_{OLLAMA_ROUTER}": OLLAMA_MODEL,
}

fallback_client = FallBack(**fallback_kwargs)