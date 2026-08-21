from llm.fallback import FallBack

PRIMARY_ROUTER = "groq"
PRIMARY_MODEL = "llama-3.1-8b-instant"

SECONDARY_ROUTER = "gpt"
SECONDARY_MODEL = "gpt-4o-mini"

FALLBACK_ORDER = [PRIMARY_ROUTER, SECONDARY_ROUTER]


fallback_kwargs = {
    f"llm_{PRIMARY_ROUTER}": PRIMARY_MODEL,
    f"llm_{SECONDARY_ROUTER}": SECONDARY_MODEL
}

fallback_client = FallBack(**fallback_kwargs)