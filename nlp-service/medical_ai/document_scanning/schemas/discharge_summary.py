"""
JSON Schema for Discharge Summary extraction.

Defines structured data format for hospital discharge summaries.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from enum import Enum


class DischargeStatus(str, Enum):
    """Patient discharge status."""

    RECOVERED = "recovered"
    IMPROVED = "improved"
    STABLE = "stable"
    AGAINST_ADVICE = "against_medical_advice"
    REFERRED = "referred"
    EXPIRED = "expired"
    UNCHANGED = "unchanged"


class AdmissionType(str, Enum):
    """Type of admission."""

    EMERGENCY = "emergency"
    ELECTIVE = "elective"
    TRANSFER = "transfer"
    ROUTINE = "routine"


class ProcedureRecord(BaseModel):
    """Record of a procedure performed."""

    procedure_name: str = Field(..., description="Name of the procedure")
    procedure_date: Optional[date] = Field(None, description="Date performed")
    surgeon: Optional[str] = Field(None, description="Performing surgeon")
    findings: Optional[str] = Field(None, description="Procedure findings")
    complications: Optional[str] = Field(None, description="Any complications")
    notes: Optional[str] = Field(None, description="Additional notes")


class MedicationAtDischarge(BaseModel):
    """Medication prescribed at discharge."""

    drug_name: str = Field(..., description="Medication name")
    dosage: Optional[str] = Field(None, description="Dosage")
    frequency: Optional[str] = Field(None, description="Frequency")
    duration: Optional[str] = Field(None, description="Duration")
    instructions: Optional[str] = Field(None, description="Special instructions")


class VitalSignsRecord(BaseModel):
    """Vital signs at a point in time."""

    recorded_at: Optional[str] = Field(None, description="When recorded")
    blood_pressure: Optional[str] = Field(None, description="BP (systolic/diastolic)")
    heart_rate: Optional[int] = Field(None, description="Heart rate (bpm)")
    temperature: Optional[float] = Field(None, description="Temperature")
    respiratory_rate: Optional[int] = Field(None, description="Respiratory rate")
    spo2: Optional[int] = Field(None, description="Oxygen saturation (%)")
    weight: Optional[float] = Field(None, description="Weight (kg)")


class FollowUpInstruction(BaseModel):
    """Follow-up appointment instruction."""

    department: Optional[str] = Field(None, description="Department to visit")
    doctor: Optional[str] = Field(None, description="Doctor to see")
    date: Optional[date] = Field(None, description="Follow-up date")
    timeframe: Optional[str] = Field(None, description="Timeframe (e.g., '1 week')")
    purpose: Optional[str] = Field(None, description="Purpose of follow-up")


class DischargeSummarySchema(BaseModel):
    """
    Structured schema for discharge summary extraction.

    Handles:
    - Patient and admission details
    - Diagnosis (primary and secondary)
    - Hospital course and treatment
    - Procedures performed
    - Discharge medications
    - Follow-up instructions
    - Home care advice
    """

    # Patient Information
    patient_name: Optional[str] = Field(None, description="Patient name")
    patient_id: Optional[str] = Field(None, description="Patient ID/MRN")
    patient_age: Optional[int] = Field(None, ge=0, le=150, description="Patient age")
    patient_gender: Optional[str] = Field(None, description="Patient gender")
    patient_dob: Optional[date] = Field(None, description="Date of birth")
    patient_address: Optional[str] = Field(None, description="Patient address")
    patient_phone: Optional[str] = Field(None, description="Patient phone")
    blood_group: Optional[str] = Field(None, description="Blood group")

    # Hospital Information
    hospital_name: Optional[str] = Field(None, description="Hospital name")
    hospital_address: Optional[str] = Field(None, description="Hospital address")
    department: Optional[str] = Field(None, description="Department")
    ward: Optional[str] = Field(None, description="Ward name")
    room_number: Optional[str] = Field(None, description="Room/Bed number")

    # Admission Details
    admission_number: Optional[str] = Field(None, description="Admission/IP number")
    admission_date: Optional[date] = Field(None, description="Admission date")
    admission_time: Optional[str] = Field(None, description="Admission time")
    admission_type: Optional[AdmissionType] = Field(
        None, description="Type of admission"
    )

    # Discharge Details
    discharge_date: Optional[date] = Field(None, description="Discharge date")
    discharge_time: Optional[str] = Field(None, description="Discharge time")
    discharge_status: Optional[DischargeStatus] = Field(
        None, description="Discharge status"
    )
    length_of_stay: Optional[int] = Field(
        None, ge=0, description="Length of stay in days"
    )

    # Medical Team
    attending_doctor: Optional[str] = Field(None, description="Attending physician")
    consulting_doctors: Optional[List[str]] = Field(
        None, description="Consulting doctors"
    )
    resident_doctor: Optional[str] = Field(None, description="Resident doctor")

    # Diagnosis
    chief_complaint: Optional[str] = Field(
        None, description="Chief complaint at admission"
    )
    primary_diagnosis: Optional[str] = Field(
        None, description="Primary/Principal diagnosis"
    )
    secondary_diagnoses: Optional[List[str]] = Field(
        None, description="Secondary diagnoses"
    )
    icd_codes: Optional[List[str]] = Field(None, description="ICD diagnosis codes")

    # History
    history_of_present_illness: Optional[str] = Field(None, description="HPI")
    past_medical_history: Optional[str] = Field(
        None, description="Past medical history"
    )
    past_surgical_history: Optional[str] = Field(
        None, description="Past surgical history"
    )
    family_history: Optional[str] = Field(None, description="Family history")
    allergies: Optional[List[str]] = Field(None, description="Known allergies")

    # Examination
    general_examination: Optional[str] = Field(
        None, description="General examination findings"
    )
    systemic_examination: Optional[str] = Field(
        None, description="Systemic examination findings"
    )
    vitals_at_admission: Optional[VitalSignsRecord] = Field(
        None, description="Vitals at admission"
    )
    vitals_at_discharge: Optional[VitalSignsRecord] = Field(
        None, description="Vitals at discharge"
    )

    # Investigations
    investigations_summary: Optional[str] = Field(
        None, description="Summary of investigations"
    )
    key_lab_results: Optional[str] = Field(None, description="Key laboratory results")
    imaging_findings: Optional[str] = Field(None, description="Imaging findings")

    # Hospital Course
    hospital_course: Optional[str] = Field(
        None, description="Course during hospital stay"
    )
    treatment_given: Optional[str] = Field(
        None, description="Treatment given during stay"
    )

    # Procedures
    procedures: List[ProcedureRecord] = Field(
        default_factory=list, description="Procedures performed"
    )
    surgery_notes: Optional[str] = Field(None, description="Surgery/operative notes")

    # Discharge Medications
    discharge_medications: List[MedicationAtDischarge] = Field(
        default_factory=list, description="Medications prescribed at discharge"
    )

    # Instructions
    general_advice: Optional[str] = Field(None, description="General advice")
    dietary_instructions: Optional[str] = Field(
        None, description="Dietary instructions"
    )
    activity_restrictions: Optional[str] = Field(
        None, description="Activity restrictions"
    )
    wound_care: Optional[str] = Field(None, description="Wound care instructions")
    warning_signs: Optional[List[str]] = Field(
        None, description="Warning signs to watch for"
    )
    emergency_instructions: Optional[str] = Field(
        None, description="When to seek emergency care"
    )

    # Follow-up
    follow_up_instructions: List[FollowUpInstruction] = Field(
        default_factory=list, description="Follow-up appointments"
    )
    next_appointment_date: Optional[date] = Field(
        None, description="Next appointment date"
    )

    # Condition at Discharge
    condition_at_discharge: Optional[str] = Field(
        None, description="Condition at discharge"
    )
    prognosis: Optional[str] = Field(None, description="Prognosis")

    # Metadata
    prepared_by: Optional[str] = Field(None, description="Document prepared by")
    verified_by: Optional[str] = Field(None, description="Document verified by")
    summary_date: Optional[date] = Field(None, description="Date summary was prepared")

    extraction_confidence: float = Field(
        default=1.0, ge=0, le=1, description="Overall extraction confidence"
    )
    needs_verification: bool = Field(
        default=True, description="Whether human verification is needed"
    )
    uncertain_fields: List[str] = Field(
        default_factory=list, description="Fields needing review"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "patient_name": "John Doe",
                "patient_id": "MRN123456",
                "patient_age": 55,
                "hospital_name": "City General Hospital",
                "admission_date": "2025-12-10",
                "discharge_date": "2025-12-15",
                "discharge_status": "improved",
                "attending_doctor": "Dr. Jane Smith",
                "chief_complaint": "Chest pain and shortness of breath",
                "primary_diagnosis": "Acute Coronary Syndrome",
                "secondary_diagnoses": ["Type 2 Diabetes", "Hypertension"],
                "hospital_course": "Patient was admitted with chest pain...",
                "discharge_medications": [
                    {
                        "drug_name": "Aspirin",
                        "dosage": "75mg",
                        "frequency": "Once daily",
                        "duration": "Lifelong",
                    }
                ],
                "follow_up_instructions": [
                    {
                        "department": "Cardiology",
                        "timeframe": "1 week",
                        "purpose": "Review cardiac status",
                    }
                ],
                "extraction_confidence": 0.90,
                "needs_verification": True,
            }
        }


def calculate_length_of_stay(admission_date: date, discharge_date: date) -> int:
    """Calculate length of hospital stay in days."""
    delta = discharge_date - admission_date
    return max(delta.days, 1)  # Minimum 1 day
