"""
Notification services for email, SMS, and push notifications.

Phase 4: Notification Services
Updated: Real SMTP, Twilio, and FCM implementations with environment config
"""

import logging
import smtplib
import ssl
import os
from typing import Optional, List, Dict, Any
from uuid import uuid4
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contextlib import contextmanager

# Optional imports for external services
try:
    from twilio.rest import Client as TwilioClient

    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    TwilioClient = None

try:
    import firebase_admin
    from firebase_admin import credentials, messaging

    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    firebase_admin = None
    credentials = None
    messaging = None

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

logger = logging.getLogger(__name__)


# ============================================================================
# EMAIL NOTIFICATION SERVICE
# ============================================================================


class EmailNotificationService:
    """
    Send email notifications via SMTP.

    Supports multiple SMTP providers:
    - Gmail (smtp.gmail.com:587)
    - SendGrid (smtp.sendgrid.net:587)
    - AWS SES (email-smtp.{region}.amazonaws.com:587)
    - Custom SMTP servers

    Environment Variables:
        SMTP_SERVER: SMTP server address
        SMTP_PORT: SMTP port (default: 587)
        SMTP_USE_TLS: Enable TLS (default: true)
        EMAIL_FROM: Sender email address
        EMAIL_PASSWORD: Sender password/app password
        EMAIL_MOCK_MODE: Set to 'true' to skip actual sending
    """

    def __init__(
        self,
        smtp_server: str = None,
        smtp_port: int = None,
        from_email: str = None,
        from_password: Optional[str] = None,
        use_tls: bool = True,
        mock_mode: bool = None,
    ):
        """
        Initialize email service.

        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP port
            from_email: Sender email address
            from_password: Sender password (use environment variables in production)
            use_tls: Enable TLS encryption
            mock_mode: Skip actual sending (for testing)
        """
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.from_email = from_email or os.getenv(
            "EMAIL_FROM", "noreply@healthcare-chatbot.com"
        )
        self.from_password = from_password or os.getenv("EMAIL_PASSWORD", "")
        self.use_tls = (
            use_tls
            if use_tls is not None
            else os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        )

        # Mock mode check
        if mock_mode is None:
            mock_mode = os.getenv("EMAIL_MOCK_MODE", "false").lower() == "true"
        self.mock_mode = mock_mode or not self.from_password

        if self.mock_mode:
            logger.info(f"Email service initialized in MOCK mode: {self.from_email}")
        else:
            logger.info(
                f"Email service initialized: {self.from_email} via {self.smtp_server}:{self.smtp_port}"
            )

    @contextmanager
    def _smtp_connection(self):
        """Create and manage SMTP connection context."""
        server = None
        try:
            if self.use_tls:
                context = ssl.create_default_context()
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls(context=context)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)

            if self.from_password:
                server.login(self.from_email, self.from_password)

            yield server
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html: bool = False,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """
        Send email notification.

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body (HTML or plain text)
            html: Is body HTML formatted
            cc: Carbon copy recipients
            bcc: Blind carbon copy recipients

        Returns:
            True if successful
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email

            if cc:
                msg["Cc"] = ", ".join(cc)

            # Attach body
            if html:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            # Mock mode - just log
            if self.mock_mode:
                logger.info(f"[MOCK] Email to {to_email}: {subject}")
                return True

            # Real SMTP sending
            all_recipients = [to_email]
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)

            with self._smtp_connection() as server:
                server.send_message(msg, to_addrs=all_recipients)

            logger.info(f"Email sent to {to_email}: {subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending to {to_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_reminder_email(
        self,
        to_email: str,
        patient_name: str,
        appointment_datetime: str,
        provider_name: str,
        appointment_type: str,
    ) -> bool:
        """
        Send appointment reminder email.

        Args:
            to_email: Patient email
            patient_name: Patient name
            appointment_datetime: Formatted datetime
            provider_name: Provider name
            appointment_type: Type of appointment

        Returns:
            True if successful
        """
        subject = "Appointment Reminder"

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Appointment Reminder</h2>
                <p>Hi {patient_name},</p>
                <p>This is a reminder that you have an upcoming appointment:</p>
                <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px;">
                    <p><strong>Date & Time:</strong> {appointment_datetime}</p>
                    <p><strong>Provider:</strong> {provider_name}</p>
                    <p><strong>Type:</strong> {appointment_type}</p>
                </div>
                <p>Please arrive 10 minutes early.</p>
                <p>If you need to cancel or reschedule, please contact us as soon as possible.</p>
                <p>Best regards,<br>Healthcare Chatbot Team</p>
            </body>
        </html>
        """

        return self.send_email(to_email, subject, html_body, html=True)


# ============================================================================
# SMS NOTIFICATION SERVICE
# ============================================================================


class SMSNotificationService:
    """
    Send SMS notifications via Twilio.

    Environment Variables:
        TWILIO_ACCOUNT_SID: Twilio account SID
        TWILIO_AUTH_TOKEN: Twilio authentication token
        TWILIO_PHONE_NUMBER: Twilio phone number (sender)
        SMS_MOCK_MODE: Set to 'true' to skip actual sending
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        mock_mode: bool = None,
    ):
        """
        Initialize SMS service.

        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            from_number: Twilio phone number
            mock_mode: Skip actual sending (for testing)
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = from_number or os.getenv(
            "TWILIO_PHONE_NUMBER", "+1234567890"
        )

        # Mock mode check
        if mock_mode is None:
            mock_mode = os.getenv("SMS_MOCK_MODE", "false").lower() == "true"
        self.mock_mode = mock_mode or not TWILIO_AVAILABLE or not self.account_sid

        # Initialize Twilio client if available
        self.client = None
        if (
            TWILIO_AVAILABLE
            and self.account_sid
            and self.auth_token
            and not self.mock_mode
        ):
            try:
                self.client = TwilioClient(self.account_sid, self.auth_token)
                logger.info(f"SMS service initialized with Twilio: {self.from_number}")
            except Exception as e:
                logger.warning(f"Failed to initialize Twilio client: {e}")
                self.mock_mode = True
        else:
            if not TWILIO_AVAILABLE:
                logger.info("SMS service in MOCK mode (Twilio not installed)")
            else:
                logger.info(f"SMS service initialized in MOCK mode: {self.from_number}")

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        """
        Send SMS notification.

        Args:
            to_phone: Recipient phone number (E.164 format recommended)
            message: SMS message

        Returns:
            Dict with status and message SID if successful
        """
        try:
            # Mock mode - just log
            if self.mock_mode:
                mock_sid = f"SM_mock_{uuid4().hex[:12]}"
                logger.info(f"[MOCK] SMS to {to_phone}: {message[:50]}...")
                return {"success": True, "sid": mock_sid, "mock": True}

            # Real Twilio sending
            if not self.client:
                logger.error("Twilio client not initialized")
                return {"success": False, "error": "Twilio client not initialized"}

            result = self.client.messages.create(
                body=message, from_=self.from_number, to=to_phone
            )

            logger.info(f"SMS sent to {to_phone}, SID: {result.sid}")
            return {"success": True, "sid": result.sid}

        except Exception as e:
            logger.error(f"Failed to send SMS to {to_phone}: {e}")
            return {"success": False, "error": str(e)}

    def send_reminder_sms(
        self, to_phone: str, patient_name: str, appointment_time: str
    ) -> bool:
        """
        Send appointment reminder SMS.

        Args:
            to_phone: Patient phone
            patient_name: Patient name
            appointment_time: Appointment time string

        Returns:
            True if successful
        """
        message = f"Hi {patient_name}, reminder: Your appointment is at {appointment_time}. Reply CONFIRM to confirm."
        result = self.send_sms(to_phone, message)
        return result.get("success", False)


# ============================================================================
# PUSH NOTIFICATION SERVICE
# ============================================================================


class PushNotificationService:
    """
    Send push notifications via Firebase Cloud Messaging.

    Supports two modes:
    1. Firebase Admin SDK (recommended) - using service account
    2. Legacy HTTP API - using server key

    Environment Variables:
        FIREBASE_CREDENTIALS_FILE: Path to service account JSON
        FIREBASE_SERVER_KEY: Legacy server key (deprecated but supported)
        PUSH_MOCK_MODE: Set to 'true' to skip actual sending
    """

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        server_key: Optional[str] = None,
        fcm_url: str = "https://fcm.googleapis.com/fcm/send",
        mock_mode: bool = None,
    ):
        """
        Initialize push notification service.

        Args:
            credentials_file: Path to Firebase service account JSON
            server_key: Firebase server key (legacy)
            fcm_url: Firebase Cloud Messaging URL (legacy)
            mock_mode: Skip actual sending (for testing)
        """
        self.credentials_file = credentials_file or os.getenv(
            "FIREBASE_CREDENTIALS_FILE", ""
        )
        self.server_key = server_key or os.getenv("FIREBASE_SERVER_KEY", "")
        self.fcm_url = fcm_url

        # Mock mode check
        if mock_mode is None:
            mock_mode = os.getenv("PUSH_MOCK_MODE", "false").lower() == "true"

        self.use_admin_sdk = False
        self.mock_mode = mock_mode

        # Try to initialize Firebase Admin SDK
        if FIREBASE_AVAILABLE and self.credentials_file and not mock_mode:
            try:
                if not firebase_admin._apps:
                    cred = credentials.Certificate(self.credentials_file)
                    firebase_admin.initialize_app(cred)
                self.use_admin_sdk = True
                logger.info(
                    "Push notification service initialized with Firebase Admin SDK"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Firebase Admin SDK: {e}")

        # Fall back to legacy HTTP API
        if not self.use_admin_sdk and self.server_key and not mock_mode:
            if REQUESTS_AVAILABLE:
                logger.info(
                    "Push notification service initialized with legacy HTTP API"
                )
            else:
                logger.warning("requests library not available for legacy FCM API")
                self.mock_mode = True
        elif not self.use_admin_sdk:
            self.mock_mode = True
            logger.info("Push notification service initialized in MOCK mode")

    def send_push(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send push notification.

        Args:
            device_token: Target device FCM token
            title: Notification title
            body: Notification body
            data: Optional custom data payload

        Returns:
            Dict with status and message ID if successful
        """
        try:
            # Mock mode - just log
            if self.mock_mode:
                mock_id = f"push_mock_{uuid4().hex[:12]}"
                logger.info(f"[MOCK] Push to {device_token[:20]}...: {title}")
                return {"success": True, "message_id": mock_id, "mock": True}

            # Firebase Admin SDK (preferred)
            if self.use_admin_sdk and FIREBASE_AVAILABLE:
                message = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=data or {},
                    token=device_token,
                )
                response = messaging.send(message)
                logger.info(f"Push sent via Admin SDK: {response}")
                return {"success": True, "message_id": response}

            # Legacy HTTP API
            if self.server_key and REQUESTS_AVAILABLE:
                headers = {
                    "Authorization": f"key={self.server_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "to": device_token,
                    "notification": {"title": title, "body": body},
                    "data": data or {},
                }
                response = requests.post(
                    self.fcm_url, json=payload, headers=headers, timeout=10
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success", 0) > 0:
                        logger.info(
                            f"Push sent via legacy API to {device_token[:20]}..."
                        )
                        return {"success": True, "response": result}
                    else:
                        logger.error(f"FCM push failed: {result}")
                        return {
                            "success": False,
                            "error": result.get("results", [{}])[0].get(
                                "error", "Unknown"
                            ),
                        }
                else:
                    logger.error(f"FCM API error: {response.status_code}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}

            return {"success": False, "error": "No FCM provider configured"}

        except Exception as e:
            logger.error(
                f"Failed to send push notification to {device_token[:20]}...: {e}"
            )
            return {"success": False, "error": str(e)}

    def send_reminder_push(
        self, device_id: str, appointment_time: str, provider_name: str
    ) -> bool:
        """
        Send appointment reminder push notification.

        Args:
            device_id: Patient device ID
            appointment_time: Appointment time string
            provider_name: Provider name

        Returns:
            True if successful
        """
        title = "Appointment Reminder"
        body = f"Appointment with {provider_name} at {appointment_time}"
        data = {
            "type": "appointment_reminder",
            "appointment_time": appointment_time,
            "provider": provider_name,
        }

        result = self.send_push(device_id, title, body, data)
        return result.get("success", False)


# ============================================================================
# SINGLETON PATTERNS
# ============================================================================


_email_service: Optional[EmailNotificationService] = None
_sms_service: Optional[SMSNotificationService] = None
_push_service: Optional[PushNotificationService] = None


def get_email_service() -> EmailNotificationService:
    """Get or create email service singleton."""
    global _email_service

    if _email_service is None:
        import os

        _email_service = EmailNotificationService(
            from_email=os.getenv("EMAIL_FROM", "noreply@healthcare-chatbot.com"),
            from_password=os.getenv("EMAIL_PASSWORD", ""),
        )

    return _email_service


def get_sms_service() -> SMSNotificationService:
    """Get or create SMS service singleton."""
    global _sms_service

    if _sms_service is None:
        import os

        _sms_service = SMSNotificationService(
            account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
            from_number=os.getenv("TWILIO_PHONE_NUMBER"),
        )

    return _sms_service


def get_push_service() -> PushNotificationService:
    """Get or create push service singleton."""
    global _push_service

    if _push_service is None:
        import os

        _push_service = PushNotificationService(
            server_key=os.getenv("FIREBASE_SERVER_KEY")
        )

    return _push_service


def reset_notification_services() -> None:
    """Reset all notification services (for testing)."""
    global _email_service, _sms_service, _push_service
    _email_service = None
    _sms_service = None
    _push_service = None
