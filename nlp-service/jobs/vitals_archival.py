"""
Scheduled Daily Job: Archive Old Vitals from Redis to MySQL

This job moves vitals data older than 7 days from Redis (hot storage)
to MySQL (cold storage) to maintain optimal Redis memory usage.

Schedule: Daily at 2 AM UTC
Command: python -m jobs.vitals_archival

Performance:
- Processes all users and vital types
- Batch inserts to MySQL
- Removes from Redis after successful archival
- Handles errors gracefully (continues on individual failures)
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services.redis_vitals_store import RedisVitalsStore

# Try to import database module
try:
    from core.database.xampp_db import XAMPPDatabase
    XAMPP_DB_AVAILABLE = True
except ImportError:
    XAMPP_DB_AVAILABLE = False
    logging.warning("XAMPPDatabase not available, will use SQLAlchemy directly")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("vitals_archival.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def archive_all_users_vitals():
    """
    Daily job to archive old vitals from Redis to MySQL.

    Process:
    1. Get all active users from database
    2. For each user and vital type:
       - Call archive_to_cold_storage()
       - Batch insert to MySQL
       - Remove from Redis
    3. Log total archived count

    Returns:
        Total number of vitals archived
    """
    logger.info("=" * 80)
    logger.info("Starting vitals archival job")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 80)

    store = RedisVitalsStore()
    total_archived = 0
    total_errors = 0
    vital_types = ["heart_rate", "blood_pressure", "spo2", "temperature"]

    try:
        # Get all users (implementation depends on your database setup)
        users = await get_all_active_users()
        logger.info(f"Found {len(users)} active users to process")

        for user in users:
            user_id = user.get("id") or user.get("user_id") or user.get("device_id")
            
            if not user_id:
                logger.warning(f"Skipping user with no ID: {user}")
                continue

            user_archived = 0

            for vital_type in vital_types:
                try:
                    count = await store.archive_to_cold_storage(user_id, vital_type)
                    user_archived += count
                    total_archived += count

                    if count > 0:
                        logger.info(f"✓ Archived {count} {vital_type} vitals for user {user_id}")
                except Exception as e:
                    total_errors += 1
                    logger.error(
                        f"✗ Failed to archive {vital_type} for user {user_id}: {e}",
                        exc_info=True
                    )

            if user_archived > 0:
                logger.info(f"User {user_id} total: {user_archived} vitals archived")

    except Exception as e:
        logger.error(f"Fatal error in archival job: {e}", exc_info=True)
        total_errors += 1

    # Summary
    logger.info("=" * 80)
    logger.info("Archival job complete")
    logger.info(f"Total vitals archived: {total_archived}")
    logger.info(f"Total errors: {total_errors}")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 80)

    return total_archived


async def get_all_active_users():
    """
    Get all active users from the database.

    Returns:
        List of user dictionaries with at least an 'id' field
    """
    if XAMPP_DB_AVAILABLE:
        try:
            db = XAMPPDatabase()
            await db.connect()

            users = await db.execute_query(
                "SELECT id FROM users WHERE active = 1",
                operation="read",
                fetch_all=True
            )

            await db.close()
            return users
        except Exception as e:
            logger.error(f"Failed to query XAMPP database: {e}")

    # Fallback: Get unique device IDs from Redis
    logger.info("Falling back to Redis key scanning for user IDs")
    store = RedisVitalsStore()

    if not store.use_redis or not store.client:
        logger.warning("Redis not available, cannot determine users")
        return []

    try:
        # Scan for all vitals:* keys
        cursor = 0
        user_ids = set()

        while True:
            cursor, keys = store.client.scan(cursor, match="vitals:*", count=100)

            for key in keys:
                # Extract user_id from key pattern: vitals:{user_id}:{vital_type}
                parts = key.split(":")
                if len(parts) >= 2:
                    user_ids.add(parts[1])

            if cursor == 0:
                break

        logger.info(f"Found {len(user_ids)} unique users from Redis keys")
        return [{"id": uid} for uid in user_ids]
    except Exception as e:
        logger.error(f"Failed to scan Redis for users: {e}")
        return []


def main():
    """Entry point for the archival job."""
    try:
        # Run the archival job
        total = asyncio.run(archive_all_users_vitals())

        # Exit with status code
        if total >= 0:
            logger.info("✅ Archival job completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Archival job failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("⚠️ Archival job interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"💥 Archival job crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
