"""
Notifications API Routes.

FastAPI routes for multi-channel notification management:
- WhatsApp messaging
- Email notifications
- Push notifications
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ==================== Request/Response Models ====================


class WhatsAppMessageRequest(BaseModel):
    """Request to send WhatsApp message."""

    phone_number: str = Field(..., description="Phone number with country code")
    message: str = Field(..., max_length=4096)
    template_name: Optional[str] = Field(None, description="Pre-approved template name")
    template_params: Optional[Dict[str, str]] = Field(
        None, description="Template parameters"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "phone_number": "+1234567890",
                "message": "Your weekly health summary is ready!",
                "template_name": None,
                "template_params": None,
            }
        }


class EmailMessageRequest(BaseModel):
    """Request to send email."""

    to_email: str
    subject: str = Field(..., max_length=200)
    body_text: str = Field(..., description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    template_name: Optional[str] = Field(None)
    template_data: Optional[Dict[str, Any]] = Field(None)

    class Config:
        json_schema_extra = {
            "example": {
                "to_email": "patient@example.com",
                "subject": "Your Weekly Health Summary",
                "body_text": "Here is your weekly health summary...",
                "body_html": "<h1>Weekly Health Summary</h1>...",
            }
        }


class PushNotificationRequest(BaseModel):
    """Request to send push notification."""

    device_token: str = Field(..., description="Device push token")
    title: str = Field(..., max_length=100)
    body: str = Field(..., max_length=500)
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data payload")
    priority: str = Field("normal", description="Priority: normal or high")

    class Config:
        json_schema_extra = {
            "example": {
                "device_token": "fcm_token_xxx",
                "title": "Medication Reminder",
                "body": "Time to take your evening medications",
                "data": {"action": "open_medications"},
                "priority": "high",
            }
        }


class BulkNotificationRequest(BaseModel):
    """Request for bulk notifications."""

    user_ids: List[str]
    channels: List[str] = Field(
        default=["push"], description="Channels: push, email, whatsapp"
    )
    title: str
    message: str
    template_name: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    priority: str = "normal"


class NotificationResponse(BaseModel):
    """Generic notification response."""

    status: str
    message_id: Optional[str] = None
    channel: str
    recipient: str
    sent_at: datetime
    error: Optional[str] = None


class DeliveryStatusResponse(BaseModel):
    """Notification delivery status."""

    message_id: str
    channel: str
    status: str
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error: Optional[str] = None


# ==================== WhatsApp Endpoints ====================


@router.post("/whatsapp/send", response_model=NotificationResponse)
async def send_whatsapp(request: WhatsAppMessageRequest):
    """
    Send a WhatsApp message to a phone number.

    Supports both free-form messages and pre-approved templates.
    """
    try:
        from notifications import WhatsAppService

        service = WhatsAppService()

        if request.template_name:
            result = await service.send_template(
                phone_number=request.phone_number,
                template_name=request.template_name,
                params=request.template_params or {},
            )
        else:
            result = await service.send_message(
                phone_number=request.phone_number,
                message=request.message,
            )

        return NotificationResponse(
            status=(
                result.status.value
                if hasattr(result.status, "value")
                else str(result.status)
            ),
            message_id=result.message_id,
            channel="whatsapp",
            recipient=request.phone_number,
            sent_at=datetime.utcnow(),
            error=result.error,
        )

    except ImportError:
        raise HTTPException(status_code=503, detail="WhatsApp service not available")
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whatsapp/templates")
async def list_whatsapp_templates():
    """
    List available WhatsApp message templates.
    """
    try:
        from notifications import WhatsAppService

        service = WhatsAppService()
        templates = await service.get_templates()

        return {
            "templates": templates,
            "count": len(templates),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="WhatsApp service not available")
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Email Endpoints ====================


@router.post("/email/send", response_model=NotificationResponse)
async def send_email(request: EmailMessageRequest):
    """
    Send an email notification.

    Supports both plain text and HTML content, as well as templates.
    """
    try:
        from notifications import EmailService, EmailMessage

        service = EmailService()

        message = EmailMessage(
            to_email=request.to_email,
            subject=request.subject,
            body_text=request.body_text,
            body_html=request.body_html,
        )

        if request.template_name:
            result = await service.send_template(
                to_email=request.to_email,
                template_name=request.template_name,
                data=request.template_data or {},
            )
        else:
            result = await service.send(message)

        return NotificationResponse(
            status=(
                result.status.value
                if hasattr(result.status, "value")
                else str(result.status)
            ),
            message_id=result.message_id,
            channel="email",
            recipient=request.to_email,
            sent_at=datetime.utcnow(),
            error=result.error,
        )

    except ImportError:
        raise HTTPException(status_code=503, detail="Email service not available")
    except Exception as e:
        logger.error(f"Email send error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email/templates")
async def list_email_templates():
    """
    List available email templates.
    """
    try:
        from notifications import EmailService

        service = EmailService()
        templates = await service.get_templates()

        return {
            "templates": templates,
            "count": len(templates),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="Email service not available")
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Push Notification Endpoints ====================


@router.post("/push/send", response_model=NotificationResponse)
async def send_push(request: PushNotificationRequest):
    """
    Send a push notification to a device.
    """
    try:
        from notifications import (
            PushNotificationService,
            PushNotification,
            PushPriority,
        )

        service = PushNotificationService()

        notification = PushNotification(
            device_token=request.device_token,
            title=request.title,
            body=request.body,
            data=request.data,
            priority=PushPriority(request.priority),
        )

        result = await service.send(notification)

        return NotificationResponse(
            status="sent" if result.success else "failed",
            message_id=result.message_id,
            channel="push",
            recipient=request.device_token[:20] + "...",  # Truncate for privacy
            sent_at=datetime.utcnow(),
            error=result.error,
        )

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Push notification service not available"
        )
    except Exception as e:
        logger.error(f"Push send error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/register-device")
async def register_device(
    user_id: str,
    device_token: str = Body(..., embed=True),
    platform: str = Body("android", embed=True, description="ios or android"),
):
    """
    Register a device for push notifications.
    """
    try:
        from notifications import PushNotificationService

        service = PushNotificationService()
        await service.register_device(
            user_id=user_id,
            device_token=device_token,
            platform=platform,
        )

        return {
            "status": "registered",
            "user_id": user_id,
            "platform": platform,
            "registered_at": datetime.utcnow().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="Push service not available")
    except Exception as e:
        logger.error(f"Device registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Bulk & Status Endpoints ====================


@router.post("/bulk/send")
async def send_bulk_notifications(request: BulkNotificationRequest):
    """
    Send notifications to multiple users across multiple channels.
    """
    results = []

    for user_id in request.user_ids:
        for channel in request.channels:
            try:
                if channel == "push":

                    # Would look up device token by user_id
                    result = {
                        "user_id": user_id,
                        "channel": channel,
                        "status": "queued",
                    }
                elif channel == "email":

                    result = {
                        "user_id": user_id,
                        "channel": channel,
                        "status": "queued",
                    }
                elif channel == "whatsapp":

                    result = {
                        "user_id": user_id,
                        "channel": channel,
                        "status": "queued",
                    }
                else:
                    result = {
                        "user_id": user_id,
                        "channel": channel,
                        "status": "unsupported",
                    }

                results.append(result)

            except ImportError:
                results.append(
                    {
                        "user_id": user_id,
                        "channel": channel,
                        "status": "service_unavailable",
                    }
                )

    return {
        "total_users": len(request.user_ids),
        "channels": request.channels,
        "results": results,
        "queued_at": datetime.utcnow().isoformat(),
    }


@router.get("/status/{message_id}", response_model=DeliveryStatusResponse)
async def get_delivery_status(message_id: str, channel: str = Query(...)):
    """
    Get delivery status for a sent notification.
    """
    try:
        if channel == "whatsapp":
            from notifications import WhatsAppService

            service = WhatsAppService()
        elif channel == "email":
            from notifications import EmailService

            service = EmailService()
        elif channel == "push":
            from notifications import PushNotificationService

            service = PushNotificationService()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown channel: {channel}")

        status = await service.get_status(message_id)

        return DeliveryStatusResponse(
            message_id=message_id,
            channel=channel,
            status=status.status,
            delivered_at=status.delivered_at,
            read_at=status.read_at,
            error=status.error,
        )

    except ImportError:
        raise HTTPException(status_code=503, detail=f"{channel} service not available")
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/preferences")
async def get_notification_preferences(user_id: str):
    """
    Get user's notification preferences.
    """
    # Would integrate with user_preferences module
    return {
        "user_id": user_id,
        "preferences": {
            "push_enabled": True,
            "email_enabled": True,
            "whatsapp_enabled": False,
            "quiet_hours": {
                "enabled": True,
                "start": "22:00",
                "end": "07:00",
            },
            "categories": {
                "medication_reminders": True,
                "appointment_reminders": True,
                "health_alerts": True,
                "weekly_summaries": True,
                "marketing": False,
            },
        },
    }


@router.put("/{user_id}/preferences")
async def update_notification_preferences(
    user_id: str, preferences: Dict[str, Any] = Body(...)
):
    """
    Update user's notification preferences.
    """
    # Would integrate with user_preferences module
    return {
        "status": "updated",
        "user_id": user_id,
        "updated_at": datetime.utcnow().isoformat(),
    }
