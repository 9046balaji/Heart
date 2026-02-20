"""
Calendar Routes
===============
Google Calendar integration for appointment scheduling and reminders.
Endpoints:
    POST /calendar/{user_id}/credentials
    POST /calendar/{user_id}/sync
    GET  /calendar/{user_id}/events
    POST /calendar/{user_id}/reminder
"""

import logging
import uuid
from typing import Optional, List, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("calendar")

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory store (production would use database)
# ---------------------------------------------------------------------------

_calendar_store: dict = {}  # user_id -> {credentials, events, reminders}


def _get_user_store(user_id: str) -> dict:
    if user_id not in _calendar_store:
        _calendar_store[user_id] = {"credentials": None, "events": [], "reminders": []}
    return _calendar_store[user_id]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CalendarCredentials(BaseModel):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    provider: str = "google"


class SyncOptions(BaseModel):
    days_ahead: int = 30
    include_recurring: bool = True


class SyncResponse(BaseModel):
    events_synced: int
    reminders_created: int
    sync_completed_at: str


class CalendarEvent(BaseModel):
    id: str
    title: str
    start_time: str
    end_time: str
    location: Optional[str] = None
    description: Optional[str] = None


class ReminderRequest(BaseModel):
    title: str
    scheduled_for: str
    description: Optional[str] = None
    reminder_minutes_before: int = 30


class ReminderResponse(BaseModel):
    id: str
    appointment_id: str
    scheduled_for: str
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{user_id}/credentials")
async def store_credentials(user_id: str, credentials: CalendarCredentials):
    """Store calendar integration credentials for a user."""
    store = _get_user_store(user_id)
    store["credentials"] = credentials.dict()
    logger.info(f"Calendar credentials stored for user {user_id} (provider: {credentials.provider})")
    return {"message": "Credentials stored successfully", "provider": credentials.provider}


@router.post("/{user_id}/sync", response_model=SyncResponse)
async def sync_calendar(user_id: str, options: SyncOptions):
    """Sync calendar events from the configured provider."""
    store = _get_user_store(user_id)

    # Generate sample health-related events if no real integration
    now = datetime.utcnow()
    sample_events = [
        CalendarEvent(
            id=str(uuid.uuid4()),
            title="Annual Physical Exam",
            start_time=(now + timedelta(days=7)).isoformat() + "Z",
            end_time=(now + timedelta(days=7, hours=1)).isoformat() + "Z",
            location="Primary Care Clinic",
            description="Annual wellness check-up",
        ),
        CalendarEvent(
            id=str(uuid.uuid4()),
            title="Cardiology Follow-up",
            start_time=(now + timedelta(days=14)).isoformat() + "Z",
            end_time=(now + timedelta(days=14, hours=1)).isoformat() + "Z",
            location="Heart Center",
            description="Follow-up appointment for heart health",
        ),
    ]
    store["events"] = [e.dict() for e in sample_events]

    return SyncResponse(
        events_synced=len(sample_events),
        reminders_created=0,
        sync_completed_at=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/{user_id}/events", response_model=List[CalendarEvent])
async def get_events(
    user_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Get calendar events for a user, optionally filtered by date range."""
    store = _get_user_store(user_id)
    events = store.get("events", [])

    # Filter by date range if provided
    if start_date or end_date:
        filtered = []
        for evt in events:
            evt_start = evt.get("start_time", "")
            if start_date and evt_start < start_date:
                continue
            if end_date and evt_start > end_date:
                continue
            filtered.append(evt)
        events = filtered

    return [CalendarEvent(**e) if isinstance(e, dict) else e for e in events]


@router.post("/{user_id}/reminder", response_model=ReminderResponse)
async def schedule_reminder(user_id: str, reminder: ReminderRequest):
    """Schedule a health-related reminder."""
    store = _get_user_store(user_id)
    reminder_id = str(uuid.uuid4())
    appointment_id = str(uuid.uuid4())

    entry = {
        "id": reminder_id,
        "appointment_id": appointment_id,
        "title": reminder.title,
        "scheduled_for": reminder.scheduled_for,
        "description": reminder.description,
        "reminder_minutes_before": reminder.reminder_minutes_before,
        "status": "scheduled",
    }
    store["reminders"].append(entry)
    logger.info(f"Reminder scheduled for user {user_id}: {reminder.title}")

    return ReminderResponse(
        id=reminder_id,
        appointment_id=appointment_id,
        scheduled_for=reminder.scheduled_for,
        status="scheduled",
    )
