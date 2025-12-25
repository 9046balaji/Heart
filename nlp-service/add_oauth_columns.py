"""
Simple Database Migration: Add OAuth Token Columns

Run with: python add_oauth_columns.py
"""

import asyncio
import aiomysql
import os
from dotenv import load_dotenv

load_dotenv()

async def run_migration():
    """Add OAuth token columns to users table."""
    
    print("=" * 70)
    print(" OAuth Token Storage - Database Migration")
    print("=" * 70)
    
    # Connect to database
    connection = await aiomysql.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', ''),
        db=os.getenv('MYSQL_DATABASE', 'cardio_ai'),
    )
    
    try:
        async with connection.cursor() as cursor:
            # Check if columns exist
            print("\nStep 1: Checking existing columns...")
            await cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME IN ('google_oauth_token', 'google_oauth_updated_at')
            """)
            
            existing = await cursor.fetchall()
            
            if len(existing) >= 2:
                print("✅ Columns already exist, migration not needed")
                return
            
            # Add google_oauth_token column
            print("\nStep 2: Adding google_oauth_token column...")
            try:
                await cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN google_oauth_token TEXT NULL
                """)
                await connection.commit()
                print("✅ google_oauth_token column added")
            except Exception as e:
                if "Duplicate column" in str(e):
                    print("✅ google_oauth_token column already exists")
                else:
                    raise
            
            # Add google_oauth_updated_at column
            print("\nStep 3: Adding google_oauth_updated_at column...")
            try:
                await cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN google_oauth_updated_at DATETIME NULL
                """)
                await connection.commit()
                print("✅ google_oauth_updated_at column added")
            except Exception as e:
                if "Duplicate column" in str(e):
                    print("✅ google_oauth_updated_at column already exists")
                else:
                    raise
            
            # Verify
            print("\nStep 4: Verifying migration...")
            await cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME IN ('google_oauth_token', 'google_oauth_updated_at')
                ORDER BY COLUMN_NAME
            """)
            
            result = await cursor.fetchall()
            
            if len(result) == 2:
                print("✅ Migration verified successfully")
                for col in result:
                    print(f"   - {col[0]}: {col[1]}")
            else:
                print("❌ Migration verification failed")
        
        print("\n" + "=" * 70)
        print("✅ OAuth Token Storage Migration Complete!")
        print("=" * 70)
        
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_migration())
    except KeyboardInterrupt:
        print("\nMigration cancelled by user")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
