from llm.fallback import FallBack

PRIMARY_ROUTER = "anthropic"
PRIMARY_MODEL = "claude-sonnet-5"

SECONDARY_ROUTER = "groq"
SECONDARY_MODEL = "openai/gpt-oss-120b"

TERTIARY_ROUTER = "gpt"
TERTIARY_MODEL = "gpt-4o-mini"

FALLBACK_ORDER = [PRIMARY_ROUTER, SECONDARY_ROUTER, TERTIARY_ROUTER]


fallback_kwargs = {
    f"llm_{PRIMARY_ROUTER}": PRIMARY_MODEL,
    f"llm_{SECONDARY_ROUTER}": SECONDARY_MODEL,
    f"llm_{TERTIARY_ROUTER}": TERTIARY_MODEL,
}

fallback_client = FallBack(**fallback_kwargs)