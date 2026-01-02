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
from typing import Optional, AsyncGenerator, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
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

# Global dictionary to store user provider selections
_user_provider_selections: Dict[str, str] = {}


class LLMGateway:
    """
    The Single Source of Truth for LLM interactions.
    Combines LangChain execution with LangFuse observability and Safety Guardrails.
    Supports user-selected providers (Ollama or OpenRouter).
    """

    def __init__(self):
        self.primary_provider = os.getenv("LLM_PROVIDER", "openrouter")
        self.guardrails = SafetyGuardrail()
        self.use_gemini = os.getenv("USE_GEMINI", "false").lower() == "true"

        # Initialize OpenRouter Model via ChatOpenAI (compatible with OpenRouter API)
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_api_key:
            try:
                self.openrouter = ChatOpenAI(
                    model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free"),
                    api_key=openrouter_api_key,
                    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                    temperature=float(os.getenv("OPENROUTER_TEMPERATURE", "0.7")),
                    max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "256")),
                )
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter: {e}")
                self.openrouter = None
        else:
            self.openrouter = None

        # Initialize OpenRouter Gemini Model via ChatOpenAI (Fallback)
        openrouter_gemini_api_key = os.getenv("OPENROUTER_GEMINI_API_KEY")
        if openrouter_gemini_api_key:
            try:
                self.openrouter_gemini = ChatOpenAI(
                    model=os.getenv("OPENROUTER_GEMINI_MODEL", "google/gemma-3-4b-it:free"),
                    api_key=openrouter_gemini_api_key,
                    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                    temperature=float(os.getenv("OPENROUTER_GEMINI_TEMPERATURE", "0.7")),
                    max_tokens=int(os.getenv("OPENROUTER_GEMINI_MAX_TOKENS", "256")),
                )
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter Gemini: {e}")
                self.openrouter_gemini = None
        else:
            self.openrouter_gemini = None

        # Initialize Google Gemini via LangChain (if USE_GEMINI=true)
        if self.use_gemini:
            try:
                self.gemini = ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash",
                    google_api_key=os.getenv("GOOGLE_API_KEY"),
                    convert_system_message_to_human=True,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Google Gemini: {e}")
                self.gemini = None
        else:
            self.gemini = None
        self.ollama = ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "gemma3:1b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    def _get_model(self, provider: str):
        if provider == "openrouter":
            if self.openrouter:
                return self.openrouter
            else:
                logger.warning("OpenRouter not configured, falling back to Ollama")
                return self.ollama
        elif provider == "openrouter-gemini":
            if self.openrouter_gemini:
                return self.openrouter_gemini
            else:
                logger.warning("OpenRouter Gemini not configured, falling back to Ollama")
                return self.ollama
        elif provider == "ollama":
            return self.ollama
        elif provider == "gemini" and self.gemini:
            return self.gemini
        # Fallback to Ollama if provider is not available
        return self.ollama

    def _get_user_provider(self, user_id: Optional[str] = None) -> str:
        """
        Get the provider for a user. Uses user selection if available,
        otherwise falls back to environment configuration.
        
        Args:
            user_id: Optional user ID to get their provider preference
            
        Returns:
            Provider name: 'ollama' or 'openrouter'
        """
        if user_id and user_id in _user_provider_selections:
            return _user_provider_selections[user_id]
        # Fall back to environment default
        return self.primary_provider
    
    def set_user_provider(self, user_id: str, provider: str) -> None:
        """
        Set the LLM provider preference for a user.
        
        Args:
            user_id: User identifier
            provider: Provider to use ('ollama' or 'openrouter')
        """
        if provider not in ['ollama', 'openrouter']:
            raise ValueError(f"Invalid provider: {provider}. Must be 'ollama' or 'openrouter'")
        _user_provider_selections[user_id] = provider
        logger.info(f"Provider '{provider}' set for user: {user_id}")

    @observe(name="llm-generation")  # ✅ LangFuse Observability
    async def generate(
        self, prompt: str, content_type: str = "general", user_id: Optional[str] = None
    ) -> str:
        """
        Generate text with automatic fallback and safety checks.

        Args:
            prompt: The prompt to send to the LLM
            content_type: "medical", "nutrition", or "general"
            user_id: Optional user ID for tracing and provider selection

        Returns:
            Generated response with safety processing applied
        """
        # Get user's preferred provider (or use primary from env)
        user_provider = self._get_user_provider(user_id)
        
        try:
            raw_response = await self._execute_generation(
                user_provider, prompt, content_type
            )
        except Exception as e:
            logger.warning(f"User provider '{user_provider}' failed: {e}")
            # Fallback Logic Chain
            if user_provider == "ollama":
                logger.info("🔄 Ollama failed, falling back to OpenRouter...")
                try:
                    raw_response = await self._execute_generation(
                        "openrouter", prompt, content_type
                    )
                except Exception as e2:
                    logger.warning(f"OpenRouter fallback also failed: {e2}")
                    raise e  # Raise original error
            elif user_provider == "openrouter":
                logger.info("🔄 OpenRouter failed, trying fallback...")
                try:
                    raw_response = await self._execute_generation(
                        "openrouter-gemini", prompt, content_type
                    )
                except Exception as e2:
                    logger.warning(f"OpenRouter Gemini fallback also failed: {e2}")
                    logger.info("🔄 Falling back to Ollama...")
                    try:
                        raw_response = await self._execute_generation(
                            "ollama", prompt, content_type
                        )
                    except Exception as e3:
                        logger.error(f"Ollama fallback also failed: {e3}")
                        raise e
            else:
                raise e  # Raise original error

        # Apply Guardrails ✅
        return self.guardrails.process_output(
            raw_response, {"type": content_type, "user_id": user_id}
        )

    async def _execute_generation(
        self, provider: str, prompt: str, content_type: str
    ) -> str:
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
            Be friendly, informative, and supportive.""",
        }

        # 1. Create Chain
        chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        system_prompts.get(content_type, system_prompts["general"]),
                    ),
                    ("human", "{input}"),
                ]
            )
            | model
            | StrOutputParser()
        )

        # 2. Execute
        raw_response = await chain.ainvoke({"input": prompt})
        return raw_response

    async def generate_stream(
        self, prompt: str, content_type: str = "general", user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Streaming generation for chat interfaces.
        Respects user's provider selection.
        """
        # Get user's preferred provider (or use primary from env)
        user_provider = self._get_user_provider(user_id)
        model = self._get_model(user_provider)

        system_prompts = {
            "medical": """You are a healthcare AI assistant.
            Provide accurate, empathetic, and safety-conscious responses.
            Always recommend professional medical consultation for serious concerns.
            Never diagnose conditions - only provide information.""",
            "nutrition": """You are a nutrition expert specializing in heart-healthy diets.
            Provide evidence-based nutritional advice.
            Focus on cardiovascular health benefits.""",
            "general": """You are a helpful AI assistant.
            Be friendly, informative, and supportive.""",
        }

        chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        system_prompts.get(content_type, system_prompts["general"]),
                    ),
                    ("human", "{input}"),
                ]
            )
            | model
            | StrOutputParser()
        )

        async for chunk in chain.astream({"input": prompt}):
            yield chunk

    def get_status(self) -> Dict[str, Any]:
        """Return the health status of the LLM Gateway."""
        return {
            "status": "online",
            "provider": self.primary_provider,
            "model": os.getenv("OLLAMA_MODEL", "gemma3:1b"),
            "openrouter_available": self.openrouter is not None,
            "openrouter_gemini_available": self.openrouter_gemini is not None,
            "gemini_available": self.gemini is not None,
        }


# Singleton Accessor
_gateway_instance = None


def get_llm_gateway() -> LLMGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = LLMGateway()
    return _gateway_instance
