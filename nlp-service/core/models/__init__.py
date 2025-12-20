"""
Models module exports.

This package provides a unified interface for importing all models.
The actual model definitions are in the root models.py file.
"""

import os

# Debug: Show where models are loading from
_models_dir = os.path.dirname(os.path.abspath(__file__))
print(f"[MODELS] Loading from: {_models_dir}")

# Import directly from the root models.py file (sibling to this package)
# Using importlib to avoid circular import issues

# Get the path to the root models.py
_root_models_path = os.path.join(os.path.dirname(_models_dir), "models.py")

# We can't import from sibling models.py easily, so we'll import inline
# The main.py already imports from root models.py, so we just re-export what it needs

# Define the classes that need to be available when importing from models package
# These will be populated when the root models.py is imported

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# ============================================================================
# Define IntentEnum and SentimentEnum inline to avoid circular imports
# ============================================================================


class IntentEnum(str, Enum):
    """Intent types"""

    GREETING = "greeting"
    RISK_ASSESSMENT = "risk_assessment"
    NUTRITION_ADVICE = "nutrition_advice"
    EXERCISE_COACHING = "exercise_coaching"
    MEDICATION_REMINDER = "medication_reminder"
    SYMPTOM_CHECK = "symptom_check"
    HEALTH_GOAL = "health_goal"
    HEALTH_EDUCATION = "health_education"
    APPOINTMENT_BOOKING = "appointment_booking"
    EMERGENCY = "emergency"
    UNKNOWN = "unknown"


class SentimentEnum(str, Enum):
    """Sentiment types"""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    DISTRESSED = "distressed"
    URGENT = "urgent"


class Entity(BaseModel):
    """Extracted entity"""

    type: str = Field(..., description="Entity type")
    value: str = Field(..., description="Entity value")
    start_index: int = Field(..., description="Start index")
    end_index: int = Field(..., description="End index")
    confidence: Optional[float] = Field(None, description="Confidence score")


class IntentResult(BaseModel):
    """Intent recognition result"""

    intent: IntentEnum = Field(..., description="Identified intent")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")
    keywords_matched: List[str] = Field(
        default_factory=list, description="Matched keywords"
    )


class SentimentResult(BaseModel):
    """Sentiment analysis result"""

    sentiment: SentimentEnum = Field(..., description="Detected sentiment")
    score: float = Field(..., ge=-1, le=1, description="Sentiment score")
    intensity: str = Field(..., description="Intensity level")


class NLPProcessRequest(BaseModel):
    """Request for NLP processing"""

    message: str = Field(..., description="User message to process", max_length=10000)
    user_id: Optional[str] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class NLPProcessResponse(BaseModel):
    """Response from NLP processing"""

    intent: IntentEnum = Field(..., description="Identified intent")
    intent_confidence: float = Field(..., description="Intent confidence")
    sentiment: SentimentEnum = Field(..., description="Detected sentiment")
    sentiment_score: float = Field(..., description="Sentiment score")
    entities: List[Entity] = Field(
        default_factory=list, description="Extracted entities"
    )
    requires_escalation: bool = Field(False, description="Requires human escalation")
    confidence_overall: float = Field(..., description="Overall confidence")


class EntityExtractionRequest(BaseModel):
    """Request for entity extraction"""

    text: str = Field(..., description="Text to extract entities from")
    entity_types: Optional[List[str]] = Field(
        None, description="Entity types to extract"
    )


class EntityExtractionResponse(BaseModel):
    """Response from entity extraction"""

    entities: List[Entity] = Field(
        default_factory=list, description="Extracted entities"
    )


class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")


class HealthMetrics(BaseModel):
    """User health metrics for risk assessment"""

    age: int = Field(..., ge=18, le=120)
    gender: str = Field(..., pattern="^(M|F|Other)$")
    blood_pressure_systolic: Optional[int] = Field(None, ge=60, le=300)
    blood_pressure_diastolic: Optional[int] = Field(None, ge=40, le=200)
    cholesterol_total: Optional[int] = Field(None, ge=100, le=500)
    hdl_cholesterol: Optional[int] = Field(None, ge=20, le=150)
    smoker: bool = Field(default=False)
    diabetes: bool = Field(default=False)
    family_history_heart_disease: bool = Field(default=False)
    physical_activity_minutes_per_week: int = Field(default=0, ge=0, le=1000)


class RiskAssessmentRequest(BaseModel):
    """Request for risk assessment"""

    metrics: HealthMetrics = Field(..., description="User health metrics")
    user_id: Optional[str] = Field(None, description="User ID")


class RiskAssessmentResponse(BaseModel):
    """Response from risk assessment"""

    risk_level: str = Field(..., description="Risk level")
    risk_score: float = Field(..., ge=0, le=100, description="Risk score")
    risk_interpretation: str = Field(..., description="Interpretation")
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations"
    )
    consultation_urgency: str = Field(..., description="Consultation urgency")


# Alias for compatibility with NLP service
RiskAssessmentResult = RiskAssessmentResponse


class OllamaResponseRequest(BaseModel):
    """Request for Ollama response"""

    prompt: str = Field(..., description="Prompt for generation")
    model: Optional[str] = Field(None, description="Model name")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Temperature")
    max_tokens: Optional[int] = Field(None, ge=1, le=4096, description="Max tokens")


class OllamaResponseResponse(BaseModel):
    """Response from Ollama"""

    response: str = Field(..., description="Generated response")
    model: str = Field(..., description="Model used")
    tokens_used: Optional[int] = Field(None, description="Tokens used")


class OllamaHealthCheckResponse(BaseModel):
    """Ollama health check response"""

    status: str = Field(..., description="Ollama status")
    model: str = Field(..., description="Model name")
    available: bool = Field(..., description="Whether Ollama is available")


print("[MODELS] [OK] NLP models defined successfully")


# Health Models - stubs (optional)
class HealthRecord:
    pass


class VitalSigns:
    pass


class MedicationRecord:
    pass


class Allergy:
    pass


class HealthRecordCreate:
    pass


class HealthRecordUpdate:
    pass


class HealthRecordResponse:
    pass


class MedicationFrequency:
    pass


class AllergyReactionSeverity:
    pass


class SleepQuality:
    pass


class SmokingStatus:
    pass


__all__ = [
    # NLP models
    "IntentEnum",
    "SentimentEnum",
    "Entity",
    "IntentResult",
    "SentimentResult",
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
    "RiskAssessmentResult",
    "HealthMetrics",
    # Health models (stubs)
    "HealthRecord",
    "VitalSigns",
    "MedicationRecord",
    "Allergy",
    "HealthRecordCreate",
    "HealthRecordUpdate",
    "HealthRecordResponse",
    "MedicationFrequency",
    "AllergyReactionSeverity",
    "SleepQuality",
    "SmokingStatus",
]
