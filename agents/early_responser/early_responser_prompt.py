from llm.prompt_loader import load_prompt

SYSTEM_PROMPT_EARLY_RESPONSER = load_prompt("responder_prompt.md")


def human_prompt_early_responser (query,user_language,chat_history,content):
    return f"""
user's query: {query}
user's language: {user_language}
chat history: {chat_history}
content: {content}
"""

