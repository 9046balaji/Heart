# The Winner: A Consolidated Strategy

You should NOT choose just one. You should merge them into a single `llm_gateway.py` and delete the others.

## Why?

- If you use only `langchain_gateway.py`, you lose the observability from observable....
- If you use only observable..., you lose the robustness of LangChain.
- If you keep all three, developers won't know which one to import.

## 🚀 Implementation Plan (The "Best of All Worlds" File)

Here is the code for the Unified LLM Gateway. It combines:
- ✅ LangChain (for stability)
- ✅ Langfuse (for debugging)
- ✅ Guardrails (for safety)

### Step 1: Replace contents of `nlp-service/core/llm_gateway.py` with this:

```python
import os
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langfuse.decorators import observe
from core.guardrails import SafetyGuardrail

logger = logging.getLogger(__name__)

class LLMGateway:
    """
    The Single Source of Truth for LLM interactions.
    Combines LangChain execution with Langfuse observability and Safety Guardrails.
    """
    
    def __init__(self):
        self.primary_provider = os.getenv("LLM_PROVIDER", "gemini")
        self.guardrails = SafetyGuardrail()
        
        # Initialize Models via LangChain
        self.gemini = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            convert_system_message_to_human=True
        )
        self.ollama = ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "gemma3:1b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )

    def _get_model(self, provider: str):
        if provider == "ollama":
            return self.ollama
        return self.gemini

    @observe(name="llm-generation")  # ✅ Langfuse Observability
    async def generate(self, prompt: str, content_type: str = "general") -> str:
        """
        Generate text with automatic fallback and safety checks.
        """
        try:
            return await self._execute_generation(self.primary_provider, prompt, content_type)
        except Exception as e:
            logger.warning(f"Primary provider {self.primary_provider} failed: {e}")
            # Fallback Logic
            if self.primary_provider != "ollama":
                logger.info("🔄 Falling back to Ollama...")
                return await self._execute_generation("ollama", prompt, content_type)
            raise e

    async def _execute_generation(self, provider: str, prompt: str, content_type: str) -> str:
        model = self._get_model(provider)
        
        # 1. Create Chain
        chain = (
            ChatPromptTemplate.from_template("{input}") 
            | model 
            | StrOutputParser()
        )
        
        # 2. Execute
        raw_response = await chain.ainvoke({"input": prompt})
        
        # 3. Apply Guardrails ✅
        return self.guardrails.process_output(raw_response, {"type": content_type})

    async def generate_stream(self, prompt: str, content_type: str = "general") -> AsyncGenerator[str, None]:
        """Streaming generation for chat interfaces."""
        model = self._get_model(self.primary_provider)
        chain = ChatPromptTemplate.from_template("{input}") | model | StrOutputParser()
        
        async for chunk in chain.astream({"input": prompt}):
            yield chunk

# Singleton Accessor
_gateway_instance = None

def get_llm_gateway() -> LLMGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = LLMGateway()
    return _gateway_instance
```
