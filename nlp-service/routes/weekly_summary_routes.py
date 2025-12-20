"""
Weekly Summary & Consent API Routes.

FastAPI routes for weekly health summary preferences, consent management,
and manual summary triggers.
"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/weekly-summary", tags=["Weekly Summary"])


# ==================== Request/Response Models ====================


class DeliveryPreference(BaseModel):
    """User's delivery preference for weekly summaries."""

    channel: str = Field(
        ..., description="Delivery channel: whatsapp, email, sms, push"
    )
    enabled: bool = True
    destination: Optional[str] = Field(None, description="Phone number or email")


class SummaryPreferencesRequest(BaseModel):
    """Request to update summary preferences."""

    enabled: bool = Field(True, description="Enable/disable weekly summaries")
    delivery_channels: List[DeliveryPreference]
    preferred_day: int = Field(
        0, ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)"
    )
    preferred_time: str = Field("09:00", description="Time in HH:MM format")
    timezone: str = Field("UTC", description="User's timezone")

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "delivery_channels": [
                    {
                        "channel": "whatsapp",
                        "enabled": True,
                        "destination": "+1234567890",
                    },
                    {
                        "channel": "email",
                        "enabled": True,
                        "destination": "user@example.com",
                    },
                ],
                "preferred_day": 0,
                "preferred_time": "09:00",
                "timezone": "America/New_York",
            }
        }


class SummaryPreferencesResponse(BaseModel):
    """Current summary preferences."""

    user_id: str
    enabled: bool
    delivery_channels: List[DeliveryPreference]
    preferred_day: int
    preferred_time: str
    timezone: str
    last_summary_at: Optional[datetime] = None
    next_summary_at: Optional[datetime] = None


class ManualSummaryRequest(BaseModel):
    """Request to manually trigger a summary."""

    channels: Optional[List[str]] = Field(None, description="Specific channels to use")

    class Config:
        json_schema_extra = {"example": {"channels": ["whatsapp"]}}


class SummaryDeliveryResult(BaseModel):
    """Result of summary delivery."""

    channel: str
    status: str  # sent, delivered, failed
    message_id: Optional[str] = None
    error: Optional[str] = None
    delivered_at: Optional[datetime] = None


class ManualSummaryResponse(BaseModel):
    """Response for manual summary trigger."""

    user_id: str
    summary_id: str
    message_preview: str
    delivery_results: List[SummaryDeliveryResult]
    generated_at: datetime


# ==================== Consent Models ====================


class ConsentRequest(BaseModel):
    """Request to grant consent."""

    consent_type: str = Field(..., description="Type of consent")
    granted: bool = Field(..., description="Whether consent is granted")

    class Config:
        json_schema_extra = {
            "example": {"consent_type": "weekly_summary_whatsapp", "granted": True}
        }


class ConsentRecord(BaseModel):
    """Consent record."""

    consent_type: str
    status: str  # granted, denied, withdrawn
    granted_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class ConsentStatusResponse(BaseModel):
    """User's consent status."""

    user_id: str
    consents: List[ConsentRecord]
    can_receive_summaries: bool
    missing_required_consents: List[str]


# ==================== Routes - Summary Preferences ====================


@router.get(
    "/preferences",
    response_model=SummaryPreferencesResponse,
    summary="Get Summary Preferences",
    description="Get user's weekly summary delivery preferences.",
)
async def get_preferences(user_id: str = Query(..., description="User ID")):
    """Get user's weekly summary preferences."""
    # Mock response (in production: retrieve from database)
    return SummaryPreferencesResponse(
        user_id=user_id,
        enabled=True,
        delivery_channels=[
            DeliveryPreference(
                channel="whatsapp", enabled=True, destination="+1234567890"
            ),
            DeliveryPreference(
                channel="email", enabled=True, destination="user@example.com"
            ),
        ],
        preferred_day=0,  # Monday
        preferred_time="09:00",
        timezone="America/New_York",
        last_summary_at=datetime(2024, 1, 8, 9, 0, 0),
        next_summary_at=datetime(2024, 1, 15, 9, 0, 0),
    )


@router.put(
    "/preferences",
    response_model=SummaryPreferencesResponse,
    summary="Update Summary Preferences",
    description="Update user's weekly summary delivery preferences.",
)
async def update_preferences(
    request: SummaryPreferencesRequest, user_id: str = Query(..., description="User ID")
):
    """Update weekly summary preferences."""
    logger.info(f"Updating preferences for user {user_id}: enabled={request.enabled}")

    # In production: save to database and update scheduler

    return SummaryPreferencesResponse(
        user_id=user_id,
        enabled=request.enabled,
        delivery_channels=request.delivery_channels,
        preferred_day=request.preferred_day,
        preferred_time=request.preferred_time,
        timezone=request.timezone,
        next_summary_at=datetime(2024, 1, 15, 9, 0, 0) if request.enabled else None,
    )


@router.post(
    "/trigger",
    response_model=ManualSummaryResponse,
    summary="Trigger Manual Summary",
    description="Manually trigger a weekly summary delivery.",
)
async def trigger_summary(
    request: ManualSummaryRequest = Body(default=None),
    user_id: str = Query(..., description="User ID"),
):
    """
    Manually trigger a weekly health summary.

    This will:
    1. Aggregate the past 7 days of health data
    2. Generate a formatted summary
    3. Deliver via specified channels
    """
    import uuid

    summary_id = f"sum_{uuid.uuid4().hex[:8]}"

    # Mock delivery results
    delivery_results = [
        SummaryDeliveryResult(
            channel="whatsapp",
            status="sent",
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            delivered_at=datetime.utcnow(),
        )
    ]

    return ManualSummaryResponse(
        user_id=user_id,
        summary_id=summary_id,
        message_preview=(
            "📊 *Weekly Health Summary*\n\n"
            "Hi! Here's your health report for Jan 8-15, 2024:\n\n"
            "❤️ Heart Rate: 72 bpm avg\n"
            "👣 Steps: 8,500 avg\n"
            "💊 Medications: 95% compliance\n\n"
            "_Reply STOP to unsubscribe_"
        ),
        delivery_results=delivery_results,
        generated_at=datetime.utcnow(),
    )


@router.delete(
    "/unsubscribe",
    summary="Unsubscribe from Summaries",
    description="Unsubscribe from all weekly summary deliveries.",
)
async def unsubscribe(
    user_id: str = Query(..., description="User ID"),
    channel: Optional[str] = Query(
        None, description="Specific channel to unsubscribe from"
    ),
):
    """Unsubscribe from weekly summaries."""
    logger.info(f"Unsubscribing user {user_id} from {channel or 'all channels'}")

    return {
        "status": "unsubscribed",
        "user_id": user_id,
        "channel": channel or "all",
        "message": "You have been unsubscribed from weekly health summaries.",
    }


# ==================== Routes - Consent Management ====================

consent_router = APIRouter(prefix="/api/consent", tags=["Consent Management"])


@consent_router.get(
    "/status",
    response_model=ConsentStatusResponse,
    summary="Get Consent Status",
    description="Get user's current consent status for all features.",
)
async def get_consent_status(user_id: str = Query(..., description="User ID")):
    """Get comprehensive consent status."""
    # Mock response
    consents = [
        ConsentRecord(
            consent_type="health_data_processing",
            status="granted",
            granted_at=datetime(2024, 1, 1, 10, 0, 0),
            expires_at=datetime(2025, 1, 1, 10, 0, 0),
        ),
        ConsentRecord(
            consent_type="weekly_summary_whatsapp",
            status="granted",
            granted_at=datetime(2024, 1, 1, 10, 0, 0),
        ),
        ConsentRecord(
            consent_type="weekly_summary_email",
            status="granted",
            granted_at=datetime(2024, 1, 1, 10, 0, 0),
        ),
        ConsentRecord(
            consent_type="ai_analysis",
            status="granted",
            granted_at=datetime(2024, 1, 1, 10, 0, 0),
        ),
    ]

    # Check for missing required consents
    required = ["health_data_processing", "privacy_policy"]
    granted_types = [c.consent_type for c in consents if c.status == "granted"]
    missing = [r for r in required if r not in granted_types]

    return ConsentStatusResponse(
        user_id=user_id,
        consents=consents,
        can_receive_summaries=len(missing) == 0,
        missing_required_consents=missing,
    )


@consent_router.post(
    "/grant",
    summary="Grant Consent",
    description="Grant consent for a specific feature.",
)
async def grant_consent(
    request: ConsentRequest, user_id: str = Query(..., description="User ID")
):
    """Grant consent for a feature."""
    logger.info(f"Consent granted: {user_id} -> {request.consent_type}")

    return {
        "status": "success",
        "user_id": user_id,
        "consent_type": request.consent_type,
        "granted": request.granted,
        "granted_at": datetime.utcnow().isoformat(),
    }


@consent_router.post(
    "/withdraw",
    summary="Withdraw Consent",
    description="Withdraw previously granted consent.",
)
async def withdraw_consent(
    consent_type: str = Query(..., description="Type of consent to withdraw"),
    user_id: str = Query(..., description="User ID"),
):
    """Withdraw consent for a feature."""
    logger.info(f"Consent withdrawn: {user_id} -> {consent_type}")

    return {
        "status": "success",
        "user_id": user_id,
        "consent_type": consent_type,
        "withdrawn_at": datetime.utcnow().isoformat(),
        "message": "Your consent has been withdrawn. This may affect some features.",
    }


@consent_router.get(
    "/export",
    summary="Export Consent Report",
    description="Export comprehensive consent report (GDPR compliance).",
)
async def export_consent_report(user_id: str = Query(..., description="User ID")):
    """Export consent report for GDPR Article 15 compliance."""
    # In production: generate comprehensive report
    return {
        "user_id": user_id,
        "export_date": datetime.utcnow().isoformat(),
        "report_type": "consent_record",
        "consents": [
            {
                "type": "health_data_processing",
                "status": "granted",
                "granted_at": "2024-01-01T10:00:00Z",
                "purpose": "To provide personalized health insights",
                "scope": "Health metrics, vitals, and wellness data",
            }
        ],
        "data_retained": {
            "health_data": "6 years (HIPAA requirement)",
            "audit_logs": "6 years (HIPAA requirement)",
            "weekly_summaries": "1 year",
        },
    }


@consent_router.get(
    "/required",
    summary="Get Required Consents",
    description="Get list of required consents for specific features.",
)
async def get_required_consents(
    feature: str = Query(
        ...,
        description="Feature to check (weekly_summary, document_scanning, ai_analysis)",
    )
):
    """Get required consents for a feature."""
    required_map = {
        "weekly_summary": [
            "health_data_processing",
            "privacy_policy",
            # Plus at least one delivery channel
        ],
        "document_scanning": ["document_scanning", "ai_analysis", "privacy_policy"],
        "ai_analysis": ["ai_analysis", "health_data_processing", "privacy_policy"],
    }

    if feature not in required_map:
        raise HTTPException(status_code=400, detail=f"Unknown feature: {feature}")

    return {
        "feature": feature,
        "required_consents": required_map[feature],
        "description": f"These consents are required to use {feature}",
    }


# ==================== Webhook Routes ====================

webhook_router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@webhook_router.post(
    "/twilio/whatsapp",
    summary="Twilio WhatsApp Webhook",
    description="Handle incoming WhatsApp messages and status updates from Twilio.",
)
async def twilio_whatsapp_webhook(body: dict = Body(...)):
    """
    Handle Twilio WhatsApp webhooks.

    Processes:
    - Message delivery status updates
    - Incoming user messages (STOP, HELP, etc.)
    """
    message_sid = body.get("MessageSid")
    status = body.get("MessageStatus") or body.get("SmsStatus")
    from_number = body.get("From", "").replace("whatsapp:", "")
    message_body = body.get("Body", "").strip().lower()

    logger.info(f"WhatsApp webhook: {message_sid}, status={status}, from={from_number}")

    # Handle opt-out
    if message_body in ["stop", "unsubscribe", "cancel"]:
        logger.info(f"Opt-out request from {from_number}")
        return {"action": "opt_out", "user": from_number}

    # Handle help
    if message_body == "help":
        logger.info(f"Help request from {from_number}")
        return {"action": "send_help", "user": from_number}

    # Handle summary request
    if message_body == "summary":
        logger.info(f"Summary request from {from_number}")
        return {"action": "send_summary", "user": from_number}

    return {"status": "received"}


@webhook_router.post(
    "/sendgrid/email",
    summary="SendGrid Email Webhook",
    description="Handle email delivery events from SendGrid.",
)
async def sendgrid_webhook(events: List[dict] = Body(...)):
    """Handle SendGrid email webhooks."""
    for event in events:
        event_type = event.get("event")
        email = event.get("email")

        logger.info(f"SendGrid event: {event_type} for {email}")

        if event_type == "bounce":
            logger.warning(f"Email bounced for {email}")
        elif event_type == "unsubscribe":
            logger.info(f"Email unsubscribe: {email}")

    return {"status": "processed", "events_count": len(events)}


# Note: consent_router is exported and mounted by main.py directly, not included here
# to avoid double mounting with incorrect prefix
