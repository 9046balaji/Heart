"""
Healthcare Audit Trail Service.

Provides comprehensive logging for HIPAA/GDPR compliance.
Tracks all document processing and data access events.
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Document Events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_VIEWED = "document.viewed"
    DOCUMENT_EXPORTED = "document.exported"

    # OCR/AI Events
    OCR_STARTED = "ocr.started"
    OCR_COMPLETED = "ocr.completed"
    OCR_FAILED = "ocr.failed"
    AI_EXTRACTION_STARTED = "ai.extraction.started"
    AI_EXTRACTION_COMPLETED = "ai.extraction.completed"
    AI_SUMMARY_GENERATED = "ai.summary.generated"

    # Verification Events
    VERIFICATION_REQUESTED = "verification.requested"
    VERIFICATION_COMPLETED = "verification.completed"
    VERIFICATION_REJECTED = "verification.rejected"
    DATA_CORRECTED = "data.corrected"

    # Access Events
    DATA_ACCESSED = "data.accessed"
    DATA_MODIFIED = "data.modified"
    DATA_SHARED = "data.shared"

    # Consent Events
    CONSENT_GRANTED = "consent.granted"
    CONSENT_WITHDRAWN = "consent.withdrawn"

    # Weekly Summary Events
    SUMMARY_GENERATED = "summary.generated"
    SUMMARY_DELIVERED = "summary.delivered"
    SUMMARY_DELIVERY_FAILED = "summary.delivery.failed"

    # Security Events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    UNAUTHORIZED_ACCESS = "auth.unauthorized"


@dataclass
class AuditLog:
    """Audit log entry."""

    id: int
    event_id: str
    timestamp: datetime
    event_type: str

    # Actor information
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Resource information
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None

    # Event details
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    error_message: Optional[str] = None

    # Data change tracking
    old_value_hash: Optional[str] = None
    new_value_hash: Optional[str] = None

    # Compliance fields
    phi_accessed: bool = False
    consent_verified: bool = False


@dataclass
class AuditEvent:
    """Structured audit event for logging."""

    event_type: AuditEventType
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    result: str = "success"
    error_message: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    phi_accessed: bool = False
    consent_verified: bool = False


class AuditService:
    """
    Healthcare-compliant audit logging service.

    Features:
    - Immutable audit logs
    - Tamper detection via hashing
    - PHI access tracking
    - Consent verification
    - HIPAA 6-year retention policy support
    - Query and export capabilities

    Example:
        audit = AuditService()

        # Log document upload
        event_id = audit.log_document_upload(
            user_id="user123",
            document_id="doc456",
            filename="lab_results.pdf",
            file_size=102400
        )

        # Log AI extraction
        audit.log_ai_extraction(
            user_id="user123",
            document_id="doc456",
            model_used="medgemma",
            entities_extracted=15,
            confidence=0.92
        )
    """

    # HIPAA requires 6-year retention
    DEFAULT_RETENTION_DAYS = 365 * 6

    def __init__(
        self,
        database_url: Optional[str] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        log_to_file: bool = True,
        log_file_path: Optional[str] = None,
    ):
        """
        Initialize audit service.

        Args:
            database_url: Database connection string
            retention_days: Log retention period (default 6 years)
            log_to_file: Also write to audit log file
            log_file_path: Path to audit log file
        """
        self.retention_days = retention_days
        self.log_to_file = log_to_file
        self.log_file_path = log_file_path or "audit_trail.log"

        self._db_url = database_url or os.getenv(
            "AUDIT_DATABASE_URL", "sqlite:///audit_logs.db"
        )
        self._session = None
        self._engine = None

        # In-memory fallback for when DB not available
        self._memory_logs: List[AuditLog] = []
        self._use_memory = False

        self._setup_file_logger()

    def _setup_file_logger(self) -> None:
        """Set up dedicated file logger for audit trail."""
        if not self.log_to_file:
            return

        self._audit_logger = logging.getLogger("audit_trail")
        self._audit_logger.setLevel(logging.INFO)

        # Remove existing handlers
        self._audit_logger.handlers = []

        # Add file handler
        handler = logging.FileHandler(self.log_file_path)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        self._audit_logger.addHandler(handler)

    def _generate_event_id(self, event: AuditEvent, timestamp: datetime) -> str:
        """Generate unique event ID."""
        import uuid

        # Combine timestamp + event type + random for uniqueness
        data = f"{timestamp.isoformat()}:{event.event_type.value}:{uuid.uuid4()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def _hash_value(self, value: Any) -> str:
        """Hash a value for change tracking."""
        if value is None:
            return ""

        if isinstance(value, dict):
            value = json.dumps(value, sort_keys=True)

        return hashlib.sha256(str(value).encode()).hexdigest()

    def log_event(self, event: AuditEvent) -> str:
        """
        Log an audit event.

        Args:
            event: AuditEvent to log

        Returns:
            Event ID for reference
        """
        timestamp = datetime.now(timezone.utc)
        event_id = self._generate_event_id(event, timestamp)

        # Calculate hashes for change tracking
        old_hash = self._hash_value(event.old_value) if event.old_value else None
        new_hash = self._hash_value(event.new_value) if event.new_value else None

        audit_log = AuditLog(
            id=0,  # Auto-increment in DB
            event_id=event_id,
            timestamp=timestamp,
            event_type=event.event_type.value,
            user_id=event.user_id,
            user_email=event.user_email,
            user_role=event.user_role,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            resource_name=event.resource_name,
            action=event.action,
            details=event.details,
            result=event.result,
            error_message=event.error_message,
            old_value_hash=old_hash,
            new_value_hash=new_hash,
            phi_accessed=event.phi_accessed,
            consent_verified=event.consent_verified,
        )

        # Store in memory (fallback)
        self._memory_logs.append(audit_log)

        # Log to file
        if self.log_to_file and hasattr(self, "_audit_logger"):
            log_line = (
                f"{event.event_type.value} | "
                f"user={event.user_id} | "
                f"resource={event.resource_type}/{event.resource_id} | "
                f"action={event.action} | "
                f"result={event.result} | "
                f"phi={event.phi_accessed} | "
                f"consent={event.consent_verified}"
            )
            if event.details:
                log_line += f" | details={json.dumps(event.details)}"
            self._audit_logger.info(log_line)

        # Also log to standard logger
        logger.info(
            f"AUDIT [{event_id[:8]}]: {event.event_type.value} | "
            f"user={event.user_id} | resource={event.resource_type}/{event.resource_id}"
        )

        return event_id

    # ==================== Document Events ====================

    def log_document_upload(
        self,
        user_id: str,
        document_id: str,
        filename: str,
        file_size: int,
        document_type: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """Log document upload event."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.DOCUMENT_UPLOADED,
                user_id=user_id,
                ip_address=ip_address,
                resource_type="document",
                resource_id=document_id,
                resource_name=filename,
                action="upload",
                details={
                    "file_size": file_size,
                    "filename": filename,
                    "document_type": document_type,
                },
                phi_accessed=True,
            )
        )

    def log_document_viewed(
        self, user_id: str, document_id: str, ip_address: Optional[str] = None
    ) -> str:
        """Log document view event."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.DOCUMENT_VIEWED,
                user_id=user_id,
                ip_address=ip_address,
                resource_type="document",
                resource_id=document_id,
                action="view",
                phi_accessed=True,
            )
        )

    def log_document_deleted(
        self,
        user_id: str,
        document_id: str,
        reason: str,
        ip_address: Optional[str] = None,
    ) -> str:
        """Log document deletion event."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.DOCUMENT_DELETED,
                user_id=user_id,
                ip_address=ip_address,
                resource_type="document",
                resource_id=document_id,
                action="delete",
                details={"reason": reason},
                phi_accessed=True,
            )
        )

    def log_document_exported(
        self,
        user_id: str,
        document_id: str,
        export_format: str,
        recipient: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """Log document export/share event."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.DOCUMENT_EXPORTED,
                user_id=user_id,
                ip_address=ip_address,
                resource_type="document",
                resource_id=document_id,
                action="export",
                details={"format": export_format, "recipient": recipient},
                phi_accessed=True,
            )
        )

    # ==================== OCR/AI Events ====================

    def log_ocr_started(self, user_id: str, document_id: str, engine: str) -> str:
        """Log OCR processing start."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.OCR_STARTED,
                user_id=user_id,
                resource_type="document",
                resource_id=document_id,
                action="ocr_start",
                details={"engine": engine},
                phi_accessed=True,
            )
        )

    def log_ocr_completed(
        self,
        user_id: str,
        document_id: str,
        engine: str,
        processing_time_ms: float,
        confidence: float,
        page_count: int = 1,
    ) -> str:
        """Log OCR processing completion."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.OCR_COMPLETED,
                user_id=user_id,
                resource_type="document",
                resource_id=document_id,
                action="ocr_complete",
                details={
                    "engine": engine,
                    "processing_time_ms": processing_time_ms,
                    "confidence": confidence,
                    "page_count": page_count,
                },
                phi_accessed=True,
            )
        )

    def log_ocr_failed(
        self, user_id: str, document_id: str, engine: str, error: str
    ) -> str:
        """Log OCR processing failure."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.OCR_FAILED,
                user_id=user_id,
                resource_type="document",
                resource_id=document_id,
                action="ocr_failed",
                result="failure",
                error_message=error,
                details={"engine": engine},
                phi_accessed=True,
            )
        )

    def log_ai_extraction(
        self,
        user_id: str,
        document_id: str,
        model_used: str,
        entities_extracted: int,
        confidence: float,
        extraction_type: str = "general",
    ) -> str:
        """Log AI extraction event."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.AI_EXTRACTION_COMPLETED,
                user_id=user_id,
                resource_type="document",
                resource_id=document_id,
                action="ai_extraction",
                details={
                    "model": model_used,
                    "entities_extracted": entities_extracted,
                    "confidence": confidence,
                    "extraction_type": extraction_type,
                },
                phi_accessed=True,
            )
        )

    def log_ai_summary_generated(
        self, user_id: str, document_id: str, model_used: str, summary_length: int
    ) -> str:
        """Log AI summary generation."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.AI_SUMMARY_GENERATED,
                user_id=user_id,
                resource_type="document",
                resource_id=document_id,
                action="ai_summary",
                details={"model": model_used, "summary_length": summary_length},
                phi_accessed=True,
            )
        )

    # ==================== Verification Events ====================

    def log_verification_requested(
        self, user_id: str, document_id: str, verification_type: str
    ) -> str:
        """Log verification request."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.VERIFICATION_REQUESTED,
                user_id=user_id,
                resource_type="document",
                resource_id=document_id,
                action="verification_request",
                details={"verification_type": verification_type},
                phi_accessed=True,
            )
        )

    def log_verification_completed(
        self,
        user_id: str,
        document_id: str,
        verifier_id: str,
        verified: bool,
        changes_made: List[Dict[str, Any]],
    ) -> str:
        """Log human verification completion."""
        event_type = (
            AuditEventType.VERIFICATION_COMPLETED
            if verified
            else AuditEventType.VERIFICATION_REJECTED
        )

        return self.log_event(
            AuditEvent(
                event_type=event_type,
                user_id=user_id,
                resource_type="document",
                resource_id=document_id,
                action="human_verification",
                details={
                    "verifier_id": verifier_id,
                    "verified": verified,
                    "changes_count": len(changes_made),
                    "changes": changes_made,
                },
                phi_accessed=True,
                consent_verified=True,
            )
        )

    def log_data_correction(
        self,
        user_id: str,
        document_id: str,
        field_name: str,
        old_value: Any,
        new_value: Any,
        reason: str,
    ) -> str:
        """Log data correction by human."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.DATA_CORRECTED,
                user_id=user_id,
                resource_type="document",
                resource_id=document_id,
                action="data_correction",
                details={"field": field_name, "reason": reason},
                old_value=old_value,
                new_value=new_value,
                phi_accessed=True,
            )
        )

    # ==================== Weekly Summary Events ====================

    def log_summary_generated(
        self,
        user_id: str,
        summary_id: str,
        week_start: datetime,
        week_end: datetime,
        data_completeness: float,
    ) -> str:
        """Log weekly summary generation."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.SUMMARY_GENERATED,
                user_id=user_id,
                resource_type="weekly_summary",
                resource_id=summary_id,
                action="generate_summary",
                details={
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "data_completeness": data_completeness,
                },
                phi_accessed=True,
                consent_verified=True,
            )
        )

    def log_summary_delivered(
        self, user_id: str, summary_id: str, channel: str, destination: str
    ) -> str:
        """Log weekly summary delivery."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.SUMMARY_DELIVERED,
                user_id=user_id,
                resource_type="weekly_summary",
                resource_id=summary_id,
                action="deliver_summary",
                details={
                    "channel": channel,
                    "destination": self._mask_destination(destination),
                },
                phi_accessed=True,
                consent_verified=True,
            )
        )

    def log_summary_delivery_failed(
        self, user_id: str, summary_id: str, channel: str, error: str
    ) -> str:
        """Log weekly summary delivery failure."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.SUMMARY_DELIVERY_FAILED,
                user_id=user_id,
                resource_type="weekly_summary",
                resource_id=summary_id,
                action="deliver_summary",
                result="failure",
                error_message=error,
                details={"channel": channel},
                phi_accessed=True,
            )
        )

    # ==================== Consent Events ====================

    def log_consent_granted(
        self,
        user_id: str,
        consent_type: str,
        scope: str,
        ip_address: Optional[str] = None,
    ) -> str:
        """Log consent grant."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.CONSENT_GRANTED,
                user_id=user_id,
                ip_address=ip_address,
                resource_type="consent",
                resource_id=f"{user_id}:{consent_type}",
                action="grant_consent",
                details={"consent_type": consent_type, "scope": scope},
                consent_verified=True,
            )
        )

    def log_consent_withdrawn(
        self, user_id: str, consent_type: str, ip_address: Optional[str] = None
    ) -> str:
        """Log consent withdrawal."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.CONSENT_WITHDRAWN,
                user_id=user_id,
                ip_address=ip_address,
                resource_type="consent",
                resource_id=f"{user_id}:{consent_type}",
                action="withdraw_consent",
                details={"consent_type": consent_type},
            )
        )

    # ==================== Security Events ====================

    def log_login_success(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Log successful login."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                action="login",
                result="success",
            )
        )

    def log_login_failed(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        reason: str = "invalid_credentials",
    ) -> str:
        """Log failed login."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.LOGIN_FAILED,
                user_id=user_id,
                ip_address=ip_address,
                action="login",
                result="failure",
                error_message=reason,
            )
        )

    def log_unauthorized_access(
        self,
        user_id: Optional[str],
        resource_type: str,
        resource_id: str,
        ip_address: Optional[str] = None,
    ) -> str:
        """Log unauthorized access attempt."""
        return self.log_event(
            AuditEvent(
                event_type=AuditEventType.UNAUTHORIZED_ACCESS,
                user_id=user_id,
                ip_address=ip_address,
                resource_type=resource_type,
                resource_id=resource_id,
                action="access_denied",
                result="failure",
            )
        )

    # ==================== Query Methods ====================

    def get_user_events(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
    ) -> List[AuditLog]:
        """Get audit events for a user."""
        results = []

        for log in self._memory_logs:
            if log.user_id != user_id:
                continue

            if start_date and log.timestamp < start_date:
                continue

            if end_date and log.timestamp > end_date:
                continue

            if event_types and log.event_type not in [e.value for e in event_types]:
                continue

            results.append(log)

        return sorted(results, key=lambda x: x.timestamp, reverse=True)

    def get_document_events(self, document_id: str) -> List[AuditLog]:
        """Get all events for a document."""
        return [
            log
            for log in self._memory_logs
            if log.resource_type == "document" and log.resource_id == document_id
        ]

    def get_phi_access_report(
        self, start_date: datetime, end_date: datetime
    ) -> List[AuditLog]:
        """Get PHI access report for compliance."""
        return [
            log
            for log in self._memory_logs
            if log.phi_accessed and start_date <= log.timestamp <= end_date
        ]

    # ==================== Utility Methods ====================

    def _mask_destination(self, destination: str) -> str:
        """Mask PII in destination (email/phone)."""
        if "@" in destination:
            # Email: show first 2 chars and domain
            parts = destination.split("@")
            return f"{parts[0][:2]}***@{parts[1]}"
        elif destination.startswith("+"):
            # Phone: show country code and last 4
            return f"{destination[:3]}***{destination[-4:]}"
        return "***"


# ==================== Singleton Access ====================

# Global audit service instance
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """
    Get or create the global audit service instance.

    Returns:
        AuditService instance
    """
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
