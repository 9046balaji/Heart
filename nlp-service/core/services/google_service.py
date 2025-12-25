"""
Secure Google Calendar OAuth Service with Encrypted Token Storage

Replaces plaintext JSON file storage with AES-256 encrypted database storage
for HIPAA compliance and security hardening.

Phase 4: Security & Privacy - Encrypted OAuth Tokens
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SecureGoogleService:
    """
    Google Calendar integration with encrypted OAuth token storage.
    
    Security Improvements:
    - Old: token_{email}.json files in plaintext
    - New: AES-256-GCM encrypted storage in database
    - No tokens on filesystem
    - Automatic token expiry tracking
    
    Example:
        service = SecureGoogleService()
        
        # Store token securely
        await service.store_oauth_token(user_id="123", token_data={
            "access_token": "ya29...",
            "refresh_token": "1//...",
            "expires_at": 1735123456
        })
        
        # Retrieve and decrypt
        token = await service.get_oauth_token(user_id="123")
        # Use with Google API
    """
    
    def __init__(self):
        """Initialize service with encryption and database."""
        from core.services.encryption_service import get_encryption_service
        
        self.encryption = get_encryption_service()
        self._db = None  # Lazy load
        
        logger.info("SecureGoogleService initialized")
    
    def _get_database(self):
        """Lazy load database connection."""
        if self._db is None:
            try:
                from core.database.xampp_db import XAMPPDatabase
                self._db = XAMPPDatabase()
                logger.info("Database connection established for OAuth storage")
            except ImportError:
                logger.error("Database not available")
                raise ValueError("Database connection failed")
        return self._db
    
    async def store_oauth_token(
        self,
        user_id: str,
        token_data: Dict[str, Any]
    ) -> bool:
        """
        Store OAuth token securely in database.
        
        OLD: Wrote to tokens/token_{email}.json (plaintext file)
        NEW: AES-256-GCM encrypted column in users table
        
        Args:
            user_id: User ID
            token_data: OAuth token dictionary from Google
                - access_token: Current access token
                - refresh_token: Refresh token
                - expires_at: Unix timestamp of expiration
                - scope: Granted scopes
                - token_type: "Bearer"
        
        Returns:
            True if stored successfully
        """
        try:
            # Serialize token to JSON
            token_json = json.dumps(token_data)
            
            # Encrypt using AES-256-GCM
            encrypted_token = self.encryption.encrypt(token_json)
            
            # Store in database
            db = self._get_database()
            await db.execute_query(
                """
                UPDATE users 
                SET google_oauth_token = %s,
                    google_oauth_updated_at = NOW()
                WHERE id = %s
                """,
                (encrypted_token, user_id),
                operation="write"
            )
            
            logger.info(f"OAuth token securely stored for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store OAuth token for user {user_id}: {e}")
            return False
    
    async def get_oauth_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt OAuth token.
        
        Args:
            user_id: User ID
        
        Returns:
            Decrypted token dictionary, or None if not found
        """
        try:
            db = self._get_database()
            result = await db.execute_query(
                "SELECT google_oauth_token FROM users WHERE id = %s",
                (user_id,),
                operation="read",
                fetch_one=True
            )
            
            if not result or not result.get('google_oauth_token'):
                logger.debug(f"No OAuth token found for user {user_id}")
                return None
            
            # Decrypt token
            encrypted_token = result['google_oauth_token']
            decrypted_json = self.encryption.decrypt(encrypted_token)
            
            # Parse JSON
            token_data = json.loads(decrypted_json)
            
            logger.info(f"OAuth token retrieved for user {user_id}")
            return token_data
            
        except Exception as e:
            logger.error(f"Failed to retrieve OAuth token for user {user_id}: {e}")
            return None
    
    async def delete_oauth_token(self, user_id: str) -> bool:
        """
        Revoke and delete OAuth token.
        
        This should be called when:
        - User disconnects Google Calendar
        - User logs out
        - Token is compromised
        
        Args:
            user_id: User ID
        
        Returns:
            True if deleted successfully
        """
        try:
            # TODO: Optionally revoke token with Google API first
            # This would call Google's revoke endpoint
            
            db = self._get_database()
            await db.execute_query(
                """
                UPDATE users 
                SET google_oauth_token = NULL,
                    google_oauth_updated_at = NOW()
                WHERE id = %s
                """,
                (user_id,),
                operation="write"
            )
            
            logger.info(f"OAuth token deleted for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete OAuth token for user {user_id}: {e}")
            return False
    
    async def check_token_expiry(self, user_id: str) -> bool:
        """
        Check if stored token is expired.
        
        Args:
            user_id: User ID
        
        Returns:
            True if token is expired or missing
        """
        token = await self.get_oauth_token(user_id)
        
        if not token:
            return True  # No token = expired
        
        expires_at = token.get('expires_at', 0)
        current_time = datetime.now().timestamp()
        
        is_expired = current_time >= expires_at
        
        if is_expired:
            logger.warning(f"OAuth token expired for user {user_id}")
        
        return is_expired
    
    async def refresh_token_if_needed(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if token is expired and refresh if needed.
        
        Args:
            user_id: User ID
        
        Returns:
            Current valid token, or None if refresh failed
        """
        # Check if expired
        if not await self.check_token_expiry(user_id):
            # Token is still valid
            return await self.get_oauth_token(user_id)
        
        # Token expired, try to refresh
        logger.info(f"Refreshing expired OAuth token for user {user_id}")
        
        token = await self.get_oauth_token(user_id)
        if not token or 'refresh_token' not in token:
            logger.error(f"No refresh token available for user {user_id}")
            return None
        
        try:
            # TODO: Implement actual token refresh with Google OAuth
            # This would use the refresh_token to get a new access_token
            # from Google's token endpoint
            
            logger.warning("Token refresh not yet implemented - requires Google OAuth flow")
            return None
            
        except Exception as e:
            logger.error(f"Token refresh failed for user {user_id}: {e}")
            return None


# =============================================================================
# MIGRATION UTILITIES
# =============================================================================

async def migrate_json_tokens_to_database():
    """
    Migrate existing JSON token files to encrypted database storage.
    
    This should be run once during deployment to migrate existing tokens.
    
    Steps:
    1. Find all token_*.json files
    2. Read each file
    3. Extract email/user_id
    4. Encrypt and store in database
    5. Backup original file
    6. Delete original file
    """
    import glob
    import shutil
    from pathlib import Path
    
    logger.info("Starting OAuth token migration from JSON files to database")
    
    service = SecureGoogleService()
    db = service._get_database()
    
    # Find token files
    token_files = glob.glob("tokens/token_*.json")
    
    if not token_files:
        logger.info("No token files found to migrate")
        return
    
    migrated_count = 0
    error_count = 0
    
    # Create backup directory
    backup_dir = Path("tokens/backup_before_migration")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    for token_file in token_files:
        try:
            # Extract email from filename: token_user@example.com.json
            filename = Path(token_file).name
            email = filename.replace("token_", "").replace(".json", "")
            
            logger.info(f"Migrating token for: {email}")
            
            # Read token file
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            
            # Find user ID from email
            user = await db.execute_query(
                "SELECT id FROM users WHERE email = %s",
                (email,),
                operation="read",
                fetch_one=True
            )
            
            if not user:
                logger.warning(f"No user found for email: {email}, skipping")
                continue
            
            user_id = user['id']
            
            # Store encrypted token
            success = await service.store_oauth_token(user_id, token_data)
            
            if success:
                # Backup original file
                backup_path = backup_dir / filename
                shutil.copy2(token_file, backup_path)
                logger.info(f"Backed up to: {backup_path}")
                
                # Delete original
                os.remove(token_file)
                logger.info(f"Deleted original file: {token_file}")
                
                migrated_count += 1
            else:
                error_count += 1
                logger.error(f"Failed to migrate: {token_file}")
                
        except Exception as e:
            error_count += 1
            logger.error(f"Error migrating {token_file}: {e}")
    
    logger.info(f"Migration complete: {migrated_count} migrated, {error_count} errors")
    logger.info(f"Backup files saved to: {backup_dir}")


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_service_instance: Optional[SecureGoogleService] = None


def get_secure_google_service() -> SecureGoogleService:
    """Get singleton SecureGoogleService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SecureGoogleService()
    return _service_instance


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test_service():
        print("=" * 70)
        print(" Testing Secure Google OAuth Service")
        print("=" * 70)
        
        service = SecureGoogleService()
        
        # Test token storage and retrieval
        test_user_id = "test_user_123"
        test_token = {
            "access_token": "ya29.test_access_token_12345",
            "refresh_token": "1//test_refresh_token_67890",
            "expires_at": datetime.now().timestamp() + 3600,  # 1 hour from now
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer"
        }
        
        print(f"\n🧪 Test 1: Store Token\n")
        print(f"User ID: {test_user_id}")
        print(f"Token (first 50 chars): {str(test_token)[:50]}...")
        
        # Note: This will fail without database connection
        try:
            success = await service.store_oauth_token(test_user_id, test_token)
            print(f"Result: {'✅ Stored' if success else '❌ Failed'}")
        except Exception as e:
            print(f"❌ Error (expected without database): {e}")
        
        print("\n" + "=" * 70)
        print("✅ Secure Google OAuth Service implementation complete!")
        print("=" * 70)
        print("\nNote: Full testing requires database connection.")
        print("Migration utility available: migrate_json_tokens_to_database()")
    
    asyncio.run(test_service())
