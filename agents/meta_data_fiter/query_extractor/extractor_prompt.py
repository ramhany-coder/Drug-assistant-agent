from llm.prompt_loader import load_prompt

SYSTEM_PROMPT_EXTRACTOR = load_prompt("metadata_extractor_prompt.md")


def human_prompt_extractor(query):
    return f"""
    Human query :
    {query}
    """
