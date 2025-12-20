"""
FastAPI routes for XAMPP RAG service integration.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from ..core.rag.xampp_rag import get_rag_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/xampp-rag", tags=["XAMPP RAG"])


# Pydantic models
class AddDocumentRequest(BaseModel):
    """Request model for adding a document to the knowledge base."""

    content: str = Field(..., description="Document content")
    content_type: str = Field(
        ..., description="Type of content (e.g., medical_guideline, drug_information)"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class AddDocumentResponse(BaseModel):
    """Response model for adding a document."""

    success: bool
    message: str


class QueryRequest(BaseModel):
    """Request model for querying the RAG system."""

    query: str = Field(..., description="Query string")
    content_types: Optional[List[str]] = Field(
        None, description="Specific content types to search"
    )
    user_id: Optional[str] = Field(None, description="User identifier")


class QueryResponse(BaseModel):
    """Response model for RAG queries."""

    response: str
    context_used: List[Dict[str, Any]]
    success: bool
    error: Optional[str] = None


class ContentTypesResponse(BaseModel):
    """Response model for available content types."""

    content_types: List[str]


@router.post("/documents", response_model=AddDocumentResponse)
async def add_document(request: AddDocumentRequest):
    """Add a document to the knowledge base."""
    try:
        rag_service = await get_rag_service()
        success = await rag_service.add_medical_document(
            content=request.content,
            content_type=request.content_type,
            metadata=request.metadata,
        )

        if success:
            return AddDocumentResponse(
                success=True,
                message=f"Document of type '{request.content_type}' added successfully",
            )
        else:
            return AddDocumentResponse(
                success=False, message="Failed to add document to knowledge base"
            )
    except Exception as e:
        logger.error(f"Error adding document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add document: {str(e)}",
        )


@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """Query the knowledge base using RAG."""
    try:
        rag_service = await get_rag_service()
        result = await rag_service.generate_augmented_response(
            query=request.query,
            user_id=request.user_id,
            content_types=request.content_types,
        )

        return QueryResponse(**result)
    except Exception as e:
        logger.error(f"Error querying knowledge base: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query knowledge base: {str(e)}",
        )


@router.get("/content-types", response_model=ContentTypesResponse)
async def get_content_types():
    """Get available content types in the knowledge base."""
    try:
        rag_service = await get_rag_service()
        content_types = await rag_service.get_available_content_types()
        return ContentTypesResponse(content_types=content_types)
    except Exception as e:
        logger.error(f"Error getting content types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get content types: {str(e)}",
        )


@router.get("/health")
async def rag_health_check():
    """Health check endpoint for the RAG service."""
    try:
        rag_service = await get_rag_service()
        return {
            "status": "healthy" if rag_service.initialized else "uninitialized",
            "service": "XAMPP RAG Service",
            "database_connected": (
                rag_service.db.initialized if rag_service.db else False
            ),
        }
    except Exception as e:
        logger.error(f"Error in RAG health check: {e}")
        return {"status": "unhealthy", "error": str(e)}
