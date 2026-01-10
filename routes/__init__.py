"""
Routes module for Cardio AI NLP Service.

Provides REST API endpoints for:
- Authentication (auth_routes)
- Memory management (memory)
- Orchestrated chat with LangGraph (orchestrated_chat)
- Document upload and multimodal processing (documents)
"""

from fastapi import APIRouter

# Import individual routers
from .auth_routes import router as auth_router
from .memory import router as memory_router
from .orchestrated_chat import router as orchestrated_chat_router
from .documents import router as document_router

# Create a placeholder router for backward compatibility
router = APIRouter()

__all__ = [
    "router",
    "auth_router",
    "memory_router",
    "orchestrated_chat_router",
    "document_router",
]
