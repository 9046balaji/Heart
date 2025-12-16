"""
WhatsApp Notification Service.

Twilio WhatsApp Business API integration for health summaries.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
import os

logger = logging.getLogger(__name__)


class WhatsAppMessageStatus(str, Enum):
    """WhatsApp message delivery status."""
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


@dataclass
class WhatsAppMessage:
    """WhatsApp message details."""
    message_id: str
    to_number: str
    from_number: str
    body: str
    status: WhatsAppMessageStatus
    sent_at: datetime
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class WhatsAppTemplateMessage:
    """WhatsApp template message (for business notifications)."""
    template_name: str
    template_language: str = "en"
    components: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.components is None:
            self.components = []


class WhatsAppService:
    """
    WhatsApp Business API service using Twilio.
    
    Supports:
    - Text messages
    - Template messages (for proactive notifications)
    - Media messages
    - Message status webhooks
    
    Environment Variables:
        TWILIO_ACCOUNT_SID: Twilio account SID
        TWILIO_AUTH_TOKEN: Twilio auth token
        TWILIO_WHATSAPP_NUMBER: Your Twilio WhatsApp-enabled number
    
    Example:
        service = WhatsAppService()
        message = service.send("+1234567890", "Your weekly health summary...")
        print(f"Sent: {message.message_id}")
    """
    
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        sandbox_mode: bool = False
    ):
        """
        Initialize WhatsApp service.
        
        Args:
            account_sid: Twilio account SID (or from env)
            auth_token: Twilio auth token (or from env)
            from_number: Your WhatsApp-enabled number (or from env)
            sandbox_mode: Use Twilio sandbox for testing
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_WHATSAPP_NUMBER")
        self.sandbox_mode = sandbox_mode
        
        self._client = None
        self._initialized = False
    
    def _get_client(self):
        """Lazy-load Twilio client."""
        if self._client is None:
            try:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
                self._initialized = True
            except ImportError:
                raise ImportError(
                    "twilio package not installed. "
                    "Run: pip install twilio"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
                raise
        return self._client
    
    def _format_number(self, phone_number: str) -> str:
        """Format phone number for WhatsApp."""
        # Remove any existing prefix
        number = phone_number.replace("whatsapp:", "")
        
        # Ensure it starts with + 
        if not number.startswith("+"):
            number = f"+{number}"
        
        return f"whatsapp:{number}"
    
    def send(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None
    ) -> WhatsAppMessage:
        """
        Send a WhatsApp message.
        
        Args:
            to_number: Recipient phone number (E.164 format)
            message: Message text
            media_url: Optional media attachment URL
        
        Returns:
            WhatsAppMessage with delivery details
        """
        client = self._get_client()
        
        to_formatted = self._format_number(to_number)
        from_formatted = self._format_number(self.from_number)
        
        try:
            # Build message parameters
            params = {
                "from_": from_formatted,
                "to": to_formatted,
                "body": message
            }
            
            if media_url:
                params["media_url"] = [media_url]
            
            # Send via Twilio
            twilio_message = client.messages.create(**params)
            
            logger.info(
                f"WhatsApp message sent to {to_number}: {twilio_message.sid}"
            )
            
            return WhatsAppMessage(
                message_id=twilio_message.sid,
                to_number=to_number,
                from_number=self.from_number,
                body=message,
                status=self._map_status(twilio_message.status),
                sent_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message to {to_number}: {e}")
            return WhatsAppMessage(
                message_id="",
                to_number=to_number,
                from_number=self.from_number,
                body=message,
                status=WhatsAppMessageStatus.FAILED,
                sent_at=datetime.utcnow(),
                error_message=str(e)
            )
    
    async def send_async(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None
    ) -> str:
        """
        Async version of send.
        
        Returns:
            Message ID string
        """
        import asyncio
        
        # Run sync method in executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.send(to_number, message, media_url)
        )
        
        if result.status == WhatsAppMessageStatus.FAILED:
            raise Exception(result.error_message or "Failed to send message")
        
        return result.message_id
    
    def send_template(
        self,
        to_number: str,
        template: WhatsAppTemplateMessage,
        parameters: Optional[Dict[str, str]] = None
    ) -> WhatsAppMessage:
        """
        Send a pre-approved WhatsApp template message.
        
        Template messages are required for initiating conversations
        outside the 24-hour window.
        
        Args:
            to_number: Recipient phone number
            template: Template configuration
            parameters: Template variable values
        
        Returns:
            WhatsAppMessage with delivery details
        """
        client = self._get_client()
        
        to_formatted = self._format_number(to_number)
        from_formatted = self._format_number(self.from_number)
        
        try:
            # Build content SID for template
            # Note: In production, use Twilio Content API for templates
            
            content_variables = {}
            if parameters:
                content_variables = {str(i+1): v for i, v in enumerate(parameters.values())}
            
            twilio_message = client.messages.create(
                from_=from_formatted,
                to=to_formatted,
                content_sid=template.template_name,  # Content template SID
                content_variables=content_variables
            )
            
            logger.info(
                f"WhatsApp template sent to {to_number}: {twilio_message.sid}"
            )
            
            return WhatsAppMessage(
                message_id=twilio_message.sid,
                to_number=to_number,
                from_number=self.from_number,
                body=f"[Template: {template.template_name}]",
                status=self._map_status(twilio_message.status),
                sent_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to send template message to {to_number}: {e}")
            return WhatsAppMessage(
                message_id="",
                to_number=to_number,
                from_number=self.from_number,
                body=f"[Template: {template.template_name}]",
                status=WhatsAppMessageStatus.FAILED,
                sent_at=datetime.utcnow(),
                error_message=str(e)
            )
    
    def get_message_status(self, message_id: str) -> WhatsAppMessageStatus:
        """
        Get the current status of a sent message.
        
        Args:
            message_id: Twilio message SID
        
        Returns:
            Current message status
        """
        client = self._get_client()
        
        try:
            message = client.messages(message_id).fetch()
            return self._map_status(message.status)
        except Exception as e:
            logger.error(f"Failed to get message status for {message_id}: {e}")
            return WhatsAppMessageStatus.FAILED
    
    def _map_status(self, twilio_status: str) -> WhatsAppMessageStatus:
        """Map Twilio status to our enum."""
        status_map = {
            "queued": WhatsAppMessageStatus.QUEUED,
            "sending": WhatsAppMessageStatus.QUEUED,
            "sent": WhatsAppMessageStatus.SENT,
            "delivered": WhatsAppMessageStatus.DELIVERED,
            "read": WhatsAppMessageStatus.READ,
            "failed": WhatsAppMessageStatus.FAILED,
            "undelivered": WhatsAppMessageStatus.FAILED
        }
        return status_map.get(twilio_status, WhatsAppMessageStatus.QUEUED)
    
    def process_webhook(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process incoming webhook from Twilio.
        
        Handles:
        - Status callbacks
        - Incoming messages
        
        Args:
            payload: Webhook payload from Twilio
        
        Returns:
            Processed webhook data or None
        """
        message_sid = payload.get("MessageSid")
        status = payload.get("MessageStatus") or payload.get("SmsStatus")
        from_number = payload.get("From", "").replace("whatsapp:", "")
        body = payload.get("Body")
        
        if status:
            # Status callback
            logger.info(f"Message {message_sid} status: {status}")
            return {
                "type": "status_update",
                "message_id": message_sid,
                "status": self._map_status(status)
            }
        
        if body:
            # Incoming message
            logger.info(f"Incoming message from {from_number}")
            return {
                "type": "incoming_message",
                "from": from_number,
                "body": body,
                "message_id": message_sid
            }
        
        return None
    
    def validate_webhook_signature(
        self,
        signature: str,
        url: str,
        params: Dict[str, str]
    ) -> bool:
        """
        Validate Twilio webhook signature.
        
        Args:
            signature: X-Twilio-Signature header value
            url: Full webhook URL
            params: Request parameters
        
        Returns:
            True if signature is valid
        """
        try:
            from twilio.request_validator import RequestValidator
            validator = RequestValidator(self.auth_token)
            return validator.validate(url, params, signature)
        except Exception as e:
            logger.error(f"Webhook validation error: {e}")
            return False


class WhatsAppHealthSummaryService:
    """
    Specialized WhatsApp service for health summaries.
    
    Handles:
    - Weekly summary delivery
    - Opt-in/opt-out management
    - Delivery scheduling
    """
    
    # Pre-approved template names (register in Twilio)
    TEMPLATE_WEEKLY_SUMMARY = "weekly_health_summary"
    TEMPLATE_MEDICATION_REMINDER = "medication_reminder"
    TEMPLATE_APPOINTMENT_REMINDER = "appointment_reminder"
    
    def __init__(self, whatsapp_service: WhatsAppService):
        """Initialize with base WhatsApp service."""
        self.whatsapp = whatsapp_service
    
    def send_weekly_summary(
        self,
        phone_number: str,
        summary_message: str
    ) -> WhatsAppMessage:
        """
        Send weekly health summary.
        
        Args:
            phone_number: User's phone number
            summary_message: Formatted summary from message generator
        
        Returns:
            WhatsAppMessage result
        """
        return self.whatsapp.send(phone_number, summary_message)
    
    def send_medication_reminder(
        self,
        phone_number: str,
        medication_name: str,
        time_str: str
    ) -> WhatsAppMessage:
        """
        Send medication reminder using template.
        
        Args:
            phone_number: User's phone number
            medication_name: Name of medication
            time_str: Time to take medication
        
        Returns:
            WhatsAppMessage result
        """
        message = f"💊 Reminder: It's time to take your {medication_name} ({time_str})"
        return self.whatsapp.send(phone_number, message)
    
    def handle_opt_out(self, phone_number: str, message: str) -> bool:
        """
        Check if message indicates opt-out.
        
        Args:
            phone_number: User's phone number
            message: Incoming message text
        
        Returns:
            True if user wants to opt out
        """
        opt_out_keywords = ["stop", "unsubscribe", "cancel", "quit", "opt out"]
        return message.lower().strip() in opt_out_keywords
    
    def handle_help(self, phone_number: str, message: str) -> Optional[WhatsAppMessage]:
        """
        Handle help requests.
        
        Args:
            phone_number: User's phone number
            message: Incoming message text
        
        Returns:
            Help message if applicable
        """
        if message.lower().strip() == "help":
            help_text = """📋 *Health Summary Help*

Commands:
• STOP - Unsubscribe from summaries
• SUMMARY - Get your summary now
• STATUS - Check your health status
• SETTINGS - Update preferences

Need support? Contact us at support@healthapp.com"""
            
            return self.whatsapp.send(phone_number, help_text)
        
        return None
