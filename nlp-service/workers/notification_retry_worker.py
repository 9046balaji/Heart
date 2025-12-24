"""
Background worker for processing notification retry queue.

Runs every 5 minutes to check for pending retries.
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def process_notification_retries():
    """
    Process pending notification retries.
    
    This function should be called periodically (e.g., every 5 minutes)
    by a scheduler like APScheduler or as a celery task.
    """
    from core.notifications.dlq_service import get_dlq_service, NotificationType
    from core.notifications.push_service import PushNotificationService, PushDeliveryStatus
    
    dlq = await get_dlq_service()
    push_service = PushNotificationService()
    
    # Get pending retries
    pending = await dlq.get_pending_retries(limit=100)
    
    logger.info(f"Processing {len(pending)} pending notification retries")
    
    for notification in pending:
        try:
            if notification['notification_type'] == NotificationType.PUSH.value:
                # Retry push notification
                # Assuming recipient is the device token
                result = await push_service.send_to_device_async(
                    device_token=notification['recipient'],
                    title=notification['subject'],
                    body=notification['content']
                )
                
                if result.status == PushDeliveryStatus.SENT:
                    await dlq.record_retry_attempt(notification['id'], success=True)
                else:
                    await dlq.record_retry_attempt(
                        notification['id'],
                        success=False,
                        error=result.error_message or "Unknown error"
                    )
            
            elif notification['notification_type'] == NotificationType.EMAIL.value:
                # Retry email notification
                from core.notifications.email_service import EmailService
                email_service = EmailService()
                
                result = email_service.send(
                    to=notification['recipient'],
                    subject=notification['subject'],
                    body_html=notification['content']
                )
                
                if result.status == 'sent':
                    await dlq.record_retry_attempt(notification['id'], success=True)
                else:
                    await dlq.record_retry_attempt(
                        notification['id'],
                        success=False,
                        error=result.error_message
                    )
            
            elif notification['notification_type'] == NotificationType.SMS.value:
                # Retry SMS/WhatsApp notification
                from core.notifications.whatsapp_service import WhatsAppService
                whatsapp_service = WhatsAppService()
                
                try:
                    result = await whatsapp_service.send_async(
                        to_number=notification['recipient'],
                        message=notification['content']
                    )
                    
                    if result:
                        await dlq.record_retry_attempt(notification['id'], success=True)
                    else:
                        await dlq.record_retry_attempt(
                            notification['id'],
                            success=False,
                            error="Failed to send WhatsApp message"
                        )
                except Exception as e:
                    await dlq.record_retry_attempt(
                        notification['id'],
                        success=False,
                        error=str(e)
                    )
            
        except Exception as e:
            logger.exception(f"Retry processing error for notification {notification['id']}")
            await dlq.record_retry_attempt(
                notification['id'],
                success=False,
                error=str(e)
            )


async def notification_retry_daemon():
    """
    Daemon process that runs retry worker every 5 minutes.
    
    Usage:
        asyncio.run(notification_retry_daemon())
    """
    logger.info("Starting notification retry daemon")
    
    while True:
        try:
            await process_notification_retries()
        except Exception as e:
            logger.exception("Notification retry daemon error")
        
        # Wait 5 minutes
        await asyncio.sleep(300)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(notification_retry_daemon())