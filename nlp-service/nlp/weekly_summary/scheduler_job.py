"""
Weekly Summary Scheduler Job.

APScheduler job for automated weekly summary delivery.
"""

from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class DeliveryChannel(str, Enum):
    """Supported delivery channels."""

    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class DeliveryStatus(str, Enum):
    """Delivery status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DeliveryResult:
    """Result of a delivery attempt."""

    user_id: str
    channel: DeliveryChannel
    status: DeliveryStatus
    message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class UserDeliveryPreference:
    """User preferences for summary delivery."""

    user_id: str
    enabled: bool = True
    channels: List[DeliveryChannel] = field(
        default_factory=lambda: [DeliveryChannel.WHATSAPP]
    )
    preferred_day: int = 0  # 0=Monday, 6=Sunday
    preferred_time: time = field(default_factory=lambda: time(9, 0))  # 9 AM
    timezone: str = "UTC"

    # Contact info
    phone_number: Optional[str] = None
    email: Optional[str] = None

    # Last delivery info
    last_delivery_at: Optional[datetime] = None
    last_delivery_status: Optional[DeliveryStatus] = None


class WeeklySummaryJob:
    """
    Scheduled job for weekly health summary delivery.

    Features:
    - Configurable delivery schedule per user
    - Multi-channel delivery (WhatsApp, Email, SMS, Push)
    - Retry logic for failed deliveries
    - Delivery tracking and logging

    Example:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()
        job = WeeklySummaryJob(
            data_aggregator=aggregator,
            message_generator=generator,
            notification_services={
                DeliveryChannel.WHATSAPP: whatsapp_service,
                DeliveryChannel.EMAIL: email_service
            }
        )
        register_weekly_summary_job(scheduler, job)
        scheduler.start()
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        data_aggregator: Any,  # WeeklyDataAggregator
        message_generator: Any,  # WeeklySummaryMessageGenerator
        notification_services: Dict[DeliveryChannel, Any],
        user_preference_repository: Optional[Any] = None,
    ):
        """
        Initialize the weekly summary job.

        Args:
            data_aggregator: Service to aggregate weekly health data
            message_generator: Service to generate formatted messages
            notification_services: Dict of channel -> notification service
            user_preference_repository: Repository for user delivery preferences
        """
        self.aggregator = data_aggregator
        self.generator = message_generator
        self.notification_services = notification_services
        self.user_prefs_repo = user_preference_repository

        self._delivery_callbacks: List[Callable[[DeliveryResult], None]] = []

    def add_delivery_callback(self, callback: Callable[[DeliveryResult], None]) -> None:
        """Add a callback to be called after each delivery attempt."""
        self._delivery_callbacks.append(callback)

    async def execute(
        self, user_ids: Optional[List[str]] = None
    ) -> List[DeliveryResult]:
        """
        Execute the weekly summary job.

        Args:
            user_ids: Specific users to process, or None for all eligible users

        Returns:
            List of delivery results
        """
        logger.info("Starting weekly summary job execution")
        results: List[DeliveryResult] = []

        # Get users to process
        if user_ids:
            users = [await self._get_user_preference(uid) for uid in user_ids]
            users = [u for u in users if u is not None]
        else:
            users = await self._get_eligible_users()

        logger.info(f"Processing {len(users)} users for weekly summary")

        for user_pref in users:
            try:
                user_results = await self._process_user(user_pref)
                results.extend(user_results)
            except Exception as e:
                logger.error(f"Error processing user {user_pref.user_id}: {e}")
                results.append(
                    DeliveryResult(
                        user_id=user_pref.user_id,
                        channel=DeliveryChannel.WHATSAPP,
                        status=DeliveryStatus.FAILED,
                        error_message=str(e),
                    )
                )

        logger.info(
            f"Weekly summary job completed. Processed {len(results)} deliveries"
        )
        return results

    async def _process_user(
        self, user_pref: UserDeliveryPreference
    ) -> List[DeliveryResult]:
        """Process a single user's weekly summary delivery."""
        results: List[DeliveryResult] = []

        if not user_pref.enabled:
            logger.debug(f"Skipping user {user_pref.user_id}: delivery disabled")
            return results

        # Aggregate data
        weekly_data = self.aggregator.aggregate_weekly_data(user_pref.user_id)

        # Check if there's enough data
        if weekly_data.data_completeness < 0.1:
            logger.debug(f"Skipping user {user_pref.user_id}: insufficient data")
            results.append(
                DeliveryResult(
                    user_id=user_pref.user_id,
                    channel=(
                        user_pref.channels[0]
                        if user_pref.channels
                        else DeliveryChannel.WHATSAPP
                    ),
                    status=DeliveryStatus.SKIPPED,
                    error_message="Insufficient data for summary",
                )
            )
            return results

        # Deliver to each enabled channel
        for channel in user_pref.channels:
            result = await self._deliver_to_channel(user_pref, weekly_data, channel)
            results.append(result)

            # Notify callbacks
            for callback in self._delivery_callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Delivery callback error: {e}")

        # Update last delivery
        if any(r.status == DeliveryStatus.SENT for r in results):
            await self._update_last_delivery(user_pref.user_id, results)

        return results

    async def _deliver_to_channel(
        self,
        user_pref: UserDeliveryPreference,
        weekly_data: Any,
        channel: DeliveryChannel,
    ) -> DeliveryResult:
        """Deliver summary to a specific channel."""

        # Generate message for channel
        if channel == DeliveryChannel.WHATSAPP:
            summary = self.generator.generate_whatsapp_message(weekly_data)
            destination = user_pref.phone_number
        elif channel == DeliveryChannel.EMAIL:
            summary = self.generator.generate_email_message(weekly_data)
            destination = user_pref.email
        elif channel == DeliveryChannel.SMS:
            summary = self.generator.generate_sms_message(weekly_data)
            destination = user_pref.phone_number
        else:
            return DeliveryResult(
                user_id=user_pref.user_id,
                channel=channel,
                status=DeliveryStatus.FAILED,
                error_message=f"Unsupported channel: {channel}",
            )

        if not destination:
            return DeliveryResult(
                user_id=user_pref.user_id,
                channel=channel,
                status=DeliveryStatus.SKIPPED,
                error_message=f"No destination for channel {channel}",
            )

        # Get notification service
        service = self.notification_services.get(channel)
        if not service:
            return DeliveryResult(
                user_id=user_pref.user_id,
                channel=channel,
                status=DeliveryStatus.FAILED,
                error_message=f"No service configured for {channel}",
            )

        # Attempt delivery with retries
        return await self._send_with_retry(
            user_pref.user_id, channel, service, destination, summary.message
        )

    async def _send_with_retry(
        self,
        user_id: str,
        channel: DeliveryChannel,
        service: Any,
        destination: str,
        message: str,
    ) -> DeliveryResult:
        """Send message with retry logic."""
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                # Call the service's send method
                if hasattr(service, "send_async"):
                    message_id = await service.send_async(destination, message)
                else:
                    message_id = service.send(destination, message)

                return DeliveryResult(
                    user_id=user_id,
                    channel=channel,
                    status=DeliveryStatus.SENT,
                    message_id=message_id,
                    sent_at=datetime.utcnow(),
                    retry_count=attempt,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Delivery attempt {attempt + 1} failed for {user_id} "
                    f"via {channel}: {e}"
                )
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff

        return DeliveryResult(
            user_id=user_id,
            channel=channel,
            status=DeliveryStatus.FAILED,
            error_message=last_error,
            retry_count=self.MAX_RETRIES,
        )

    async def _get_eligible_users(self) -> List[UserDeliveryPreference]:
        """Get all users eligible for delivery at current time."""
        if self.user_prefs_repo is None:
            return []

        try:
            if hasattr(self.user_prefs_repo, "get_users_for_delivery_async"):
                return await self.user_prefs_repo.get_users_for_delivery_async()
            return self.user_prefs_repo.get_users_for_delivery()
        except Exception as e:
            logger.error(f"Error getting eligible users: {e}")
            return []

    async def _get_user_preference(
        self, user_id: str
    ) -> Optional[UserDeliveryPreference]:
        """Get a specific user's delivery preferences."""
        if self.user_prefs_repo is None:
            # Return default preferences
            return UserDeliveryPreference(user_id=user_id)

        try:
            if hasattr(self.user_prefs_repo, "get_by_user_id_async"):
                return await self.user_prefs_repo.get_by_user_id_async(user_id)
            return self.user_prefs_repo.get_by_user_id(user_id)
        except Exception as e:
            logger.error(f"Error getting user preferences for {user_id}: {e}")
            return None

    async def _update_last_delivery(
        self, user_id: str, results: List[DeliveryResult]
    ) -> None:
        """Update user's last delivery timestamp."""
        if self.user_prefs_repo is None:
            return

        try:
            successful = next(
                (r for r in results if r.status == DeliveryStatus.SENT), None
            )
            if successful and hasattr(self.user_prefs_repo, "update_last_delivery"):
                self.user_prefs_repo.update_last_delivery(
                    user_id, successful.sent_at, successful.status
                )
        except Exception as e:
            logger.error(f"Error updating last delivery for {user_id}: {e}")


def register_weekly_summary_job(
    scheduler: Any,  # APScheduler
    job: WeeklySummaryJob,
    cron_expression: Optional[str] = None,
    day_of_week: str = "mon",
    hour: int = 9,
    minute: int = 0,
) -> str:
    """
    Register the weekly summary job with APScheduler.

    Args:
        scheduler: APScheduler instance
        job: WeeklySummaryJob instance
        cron_expression: Optional cron expression (overrides other params)
        day_of_week: Day to run (mon, tue, wed, etc.)
        hour: Hour to run (0-23)
        minute: Minute to run (0-59)

    Returns:
        Job ID

    Example:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()
        job_id = register_weekly_summary_job(
            scheduler,
            weekly_job,
            day_of_week="mon",
            hour=9
        )
    """

    async def job_wrapper():
        """Wrapper to execute job."""
        try:
            results = await job.execute()
            successful = sum(1 for r in results if r.status == DeliveryStatus.SENT)
            failed = sum(1 for r in results if r.status == DeliveryStatus.FAILED)
            logger.info(f"Weekly summary: {successful} sent, {failed} failed")
        except Exception as e:
            logger.error(f"Weekly summary job error: {e}")

    # Register with scheduler
    job_id = scheduler.add_job(
        job_wrapper,
        "cron",
        day_of_week=day_of_week,
        hour=hour,
        minute=minute,
        id="weekly_health_summary",
        name="Weekly Health Summary Delivery",
        replace_existing=True,
    )

    logger.info(
        f"Registered weekly summary job: {day_of_week} at {hour:02d}:{minute:02d}"
    )

    return job_id.id if hasattr(job_id, "id") else "weekly_health_summary"


async def run_manual_summary(job: WeeklySummaryJob, user_id: str) -> DeliveryResult:
    """
    Manually trigger a summary for a specific user.

    Args:
        job: WeeklySummaryJob instance
        user_id: User to send summary to

    Returns:
        DeliveryResult
    """
    results = await job.execute(user_ids=[user_id])
    return (
        results[0]
        if results
        else DeliveryResult(
            user_id=user_id,
            channel=DeliveryChannel.WHATSAPP,
            status=DeliveryStatus.FAILED,
            error_message="No results returned",
        )
    )
