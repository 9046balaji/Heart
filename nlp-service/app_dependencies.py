"""
FastAPI Dependency Injection Providers

This module contains all dependency injection functions for the NLP Service.
Extracted from main.py to improve modularity and testability.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, Request, status
from models import PatientMemory

# Import state manager (will be defined in main.py)
# These are forward references that get resolved at runtime
class NLPState:
    """Forward reference to NLPState from main.py"""
    intent_recognizer = None
    sentiment_analyzer = None
    entity_extractor = None
    risk_assessor = None
    memory_manager = None


# ========================================
# Component Dependencies
# ========================================

def get_intent_recognizer():
    """
    Dependency: Get intent recognizer from app state.
    
    Returns:
        IntentRecognizer instance
        
    Raises:
        HTTPException: If service not initialized
    """
    from main import NLPState as MainNLPState  # Import at runtime
    
    if MainNLPState.intent_recognizer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IntentRecognizer not initialized"
        )
    return MainNLPState.intent_recognizer


def get_sentiment_analyzer():
    """
    Dependency: Get sentiment analyzer from app state.
    
    Returns:
        SentimentAnalyzer instance
        
    Raises:
        HTTPException: If service not initialized
    """
    from main import NLPState as MainNLPState
    
    if MainNLPState.sentiment_analyzer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SentimentAnalyzer not initialized"
        )
    return MainNLPState.sentiment_analyzer


def get_entity_extractor():
    """
    Dependency: Get entity extractor from app state.
    
    Returns:
        EntityExtractor instance
        
    Raises:
        HTTPException: If service not initialized
    """
    from main import NLPState as MainNLPState
    
    if MainNLPState.entity_extractor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="EntityExtractor not initialized"
        )
    return MainNLPState.entity_extractor


def get_risk_assessor():
    """
    Dependency: Get risk assessor from app state.
    
    Returns:
        RiskAssessor instance
        
    Raises:
        HTTPException: If service not initialized
    """
    from main import NLPState as MainNLPState
    
    if MainNLPState.risk_assessor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RiskAssessor not initialized"
        )
    return MainNLPState.risk_assessor


def get_memory_manager():
    """
    Dependency: Get memory manager instance.
    
    Returns:
        MemoryManager instance
        
    Raises:
        HTTPException: If service not initialized
    """
    from main import NLPState as MainNLPState
    
    if MainNLPState.memory_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MemoryManager not initialized"
        )
    return MainNLPState.memory_manager


async def get_memory_context(patient_id: Optional[str] = None) -> Optional[PatientMemory]:
    """
    Dependency: Get memory context for patient.
    
    Args:
        patient_id: Patient identifier (optional)
    
    Returns:
        PatientMemory instance if available, None otherwise
    """
    if not patient_id:
        return None
    
    try:
        import logging
        logger = logging.getLogger(__name__)
        memory_mgr = get_memory_manager()
        return await memory_mgr.get_patient_memory(patient_id)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not get memory context for {patient_id}: {e}")
        return None


# ========================================
# Generator Dependencies
# ========================================

def get_ollama_generator(model_name: str = "gemma3:1b"):
    """
    Dependency: Get Ollama generator instance.
    
    Args:
        model_name: Model to use (default: gemma3:1b)
        
    Returns:
        OllamaGenerator instance
    """
    from ollama_generator import OllamaGenerator
    return OllamaGenerator(model_name=model_name)


async def get_rag_context(
    query: str, 
    user_id: Optional[str] = None, 
    top_k: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Retrieve relevant context from RAG system for response augmentation.
    
    Args:
        query: Search query
        user_id: Optional user identifier
        top_k: Number of results to retrieve
    
    Returns:
        Context dictionary with medical/drug/memory context, or None if RAG disabled
    """
    from main import RAG_ENABLED  # Import flag from main
    
    if not RAG_ENABLED:
        return None
    
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        # Import lazily to avoid circular imports
        from rag_api import get_rag_pipeline
        pipeline = get_rag_pipeline()
        
        # Search for relevant context (don't generate, just retrieve)
        result = await pipeline.query(
            query=query,
            user_id=user_id,
            search_medical=True,
            search_drugs=True,
            search_user_memory=bool(user_id),
            top_k=top_k,
            generate=False,  # Just retrieve, don't generate
        )
        
        # Return context dictionary
        return {
            "medical_context": result.to_dict().get("sources", {}).get("medical", []),
            "drug_context": result.to_dict().get("sources", {}).get("drugs", []),
            "user_memory_context": result.to_dict().get("sources", {}).get("memories", []),
            "citations": [c for c in result.citations[:5]],  # Limit citations
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"RAG context retrieval failed (non-fatal): {e}")
        return None


# ========================================
# Authentication & Authorization
# ========================================

async def get_current_user():
    """
    Placeholder for authentication - returns empty dict for now.
    
    TODO: Implement actual authentication (JWT, OAuth2, etc.)
    
    Returns:
        User dict (currently empty)
    """
    return {}


async def rate_limiter(request: Request):
    """
    Rate limiting dependency.
    
    Note: Actual rate limiting is done via @limiter.limit() decorator on endpoints.
    This function is kept for backward compatibility but slowapi handles the actual limiting.
    
    Args:
        request: FastAPI request object
        
    Returns:
        True (always passes)
    """
    return True
