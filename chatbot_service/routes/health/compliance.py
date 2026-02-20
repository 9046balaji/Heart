"""
Compliance Routes
=================
HIPAA compliance endpoints: disclaimers, PHI encryption, content verification.
Leverages existing EncryptionService for PHI operations.
Endpoints:
    GET  /compliance/disclaimer/{type}
    POST /compliance/encrypt-phi
    GET  /compliance/verification/pending
    POST /compliance/verification/submit
"""

import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("compliance")

router = APIRouter()


# ---------------------------------------------------------------------------
# Load existing encryption service
# ---------------------------------------------------------------------------

_encryption_service = None

try:
    from core.services.encryption_service import EncryptionService
    import os
    key = os.getenv("ENCRYPTION_MASTER_KEY")
    if key and len(key) >= 32:
        _encryption_service = EncryptionService(master_key=key)
        logger.info("EncryptionService loaded for PHI encryption")
    else:
        logger.info("ENCRYPTION_MASTER_KEY not set or too short; PHI encryption unavailable")
except Exception as e:
    logger.info(f"EncryptionService not available: {e}")


# ---------------------------------------------------------------------------
# In-memory verification queue
# ---------------------------------------------------------------------------

_verification_queue: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Disclaimers database
# ---------------------------------------------------------------------------

DISCLAIMERS = {
    "general": {
        "type": "general",
        "title": "General Health Disclaimer",
        "text": (
            "This application provides health information for educational purposes only. "
            "It is not intended as medical advice, diagnosis, or treatment. Always consult "
            "a qualified healthcare provider for medical decisions. If you are experiencing "
            "a medical emergency, call 911 or your local emergency number immediately."
        ),
        "version": "1.0",
    },
    "prediction": {
        "type": "prediction",
        "title": "Heart Disease Prediction Disclaimer",
        "text": (
            "The heart disease risk prediction uses a machine learning model trained on "
            "clinical data. Results are probabilistic and should NOT be used as the sole "
            "basis for clinical decisions. This tool is intended to supplement, not replace, "
            "professional medical evaluation. Individual results may vary based on factors "
            "not captured by the model."
        ),
        "version": "1.0",
    },
    "ai_chat": {
        "type": "ai_chat",
        "title": "AI Chat Disclaimer",
        "text": (
            "AI-generated responses are based on general medical knowledge and may not "
            "account for your specific medical history, medications, or conditions. "
            "Never disregard professional medical advice or delay seeking it because of "
            "information provided by this AI assistant."
        ),
        "version": "1.0",
    },
    "data_privacy": {
        "type": "data_privacy",
        "title": "Data Privacy Notice",
        "text": (
            "Your health data is encrypted at rest and in transit. We follow HIPAA-compliant "
            "practices for data handling. You can request data export or deletion at any time "
            "through the GDPR compliance features."
        ),
        "version": "1.0",
    },
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class EncryptPHIRequest(BaseModel):
    data: Any


class EncryptPHIResponse(BaseModel):
    encrypted: str
    algorithm: str
    timestamp: str


class VerificationItem(BaseModel):
    id: str
    content: str
    content_type: str
    submitted_by: Optional[str] = None
    submitted_at: str
    status: str = "pending"


class VerificationSubmitRequest(BaseModel):
    item_id: str
    verified: bool
    notes: Optional[str] = None


class VerificationSubmitResponse(BaseModel):
    item_id: str
    verified: bool
    reviewed_at: str
    reviewer_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/disclaimer/{disclaimer_type}")
async def get_disclaimer(disclaimer_type: str):
    """Get a specific type of disclaimer."""
    if disclaimer_type not in DISCLAIMERS:
        raise HTTPException(
            status_code=404,
            detail=f"Disclaimer type '{disclaimer_type}' not found. Available: {list(DISCLAIMERS.keys())}",
        )
    return DISCLAIMERS[disclaimer_type]


@router.post("/encrypt-phi", response_model=EncryptPHIResponse)
async def encrypt_phi(request: EncryptPHIRequest):
    """Encrypt sensitive PHI data using AES-256-GCM."""
    if request.data is None:
        raise HTTPException(status_code=400, detail="Data is required")

    if _encryption_service:
        try:
            import json
            data_str = json.dumps(request.data) if not isinstance(request.data, str) else request.data
            encrypted = _encryption_service.encrypt(data_str)
            return EncryptPHIResponse(
                encrypted=encrypted,
                algorithm=_encryption_service.algorithm,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
        except Exception as e:
            logger.error(f"PHI encryption failed: {e}")
            raise HTTPException(status_code=500, detail="Encryption failed")
    else:
        # Fallback: base64 encoding (NOT real encryption — for development only)
        import base64
        import json
        data_str = json.dumps(request.data) if not isinstance(request.data, str) else request.data
        encoded = base64.b64encode(data_str.encode()).decode()
        return EncryptPHIResponse(
            encrypted=encoded,
            algorithm="base64-dev-only",
            timestamp=datetime.utcnow().isoformat() + "Z",
        )


@router.get("/verification/pending", response_model=List[VerificationItem])
async def get_pending_verifications():
    """Get pending content verification items."""
    return [VerificationItem(**item) for item in _verification_queue if item.get("status") == "pending"]


@router.post("/verification/submit", response_model=VerificationSubmitResponse)
async def submit_verification(request: VerificationSubmitRequest):
    """Submit a verification decision for a content item."""
    # Find the item in queue
    for item in _verification_queue:
        if item["id"] == request.item_id:
            item["status"] = "verified" if request.verified else "rejected"
            item["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
            item["reviewer_notes"] = request.notes
            return VerificationSubmitResponse(
                item_id=request.item_id,
                verified=request.verified,
                reviewed_at=item["reviewed_at"],
                reviewer_notes=request.notes,
            )

    raise HTTPException(status_code=404, detail=f"Verification item {request.item_id} not found")
