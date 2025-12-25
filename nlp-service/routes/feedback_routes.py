"""API routes for feedback collection."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from nlp.rag.feedback_store import get_feedback_store

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    feedback_id: str
    rating: int  # 1, 0, or -1
    query: str
    response: str
    citations: list = []
    user_id: Optional[str] = None
    comment: Optional[str] = None


@router.post("/submit")
async def submit_feedback(request: FeedbackRequest):
    """Submit user feedback for a RAG response."""
    if request.rating not in [-1, 0, 1]:
        raise HTTPException(400, "Rating must be -1, 0, or 1")
    
    store = get_feedback_store()
    success = store.record_feedback(
        feedback_id=request.feedback_id,
        rating=request.rating,
        query=request.query,
        response=request.response,
        citations=request.citations,
        user_id=request.user_id,
        comment=request.comment
    )
    
    if not success:
        raise HTTPException(500, "Failed to record feedback")
    
    return {"status": "success", "feedback_id": request.feedback_id}


@router.get("/stats")
async def get_stats():
    """Get feedback statistics."""
    store = get_feedback_store()
    return store.get_feedback_stats()


@router.get("/list")
async def list_feedback(limit: int = 50):
    """List recent feedback."""
    store = get_feedback_store()
    # Assuming store has a method to list feedback, if not return empty
    if hasattr(store, "list_feedback"):
        return store.list_feedback(limit=limit)
    return {"feedback": [], "count": 0}