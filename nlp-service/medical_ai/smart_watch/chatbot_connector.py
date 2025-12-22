"""
Chatbot Connector - Integrates with Gemini and Ollama

This module provides a unified interface to multiple LLM backends
with automatic fallback support. Gemini is used as primary (cloud),
Ollama as fallback (local/offline).
"""

import os
import logging
import asyncio
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """
    Response from chatbot.

    Attributes:
        content: The generated text response
        model: Name of the model used
        tokens_used: Number of tokens consumed
        latency_ms: Response time in milliseconds
        success: Whether the generation was successful
        error: Error message if failed
    """

    content: str
    model: str
    tokens_used: int = 0
    latency_ms: float = 0
    success: bool = True
    error: Optional[str] = None


class BaseChatbot(ABC):
    """Abstract base class for chatbot implementations."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> ChatResponse:
        """Generate a response from the LLM."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this chatbot backend is available."""


class GeminiChatbot(BaseChatbot):
    """
    Google Gemini API integration.

    Uses gemini-1.5-flash for fast, cost-effective responses.
    Requires GEMINI_API_KEY environment variable.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize Gemini chatbot.

        Args:
            api_key: Optional API key. Falls back to GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = "gemini-1.5-flash"
        self._client = None

        if self.api_key:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self.model_name)
                logger.info("Gemini chatbot initialized")
            except ImportError:
                logger.warning("google-generativeai not installed")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")

    def is_available(self) -> bool:
        """Check if Gemini is available."""
        return self._client is not None

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> ChatResponse:
        """
        Generate response using Gemini.

        Args:
            system_prompt: System instructions for the model
            user_prompt: User's message/query
            temperature: Creativity (0.0-1.0)
            max_tokens: Maximum response length

        Returns:
            ChatResponse with generated content
        """
        if not self._client:
            return ChatResponse(
                content="",
                model=self.model_name,
                success=False,
                error="Gemini client not initialized",
            )

        start = time.time()

        try:
            # Combine prompts for Gemini
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

            # Generate response (run in thread to not block)
            response = await asyncio.to_thread(
                self._client.generate_content,
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )

            latency = (time.time() - start) * 1000

            return ChatResponse(
                content=response.text,
                model=self.model_name,
                latency_ms=latency,
                success=True,
            )

        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            return ChatResponse(
                content="", model=self.model_name, success=False, error=str(e)
            )


class OllamaChatbot(BaseChatbot):
    """
    Local Ollama integration for offline use.

    Connects to locally running Ollama instance.
    Default model is llama3.2 but can be configured.
    """

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "llama3.2"
    ):
        """
        Initialize Ollama chatbot.

        Args:
            base_url: URL of Ollama server
            model: Model name to use
        """
        self.base_url = base_url
        self.model = model
        self._available = False
        self._check_availability()

    def _check_availability(self):
        """Check if Ollama is running."""
        try:
            import requests

            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            self._available = response.status_code == 200
            if self._available:
                logger.info(f"Ollama available at {self.base_url}")
        except Exception:
            logger.warning("Ollama not available")
            self._available = False

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        return self._available

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> ChatResponse:
        """
        Generate response using Ollama.

        Args:
            system_prompt: System instructions
            user_prompt: User's message
            temperature: Creativity
            max_tokens: Maximum response length

        Returns:
            ChatResponse with generated content
        """
        if not self._available:
            return ChatResponse(
                content="",
                model=self.model,
                success=False,
                error="Ollama not available",
            )

        start = time.time()

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                }

                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        latency = (time.time() - start) * 1000

                        return ChatResponse(
                            content=data.get("response", ""),
                            model=self.model,
                            latency_ms=latency,
                            success=True,
                        )
                    else:
                        return ChatResponse(
                            content="",
                            model=self.model,
                            success=False,
                            error=f"Ollama returned {response.status}",
                        )

        except ImportError:
            logger.error("aiohttp not installed")
            return ChatResponse(
                content="",
                model=self.model,
                success=False,
                error="aiohttp not installed",
            )
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            return ChatResponse(
                content="", model=self.model, success=False, error=str(e)
            )


class ChatbotManager:
    """
    Manages multiple chatbot backends with fallback.

    Tries Gemini first (better quality), falls back to Ollama (offline).
    Provides a unified interface regardless of which backend is used.

    Example:
        manager = ChatbotManager()
        response = await manager.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="What is a healthy heart rate?"
        )
        print(response.content)
    """

    def __init__(self, gemini_api_key: str = None, ollama_url: str = None):
        """
        Initialize chatbot manager.

        Args:
            gemini_api_key: Optional Gemini API key
            ollama_url: Optional Ollama server URL
        """
        self.gemini = GeminiChatbot(api_key=gemini_api_key)
        self.ollama = OllamaChatbot(
            base_url=ollama_url or "http://localhost:11434", model="gemma3:1b"
        )

        # Determine primary backend
        if self.gemini.is_available():
            self.primary = self.gemini
            self.fallback = self.ollama
            logger.info("Using Gemini as primary chatbot")
        elif self.ollama.is_available():
            self.primary = self.ollama
            self.fallback = None
            logger.info("Using Ollama as primary chatbot")
        else:
            self.primary = None
            self.fallback = None
            logger.warning("No chatbot backend available!")

    def is_available(self) -> bool:
        """Check if any chatbot is available."""
        return self.primary is not None

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> ChatResponse:
        """
        Generate response with automatic fallback.

        Args:
            system_prompt: System instructions
            user_prompt: User's message
            temperature: Creativity
            max_tokens: Maximum response length

        Returns:
            ChatResponse from primary or fallback backend
        """
        if not self.primary:
            return ChatResponse(
                content="I'm unable to generate a response right now. Please check your connection.",
                model="none",
                success=False,
                error="No chatbot available",
            )

        # Try primary
        response = await self.primary.generate(
            system_prompt, user_prompt, temperature, max_tokens
        )

        # If failed, try fallback
        if not response.success and self.fallback and self.fallback.is_available():
            logger.info("Primary chatbot failed, trying fallback...")
            response = await self.fallback.generate(
                system_prompt, user_prompt, temperature, max_tokens
            )

        return response

    def get_status(self) -> Dict[str, Any]:
        """Get status of all chatbot backends."""
        return {
            "gemini_available": self.gemini.is_available(),
            "ollama_available": self.ollama.is_available(),
            "primary": self.primary.__class__.__name__ if self.primary else "None",
            "fallback": self.fallback.__class__.__name__ if self.fallback else "None",
        }

    def refresh_availability(self) -> None:
        """Recheck availability of all backends."""
        # Re-check Ollama (Gemini doesn't need refresh)
        self.ollama._check_availability()

        # Update primary/fallback
        if self.gemini.is_available():
            self.primary = self.gemini
            self.fallback = self.ollama if self.ollama.is_available() else None
        elif self.ollama.is_available():
            self.primary = self.ollama
            self.fallback = None
        else:
            self.primary = None
            self.fallback = None
