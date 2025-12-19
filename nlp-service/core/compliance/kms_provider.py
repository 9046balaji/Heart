"""
Key Management Service Integration.

Provides abstraction layer for encryption key management with multiple KMS providers.
Supports AWS KMS, Azure Key Vault, and environment variable fallback for development.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class KMSProvider(ABC):
    """Abstract base class for KMS providers."""
    
    @abstractmethod
    def get_key(self, key_id: str) -> bytes:
        """
        Get encryption key from KMS.
        
        Args:
            key_id: Key identifier
            
        Returns:
            Raw key bytes
        """
        pass
    
    @abstractmethod
    def rotate_key(self, key_id: str) -> str:
        """
        Rotate encryption key in KMS.
        
        Args:
            key_id: Key identifier
            
        Returns:
            New key identifier
        """
        pass


class AWSKMSProvider(KMSProvider):
    """AWS KMS integration."""
    
    def __init__(self):
        """Initialize AWS KMS provider."""
        try:
            import boto3
            self.client = boto3.client('kms')
            self.key_id = os.getenv("AWS_KMS_KEY_ID")
            if not self.key_id:
                raise ValueError("AWS_KMS_KEY_ID environment variable not set")
            logger.info("AWS KMS provider initialized")
        except ImportError:
            raise ImportError("boto3 required for AWS KMS. Install with: pip install boto3")
        except Exception as e:
            logger.error(f"Failed to initialize AWS KMS provider: {e}")
            raise
    
    def get_key(self, key_id: str) -> bytes:
        """
        Get encryption key from AWS KMS.
        
        Args:
            key_id: Key identifier (ARN or alias)
            
        Returns:
            Raw key bytes
        """
        try:
            response = self.client.generate_data_key(
                KeyId=key_id or self.key_id,
                KeySpec='AES_256'
            )
            return response['Plaintext']
        except Exception as e:
            logger.error(f"Failed to get key from AWS KMS: {e}")
            raise
    
    def rotate_key(self, key_id: str) -> str:
        """
        Rotate encryption key in AWS KMS.
        
        Args:
            key_id: Key identifier (ARN or alias)
            
        Returns:
            New key identifier
        """
        try:
            response = self.client.rotate_key(KeyId=key_id or self.key_id)
            return response['KeyId']
        except Exception as e:
            logger.error(f"Failed to rotate key in AWS KMS: {e}")
            raise


class AzureKeyVaultProvider(KMSProvider):
    """Azure Key Vault integration."""
    
    def __init__(self):
        """Initialize Azure Key Vault provider."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.keys import KeyClient
            self.vault_url = os.getenv("AZURE_KEY_VAULT_URL")
            if not self.vault_url:
                raise ValueError("AZURE_KEY_VAULT_URL environment variable not set")
            credential = DefaultAzureCredential()
            self.client = KeyClient(vault_url=self.vault_url, credential=credential)
            logger.info("Azure Key Vault provider initialized")
        except ImportError:
            raise ImportError("azure-identity and azure-keyvault-keys required for Azure Key Vault. Install with: pip install azure-identity azure-keyvault-keys")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Key Vault provider: {e}")
            raise
    
    def get_key(self, key_id: str) -> bytes:
        """
        Get encryption key from Azure Key Vault.
        
        Args:
            key_id: Key name
            
        Returns:
            Raw key bytes
        """
        try:
            # For Azure Key Vault, we typically use the key for wrapping/unwrapping
            # rather than directly getting the key material
            key = self.client.get_key(key_id)
            # This is a simplified implementation - in practice, you'd use the key
            # for cryptographic operations rather than extracting the raw key
            return key.key.n.to_bytes((key.key.n.bit_length() + 7) // 8, 'big')
        except Exception as e:
            logger.error(f"Failed to get key from Azure Key Vault: {e}")
            raise
    
    def rotate_key(self, key_id: str) -> str:
        """
        Rotate encryption key in Azure Key Vault.
        
        Args:
            key_id: Key name
            
        Returns:
            New key version identifier
        """
        try:
            response = self.client.rotate_key(key_id)
            return response.properties.version
        except Exception as e:
            logger.error(f"Failed to rotate key in Azure Key Vault: {e}")
            raise


class EnvFallbackKMSProvider(KMSProvider):
    """Development fallback - NOT FOR PRODUCTION."""
    
    def get_key(self, key_id: str) -> bytes:
        """
        Get encryption key from environment variable.
        
        Args:
            key_id: Ignored for environment fallback
            
        Returns:
            Raw key bytes
        """
        env_key = os.getenv("PHI_ENCRYPTION_KEY")
        if not env_key:
            raise ValueError("PHI_ENCRYPTION_KEY environment variable not set")
        # Convert string key to bytes (this is a simplified approach)
        return env_key.encode()[:32].ljust(32, b'\0')
    
    def rotate_key(self, key_id: str) -> str:
        """
        Rotate encryption key (no-op for environment fallback).
        
        Args:
            key_id: Ignored for environment fallback
            
        Returns:
            Same key identifier
        """
        logger.warning("Key rotation not supported in environment fallback mode")
        return key_id


def get_kms_provider() -> KMSProvider:
    """
    Get appropriate KMS provider based on environment configuration.
    
    Returns:
        Configured KMS provider instance
    """
    # Check for AWS KMS configuration
    if os.getenv("AWS_KMS_KEY_ID"):
        try:
            return AWSKMSProvider()
        except Exception as e:
            logger.warning(f"AWS KMS configuration failed: {e}")
    
    # Check for Azure Key Vault configuration
    if os.getenv("AZURE_KEY_VAULT_URL"):
        try:
            return AzureKeyVaultProvider()
        except Exception as e:
            logger.warning(f"Azure Key Vault configuration failed: {e}")
    
    # Fallback to environment variable for development
    logger.warning("Using environment variable fallback for KMS - NOT RECOMMENDED FOR PRODUCTION")
    return EnvFallbackKMSProvider()