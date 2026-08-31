from llm.prompt_loader import load_prompt

SYSTEM_PROMPT_QUERY_MERGER = load_prompt("query_merger_prompt.md")


def human_prompt_query_merger(description, image_type, is_readable, eng_query, chat_history):
    return f"""
description: {description}
image_type: {image_type}
is_readable: {is_readable}
eng_query: {eng_query}
chat_history: {chat_history}
"""
