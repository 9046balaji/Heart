"""
LangChain Gateway - Enhanced LLM interaction using LangChain framework.

This module replaces the custom LLMGateway with LangChain implementation
for better provider abstraction, retry mechanisms, and observability integration.

Features:
- Standardized interface for multiple LLM providers (Gemini, Ollama)
- Built-in retry mechanisms and error handling
- Easy model switching and experimentation
- Integration with LangSmith for observability
"""

import os
import asyncio
from typing import Optional, Dict, Any
import logging

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

logger = logging.getLogger(__name__)


class LangChainGateway:
    """
    Enhanced LLM Gateway using LangChain framework.
    
    Responsibilities:
    1. Provider abstraction (Gemini, Ollama)
    2. Standardized prompt templating
    3. Retry mechanisms and error handling
    4. Easy model switching
    """
    
    def __init__(
        self,
        primary_provider: Optional[str] = None,
        fallback_enabled: bool = True,
    ):
        """
        Initialize LangChain Gateway.
        
        Args:
            primary_provider: "gemini" or "ollama" (default from env)
            fallback_enabled: If True, fall back to Ollama on Gemini failure
        """
        self.primary_provider = primary_provider or os.getenv("LLM_PROVIDER", "gemini")
        self.fallback_enabled = fallback_enabled
        
        # Initialize LLM models
        self.gemini_model = None
        self.ollama_model = None
        
        # Check provider availability and initialize
        self.gemini_available = self._init_gemini()
        self.ollama_available = self._init_ollama()
        
        logger.info(
            f"LangChainGateway initialized: primary={self.primary_provider}, "
            f"gemini={self.gemini_available}, ollama={self.ollama_available}"
        )
    
    def _init_gemini(self) -> bool:
        """Initialize Google Gemini model."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "your-google-api-key-here":
            logger.warning("Google API key not configured")
            return False
        
        try:
            self.gemini_model = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=api_key,
                temperature=0.7
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini model: {e}")
            return False
    
    def _init_ollama(self) -> bool:
        """Initialize Ollama model."""
        try:
            self.ollama_model = ChatOllama(
                model=os.getenv("OLLAMA_MODEL", "gemma3:1b"),
                temperature=0.7,
                timeout=120.0
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama model: {e}")
            return False
    
    def create_chain(self, system_prompt: str):
        """
        Create a LangChain chain with system prompt.
        
        Args:
            system_prompt: System prompt for the LLM
            
        Returns:
            LangChain Runnable sequence
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}")
        ])
        
        # Select model based on availability
        model = self.gemini_model if self.primary_provider == "gemini" and self.gemini_available else self.ollama_model
        
        return prompt | model | StrOutputParser()
    
    async def generate(
        self,
        prompt: str,
        content_type: str = "general",
        **kwargs
    ) -> str:
        """
        Generate response with automatic safety processing.
        
        Args:
            prompt: The prompt to send to the LLM
            content_type: "medical", "nutrition", or "general"
            **kwargs: Additional parameters
            
        Returns:
            Generated response
        """
        logger.info(
            f"LangChainGateway.generate: type={content_type}, "
            f"provider={self.primary_provider}"
        )
        
        try:
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
            
            chain = self.create_chain(system_prompts.get(content_type, system_prompts["general"]))
            response = await chain.ainvoke({"input": prompt})
            return response
            
        except Exception as e:
            logger.error(f"LangChain generation failed: {e}")
            
            # Try fallback if enabled
            if self.fallback_enabled and self.ollama_available and self.primary_provider != "ollama":
                logger.info("Falling back to Ollama")
                self.primary_provider = "ollama"
                chain = self.create_chain(system_prompts.get(content_type, system_prompts["general"]))
                response = await chain.ainvoke({"input": prompt})
                return response
            else:
                raise RuntimeError(f"LLM generation failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get gateway status for health checks."""
        return {
            "primary_provider": self.primary_provider,
            "gemini_available": self.gemini_available,
            "ollama_available": self.ollama_available,
            "fallback_enabled": self.fallback_enabled,
            "ready": self.gemini_available or self.ollama_available
        }