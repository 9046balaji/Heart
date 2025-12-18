"""
Compliance & Audit Package.

HIPAA/GDPR compliant audit logging, consent management, data retention,
medical disclaimers, and PHI encryption.
"""

from .audit_logger import (
    AuditService,
    AuditEvent,
    AuditEventType,
    AuditLog,
    get_audit_service
)
from .consent_manager import (
    ConsentManager,
    ConsentRecord,
    ConsentType,
    ConsentStatus,
    get_consent_manager
)
from .data_retention import (
    DataRetentionService,
    RetentionPolicy,
    RetentionAction,
    get_retention_service
)
from .verification_queue import (
    VerificationQueue,
    VerificationItem,
    VerificationStatus,
    VerificationResult,
    get_verification_queue
)
from .disclaimer_service import (
    DisclaimerService,
    DisclaimerType,
    DisclaimerSeverity,
    Disclaimer,
    get_disclaimer_service
)
from .encryption_service import (
    PHIEncryptionService,
    get_encryption_service
)

__all__ = [
    # Audit
    "AuditService",
    "AuditEvent",
    "AuditEventType",
    "AuditLog",
    
    # Consent
    "ConsentManager",
    "ConsentRecord",
    "ConsentType",
    "ConsentStatus",
    
    # Retention
    "DataRetentionService",
    "RetentionPolicy",
    "RetentionAction",
    
    # Verification
    "VerificationQueue",
    "VerificationItem",
    "VerificationStatus",
    "VerificationResult"
]
