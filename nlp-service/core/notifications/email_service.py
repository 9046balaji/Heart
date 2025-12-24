"""
Email Notification Service.

SMTP and SendGrid integration for health summary emails.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

logger = logging.getLogger(__name__)


class EmailDeliveryStatus(str, Enum):
    """Email delivery status."""

    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


@dataclass
class EmailAttachment:
    """Email attachment details."""

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass
class EmailMessage:
    """Email message details."""

    message_id: str
    to_addresses: List[str]
    from_address: str
    subject: str
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    status: EmailDeliveryStatus = EmailDeliveryStatus.QUEUED
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    attachments: List[EmailAttachment] = field(default_factory=list)


class EmailService:
    """
    Email notification service.

    Supports:
    - SMTP delivery
    - SendGrid API
    - HTML and plain text
    - Attachments

    Environment Variables:
        EMAIL_PROVIDER: "smtp" or "sendgrid"
        SMTP_HOST: SMTP server host
        SMTP_PORT: SMTP server port
        SMTP_USERNAME: SMTP username
        SMTP_PASSWORD: SMTP password
        SMTP_USE_TLS: "true" or "false"
        SENDGRID_API_KEY: SendGrid API key
        EMAIL_FROM_ADDRESS: Default sender address
        EMAIL_FROM_NAME: Default sender name

    Example:
        service = EmailService()
        message = service.send(
            to="user@example.com",
            subject="Your Weekly Health Summary",
            body_html=html_content
        )
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_use_tls: bool = True,
        sendgrid_api_key: Optional[str] = None,
        from_address: Optional[str] = None,
        from_name: Optional[str] = None,
    ):
        """
        Initialize email service.

        Args:
            provider: "smtp" or "sendgrid"
            smtp_*: SMTP configuration
            sendgrid_api_key: SendGrid API key
            from_address: Default sender address
            from_name: Default sender name
        """
        self.provider = provider or os.getenv("EMAIL_PROVIDER", "smtp")

        # SMTP config
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = smtp_username or os.getenv("SMTP_USERNAME")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.smtp_use_tls = (
            smtp_use_tls or os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        )

        # SendGrid config
        self.sendgrid_api_key = sendgrid_api_key or os.getenv("SENDGRID_API_KEY")

        # Sender config
        self.from_address = from_address or os.getenv(
            "EMAIL_FROM_ADDRESS", "noreply@healthapp.com"
        )
        self.from_name = from_name or os.getenv("EMAIL_FROM_NAME", "Health App")

    def send(
        self,
        to: str,
        subject: str,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
        attachments: Optional[List[EmailAttachment]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> EmailMessage:
        """
        Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            body_html: HTML body content
            body_text: Plain text body content
            attachments: Optional file attachments
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            EmailMessage with delivery details
        """
        to_addresses = [to]
        if cc:
            to_addresses.extend(cc)
        if bcc:
            to_addresses.extend(bcc)

        if self.provider == "sendgrid":
            return self._send_sendgrid(
                to_addresses, subject, body_html, body_text, attachments
            )
        else:
            return self._send_smtp(
                to_addresses, subject, body_html, body_text, attachments, cc, bcc
            )

    async def send_async(self, to: str, message: str) -> str:
        """
        Async version of send for compatibility with scheduler.

        Args:
            to: Recipient email address
            message: Message content (can be HTML)

        Returns:
            Message ID string
        """
        import asyncio

        # Detect if HTML
        is_html = message.strip().startswith("<!DOCTYPE") or message.strip().startswith(
            "<html"
        )

        body_html = message if is_html else None
        body_text = None if is_html else message

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.send(
                to=to,
                subject="Your Weekly Health Summary",
                body_html=body_html,
                body_text=body_text,
            ),
        )

        if result.status == EmailDeliveryStatus.FAILED:
            raise Exception(result.error_message or "Failed to send email")

        return result.message_id

    def _send_smtp(
        self,
        to_addresses: List[str],
        subject: str,
        body_html: Optional[str],
        body_text: Optional[str],
        attachments: Optional[List[EmailAttachment]],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> EmailMessage:
        """Send email via SMTP."""
        import uuid

        message_id = str(uuid.uuid4())

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_address}>"
            msg["To"] = to_addresses[0]

            if cc:
                msg["Cc"] = ", ".join(cc)

            # Add body parts
            if body_text:
                msg.attach(MIMEText(body_text, "plain", "utf-8"))
            if body_html:
                msg.attach(MIMEText(body_html, "html", "utf-8"))

            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEBase(*attachment.content_type.split("/", 1))
                    part.set_payload(attachment.content)
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{attachment.filename}"',
                    )
                    msg.attach(part)

            # Connect and send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()

                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)

                server.sendmail(self.from_address, to_addresses, msg.as_string())

            logger.info(f"Email sent via SMTP to {to_addresses[0]}")

            return EmailMessage(
                message_id=message_id,
                to_addresses=to_addresses,
                from_address=self.from_address,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                status=EmailDeliveryStatus.SENT,
                sent_at=datetime.utcnow(),
                attachments=attachments or [],
            )

        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return EmailMessage(
                message_id=message_id,
                to_addresses=to_addresses,
                from_address=self.from_address,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                status=EmailDeliveryStatus.FAILED,
                error_message=str(e),
                attachments=attachments or [],
            )

    def _send_sendgrid(
        self,
        to_addresses: List[str],
        subject: str,
        body_html: Optional[str],
        body_text: Optional[str],
        attachments: Optional[List[EmailAttachment]],
    ) -> EmailMessage:
        """Send email via SendGrid API."""
        import uuid

        message_id = str(uuid.uuid4())

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import (
                Mail,
                Attachment,
                FileContent,
                FileName,
                FileType,
                Disposition,
            )
        except ImportError:
            raise ImportError(
                "sendgrid package not installed. " "Run: pip install sendgrid"
            )

        try:
            # Build message
            message = Mail(
                from_email=(self.from_address, self.from_name),
                to_emails=to_addresses,
                subject=subject,
            )

            if body_text:
                message.plain_text_content = body_text
            if body_html:
                message.html_content = body_html

            # Add attachments
            if attachments:
                import base64

                for att in attachments:
                    attachment = Attachment(
                        FileContent(base64.b64encode(att.content).decode()),
                        FileName(att.filename),
                        FileType(att.content_type),
                        Disposition("attachment"),
                    )
                    message.add_attachment(attachment)

            # Send via SendGrid
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            logger.info(
                f"Email sent via SendGrid to {to_addresses[0]}: "
                f"status {response.status_code}"
            )

            return EmailMessage(
                message_id=message_id,
                to_addresses=to_addresses,
                from_address=self.from_address,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                status=EmailDeliveryStatus.SENT,
                sent_at=datetime.utcnow(),
                attachments=attachments or [],
            )

        except Exception as e:
            logger.error(f"SendGrid send failed: {e}")
            return EmailMessage(
                message_id=message_id,
                to_addresses=to_addresses,
                from_address=self.from_address,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                status=EmailDeliveryStatus.FAILED,
                error_message=str(e),
                attachments=attachments or [],
            )


class HealthSummaryEmailService:
    """
    Specialized email service for health summaries.

    Features:
    - Pre-designed email templates
    - PDF report generation
    - Unsubscribe handling
    - Enhanced chart-rich reports
    """

    def __init__(self, email_service: EmailService):
        """Initialize with base email service."""
        self.email = email_service
        
        # Setup Jinja2 environment
        template_dir = Path(__file__).parent.parent.parent / 'templates'
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def send_weekly_summary(
        self,
        to_email: str,
        html_content: str,
        user_name: Optional[str] = None,
        include_pdf: bool = False,
    ) -> EmailMessage:
        """
        Send weekly health summary email.

        Args:
            to_email: Recipient email
            html_content: HTML email content
            user_name: User's name for personalization
            include_pdf: Generate and attach PDF version

        Returns:
            EmailMessage result
        """
        subject = "Your Weekly Health Summary"
        if user_name:
            subject = f"{user_name}, {subject}"

        attachments = []
        if include_pdf:
            pdf_content = self._generate_summary_pdf(html_content)
            if pdf_content:
                attachments.append(
                    EmailAttachment(
                        filename="weekly_health_summary.pdf",
                        content=pdf_content,
                        content_type="application/pdf",
                    )
                )

        return self.email.send(
            to=to_email,
            subject=subject,
            body_html=html_content,
            attachments=attachments if attachments else None,
        )

    def _generate_summary_pdf(self, html_content: str) -> Optional[bytes]:
        """
        Generate PDF from HTML content.

        Requires weasyprint or similar library.
        """
        try:
            from weasyprint import HTML

            return HTML(string=html_content).write_pdf()
        except ImportError:
            logger.warning("weasyprint not installed, PDF generation skipped")
            return None
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return None

    def send_weekly_summary_with_charts(
        self,
        to_email: str,
        user_name: str,
        week_data: Dict[str, Any],
        insights: Dict[str, str],
        recommendations: List[str]
    ) -> EmailMessage:
        """
        Send visually rich weekly summary with charts.
        
        Args:
            to_email: Recipient email
            user_name: User's name
            week_data: Dictionary with health data:
                {
                    'dates': ['2024-01-01', ...],
                    'heart_rates': [72, 75, ...],
                    'steps': [8000, 10500, ...],
                    'blood_pressure': {'systolic': [...], 'diastolic': [...]},
                    'medication_adherence': 85.0,
                    'medication_doses': {'total': 14, 'taken': 12}
                }
            insights: AI-generated insights for each metric
            recommendations: List of health recommendations
            
        Returns:
            EmailMessage result
        """
        from nlp.weekly_summary.chart_generator import get_chart_generator
        
        chart_gen = get_chart_generator()
        
        # Generate all charts
        charts = {
            'heart_rate': chart_gen.generate_heart_rate_chart(
                dates=week_data['dates'],
                values=week_data['heart_rates'],
                resting_hr=week_data.get('resting_hr')
            ),
            'steps': chart_gen.generate_activity_bar_chart(
                days=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                steps=week_data['steps'],
                goal=10000
            ),
            'blood_pressure': chart_gen.generate_blood_pressure_chart(
                dates=week_data['dates'],
                systolic=week_data['blood_pressure']['systolic'],
                diastolic=week_data['blood_pressure']['diastolic']
            ),
            'medication': chart_gen.generate_medication_gauge(
                adherence_percent=week_data['medication_adherence'],
                total_doses=week_data['medication_doses']['total'],
                taken_doses=week_data['medication_doses']['taken']
            )
        }
        
        # Render template
        template = self.jinja_env.get_template('weekly_report.html')
        html_content = template.render(
            user_name=user_name,
            week_range=f"{week_data['dates'][0]} to {week_data['dates'][-1]}",
            charts=charts,
            insights=insights,
            scores={
                'medication': week_data['medication_adherence'],
                'medication_message': self._get_adherence_message(
                    week_data['medication_adherence']
                )
            },
            recommendations=recommendations
        )
        
        # Generate PDF
        pdf_content = self._generate_rich_pdf(html_content)
        
        attachments = []
        if pdf_content:
            attachments.append(
                EmailAttachment(
                    filename="weekly_health_summary.pdf",
                    content=pdf_content,
                    content_type="application/pdf",
                )
            )
        
        return self.email.send(
            to=to_email,
            subject=f"{user_name}, Your Weekly Health Summary",
            body_html=html_content,
            attachments=attachments if attachments else None,
        )

    def _get_adherence_message(self, percent: float) -> str:
        """Get adherence message based on percentage."""
        if percent >= 90:
            return "Excellent! Keep up the great work."
        elif percent >= 80:
            return "Good adherence. Try to maintain this level."
        elif percent >= 70:
            return "Fair adherence. Consider setting reminders."
        else:
            return "Low adherence detected. Please consult your doctor."

    def _generate_rich_pdf(self, html_content: str) -> Optional[bytes]:
        """Enhanced PDF generation with proper CSS rendering."""
        try:
            from weasyprint import HTML, CSS
            
            # Generate PDF with CSS support
            return HTML(string=html_content).write_pdf(
                stylesheets=[
                    CSS(string='@page { size: A4; margin: 1.5cm; }')
                ]
            )
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return None

    def generate_unsubscribe_link(self, user_id: str, token: str) -> str:
        """
        Generate unsubscribe link for email.

        Args:
            user_id: User ID
            token: Unsubscribe token

        Returns:
            Unsubscribe URL
        """
        base_url = os.getenv("APP_BASE_URL", "https://healthapp.com")
        return f"{base_url}/api/unsubscribe?user={user_id}&token={token}"
