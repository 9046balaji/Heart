"""
NLP data models - Re-exported from root models.py

This file maintains backward compatibility for imports like:
    from models.nlp import IntentEnum, NLPProcessRequest

All models are defined in the root models.py file.
"""

# Re-export all models from root models.py
from core.models import (
    # Enums
    IntentEnum,
    SentimentEnum,
    # Base models
    Entity,
    IntentResult,
    SentimentResult,
    # Request/Response models
    EntityExtractionRequest,
    EntityExtractionResponse,
    HealthCheckResponse,
    NLPProcessRequest,
    NLPProcessResponse,
    OllamaResponseRequest,
    OllamaResponseResponse,
    OllamaHealthCheckResponse,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)

# Define __all__ for explicit exports
__all__ = [
    # Enums
    "IntentEnum",
    "SentimentEnum",
    # Base models
    "Entity",
    "IntentResult",
    "SentimentResult",
    # Request/Response models
    "EntityExtractionRequest",
    "EntityExtractionResponse",
    "HealthCheckResponse",
    "NLPProcessRequest",
    "NLPProcessResponse",
    "OllamaResponseRequest",
    "OllamaResponseResponse",
    "OllamaHealthCheckResponse",
    "RiskAssessmentRequest",
    "RiskAssessmentResponse",
]
