"""
Calendar synchronization and reminder scheduling agents.

Phase 4: Calendar Agents
"""

import logging
from typing import Dict

from agents.base import BaseAgent
from appointments.models import Appointment, AppointmentStatus
from appointments.service import get_appointment_service
from calendar_integration.models import (
    CalendarEvent,
    SyncAppointmentsRequest,
    ScheduleRemindersRequest,
    CalendarProvider,
    NotificationType,
    Reminder,
)
from calendar_integration.google_service import get_google_calendar_service
from calendar_integration.outlook_service import get_outlook_calendar_service
from calendar_integration.scheduler import get_reminder_scheduler
from calendar_integration.notifications import (
    get_email_service,
    get_sms_service,
    get_push_service,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CALENDAR SYNC AGENT
# ============================================================================


class CalendarSyncAgent(BaseAgent):
    """
    Synchronizes appointments to calendar providers.
    Handles Google Calendar and Outlook integration.
    """

    def __init__(self):
        """Initialize calendar sync agent."""
        super().__init__(
            name="CalendarSync",
            description="Synchronizes appointments to calendar providers",
        )
        self.appointment_service = get_appointment_service()
        self.google_service = get_google_calendar_service()
        self.outlook_service = get_outlook_calendar_service()

    def execute(self, request: SyncAppointmentsRequest) -> Dict:
        """
        Sync appointments to calendar provider.

        Args:
            request: Sync request with provider and appointments

        Returns:
            Result dict with sync status and details
        """
        try:
            self.log_action("sync_appointments", f"provider={request.provider.value}")

            # Fetch appointments to sync
            if request.appointment_ids:
                appointments = []
                for appt_id in request.appointment_ids:
                    appt = self.appointment_service.get_appointment(appt_id, "SYSTEM")
                    if appt and appt.status in [
                        AppointmentStatus.CONFIRMED,
                        AppointmentStatus.PENDING,
                    ]:
                        appointments.append(appt)
            else:
                # Get all confirmed appointments
                all_appts = self.appointment_service.get_patient_appointments(
                    request.user_email.split("@")[0],  # Simplified patient lookup
                    include_cancelled=False,
                )
                appointments = [
                    a for a in all_appts if a.status == AppointmentStatus.CONFIRMED
                ]

            # Convert to calendar events
            calendar_events = [
                self._appointment_to_event(appt, request.provider)
                for appt in appointments
            ]

            # Sync based on provider
            if request.provider == CalendarProvider.GOOGLE:
                sync_result = self.google_service.sync_appointments(
                    request.user_email,
                    calendar_events,
                    request.date_range_start,
                    request.date_range_end,
                )
            elif request.provider in [
                CalendarProvider.OUTLOOK,
                CalendarProvider.MICROSOFT,
            ]:
                sync_result = self.outlook_service.sync_appointments(
                    request.user_email,
                    calendar_events,
                    request.date_range_start,
                    request.date_range_end,
                )
            else:
                raise ValueError(f"Unsupported provider: {request.provider}")

            self.log_action(
                "sync_completed",
                f"synced={sync_result.successful_syncs}, failed={sync_result.failed_syncs}",
            )

            return {
                "sync_id": sync_result.sync_id,
                "status": sync_result.sync_status.value,
                "synced_count": sync_result.successful_syncs,
                "failed_count": sync_result.failed_syncs,
                "total_count": sync_result.total_appointments,
            }

        except Exception as e:
            self.log_action("sync_error", str(e))
            logger.error(f"Sync error: {e}")
            return {"status": "failed", "error": str(e)}

    def _appointment_to_event(
        self, appointment: Appointment, provider: CalendarProvider
    ) -> CalendarEvent:
        """Convert appointment to calendar event."""
        return CalendarEvent(
            event_id=f"evt_{appointment.appointment_id}",
            appointment_id=appointment.appointment_id,
            provider=provider,
            title=f"{appointment.appointment_type.value} - {appointment.reason_for_visit}",
            description=appointment.clinical_notes or appointment.reason_for_visit,
            location=appointment.location,
            start_time=appointment.scheduled_datetime,
            end_time=appointment.scheduled_datetime.replace(
                minute=appointment.scheduled_datetime.minute
                + appointment.estimated_duration_minutes
            ),
            duration_minutes=appointment.estimated_duration_minutes,
            meeting_url=appointment.meeting_url if appointment.is_telehealth else None,
            is_virtual=appointment.is_telehealth,
            organizer_email="healthcare-system@example.com",
            attendee_emails=[appointment.patient_id],
            reminder_minutes=[60, 15],
        )


# ============================================================================
# REMINDER SCHEDULING AGENT
# ============================================================================


class ReminderScheduleAgent(BaseAgent):
    """
    Schedules appointment reminders.
    Handles email, SMS, and push notifications.
    """

    def __init__(self):
        """Initialize reminder schedule agent."""
        super().__init__(
            name="ReminderSchedule", description="Schedules appointment reminders"
        )
        self.scheduler = get_reminder_scheduler()
        self.appointment_service = get_appointment_service()
        self.email_service = get_email_service()
        self.sms_service = get_sms_service()
        self.push_service = get_push_service()

        # Register callbacks for reminder execution
        self.scheduler.register_callback(self._execute_email_reminder)
        self.scheduler.register_callback(self._execute_sms_reminder)
        self.scheduler.register_callback(self._execute_push_reminder)

    def execute(self, request: ScheduleRemindersRequest) -> Dict:
        """
        Schedule reminders for appointment.

        Args:
            request: Schedule reminders request

        Returns:
            Result dict with scheduled reminder IDs
        """
        try:
            self.log_action(
                "schedule_reminders", f"appointment={request.appointment_id}"
            )

            # Get appointment details
            appointment = self.appointment_service.get_appointment(
                request.appointment_id, "SYSTEM"
            )
            if not appointment:
                raise ValueError(f"Appointment not found: {request.appointment_id}")

            # Schedule reminders
            scheduled_ids = self.scheduler.schedule_reminders(
                appointment_id=request.appointment_id,
                recipient_email=request.recipient_email,
                recipient_phone=request.recipient_phone,
                reminder_minutes=[60, 15],  # 1 hour and 15 minutes before
                appointment_datetime=appointment.scheduled_datetime,
            )

            self.log_action("reminders_scheduled", f"count={len(scheduled_ids)}")

            return {
                "appointment_id": request.appointment_id,
                "reminder_ids": scheduled_ids,
                "scheduled_count": len(scheduled_ids),
                "next_reminder": appointment.scheduled_datetime.isoformat(),
            }

        except Exception as e:
            self.log_action("reminder_scheduling_error", str(e))
            logger.error(f"Reminder scheduling error: {e}")
            return {"status": "failed", "error": str(e)}

    def cancel_reminders(self, appointment_id: str) -> Dict:
        """
        Cancel all reminders for an appointment.

        Args:
            appointment_id: Appointment ID

        Returns:
            Result dict
        """
        try:
            self.log_action("cancel_reminders", f"appointment={appointment_id}")

            cancelled_count = self.scheduler.cancel_appointment_reminders(
                appointment_id
            )

            self.log_action("reminders_cancelled", f"count={cancelled_count}")

            return {
                "appointment_id": appointment_id,
                "cancelled_count": cancelled_count,
            }

        except Exception as e:
            self.log_action("cancel_error", str(e))
            return {"status": "failed", "error": str(e)}

    def _execute_email_reminder(self, reminder: Reminder) -> None:
        """Execute email reminder."""
        if reminder.notification_type != NotificationType.EMAIL:
            return

        try:
            self.email_service.send_email(
                to_email=reminder.recipient_email,
                subject=reminder.message_subject or "Appointment Reminder",
                body=reminder.message_body,
            )
            logger.info(f"Email reminder sent: {reminder.reminder_id}")
        except Exception as e:
            logger.error(f"Email reminder failed: {e}")

    def _execute_sms_reminder(self, reminder: Reminder) -> None:
        """Execute SMS reminder."""
        if reminder.notification_type != NotificationType.SMS:
            return

        try:
            self.sms_service.send_sms(
                to_phone=reminder.recipient_phone, message=reminder.message_body
            )
            logger.info(f"SMS reminder sent: {reminder.reminder_id}")
        except Exception as e:
            logger.error(f"SMS reminder failed: {e}")

    def _execute_push_reminder(self, reminder: Reminder) -> None:
        """Execute push reminder."""
        if reminder.notification_type != NotificationType.PUSH:
            return

        try:
            self.push_service.send_push(
                device_id=reminder.recipient_device_id,
                title="Appointment Reminder",
                body=reminder.message_body,
            )
            logger.info(f"Push reminder sent: {reminder.reminder_id}")
        except Exception as e:
            logger.error(f"Push reminder failed: {e}")
