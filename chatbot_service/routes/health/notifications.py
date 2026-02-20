"""
Notifications Routes
====================
Multi-channel notification delivery (WhatsApp, Email, Push).
Endpoints:
    POST /notifications/whatsapp
    POST /notifications/email
    POST /notifications/register-device
    POST /notifications/push
"""

import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("notifications")

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory device registry
# ---------------------------------------------------------------------------

_device_registry: Dict[str, List[Dict]] = {}  # user_id -> [devices]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class WhatsAppRequest(BaseModel):
    to: str = Field(..., description="Phone number in E.164 format")
    message: str
    template: Optional[str] = None


class EmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    html: Optional[bool] = False


class DeviceRegistration(BaseModel):
    user_id: str
    device_token: str
    platform: str = Field(..., description="ios, android, or web")


class PushRequest(BaseModel):
    user_id: str
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None


class NotificationResponse(BaseModel):
    id: str
    status: str
    channel: str
    sent_at: str
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/whatsapp", response_model=NotificationResponse)
async def send_whatsapp(request: WhatsAppRequest):
    """Send a WhatsApp notification via Twilio/WhatsApp Business API."""
    notification_id = str(uuid.uuid4())

    # In production, integrate with Twilio WhatsApp API
    logger.info(f"WhatsApp notification queued to {request.to}: {request.message[:50]}...")

    return NotificationResponse(
        id=notification_id,
        status="queued",
        channel="whatsapp",
        sent_at=datetime.utcnow().isoformat() + "Z",
        message="WhatsApp notification queued for delivery",
    )


@router.post("/email", response_model=NotificationResponse)
async def send_email(request: EmailRequest):
    """Send an email notification."""
    notification_id = str(uuid.uuid4())

    # In production, integrate with SMTP / SendGrid / SES
    logger.info(f"Email notification queued to {request.to}: {request.subject}")

    return NotificationResponse(
        id=notification_id,
        status="queued",
        channel="email",
        sent_at=datetime.utcnow().isoformat() + "Z",
        message="Email notification queued for delivery",
    )


@router.post("/register-device")
async def register_device(request: DeviceRegistration):
    """Register a device for push notifications."""
    if request.platform not in ("ios", "android", "web"):
        raise HTTPException(status_code=400, detail="Platform must be ios, android, or web")

    if request.user_id not in _device_registry:
        _device_registry[request.user_id] = []

    # Check for duplicate token
    existing_tokens = [d["device_token"] for d in _device_registry[request.user_id]]
    if request.device_token not in existing_tokens:
        _device_registry[request.user_id].append({
            "device_token": request.device_token,
            "platform": request.platform,
            "registered_at": datetime.utcnow().isoformat() + "Z",
        })

    logger.info(f"Device registered for user {request.user_id}: {request.platform}")
    return {"message": "Device registered successfully", "platform": request.platform}


@router.post("/push", response_model=NotificationResponse)
async def send_push(request: PushRequest):
    """Send a push notification to registered devices."""
    notification_id = str(uuid.uuid4())

    devices = _device_registry.get(request.user_id, [])
    if not devices:
        logger.warning(f"No devices registered for user {request.user_id}")

    # In production, integrate with FCM / APNs
    logger.info(f"Push notification queued for user {request.user_id}: {request.title}")

    return NotificationResponse(
        id=notification_id,
        status="queued",
        channel="push",
        sent_at=datetime.utcnow().isoformat() + "Z",
        message=f"Push notification queued for {len(devices)} device(s)",
    )
