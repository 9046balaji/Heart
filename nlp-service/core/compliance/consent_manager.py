"""
Consent Management Service.

HIPAA/GDPR compliant consent tracking for healthcare features.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class ConsentType(str, Enum):
    """Types of consent."""
    # Data Processing
    HEALTH_DATA_PROCESSING = "health_data_processing"
    DOCUMENT_SCANNING = "document_scanning"
    AI_ANALYSIS = "ai_analysis"
    
    # Communication
    WEEKLY_SUMMARY_EMAIL = "weekly_summary_email"
    WEEKLY_SUMMARY_WHATSAPP = "weekly_summary_whatsapp"
    WEEKLY_SUMMARY_SMS = "weekly_summary_sms"
    WEEKLY_SUMMARY_PUSH = "weekly_summary_push"
    MEDICATION_REMINDERS = "medication_reminders"
    HEALTH_ALERTS = "health_alerts"
    MARKETING = "marketing"
    
    # Data Sharing
    SHARE_WITH_PROVIDER = "share_with_provider"
    SHARE_WITH_FAMILY = "share_with_family"
    RESEARCH_PARTICIPATION = "research_participation"
    
    # Terms and Policies
    TERMS_OF_SERVICE = "terms_of_service"
    PRIVACY_POLICY = "privacy_policy"
    HIPAA_AUTHORIZATION = "hipaa_authorization"


class ConsentStatus(str, Enum):
    """Consent status."""
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PENDING = "pending"


@dataclass
class ConsentRecord:
    """Record of consent grant or withdrawal."""
    id: str
    user_id: str
    consent_type: ConsentType
    status: ConsentStatus
    granted_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    consent_version: str = "1.0"
    
    # Legal text shown to user
    consent_text_hash: Optional[str] = None
    
    # Additional details
    scope: Optional[str] = None  # What data/features covered
    purpose: Optional[str] = None  # Why consent was requested
    third_parties: List[str] = field(default_factory=list)  # Who data may be shared with
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConsentManager:
    """
    Healthcare consent management service.
    
    Features:
    - Granular per-feature consent
    - Consent versioning
    - Expiration support
    - Audit trail integration
    - GDPR Article 7 compliance
    
    Example:
        consent_mgr = ConsentManager()
        
        # Check if user consented to weekly summaries
        if consent_mgr.has_valid_consent(user_id, ConsentType.WEEKLY_SUMMARY_WHATSAPP):
            send_weekly_summary(user_id)
        
        # Grant consent
        consent_mgr.grant_consent(
            user_id="user123",
            consent_type=ConsentType.WEEKLY_SUMMARY_EMAIL,
            ip_address=request.client.host
        )
        
        # Withdraw consent
        consent_mgr.withdraw_consent(user_id, ConsentType.WEEKLY_SUMMARY_EMAIL)
    """
    
    # Default consent expiration (1 year for healthcare)
    DEFAULT_EXPIRATION_DAYS = 365
    
    def __init__(
        self,
        audit_service: Optional[Any] = None,
        auto_expire_days: int = DEFAULT_EXPIRATION_DAYS
    ):
        """
        Initialize consent manager.
        
        Args:
            audit_service: AuditService for logging consent changes
            auto_expire_days: Days until consent expires (0 = no expiration)
        """
        self.audit = audit_service
        self.auto_expire_days = auto_expire_days
        
        # In-memory storage (replace with DB in production)
        self._consents: Dict[str, Dict[str, ConsentRecord]] = {}
    
    def grant_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        scope: Optional[str] = None,
        purpose: Optional[str] = None,
        consent_text_hash: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        third_parties: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None
    ) -> ConsentRecord:
        """
        Grant consent for a specific type.
        
        Args:
            user_id: User granting consent
            consent_type: Type of consent
            scope: What the consent covers
            purpose: Why consent is requested
            consent_text_hash: Hash of consent text shown
            ip_address: User's IP address
            user_agent: User's browser/app
            third_parties: List of third parties data may be shared with
            expires_in_days: Custom expiration (default: auto_expire_days)
        
        Returns:
            ConsentRecord
        """
        import uuid
        from datetime import timedelta
        
        now = datetime.now(timezone.utc)
        
        # Calculate expiration
        expire_days = expires_in_days or self.auto_expire_days
        expires_at = None
        if expire_days > 0:
            expires_at = now + timedelta(days=expire_days)
        
        record = ConsentRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            consent_type=consent_type,
            status=ConsentStatus.GRANTED,
            granted_at=now,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            consent_text_hash=consent_text_hash,
            scope=scope or self._get_default_scope(consent_type),
            purpose=purpose or self._get_default_purpose(consent_type),
            third_parties=third_parties or []
        )
        
        # Store consent
        if user_id not in self._consents:
            self._consents[user_id] = {}
        self._consents[user_id][consent_type.value] = record
        
        # Audit log
        if self.audit:
            self.audit.log_consent_granted(
                user_id=user_id,
                consent_type=consent_type.value,
                scope=record.scope,
                ip_address=ip_address
            )
        
        logger.info(f"Consent granted: {user_id} -> {consent_type.value}")
        
        return record
    
    def withdraw_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        ip_address: Optional[str] = None
    ) -> Optional[ConsentRecord]:
        """
        Withdraw previously granted consent.
        
        Args:
            user_id: User withdrawing consent
            consent_type: Type of consent to withdraw
            ip_address: User's IP address
        
        Returns:
            Updated ConsentRecord or None if not found
        """
        if user_id not in self._consents:
            return None
        
        if consent_type.value not in self._consents[user_id]:
            return None
        
        record = self._consents[user_id][consent_type.value]
        record.status = ConsentStatus.WITHDRAWN
        record.withdrawn_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)
        
        # Audit log
        if self.audit:
            self.audit.log_consent_withdrawn(
                user_id=user_id,
                consent_type=consent_type.value,
                ip_address=ip_address
            )
        
        logger.info(f"Consent withdrawn: {user_id} -> {consent_type.value}")
        
        return record
    
    def has_valid_consent(
        self,
        user_id: str,
        consent_type: ConsentType
    ) -> bool:
        """
        Check if user has valid (not expired, not withdrawn) consent.
        
        Args:
            user_id: User to check
            consent_type: Type of consent
        
        Returns:
            True if valid consent exists
        """
        record = self.get_consent(user_id, consent_type)
        
        if not record:
            return False
        
        if record.status != ConsentStatus.GRANTED:
            return False
        
        # Check expiration
        if record.expires_at:
            if datetime.now(timezone.utc) > record.expires_at:
                # Update status to expired
                record.status = ConsentStatus.EXPIRED
                record.updated_at = datetime.now(timezone.utc)
                return False
        
        return True
    
    def get_consent(
        self,
        user_id: str,
        consent_type: ConsentType
    ) -> Optional[ConsentRecord]:
        """
        Get consent record for a user and type.
        
        Args:
            user_id: User to look up
            consent_type: Type of consent
        
        Returns:
            ConsentRecord or None
        """
        if user_id not in self._consents:
            return None
        
        return self._consents[user_id].get(consent_type.value)
    
    def get_all_consents(
        self,
        user_id: str,
        include_withdrawn: bool = False
    ) -> List[ConsentRecord]:
        """
        Get all consent records for a user.
        
        Args:
            user_id: User to look up
            include_withdrawn: Include withdrawn consents
        
        Returns:
            List of ConsentRecords
        """
        if user_id not in self._consents:
            return []
        
        records = list(self._consents[user_id].values())
        
        if not include_withdrawn:
            records = [r for r in records if r.status != ConsentStatus.WITHDRAWN]
        
        return records
    
    def get_users_with_consent(
        self,
        consent_type: ConsentType
    ) -> List[str]:
        """
        Get all users who have granted a specific consent.
        
        Args:
            consent_type: Type of consent to check
        
        Returns:
            List of user IDs
        """
        users = []
        
        for user_id, consents in self._consents.items():
            if consent_type.value in consents:
                record = consents[consent_type.value]
                if record.status == ConsentStatus.GRANTED:
                    # Check expiration
                    if not record.expires_at or datetime.now(timezone.utc) <= record.expires_at:
                        users.append(user_id)
        
        return users
    
    def bulk_grant_default_consents(
        self,
        user_id: str,
        consent_types: List[ConsentType],
        ip_address: Optional[str] = None
    ) -> List[ConsentRecord]:
        """
        Grant multiple consents at once (e.g., during registration).
        
        Args:
            user_id: User granting consent
            consent_types: List of consent types
            ip_address: User's IP address
        
        Returns:
            List of ConsentRecords
        """
        records = []
        
        for consent_type in consent_types:
            record = self.grant_consent(
                user_id=user_id,
                consent_type=consent_type,
                ip_address=ip_address
            )
            records.append(record)
        
        return records
    
    def check_required_consents(
        self,
        user_id: str,
        required: List[ConsentType]
    ) -> Dict[str, bool]:
        """
        Check if user has all required consents.
        
        Args:
            user_id: User to check
            required: List of required consent types
        
        Returns:
            Dict mapping consent type to validity
        """
        return {
            consent_type.value: self.has_valid_consent(user_id, consent_type)
            for consent_type in required
        }
    
    def get_missing_consents(
        self,
        user_id: str,
        required: List[ConsentType]
    ) -> List[ConsentType]:
        """
        Get list of missing required consents.
        
        Args:
            user_id: User to check
            required: List of required consent types
        
        Returns:
            List of missing consent types
        """
        return [
            consent_type
            for consent_type in required
            if not self.has_valid_consent(user_id, consent_type)
        ]
    
    def _get_default_scope(self, consent_type: ConsentType) -> str:
        """Get default scope description for consent type."""
        scopes = {
            ConsentType.HEALTH_DATA_PROCESSING: "Processing of health metrics, vitals, and wellness data",
            ConsentType.DOCUMENT_SCANNING: "Scanning and OCR processing of uploaded medical documents",
            ConsentType.AI_ANALYSIS: "AI-powered analysis and entity extraction from health data",
            ConsentType.WEEKLY_SUMMARY_EMAIL: "Weekly health summary delivery via email",
            ConsentType.WEEKLY_SUMMARY_WHATSAPP: "Weekly health summary delivery via WhatsApp",
            ConsentType.WEEKLY_SUMMARY_SMS: "Weekly health summary delivery via SMS",
            ConsentType.WEEKLY_SUMMARY_PUSH: "Weekly health summary delivery via push notification",
            ConsentType.MEDICATION_REMINDERS: "Medication reminder notifications",
            ConsentType.HEALTH_ALERTS: "Health-related alert notifications",
            ConsentType.SHARE_WITH_PROVIDER: "Sharing health data with healthcare providers",
            ConsentType.SHARE_WITH_FAMILY: "Sharing health data with designated family members",
            ConsentType.RESEARCH_PARTICIPATION: "De-identified data use for research purposes",
            ConsentType.TERMS_OF_SERVICE: "Agreement to terms of service",
            ConsentType.PRIVACY_POLICY: "Agreement to privacy policy",
            ConsentType.HIPAA_AUTHORIZATION: "HIPAA authorization for health data use",
        }
        return scopes.get(consent_type, "General data processing")
    
    def _get_default_purpose(self, consent_type: ConsentType) -> str:
        """Get default purpose description for consent type."""
        purposes = {
            ConsentType.HEALTH_DATA_PROCESSING: "To provide personalized health insights",
            ConsentType.DOCUMENT_SCANNING: "To digitize and extract information from medical documents",
            ConsentType.AI_ANALYSIS: "To provide AI-assisted health analysis and recommendations",
            ConsentType.WEEKLY_SUMMARY_EMAIL: "To keep you informed about your weekly health progress",
            ConsentType.WEEKLY_SUMMARY_WHATSAPP: "To keep you informed about your weekly health progress",
            ConsentType.MEDICATION_REMINDERS: "To help you maintain medication compliance",
            ConsentType.HEALTH_ALERTS: "To notify you of important health-related events",
        }
        return purposes.get(consent_type, "To provide health-related services")
    
    def export_consent_report(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Export consent report for GDPR compliance.
        
        Args:
            user_id: User to export
        
        Returns:
            Dict with consent report
        """
        consents = self.get_all_consents(user_id, include_withdrawn=True)
        
        return {
            "user_id": user_id,
            "export_date": datetime.now(timezone.utc).isoformat(),
            "total_consents": len(consents),
            "active_consents": len([c for c in consents if c.status == ConsentStatus.GRANTED]),
            "withdrawn_consents": len([c for c in consents if c.status == ConsentStatus.WITHDRAWN]),
            "consents": [
                {
                    "type": c.consent_type.value,
                    "status": c.status.value,
                    "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                    "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    "scope": c.scope,
                    "purpose": c.purpose,
                    "version": c.consent_version
                }
                for c in consents
            ]
        }


# Required consents for specific features
REQUIRED_CONSENTS = {
    "weekly_summary": [
        ConsentType.HEALTH_DATA_PROCESSING,
        ConsentType.PRIVACY_POLICY
    ],
    "document_scanning": [
        ConsentType.DOCUMENT_SCANNING,
        ConsentType.AI_ANALYSIS,
        ConsentType.PRIVACY_POLICY
    ],
    "ai_analysis": [
        ConsentType.AI_ANALYSIS,
        ConsentType.HEALTH_DATA_PROCESSING,
        ConsentType.PRIVACY_POLICY
    ]
}
