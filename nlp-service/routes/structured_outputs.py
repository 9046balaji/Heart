from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from core.structured_outputs import (
    HealthAnalysisGenerator,
    IntentAnalysisGenerator,
    ConversationGenerator,
    CardioHealthAnalysis,
    SimpleIntentAnalysis,
    ConversationResponse,
)
from nlp.ollama_generator import get_ollama_generator

router = APIRouter(prefix="/api/structured-outputs", tags=["Structured Outputs"])
logger = logging.getLogger(__name__)

# Generators
health_generator = HealthAnalysisGenerator()
intent_generator = IntentAnalysisGenerator()
conversation_generator = ConversationGenerator()


class StructuredRequest(BaseModel):
    message: str
    user_id: str = "anonymous"
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@router.post("/health-analysis", response_model=CardioHealthAnalysis)
async def health_analysis(request: StructuredRequest):
    """Generate structured health analysis from user message."""
    try:
        ollama = get_ollama_generator()
        result = await health_generator.generate(
            ollama_generator=ollama,
            user_message=request.message,
            additional_context=str(request.context) if request.context else None,
        )
        return result
    except Exception as e:
        logger.error(f"Error in structured health analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intent", response_model=SimpleIntentAnalysis)
async def intent_analysis(request: StructuredRequest):
    """Generate structured intent analysis."""
    try:
        ollama = get_ollama_generator()
        result = await intent_generator.generate(
            ollama_generator=ollama, user_message=request.message
        )
        return result
    except Exception as e:
        logger.error(f"Error in structured intent analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversation", response_model=ConversationResponse)
async def conversation_response(request: StructuredRequest):
    """Generate structured conversation response."""
    try:
        ollama = get_ollama_generator()
        result = await conversation_generator.generate(
            ollama_generator=ollama,
            user_message=request.message,
            additional_context=str(request.context) if request.context else None,
        )
        return result
    except Exception as e:
        logger.error(f"Error in structured conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """Get status of structured output system."""
    try:
        ollama = get_ollama_generator()
        return {
            "status": "online",
            "provider": "ollama",
            "model": ollama.model_name if ollama else "unknown",
            "generators": ["health", "intent", "conversation"],
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "provider": "unknown",
        }


@router.get("/schema/{name}")
async def get_schema(name: str):
    """Get JSON schema for a structured output model."""
    schema_map = {
        "health-analysis": CardioHealthAnalysis,
        "intent": SimpleIntentAnalysis,
        "conversation": ConversationResponse,
    }

    if name not in schema_map:
        raise HTTPException(
            status_code=404,
            detail=f"Schema '{name}' not found. Available: {list(schema_map.keys())}",
        )

    return schema_map[name].model_json_schema()
