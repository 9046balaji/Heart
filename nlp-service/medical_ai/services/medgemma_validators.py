"""
Pydantic validators for MedGemma service outputs.

Provides validation for extracted medical entities to prevent hallucinations
and ensure data quality in medical AI responses.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional
from enum import Enum


class DrugUnit(str, Enum):
    """Standard units for drug dosages."""

    MG = "mg"
    MCG = "mcg"
    G = "g"
    ML = "ml"
    UNITS = "units"
    IU = "IU"
    MEQ = "mEq"


class ExtractedDrug(BaseModel):
    """Validated drug extraction."""

    name: str = Field(..., min_length=2, max_length=100, description="Drug name")
    dosage_value: Optional[float] = Field(
        None, ge=0, le=10000, description="Dosage amount"
    )
    dosage_unit: Optional[DrugUnit] = Field(None, description="Dosage unit")
    frequency: Optional[str] = Field(
        None, max_length=50, description="How often to take"
    )
    route: Optional[str] = Field(
        None, max_length=50, description="Route of administration"
    )
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="Confidence score")

    @validator("name")
    def validate_drug_name(cls, v):
        """Validate drug name to reject common hallucination patterns."""
        # Reject common hallucination patterns
        hallucination_patterns = [
            "unknown",
            "n/a",
            "not specified",
            "drug x",
            "medication",
        ]
        if v.lower() in hallucination_patterns:
            raise ValueError(f"Invalid drug name: {v}")
        return v


class ExtractedLabValue(BaseModel):
    """Validated lab result extraction."""

    test_name: str = Field(..., min_length=2, description="Name of the test")
    value: float = Field(..., description="Test result value")
    unit: str = Field(..., description="Measurement unit")
    reference_min: Optional[float] = Field(None, description="Reference range minimum")
    reference_max: Optional[float] = Field(None, description="Reference range maximum")
    is_abnormal: Optional[bool] = Field(None, description="Whether value is abnormal")

    @validator("value")
    def validate_value_range(cls, v, values):
        """Validate that lab values are physiologically plausible."""
        # Flag physiologically impossible values
        if abs(v) > 100000:
            raise ValueError(f"Lab value {v} is physiologically implausible")
        return v


class MedGemmaExtractionResult(BaseModel):
    """Validated extraction result container."""

    patient_name: Optional[str] = Field(None, description="Patient name")
    date_of_service: Optional[str] = Field(None, description="Date of service")
    document_type: str = Field(..., description="Type of medical document")
    medications: List[ExtractedDrug] = Field(
        default=[], description="Extracted medications"
    )
    lab_values: List[ExtractedLabValue] = Field(
        default=[], description="Extracted lab values"
    )
    diagnoses: List[str] = Field(default=[], description="Extracted diagnoses")
    raw_confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Overall confidence score"
    )
