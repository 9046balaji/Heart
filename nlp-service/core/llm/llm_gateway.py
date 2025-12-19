"""
LLM Gateway - Unified implementation combining LangChain, LangFuse, and Guardrails.

This is the ONLY module that should directly call LLM providers (Gemini, Ollama).
All AI generation in the system MUST flow through this gateway.

Features:
- ✅ LangChain (for stability)
- ✅ LangFuse (for debugging)
- ✅ Guardrails (for safety)

Usage:
    from core.llm_gateway import LLMGateway
    
    gateway = LLMGateway()
    response = await gateway.generate(
        prompt="Explain heart health tips",
        content_type="medical"  # Adds medical disclaimer
    )
"""
import os
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# LangFuse imports
try:
    from langfuse.decorators import observe
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    # Define a dummy observe decorator
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Import guardrails for safety processing
from .guardrails import SafetyGuardrail

logger = logging.getLogger(__name__)


class LLMGateway:
    """
    The Single Source of Truth for LLM interactions.
    Combines LangChain execution with LangFuse observability and Safety Guardrails.
    """
    
    def __init__(self):
        self.primary_provider = os.getenv("LLM_PROVIDER", "ollama")
        self.guardrails = SafetyGuardrail()
        self.use_gemini = os.getenv("USE_GEMINI", "false").lower() == "true"
        
        # Initialize Models via LangChain
        if self.use_gemini:
            self.gemini = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                convert_system_message_to_human=True
            )
        else:
            self.gemini = None
            
        self.ollama = ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "gemma3:1b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )

    def _get_model(self, provider: str):
        if provider == "ollama":
            return self.ollama
        elif provider == "gemini" and self.gemini:
            return self.gemini
        # Fallback to Ollama if Gemini is not available
        return self.ollama

    @observe(name="llm-generation")  # ✅ LangFuse Observability
    async def generate(self, prompt: str, content_type: str = "general", user_id: Optional[str] = None) -> str:
        """
        Generate text with automatic fallback and safety checks.
        
        Args:
            prompt: The prompt to send to the LLM
            content_type: "medical", "nutrition", or "general"
            user_id: Optional user ID for tracing
            
        Returns:
            Generated response with safety processing applied
        """
        try:
            raw_response = await self._execute_generation(self.primary_provider, prompt, content_type)
        except Exception as e:
            logger.warning(f"Primary provider {self.primary_provider} failed: {e}")
            # Fallback Logic
            if self.primary_provider != "ollama":
                logger.info("🔄 Falling back to Ollama...")
                raw_response = await self._execute_generation("ollama", prompt, content_type)
            else:
                raise e
        
        # Apply Guardrails ✅
        return self.guardrails.process_output(raw_response, {"type": content_type, "user_id": user_id})

    async def _execute_generation(self, provider: str, prompt: str, content_type: str) -> str:
        model = self._get_model(provider)
        
        # Apply appropriate system prompt based on content type
        system_prompts = {
            "medical": """You are a healthcare AI assistant.
            Provide accurate, empathetic, and safety-conscious responses.
            Always recommend professional medical consultation for serious concerns.
            Never diagnose conditions - only provide information.""",
            "nutrition": """You are a nutrition expert specializing in heart-healthy diets.
            Provide evidence-based nutritional advice.
            Focus on cardiovascular health benefits.""",
            "general": """You are a helpful AI assistant.
            Be friendly, informative, and supportive."""
        }
        
        # 1. Create Chain
        chain = (
            ChatPromptTemplate.from_messages([
                ("system", system_prompts.get(content_type, system_prompts["general"])),
                ("human", "{input}")
            ]) 
            | model 
            | StrOutputParser()
        )
        
        # 2. Execute
        raw_response = await chain.ainvoke({"input": prompt})
        return raw_response

    async def generate_stream(self, prompt: str, content_type: str = "general") -> AsyncGenerator[str, None]:
        """Streaming generation for chat interfaces."""
        model = self._get_model(self.primary_provider)
        
        system_prompts = {
            "medical": """You are a healthcare AI assistant.
            Provide accurate, empathetic, and safety-conscious responses.
            Always recommend professional medical consultation for serious concerns.
            Never diagnose conditions - only provide information.""",
            "nutrition": """You are a nutrition expert specializing in heart-healthy diets.
            Provide evidence-based nutritional advice.
            Focus on cardiovascular health benefits.""",
            "general": """You are a helpful AI assistant.
            Be friendly, informative, and supportive."""
        }
        
        chain = (
            ChatPromptTemplate.from_messages([
                ("system", system_prompts.get(content_type, system_prompts["general"])),
                ("human", "{input}")
            ]) 
            | model 
            | StrOutputParser()
        )
        
        async for chunk in chain.astream({"input": prompt}):
            yield chunk

# Singleton Accessor
_gateway_instance = None

def get_llm_gateway() -> LLMGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = LLMGateway()
    return _gateway_instance