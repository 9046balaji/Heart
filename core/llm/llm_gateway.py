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
import re
from typing import Optional, AsyncGenerator, Dict, Any

# Import PromptRegistry for centralized prompt management
from core.prompts.registry import get_prompt

# Import LangChain components
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    ChatOpenAI = None
    OPENAI_AVAILABLE = False
    logging.getLogger(__name__).warning("langchain-openai not installed. OpenAI/OpenRouter features disabled.")
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# LangFuse imports (optional - for observability)
# Only import langfuse if explicitly enabled to avoid auth warnings
import os
_langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"

if _langfuse_enabled:
    try:
        from langfuse import observe
        LANGFUSE_AVAILABLE = True
        logging.getLogger(__name__).info("Langfuse observability enabled")
    except ImportError:
        LANGFUSE_AVAILABLE = False
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        logging.getLogger(__name__).warning("langfuse not installed. Observability features disabled.")
else:
    LANGFUSE_AVAILABLE = False
    # Create a no-op decorator when langfuse is disabled
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
        if openrouter_api_key and OPENAI_AVAILABLE and ChatOpenAI is not None:
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
        if openrouter_gemini_api_key and OPENAI_AVAILABLE and ChatOpenAI is not None:
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

        # Initialize Google Gemini via LangChain (if USE_GEMINI=true and available)
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
            
        # Initialize Ollama
        try:
            self.ollama = ChatOllama(
                model=os.getenv("OLLAMA_MODEL", "gemma3:1b"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama: {e}")
            self.ollama = None

        # Initialize Local Llama Server (MedGemma via OpenAI-compatible API)
        if OPENAI_AVAILABLE and ChatOpenAI is not None:
            try:
                self.llama_local = ChatOpenAI(
                    model=os.getenv("LLAMA_LOCAL_MODEL", "medgemma-4b-it"),
                    api_key=os.getenv("LLAMA_LOCAL_API_KEY", "sk-no-key-required"),
                    base_url=os.getenv("LLAMA_LOCAL_BASE_URL", "http://127.0.0.1:8090/v1"),
                    temperature=float(os.getenv("LLAMA_LOCAL_TEMPERATURE", "0.7")),
                    max_tokens=int(os.getenv("LLAMA_LOCAL_MAX_TOKENS", "2048")),
                )
                logger.info(f"[SUCCESS] Local Llama Server initialized at {os.getenv('LLAMA_LOCAL_BASE_URL', 'http://127.0.0.1:8090/v1')}")
            except Exception as e:
                logger.warning(f"Failed to initialize Local Llama Server: {e}")
                self.llama_local = None
        else:
            self.llama_local = None
            logger.warning("langchain-openai not available - Local Llama Server disabled")

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
        elif provider == "llama-local":
            if self.llama_local:
                return self.llama_local
            else:
                logger.warning("Local Llama Server not configured, falling back to Ollama")
                return self.ollama
        elif provider == "gemini" and self.gemini:
            return self.gemini
        # Fallback to llama-local if available, otherwise Ollama
        if self.llama_local:
            return self.llama_local
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
    
    def _contains_pii(self, text: str) -> bool:
        """
        Detect if text contains Personally Identifiable Information (PII).
        
        Patterns checked:
        - Social Security Number (XXX-XX-XXXX)
        - Email addresses
        - Phone numbers (XXX-XXX-XXXX, (XXX) XXX-XXXX)
        - Medical record numbers
        - Health insurance IDs
        
        Args:
            text: Text to analyze for PII
            
        Returns:
            True if PII detected, False otherwise
        """
        if not text:
            return False
        
        # Social Security Number pattern (XXX-XX-XXXX)
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        if re.search(ssn_pattern, text):
            logger.warning("PII detected: SSN pattern found")
            return True
        
        # Email address pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, text):
            logger.debug("PII detected: Email found")
            return True
        
        # US Phone number patterns
        phone_patterns = [
            r'\b\d{3}-\d{3}-\d{4}\b',  # XXX-XXX-XXXX
            r'\b\(\d{3}\)\s*\d{3}-\d{4}\b',  # (XXX) XXX-XXXX
            r'\b\+1\s*\d{3}-\d{3}-\d{4}\b',  # +1 XXX-XXX-XXXX
            r'\b\d{3}\.\d{3}\.\d{4}\b',  # XXX.XXX.XXXX
        ]
        for pattern in phone_patterns:
            if re.search(pattern, text):
                logger.debug("PII detected: Phone number found")
                return True
        
        # Medical record number (MRN) pattern - typically 6-10 digits
        mrn_pattern = r'\bMRN\s*[:\s]+\d{6,10}\b'
        if re.search(mrn_pattern, text, re.IGNORECASE):
            logger.warning("PII detected: Medical Record Number found")
            return True
        
        # Health Insurance ID patterns
        insurance_patterns = [
            r'\bMember\s*ID\s*[:\s]+[A-Z0-9]{8,}\b',
            r'\bPolicy\s*#\s*[:\s]+\d{6,}\b',
            r'\bInsurance\s*ID\s*[:\s]+[A-Z0-9]{8,}\b',
        ]
        for pattern in insurance_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning("PII detected: Insurance ID found")
                return True
        
        return False
    
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
        
        Automatic PII Detection: If PII is detected in the prompt, automatically
        switches to Ollama (on-premise) instead of external LLM providers for privacy.

        Args:
            prompt: The prompt to send to the LLM
            content_type: "medical", "nutrition", or "general"
            user_id: Optional user ID for tracing and provider selection

        Returns:
            Generated response with safety processing applied
        """
        # Check for PII and auto-select provider
        user_provider = self._get_user_provider(user_id)
        
        if self._contains_pii(prompt):
            logger.warning(
                f"PII detected in prompt - forcing privacy-mode provider (Ollama). "
                f"Original provider: {user_provider}"
            )
            user_provider = "ollama"  # Force Ollama for PII-containing prompts
        
        try:
            raw_response = await self._execute_generation(
                user_provider, prompt, content_type
            )
        except Exception as e:
            logger.warning(f"User provider '{user_provider}' failed: {e}")
            raise e  # Raise original error

        # Apply Guardrails ✅
        return self.guardrails.process_output(
            raw_response, {"type": content_type, "user_id": user_id}
        )

    async def _execute_generation(
        self, provider: str, prompt: str, content_type: str
    ) -> str:
        model = self._get_model(provider)

        # Apply appropriate system prompt based on content type using PromptRegistry
        system_prompts = {
            "medical": get_prompt("llm_gateway", "medical"),
            "nutrition": get_prompt("llm_gateway", "nutrition"),
            "general": get_prompt("llm_gateway", "general"),
        }

        # Create Chain with LangChain
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

        # Execute
        raw_response = await chain.ainvoke({"input": prompt})

        return raw_response

    async def generate_stream(
        self, prompt: str, content_type: str = "general", user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Streaming generation for chat interfaces.
        Respects user's provider selection.
        
        Automatic PII Detection: If PII is detected in the prompt, automatically
        switches to Ollama (on-premise) instead of external LLM providers for privacy.
        """
        # Check for PII and auto-select provider
        user_provider = self._get_user_provider(user_id)
        
        if self._contains_pii(prompt):
            logger.warning(
                f"PII detected in streaming prompt - forcing privacy-mode provider (Ollama). "
                f"Original provider: {user_provider}"
            )
            user_provider = "ollama"  # Force Ollama for PII-containing prompts
        
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

        # Create Chain with LangChain
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

    @observe(name="llm-multimodal")
    async def generate_multimodal(
        self, 
        prompt: str, 
        image_data: str, 
        content_type: str = "medical", 
        user_id: Optional[str] = None
    ) -> str:
        """
        Generate text from multimodal input (text + image).
        
        Args:
            prompt: Text prompt
            image_data: Base64 encoded image string or URL
            content_type: Content type for system prompt selection
            user_id: User ID for tracing
            
        Returns:
            Generated response
        """
        from langchain_core.messages import HumanMessage, SystemMessage
        
        user_provider = self._get_user_provider(user_id)
        model = self._get_model(user_provider)
        
        # System prompt from PromptRegistry
        system_msg = SystemMessage(content=get_prompt("llm_gateway", "multimodal_medical"))
        
        # Prepare content
        # Check if image_data is a URL or base64
        if image_data.startswith("http"):
            image_url = image_data
        else:
            # Assume base64, ensure prefix
            if not image_data.startswith("data:image"):
                image_url = f"data:image/jpeg;base64,{image_data}"
            else:
                image_url = image_data
                
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
        
        human_msg = HumanMessage(content=content)
        
        try:
            # Direct invocation of the model with messages
            response = await model.ainvoke([system_msg, human_msg])
            
            # Handle response types (some return string, some AIMessage)
            if hasattr(response, "content"):
                return response.content
            return str(response)
            
        except Exception as e:
            logger.error(f"Multimodal generation failed with provider {user_provider}: {e}")
            raise e

    def get_status(self) -> Dict[str, Any]:
        """Return the health status of the LLM Gateway."""
        return {
            "status": "online" if any([getattr(self, 'llama_local', None), self.openrouter, self.openrouter_gemini, self.gemini, self.ollama]) else "degraded",
            "provider": self.primary_provider,
            "model": os.getenv("OLLAMA_MODEL", "gemma3:1b"),
            "openrouter_available": self.openrouter is not None,
            "openrouter_gemini_available": self.openrouter_gemini is not None,
            "gemini_available": self.gemini is not None,
            "ollama_available": self.ollama is not None,
        }


# Singleton Accessor
_gateway_instance = None


def get_llm_gateway() -> LLMGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = LLMGateway()
    return _gateway_instance