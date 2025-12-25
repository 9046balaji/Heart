"""
Database Migration: Add Encrypted OAuth Token Columns

Adds google_oauth_token and google_oauth_updated_at columns to users table
for secure OAuth token storage.

Run with: python run_oauth_token_migration.py
"""

import asyncio
import logging
import sys
sys.path.insert(0, '.')

from core.database.xampp_db import XAMPPDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migration():
    """Add OAuth token columns to users table."""
    
    logger.info("=" * 70)
    logger.info(" OAuth Token Storage - Database Migration")
    logger.info("=" * 70)
    
    db = XAMPPDatabase()
    
    # Check if columns already exist
    logger.info("\nStep 1: Checking if migration is needed...")
    
    try:
        result = await db.execute_query(
            """
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'users' 
            AND COLUMN_NAME IN ('google_oauth_token', 'google_oauth_updated_at')
            """,
            operation="read"
        )
        
        if result and len(result) >= 2:
            logger.info("✅ Columns already exist, migration not needed")
            return
            
    except Exception as e:
        logger.warning(f"Could not check existing columns: {e}")
    
    # Add columns
    logger.info("\nStep 2: Adding google_oauth_token column...")
    
    try:
        await db.execute_query(
            """
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS google_oauth_token TEXT NULL
            """,
            operation="write"
        )
        logger.info("✅ google_oauth_token column added")
    except Exception as e:
        logger.error(f"Failed to add google_oauth_token column: {e}")
        raise
    
    logger.info("\nStep 3: Adding google_oauth_updated_at column...")
    
    try:
        await db.execute_query(
            """
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS google_oauth_updated_at DATETIME NULL
            """,
            operation="write"
        )
        logger.info("✅ google_oauth_updated_at column added")
    except Exception as e:
        logger.error(f"Failed to add google_oauth_updated_at column: {e}")
        raise
    
    # Verify
    logger.info("\nStep 4: Verifying migration...")
    
    try:
        result = await db.execute_query(
            """
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'users' 
            AND COLUMN_NAME IN ('google_oauth_token', 'google_oauth_updated_at')
            ORDER BY COLUMN_NAME
            """,
            operation="read"
        )
        
        if result and len(result) == 2:
            logger.info("✅ Migration verified successfully")
            for col in result:
                logger.info(f"   - {col['COLUMN_NAME']}: {col['DATA_TYPE']}")
        else:
            logger.error("❌ Migration verification failed")
            
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ OAuth Token Storage Migration Complete!")
    logger.info("=" * 70)
    logger.info("\nNext steps:")
    logger.info("  1. Test token storage with SecureGoogleService")
    logger.info("  2. Run migrate_json_tokens_to_database() to migrate existing tokens")
    logger.info("  3. Update OAuth endpoints to use new service")


if __name__ == "__main__":
    try:
        asyncio.run(run_migration())
    except KeyboardInterrupt:
        logger.info("\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        sys.exit(1)
