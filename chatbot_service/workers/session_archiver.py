"""
Session Archiver Worker

Moves completed sessions from Redis to PostgreSQL for:
- HIPAA audit trail
- Long-term storage
- Analytics
- Legal compliance

This runs as a background job, does not affect hot path performance.
The archiver monitors LangGraph checkpoints in Redis and archives completed
workflows to PostgreSQL for compliance and analytics.

Usage:
    python -m workers.session_archiver

    # Or run as a service
    python workers/session_archiver.py
"""

import os
import sys
import json
import asyncio
import logging
import signal
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis.asyncio as redis
import asyncpg

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

# Archive sessions older than this (minutes since last activity)
ARCHIVE_AFTER_MINUTES = int(os.getenv("ARCHIVE_AFTER_MINUTES", "60"))

# Run archiver every N seconds
ARCHIVE_INTERVAL = int(os.getenv("ARCHIVE_INTERVAL", "300"))  # 5 minutes

# Redis key patterns for LangGraph checkpoints
CHECKPOINT_PREFIX = "langgraph:checkpoint:"
CHECKPOINT_WRITES_PREFIX = "langgraph:checkpoint_writes:"


# ============================================================================
# Database Schema
# ============================================================================

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS session_archives (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    workflow_type VARCHAR(100) DEFAULT 'chat',
    
    -- Session metadata
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    
    -- State data (compressed JSON)
    initial_state JSONB,
    final_state JSONB,
    checkpoints JSONB,  -- Array of checkpoint summaries
    
    -- Statistics
    total_steps INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    
    -- Audit fields
    archived_at TIMESTAMPTZ DEFAULT NOW(),
    archived_by VARCHAR(100) DEFAULT 'session_archiver',
    
    -- Indexes for queries
    CONSTRAINT idx_user_completed UNIQUE (user_id, completed_at, thread_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_session_archives_user_id ON session_archives(user_id);
CREATE INDEX IF NOT EXISTS idx_session_archives_completed_at ON session_archives(completed_at);
CREATE INDEX IF NOT EXISTS idx_session_archives_archived_at ON session_archives(archived_at);
CREATE INDEX IF NOT EXISTS idx_session_archives_thread_id ON session_archives(thread_id);
"""


# ============================================================================
# Session Archiver
# ============================================================================

class SessionArchiver:
    """
    Archives completed LangGraph sessions from Redis to PostgreSQL.
    
    Pattern:
    1. Scan Redis for LangGraph checkpoint keys
    2. Identify completed sessions (has FINISH state or no activity for N minutes)
    3. Extract full checkpoint history
    4. Insert into PostgreSQL for HIPAA audit trail
    5. Optionally delete from Redis to free memory
    """
    
    def __init__(
        self,
        redis_url: str = REDIS_URL,
        postgres_url: str = POSTGRES_URL,
        archive_after_minutes: int = ARCHIVE_AFTER_MINUTES
    ):
        self.redis_url = redis_url
        self.postgres_url = postgres_url
        self.archive_after_minutes = archive_after_minutes
        
        self.redis: Optional[redis.Redis] = None
        self.pg_pool: Optional[asyncpg.Pool] = None
        self._running = False
    
    async def initialize(self) -> None:
        """Initialize database connections."""
        logger.info("🚀 Initializing Session Archiver...")
        
        # Connect to Redis
        self.redis = redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        await self.redis.ping()
        logger.info("✅ Connected to Redis")
        
        # Connect to PostgreSQL
        try:
            self.pg_pool = await asyncpg.create_pool(
                self.postgres_url,
                min_size=2,
                max_size=10
            )
            
            # Create table if not exists
            async with self.pg_pool.acquire() as conn:
                await conn.execute(CREATE_TABLE_SQL)
            
            logger.info("✅ Connected to PostgreSQL, table verified")
            
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown connections."""
        logger.info("🛑 Shutting down Session Archiver...")
        self._running = False
        
        if self.redis:
            await self.redis.aclose()
        
        if self.pg_pool:
            await self.pg_pool.close()
        
        logger.info("✅ Session Archiver shutdown complete")
    
    async def run(self) -> None:
        """Main archiver loop."""
        await self.initialize()
        self._running = True
        
        logger.info(
            f"📦 Session Archiver running (archive after {self.archive_after_minutes}m, "
            f"interval {ARCHIVE_INTERVAL}s)"
        )
        
        while self._running:
            try:
                archived = await self.archive_completed_sessions()
                if archived > 0:
                    logger.info(f"📁 Archived {archived} sessions")
                
                await asyncio.sleep(ARCHIVE_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Archiver error: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def archive_completed_sessions(self) -> int:
        """
        Find and archive completed sessions.
        
        Returns:
            Number of sessions archived
        """
        archived_count = 0
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.archive_after_minutes)
        
        # Scan for checkpoint keys
        thread_ids = set()
        async for key in self.redis.scan_iter(f"{CHECKPOINT_PREFIX}*"):
            # Extract thread_id from key pattern: langgraph:checkpoint:{thread_id}:*
            parts = key.split(":")
            if len(parts) >= 3:
                thread_id = parts[2]
                thread_ids.add(thread_id)
        
        for thread_id in thread_ids:
            try:
                # Check if session should be archived
                should_archive = await self._should_archive(thread_id, cutoff_time)
                
                if should_archive:
                    await self._archive_session(thread_id)
                    archived_count += 1
                    
            except Exception as e:
                logger.error(f"Error archiving session {thread_id}: {e}")
        
        return archived_count
    
    async def _should_archive(
        self, 
        thread_id: str, 
        cutoff_time: datetime
    ) -> bool:
        """
        Determine if a session should be archived.
        
        A session should be archived if:
        1. It has reached FINISH state, OR
        2. No checkpoint activity for archive_after_minutes
        """
        # Check if already archived
        async with self.pg_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM session_archives WHERE thread_id = $1)",
                thread_id
            )
            if exists:
                return False
        
        # Get latest checkpoint for this thread
        latest_key = await self._get_latest_checkpoint_key(thread_id)
        if not latest_key:
            return False
        
        # Get checkpoint data
        checkpoint_data = await self.redis.get(latest_key)
        if not checkpoint_data:
            return False
        
        try:
            checkpoint = json.loads(checkpoint_data)
            
            # Check for FINISH state
            values = checkpoint.get("values", {})
            next_node = values.get("next", "")
            
            if next_node == "FINISH" or next_node == "" or values.get("final_response"):
                return True
            
            # Check last activity time (if metadata available)
            metadata = checkpoint.get("metadata", {})
            created_at = metadata.get("created_at")
            
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if created_dt.replace(tzinfo=None) < cutoff_time:
                        return True
                except ValueError:
                    pass
            
        except json.JSONDecodeError:
            pass
        
        return False
    
    async def _get_latest_checkpoint_key(self, thread_id: str) -> Optional[str]:
        """Get the latest checkpoint key for a thread."""
        pattern = f"{CHECKPOINT_PREFIX}{thread_id}:*"
        keys = []
        async for key in self.redis.scan_iter(pattern):
            keys.append(key)
        
        if not keys:
            return None
        
        # Sort by checkpoint number (last part of key)
        return sorted(keys)[-1] if keys else None
    
    async def _archive_session(self, thread_id: str) -> None:
        """Archive a session to PostgreSQL."""
        logger.info(f"📁 Archiving session: {thread_id}")
        
        # Collect all checkpoints
        checkpoints = []
        pattern = f"{CHECKPOINT_PREFIX}{thread_id}:*"
        
        async for key in self.redis.scan_iter(pattern):
            data = await self.redis.get(key)
            if data:
                try:
                    checkpoint = json.loads(data)
                    checkpoints.append({
                        "key": key,
                        "data": checkpoint
                    })
                except json.JSONDecodeError:
                    pass
        
        if not checkpoints:
            return
        
        # Sort checkpoints
        checkpoints.sort(key=lambda c: c["key"])
        
        # Extract session info
        initial_state = checkpoints[0]["data"].get("values", {}) if checkpoints else {}
        final_state = checkpoints[-1]["data"].get("values", {}) if checkpoints else {}
        
        user_id = initial_state.get("user_id", "unknown")
        
        # Calculate timing
        started_at = None
        completed_at = None
        
        if checkpoints:
            first_meta = checkpoints[0]["data"].get("metadata", {})
            last_meta = checkpoints[-1]["data"].get("metadata", {})
            
            started_at_str = first_meta.get("created_at")
            completed_at_str = last_meta.get("created_at")
            
            if started_at_str:
                try:
                    started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
                except ValueError:
                    started_at = datetime.utcnow()
            
            if completed_at_str:
                try:
                    completed_at = datetime.fromisoformat(completed_at_str.replace("Z", "+00:00"))
                except ValueError:
                    completed_at = datetime.utcnow()
        
        duration_ms = None
        if started_at and completed_at:
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        
        # Count messages
        messages = initial_state.get("messages", [])
        total_messages = len(messages) if isinstance(messages, list) else 0
        
        # Create checkpoint summaries (don't store full data to save space)
        checkpoint_summaries = []
        for cp in checkpoints:
            summary = {
                "step": len(checkpoint_summaries),
                "next": cp["data"].get("values", {}).get("next"),
                "has_response": bool(cp["data"].get("values", {}).get("final_response")),
            }
            checkpoint_summaries.append(summary)
        
        # Insert into PostgreSQL
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO session_archives (
                    thread_id, user_id, workflow_type,
                    started_at, completed_at, duration_ms,
                    initial_state, final_state, checkpoints,
                    total_steps, total_messages
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (thread_id) DO UPDATE SET
                    final_state = EXCLUDED.final_state,
                    completed_at = EXCLUDED.completed_at,
                    duration_ms = EXCLUDED.duration_ms,
                    checkpoints = EXCLUDED.checkpoints,
                    total_steps = EXCLUDED.total_steps,
                    archived_at = NOW()
                """,
                thread_id,
                user_id,
                "chat",
                started_at,
                completed_at,
                duration_ms,
                json.dumps(initial_state),
                json.dumps(final_state),
                json.dumps(checkpoint_summaries),
                len(checkpoints),
                total_messages
            )
        
        # Optionally clean up Redis (keep for some time for debugging)
        # For now, just mark as archived
        await self.redis.set(
            f"chatbot:archived:{thread_id}",
            json.dumps({"archived_at": datetime.utcnow().isoformat()}),
            ex=86400  # 24 hour TTL
        )
        
        logger.info(f"✅ Session {thread_id} archived (user={user_id}, steps={len(checkpoints)})")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point for session archiver."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    archiver = SessionArchiver()
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    
    def handle_signal(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(archiver.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass
    
    try:
        await archiver.run()
    except KeyboardInterrupt:
        await archiver.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
