"""
Reminder scheduling system with APScheduler.

Phase 4: Reminder Scheduler
Updated: Real APScheduler with SQLite job persistence
"""

import logging
import os
from typing import Optional, List, Callable, Dict
from datetime import datetime, timedelta
from uuid import uuid4
import threading

# APScheduler imports (with graceful fallback)
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    AsyncIOScheduler = None
    SQLAlchemyJobStore = None
    MemoryJobStore = None

from calendar_integration.models import Reminder, ReminderStatus, NotificationType

logger = logging.getLogger(__name__)

# Configuration
SCHEDULER_DB_PATH = os.getenv("SCHEDULER_DB_PATH", "scheduler_jobs.db")
SCHEDULER_MOCK_MODE = os.getenv("SCHEDULER_MOCK_MODE", "false").lower() == "true"


# ============================================================================
# REMINDER SCHEDULER
# ============================================================================


class ReminderScheduler:
    """
    Schedule and manage appointment reminders.

    Features:
    - APScheduler with SQLite persistence (production)
    - In-memory fallback (development/testing)
    - Thread-safe operations
    - Automatic job recovery on restart

    Environment Variables:
        SCHEDULER_DB_PATH: SQLite database path for job persistence
        SCHEDULER_MOCK_MODE: Set to 'true' to use in-memory scheduler
        SCHEDULER_MAX_WORKERS: Thread pool size (default: 10)
    """

    def __init__(self, mock_mode: bool = None):
        """
        Initialize reminder scheduler.

        Args:
            mock_mode: Force in-memory scheduler (for testing)
        """
        self.scheduled_reminders: Dict[str, Reminder] = {}
        self.reminder_callbacks: List[Callable] = []
        self.lock = threading.RLock()

        # Determine mock mode
        if mock_mode is None:
            mock_mode = SCHEDULER_MOCK_MODE or not APSCHEDULER_AVAILABLE
        self.mock_mode = mock_mode

        self.scheduler = None
        self._started = False

        if not self.mock_mode and APSCHEDULER_AVAILABLE:
            self._init_apscheduler()
        else:
            if not APSCHEDULER_AVAILABLE:
                logger.warning(
                    "APScheduler not available. Install with: pip install apscheduler"
                )
            logger.info("Reminder scheduler initialized in MOCK mode (in-memory only)")

    def _init_apscheduler(self) -> None:
        """Initialize APScheduler with SQLite persistence."""
        try:
            # Configure job stores
            job_stores = {
                "default": SQLAlchemyJobStore(url=f"sqlite:///{SCHEDULER_DB_PATH}"),
                "memory": MemoryJobStore(),
            }

            # Configure executors
            max_workers = int(os.getenv("SCHEDULER_MAX_WORKERS", "10"))
            executors = {
                "default": ThreadPoolExecutor(max_workers=max_workers),
            }

            # Job defaults
            job_defaults = {
                "coalesce": True,  # Combine missed runs
                "max_instances": 3,  # Max concurrent instances of same job
                "misfire_grace_time": 300,  # 5 minute grace period
            }

            # Create scheduler
            self.scheduler = BackgroundScheduler(
                jobstores=job_stores,
                executors=executors,
                job_defaults=job_defaults,
                timezone="UTC",
            )

            # Add event listeners
            self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
            self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
            self.scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)

            logger.info(f"APScheduler initialized with SQLite: {SCHEDULER_DB_PATH}")

        except Exception as e:
            logger.error(f"Failed to initialize APScheduler: {e}")
            self.mock_mode = True
            self.scheduler = None

    def _on_job_executed(self, event) -> None:
        """Handle successful job execution."""
        job_id = event.job_id
        logger.debug(f"Job executed: {job_id}")
        with self.lock:
            if job_id in self.scheduled_reminders:
                self.scheduled_reminders[job_id].status = ReminderStatus.SENT
                self.scheduled_reminders[job_id].sent_at = datetime.now()

    def _on_job_error(self, event) -> None:
        """Handle job execution error."""
        job_id = event.job_id
        logger.error(f"Job failed: {job_id}, exception: {event.exception}")
        with self.lock:
            if job_id in self.scheduled_reminders:
                self.scheduled_reminders[job_id].status = ReminderStatus.FAILED
                self.scheduled_reminders[job_id].last_error = str(event.exception)
                self.scheduled_reminders[job_id].retry_count += 1

    def _on_job_missed(self, event) -> None:
        """Handle missed job."""
        job_id = event.job_id
        logger.warning(f"Job missed: {job_id}")
        with self.lock:
            if job_id in self.scheduled_reminders:
                self.scheduled_reminders[job_id].status = ReminderStatus.FAILED
                self.scheduled_reminders[job_id].last_error = (
                    "Job missed - scheduler was stopped"
                )

    def start(self) -> bool:
        """
        Start the scheduler.

        Returns:
            True if started successfully
        """
        if self._started:
            return True

        if self.mock_mode or not self.scheduler:
            self._started = True
            logger.info("Scheduler started (mock mode)")
            return True

        try:
            self.scheduler.start()
            self._started = True
            logger.info("APScheduler started")
            return True
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            return False

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the scheduler.

        Args:
            wait: Wait for running jobs to complete
        """
        if not self._started:
            return

        if self.scheduler:
            try:
                self.scheduler.shutdown(wait=wait)
                logger.info("APScheduler shutdown complete")
            except Exception as e:
                logger.error(f"Error during scheduler shutdown: {e}")

        self._started = False

    def register_callback(self, callback: Callable) -> None:
        """
        Register callback for when reminder should be sent.

        Args:
            callback: Function to call when reminder is due
        """
        self.reminder_callbacks.append(callback)
        logger.info(f"Registered callback: {callback.__name__}")

    def schedule_reminder(self, reminder: Reminder) -> bool:
        """
        Schedule a reminder.

        Args:
            reminder: Reminder to schedule

        Returns:
            True if successful
        """
        try:
            with self.lock:
                # Calculate delay
                now = datetime.now()
                delay_seconds = (reminder.scheduled_time - now).total_seconds()

                if delay_seconds < 0:
                    logger.warning(
                        f"Scheduled time is in the past: {reminder.scheduled_time}"
                    )
                    reminder.status = ReminderStatus.FAILED
                    reminder.last_error = "Scheduled time is in the past"
                    return False

                # Store reminder
                self.scheduled_reminders[reminder.reminder_id] = reminder

                # Schedule with APScheduler if available
                if not self.mock_mode and self.scheduler and self._started:
                    self.scheduler.add_job(
                        func=self._execute_reminder,
                        trigger="date",
                        run_date=reminder.scheduled_time,
                        args=[reminder.reminder_id],
                        id=reminder.reminder_id,
                        name=f"reminder_{reminder.appointment_id}_{reminder.minutes_before}min",
                        replace_existing=True,
                    )

                logger.info(
                    f"Scheduled reminder {reminder.reminder_id}: "
                    f"Will send at {reminder.scheduled_time} "
                    f"(in {delay_seconds:.0f} seconds)"
                )

                return True

        except Exception as e:
            logger.error(f"Failed to schedule reminder: {e}")
            reminder.status = ReminderStatus.FAILED
            reminder.last_error = str(e)
            return False

    def schedule_reminders(
        self,
        appointment_id: str,
        recipient_email: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        reminder_minutes: Optional[List[int]] = None,
        appointment_datetime: Optional[datetime] = None,
    ) -> List[str]:
        """
        Schedule multiple reminders for an appointment.

        Args:
            appointment_id: Appointment ID
            recipient_email: Email recipient
            recipient_phone: SMS recipient
            reminder_minutes: Minutes before to remind (default: [60, 15])
            appointment_datetime: Appointment datetime

        Returns:
            List of scheduled reminder IDs
        """
        if reminder_minutes is None:
            reminder_minutes = [60, 15]

        if appointment_datetime is None:
            appointment_datetime = datetime.now() + timedelta(days=1)

        scheduled_ids = []

        try:
            with self.lock:
                # Schedule email reminders
                if recipient_email:
                    for minutes in reminder_minutes:
                        scheduled_time = appointment_datetime - timedelta(
                            minutes=minutes
                        )

                        reminder = Reminder(
                            reminder_id=f"rem_{uuid4().hex[:12]}",
                            appointment_id=appointment_id,
                            notification_type=NotificationType.EMAIL,
                            minutes_before=minutes,
                            recipient_email=recipient_email,
                            scheduled_time=scheduled_time,
                            message_body=f"Reminder: Your appointment is in {minutes} minutes",
                            status=ReminderStatus.SCHEDULED,
                        )

                        if self.schedule_reminder(reminder):
                            scheduled_ids.append(reminder.reminder_id)

                # Schedule SMS reminders (fewer messages to avoid spam)
                if recipient_phone:
                    # Only 1 hour before
                    minutes = 60
                    scheduled_time = appointment_datetime - timedelta(minutes=minutes)

                    reminder = Reminder(
                        reminder_id=f"rem_{uuid4().hex[:12]}",
                        appointment_id=appointment_id,
                        notification_type=NotificationType.SMS,
                        minutes_before=minutes,
                        recipient_phone=recipient_phone,
                        scheduled_time=scheduled_time,
                        message_body=f"SMS Reminder: Your appointment is in {minutes} minutes",
                        status=ReminderStatus.SCHEDULED,
                    )

                    if self.schedule_reminder(reminder):
                        scheduled_ids.append(reminder.reminder_id)

                logger.info(
                    f"Scheduled {len(scheduled_ids)} reminders for appointment {appointment_id}"
                )
                return scheduled_ids

        except Exception as e:
            logger.error(f"Failed to schedule reminders: {e}")
            return scheduled_ids

    def cancel_reminder(self, reminder_id: str) -> bool:
        """
        Cancel a scheduled reminder.

        Args:
            reminder_id: ID of reminder to cancel

        Returns:
            True if successful
        """
        try:
            with self.lock:
                if reminder_id in self.scheduled_reminders:
                    reminder = self.scheduled_reminders[reminder_id]
                    reminder.status = ReminderStatus.CANCELLED

                    # Cancel APScheduler job if available
                    if not self.mock_mode and self.scheduler and self._started:
                        try:
                            self.scheduler.remove_job(reminder_id)
                        except Exception as e:
                            logger.debug(
                                f"Job {reminder_id} already removed or not found: {e}"
                            )

                    logger.info(f"Cancelled reminder {reminder_id}")
                    return True

                logger.warning(f"Reminder not found: {reminder_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to cancel reminder: {e}")
            return False

    def cancel_appointment_reminders(self, appointment_id: str) -> int:
        """
        Cancel all reminders for an appointment.

        Args:
            appointment_id: Appointment ID

        Returns:
            Number of reminders cancelled
        """
        cancelled_count = 0

        try:
            with self.lock:
                reminder_ids_to_cancel = [
                    rid
                    for rid, reminder in self.scheduled_reminders.items()
                    if reminder.appointment_id == appointment_id
                    and reminder.status == ReminderStatus.SCHEDULED
                ]

                for rid in reminder_ids_to_cancel:
                    if self.cancel_reminder(rid):
                        cancelled_count += 1

                logger.info(
                    f"Cancelled {cancelled_count} reminders for appointment {appointment_id}"
                )
                return cancelled_count

        except Exception as e:
            logger.error(f"Failed to cancel appointment reminders: {e}")
            return 0

    def _execute_reminder(self, reminder_id: str) -> None:
        """
        Execute reminder notification.
        Called by scheduler when reminder time is reached.

        Args:
            reminder_id: ID of reminder to execute
        """
        try:
            with self.lock:
                if reminder_id not in self.scheduled_reminders:
                    logger.warning(f"Reminder not found: {reminder_id}")
                    return

                reminder = self.scheduled_reminders[reminder_id]
                reminder.status = ReminderStatus.SENT
                reminder.sent_at = datetime.now()

                # Execute callbacks
                for callback in self.reminder_callbacks:
                    try:
                        callback(reminder)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                        reminder.status = ReminderStatus.FAILED
                        reminder.last_error = str(e)
                        reminder.retry_count += 1

                logger.info(f"Executed reminder {reminder_id}")

        except Exception as e:
            logger.error(f"Failed to execute reminder: {e}")

    def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """Get reminder by ID."""
        with self.lock:
            return self.scheduled_reminders.get(reminder_id)

    def get_appointment_reminders(self, appointment_id: str) -> List[Reminder]:
        """Get all reminders for an appointment."""
        with self.lock:
            return [
                reminder
                for reminder in self.scheduled_reminders.values()
                if reminder.appointment_id == appointment_id
            ]

    def get_pending_reminders(self) -> List[Reminder]:
        """Get all pending reminders."""
        with self.lock:
            return [
                reminder
                for reminder in self.scheduled_reminders.values()
                if reminder.status == ReminderStatus.SCHEDULED
            ]

    def clear_completed_reminders(self) -> int:
        """Clear sent and failed reminders from memory."""
        cleared_count = 0

        try:
            with self.lock:
                ids_to_remove = [
                    rid
                    for rid, reminder in self.scheduled_reminders.items()
                    if reminder.status
                    in [
                        ReminderStatus.SENT,
                        ReminderStatus.FAILED,
                        ReminderStatus.CANCELLED,
                    ]
                ]

                for rid in ids_to_remove:
                    del self.scheduled_reminders[rid]
                    cleared_count += 1

                logger.info(f"Cleared {cleared_count} completed reminders")
                return cleared_count

        except Exception as e:
            logger.error(f"Failed to clear reminders: {e}")
            return 0


# ============================================================================
# SINGLETON PATTERN
# ============================================================================


_scheduler: Optional[ReminderScheduler] = None


def get_reminder_scheduler(auto_start: bool = True) -> ReminderScheduler:
    """
    Get or create reminder scheduler singleton.

    Args:
        auto_start: Automatically start the scheduler

    Returns:
        ReminderScheduler instance
    """
    global _scheduler

    if _scheduler is None:
        _scheduler = ReminderScheduler()
        if auto_start:
            _scheduler.start()

    return _scheduler


def reset_reminder_scheduler() -> None:
    """Reset scheduler singleton (for testing)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
    _scheduler = None
