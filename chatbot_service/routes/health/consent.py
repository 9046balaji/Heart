"""
Consent Management Routes
=========================
User consent tracking for data processing, sharing, and analytics.
Endpoints:
    GET    /consent/{user_id}
    PUT    /consent/{user_id}
    DELETE /consent/{user_id}/{consent_type}
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("consent")

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory consent store
# ---------------------------------------------------------------------------

_consent_store: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Default consent template
# ---------------------------------------------------------------------------

DEFAULT_CONSENTS = {
    "data_processing": {
        "granted": False,
        "description": "Allow processing of health data for AI-powered analysis",
        "required": True,
        "updated_at": None,
    },
    "data_sharing_doctors": {
        "granted": False,
        "description": "Share health data with your healthcare providers",
        "required": False,
        "updated_at": None,
    },
    "data_sharing_research": {
        "granted": False,
        "description": "Allow anonymized data to be used for medical research",
        "required": False,
        "updated_at": None,
    },
    "analytics": {
        "granted": False,
        "description": "Allow anonymous usage analytics to improve the service",
        "required": False,
        "updated_at": None,
    },
    "notifications": {
        "granted": True,
        "description": "Receive health-related notifications and reminders",
        "required": False,
        "updated_at": None,
    },
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ConsentStatus(BaseModel):
    user_id: str
    consents: Dict[str, Any]
    last_updated: Optional[str] = None


class ConsentUpdate(BaseModel):
    consents: Dict[str, bool]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_consents(user_id: str) -> dict:
    if user_id not in _consent_store:
        import copy
        _consent_store[user_id] = copy.deepcopy(DEFAULT_CONSENTS)
    return _consent_store[user_id]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{user_id}", response_model=ConsentStatus)
async def get_consent(user_id: str):
    """Get all consent statuses for a user."""
    consents = _get_user_consents(user_id)
    return ConsentStatus(
        user_id=user_id,
        consents=consents,
        last_updated=datetime.utcnow().isoformat() + "Z",
    )


@router.put("/{user_id}", response_model=ConsentStatus)
async def update_consent(user_id: str, update: ConsentUpdate):
    """Update consent statuses for a user."""
    consents = _get_user_consents(user_id)
    now = datetime.utcnow().isoformat() + "Z"

    for consent_type, granted in update.consents.items():
        if consent_type in consents:
            consents[consent_type]["granted"] = granted
            consents[consent_type]["updated_at"] = now
        else:
            consents[consent_type] = {
                "granted": granted,
                "description": f"Custom consent: {consent_type}",
                "required": False,
                "updated_at": now,
            }

    logger.info(f"Consent updated for user {user_id}: {list(update.consents.keys())}")

    return ConsentStatus(
        user_id=user_id,
        consents=consents,
        last_updated=now,
    )


@router.delete("/{user_id}/{consent_type}")
async def revoke_consent(user_id: str, consent_type: str):
    """Revoke a specific consent type."""
    consents = _get_user_consents(user_id)

    if consent_type not in consents:
        raise HTTPException(status_code=404, detail=f"Consent type '{consent_type}' not found")

    if consents[consent_type].get("required"):
        raise HTTPException(status_code=400, detail=f"Cannot revoke required consent: {consent_type}")

    consents[consent_type]["granted"] = False
    consents[consent_type]["updated_at"] = datetime.utcnow().isoformat() + "Z"

    logger.info(f"Consent revoked for user {user_id}: {consent_type}")
    return {"message": f"Consent '{consent_type}' revoked successfully", "user_id": user_id}
