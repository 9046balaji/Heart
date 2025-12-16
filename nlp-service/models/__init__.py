"""
Models module exports.
"""

import sys
import os

# Debug: Show where models are loading from
_models_dir = os.path.dirname(os.path.abspath(__file__))
print(f"[MODELS] Loading from: {_models_dir}")

# NLP Models - with error handling
try:
    from models.nlp import (
        IntentEnum,
        SentimentEnum,
        Entity,
        IntentResult,
        SentimentResult,
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
    print("[MODELS] [OK] NLP models imported successfully")
except ImportError as e:
    print(f"[MODELS] [ERROR] ERROR importing NLP models: {e}")
    print(f"[MODELS] Working directory: {os.getcwd()}")
    print(f"[MODELS] sys.path: {sys.path}")
    raise

# Health Models - with error handling (optional)
try:
    from models.health import (
        HealthRecord,
        VitalSigns,
        MedicationRecord,
        Allergy,
        HealthRecordCreate,
        HealthRecordUpdate,
        HealthRecordResponse,
        MedicationFrequency,
        AllergyReactionSeverity,
        SleepQuality,
        SmokingStatus,
        HealthMetrics
    )
    print("[MODELS] [OK] Health models imported successfully")
except ImportError as e:
    print(f"[MODELS] [WARNING] Could not import health models: {e}")
    print("[MODELS] Health models are optional, continuing without them")
    # Define stub classes for health models when they fail to import
    class HealthRecord: pass
    class VitalSigns: pass
    class MedicationRecord: pass
    class Allergy: pass
    class HealthRecordCreate: pass
    class HealthRecordUpdate: pass
    class HealthRecordResponse: pass
    class MedicationFrequency: pass
    class AllergyReactionSeverity: pass
    class SleepQuality: pass
    class SmokingStatus: pass
    class HealthMetrics: pass

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
    # Health models
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
    "HealthMetrics"
]
