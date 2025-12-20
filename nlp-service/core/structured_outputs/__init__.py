"""
Structured Outputs Package for Cardio AI.

This package contains modules for structured output generation using PydanticAI.
"""

from .pydantic_ai_wrapper import (
    HealthRecommendation,
    SymptomAssessment,
    CardioHealthAnalysis,
    PydanticHealthAgent,
    create_pydantic_health_agent,
    SimpleIntentAnalysis,
    ConversationResponse,
    HealthAnalysisGenerator,
    IntentAnalysisGenerator,
    ConversationGenerator,
)

__all__ = [
    "HealthRecommendation",
    "SymptomAssessment",
    "CardioHealthAnalysis",
    "PydanticHealthAgent",
    "create_pydantic_health_agent",
    "SimpleIntentAnalysis",
    "ConversationResponse",
    "HealthAnalysisGenerator",
    "IntentAnalysisGenerator",
    "ConversationGenerator",
]
