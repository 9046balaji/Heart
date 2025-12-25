"""
Database Schema Migration for Advanced Data & Reliability

Creates necessary tables for:
1. Vitals Archive (cold storage for vitals older than 7 days)
2. Checkpoints (agent state persistence for crash recovery)

Usage:
    python create_advanced_reliability_schema.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# SQL Schema for Advanced Data & Reliability Tables
SCHEMA_SQL = """
-- =========================================================================
-- PHASE 1: Vitals Archive Table (Cold Storage)
-- =========================================================================

CREATE TABLE IF NOT EXISTS vitals_archive (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    vital_type VARCHAR(50) NOT NULL,
    value FLOAT NOT NULL,
    metadata JSON DEFAULT NULL,
    timestamp DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_vital_time (user_id, vital_type, timestamp),
    INDEX idx_timestamp (timestamp),
    INDEX idx_user_id (user_id),
    INDEX idx_vital_type (vital_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =========================================================================
-- PHASE 2: Checkpoints Table (Agent State Persistence)
-- =========================================================================

CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255) DEFAULT NULL,
    checkpoint JSON NOT NULL,
    metadata JSON DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (thread_id, checkpoint_id),
    INDEX idx_checkpoints_thread (thread_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =========================================================================
-- Cleanup Stored Procedures (Optional - for maintenance)
-- =========================================================================

-- Delete old checkpoints (older than 30 days)
DELIMITER $$
CREATE PROCEDURE IF NOT EXISTS cleanup_old_checkpoints()
BEGIN
    DELETE FROM checkpoints 
    WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
    
    SELECT ROW_COUNT() AS deleted_count;
END$$
DELIMITER ;

-- Delete old vitals archive (older than 1 year)
DELIMITER $$
CREATE PROCEDURE IF NOT EXISTS cleanup_old_vitals_archive()
BEGIN
    DELETE FROM vitals_archive 
    WHERE timestamp < DATE_SUB(NOW(), INTERVAL 1 YEAR);
    
    SELECT ROW_COUNT() AS deleted_count;
END$$
DELIMITER ;
"""


# SQLite version (for development/testing)
SQLITE_SCHEMA = """
-- SQLite version of schema

CREATE TABLE IF NOT EXISTS vitals_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    vital_type TEXT NOT NULL,
    value REAL NOT NULL,
    metadata TEXT,
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vitals_user_vital_time ON vitals_archive(user_id, vital_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_vitals_timestamp ON vitals_archive(timestamp);

CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    parent_id TEXT,
    checkpoint TEXT NOT NULL,
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (thread_id, checkpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON checkpoints(thread_id);
"""


def create_mysql_schema(database_url: str):
    """Create MySQL schema for advanced reliability tables."""
    logger.info("Creating MySQL schema...")
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Execute schema SQL (split by statements)
            for statement in SCHEMA_SQL.split(";"):
                statement = statement.strip()
                if statement and not statement.startswith("--"):
                    try:
                        conn.execute(text(statement))
                        conn.commit()
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Statement execution warning: {e}")
        
        logger.info("✅ MySQL schema created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create MySQL schema: {e}")
        return False


def create_sqlite_schema(database_url: str):
    """Create SQLite schema for advanced reliability tables."""
    logger.info("Creating SQLite schema...")
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Execute schema SQL
            for statement in SQLITE_SCHEMA.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
                    conn.commit()
        
        logger.info("✅ SQLite schema created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create SQLite schema: {e}")
        return False


def main():
    """Main entry point."""
    # Try to load settings
    try:
        from config import settings
        database_url = settings.DATABASE_URL
    except ImportError:
        database_url = os.getenv("DATABASE_URL", "sqlite:///./vitals_cold_storage.db")
    
    logger.info("=" * 80)
    logger.info("Advanced Data & Reliability Schema Migration")
    logger.info("=" * 80)
    logger.info(f"Database URL: {database_url}")
    
    # Determine database type and create schema
    if "mysql" in database_url or "mariadb" in database_url:
        success = create_mysql_schema(database_url)
    elif "sqlite" in database_url:
        success = create_sqlite_schema(database_url)
    else:
        logger.error(f"Unsupported database type: {database_url}")
        success = False
    
    if success:
        logger.info("=" * 80)
        logger.info("✅ Schema migration completed successfully")
        logger.info("=" * 80)
        logger.info("Tables created:")
        logger.info("  - vitals_archive (cold storage for vitals > 7 days)")
        logger.info("  - checkpoints (agent state persistence)")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Set up cron job for vitals archival: python -m jobs.vitals_archival")
        logger.info("  2. Configure CHECKPOINT_BACKEND in .env (postgres or redis)")
        logger.info("  3. Test vitals storage with your application")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("❌ Schema migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
