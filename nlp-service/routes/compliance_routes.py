"""
Compliance API Routes.

Endpoints for compliance and audit services:
- Audit trail access
- Human verification queue
- Disclaimer management
- PHI encryption utilities
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compliance", tags=["Compliance"])


# ============================================================================
# Request/Response Models
# ============================================================================


class VerificationSubmission(BaseModel):
    """Human verification submission request."""

    request_id: str
    verifier_id: str
    approved: bool
    corrections: Optional[dict] = None
    notes: Optional[str] = None


class VerificationRequestResponse(BaseModel):
    """Verification request response."""

    id: str
    document_id: str
    user_id: str
    status: str
    confidence_score: float
    flag_reasons: List[str]
    created_at: str
    expires_at: str


class AuditEventResponse(BaseModel):
    """Audit event response."""

    event_id: str
    timestamp: str
    event_type: str
    user_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: Optional[str]
    result: Optional[str]


class DisclaimerResponse(BaseModel):
    """Disclaimer response."""

    type: str
    title: str
    text: str
    severity: str
    short_text: Optional[str]


class WrapContentRequest(BaseModel):
    """Request to wrap content with disclaimers."""

    content: str
    content_type: str
    format: str = Field(
        default="text", description="Output format: text, markdown, html, whatsapp"
    )


class EncryptRequest(BaseModel):
    """Request to encrypt PHI fields."""

    data: dict
    fields: Optional[List[str]] = None


# ============================================================================
# Audit Trail Endpoints
# ============================================================================


@router.get("/audit/{document_id}", response_model=List[AuditEventResponse])
async def get_document_audit_trail(
    document_id: str, limit: int = Query(default=100, ge=1, le=500)
):
    """
    Get complete audit trail for a document.

    Returns all events related to the document including:
    - Upload
    - OCR processing
    - AI extraction
    - Human verification
    - Access events
    """
    try:
        from core.compliance.audit_logger import get_audit_service

        service = get_audit_service()
        events = service.get_document_audit_trail(document_id, limit=limit)

        return [
            AuditEventResponse(
                event_id=e.get("event_id", ""),
                timestamp=e.get("timestamp", ""),
                event_type=e.get("event_type", ""),
                user_id=e.get("user_id"),
                resource_type=e.get("resource_type"),
                resource_id=e.get("resource_id"),
                action=e.get("action"),
                result=e.get("result"),
            )
            for e in events
        ]

    except Exception as e:
        logger.error(f"Audit trail retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Audit service error")


@router.get("/audit-log/{user_id}")
async def get_user_activity(
    user_id: str,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Get user activity for compliance review.

    Returns all audit events for a specific user.
    """
    try:
        from core.compliance.audit_logger import get_audit_service

        service = get_audit_service()
        events = service.get_user_activity(user_id, days=days)

        return {
            "user_id": user_id,
            "days": days,
            "event_count": len(events),
            "events": events[:limit],
        }

    except Exception as e:
        logger.error(f"User activity retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Audit service error")


@router.get("/audit/phi-access")
async def get_phi_access_log(
    days: int = Query(default=30, ge=1, le=365), user_id: Optional[str] = None
):
    """
    Get PHI access log for HIPAA compliance.

    Returns all events where PHI was accessed.
    """
    try:
        from core.compliance.audit_logger import get_audit_service

        service = get_audit_service()

        # Get all events with PHI access
        events = service.get_user_activity(user_id, days=days) if user_id else []

        phi_events = [e for e in events if e.get("phi_accessed") == "true"]

        return {
            "phi_access_count": len(phi_events),
            "period_days": days,
            "events": phi_events,
        }

    except Exception as e:
        logger.error(f"PHI access log failed: {e}")
        raise HTTPException(status_code=500, detail="Audit service error")


# ============================================================================
# Human Verification Endpoints
# ============================================================================


@router.get("/verification-queue", response_model=List[VerificationRequestResponse])
async def get_pending_verifications(
    user_id: Optional[str] = None,
    priority: bool = Query(
        default=True, description="Sort by priority (most flags first)"
    ),
):
    """
    Get pending human verification requests.

    Returns extraction results awaiting human review.
    """
    try:
        from core.compliance.verification_queue import get_verification_queue

        queue = get_verification_queue()
        requests = queue.get_pending_requests(user_id=user_id)

        # Sort by priority if requested
        if priority:
            requests = sorted(requests, key=lambda r: len(r.flag_reasons), reverse=True)

        return [
            VerificationRequestResponse(
                id=r.id,
                document_id=r.document_id,
                user_id=r.user_id,
                status=r.status.value,
                confidence_score=r.confidence_score,
                flag_reasons=[f.value for f in r.flag_reasons],
                created_at=r.created_at.isoformat(),
                expires_at=r.expires_at.isoformat(),
            )
            for r in requests
        ]

    except Exception as e:
        logger.error(f"Pending verifications failed: {e}")
        raise HTTPException(status_code=500, detail="Verification service error")


@router.get("/verification/{request_id}")
async def get_verification_request(request_id: str):
    """Get details of a specific verification request."""
    try:
        from core.compliance.verification_queue import get_verification_queue

        queue = get_verification_queue()
        request = queue.get_request(request_id)

        if not request:
            raise HTTPException(
                status_code=404, detail="Verification request not found"
            )

        return {
            "id": request.id,
            "document_id": request.document_id,
            "user_id": request.user_id,
            "status": request.status.value,
            "extracted_data": request.extracted_data,
            "confidence_score": request.confidence_score,
            "flag_reasons": [f.value for f in request.flag_reasons],
            "created_at": request.created_at.isoformat(),
            "expires_at": request.expires_at.isoformat(),
            "verified_by": request.verified_by,
            "verified_at": (
                request.verified_at.isoformat() if request.verified_at else None
            ),
            "corrections": request.corrections,
            "notes": request.notes,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get verification request failed: {e}")
        raise HTTPException(status_code=500, detail="Verification service error")


@router.post("/verify")
async def submit_verification(submission: VerificationSubmission):
    """
    Submit human verification decision.

    Approves or rejects AI extraction with optional corrections.
    """
    try:
        from core.compliance.verification_queue import get_verification_queue

        queue = get_verification_queue()

        # Submit verification
        result = queue.submit_verification(
            request_id=submission.request_id,
            verifier_id=submission.verifier_id,
            approved=submission.approved,
            corrections=submission.corrections,
            notes=submission.notes,
        )

        return {
            "status": "submitted",
            "request_id": submission.request_id,
            "decision": "approved" if submission.approved else "rejected",
            "verified_at": (
                result.verified_at.isoformat() if result.verified_at else None
            ),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Verification submission failed: {e}")
        raise HTTPException(status_code=500, detail="Verification service error")


@router.get("/verification/stats")
async def get_verification_stats():
    """Get verification statistics."""
    try:
        from core.compliance.verification_queue import get_verification_queue

        queue = get_verification_queue()
        stats = queue.get_stats()

        return stats

    except Exception as e:
        logger.error(f"Verification stats failed: {e}")
        raise HTTPException(status_code=500, detail="Verification service error")


# ============================================================================
# Disclaimer Endpoints
# ============================================================================


@router.get("/disclaimer/{disclaimer_type}", response_model=DisclaimerResponse)
async def get_disclaimer(disclaimer_type: str):
    """
    Get a specific disclaimer by type.

    Types: general, patient_summary, lab_results, medication, extraction,
           health_advice, risk_assessment, weekly_summary
    """
    try:
        from core.compliance.disclaimer_service import get_disclaimer_service, DisclaimerType

        service = get_disclaimer_service()

        try:
            dtype = DisclaimerType(disclaimer_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid disclaimer type. Valid types: {[t.value for t in DisclaimerType]}",
            )

        disclaimer = service.get_disclaimer(dtype)

        return DisclaimerResponse(
            type=disclaimer.type.value,
            title=disclaimer.title,
            text=disclaimer.text,
            severity=disclaimer.severity.value,
            short_text=disclaimer.short_text,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get disclaimer failed: {e}")
        raise HTTPException(status_code=500, detail="Disclaimer service error")


@router.get("/disclaimers/for/{content_type}")
async def get_disclaimers_for_content(content_type: str):
    """
    Get all applicable disclaimers for a content type.

    Content types: summary, lab_report, medication, prescription, extraction,
                   health_advice, recommendation, risk_assessment, prediction
    """
    try:
        from core.compliance.disclaimer_service import get_disclaimer_service

        service = get_disclaimer_service()
        disclaimers = service.get_disclaimers_for_content(content_type)

        return {
            "content_type": content_type,
            "disclaimers": [
                {
                    "type": d.type.value,
                    "title": d.title,
                    "text": d.text,
                    "severity": d.severity.value,
                    "short_text": d.short_text,
                }
                for d in disclaimers
            ],
        }

    except Exception as e:
        logger.error(f"Get disclaimers failed: {e}")
        raise HTTPException(status_code=500, detail="Disclaimer service error")


@router.post("/disclaimers/wrap")
async def wrap_content_with_disclaimer(request: WrapContentRequest):
    """
    Wrap content with appropriate disclaimers.

    Formats: text, markdown, html, whatsapp
    """
    try:
        from core.compliance.disclaimer_service import get_disclaimer_service

        service = get_disclaimer_service()
        wrapped = service.wrap_with_disclaimer(
            content=request.content,
            content_type=request.content_type,
            format=request.format,
        )

        return {"wrapped_content": wrapped, "format": request.format}

    except Exception as e:
        logger.error(f"Wrap content failed: {e}")
        raise HTTPException(status_code=500, detail="Disclaimer service error")


# ============================================================================
# PHI Encryption Endpoints
# ============================================================================


@router.post("/encrypt")
async def encrypt_phi_fields(request: EncryptRequest):
    """
    Encrypt PHI fields in data.

    Automatically identifies and encrypts PHI fields like:
    patient_name, date_of_birth, ssn, medical_record_number, etc.
    """
    try:
        from core.compliance.encryption_service import get_encryption_service

        service = get_encryption_service()
        encrypted = service.encrypt_phi_fields(request.data, fields=request.fields)

        return {
            "encrypted_data": encrypted,
            "fields_encrypted": list(set(request.fields or service.PHI_FIELDS)),
        }

    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise HTTPException(status_code=500, detail="Encryption service error")


@router.post("/encryption/decrypt")
async def decrypt_phi_fields(request: EncryptRequest):
    """
    Decrypt PHI fields in data.

    Decrypts fields that were previously encrypted with ENC: prefix.
    """
    try:
        from core.compliance.encryption_service import get_encryption_service

        service = get_encryption_service()
        decrypted = service.decrypt_phi_fields(request.data, fields=request.fields)

        return {"decrypted_data": decrypted}

    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise HTTPException(status_code=500, detail="Encryption service error")


@router.post("/encryption/mask")
async def mask_phi_fields(
    request: EncryptRequest, show_last: int = Query(default=4, ge=0, le=10)
):
    """
    Mask PHI fields for display (shows only last N characters).

    Example: "John Smith" -> "********ith"
    """
    try:
        from core.compliance.encryption_service import get_encryption_service

        service = get_encryption_service()
        masked = service.mask_phi(request.data, show_last=show_last)

        return {"masked_data": masked}

    except Exception as e:
        logger.error(f"Masking failed: {e}")
        raise HTTPException(status_code=500, detail="Encryption service error")


# ============================================================================
# Consent Management Endpoints
# ============================================================================


@router.get("/consent/{user_id}")
async def get_user_consents(user_id: str):
    """Get all consent records for a user."""
    try:
        from core.compliance.consent_manager import get_consent_manager

        manager = get_consent_manager()
        consents = manager.get_all_consents(user_id)

        return {
            "user_id": user_id,
            "consents": [
                {
                    "type": c.consent_type.value,
                    "granted": c.granted,
                    "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    "method": c.method,
                }
                for c in consents
            ],
        }

    except Exception as e:
        logger.error(f"Get consents failed: {e}")
        raise HTTPException(status_code=500, detail="Consent service error")


@router.post("/consent/{user_id}/grant")
async def grant_consent(
    user_id: str,
    consent_type: str = Query(..., description="Type of consent to grant"),
    method: str = Query(default="explicit", description="How consent was obtained"),
):
    """Grant consent for a specific feature/purpose."""
    try:
        from core.compliance.consent_manager import get_consent_manager, ConsentType

        manager = get_consent_manager()

        try:
            ctype = ConsentType(consent_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid consent type. Valid types: {[t.value for t in ConsentType]}",
            )

        record = manager.grant_consent(user_id, ctype, method=method)

        return {
            "status": "granted",
            "consent_type": consent_type,
            "granted_at": record.granted_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grant consent failed: {e}")
        raise HTTPException(status_code=500, detail="Consent service error")


@router.post("/consent/{user_id}/withdraw")
async def withdraw_consent(
    user_id: str,
    consent_type: str = Query(..., description="Type of consent to withdraw"),
):
    """Withdraw previously granted consent."""
    try:
        from core.compliance.consent_manager import get_consent_manager, ConsentType

        manager = get_consent_manager()

        try:
            ctype = ConsentType(consent_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid consent type. Valid types: {[t.value for t in ConsentType]}",
            )

        manager.withdraw_consent(user_id, ctype)

        return {"status": "withdrawn", "consent_type": consent_type}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Withdraw consent failed: {e}")
        raise HTTPException(status_code=500, detail="Consent service error")


# ============================================================================
# Data Retention Endpoints
# ============================================================================


@router.get("/retention/policy")
async def get_retention_policy():
    """Get current data retention policy."""
    try:
        from core.compliance.data_retention import get_retention_service

        service = get_retention_service()
        policy = service.get_policy()

        return {
            "default_retention_days": policy.default_retention_days,
            "phi_retention_years": policy.default_retention_days // 365,
            "audit_retention_years": 6,  # HIPAA requirement
            "policies_by_type": policy.policies_by_type,
        }

    except Exception as e:
        logger.error(f"Get retention policy failed: {e}")
        raise HTTPException(status_code=500, detail="Retention service error")


@router.get("/retention/check/{document_id}")
async def check_retention_status(document_id: str):
    """Check retention status of a document."""
    try:
        from core.compliance.data_retention import get_retention_service

        service = get_retention_service()
        status = service.check_document_retention(document_id)

        return status

    except Exception as e:
        logger.error(f"Check retention failed: {e}")
        raise HTTPException(status_code=500, detail="Retention service error")

@router.get("/gdpr/export/{user_id}")
async def export_user_data(user_id: str):
    """Export all user data for GDPR compliance."""
    try:
        from core.compliance.consent_manager import get_consent_manager
        manager = get_consent_manager()
        report = manager.export_consent_report(user_id)
        return report
    except Exception as e:
        logger.error(f"GDPR export failed: {e}")
        raise HTTPException(status_code=500, detail="Compliance service error")
