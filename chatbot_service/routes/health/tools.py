"""
Health Tools Routes
===================
Clinical tool endpoints: vitals recording, drug interactions, symptom triage.
Leverages existing backend services: DrugInteractionDetector, triage_system.
Endpoints:
    POST /tools/blood-pressure
    POST /tools/heart-rate
    POST /tools/drug-interactions
    POST /tools/symptom-triage
"""

import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("tools")

router = APIRouter()


# ---------------------------------------------------------------------------
# Load existing backend services
# ---------------------------------------------------------------------------

_interaction_detector = None
_triage_system = None

try:
    from core.services.interaction_detector import DrugInteractionDetector
    _interaction_detector = DrugInteractionDetector()
    logger.info("DrugInteractionDetector loaded for /tools/drug-interactions")
except Exception as e:
    logger.info(f"DrugInteractionDetector not available: {e}")

try:
    from agents.components.triage_system import TriageSystem
    _triage_system = TriageSystem()
    logger.info("TriageSystem loaded for /tools/symptom-triage")
except Exception as e:
    logger.info(f"TriageSystem not available: {e}")


# ---------------------------------------------------------------------------
# In-memory vitals store
# ---------------------------------------------------------------------------

_vitals_log: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class BloodPressureRequest(BaseModel):
    systolic: int = Field(..., ge=50, le=300, description="Systolic pressure in mmHg")
    diastolic: int = Field(..., ge=30, le=200, description="Diastolic pressure in mmHg")
    user_id: str
    timestamp: Optional[str] = None


class HeartRateRequest(BaseModel):
    bpm: int = Field(..., ge=20, le=300, description="Heart rate in BPM")
    user_id: str
    timestamp: Optional[str] = None


class VitalRecordResponse(BaseModel):
    id: str
    status: str
    metric: str
    value: Any
    interpretation: str
    recorded_at: str


class DrugInteractionsRequest(BaseModel):
    medications: List[str] = Field(..., min_length=1)


class DrugInteractionsResponse(BaseModel):
    found: bool
    count: int = 0
    interactions: List[Dict[str, Any]] = []
    checked_medications: List[str] = []


class SymptomTriageRequest(BaseModel):
    symptoms: List[str] = Field(..., min_length=1)
    user_id: str


class SymptomTriageResponse(BaseModel):
    urgency: str  # critical, high, moderate, low
    recommendation: str
    symptoms_analyzed: List[str]
    possible_conditions: List[str] = []
    next_steps: List[str] = []
    disclaimer: str = "This is not a medical diagnosis. Please consult a healthcare professional."


# ---------------------------------------------------------------------------
# Blood pressure interpretation
# ---------------------------------------------------------------------------

def interpret_bp(systolic: int, diastolic: int) -> str:
    if systolic < 90 or diastolic < 60:
        return "Low blood pressure (hypotension). Monitor for dizziness or fainting."
    if systolic < 120 and diastolic < 80:
        return "Normal blood pressure. Excellent!"
    if systolic < 130 and diastolic < 80:
        return "Elevated blood pressure. Adopt heart-healthy habits."
    if systolic < 140 or diastolic < 90:
        return "High blood pressure Stage 1. Lifestyle changes recommended; consult your doctor."
    if systolic < 180 and diastolic < 120:
        return "High blood pressure Stage 2. Medication likely needed. See your doctor."
    return "Hypertensive crisis! Seek immediate medical attention."


def interpret_hr(bpm: int) -> str:
    if bpm < 50:
        return "Bradycardia (slow heart rate). Normal for athletes; otherwise consult a doctor."
    if bpm <= 100:
        return "Normal resting heart rate."
    if bpm <= 120:
        return "Slightly elevated heart rate. May be due to stress, caffeine, or mild exertion."
    return "Tachycardia (fast heart rate). If persistent at rest, seek medical evaluation."


# ---------------------------------------------------------------------------
# Symptom triage logic
# ---------------------------------------------------------------------------

EMERGENCY_SYMPTOMS = {
    "chest pain", "difficulty breathing", "severe chest pressure",
    "sudden numbness", "loss of consciousness", "severe bleeding",
    "seizure", "stroke symptoms", "heart attack symptoms",
}

HIGH_URGENCY_SYMPTOMS = {
    "high fever", "persistent vomiting", "blood in stool",
    "severe abdominal pain", "sudden vision changes",
    "confusion", "shortness of breath",
}


def triage_symptoms(symptoms: List[str]) -> dict:
    """Basic symptom triage based on keyword matching."""
    symptoms_lower = [s.lower().strip() for s in symptoms]

    # Check for emergency
    for s in symptoms_lower:
        for emergency in EMERGENCY_SYMPTOMS:
            if emergency in s:
                return {
                    "urgency": "critical",
                    "recommendation": "Call 911 or go to the nearest emergency room immediately.",
                    "next_steps": [
                        "Call emergency services (911)",
                        "Do not drive yourself",
                        "If possible, have someone stay with you",
                    ],
                }

    # Check for high urgency
    for s in symptoms_lower:
        for high in HIGH_URGENCY_SYMPTOMS:
            if high in s:
                return {
                    "urgency": "high",
                    "recommendation": "Seek medical attention within 24 hours. Visit urgent care or call your doctor.",
                    "next_steps": [
                        "Contact your healthcare provider today",
                        "Visit an urgent care center if symptoms worsen",
                        "Monitor symptoms closely",
                    ],
                }

    # Moderate/Low
    return {
        "urgency": "moderate" if len(symptoms) > 2 else "low",
        "recommendation": "Monitor your symptoms and schedule an appointment with your healthcare provider if they persist.",
        "next_steps": [
            "Rest and hydrate",
            "Track symptom changes",
            "Schedule a doctor visit if symptoms persist beyond 48 hours",
        ],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/blood-pressure", response_model=VitalRecordResponse)
async def record_blood_pressure(request: BloodPressureRequest):
    """Record a blood pressure reading with clinical interpretation."""
    record_id = str(uuid.uuid4())
    ts = request.timestamp or datetime.utcnow().isoformat() + "Z"
    interpretation = interpret_bp(request.systolic, request.diastolic)

    entry = {
        "id": record_id,
        "user_id": request.user_id,
        "metric": "blood_pressure",
        "systolic": request.systolic,
        "diastolic": request.diastolic,
        "timestamp": ts,
    }
    _vitals_log.append(entry)

    return VitalRecordResponse(
        id=record_id,
        status="recorded",
        metric="blood_pressure",
        value=f"{request.systolic}/{request.diastolic} mmHg",
        interpretation=interpretation,
        recorded_at=ts,
    )


@router.post("/heart-rate", response_model=VitalRecordResponse)
async def record_heart_rate(request: HeartRateRequest):
    """Record a heart rate reading with clinical interpretation."""
    record_id = str(uuid.uuid4())
    ts = request.timestamp or datetime.utcnow().isoformat() + "Z"
    interpretation = interpret_hr(request.bpm)

    entry = {
        "id": record_id,
        "user_id": request.user_id,
        "metric": "heart_rate",
        "bpm": request.bpm,
        "timestamp": ts,
    }
    _vitals_log.append(entry)

    return VitalRecordResponse(
        id=record_id,
        status="recorded",
        metric="heart_rate",
        value=f"{request.bpm} bpm",
        interpretation=interpretation,
        recorded_at=ts,
    )


@router.post("/drug-interactions", response_model=DrugInteractionsResponse)
async def check_drug_interactions(request: DrugInteractionsRequest):
    """Check for potential adverse drug interactions."""
    if len(request.medications) < 2:
        return DrugInteractionsResponse(
            found=False,
            count=0,
            interactions=[],
            checked_medications=request.medications,
        )

    # Use the existing DrugInteractionDetector service
    if _interaction_detector:
        try:
            summary = _interaction_detector.get_interaction_summary(request.medications)
            return DrugInteractionsResponse(
                found=summary.get("found", False),
                count=summary.get("count", 0),
                interactions=summary.get("interactions", []),
                checked_medications=request.medications,
            )
        except Exception as e:
            logger.warning(f"DrugInteractionDetector failed: {e}")

    # Fallback
    return DrugInteractionsResponse(
        found=False,
        count=0,
        interactions=[],
        checked_medications=request.medications,
    )


@router.post("/symptom-triage", response_model=SymptomTriageResponse)
async def symptom_triage(request: SymptomTriageRequest):
    """Triage symptoms and recommend next steps."""
    if not request.symptoms:
        raise HTTPException(status_code=400, detail="At least one symptom is required")

    # Try the existing TriageSystem
    if _triage_system:
        try:
            result = _triage_system.triage(request.symptoms)
            if isinstance(result, dict):
                return SymptomTriageResponse(
                    urgency=result.get("urgency", "moderate"),
                    recommendation=result.get("recommendation", ""),
                    symptoms_analyzed=request.symptoms,
                    possible_conditions=result.get("possible_conditions", []),
                    next_steps=result.get("next_steps", []),
                )
        except Exception as e:
            logger.warning(f"TriageSystem failed: {e}")

    # Fallback: basic keyword-based triage
    result = triage_symptoms(request.symptoms)
    return SymptomTriageResponse(
        urgency=result["urgency"],
        recommendation=result["recommendation"],
        symptoms_analyzed=request.symptoms,
        possible_conditions=[],
        next_steps=result["next_steps"],
    )
