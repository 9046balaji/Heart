"""
Pydantic schemas for vitals data validation.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class VitalsReading(BaseModel):
    """Validated vitals reading from smartwatch."""

    heart_rate: int = Field(..., ge=20, le=300, description="Heart rate in BPM")
    blood_pressure_systolic: Optional[int] = Field(
        None, ge=60, le=250, description="Systolic blood pressure in mmHg"
    )
    blood_pressure_diastolic: Optional[int] = Field(
        None, ge=40, le=150, description="Diastolic blood pressure in mmHg"
    )
    blood_oxygen: Optional[float] = Field(
        None, ge=70.0, le=100.0, description="Blood oxygen saturation percentage"
    )
    temperature: Optional[float] = Field(
        None, ge=90.0, le=110.0, description="Body temperature in Fahrenheit"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of the reading"
    )

    @validator("heart_rate")
    def validate_heart_rate(cls, v):
        """Validate heart rate is an integer."""
        if not isinstance(v, int):
            raise ValueError("heart_rate must be an integer")
        return v

    @validator("blood_pressure_diastolic")
    def validate_blood_pressure(cls, v, values, **kwargs):
        """Validate that diastolic pressure is less than systolic pressure."""
        systolic = values.get("blood_pressure_systolic")
        if systolic is not None and v is not None and v >= systolic:
            raise ValueError("Diastolic pressure must be less than systolic pressure")
        return v

    class Config:
        max_anystr_length = 1000  # Prevent payload bombing
        extra = "forbid"  # Reject unknown fields
        json_schema_extra = {
            "example": {
                "heart_rate": 72,
                "blood_pressure_systolic": 120,
                "blood_pressure_diastolic": 80,
                "blood_oxygen": 98.0,
                "temperature": 98.6,
                "timestamp": "2025-12-19T10:30:00Z",
            }
        }


class VitalsSubmission(BaseModel):
    """Wrapper for vitals submission with device ID."""

    device_id: str = Field(
        ..., min_length=1, max_length=100, description="Device identifier"
    )
    reading: VitalsReading = Field(..., description="Vitals reading data")
