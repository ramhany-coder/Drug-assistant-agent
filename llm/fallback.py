from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from llm.helpers import Helpers
from llm.llm_models import client_llm

class FallBack:
    def __init__(
        self,
        llm_ollama: Optional[str] = None,
        llm_gpt: Optional[str] = None,
        llm_gemini: Optional[str] = None,
        llm_groq: Optional[str] = None,
    ):
        # Map the router names to their specific model strings
        self.llms: Dict[str, str] = {}
        
        if llm_ollama:
            self.llms["ollama"] = llm_ollama
        if llm_gpt:
            self.llms["gpt"] = llm_gpt
        if llm_gemini:
            self.llms["gemini"] = llm_gemini
        if llm_groq:
            self.llms["groq"] = llm_groq
            

    def invoke(self, message: Any, fallback_order: List[str]) -> str:
        """
        Entry point 1: Regular text generation.
        Attempts to invoke models in the provided sequence. 
        Falls back to the next router if one fails.
        """
        errors = []
        
        for router in fallback_order:
            try:
                print(f"Attempting regular generation using: {router}...")
                router = Helpers.validate_router(router)
                
                if router not in self.llms:
                    raise ValueError(f"No model string configured for '{router}' during initialization.")
                
                model_name = self.llms[router]
                llm = client_llm.get_model(router, model_name)
                
                response = llm.invoke(message)
                return response.content
                
            except Exception as e:
                print(f"Router '{router}' failed: {e}")
                errors.append(f"{router} error: {str(e)}")
                continue
                
        # If the loop finishes without returning, all models failed
        raise RuntimeError(f"All fallback models failed. Details: {errors}")

    def constrained_invoke(self, message: Any, fallback_order: List[str] , constraine_model: Optional[BaseModel] = None) -> dict:
        """
        Entry point 2: Constrained/structured generation.
        Forces the output to match the Pydantic schema, trying models in sequence.
        Returns the parsed attributes as a dictionary.
        """
        if not constraine_model:
            raise ValueError("Cannot perform constrained invoke: 'constraine_model' was not provided.")

        errors = []
        
        for router in fallback_order:
            try:
                print(f"Attempting constrained generation using: {router}...")
                router = Helpers.validate_router(router)
                
                if router not in self.llms:
                    raise ValueError(f"No model string configured for '{router}' during initialization.")
                    
                model_name = self.llms[router]
                llm = client_llm.get_model(router, model_name)
                
                # Bind the Pydantic schema to the LLM
                structured_llm = llm.with_structured_output(constraine_model)
                pydantic_response = structured_llm.invoke(message)
                
                # Return as a dictionary
                return pydantic_response.model_dump()
                
            except Exception as e:
                print(f"Constrained router '{router}' failed: {e}")
                errors.append(f"{router} error: {str(e)}")
                continue
                
        # If the loop finishes without returning, all models failed
        raise RuntimeError(f"All fallback models failed to generate valid constrained output. Details: {errors}")


