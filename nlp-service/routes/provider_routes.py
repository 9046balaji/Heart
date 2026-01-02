"""
Provider Selection Routes - Allow users to switch between LLM providers.

Endpoints:
- GET  /api/provider/current      - Get current selected provider
- POST /api/provider/select       - Select Ollama or OpenRouter
- GET  /api/provider/status       - Get status of available providers
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/provider", tags=["Provider Selection"])

# In-memory provider selection (in production, store in database)
_provider_selection: Dict[str, str] = {}


class ProviderSelectRequest(BaseModel):
    """Request to select a provider."""
    
    provider: str = Field(..., description="Provider to select: 'ollama' or 'openrouter'")
    user_id: Optional[str] = Field(None, description="Optional user ID for persistence")


class ProviderStatusResponse(BaseModel):
    """Status of available providers."""
    
    ollama_available: bool = Field(..., description="Whether Ollama is available")
    openrouter_available: bool = Field(..., description="Whether OpenRouter is available")
    current_provider: str = Field(..., description="Currently selected provider")
    ollama_url: str = Field(..., description="Ollama service URL")
    openrouter_configured: bool = Field(..., description="Whether OpenRouter API key is set")


class ProviderResponse(BaseModel):
    """Response for provider selection."""
    
    selected_provider: str = Field(..., description="Selected provider")
    message: str = Field(..., description="Status message")


@router.get("/current")
async def get_current_provider(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get the currently selected provider for a user."""
    
    # If user_id provided, get their selection; otherwise get default
    if user_id and user_id in _provider_selection:
        provider = _provider_selection[user_id]
    else:
        # Get from environment or default
        provider = os.getenv("LLM_PROVIDER", "openrouter")
    
    return {
        "selected_provider": provider,
        "user_id": user_id or "anonymous"
    }


@router.post("/select")
async def select_provider(request: ProviderSelectRequest) -> ProviderResponse:
    """
    Select an LLM provider (Ollama or OpenRouter).
    
    Args:
        request: Provider selection request with provider name and optional user_id
        
    Returns:
        Confirmation of selected provider
        
    Raises:
        HTTPException: If provider is invalid
    """
    
    provider = request.provider.lower()
    
    # Validate provider
    if provider not in ["ollama", "openrouter"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider '{provider}'. Must be 'ollama' or 'openrouter'"
        )
    
    # Store selection (with user context if provided)
    if request.user_id:
        _provider_selection[request.user_id] = provider
        logger.info(f"Provider '{provider}' selected for user: {request.user_id}")
    else:
        logger.info(f"Provider '{provider}' selected for anonymous user")
    
    return ProviderResponse(
        selected_provider=provider,
        message=f"Successfully switched to {provider}"
    )


@router.get("/status")
async def get_provider_status(user_id: Optional[str] = None) -> ProviderStatusResponse:
    """
    Get status of available providers and current selection.
    
    Args:
        user_id: Optional user ID to get their preference
        
    Returns:
        Status of all providers and current selection
    """
    
    # Check Ollama availability
    import aiohttp
    import asyncio
    
    ollama_host = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_available = False
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ollama_host}/api/tags", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                ollama_available = resp.status == 200
    except Exception as e:
        logger.debug(f"Ollama health check failed: {e}")
        ollama_available = False
    
    # Check OpenRouter availability
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_configured = bool(openrouter_api_key and openrouter_api_key != "")
    
    # Get current provider for user
    if user_id and user_id in _provider_selection:
        current = _provider_selection[user_id]
    else:
        current = os.getenv("LLM_PROVIDER", "openrouter")
    
    return ProviderStatusResponse(
        ollama_available=ollama_available,
        openrouter_available=openrouter_configured,
        current_provider=current,
        ollama_url=ollama_host,
        openrouter_configured=openrouter_configured
    )


@router.get("/available")
async def get_available_providers(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get list of available providers the user can switch to.
    
    Returns:
        List of available provider options
    """
    
    import aiohttp
    
    status = await get_provider_status(user_id)
    
    available = []
    
    if status.ollama_available:
        available.append({
            "name": "ollama",
            "label": "Local Ollama (Offline)",
            "description": "Run locally on your machine using Ollama",
            "available": True
        })
    
    if status.openrouter_available:
        available.append({
            "name": "openrouter",
            "label": "OpenRouter API (Cloud)",
            "description": "Use OpenRouter cloud API for better responses",
            "available": True
        })
    
    return {
        "available_providers": available,
        "current_selection": status.current_provider,
        "user_id": user_id or "anonymous"
    }
