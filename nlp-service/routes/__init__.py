"""
Routes module for nlp-service ADK integration.
"""

# Import the router directly instead of importing from agents.py to avoid circular imports
from fastapi import APIRouter

# Create a placeholder router
router = APIRouter()

__all__ = ["router"]