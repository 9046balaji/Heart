"""
Calendar integration models for Google Calendar and Outlook.

Phase 4: Calendar Models
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================


class CalendarProvider(str, Enum):
    """Supported calendar providers."""

    GOOGLE = "google"
    OUTLOOK = "outlook"
    MICROSOFT = "microsoft"


class SyncStatus(str, Enum):
    """Calendar sync status."""

    PENDING = "pending"
    SYNCING = "syncing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class NotificationType(str, Enum):
    """Notification types."""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class ReminderStatus(str, Enum):
    """Reminder execution status."""

    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# CALENDAR CREDENTIALS
# ============================================================================


class CalendarCredentials(BaseModel):
    """Calendar provider credentials."""

    provider: CalendarProvider = Field(..., description="Calendar provider")
    access_token: str = Field(..., description="OAuth2 access token")
    refresh_token: Optional[str] = Field(
        None, description="Refresh token for token renewal"
    )
    token_expiry: Optional[datetime] = Field(None, description="Token expiration time")
    user_email: str = Field(..., description="Calendar user email")
    is_active: bool = Field(True, description="Credentials are active")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "google",
                "access_token": "ya29.a0AfH6SMB...",
                "refresh_token": "1//0gF9mzL...",
                "token_expiry": "2025-12-15T10:30:00",
                "user_email": "user@gmail.com",
                "is_active": True,
            }
        },
        from_attributes=True,
    )

    @field_validator("token_expiry")
    @classmethod
    def validate_expiry(cls, v):
        """Ensure expiry is in the future."""
        if v is not None and v <= datetime.now():
            raise ValueError("Token expiry must be in the future")
        return v


# ============================================================================
# CALENDAR EVENT
# ============================================================================


class CalendarEvent(BaseModel):
    """Calendar event model."""

    # Identifiers
    event_id: str = Field(..., description="Calendar event ID (provider-specific)")
    appointment_id: str = Field(..., description="Reference to appointment ID")
    provider: CalendarProvider = Field(..., description="Calendar provider")

    # Event details
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Physical or virtual location")
    start_time: datetime = Field(..., description="Event start time")
    end_time: datetime = Field(..., description="Event end time")
    duration_minutes: int = Field(
        ..., ge=15, le=480, description="Event duration in minutes"
    )

    # Meeting details
    meeting_url: Optional[str] = Field(
        None, description="Virtual meeting URL (Zoom, Teams, etc)"
    )
    meeting_id: Optional[str] = Field(None, description="Virtual meeting ID")
    is_virtual: bool = Field(False, description="Is virtual meeting")

    # Participants
    organizer_email: str = Field(..., description="Event organizer email")
    attendee_emails: List[str] = Field(
        default_factory=list, description="Attendee emails"
    )

    # Reminders
    reminder_minutes: List[int] = Field(
        default_factory=lambda: [15, 60],
        description="Minutes before event to remind (15, 60, etc)",
    )

    # Sync tracking
    synced_at: datetime = Field(
        default_factory=datetime.now, description="Last sync time"
    )
    is_synced: bool = Field(True, description="Is synced with provider")

    # Audit
    created_at: datetime = Field(
        default_factory=datetime.now, description="Created timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Updated timestamp"
    )

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v, info):
        """Ensure end_time > start_time."""
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v

    @model_validator(mode="after")
    def validate_duration(self):
        """Ensure duration matches start and end times."""
        calculated_duration = int(
            (self.end_time - self.start_time).total_seconds() / 60
        )
        if self.duration_minutes != calculated_duration:
            self.duration_minutes = calculated_duration
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": "evt_123abc",
                "appointment_id": "appt_456def",
                "provider": "google",
                "title": "Cardiology Consultation",
                "description": "Annual checkup with Dr. Smith",
                "location": "Google Meet: meet.google.com/abc-def-ghi",
                "start_time": "2025-12-15T10:30:00",
                "end_time": "2025-12-15T11:00:00",
                "duration_minutes": 30,
                "meeting_url": "https://meet.google.com/abc-def-ghi",
                "is_virtual": True,
                "organizer_email": "dr.smith@hospital.com",
                "attendee_emails": ["patient@example.com"],
                "reminder_minutes": [15, 60],
            }
        },
        from_attributes=True,
    )


# ============================================================================
# CALENDAR SYNC
# ============================================================================


class CalendarSync(BaseModel):
    """Calendar synchronization record."""

    sync_id: str = Field(..., description="Unique sync ID")
    provider: CalendarProvider = Field(..., description="Calendar provider")
    user_email: str = Field(..., description="User email")

    # Sync details
    sync_status: SyncStatus = Field(
        SyncStatus.PENDING, description="Current sync status"
    )
    started_at: datetime = Field(
        default_factory=datetime.now, description="Sync start time"
    )
    completed_at: Optional[datetime] = Field(None, description="Sync completion time")

    # Results
    total_appointments: int = Field(0, description="Total appointments processed")
    successful_syncs: int = Field(0, description="Successfully synced")
    failed_syncs: int = Field(0, description="Failed syncs")
    skipped_syncs: int = Field(0, description="Skipped syncs")

    # Error tracking
    error_message: Optional[str] = Field(None, description="Error details if failed")
    sync_errors: List[Dict[str, str]] = Field(
        default_factory=list, description="List of individual sync errors"
    )

    # Sync range
    sync_from_date: datetime = Field(..., description="Sync from date")
    sync_to_date: datetime = Field(..., description="Sync to date")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sync_id": "sync_789xyz",
                "provider": "google",
                "user_email": "user@gmail.com",
                "sync_status": "success",
                "started_at": "2025-11-30T10:00:00",
                "completed_at": "2025-11-30T10:05:00",
                "total_appointments": 5,
                "successful_syncs": 5,
                "failed_syncs": 0,
                "sync_from_date": "2025-11-30T00:00:00",
                "sync_to_date": "2025-12-31T23:59:59",
            }
        },
        from_attributes=True,
    )


# ============================================================================
# REMINDER
# ============================================================================


class Reminder(BaseModel):
    """Appointment reminder with notification tracking."""

    reminder_id: str = Field(..., description="Unique reminder ID")
    appointment_id: str = Field(..., description="Reference to appointment")
    event_id: Optional[str] = Field(None, description="Reference to calendar event")

    # Reminder details
    notification_type: NotificationType = Field(..., description="Notification method")
    minutes_before: int = Field(
        ..., ge=5, le=10080, description="Minutes before appointment"
    )

    # Recipient
    recipient_email: Optional[str] = Field(None, description="Email recipient")
    recipient_phone: Optional[str] = Field(None, description="SMS recipient phone")
    recipient_device_id: Optional[str] = Field(
        None, description="Push notification device ID"
    )

    # Status
    status: ReminderStatus = Field(
        ReminderStatus.SCHEDULED, description="Reminder status"
    )
    scheduled_time: datetime = Field(..., description="Scheduled send time")
    sent_at: Optional[datetime] = Field(None, description="Actual send time")

    # Message
    message_subject: Optional[str] = Field(None, description="Email subject")
    message_body: str = Field(..., description="Notification message")

    # Error tracking
    retry_count: int = Field(0, ge=0, le=5, description="Number of retries")
    last_error: Optional[str] = Field(None, description="Last error message")

    # Audit
    created_at: datetime = Field(
        default_factory=datetime.now, description="Created timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Updated timestamp"
    )

    @model_validator(mode="after")
    def validate_recipient(self):
        """Ensure appropriate recipient for notification type."""
        if (
            self.notification_type == NotificationType.EMAIL
            and not self.recipient_email
        ):
            raise ValueError("Email recipient required for email notifications")
        if self.notification_type == NotificationType.SMS and not self.recipient_phone:
            raise ValueError("Phone recipient required for SMS notifications")
        if (
            self.notification_type == NotificationType.PUSH
            and not self.recipient_device_id
        ):
            raise ValueError("Device ID required for push notifications")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reminder_id": "rem_123",
                "appointment_id": "appt_456",
                "notification_type": "email",
                "minutes_before": 60,
                "recipient_email": "patient@example.com",
                "status": "scheduled",
                "scheduled_time": "2025-12-15T09:30:00",
                "message_subject": "Reminder: Your appointment tomorrow",
                "message_body": "Your appointment with Dr. Smith is scheduled for tomorrow at 10:30 AM.",
            }
        },
        from_attributes=True,
    )


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class SyncAppointmentsRequest(BaseModel):
    """Request to sync appointments to calendar."""

    provider: CalendarProvider = Field(..., description="Target calendar provider")
    user_email: str = Field(..., description="Calendar user email")
    appointment_ids: Optional[List[str]] = Field(
        None, description="Specific appointments to sync"
    )
    sync_all: bool = Field(False, description="Sync all pending appointments")
    date_range_start: Optional[datetime] = Field(None, description="Sync from date")
    date_range_end: Optional[datetime] = Field(None, description="Sync to date")


class ScheduleRemindersRequest(BaseModel):
    """Request to schedule reminders for appointment."""

    appointment_id: str = Field(..., description="Appointment to remind about")
    recipient_email: Optional[str] = Field(None, description="Email recipient")
    recipient_phone: Optional[str] = Field(None, description="SMS recipient")
    notification_types: List[NotificationType] = Field(
        default_factory=lambda: [NotificationType.EMAIL],
        description="Notification types",
    )
    reminder_minutes: List[int] = Field(
        default_factory=lambda: [60, 15], description="Minutes before to remind"
    )


class CalendarSyncResponse(BaseModel):
    """Response from calendar sync operation."""

    sync_id: str = Field(..., description="Sync ID")
    status: SyncStatus = Field(..., description="Sync status")
    synced_count: int = Field(..., description="Successfully synced count")
    failed_count: int = Field(..., description="Failed count")
    sync_details: Optional[Dict] = Field(None, description="Detailed sync information")


class ReminderScheduleResponse(BaseModel):
    """Response from reminder scheduling."""

    reminder_ids: List[str] = Field(..., description="Scheduled reminder IDs")
    scheduled_count: int = Field(..., description="Successfully scheduled count")
    failed_count: int = Field(..., description="Failed count")
    next_reminder_time: Optional[datetime] = Field(
        None, description="Next reminder time"
    )
