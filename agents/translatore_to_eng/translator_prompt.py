from llm.prompt_loader import load_prompt

SYSTEM_PROMPT_TRANSLATOR_TO_ENG = load_prompt("translator_prompt_constrained.md")


def human_prompt_translator_to_eng(query, chat_history):
    return f"""
user query :
{query}

chat history (prior turns, as english query : response):
{chat_history}
"""
