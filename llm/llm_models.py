from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from llm.helpers import Helpers
from config import settings

class Llm :
    routers_list = ["anthropic","gemini","gpt","groq","ollama"]

    def __init__(self,temp:float=0):
        self.temp = temp

    def get_model(self, router: str, model: str):
        router = Helpers.validate_router(router)

        providers = {
            "anthropic": Llm.anthropic,
            "gemini": Llm.gemini,
            "groq": Llm.groq,
            "ollama": Llm.ollama,
            "gpt": Llm.gpt,
        }

        return providers[router](model,self.temp)

    # 0. Anthropic Claude
    @staticmethod
    def anthropic(model: str, temp: float):
        return ChatAnthropic(
        model=model,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=temp,
        )


# 1. Google Gemini
    @staticmethod
    def gemini(model: str, temp: float):
        return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.GEMINI_API,
        temperature=temp,
        )


    # 2. Groq
    @staticmethod
    def groq(model: str, temp: float):
        return ChatGroq(
        model=model,
        api_key=settings.GROQ_API,
        temperature=temp,
        )


    # 3. Local Ollama
    @staticmethod
    def ollama(model: str, temp: float):
        return ChatOllama(
        model=model,
        base_url=settings.OLLAMA_PATH,
        temperature=temp,
        )


    # 4. OpenAI GPT
    @staticmethod
    def gpt(model: str, temp: float):
        return ChatOpenAI(
        model=model,
        api_key=settings.GPT_API,
        temperature=temp,
        )
    
client_llm = Llm(temp=0.1)