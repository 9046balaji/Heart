"""
LLM Gateway - Single point of control for all LLM interactions.

This is the ONLY module that should directly call LLM providers (Gemini, Ollama).
All AI generation in the system MUST flow through this gateway.

Features:
- Provider abstraction (Gemini, Ollama)
- Automatic fallback to Ollama if Gemini fails
- Built-in safety guardrails (PII redaction, disclaimers)
- Unified logging and metrics
- Streaming support

Usage:
    from core.llm_gateway import LLMGateway
    
    gateway = LLMGateway()
    response = await gateway.generate(
        prompt="Explain heart health tips",
        content_type="medical"  # Adds medical disclaimer
    )
"""
import os
import asyncio
from typing import Optional, AsyncGenerator, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Import guardrails for safety processing
from .guardrails import SafetyGuardrail


class LLMGateway:
    """
    Unified gateway for all LLM model interactions.
    
    Responsibilities:
    1. Provider selection and fallback
    2. Safety guardrail enforcement
    3. Logging and metrics
    4. Streaming support
    """
    
    def __init__(
        self,
        primary_provider: Optional[str] = None,
        fallback_enabled: bool = True,
        guardrails_enabled: bool = True
    ):
        """
        Initialize LLM Gateway.
        
        Args:
            primary_provider: "gemini" or "ollama" (default from env)
            fallback_enabled: If True, fall back to Ollama on Gemini failure
            guardrails_enabled: If True, apply safety guardrails to outputs
        """
        self.primary_provider = primary_provider or os.getenv("LLM_PROVIDER", "gemini")
        self.fallback_enabled = fallback_enabled
        self.guardrails_enabled = guardrails_enabled
        
        # Initialize components
        self.guardrails = SafetyGuardrail() if guardrails_enabled else None
        
        # Check provider availability
        self.gemini_available = self._check_gemini()
        self.ollama_available = self._check_ollama()
        
        logger.info(
            f"LLMGateway initialized: primary={self.primary_provider}, "
            f"gemini={self.gemini_available}, ollama={self.ollama_available}, "
            f"guardrails={guardrails_enabled}"
        )
    
    def _check_gemini(self) -> bool:
        """Check if Gemini API is configured and available."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "your-google-api-key-here":
            return False
        try:
            import google.generativeai as genai
            return True
        except ImportError:
            logger.warning("google-generativeai package not installed")
            return False
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is running locally."""
        try:
            import httpx
            # Quick sync check (non-blocking timeout)
            with httpx.Client(timeout=2.0) as client:
                resp = client.get("http://localhost:11434/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
    
    async def generate(
        self,
        prompt: str,
        content_type: str = "general",
        skip_guardrails: bool = False,
        user_id: Optional[str] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        """
        Generate response with automatic safety processing.
        
        Args:
            prompt: The prompt to send to the LLM
            content_type: "medical", "nutrition", or "general" (for disclaimer)
            skip_guardrails: If True, skip safety processing (internal use only)
            user_id: Optional user ID for logging
            images: Optional list of image data dicts (for multimodal models)
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Generated response with safety processing applied
        """
        logger.info(
            f"LLMGateway.generate: type={content_type}, "
            f"user={user_id or 'anonymous'}, provider={self.primary_provider}, "
            f"has_images={bool(images)}"
        )
        
        try:
            # Try primary provider
            if self.primary_provider == "gemini" and self.gemini_available:
                raw_response = await self._generate_gemini(prompt, images=images, **kwargs)
            elif self.ollama_available:
                if images:
                    logger.warning("Ollama provider does not currently support images via Gateway. Ignoring images.")
                raw_response = await self._generate_ollama(prompt, **kwargs)
            else:
                raise RuntimeError("No LLM provider available")
                
        except Exception as e:
            logger.error(f"Primary provider ({self.primary_provider}) failed: {e}")
            
            # Try fallback
            if self.fallback_enabled and self.ollama_available:
                logger.info("Falling back to Ollama")
                if images:
                    logger.warning("Fallback to Ollama drops image context.")
                raw_response = await self._generate_ollama(prompt, **kwargs)
            else:
                raise RuntimeError(f"LLM generation failed: {e}")
        
        # Apply guardrails
        if self.guardrails_enabled and not skip_guardrails:
            return self.guardrails.process_output(
                raw_response,
                {"type": content_type, "user_id": user_id}
            )
        
        if skip_guardrails:
            logger.warning("Guardrails skipped - internal use only")
        
        return raw_response
    
    async def generate_stream(
        self,
        prompt: str,
        content_type: str = "general",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream response tokens for real-time display.
        
        Note: Guardrails are applied to the final aggregated response,
        not to individual tokens (PII could span tokens).
        
        Yields:
            Individual response tokens/chunks
        """
        logger.info(f"LLMGateway.generate_stream: type={content_type}")
        
        full_response = ""
        
        async for chunk in self._stream_ollama(prompt, **kwargs):
            full_response += chunk
            yield chunk
        
        # Log the final response for audit
        if self.guardrails_enabled:
            # Note: We can't modify streamed output, but we log for audit
            safety_check = self.guardrails.check_safety(full_response)
            if not safety_check["safe"]:
                logger.warning(f"Streamed response had safety issues: {safety_check['issues']}")
            
            # Yield disclaimer at the end
            disclaimer = self.guardrails.get_disclaimer(content_type)
            if disclaimer:
                yield "\n\n" + disclaimer
    
    async def _generate_gemini(self, prompt: str, images: Optional[List] = None, **kwargs) -> str:
        """Generate response using Google Gemini."""
        import google.generativeai as genai
        
        api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        
        model_name = kwargs.get("model", "gemini-1.5-flash")
        model = genai.GenerativeModel(model_name)
        
        content = [prompt]
        if images:
            content.extend(images)
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(content)
        )
        
        return response.text
    
    async def _generate_ollama(self, prompt: str, **kwargs) -> str:
        """Generate response using local Ollama."""
        import httpx
        
        model = kwargs.get("model", os.getenv("OLLAMA_MODEL", "llama3.2"))
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            return response.json()["response"]
    
    async def _stream_ollama(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream response tokens from Ollama."""
        import httpx
        import json
        
        model = kwargs.get("model", os.getenv("OLLAMA_MODEL", "llama3.2"))
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": True
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
    
    def get_status(self) -> Dict[str, Any]:
        """Get gateway status for health checks."""
        return {
            "primary_provider": self.primary_provider,
            "gemini_available": self.gemini_available,
            "ollama_available": self.ollama_available,
            "fallback_enabled": self.fallback_enabled,
            "guardrails_enabled": self.guardrails_enabled,
            "ready": self.gemini_available or self.ollama_available
        }


# Singleton instance for convenience
_gateway_instance: Optional[LLMGateway] = None

def get_llm_gateway() -> LLMGateway:
    """Get or create the singleton LLM Gateway instance."""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = LLMGateway()
    return _gateway_instance
