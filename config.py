import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API = os.getenv("GEMINI_API")
    GROQ_API = os.getenv("GROQ_API")
    OLLAMA_PATH = os.getenv("OLLAMA_PATH", "http://localhost:11434")
    GPT_API = os.getenv("GPT_API")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


settings = Settings()
