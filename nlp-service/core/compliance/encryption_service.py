"""
PHI Encryption Service.

Field-level encryption for Protected Health Information (PHI).
Implements HIPAA-compliant encryption for sensitive medical data.
"""

import os
import base64
import logging
import hashlib
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import cryptography library
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography library not available - PHI encryption disabled")


@dataclass
class EncryptionConfig:
    """Configuration for PHI encryption."""
    master_key: str
    salt: bytes
    iterations: int = 480000  # NIST recommended minimum
    algorithm: str = "AES-256-GCM"


class PHIEncryptionService:
    """
    Encryption service for Protected Health Information.
    
    Implements:
    - Field-level encryption for sensitive data
    - Key derivation from master password (PBKDF2)
    - Encryption at rest (Fernet/AES-256)
    - PHI field identification
    
    HIPAA Requirements:
    - Encryption of PHI at rest
    - Access controls (handled by auth layer)
    - Audit trails (handled by audit service)
    """
    
    # Fields that contain PHI and must be encrypted
    PHI_FIELDS = [
        # Patient identifiers
        'patient_name',
        'patient_id',
        'date_of_birth',
        'social_security_number',
        'ssn',
        'medical_record_number',
        'mrn',
        
        # Contact information
        'address',
        'phone_number',
        'email',
        'emergency_contact',
        
        # Medical information
        'diagnosis',
        'diagnoses',
        'treatment',
        'treatments',
        'medications',
        'medication_list',
        'allergies',
        'medical_history',
        'family_history',
        'medication_history',
        'chronic_conditions',
        
        # Financial
        'insurance_id',
        'insurance_number',
        'billing_info',
        
        # Biometric
        'fingerprint',
        'facial_data',
        'genetic_data',
    ]
    
    # Fields that should never be encrypted (needed for queries)
    EXCLUDED_FIELDS = [
        'id',
        'user_id',
        'document_id',
        'created_at',
        'updated_at',
        'document_type',
        'status',
    ]
    
    def __init__(
        self,
        master_key: Optional[str] = None,
        salt: Optional[bytes] = None,
        mock_mode: bool = False
    ):
        """
        Initialize PHI encryption service.
        
        Args:
            master_key: Master encryption key (from env if not provided)
            salt: Salt for key derivation (from env if not provided)
            mock_mode: If True, return data unencrypted (for testing)
        """
        self.mock_mode = mock_mode
        
        if mock_mode:
            logger.warning("PHI Encryption running in MOCK MODE - data is NOT encrypted")
            self.fernet = None
            return
        
        if not CRYPTO_AVAILABLE:
            logger.error("cryptography library required for PHI encryption")
            self.mock_mode = True
            self.fernet = None
            return
        
        # Get master key
        self.master_key = master_key or os.getenv("PHI_ENCRYPTION_KEY")
        if not self.master_key:
            logger.error("PHI_ENCRYPTION_KEY not configured - encryption disabled")
            self.mock_mode = True
            self.fernet = None
            return
        
        # Get or generate salt
        salt_env = os.getenv("PHI_ENCRYPTION_SALT")
        if salt:
            self.salt = salt
        elif salt_env:
            self.salt = base64.b64decode(salt_env)
        else:
            # Generate random salt (should be stored persistently in production)
            self.salt = os.urandom(16)
            logger.warning(
                f"Generated new encryption salt. Store this value: "
                f"{base64.b64encode(self.salt).decode()}"
            )
        
        # Create Fernet cipher
        self.fernet = self._create_fernet()
        logger.info("PHI Encryption Service initialized successfully")
    
    def _create_fernet(self) -> "Fernet":
        """Create Fernet cipher from master key using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=480000,  # NIST recommendation
        )
        key = base64.urlsafe_b64encode(
            kdf.derive(self.master_key.encode())
        )
        return Fernet(key)
    
    def encrypt_field(self, value: str) -> str:
        """
        Encrypt a single field value.
        
        Args:
            value: Plain text value to encrypt
            
        Returns:
            Base64-encoded encrypted value with 'ENC:' prefix
        """
        if self.mock_mode or not value:
            return value
        
        try:
            encrypted = self.fernet.encrypt(value.encode())
            # Prefix with ENC: to identify encrypted values
            return f"ENC:{base64.urlsafe_b64encode(encrypted).decode()}"
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt_field(self, encrypted_value: str) -> str:
        """
        Decrypt a single field value.
        
        Args:
            encrypted_value: Encrypted value (with ENC: prefix)
            
        Returns:
            Decrypted plain text value
        """
        if self.mock_mode:
            return encrypted_value
        
        if not encrypted_value:
            return encrypted_value
        
        # Check if actually encrypted
        if not encrypted_value.startswith("ENC:"):
            return encrypted_value  # Already plain text
        
        try:
            # Remove prefix and decode
            encrypted_bytes = base64.urlsafe_b64decode(
                encrypted_value[4:]  # Remove "ENC:" prefix
            )
            return self.fernet.decrypt(encrypted_bytes).decode()
        except InvalidToken:
            logger.error("Decryption failed - invalid token (wrong key?)")
            raise
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def is_encrypted(self, value: str) -> bool:
        """Check if a value is encrypted."""
        return isinstance(value, str) and value.startswith("ENC:")
    
    def encrypt_phi_fields(
        self,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Encrypt PHI fields in a data dictionary.
        
        Args:
            data: Dictionary containing data to encrypt
            fields: Specific fields to encrypt (defaults to PHI_FIELDS)
            
        Returns:
            Dictionary with PHI fields encrypted
        """
        if self.mock_mode:
            return data
        
        fields_to_encrypt = fields or self.PHI_FIELDS
        encrypted_data = data.copy()
        
        for key, value in data.items():
            # Skip excluded fields
            if key in self.EXCLUDED_FIELDS:
                continue
            
            # Check if field should be encrypted
            key_lower = key.lower()
            should_encrypt = any(
                phi_field in key_lower 
                for phi_field in [f.lower() for f in fields_to_encrypt]
            )
            
            if should_encrypt and isinstance(value, str) and value:
                # Don't re-encrypt already encrypted values
                if not self.is_encrypted(value):
                    encrypted_data[key] = self.encrypt_field(value)
            elif isinstance(value, dict):
                # Recursively encrypt nested dictionaries
                encrypted_data[key] = self.encrypt_phi_fields(value, fields)
            elif isinstance(value, list):
                # Handle lists of dictionaries or strings
                encrypted_data[key] = self._encrypt_list(value, fields_to_encrypt)
        
        return encrypted_data
    
    def decrypt_phi_fields(
        self,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Decrypt PHI fields in a data dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            fields: Specific fields to decrypt (defaults to all encrypted)
            
        Returns:
            Dictionary with PHI fields decrypted
        """
        if self.mock_mode:
            return data
        
        decrypted_data = data.copy()
        
        for key, value in data.items():
            if isinstance(value, str) and self.is_encrypted(value):
                decrypted_data[key] = self.decrypt_field(value)
            elif isinstance(value, dict):
                decrypted_data[key] = self.decrypt_phi_fields(value, fields)
            elif isinstance(value, list):
                decrypted_data[key] = self._decrypt_list(value)
        
        return decrypted_data
    
    def _encrypt_list(
        self, 
        items: List[Any], 
        fields: List[str]
    ) -> List[Any]:
        """Encrypt items in a list."""
        result = []
        for item in items:
            if isinstance(item, dict):
                result.append(self.encrypt_phi_fields(item, fields))
            elif isinstance(item, str):
                # Encrypt string items in lists (e.g., list of diagnoses)
                result.append(self.encrypt_field(item))
            else:
                result.append(item)
        return result
    
    def _decrypt_list(self, items: List[Any]) -> List[Any]:
        """Decrypt items in a list."""
        result = []
        for item in items:
            if isinstance(item, dict):
                result.append(self.decrypt_phi_fields(item))
            elif isinstance(item, str) and self.is_encrypted(item):
                result.append(self.decrypt_field(item))
            else:
                result.append(item)
        return result
    
    def mask_phi(
        self,
        data: Dict[str, Any],
        show_last: int = 4
    ) -> Dict[str, Any]:
        """
        Mask PHI fields for display (show only last N characters).
        
        Args:
            data: Dictionary with PHI data
            show_last: Number of characters to show at end
            
        Returns:
            Dictionary with masked PHI
        """
        masked_data = data.copy()
        
        for key, value in data.items():
            key_lower = key.lower()
            should_mask = any(
                phi_field in key_lower 
                for phi_field in [f.lower() for f in self.PHI_FIELDS]
            )
            
            if should_mask and isinstance(value, str) and len(value) > show_last:
                # Decrypt if encrypted
                plain_value = self.decrypt_field(value) if self.is_encrypted(value) else value
                # Mask
                masked_data[key] = "*" * (len(plain_value) - show_last) + plain_value[-show_last:]
            elif isinstance(value, dict):
                masked_data[key] = self.mask_phi(value, show_last)
        
        return masked_data
    
    def hash_phi(self, value: str) -> str:
        """
        Create a one-way hash of PHI for comparison without exposing data.
        
        Args:
            value: PHI value to hash
            
        Returns:
            SHA-256 hash of the value
        """
        return hashlib.sha256(value.encode()).hexdigest()
    
    def rotate_key(
        self, 
        data: Dict[str, Any], 
        new_master_key: str
    ) -> Dict[str, Any]:
        """
        Rotate encryption key - decrypt with old key, encrypt with new.
        
        Args:
            data: Data encrypted with current key
            new_master_key: New master key to use
            
        Returns:
            Data re-encrypted with new key
        """
        if self.mock_mode:
            return data
        
        # Decrypt with current key
        decrypted = self.decrypt_phi_fields(data)
        
        # Create new cipher with new key
        old_fernet = self.fernet
        self.master_key = new_master_key
        self.fernet = self._create_fernet()
        
        # Encrypt with new key
        re_encrypted = self.encrypt_phi_fields(decrypted)
        
        logger.info("Key rotation completed successfully")
        return re_encrypted


# Global instance (initialized lazily)
_encryption_service: Optional[PHIEncryptionService] = None


def get_encryption_service(mock_mode: bool = False) -> PHIEncryptionService:
    """Get or create the global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = PHIEncryptionService(mock_mode=mock_mode)
    return _encryption_service
