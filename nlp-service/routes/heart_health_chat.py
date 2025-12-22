"""
Heart Health Chat API Routes

Provides REST API endpoints for the Heart Health AI Assistant chat functionality.
"""

import logging
import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

# Import response generator
from core.heart_health.response_generator import (
    get_response_generator,
    HeartHealthResponseGenerator
)
from core.heart_health.emergency_detector import EmergencyDetector

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/chat", tags=["Heart Health Chat"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ChatRequest(BaseModel):
    """Request model for chat message."""
    message: str = Field(..., description="User's message/question", min_length=1, max_length=5000)
    session_id: Optional[str] = Field(None, description="Chat session ID for context continuity")
    include_vitals: bool = Field(True, description="Include smart watch vitals in context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Is my heart rate of 120 dangerous?",
                "session_id": None,
                "include_vitals": True
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat message."""
    response: str = Field(..., description="AI-generated response")
    success: bool = Field(..., description="Whether the request was successful")
    session_id: str = Field(..., description="Chat session ID")
    is_emergency: bool = Field(False, description="Whether emergency was detected")
    urgency_level: str = Field("routine", description="Urgency classification")
    recommended_action: Optional[str] = Field(None, description="Recommended action for urgent situations")
    response_time_ms: int = Field(..., description="Response generation time in milliseconds")
    context_summary: Optional[dict] = Field(None, description="Summary of context used")


class EmergencyCheckRequest(BaseModel):
    """Request model for emergency detection check."""
    message: str = Field(..., description="Message to check for emergency indicators")


class EmergencyCheckResponse(BaseModel):
    """Response model for emergency detection."""
    is_emergency: bool
    urgency_level: str
    matched_keywords: List[str]
    recommended_action: str
    confidence: float


class SessionInfo(BaseModel):
    """Information about a chat session."""
    session_id: str
    started_at: datetime
    message_count: int
    is_active: bool


# ============================================================================
# DEPENDENCIES
# ============================================================================

async def get_generator_dependency() -> HeartHealthResponseGenerator:
    """Dependency for getting the response generator."""
    generator = await get_response_generator()
    if not generator.initialized:
        raise HTTPException(
            status_code=503,
            detail="Heart Health AI service is not fully initialized"
        )
    return generator


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user_id: str = Query(..., description="User ID for personalization"),
    generator: HeartHealthResponseGenerator = Depends(get_generator_dependency)
):
    """
    Send a message to the Heart Health AI Assistant.
    
    This endpoint:
    1. Fetches user profile and vitals from MySQL
    2. Searches medical knowledge base (ChromaDB)
    3. Detects emergency situations
    4. Generates personalized AI response
    5. Stores conversation in chat history
    
    Args:
        request: Chat request containing the message
        user_id: User ID for personalization and context
        
    Returns:
        AI-generated response with metadata
    """
    try:
        result = await generator.generate_response(
            user_id=user_id,
            user_query=request.message,
            session_id=request.session_id,
            include_vitals=request.include_vitals
        )
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to generate response")
            )
        
        metadata = result.get("metadata", {})
        context_summary = metadata.get("context_summary", {})
        
        return ChatResponse(
            response=result["response"],
            success=True,
            session_id=result.get("session_id", request.session_id or str(uuid.uuid4())),
            is_emergency=metadata.get("is_emergency", False),
            urgency_level=metadata.get("urgency_level", "routine"),
            recommended_action=metadata.get("recommended_action"),
            response_time_ms=metadata.get("response_time_ms", 0),
            context_summary=context_summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat message endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/check-emergency", response_model=EmergencyCheckResponse)
async def check_emergency(request: EmergencyCheckRequest):
    """
    Check a message for emergency indicators without generating a response.
    
    Useful for quick triage or form validation before submitting.
    
    Args:
        request: Message to analyze
        
    Returns:
        Emergency assessment results
    """
    try:
        detector = EmergencyDetector()
        assessment = detector.detect(request.message)
        
        return EmergencyCheckResponse(
            is_emergency=assessment.is_emergency,
            urgency_level=assessment.urgency_level.value,
            matched_keywords=assessment.matched_keywords,
            recommended_action=assessment.recommended_action,
            confidence=assessment.confidence
        )
        
    except Exception as e:
        logger.error(f"Error in emergency check: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Emergency check failed: {str(e)}"
        )


@router.get("/history")
async def get_chat_history(
    session_id: str = Query(..., description="Chat session ID"),
    limit: int = Query(50, description="Maximum messages to return", ge=1, le=200),
    generator: HeartHealthResponseGenerator = Depends(get_generator_dependency)
):
    """
    Retrieve chat history for a session.
    
    Args:
        session_id: The chat session ID
        limit: Maximum number of messages to return
        
    Returns:
        List of chat messages in chronological order
    """
    try:
        if not generator.db or not generator.db.initialized:
            return {"messages": [], "count": 0, "session_id": session_id}
        
        messages = await generator.db.get_chat_history(
            session_id=session_id,
            limit=limit
        )
        
        return {
            "messages": messages,
            "count": len(messages),
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch chat history: {str(e)}"
        )


@router.post("/session/new")
async def create_new_session(
    user_id: str = Query(..., description="User ID"),
    session_type: str = Query("general", description="Session type")
):
    """
    Create a new chat session.
    
    Args:
        user_id: User ID for the session
        session_type: Type of session (general, symptom_check, medication_query, etc.)
        
    Returns:
        New session information
    """
    try:
        session_id = str(uuid.uuid4())
        
        return {
            "session_id": session_id,
            "user_id": user_id,
            "session_type": session_type,
            "created_at": datetime.now().isoformat(),
            "is_active": True
        }
        
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Check the health status of the chat service.
    
    Returns:
        Service health status and component availability
    """
    try:
        generator = await get_response_generator()
        
        return {
            "status": "healthy" if generator.initialized else "degraded",
            "components": {
                "response_generator": generator.initialized,
                "mysql_database": generator.db is not None and generator.db.initialized if generator.db else False,
                "chromadb": generator.chroma_service is not None and generator.chroma_service.initialized if generator.chroma_service else False,
                "llm_gateway": generator.llm_gateway is not None,
                "embedding_model": generator.embedding_model is not None
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
