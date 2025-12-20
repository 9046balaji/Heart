"""
JSON Schema for Lab Report extraction.

Defines structured data format for laboratory test results.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from enum import Enum


class TestFlag(str, Enum):
    """Lab test result flags."""

    HIGH = "H"
    LOW = "L"
    NORMAL = "N"
    CRITICAL_HIGH = "CH"
    CRITICAL_LOW = "CL"
    ABNORMAL = "A"


class TestResult(BaseModel):
    """Individual test result."""

    test_name: str = Field(..., description="Name of the test")
    value: str = Field(..., description="Test result value")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    reference_range: Optional[str] = Field(None, description="Normal reference range")
    flag: Optional[TestFlag] = Field(None, description="H=High, L=Low, N=Normal, etc.")
    notes: Optional[str] = Field(None, description="Additional notes")
    confidence: float = Field(
        default=1.0, ge=0, le=1, description="Extraction confidence"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "test_name": "Hemoglobin",
                "value": "14.5",
                "unit": "g/dL",
                "reference_range": "12.0-16.0",
                "flag": "N",
                "notes": None,
                "confidence": 0.95,
            }
        }


class LabReportSchema(BaseModel):
    """
    Structured schema for lab report extraction.

    This schema is used for schema-driven extraction as
    recommended in medical.md Section 3.

    Capabilities:
    - Patient identification
    - Lab/hospital information
    - Sample collection details
    - Multiple test results with flags
    - Doctor information
    """

    # Patient Information
    patient_name: Optional[str] = Field(None, description="Patient full name")
    patient_id: Optional[str] = Field(None, description="Patient ID/MRN")
    patient_age: Optional[int] = Field(None, description="Patient age", ge=0, le=150)
    patient_gender: Optional[str] = Field(None, description="Patient gender")
    patient_dob: Optional[date] = Field(None, description="Patient date of birth")
    patient_phone: Optional[str] = Field(None, description="Patient phone number")

    # Lab/Hospital Information
    lab_name: Optional[str] = Field(None, description="Laboratory/Hospital name")
    lab_address: Optional[str] = Field(None, description="Laboratory address")
    lab_phone: Optional[str] = Field(None, description="Laboratory phone")
    lab_accreditation: Optional[str] = Field(
        None, description="Lab accreditation (e.g., NABL)"
    )

    # Report Details
    report_id: Optional[str] = Field(None, description="Report/Sample ID")
    report_date: Optional[date] = Field(None, description="Report date")

    # Sample Information
    sample_type: Optional[str] = Field(
        None, description="Sample type (blood, urine, etc.)"
    )
    sample_collected_date: Optional[date] = Field(
        None, description="Sample collection date"
    )
    sample_collected_time: Optional[str] = Field(
        None, description="Sample collection time"
    )
    sample_received_date: Optional[date] = Field(
        None, description="Sample received date"
    )
    fasting: Optional[bool] = Field(None, description="Whether patient was fasting")

    # Test Results
    test_category: Optional[str] = Field(
        None, description="Category (CBC, Lipid Panel, etc.)"
    )
    test_results: List[TestResult] = Field(
        default_factory=list, description="List of test results"
    )

    # Doctor Information
    referring_doctor: Optional[str] = Field(None, description="Referring doctor name")
    pathologist: Optional[str] = Field(None, description="Pathologist name")
    technician: Optional[str] = Field(None, description="Lab technician name")

    # Interpretation
    interpretation: Optional[str] = Field(
        None, description="Overall interpretation/comments"
    )
    critical_values: Optional[List[str]] = Field(
        None, description="Any critical values detected"
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

    class Config:
        json_schema_extra = {
            "example": {
                "patient_name": "John Doe",
                "patient_id": "MRN123456",
                "patient_age": 45,
                "patient_gender": "Male",
                "lab_name": "ABC Diagnostics",
                "report_date": "2025-12-15",
                "sample_type": "Blood",
                "test_category": "Complete Blood Count",
                "test_results": [
                    {
                        "test_name": "Hemoglobin",
                        "value": "14.5",
                        "unit": "g/dL",
                        "reference_range": "12.0-16.0",
                        "flag": "N",
                    }
                ],
                "extraction_confidence": 0.92,
                "needs_verification": True,
                "uncertain_fields": ["patient_phone"],
            }
        }


# Common lab test categories for classification
LAB_TEST_CATEGORIES = {
    "cbc": ["hemoglobin", "hematocrit", "rbc", "wbc", "platelet", "mcv", "mch", "mchc"],
    "lipid_panel": ["cholesterol", "triglycerides", "hdl", "ldl", "vldl"],
    "liver_function": [
        "ast",
        "alt",
        "bilirubin",
        "albumin",
        "alkaline phosphatase",
        "ggt",
    ],
    "kidney_function": ["creatinine", "bun", "urea", "gfr", "uric acid"],
    "thyroid": ["tsh", "t3", "t4", "ft3", "ft4"],
    "diabetes": ["glucose", "hba1c", "fasting blood sugar", "fbs", "ppbs"],
    "cardiac_markers": ["troponin", "ck-mb", "bnp", "crp"],
    "electrolytes": [
        "sodium",
        "potassium",
        "chloride",
        "bicarbonate",
        "calcium",
        "magnesium",
    ],
}


def identify_test_category(test_names: List[str]) -> str:
    """
    Identify the lab test category based on test names.

    Args:
        test_names: List of test names from the report

    Returns:
        Category name or 'general' if no match
    """
    test_names_lower = [t.lower() for t in test_names]

    for category, keywords in LAB_TEST_CATEGORIES.items():
        matches = sum(1 for kw in keywords if any(kw in tn for tn in test_names_lower))
        if matches >= 2:  # At least 2 matches to identify category
            return category

    return "general"
