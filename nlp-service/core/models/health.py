"""
Health data models with HIPAA compliance and validation.
Based on adk-sourced-code/4-structured-outputs patterns.

Phase 2: Health Data Models
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
from typing import List, Optional


# ============================================================================
# ENUMS FOR STANDARDIZED VALUES
# ============================================================================


class VitalSignsType(str, Enum):
    """Types of vital signs measurements."""

    HEART_RATE = "heart_rate"
    BLOOD_PRESSURE = "blood_pressure"
    TEMPERATURE = "temperature"
    RESPIRATORY_RATE = "respiratory_rate"
    OXYGEN_SATURATION = "oxygen_saturation"


class MedicationFrequency(str, Enum):
    """Medication dosing frequencies."""

    ONCE_DAILY = "once_daily"
    TWICE_DAILY = "twice_daily"
    THREE_TIMES_DAILY = "three_times_daily"
    FOUR_TIMES_DAILY = "four_times_daily"
    AS_NEEDED = "as_needed"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AllergyReactionSeverity(str, Enum):
    """Severity of allergic reactions."""

    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class SleepQuality(str, Enum):
    """Sleep quality rating."""

    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


class SmokingStatus(str, Enum):
    """Patient smoking status."""

    NEVER = "never"
    FORMER = "former"
    CURRENT = "current"


# ============================================================================
# VITAL SIGNS MODEL
# ============================================================================


class VitalSigns(BaseModel):
    """Patient vital signs with medical validation ranges."""

    heart_rate: Optional[int] = Field(None, ge=40, le=200, description="BPM (40-200)")
    blood_pressure_systolic: Optional[int] = Field(
        None, ge=60, le=220, description="mmHg (60-220)"
    )
    blood_pressure_diastolic: Optional[int] = Field(
        None, ge=40, le=130, description="mmHg (40-130)"
    )
    temperature: Optional[float] = Field(
        None, ge=95.0, le=106.0, description="°F (95-106)"
    )
    respiratory_rate: Optional[int] = Field(
        None, ge=8, le=60, description="Breaths/min (8-60)"
    )
    oxygen_saturation: Optional[int] = Field(
        None, ge=70, le=100, description="% (70-100)"
    )
    measured_at: datetime = Field(
        default_factory=datetime.now, description="When measured"
    )
    notes: Optional[str] = Field(None, description="Additional observations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "heart_rate": 72,
                "blood_pressure_systolic": 120,
                "blood_pressure_diastolic": 80,
                "temperature": 98.6,
                "respiratory_rate": 16,
                "oxygen_saturation": 98,
                "measured_at": "2025-11-30T10:30:00Z",
                "notes": "Measured at home",
            }
        }
    )


# ============================================================================
# MEDICATION MODEL
# ============================================================================


class MedicationRecord(BaseModel):
    """Medication prescription with PHI protection."""

    medication_id: str = Field(..., description="Unique medication ID")
    medication_name: str = Field(..., description="E.g., 'Metformin', 'Lisinopril'")
    dosage: str = Field(..., description="E.g., '500mg', '10mg'")
    frequency: MedicationFrequency = Field(..., description="Dosing frequency")
    start_date: datetime = Field(..., description="When started")
    end_date: Optional[datetime] = Field(
        None, description="When stopped (if applicable)"
    )
    prescriber: str = Field(..., description="Clinician name or ID")
    indication: Optional[str] = Field(
        None, description="Why prescribed (e.g., 'Type 2 Diabetes')"
    )
    side_effects_reported: List[str] = Field(
        default_factory=list, description="Known side effects"
    )
    is_active: bool = Field(True, description="Is currently taking")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "medication_id": "med_abc123",
                "medication_name": "Metformin",
                "dosage": "500mg",
                "frequency": "twice_daily",
                "start_date": "2024-01-15T00:00:00Z",
                "prescriber": "Dr. Smith",
                "indication": "Type 2 Diabetes",
                "side_effects_reported": ["nausea"],
                "is_active": True,
            }
        }
    )


# ============================================================================
# ALLERGY MODEL
# ============================================================================


class Allergy(BaseModel):
    """Allergy record with reaction details."""

    allergen: str = Field(
        ..., description="What patient is allergic to (e.g., 'Penicillin')"
    )
    reaction_type: str = Field(
        ..., description="Type of reaction (e.g., 'rash', 'anaphylaxis')"
    )
    severity: AllergyReactionSeverity = Field(..., description="Reaction severity")
    onset_date: datetime = Field(..., description="When allergy discovered")
    notes: Optional[str] = Field(None, description="Additional details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "allergen": "Penicillin",
                "reaction_type": "rash",
                "severity": "moderate",
                "onset_date": "2020-05-10T00:00:00Z",
                "notes": "Always causes hives",
            }
        }
    )


# ============================================================================
# MAIN HEALTH RECORD MODEL
# ============================================================================


class HealthRecord(BaseModel):
    """
    Complete patient health record.
    HIPAA-compliant with audit fields and encryption support.
    """

    # ========== IDENTIFIERS (encrypted in DB) ==========
    patient_id: str = Field(..., description="Encrypted patient UUID")
    medical_record_number: Optional[str] = Field(None, description="MRN")

    # ========== CURRENT VITALS ==========
    vitals: Optional[VitalSigns] = Field(None, description="Most recent vital signs")
    last_vitals_updated: Optional[datetime] = Field(
        None, description="When vitals were last measured"
    )

    # ========== MEDICATIONS ==========
    active_medications: List[MedicationRecord] = Field(
        default_factory=list, description="Currently taking"
    )
    past_medications: List[MedicationRecord] = Field(
        default_factory=list, description="Previously took"
    )

    # ========== ALLERGIES ==========
    allergies: List[Allergy] = Field(
        default_factory=list, description="Known allergies"
    )

    # ========== MEDICAL HISTORY ==========
    chronic_conditions: List[str] = Field(
        default_factory=list, description="E.g., ['Type 2 Diabetes', 'Hypertension']"
    )
    past_surgeries: List[str] = Field(
        default_factory=list, description="Previous surgical procedures"
    )
    family_history: Optional[str] = Field(
        None, description="Relevant family medical history"
    )

    # ========== LIFESTYLE ==========
    daily_steps: Optional[int] = Field(None, ge=0, description="Daily step count")
    exercise_minutes_per_week: Optional[int] = Field(
        None, ge=0, description="Weekly exercise"
    )
    sleep_hours_per_night: Optional[float] = Field(
        None, ge=0, le=24, description="Average sleep"
    )
    sleep_quality: Optional[SleepQuality] = Field(None, description="Sleep quality")
    smoking_status: Optional[SmokingStatus] = Field(None, description="Smoking status")
    alcohol_use: Optional[str] = Field(None, description="Alcohol consumption")

    # ========== CURRENT SYMPTOMS ==========
    reported_symptoms: List[str] = Field(
        default_factory=list, description="Current symptoms reported"
    )
    symptom_severity: Optional[int] = Field(
        None, ge=1, le=10, description="Severity 1-10"
    )
    symptom_onset_date: Optional[datetime] = Field(
        None, description="When symptoms started"
    )

    # ========== HIPAA COMPLIANCE ==========
    data_classification: str = Field(
        default="CONFIDENTIAL_MEDICAL", description="PHI classification level"
    )
    hipaa_consent: bool = Field(True, description="Patient consented to PHI processing")

    # ========== AUDIT FIELDS ==========
    created_at: datetime = Field(
        default_factory=datetime.now, description="Record creation date"
    )
    modified_at: datetime = Field(
        default_factory=datetime.now, description="Last modification date"
    )
    last_accessed_at: Optional[datetime] = Field(
        None, description="Last access for audit"
    )
    accessed_by: List[str] = Field(
        default_factory=list, description="User IDs who accessed this record"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "enc_patient_abc123xyz",
                "medical_record_number": "MRN123456",
                "vitals": {
                    "heart_rate": 72,
                    "blood_pressure_systolic": 120,
                    "blood_pressure_diastolic": 80,
                    "temperature": 98.6,
                    "measured_at": "2025-11-30T10:30:00Z",
                },
                "active_medications": [
                    {
                        "medication_id": "med_001",
                        "medication_name": "Metformin",
                        "dosage": "500mg",
                        "frequency": "twice_daily",
                        "prescriber": "Dr. Smith",
                    }
                ],
                "allergies": [
                    {
                        "allergen": "Penicillin",
                        "reaction_type": "rash",
                        "severity": "moderate",
                        "onset_date": "2020-05-10T00:00:00Z",
                    }
                ],
                "chronic_conditions": ["Type 2 Diabetes", "Hypertension"],
                "data_classification": "CONFIDENTIAL_MEDICAL",
            }
        }
    )


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class HealthRecordCreate(BaseModel):
    """Request model for creating health records."""

    patient_id: str
    vitals: Optional[VitalSigns] = None
    medications: Optional[List[MedicationRecord]] = None
    allergies: Optional[List[Allergy]] = None
    chronic_conditions: Optional[List[str]] = None
    symptoms: Optional[List[str]] = None


class HealthRecordUpdate(BaseModel):
    """Request model for updating health records."""

    vitals: Optional[VitalSigns] = None
    medications: Optional[List[MedicationRecord]] = None
    allergies: Optional[List[Allergy]] = None
    chronic_conditions: Optional[List[str]] = None
    symptoms: Optional[List[str]] = None


class HealthRecordResponse(BaseModel):
    """Response model for health record queries."""

    success: bool
    patient_id: str
    record: Optional[HealthRecord] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class HealthMetrics(BaseModel):
    """User health metrics for risk assessment"""

    age: int = Field(..., ge=18, le=120)
    gender: str = Field(..., pattern="^(M|F|Other)$")
    blood_pressure_systolic: Optional[int] = Field(None, ge=60, le=300)
    blood_pressure_diastolic: Optional[int] = Field(None, ge=40, le=200)
    cholesterol_total: Optional[int] = Field(None, ge=0, le=400)
    cholesterol_ldl: Optional[int] = Field(None, ge=0, le=400)
    cholesterol_hdl: Optional[int] = Field(None, ge=0, le=200)
    smoking_status: str = Field(default="never", pattern="^(never|former|current)$")
    diabetes: bool = Field(default=False)
    family_history_heart_disease: bool = Field(default=False)
    physical_activity_minutes_per_week: int = Field(default=0, ge=0, le=1000)
