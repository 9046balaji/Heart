"""
Human Verification Queue.

Queue system for human review of AI extractions.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    """Status of verification item."""

    PENDING = "pending"  # Awaiting review
    IN_PROGRESS = "in_progress"  # Being reviewed
    APPROVED = "approved"  # Verified correct
    REJECTED = "rejected"  # Marked incorrect
    CORRECTED = "corrected"  # Corrected by reviewer
    ESCALATED = "escalated"  # Needs higher authority
    EXPIRED = "expired"  # Review window expired


class VerificationPriority(str, Enum):
    """Priority levels for verification."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class VerificationItem:
    """Item in the verification queue."""

    id: str
    user_id: str
    document_id: str
    document_type: str

    # AI extraction data
    extraction_model: str
    extraction_confidence: float
    extracted_data: Dict[str, Any]

    # Status
    status: VerificationStatus = VerificationStatus.PENDING
    priority: VerificationPriority = VerificationPriority.NORMAL

    # Flags
    low_confidence_fields: List[str] = field(default_factory=list)
    flagged_issues: List[str] = field(default_factory=list)

    # Review info
    assigned_to: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    # Corrections
    corrected_data: Optional[Dict[str, Any]] = None
    correction_notes: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    # Metadata
    source_ocr_confidence: Optional[float] = None
    processing_time_ms: Optional[float] = None


@dataclass
class VerificationResult:
    """Result of a verification review."""

    item_id: str
    verified: bool
    reviewer_id: str
    reviewed_at: datetime

    # Changes made
    fields_verified: List[str] = field(default_factory=list)
    fields_corrected: List[Dict[str, Any]] = field(default_factory=list)
    fields_rejected: List[str] = field(default_factory=list)

    # Notes
    reviewer_notes: Optional[str] = None

    # Metrics
    review_duration_seconds: Optional[int] = None


class VerificationQueue:
    """
    Human verification queue for AI extractions.

    Per medical.md requirements:
    - "Always include a human verification layer"
    - "Extraction is useful, but NOT a substitute for human review"

    Features:
    - Priority-based queue management
    - Automatic flagging of low-confidence extractions
    - Reviewer assignment
    - Correction tracking
    - SLA monitoring

    Example:
        queue = VerificationQueue()

        # Add item for review
        item = queue.add_for_verification(
            user_id="user123",
            document_id="doc456",
            document_type="lab_report",
            extraction_model="medgemma",
            extraction_confidence=0.75,
            extracted_data={"glucose": "126 mg/dL", "hba1c": "6.2%"}
        )

        # Get items for a reviewer
        pending = queue.get_pending_items(reviewer_id="reviewer1", limit=10)

        # Submit review
        result = queue.submit_verification(
            item_id=item.id,
            reviewer_id="reviewer1",
            verified=True,
            corrected_data={"glucose": "125 mg/dL"}  # Corrected value
        )
    """

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.90
    LOW_CONFIDENCE_THRESHOLD = 0.70
    AUTO_FLAG_THRESHOLD = 0.50

    # Default SLA (hours to review)
    DEFAULT_SLA_HOURS = 24

    def __init__(
        self, audit_service: Optional[Any] = None, sla_hours: int = DEFAULT_SLA_HOURS
    ):
        """
        Initialize verification queue.

        Args:
            audit_service: AuditService for logging
            sla_hours: Hours until review SLA expires
        """
        self.audit = audit_service
        self.sla_hours = sla_hours

        # In-memory queue (replace with DB in production)
        self._queue: Dict[str, VerificationItem] = {}
        self._by_status: Dict[VerificationStatus, List[str]] = {
            status: [] for status in VerificationStatus
        }

    def add_for_verification(
        self,
        user_id: str,
        document_id: str,
        document_type: str,
        extraction_model: str,
        extraction_confidence: float,
        extracted_data: Dict[str, Any],
        field_confidences: Optional[Dict[str, float]] = None,
        ocr_confidence: Optional[float] = None,
        processing_time_ms: Optional[float] = None,
    ) -> VerificationItem:
        """
        Add an AI extraction for human verification.

        Args:
            user_id: Owner of the document
            document_id: Document that was processed
            document_type: Type of medical document
            extraction_model: AI model used
            extraction_confidence: Overall confidence score
            extracted_data: Extracted entities/fields
            field_confidences: Per-field confidence scores
            ocr_confidence: OCR confidence if applicable
            processing_time_ms: Processing time

        Returns:
            VerificationItem
        """
        import uuid

        item_id = str(uuid.uuid4())

        # Determine priority based on confidence
        priority = self._calculate_priority(extraction_confidence)

        # Flag low-confidence fields
        low_confidence_fields = []
        if field_confidences:
            for field_name, confidence in field_confidences.items():
                if confidence < self.LOW_CONFIDENCE_THRESHOLD:
                    low_confidence_fields.append(field_name)

        # Auto-flag issues
        flagged_issues = self._auto_flag_issues(
            extraction_confidence, extracted_data, document_type
        )

        # Calculate expiration (SLA)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.sla_hours)

        item = VerificationItem(
            id=item_id,
            user_id=user_id,
            document_id=document_id,
            document_type=document_type,
            extraction_model=extraction_model,
            extraction_confidence=extraction_confidence,
            extracted_data=extracted_data,
            priority=priority,
            low_confidence_fields=low_confidence_fields,
            flagged_issues=flagged_issues,
            expires_at=expires_at,
            source_ocr_confidence=ocr_confidence,
            processing_time_ms=processing_time_ms,
        )

        # Add to queue
        self._queue[item_id] = item
        self._by_status[VerificationStatus.PENDING].append(item_id)

        logger.info(
            f"Added to verification queue: {item_id} "
            f"(priority={priority.value}, confidence={extraction_confidence:.2f})"
        )

        # Audit
        if self.audit:
            self.audit.log_verification_requested(
                user_id=user_id,
                document_id=document_id,
                verification_type=document_type,
            )

        return item

    def get_item(self, item_id: str) -> Optional[VerificationItem]:
        """Get a verification item by ID."""
        return self._queue.get(item_id)

    def get_pending_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve pending verification requests.
        
        This is an alias for get_pending_items for backward compatibility.
        """
        items = self.get_pending_items(limit=limit)
        return [
            {
                "id": item.id,
                "user_id": item.user_id,
                "document_id": item.document_id,
                "document_type": item.document_type,
                "status": item.status.value,
            }
            for item in items
        ]

    def get_pending_items(
        self,
        reviewer_id: Optional[str] = None,
        document_type: Optional[str] = None,
        priority: Optional[VerificationPriority] = None,
        limit: int = 10,
    ) -> List[VerificationItem]:
        """
        Get pending verification items.

        Args:
            reviewer_id: Filter by assigned reviewer
            document_type: Filter by document type
            priority: Filter by priority level
            limit: Maximum items to return

        Returns:
            List of VerificationItems
        """
        pending_ids = self._by_status[VerificationStatus.PENDING]

        items = []
        for item_id in pending_ids:
            item = self._queue.get(item_id)
            if not item:
                continue

            # Apply filters
            if reviewer_id and item.assigned_to and item.assigned_to != reviewer_id:
                continue

            if document_type and item.document_type != document_type:
                continue

            if priority and item.priority != priority:
                continue

            items.append(item)

            if len(items) >= limit:
                break

        # Sort by priority and creation time
        priority_order = {
            VerificationPriority.URGENT: 0,
            VerificationPriority.HIGH: 1,
            VerificationPriority.NORMAL: 2,
            VerificationPriority.LOW: 3,
        }

        items.sort(key=lambda x: (priority_order[x.priority], x.created_at))

        return items

    def assign_to_reviewer(self, item_id: str, reviewer_id: str) -> bool:
        """
        Assign an item to a reviewer.

        Args:
            item_id: Item to assign
            reviewer_id: Reviewer to assign to

        Returns:
            True if successful
        """
        item = self._queue.get(item_id)
        if not item:
            return False

        item.assigned_to = reviewer_id
        item.status = VerificationStatus.IN_PROGRESS

        # Update status index
        if item_id in self._by_status[VerificationStatus.PENDING]:
            self._by_status[VerificationStatus.PENDING].remove(item_id)
        self._by_status[VerificationStatus.IN_PROGRESS].append(item_id)

        logger.info(f"Assigned {item_id} to reviewer {reviewer_id}")

        return True

    def submit_verification(
        self,
        item_id: str,
        reviewer_id: str,
        verified: bool,
        corrected_data: Optional[Dict[str, Any]] = None,
        correction_notes: Optional[str] = None,
        fields_verified: Optional[List[str]] = None,
        fields_rejected: Optional[List[str]] = None,
    ) -> VerificationResult:
        """
        Submit a verification review.

        Args:
            item_id: Item being reviewed
            reviewer_id: Reviewer submitting
            verified: Whether extraction is verified correct
            corrected_data: Corrected values (if any)
            correction_notes: Reviewer's notes
            fields_verified: List of verified fields
            fields_rejected: List of rejected fields

        Returns:
            VerificationResult
        """
        item = self._queue.get(item_id)
        if not item:
            raise ValueError(f"Item not found: {item_id}")

        now = datetime.now(timezone.utc)

        # Determine status
        if not verified:
            new_status = VerificationStatus.REJECTED
        elif corrected_data:
            new_status = VerificationStatus.CORRECTED
            item.corrected_data = corrected_data
        else:
            new_status = VerificationStatus.APPROVED

        # Update item
        item.status = new_status
        item.reviewed_by = reviewer_id
        item.reviewed_at = now
        item.correction_notes = correction_notes

        # Update status index
        old_status = VerificationStatus.IN_PROGRESS
        if item_id in self._by_status[old_status]:
            self._by_status[old_status].remove(item_id)
        self._by_status[new_status].append(item_id)

        # Calculate review duration
        review_duration = int((now - item.created_at).total_seconds())

        # Build corrections list
        fields_corrected = []
        if corrected_data:
            for field_name, new_value in corrected_data.items():
                old_value = item.extracted_data.get(field_name)
                if old_value != new_value:
                    fields_corrected.append(
                        {
                            "field": field_name,
                            "old_value": old_value,
                            "new_value": new_value,
                        }
                    )

        result = VerificationResult(
            item_id=item_id,
            verified=verified,
            reviewer_id=reviewer_id,
            reviewed_at=now,
            fields_verified=fields_verified or [],
            fields_corrected=fields_corrected,
            fields_rejected=fields_rejected or [],
            reviewer_notes=correction_notes,
            review_duration_seconds=review_duration,
        )

        logger.info(
            f"Verification submitted for {item_id}: "
            f"status={new_status.value}, corrections={len(fields_corrected)}"
        )

        # Audit
        if self.audit:
            self.audit.log_verification_completed(
                user_id=item.user_id,
                document_id=item.document_id,
                verifier_id=reviewer_id,
                verified=verified,
                changes_made=fields_corrected,
            )

        return result

    def escalate_item(self, item_id: str, reason: str, escalated_by: str) -> bool:
        """
        Escalate item for higher-level review.

        Args:
            item_id: Item to escalate
            reason: Reason for escalation
            escalated_by: Who is escalating

        Returns:
            True if successful
        """
        item = self._queue.get(item_id)
        if not item:
            return False

        old_status = item.status
        item.status = VerificationStatus.ESCALATED
        item.priority = VerificationPriority.URGENT
        item.flagged_issues.append(f"Escalated: {reason}")

        # Update status index
        if item_id in self._by_status[old_status]:
            self._by_status[old_status].remove(item_id)
        self._by_status[VerificationStatus.ESCALATED].append(item_id)

        logger.warning(f"Escalated {item_id} by {escalated_by}: {reason}")

        return True

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        total = len(self._queue)

        stats = {
            "total_items": total,
            "by_status": {
                status.value: len(ids) for status, ids in self._by_status.items()
            },
            "by_priority": {},
            "avg_confidence": 0.0,
            "low_confidence_count": 0,
            "sla_breached": 0,
        }

        if total == 0:
            return stats

        now = datetime.now(timezone.utc)
        confidences = []

        for item in self._queue.values():
            # Count by priority
            priority_val = item.priority.value
            stats["by_priority"][priority_val] = (
                stats["by_priority"].get(priority_val, 0) + 1
            )

            # Track confidence
            confidences.append(item.extraction_confidence)
            if item.extraction_confidence < self.LOW_CONFIDENCE_THRESHOLD:
                stats["low_confidence_count"] += 1

            # Check SLA
            if item.status == VerificationStatus.PENDING:
                if item.expires_at and now > item.expires_at:
                    stats["sla_breached"] += 1

        stats["avg_confidence"] = sum(confidences) / len(confidences)

        return stats

    def _calculate_priority(self, confidence: float) -> VerificationPriority:
        """Calculate priority based on confidence."""
        if confidence < self.AUTO_FLAG_THRESHOLD:
            return VerificationPriority.URGENT
        elif confidence < self.LOW_CONFIDENCE_THRESHOLD:
            return VerificationPriority.HIGH
        elif confidence < self.HIGH_CONFIDENCE_THRESHOLD:
            return VerificationPriority.NORMAL
        else:
            return VerificationPriority.LOW

    def _auto_flag_issues(
        self, confidence: float, extracted_data: Dict[str, Any], document_type: str
    ) -> List[str]:
        """Automatically flag potential issues."""
        issues = []

        if confidence < self.AUTO_FLAG_THRESHOLD:
            issues.append(f"Very low confidence: {confidence:.2f}")

        # Check for missing critical fields based on document type
        critical_fields = {
            "lab_report": ["patient_name", "test_date", "results"],
            "prescription": ["patient_name", "medication", "dosage"],
            "discharge_summary": ["patient_name", "diagnosis", "discharge_date"],
        }

        required = critical_fields.get(document_type, [])
        for field in required:
            if field not in extracted_data or not extracted_data[field]:
                issues.append(f"Missing critical field: {field}")

        # Check for suspicious values (example patterns)
        for field, value in extracted_data.items():
            if isinstance(value, str):
                if "?" in value or "unclear" in value.lower():
                    issues.append(f"Uncertain value in {field}: {value}")

        return issues

    def process_expired_items(self) -> int:
        """Mark expired items and return count."""
        now = datetime.now(timezone.utc)
        expired_count = 0

        pending_ids = self._by_status[VerificationStatus.PENDING].copy()

        for item_id in pending_ids:
            item = self._queue.get(item_id)
            if item and item.expires_at and now > item.expires_at:
                item.status = VerificationStatus.EXPIRED
                self._by_status[VerificationStatus.PENDING].remove(item_id)
                self._by_status[VerificationStatus.EXPIRED].append(item_id)
                expired_count += 1
                logger.warning(f"Item {item_id} expired (SLA breached)")

        return expired_count

    def get_reviewer_stats(self, reviewer_id: str) -> Dict[str, Any]:
        """Get statistics for a specific reviewer."""
        stats = {
            "reviewer_id": reviewer_id,
            "reviews_completed": 0,
            "currently_assigned": 0,
            "avg_review_time_seconds": 0,
            "corrections_made": 0,
        }

        review_times = []

        for item in self._queue.values():
            if (
                item.assigned_to == reviewer_id
                and item.status == VerificationStatus.IN_PROGRESS
            ):
                stats["currently_assigned"] += 1

            if item.reviewed_by == reviewer_id:
                stats["reviews_completed"] += 1

                if item.corrected_data:
                    stats["corrections_made"] += 1

                if item.reviewed_at:
                    duration = (item.reviewed_at - item.created_at).total_seconds()
                    review_times.append(duration)

        if review_times:
            stats["avg_review_time_seconds"] = sum(review_times) / len(review_times)

        return stats


# Global verification queue instance
_verification_queue: Optional["VerificationQueue"] = None


def get_verification_queue() -> "VerificationQueue":
    """
    Get or create the global verification queue instance.

    Returns:
        VerificationQueue instance
    """
    global _verification_queue
    if _verification_queue is None:
        _verification_queue = VerificationQueue()
    return _verification_queue
