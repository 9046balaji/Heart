"""
Data Retention Service.

HIPAA/GDPR compliant data retention and deletion policies.
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RetentionAction(str, Enum):
    """Actions to take when retention period expires."""

    DELETE = "delete"  # Permanently delete
    ARCHIVE = "archive"  # Move to cold storage
    ANONYMIZE = "anonymize"  # Remove PII but keep data
    NOTIFY = "notify"  # Notify before deletion
    EXTEND = "extend"  # Request extension


@dataclass
class RetentionPolicy:
    """Data retention policy definition."""

    name: str
    data_type: str  # documents, health_data, audit_logs, etc.
    retention_days: int
    action: RetentionAction

    # Optional configurations
    warning_days: int = 30  # Days before expiry to warn
    require_confirmation: bool = False  # Require user confirmation before action
    legal_hold_exempt: bool = False  # Can be deleted even under legal hold

    # Conditions
    conditions: Dict[str, Any] = field(default_factory=dict)

    # Audit
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None


@dataclass
class RetentionRecord:
    """Record of data subject to retention policy."""

    id: str
    data_type: str
    resource_id: str
    user_id: str
    policy_name: str

    created_at: datetime
    expires_at: datetime

    # Status
    status: str = "active"  # active, warned, expired, deleted, archived

    # Legal hold
    legal_hold: bool = False
    legal_hold_reason: Optional[str] = None

    # Processing
    last_checked: Optional[datetime] = None
    action_taken: Optional[str] = None
    action_at: Optional[datetime] = None


class DataRetentionService:
    """
    Data retention and lifecycle management service.

    Features:
    - Configurable retention policies per data type
    - HIPAA 6-year minimum for medical records
    - GDPR right to erasure support
    - Legal hold management
    - Automated cleanup jobs

    Example:
        retention = DataRetentionService()

        # Register a policy
        retention.register_policy(RetentionPolicy(
            name="medical_documents",
            data_type="document",
            retention_days=365 * 6,  # 6 years for HIPAA
            action=RetentionAction.ARCHIVE
        ))

        # Track data for retention
        retention.track_data(
            data_type="document",
            resource_id="doc123",
            user_id="user456"
        )

        # Run cleanup
        results = retention.process_expired_data()
    """

    # HIPAA requires 6-year retention for medical records
    HIPAA_RETENTION_DAYS = 365 * 6

    # GDPR specifies "no longer than necessary"
    GDPR_AUDIT_RETENTION_DAYS = 365 * 3

    # Default policies
    DEFAULT_POLICIES = [
        RetentionPolicy(
            name="medical_documents",
            data_type="document",
            retention_days=HIPAA_RETENTION_DAYS,
            action=RetentionAction.ARCHIVE,
            warning_days=90,
        ),
        RetentionPolicy(
            name="health_data",
            data_type="health_data",
            retention_days=HIPAA_RETENTION_DAYS,
            action=RetentionAction.ANONYMIZE,
            warning_days=90,
        ),
        RetentionPolicy(
            name="audit_logs",
            data_type="audit_log",
            retention_days=HIPAA_RETENTION_DAYS,
            action=RetentionAction.ARCHIVE,
            legal_hold_exempt=False,
        ),
        RetentionPolicy(
            name="weekly_summaries",
            data_type="weekly_summary",
            retention_days=365,  # 1 year
            action=RetentionAction.DELETE,
            warning_days=30,
        ),
        RetentionPolicy(
            name="session_data",
            data_type="session",
            retention_days=30,
            action=RetentionAction.DELETE,
        ),
        RetentionPolicy(
            name="temp_uploads",
            data_type="temp_file",
            retention_days=1,
            action=RetentionAction.DELETE,
        ),
    ]

    def __init__(self, audit_service: Optional[Any] = None, load_defaults: bool = True):
        """
        Initialize retention service.

        Args:
            audit_service: AuditService for logging retention actions
            load_defaults: Load default retention policies
        """
        self.audit = audit_service

        self._policies: Dict[str, RetentionPolicy] = {}
        self._records: Dict[str, RetentionRecord] = {}

        # Action handlers
        self._action_handlers: Dict[RetentionAction, Callable] = {
            RetentionAction.DELETE: self._handle_delete,
            RetentionAction.ARCHIVE: self._handle_archive,
            RetentionAction.ANONYMIZE: self._handle_anonymize,
            RetentionAction.NOTIFY: self._handle_notify,
        }

        if load_defaults:
            for policy in self.DEFAULT_POLICIES:
                self.register_policy(policy)

    def register_policy(self, policy: RetentionPolicy) -> None:
        """
        Register a retention policy.

        Args:
            policy: RetentionPolicy to register
        """
        key = f"{policy.data_type}:{policy.name}"
        self._policies[key] = policy
        logger.info(
            f"Registered retention policy: {policy.name} for {policy.data_type}"
        )

    def get_policy(
        self, data_type: str, policy_name: Optional[str] = None
    ) -> Optional[RetentionPolicy]:
        """
        Get retention policy for a data type.

        Args:
            data_type: Type of data
            policy_name: Specific policy name (optional)

        Returns:
            RetentionPolicy or None
        """
        if policy_name:
            return self._policies.get(f"{data_type}:{policy_name}")

        # Find first matching policy for data type
        for key, policy in self._policies.items():
            if policy.data_type == data_type:
                return policy

        return None

    def track_data(
        self,
        data_type: str,
        resource_id: str,
        user_id: str,
        policy_name: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> Optional[RetentionRecord]:
        """
        Register data for retention tracking.

        Args:
            data_type: Type of data
            resource_id: Unique ID of the resource
            user_id: Owner of the data
            policy_name: Specific policy to apply
            created_at: Creation timestamp (default: now)

        Returns:
            RetentionRecord or None if no policy found
        """
        import uuid

        policy = self.get_policy(data_type, policy_name)
        if not policy:
            logger.warning(f"No retention policy for data type: {data_type}")
            return None

        created = created_at or datetime.now(timezone.utc)
        expires = created + timedelta(days=policy.retention_days)

        record = RetentionRecord(
            id=str(uuid.uuid4()),
            data_type=data_type,
            resource_id=resource_id,
            user_id=user_id,
            policy_name=policy.name,
            created_at=created,
            expires_at=expires,
        )

        self._records[resource_id] = record

        logger.debug(
            f"Tracking data for retention: {data_type}/{resource_id} "
            f"expires {expires.isoformat()}"
        )

        return record

    def get_retention_info(self, resource_id: str) -> Optional[RetentionRecord]:
        """
        Get retention information for a resource.

        Args:
            resource_id: Resource ID to look up

        Returns:
            RetentionRecord or None
        """
        return self._records.get(resource_id)

    def set_legal_hold(self, resource_id: str, reason: str, set_by: str) -> bool:
        """
        Place resource under legal hold (prevents deletion).

        Args:
            resource_id: Resource to hold
            reason: Reason for hold
            set_by: User setting the hold

        Returns:
            True if successful
        """
        record = self._records.get(resource_id)
        if not record:
            return False

        record.legal_hold = True
        record.legal_hold_reason = reason

        logger.info(f"Legal hold set on {resource_id} by {set_by}: {reason}")

        return True

    def release_legal_hold(self, resource_id: str, released_by: str) -> bool:
        """
        Release legal hold on a resource.

        Args:
            resource_id: Resource to release
            released_by: User releasing the hold

        Returns:
            True if successful
        """
        record = self._records.get(resource_id)
        if not record:
            return False

        record.legal_hold = False
        record.legal_hold_reason = None

        logger.info(f"Legal hold released on {resource_id} by {released_by}")

        return True

    def get_expired_data(
        self, as_of: Optional[datetime] = None
    ) -> List[RetentionRecord]:
        """
        Get all data that has exceeded retention period.

        Args:
            as_of: Check expiration as of this date (default: now)

        Returns:
            List of expired RetentionRecords
        """
        check_date = as_of or datetime.now(timezone.utc)

        expired = []
        for record in self._records.values():
            if record.status == "active" and record.expires_at <= check_date:
                if not record.legal_hold:
                    expired.append(record)

        return expired

    def get_expiring_soon(self, within_days: int = 30) -> List[RetentionRecord]:
        """
        Get data expiring within specified days.

        Args:
            within_days: Number of days to look ahead

        Returns:
            List of RetentionRecords expiring soon
        """
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=within_days)

        expiring = []
        for record in self._records.values():
            if record.status == "active":
                if now < record.expires_at <= threshold:
                    expiring.append(record)

        return expiring

    def process_expired_data(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Process all expired data according to policies.

        Args:
            dry_run: If True, don't actually process, just report

        Returns:
            Dict with processing results
        """
        expired = self.get_expired_data()

        results = {
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "dry_run": dry_run,
            "details": [],
        }

        for record in expired:
            policy = self.get_policy(record.data_type, record.policy_name)
            if not policy:
                results["skipped"] += 1
                continue

            try:
                if dry_run:
                    results["details"].append(
                        {
                            "resource_id": record.resource_id,
                            "action": policy.action.value,
                            "status": "would_process",
                        }
                    )
                else:
                    handler = self._action_handlers.get(policy.action)
                    if handler:
                        handler(record, policy)
                        record.status = "processed"
                        record.action_taken = policy.action.value
                        record.action_at = datetime.now(timezone.utc)

                        results["details"].append(
                            {
                                "resource_id": record.resource_id,
                                "action": policy.action.value,
                                "status": "processed",
                            }
                        )

                results["processed"] += 1

            except Exception as e:
                logger.error(f"Error processing {record.resource_id}: {e}")
                results["errors"] += 1
                results["details"].append(
                    {
                        "resource_id": record.resource_id,
                        "action": policy.action.value,
                        "status": "error",
                        "error": str(e),
                    }
                )

        logger.info(
            f"Retention processing complete: "
            f"{results['processed']} processed, "
            f"{results['skipped']} skipped, "
            f"{results['errors']} errors"
        )

        return results

    def _handle_delete(self, record: RetentionRecord, policy: RetentionPolicy) -> None:
        """Handle permanent deletion."""
        logger.info(f"Deleting {record.data_type}/{record.resource_id}")
        # In production: call actual deletion service
        record.status = "deleted"

    def _handle_archive(self, record: RetentionRecord, policy: RetentionPolicy) -> None:
        """Handle archival to cold storage."""
        logger.info(f"Archiving {record.data_type}/{record.resource_id}")
        # In production: move to archive storage
        record.status = "archived"

    def _handle_anonymize(
        self, record: RetentionRecord, policy: RetentionPolicy
    ) -> None:
        """Handle data anonymization."""
        logger.info(f"Anonymizing {record.data_type}/{record.resource_id}")
        # In production: remove PII from data
        record.status = "anonymized"

    def _handle_notify(self, record: RetentionRecord, policy: RetentionPolicy) -> None:
        """Handle notification before deletion."""
        logger.info(f"Notifying about {record.data_type}/{record.resource_id}")
        # In production: send notification to user
        record.status = "warned"

    # ==================== GDPR Right to Erasure ====================

    def process_erasure_request(
        self, user_id: str, requested_by: str, reason: str
    ) -> Dict[str, Any]:
        """
        Process GDPR Article 17 erasure request.

        Args:
            user_id: User requesting erasure
            requested_by: Who made the request
            reason: Reason for erasure

        Returns:
            Dict with erasure results
        """
        results = {
            "user_id": user_id,
            "requested_by": requested_by,
            "reason": reason,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "data_types_processed": [],
            "records_deleted": 0,
            "records_held": 0,
        }

        # Find all records for user
        user_records = [r for r in self._records.values() if r.user_id == user_id]

        for record in user_records:
            if record.legal_hold:
                results["records_held"] += 1
                logger.warning(f"Cannot erase {record.resource_id}: under legal hold")
                continue

            # Check if data type has legal retention requirement
            policy = self.get_policy(record.data_type, record.policy_name)
            if policy and policy.legal_hold_exempt is False:
                # Check if minimum retention period has passed
                min_retention = timedelta(days=policy.retention_days)
                if datetime.now(timezone.utc) - record.created_at < min_retention:
                    logger.warning(
                        f"Cannot erase {record.resource_id}: "
                        f"retention period not met"
                    )
                    results["records_held"] += 1
                    continue

            # Process deletion
            self._handle_delete(record, policy)
            results["records_deleted"] += 1

            if record.data_type not in results["data_types_processed"]:
                results["data_types_processed"].append(record.data_type)

        logger.info(
            f"GDPR erasure request processed for {user_id}: "
            f"{results['records_deleted']} deleted, "
            f"{results['records_held']} held"
        )

        return results

    def get_user_data_inventory(self, user_id: str) -> Dict[str, Any]:
        """
        Get inventory of all data held for a user (for GDPR access request).

        Args:
            user_id: User to inventory

        Returns:
            Dict with data inventory
        """
        user_records = [r for r in self._records.values() if r.user_id == user_id]

        inventory = {
            "user_id": user_id,
            "report_date": datetime.now(timezone.utc).isoformat(),
            "total_records": len(user_records),
            "by_type": {},
            "records": [],
        }

        for record in user_records:
            # Count by type
            if record.data_type not in inventory["by_type"]:
                inventory["by_type"][record.data_type] = 0
            inventory["by_type"][record.data_type] += 1

            # Add record details
            inventory["records"].append(
                {
                    "id": record.id,
                    "type": record.data_type,
                    "resource_id": record.resource_id,
                    "created_at": record.created_at.isoformat(),
                    "expires_at": record.expires_at.isoformat(),
                    "status": record.status,
                    "legal_hold": record.legal_hold,
                }
            )

        return inventory


# Global data retention service instance
_retention_service: Optional["DataRetentionService"] = None


def get_retention_service() -> "DataRetentionService":
    """
    Get or create the global data retention service instance.

    Returns:
        DataRetentionService instance
    """
    global _retention_service
    if _retention_service is None:
        _retention_service = DataRetentionService()
    return _retention_service
