import logging
import uuid
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, status
from pydantic import BaseModel, Field, validator
import re

# PERFORMANCE: Lazy import - LangGraphOrchestrator has heavy dependencies
# that slow down route loading. Import moved inside get_orchestrator().
if TYPE_CHECKING:
    from agents.langgraph_orchestrator import LangGraphOrchestrator

from core.security import get_current_user

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Orchestrated Chat"])

# Global orchestrator instance (lazy loaded)
_orchestrator: Optional["LangGraphOrchestrator"] = None

def reset_orchestrator() -> None:
    """Reset the orchestrator singleton to force re-initialization."""
    global _orchestrator
    _orchestrator = None
    logger.info("🔄 Orchestrator reset - will re-initialize on next request")

def get_orchestrator() -> "LangGraphOrchestrator":
    """Get or initialize the orchestrator singleton (lazy loaded)."""
    global _orchestrator
    if _orchestrator is None:
        try:
            # LAZY IMPORT: Only load heavy dependencies when first request comes in
            from agents.langgraph_orchestrator import LangGraphOrchestrator
            logger.info("Initializing LangGraph Orchestrator for the first time...")
            _orchestrator = LangGraphOrchestrator()
            logger.info("✅ LangGraph Orchestrator initialized successfully")
        except Exception as e:
            logger.critical(f"❌ Failed to initialize orchestrator: {e}")
            raise HTTPException(
                status_code=503,
                detail="Chat service is currently unavailable. Please try again later."
            )
    return _orchestrator

# --- Data Models ---

class ChatRequest(BaseModel):
    """Request model for chat messages."""
    user_id: str = Field(..., min_length=1, max_length=100, description="User ID")
    message: str = Field(..., min_length=1, max_length=10000, description="User message (max 10KB)")
    session_id: Optional[str] = Field(None, max_length=100, description="Session ID")
    
    @validator('message')
    def sanitize_message(cls, v):
        """Remove potentially dangerous control characters."""
        # Remove control characters except newlines and tabs
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', v)

class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str
    sources: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    session_id: str
    success: bool = True

class ResearchRequest(BaseModel):
    """Request model for deep research."""
    query: str = Field(..., min_length=5, max_length=500)
    user_id: str

# --- Routes ---

@router.post("/message", response_model=ChatResponse)
async def orchestrated_chat(
    request: ChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ChatResponse:
    """
    Process a chat message through the LangGraph agentic workflow.
    
    Requires Authentication.
    """
    # 1. Security: Validate User ID matches Authenticated User
    # Compare as strings to handle int/str type mismatch
    if str(request.user_id) != str(current_user.get("user_id")):
        logger.warning(f"Auth mismatch: Request user {request.user_id} != Token user {current_user.get('user_id')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only post messages for your own user ID."
        )

    orchestrator = get_orchestrator()
    
    try:
        # 2. Execute Workflow
        logger.info(f"Processing message for user {request.user_id}: {request.message[:50]}...")
        
        result = await orchestrator.execute(
            query=request.message,
            user_id=request.user_id
        )
        
        # 3. Construct Response
        # Infer success from response presence and confidence
        is_success = bool(result.get("response")) and result.get("confidence", 0) > 0.3
        
        return ChatResponse(
            response=result.get("response", "I apologize, but I couldn't generate a response."),
            sources=result.get("sources", []),
            metadata={
                "processing_time": result.get("processing_time"),
                "steps": result.get("steps", []),
                "confidence": result.get("confidence", 0.0),
                "source": result.get("metadata", {}).get("source", "unknown"),  # Track response source (rag, web, llm, etc.)
                "intent": result.get("intent", "unknown"),
                "pii_scrubbed": result.get("pii_scrubbed", False)
            },
            session_id=request.session_id or str(uuid.uuid4()),
            success=is_success
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/research")
async def deep_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Trigger a deep research task (Async).
    """
    # Validate User
    if str(request.user_id) != str(current_user.get("user_id")):
        raise HTTPException(status_code=403, detail="Access denied")

    orchestrator = get_orchestrator()
    
    # TODO: Implement actual async task dispatch
    # background_tasks.add_task(orchestrator.run_research, request.query, request.user_id)
    
    return {
        "status": "accepted", 
        "message": "Research task started",
        "task_id": str(uuid.uuid4())
    }

@router.get("/health")
async def health_check():
    """Check if the orchestrator is ready."""
    global _orchestrator
    status = "healthy" if _orchestrator else "uninitialized"
    return {"status": status, "service": "langgraph_orchestrator"}

@router.post("/reset")
async def reset_orchestrator_endpoint():
    """Reset the orchestrator to force re-initialization with updated code."""
    reset_orchestrator()
    return {"status": "reset", "message": "Orchestrator will re-initialize on next request"}