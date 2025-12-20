"""
Appointment management models with scheduling and validation.

Phase 3: Appointment Models
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from datetime import datetime, time
from typing import Optional, List
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================


class AppointmentStatus(str, Enum):
    """Appointment status lifecycle."""

    PENDING = "pending"  # Awaiting confirmation
    CONFIRMED = "confirmed"  # Confirmed with provider
    CANCELLED = "cancelled"  # User or provider cancelled
    COMPLETED = "completed"  # Appointment happened
    NO_SHOW = "no_show"  # Patient didn't attend
    RESCHEDULED = "rescheduled"  # Moved to different time


class AppointmentType(str, Enum):
    """Types of medical appointments."""

    CONSULTATION = "consultation"  # General consultation
    FOLLOW_UP = "follow_up"  # Follow-up visit
    PROCEDURE = "procedure"  # Medical procedure
    LABORATORY = "laboratory"  # Lab work/testing
    IMAGING = "imaging"  # X-ray, ultrasound, MRI, etc.
    VACCINATION = "vaccination"  # Vaccine administration
    ROUTINE = "routine"  # Routine checkup
    URGENT = "urgent"  # Urgent/same-day visit


class ReminderType(str, Enum):
    """Reminder notification types."""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class AvailabilityStatus(str, Enum):
    """Availability slot status."""

    AVAILABLE = "available"
    BOOKED = "booked"
    BLOCKED = "blocked"  # Provider not available


# ============================================================================
# PROVIDER MODELS
# ============================================================================


class Provider(BaseModel):
    """Healthcare provider information."""

    provider_id: str = Field(..., description="Unique provider ID")
    name: str = Field(..., description="Provider full name")
    specialty: str = Field(..., description="Medical specialty (Cardiology, etc.)")
    phone: Optional[str] = Field(None, description="Provider phone number")
    email: Optional[str] = Field(None, description="Provider email")
    office_location: Optional[str] = Field(None, description="Physical office address")
    organization: Optional[str] = Field(None, description="Hospital/Clinic name")
    is_accepting_patients: bool = Field(True, description="Accepting new patients")
    average_rating: Optional[float] = Field(
        None, ge=0, le=5, description="Average rating (0-5)"
    )
    total_reviews: Optional[int] = Field(None, ge=0, description="Number of reviews")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider_id": "prov_123",
                "name": "Dr. Sarah Johnson",
                "specialty": "Cardiology",
                "phone": "555-0123",
                "email": "dr.johnson@clinic.com",
                "office_location": "123 Medical Plaza, Suite 200",
                "organization": "Heart Health Clinic",
                "is_accepting_patients": True,
                "average_rating": 4.8,
                "total_reviews": 156,
            }
        }
    )


# ============================================================================
# AVAILABILITY MODELS
# ============================================================================


class TimeSlot(BaseModel):
    """Individual appointment time slot."""

    slot_id: str = Field(..., description="Unique slot identifier")
    provider_id: str = Field(..., description="Provider offering this slot")
    start_time: datetime = Field(..., description="Appointment start time")
    end_time: datetime = Field(..., description="Appointment end time")
    status: AvailabilityStatus = Field(
        AvailabilityStatus.AVAILABLE, description="Slot availability"
    )
    appointment_duration_minutes: int = Field(
        30, ge=15, le=480, description="Duration in minutes"
    )

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v, info):
        """Ensure end_time is after start_time."""
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slot_id": "slot_456",
                "provider_id": "prov_123",
                "start_time": "2025-12-15T10:00:00",
                "end_time": "2025-12-15T10:30:00",
                "status": "available",
                "appointment_duration_minutes": 30,
            }
        }
    )


class ProviderSchedule(BaseModel):
    """Provider availability schedule."""

    schedule_id: str = Field(..., description="Unique schedule ID")
    provider_id: str = Field(..., description="Provider ID")
    available_slots: List[TimeSlot] = Field(
        default_factory=list, description="Available time slots"
    )
    blocked_dates: List[datetime] = Field(
        default_factory=list, description="Dates provider is unavailable"
    )
    working_hours_start: time = Field(
        default=time(9, 0), description="Daily work start time (HH:MM)"
    )
    working_hours_end: time = Field(
        default=time(17, 0), description="Daily work end time (HH:MM)"
    )
    days_off: List[str] = Field(
        default_factory=list, description="Days off (Mon, Tue, etc.)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schedule_id": "sched_789",
                "provider_id": "prov_123",
                "available_slots": [],
                "blocked_dates": [],
                "working_hours_start": "09:00",
                "working_hours_end": "17:00",
                "days_off": ["Saturday", "Sunday"],
            }
        }
    )


# ============================================================================
# APPOINTMENT MODELS
# ============================================================================


class AppointmentReminder(BaseModel):
    """Appointment reminder configuration."""

    reminder_id: str = Field(..., description="Unique reminder ID")
    reminder_type: ReminderType = Field(..., description="Reminder delivery method")
    time_before_minutes: int = Field(
        15, ge=1, le=10080, description="Minutes before appointment"
    )
    is_sent: bool = Field(False, description="Whether reminder was sent")
    sent_at: Optional[datetime] = Field(None, description="When reminder was sent")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reminder_id": "rem_001",
                "reminder_type": "email",
                "time_before_minutes": 24 * 60,
                "is_sent": False,
            }
        }
    )


class Appointment(BaseModel):
    """Complete appointment record with HIPAA compliance."""

    # Identifiers
    appointment_id: str = Field(..., description="Unique appointment ID")
    patient_id: str = Field(..., description="Patient ID (encrypted)")
    provider_id: str = Field(..., description="Provider ID")

    # Appointment details
    appointment_type: AppointmentType = Field(..., description="Type of appointment")
    status: AppointmentStatus = Field(
        AppointmentStatus.PENDING, description="Current status"
    )
    scheduled_datetime: datetime = Field(..., description="Scheduled appointment time")
    estimated_duration_minutes: int = Field(
        30, ge=15, le=480, description="Expected duration"
    )

    # Location and access
    location: Optional[str] = Field(
        None, description="Physical location or telehealth info"
    )
    is_telehealth: bool = Field(False, description="Virtual appointment flag")
    meeting_url: Optional[str] = Field(None, description="Telehealth meeting URL")

    # Medical context
    reason_for_visit: str = Field(
        ..., description="Chief complaint or reason for visit"
    )
    clinical_notes: Optional[str] = Field(None, description="Provider's notes")
    relevant_medications: List[str] = Field(
        default_factory=list, description="Current medications"
    )
    known_allergies: List[str] = Field(
        default_factory=list, description="Known allergies"
    )

    # Reminders
    reminders: List[AppointmentReminder] = Field(
        default_factory=list, description="Scheduled reminders"
    )

    # HIPAA compliance
    data_classification: str = Field(
        "CONFIDENTIAL_MEDICAL", description="Data sensitivity level"
    )
    patient_confirmed: bool = Field(False, description="Patient confirmed attendance")
    confirmation_datetime: Optional[datetime] = Field(
        None, description="When patient confirmed"
    )

    # Audit trail
    created_at: datetime = Field(
        default_factory=datetime.now, description="Created timestamp"
    )
    modified_at: datetime = Field(
        default_factory=datetime.now, description="Last modified timestamp"
    )
    cancelled_at: Optional[datetime] = Field(None, description="Cancellation timestamp")
    cancelled_by: Optional[str] = Field(
        None, description="Who cancelled (patient_id or provider_id)"
    )
    cancellation_reason: Optional[str] = Field(None, description="Why was it cancelled")

    @field_validator("scheduled_datetime")
    @classmethod
    def validate_future_date(cls, v):
        """Ensure appointment is in the future."""
        if v <= datetime.now():
            raise ValueError("Appointment must be scheduled for the future")
        return v

    @model_validator(mode="after")
    def validate_cancellation(self):
        """Ensure cancellation fields are consistent."""
        if self.cancelled_at is not None and not self.cancelled_by:
            raise ValueError("cancelled_by must be set if cancelled_at is set")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "appointment_id": "appt_123",
                "patient_id": "PAT_001",
                "provider_id": "prov_123",
                "appointment_type": "consultation",
                "status": "pending",
                "scheduled_datetime": "2025-12-15T10:30:00",
                "estimated_duration_minutes": 30,
                "location": "Suite 200, Medical Plaza",
                "is_telehealth": False,
                "reason_for_visit": "Annual checkup",
                "relevant_medications": ["Lisinopril 10mg"],
                "known_allergies": ["Penicillin"],
                "data_classification": "CONFIDENTIAL_MEDICAL",
                "patient_confirmed": True,
                "confirmation_datetime": "2025-12-10T14:30:00",
                "created_at": "2025-12-10T10:00:00",
            }
        }
    )


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class AppointmentCreateRequest(BaseModel):
    """Request to create a new appointment."""

    patient_id: str
    provider_id: str
    appointment_type: AppointmentType
    scheduled_datetime: datetime
    reason_for_visit: str
    is_telehealth: bool = False
    relevant_medications: List[str] = []
    known_allergies: List[str] = []


class AppointmentUpdateRequest(BaseModel):
    """Request to update an appointment."""

    status: Optional[AppointmentStatus] = None
    scheduled_datetime: Optional[datetime] = None
    clinical_notes: Optional[str] = None
    patient_confirmed: Optional[bool] = None


class AppointmentCancelRequest(BaseModel):
    """Request to cancel an appointment."""

    cancelled_by: str  # patient_id or provider_id
    cancellation_reason: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Response containing appointment details."""

    appointment_id: str
    patient_id: str
    provider_id: str
    appointment_type: AppointmentType
    status: AppointmentStatus
    scheduled_datetime: datetime
    location: Optional[str]
    is_telehealth: bool
    reason_for_visit: str
    patient_confirmed: bool
    created_at: datetime


class AvailabilityQueryRequest(BaseModel):
    """Request to query available appointment slots."""

    provider_id: Optional[str] = None
    specialty: Optional[str] = None
    start_date: datetime
    end_date: datetime
    appointment_type: Optional[AppointmentType] = None
    is_telehealth: Optional[bool] = None


class AvailabilityQueryResponse(BaseModel):
    """Response with available time slots."""

    available_slots: List[TimeSlot]
    providers: List[Provider]
    total_slots: int
    query_datetime: datetime
