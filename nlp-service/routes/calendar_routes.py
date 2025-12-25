"""
Calendar Integration API Routes.

FastAPI routes for calendar synchronization and reminder management.
Integrates Google Calendar, Outlook Calendar, and notification services.
"""

from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, field_validator
import logging
import pytz
import uuid
from core.concurrency.redis_lock import RedisLock
<<<<<<< HEAD
from config import get_settings
=======
from core.app_dependencies import get_current_user
from core.database.xampp_db import get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["Calendar Integration"])


# ==================== Request/Response Models ====================


class CalendarCredentialsRequest(BaseModel):
    """Request to store calendar credentials."""

    provider: str = Field(..., description="Calendar provider: google or outlook")
    access_token: str = Field(..., description="OAuth access token")
    refresh_token: Optional[str] = Field(None, description="OAuth refresh token")
    expires_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "google",
                "access_token": "ya29.xxx",
                "refresh_token": "1//xxx",
                "expires_at": "2025-01-15T10:30:00Z",
            }
        }


class SyncRequest(BaseModel):
    """Request to sync appointments with calendar."""

    provider: str = Field("google", description="Calendar provider")
    days_ahead: int = Field(30, ge=1, le=90, description="Days to sync ahead")
    include_reminders: bool = Field(
        True, description="Create reminders for appointments"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "google",
                "days_ahead": 30,
                "include_reminders": True,
            }
        }


class CalendarEventResponse(BaseModel):
    """Calendar event information."""

    id: str
    title: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    calendar_id: str
    provider: str
    synced_at: datetime


class SyncResponse(BaseModel):
    """Response for calendar sync operation."""

    user_id: str
    provider: str
    events_synced: int
    reminders_created: int
    sync_started_at: datetime
    sync_completed_at: datetime
    next_sync_at: Optional[datetime] = None
    errors: List[str] = []


class ReminderRequest(BaseModel):
    """Request to schedule a reminder."""

    appointment_id: str
    reminder_type: str = Field("push", description="Reminder type: push, email, sms")
    minutes_before: int = Field(
        30, ge=5, le=1440, description="Minutes before appointment"
    )
    message: Optional[str] = Field(None, description="Custom reminder message")

    class Config:
        json_schema_extra = {
            "example": {
                "appointment_id": "apt_123",
                "reminder_type": "push",
                "minutes_before": 30,
                "message": "Don't forget your cardiology appointment!",
            }
        }


class ReminderResponse(BaseModel):
    """Reminder information."""

    id: str
    appointment_id: str
    reminder_type: str
    scheduled_for: datetime
    status: str
    message: str
    created_at: datetime


# ==================== Calendar Credentials Endpoints ====================


@router.post("/{user_id}/credentials", response_model=dict)
async def store_calendar_credentials(
    user_id: str, credentials: CalendarCredentialsRequest
):
    """
    Store OAuth credentials for calendar provider.

    Securely stores credentials for Google or Outlook calendar access.
    """
    try:
        from calendar_integration import (
            CalendarCredentials,
            CalendarProvider,
            get_google_calendar_service,
            get_outlook_calendar_service,
        )

        provider = CalendarProvider(credentials.provider)
        creds = CalendarCredentials(
            user_id=user_id,
            provider=provider,
            access_token=credentials.access_token,
            refresh_token=credentials.refresh_token,
            expires_at=credentials.expires_at,
        )

        # Store credentials based on provider
        if provider == CalendarProvider.GOOGLE:
            service = get_google_calendar_service()
            await service.store_credentials(user_id, creds)
        else:
            service = get_outlook_calendar_service()
            await service.store_credentials(user_id, creds)

        return {
            "status": "stored",
            "user_id": user_id,
            "provider": credentials.provider,
            "stored_at": datetime.utcnow().isoformat(),
        }

    except ImportError as e:
        logger.warning(f"Calendar integration not available: {e}")
        raise HTTPException(
            status_code=503, detail="Calendar integration service not available"
        )
    except Exception as e:
        logger.error(f"Error storing credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}/credentials/{provider}")
async def revoke_calendar_credentials(user_id: str, provider: str):
    """
    Revoke calendar credentials for a provider.
    """
    try:
        from calendar_integration import (
            CalendarProvider,
            get_google_calendar_service,
            get_outlook_calendar_service,
        )

        prov = CalendarProvider(provider)

        if prov == CalendarProvider.GOOGLE:
            service = get_google_calendar_service()
        else:
            service = get_outlook_calendar_service()

        await service.revoke_credentials(user_id)

        return {
            "status": "revoked",
            "user_id": user_id,
            "provider": provider,
            "revoked_at": datetime.utcnow().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="Calendar service not available")
    except Exception as e:
        logger.error(f"Error revoking credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Calendar Sync Endpoints ====================


@router.post("/{user_id}/sync", response_model=SyncResponse)
async def sync_calendar(user_id: str, request: SyncRequest):
    """
    Sync appointments with external calendar.

    Creates calendar events for scheduled appointments and optionally
    sets up reminders.
    """
    try:
        from calendar_integration import CalendarSyncAgent, CalendarProvider

        agent = CalendarSyncAgent()
        result = await agent.sync_appointments(
            user_id=user_id,
            provider=CalendarProvider(request.provider),
            days_ahead=request.days_ahead,
            create_reminders=request.include_reminders,
        )

        return SyncResponse(
            user_id=user_id,
            provider=request.provider,
            events_synced=result.events_synced,
            reminders_created=result.reminders_created,
            sync_started_at=result.sync_started_at,
            sync_completed_at=result.sync_completed_at,
            next_sync_at=result.next_sync_at,
            errors=result.errors,
        )

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Calendar sync service not available"
        )
    except Exception as e:
        logger.error(f"Error syncing calendar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/events", response_model=List[CalendarEventResponse])
async def get_calendar_events(
    user_id: str,
    provider: str = Query("google", description="Calendar provider"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    limit: int = Query(50, ge=1, le=200, description="Max events to return"),
):
    """
    Get calendar events for a user.
    """
    try:
        from calendar_integration import (
            CalendarProvider,
            get_google_calendar_service,
            get_outlook_calendar_service,
        )

        prov = CalendarProvider(provider)

        if prov == CalendarProvider.GOOGLE:
            service = get_google_calendar_service()
        else:
            service = get_outlook_calendar_service()

        events = await service.get_events(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return [
            CalendarEventResponse(
                id=e.id,
                title=e.title,
                start_time=e.start_time,
                end_time=e.end_time,
                location=e.location,
                description=e.description,
                calendar_id=e.calendar_id,
                provider=provider,
                synced_at=e.synced_at,
            )
            for e in events
        ]

    except ImportError:
        raise HTTPException(status_code=503, detail="Calendar service not available")
    except Exception as e:
        logger.error(f"Error getting events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Reminder Endpoints ====================


@router.post("/{user_id}/reminders", response_model=ReminderResponse)
async def schedule_reminder(user_id: str, request: ReminderRequest):
    """
    Schedule a reminder for an appointment.
    """
    try:
        from calendar_integration import ReminderScheduleAgent, NotificationType

        agent = ReminderScheduleAgent()
        reminder = await agent.schedule_reminder(
            user_id=user_id,
            appointment_id=request.appointment_id,
            notification_type=NotificationType(request.reminder_type),
            minutes_before=request.minutes_before,
            custom_message=request.message,
        )

        return ReminderResponse(
            id=reminder.id,
            appointment_id=reminder.appointment_id,
            reminder_type=request.reminder_type,
            scheduled_for=reminder.scheduled_for,
            status=reminder.status.value,
            message=reminder.message,
            created_at=reminder.created_at,
        )

    except ImportError:
        raise HTTPException(status_code=503, detail="Reminder service not available")
    except Exception as e:
        logger.error(f"Error scheduling reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/reminders", response_model=List[ReminderResponse])
async def get_reminders(
    user_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get scheduled reminders for a user.
    """
    try:
        from calendar_integration import get_reminder_scheduler

        scheduler = get_reminder_scheduler()
        reminders = await scheduler.get_user_reminders(
            user_id=user_id,
            status=status,
            limit=limit,
        )

        return [
            ReminderResponse(
                id=r.id,
                appointment_id=r.appointment_id,
                reminder_type=r.notification_type.value,
                scheduled_for=r.scheduled_for,
                status=r.status.value,
                message=r.message,
                created_at=r.created_at,
            )
            for r in reminders
        ]

    except ImportError:
        raise HTTPException(status_code=503, detail="Reminder service not available")
    except Exception as e:
        logger.error(f"Error getting reminders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}/reminders/{reminder_id}")
async def cancel_reminder(user_id: str, reminder_id: str):
    """
    Cancel a scheduled reminder.
    """
    try:
        from calendar_integration import get_reminder_scheduler

        scheduler = get_reminder_scheduler()
        await scheduler.cancel_reminder(user_id, reminder_id)

        return {
            "status": "cancelled",
            "reminder_id": reminder_id,
            "cancelled_at": datetime.utcnow().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="Reminder service not available")
    except Exception as e:
        logger.error(f"Error cancelling reminder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Internal Appointment Management (UTC & Locking) ====================

class AppointmentCreate(BaseModel):
    """Appointment creation request."""
    
    # Frontend sends ISO 8601 with timezone
    start_time: datetime  # e.g., "2024-12-24T14:00:00-05:00"
    end_time: datetime
    doctor_id: str
    notes: Optional[str] = None
    
    @field_validator('start_time', 'end_time')
    @classmethod
    def convert_to_utc(cls, v: datetime) -> datetime:
        """
        Convert all incoming times to UTC.
        """
        if v.tzinfo is None:
            raise ValueError(
                "Timestamp must include timezone information. "
                "Use ISO 8601 format: '2024-12-24T14:00:00-05:00'"
            )
        
        # Convert to UTC
        utc_time = v.astimezone(timezone.utc)
        
        # Remove timezone info for storage (we know it's UTC)
        return utc_time.replace(tzinfo=None)


class AppointmentResponse(BaseModel):
    """Appointment response."""
    
    id: str
    start_time: datetime  # Stored as UTC
    end_time: datetime
    doctor_id: str
    user_id: str
    notes: Optional[str] = None
    
    # User's timezone for conversion
    user_timezone: str = "America/New_York"
    
    @property
    def start_time_local(self) -> str:
        """Convert stored UTC time to user's local timezone."""
        utc_time = self.start_time.replace(tzinfo=timezone.utc)
        user_tz = pytz.timezone(self.user_timezone)
        local_time = utc_time.astimezone(user_tz)
        return local_time.isoformat()
    
    @property
    def end_time_local(self) -> str:
        """Convert end time to user's local timezone."""
        utc_time = self.end_time.replace(tzinfo=timezone.utc)
        user_tz = pytz.timezone(self.user_timezone)
        local_time = utc_time.astimezone(user_tz)
        return local_time.isoformat()


def _to_user_timezone(utc_time: datetime, timezone_name: str) -> str:
    """Convert UTC datetime to user's timezone."""
    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=timezone.utc)
    
    user_tz = pytz.timezone(timezone_name)
    local_time = utc_time.astimezone(user_tz)
    return local_time.isoformat()


@router.post("/appointments")
async def create_appointment(
    appointment: AppointmentCreate,
    user_id: dict = Depends(get_current_user)
):
    """
    Create appointment with concurrency protection.
    Uses Redis mutex to prevent double booking.
    """
    # Handle user_id from dependency (might be dict or str)
    uid = user_id.get("id", "anonymous") if isinstance(user_id, dict) else str(user_id)
    
    settings = get_settings()
    redis_lock = RedisLock(settings.REDIS_URL or "redis://localhost:6379")
    db = get_database()
    
    # Validation: Start time must be in the future
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if appointment.start_time <= now_utc:
        raise HTTPException(status_code=400, detail="Appointment must be in the future")
    
    if appointment.end_time <= appointment.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    
    # Generate lock key based on doctor and time slot
    lock_key = f"booking:{appointment.doctor_id}:{appointment.start_time.timestamp()}"
    
    try:
        # Acquire lock (blocks other requests for this slot)
        async with redis_lock.acquire(lock_key, timeout=10, blocking_timeout=5):
            # Double-check availability (inside lock)
            conflict = await db.execute_query(
                """
                SELECT id FROM appointments
                WHERE doctor_id = %s
                  AND (
                    (start_time < %s AND end_time > %s) OR
                    (start_time < %s AND end_time > %s)
                  )
                """,
                (
                    appointment.doctor_id,
                    appointment.end_time, appointment.start_time,
                    appointment.end_time, appointment.start_time
                ),
                operation="read",
                fetch_one=True
            )
            
            if conflict:
                raise HTTPException(status_code=409, detail="This time slot is no longer available")
            
            # Slot is available, create appointment
            apt_id = str(uuid.uuid4())
            await db.execute_query(
                """
                INSERT INTO appointments 
                (id, user_id, doctor_id, start_time, end_time, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())
                """,
                (
                    apt_id,
                    uid,
                    appointment.doctor_id,
                    appointment.start_time,
                    appointment.end_time,
                    appointment.notes
                ),
                operation="write"
            )
            
            return {"id": apt_id, "message": "Appointment created"}
            
    except TimeoutError:
        raise HTTPException(
            status_code=409,
            detail="Someone else is currently booking this slot. Please try again."
        )


@router.get("/appointments/{target_user_id}")
async def get_appointments(target_user_id: str):
    """Get appointments with times converted to user's local timezone."""
    db = get_database()
    
    # Get user's preferred timezone
    user = await db.execute_query(
        "SELECT timezone FROM users WHERE id = %s",
        (target_user_id,),
        operation="read",
        fetch_one=True
    )
    
    user_timezone = user.get("timezone", "America/New_York") if user else "America/New_York"
    
    # Fetch appointments (stored in UTC)
    appointments = await db.execute_query(
        """
        SELECT id, user_id, doctor_id, start_time, end_time, notes
        FROM appointments
        WHERE user_id = %s AND start_time >= UTC_TIMESTAMP()
        ORDER BY start_time ASC
        """,
        (target_user_id,),
        operation="read",
        fetch_all=True
    )
    
    formatted_appointments = []
    if appointments:
        for apt in appointments:
            formatted_appointments.append({
                "id": apt["id"],
                "doctor_id": apt["doctor_id"],
                "start_time": _to_user_timezone(apt["start_time"], user_timezone),
                "end_time": _to_user_timezone(apt["end_time"], user_timezone),
                "notes": apt["notes"]
            })
    
    return {"appointments": formatted_appointments}
