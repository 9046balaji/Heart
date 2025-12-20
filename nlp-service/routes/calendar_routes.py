"""
Calendar Integration API Routes.

FastAPI routes for calendar synchronization and reminder management.
Integrates Google Calendar, Outlook Calendar, and notification services.
"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import logging

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
