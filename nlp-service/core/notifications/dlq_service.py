"""
Dead Letter Queue Service for notification failures.

Persists failed notifications and schedules retries with exponential backoff.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
import json

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Notification delivery types."""
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"


class NotificationStatus(str, Enum):
    """Notification delivery status."""
    PENDING = "pending"
    RETRYING = "retrying"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class DeadLetterQueueService:
    """
    Service for managing failed notification retries.
    
    Features:
    - Exponential backoff retry strategy
    - Maximum retry limits
    - Error tracking
    - Cleanup of old failures
    
    Retry Schedule (exponential backoff):
    - Retry 1: 5 minutes
    - Retry 2: 15 minutes
    - Retry 3: 1 hour
    - Retry 4: 4 hours
    - Retry 5: 12 hours
    """
    
    # Retry delays (minutes)
    RETRY_DELAYS = [5, 15, 60, 240, 720]  # 5m, 15m, 1h, 4h, 12h
    
    def __init__(self, db_pool):
        """
        Initialize DLQ service.
        
        Args:
            db_pool: Database connection pool (from XAMPPDatabase)
        """
        self.db = db_pool
    
    async def record_failure(
        self,
        notification_type: NotificationType,
        recipient: str,
        subject: Optional[str],
        content: str,
        error: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_retries: int = 5
    ) -> int:
        """
        Record a failed notification attempt.
        
        Args:
            notification_type: Type of notification
            recipient: Email or phone number
            subject: Email subject (if applicable)
            content: Notification content
            error: Error message from failed attempt
            user_id: Optional user identifier
            metadata: Additional metadata
            max_retries: Maximum retry attempts
            
        Returns:
            Failure record ID
        """
        # Calculate next retry time (5 minutes for first retry)
        next_retry = datetime.now() + timedelta(minutes=self.RETRY_DELAYS[0])
        
        async with self.db.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO notification_failures
                    (notification_type, recipient, subject, content, 
                     last_error, retry_count, max_retries, next_retry_at,
                     user_id, metadata_json, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    notification_type.value,
                    recipient,
                    subject,
                    content,
                    error,
                    0,  # retry_count starts at 0
                    max_retries,
                    next_retry,
                    user_id,
                    json.dumps(metadata) if metadata else None,
                    NotificationStatus.PENDING.value
                ))
                
                failure_id = cursor.lastrowid
                
                logger.warning(
                    f"Notification failure recorded: id={failure_id}, "
                    f"type={notification_type}, recipient={recipient}, "
                    f"next_retry={next_retry}"
                )
                
                return failure_id
    
    async def get_pending_retries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get notifications that are ready for retry.
        
        Args:
            limit: Maximum number of failures to retrieve
            
        Returns:
            List of failure records ready for retry
        """
        async with self.db.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, notification_type, recipient, subject, content,
                           retry_count, max_retries, last_error, user_id, metadata_json
                    FROM notification_failures
                    WHERE status IN ('pending', 'retrying')
                      AND next_retry_at <= NOW()
                      AND retry_count < max_retries
                    ORDER BY next_retry_at ASC
                    LIMIT %s
                """, (limit,))
                
                rows = await cursor.fetchall()
                
                return [
                    {
                        'id': row[0],
                        'notification_type': row[1],
                        'recipient': row[2],
                        'subject': row[3],
                        'content': row[4],
                        'retry_count': row[5],
                        'max_retries': row[6],
                        'last_error': row[7],
                        'user_id': row[8],
                        'metadata': json.loads(row[9]) if row[9] else None
                    }
                    for row in rows
                ]
    
    async def record_retry_attempt(
        self,
        failure_id: int,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Record the result of a retry attempt.
        
        Args:
            failure_id: ID of the failure record
            success: Whether retry succeeded
            error: Error message if retry failed
        """
        async with self.db.acquire() as conn:
            async with conn.cursor() as cursor:
                if success:
                    # Mark as succeeded
                    await cursor.execute("""
                        UPDATE notification_failures
                        SET status = 'succeeded',
                            retry_count = retry_count + 1,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (failure_id,))
                    
                    logger.info(f"Notification retry succeeded: id={failure_id}")
                    
                else:
                    # Increment retry count and calculate next retry
                    await cursor.execute("""
                        SELECT retry_count, max_retries
                        FROM notification_failures
                        WHERE id = %s
                    """, (failure_id,))
                    
                    row = await cursor.fetchone()
                    if row:
                        retry_count = row[0] + 1
                        max_retries = row[1]
                        
                        # Calculate next retry time with exponential backoff
                        if retry_count < max_retries:
                            delay_minutes = self.RETRY_DELAYS[
                                min(retry_count, len(self.RETRY_DELAYS) - 1)
                            ]
                            next_retry = datetime.now() + timedelta(minutes=delay_minutes)
                            status = NotificationStatus.RETRYING.value
                        else:
                            # Max retries reached
                            next_retry = None
                            status = NotificationStatus.FAILED.value
                        
                        await cursor.execute("""
                            UPDATE notification_failures
                            SET retry_count = %s,
                            last_error = %s,
                            next_retry_at = %s,
                            status = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (retry_count, error, next_retry, status, failure_id))
                    
                    if status == NotificationStatus.FAILED.value:
                        logger.error(
                            f"Notification permanently failed after {retry_count} retries: "
                            f"id={failure_id}"
                        )
                    else:
                        logger.warning(
                            f"Notification retry failed (attempt {retry_count}): "
                            f"id={failure_id}, next_retry={next_retry}"
                        )
    
    async def cleanup_old_failures(self, days_old: int = 30) -> int:
        """
        Clean up old succeeded/failed notifications.
        
        Args:
            days_old: Delete records older than this many days
            
        Returns:
            Number of records deleted
        """
        async with self.db.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM notification_failures
                    WHERE status IN ('succeeded', 'failed')
                      AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
                """, (days_old,))
                
                deleted = cursor.rowcount
                
                logger.info(f"Cleaned up {deleted} old notification failure records")
                
                return deleted


# Singleton instance
_dlq_service: Optional[DeadLetterQueueService] = None

async def get_dlq_service() -> DeadLetterQueueService:
    """Get singleton DLQ service."""
    global _dlq_service
    if _dlq_service is None:
        from core.database.xampp_db import get_database
        db = await get_database()
        _dlq_service = DeadLetterQueueService(db.pool)
    return _dlq_service