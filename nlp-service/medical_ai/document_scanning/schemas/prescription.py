"""
JSON Schema for Prescription extraction.

Defines structured data format for medical prescriptions.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from enum import Enum


class MedicationType(str, Enum):
    """Types of medication forms."""

    TABLET = "tablet"
    CAPSULE = "capsule"
    SYRUP = "syrup"
    INJECTION = "injection"
    CREAM = "cream"
    OINTMENT = "ointment"
    DROPS = "drops"
    INHALER = "inhaler"
    PATCH = "patch"
    POWDER = "powder"
    SUSPENSION = "suspension"
    OTHER = "other"


class FrequencyCode(str, Enum):
    """Standard prescription frequency codes."""

    OD = "OD"  # Once daily
    BD = "BD"  # Twice daily
    TID = "TID"  # Three times daily
    QID = "QID"  # Four times daily
    HS = "HS"  # At bedtime
    SOS = "SOS"  # As needed
    PRN = "PRN"  # As needed
    STAT = "STAT"  # Immediately
    AC = "AC"  # Before meals
    PC = "PC"  # After meals


class Medication(BaseModel):
    """Individual medication in prescription."""

    drug_name: str = Field(..., description="Name of the drug/medicine")
    generic_name: Optional[str] = Field(None, description="Generic/scientific name")
    brand_name: Optional[str] = Field(None, description="Brand name if different")

    # Dosage
    dosage_value: Optional[str] = Field(None, description="Dosage amount (e.g., 500)")
    dosage_unit: Optional[str] = Field(None, description="Dosage unit (mg, ml, etc.)")
    form: Optional[MedicationType] = Field(None, description="Medication form")

    # Frequency
    frequency: Optional[str] = Field(None, description="How often to take")
    frequency_code: Optional[FrequencyCode] = Field(
        None, description="Standard frequency code"
    )
    times_per_day: Optional[int] = Field(
        None, ge=1, le=24, description="Number of times per day"
    )

    # Timing
    timing: Optional[str] = Field(None, description="When to take (before meals, etc.)")
    specific_times: Optional[List[str]] = Field(
        None, description="Specific times (8am, 2pm, etc.)"
    )

    # Duration
    duration_value: Optional[int] = Field(None, description="Duration number")
    duration_unit: Optional[str] = Field(
        None, description="Duration unit (days, weeks, months)"
    )

    # Quantity
    quantity: Optional[int] = Field(None, description="Total quantity to dispense")
    refills: Optional[int] = Field(None, ge=0, description="Number of refills allowed")

    # Instructions
    route: Optional[str] = Field(
        None, description="Route of administration (oral, topical, etc.)"
    )
    special_instructions: Optional[str] = Field(
        None, description="Special instructions"
    )

    # Extraction metadata
    confidence: float = Field(
        default=1.0, ge=0, le=1, description="Extraction confidence"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "drug_name": "Metformin",
                "generic_name": "Metformin Hydrochloride",
                "brand_name": "Glucophage",
                "dosage_value": "500",
                "dosage_unit": "mg",
                "form": "tablet",
                "frequency": "Twice daily",
                "frequency_code": "BD",
                "times_per_day": 2,
                "timing": "After meals",
                "duration_value": 30,
                "duration_unit": "days",
                "quantity": 60,
                "route": "oral",
                "confidence": 0.95,
            }
        }


class PrescriptionSchema(BaseModel):
    """
    Structured schema for prescription extraction.

    Handles:
    - Patient identification
    - Doctor/prescriber information
    - Multiple medications with full details
    - Duration and refill information
    - Special instructions
    """

    # Patient Information
    patient_name: Optional[str] = Field(None, description="Patient full name")
    patient_id: Optional[str] = Field(None, description="Patient ID/MRN")
    patient_age: Optional[int] = Field(None, ge=0, le=150, description="Patient age")
    patient_gender: Optional[str] = Field(None, description="Patient gender")
    patient_weight: Optional[float] = Field(None, description="Patient weight in kg")
    patient_phone: Optional[str] = Field(None, description="Patient phone")
    patient_address: Optional[str] = Field(None, description="Patient address")

    # Prescriber Information
    doctor_name: Optional[str] = Field(None, description="Prescribing doctor name")
    doctor_qualification: Optional[str] = Field(
        None, description="Doctor qualifications"
    )
    doctor_registration_no: Optional[str] = Field(
        None, description="Medical registration number"
    )
    doctor_specialty: Optional[str] = Field(None, description="Doctor specialty")

    # Hospital/Clinic Information
    hospital_name: Optional[str] = Field(None, description="Hospital/Clinic name")
    hospital_address: Optional[str] = Field(None, description="Hospital address")
    hospital_phone: Optional[str] = Field(None, description="Hospital phone")

    # Prescription Details
    prescription_date: Optional[date] = Field(None, description="Prescription date")
    prescription_id: Optional[str] = Field(None, description="Prescription/Rx number")
    valid_until: Optional[date] = Field(None, description="Prescription validity date")

    # Diagnosis
    diagnosis: Optional[str] = Field(None, description="Primary diagnosis")
    secondary_diagnosis: Optional[List[str]] = Field(
        None, description="Secondary diagnoses"
    )

    # Medications
    medications: List[Medication] = Field(
        default_factory=list, description="List of medications"
    )

    # General Instructions
    general_instructions: Optional[str] = Field(
        None, description="General instructions"
    )
    dietary_advice: Optional[str] = Field(None, description="Dietary recommendations")
    follow_up_date: Optional[date] = Field(
        None, description="Follow-up appointment date"
    )
    next_visit: Optional[str] = Field(None, description="Next visit instructions")

    # Emergency
    emergency_instructions: Optional[str] = Field(
        None, description="Emergency instructions"
    )

    # Metadata
    extraction_confidence: float = Field(
        default=1.0, ge=0, le=1, description="Overall extraction confidence"
    )
    needs_verification: bool = Field(
        default=True, description="Whether human verification is needed"
    )
    uncertain_fields: List[str] = Field(
        default_factory=list, description="Fields needing review"
    )
    is_handwritten: bool = Field(
        default=False, description="Whether prescription is handwritten"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "patient_name": "Jane Smith",
                "doctor_name": "Dr. John Wilson",
                "doctor_registration_no": "MCI123456",
                "hospital_name": "City Medical Center",
                "prescription_date": "2025-12-15",
                "diagnosis": "Type 2 Diabetes Mellitus",
                "medications": [
                    {
                        "drug_name": "Metformin",
                        "dosage_value": "500",
                        "dosage_unit": "mg",
                        "frequency": "Twice daily",
                        "timing": "After meals",
                        "duration_value": 30,
                        "duration_unit": "days",
                    }
                ],
                "follow_up_date": "2026-01-15",
                "extraction_confidence": 0.88,
                "needs_verification": True,
            }
        }


# Common frequency code mappings
FREQUENCY_MAPPINGS = {
    "once daily": FrequencyCode.OD,
    "once a day": FrequencyCode.OD,
    "od": FrequencyCode.OD,
    "twice daily": FrequencyCode.BD,
    "twice a day": FrequencyCode.BD,
    "bd": FrequencyCode.BD,
    "bid": FrequencyCode.BD,
    "three times daily": FrequencyCode.TID,
    "three times a day": FrequencyCode.TID,
    "tid": FrequencyCode.TID,
    "four times daily": FrequencyCode.QID,
    "four times a day": FrequencyCode.QID,
    "qid": FrequencyCode.QID,
    "at bedtime": FrequencyCode.HS,
    "at night": FrequencyCode.HS,
    "hs": FrequencyCode.HS,
    "as needed": FrequencyCode.PRN,
    "when required": FrequencyCode.SOS,
    "sos": FrequencyCode.SOS,
    "prn": FrequencyCode.PRN,
    "before meals": FrequencyCode.AC,
    "ac": FrequencyCode.AC,
    "after meals": FrequencyCode.PC,
    "pc": FrequencyCode.PC,
}


def parse_frequency(text: str) -> Optional[FrequencyCode]:
    """Parse frequency text to standard code."""
    text_lower = text.lower().strip()
    return FREQUENCY_MAPPINGS.get(text_lower)
