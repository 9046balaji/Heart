"""
Calendar module exports for Phase 4.

Includes calendar models, services, and agents for synchronization and reminders.
"""

# Models
from calendar_integration.models import (
    CalendarProvider,
    SyncStatus,
    NotificationType,
    ReminderStatus,
    CalendarCredentials,
    CalendarEvent,
    CalendarSync,
    Reminder,
    SyncAppointmentsRequest,
    ScheduleRemindersRequest,
    CalendarSyncResponse,
    ReminderScheduleResponse,
)

# Google Calendar Service
from calendar_integration.google_service import (
    GoogleCalendarService,
    get_google_calendar_service,
    reset_google_calendar_service,
)

# Outlook Calendar Service
from calendar_integration.outlook_service import (
    OutlookCalendarService,
    get_outlook_calendar_service,
    reset_outlook_calendar_service,
)

# Notification Services
from calendar_integration.notifications import (
    EmailNotificationService,
    SMSNotificationService,
    PushNotificationService,
    get_email_service,
    get_sms_service,
    get_push_service,
    reset_notification_services,
)

# Reminder Scheduler
from calendar_integration.scheduler import (
    ReminderScheduler,
    get_reminder_scheduler,
    reset_reminder_scheduler,
)

# Agents
from calendar_integration.agents import (
    CalendarSyncAgent,
    ReminderScheduleAgent,
)

__all__ = [
    # Models
    "CalendarProvider",
    "SyncStatus",
    "NotificationType",
    "ReminderStatus",
    "CalendarCredentials",
    "CalendarEvent",
    "CalendarSync",
    "Reminder",
    "SyncAppointmentsRequest",
    "ScheduleRemindersRequest",
    "CalendarSyncResponse",
    "ReminderScheduleResponse",
    # Google Calendar
    "GoogleCalendarService",
    "get_google_calendar_service",
    "reset_google_calendar_service",
    # Outlook Calendar
    "OutlookCalendarService",
    "get_outlook_calendar_service",
    "reset_outlook_calendar_service",
    # Notifications
    "EmailNotificationService",
    "SMSNotificationService",
    "PushNotificationService",
    "get_email_service",
    "get_sms_service",
    "get_push_service",
    "reset_notification_services",
    # Scheduler
    "ReminderScheduler",
    "get_reminder_scheduler",
    "reset_reminder_scheduler",
    # Agents
    "CalendarSyncAgent",
    "ReminderScheduleAgent",
]
