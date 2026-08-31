from llm.prompt_loader import load_prompt

SYSTEM_PROMPT_IMAGE_DESCRIBER = load_prompt("image_describer_prompt.md")


def human_prompt_image_describer(eng_query):
    return f"""
image caption (if any), already translated to English: {eng_query}
"""
