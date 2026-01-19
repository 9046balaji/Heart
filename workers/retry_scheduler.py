"""
Retry Scheduler Worker

Monitors scheduled retries and delayed jobs, moving them to
active queues when their time comes.

This worker handles:
- Failed jobs scheduled for retry (exponential backoff)
- Delayed job processing (scheduled for future)
- Dead letter queue monitoring

Usage:
    python -m workers.retry_scheduler

    # Or run as a service
    python workers/retry_scheduler.py
"""

import os
import sys
import json
import asyncio
import logging
import signal
from datetime import datetime
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHECK_INTERVAL = float(os.getenv("RETRY_CHECK_INTERVAL", "1.0"))

# Queue keys
RETRY_QUEUE = "chatbot:jobs:retry"
SCHEDULED_QUEUE = "chatbot:jobs:scheduled"
DEAD_LETTER_QUEUE = "chatbot:jobs:dead"
ACTIVE_QUEUE = "arq:queue"  # ARQ's default queue

# Job store prefix
JOB_PREFIX = "chatbot:job:"


# ============================================================================
# Retry Scheduler
# ============================================================================

class RetryScheduler:
    """
    Moves due retries and scheduled jobs to active queues.
    
    This worker:
    1. Monitors retry sorted sets (score = retry timestamp)
    2. When jobs are due, moves them to active queue
    3. Updates job status
    4. Handles dead letter queue promotion
    """
    
    def __init__(self, redis_url: str = REDIS_URL):
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None
        self._running = False
    
    async def initialize(self) -> None:
        """Initialize Redis connection."""
        logger.info("🚀 Initializing Retry Scheduler...")
        
        self.redis = redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        await self.redis.ping()
        
        logger.info("✅ Retry Scheduler initialized")
    
    async def shutdown(self) -> None:
        """Shutdown scheduler."""
        logger.info("🛑 Shutting down Retry Scheduler...")
        self._running = False
        
        if self.redis:
            await self.redis.aclose()
        
        logger.info("✅ Retry Scheduler shutdown complete")
    
    async def run(self) -> None:
        """Main scheduler loop."""
        await self.initialize()
        self._running = True
        
        logger.info(f"⏰ Retry Scheduler running (check interval: {CHECK_INTERVAL}s)")
        
        while self._running:
            try:
                # Process due retries
                retry_count = await self._process_due_retries()
                
                # Process scheduled jobs
                scheduled_count = await self._process_scheduled_jobs()
                
                if retry_count > 0 or scheduled_count > 0:
                    logger.info(
                        f"📤 Processed {retry_count} retries, {scheduled_count} scheduled jobs"
                    )
                
                await asyncio.sleep(CHECK_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}")
                await asyncio.sleep(5)  # Wait before retry
    
    async def _process_due_retries(self) -> int:
        """
        Process jobs scheduled for retry.
        
        Returns:
            Number of jobs processed
        """
        now = datetime.utcnow().timestamp()
        count = 0
        
        # Get due retries (score <= now)
        due_jobs = await self.redis.zrangebyscore(
            RETRY_QUEUE,
            "-inf",
            now,
            start=0,
            num=100  # Process up to 100 at a time
        )
        
        for job_id in due_jobs:
            try:
                # Remove from retry queue
                removed = await self.redis.zrem(RETRY_QUEUE, job_id)
                
                if removed:
                    # Get job data
                    job_data = await self._get_job(job_id)
                    
                    if job_data:
                        # Check max retries
                        retry_count = job_data.get("retry_count", 0)
                        max_retries = job_data.get("max_retries", 3)
                        
                        if retry_count >= max_retries:
                            # Move to dead letter queue
                            await self._move_to_dead_letter(job_id, job_data)
                            logger.warning(f"💀 Job {job_id} moved to dead letter queue")
                        else:
                            # Re-queue for processing
                            await self._requeue_job(job_id, job_data)
                            count += 1
                            logger.info(f"🔄 Job {job_id} requeued (retry {retry_count + 1})")
                            
            except Exception as e:
                logger.error(f"Error processing retry for job {job_id}: {e}")
        
        return count
    
    async def _process_scheduled_jobs(self) -> int:
        """
        Process scheduled jobs (not yet started).
        
        Returns:
            Number of jobs processed
        """
        now = datetime.utcnow().timestamp()
        count = 0
        
        # Get due scheduled jobs
        due_jobs = await self.redis.zrangebyscore(
            SCHEDULED_QUEUE,
            "-inf",
            now,
            start=0,
            num=100
        )
        
        for job_id in due_jobs:
            try:
                removed = await self.redis.zrem(SCHEDULED_QUEUE, job_id)
                
                if removed:
                    job_data = await self._get_job(job_id)
                    
                    if job_data:
                        await self._queue_job(job_id, job_data)
                        count += 1
                        logger.info(f"⏰ Scheduled job {job_id} queued")
                        
            except Exception as e:
                logger.error(f"Error processing scheduled job {job_id}: {e}")
        
        return count
    
    async def _get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job data from Redis."""
        job_key = f"{JOB_PREFIX}{job_id}"
        data = await self.redis.get(job_key)
        
        if data:
            return json.loads(data)
        return None
    
    async def _update_job(self, job_id: str, job_data: Dict[str, Any]) -> None:
        """Update job data in Redis."""
        job_key = f"{JOB_PREFIX}{job_id}"
        await self.redis.set(
            job_key,
            json.dumps(job_data),
            ex=86400  # 24 hour TTL
        )
    
    async def _requeue_job(self, job_id: str, job_data: Dict[str, Any]) -> None:
        """Requeue a job for retry."""
        # Increment retry count
        job_data["retry_count"] = job_data.get("retry_count", 0) + 1
        job_data["status"] = "retrying"
        job_data["retried_at"] = datetime.utcnow().isoformat()
        
        await self._update_job(job_id, job_data)
        
        # Create ARQ job
        # Note: ARQ uses its own job format, so we need to enqueue properly
        await self._queue_for_arq(job_id, job_data)
    
    async def _queue_job(self, job_id: str, job_data: Dict[str, Any]) -> None:
        """Queue a scheduled job."""
        job_data["status"] = "pending"
        job_data["queued_at"] = datetime.utcnow().isoformat()
        
        await self._update_job(job_id, job_data)
        await self._queue_for_arq(job_id, job_data)
    
    async def _queue_for_arq(self, job_id: str, job_data: Dict[str, Any]) -> None:
        """
        Add job to ARQ queue.
        
        ARQ job format is specific, so we create the appropriate structure.
        """
        # ARQ uses a specific message format
        # We'll push a simple job reference that the worker can pick up
        arq_job = {
            "job_id": job_id,
            "function": "process_chat_message",
            "args": [
                job_id,
                job_data.get("user_id"),
                job_data.get("query"),
            ],
            "kwargs": {
                "session_id": job_data.get("session_id"),
                "priority": job_data.get("priority", "normal"),
                "metadata": job_data.get("metadata", {})
            },
            "queued_at": datetime.utcnow().isoformat()
        }
        
        # Push to ARQ queue (simple list push for now)
        await self.redis.lpush(
            ACTIVE_QUEUE,
            json.dumps(arq_job)
        )
    
    async def _move_to_dead_letter(
        self, 
        job_id: str, 
        job_data: Dict[str, Any]
    ) -> None:
        """Move a job to the dead letter queue."""
        job_data["status"] = "dead"
        job_data["dead_at"] = datetime.utcnow().isoformat()
        job_data["dead_reason"] = "max_retries_exceeded"
        
        await self._update_job(job_id, job_data)
        
        # Add to dead letter queue (sorted set by death time)
        await self.redis.zadd(
            DEAD_LETTER_QUEUE,
            {job_id: datetime.utcnow().timestamp()}
        )
    
    # ========================================================================
    # Dead Letter Queue Management
    # ========================================================================
    
    async def get_dead_letter_jobs(
        self, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get jobs from dead letter queue."""
        job_ids = await self.redis.zrange(
            DEAD_LETTER_QUEUE,
            0,
            limit - 1,
            desc=True
        )
        
        jobs = []
        for job_id in job_ids:
            job_data = await self._get_job(job_id)
            if job_data:
                jobs.append(job_data)
        
        return jobs
    
    async def requeue_dead_letter_job(self, job_id: str) -> bool:
        """
        Requeue a job from dead letter queue.
        
        Resets retry count and moves back to active queue.
        """
        job_data = await self._get_job(job_id)
        if not job_data:
            return False
        
        # Reset retry count
        job_data["retry_count"] = 0
        job_data["status"] = "pending"
        job_data["requeued_at"] = datetime.utcnow().isoformat()
        job_data["dead_reason"] = None
        
        await self._update_job(job_id, job_data)
        
        # Remove from dead letter queue
        await self.redis.zrem(DEAD_LETTER_QUEUE, job_id)
        
        # Queue for processing
        await self._queue_for_arq(job_id, job_data)
        
        logger.info(f"🔄 Dead letter job {job_id} requeued")
        return True
    
    async def purge_dead_letter_queue(self, older_than_hours: int = 168) -> int:
        """
        Purge old jobs from dead letter queue.
        
        Args:
            older_than_hours: Remove jobs older than this (default 7 days)
        
        Returns:
            Number of jobs purged
        """
        cutoff = datetime.utcnow().timestamp() - (older_than_hours * 3600)
        
        # Get old job IDs
        old_jobs = await self.redis.zrangebyscore(
            DEAD_LETTER_QUEUE,
            "-inf",
            cutoff
        )
        
        for job_id in old_jobs:
            # Delete job data
            job_key = f"{JOB_PREFIX}{job_id}"
            await self.redis.delete(job_key)
            
            # Remove from dead letter queue
            await self.redis.zrem(DEAD_LETTER_QUEUE, job_id)
        
        if old_jobs:
            logger.info(f"🗑️ Purged {len(old_jobs)} old dead letter jobs")
        
        return len(old_jobs)


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point for retry scheduler."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    scheduler = RetryScheduler()
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    
    def handle_signal(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(scheduler.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass
    
    try:
        await scheduler.run()
    except KeyboardInterrupt:
        await scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
