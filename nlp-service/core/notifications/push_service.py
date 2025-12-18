"""
Push Notification Service.

Firebase Cloud Messaging (FCM) integration for mobile push notifications.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import os

logger = logging.getLogger(__name__)


class PushPriority(str, Enum):
    """Push notification priority."""
    NORMAL = "normal"
    HIGH = "high"


class PushDeliveryStatus(str, Enum):
    """Push notification delivery status."""
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    INVALID_TOKEN = "invalid_token"


@dataclass
class PushNotification:
    """Push notification details."""
    notification_id: str
    device_token: str
    title: str
    body: str
    status: PushDeliveryStatus
    sent_at: Optional[datetime] = None
    data: Dict[str, str] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class PushNotificationPayload:
    """Push notification payload configuration."""
    title: str
    body: str
    image_url: Optional[str] = None
    click_action: Optional[str] = None
    data: Dict[str, str] = field(default_factory=dict)
    priority: PushPriority = PushPriority.NORMAL
    badge_count: Optional[int] = None
    sound: str = "default"
    
    # iOS specific
    ios_badge: Optional[int] = None
    ios_category: Optional[str] = None
    
    # Android specific
    android_channel_id: Optional[str] = None
    android_icon: Optional[str] = None


class PushNotificationService:
    """
    Push notification service using Firebase Cloud Messaging.
    
    Supports:
    - Single device notifications
    - Topic-based notifications
    - Data-only messages
    - Priority handling
    
    Environment Variables:
        FIREBASE_PROJECT_ID: Firebase project ID
        FIREBASE_CREDENTIALS_PATH: Path to service account JSON
        
    Example:
        service = PushNotificationService()
        result = service.send_to_device(
            device_token="abc123...",
            title="Health Update",
            body="Your weekly summary is ready!"
        )
    """
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        credentials_dict: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize push notification service.
        
        Args:
            project_id: Firebase project ID
            credentials_path: Path to service account JSON file
            credentials_dict: Credentials as dictionary (alternative to file)
        """
        self.project_id = project_id or os.getenv("FIREBASE_PROJECT_ID")
        self.credentials_path = credentials_path or os.getenv("FIREBASE_CREDENTIALS_PATH")
        self.credentials_dict = credentials_dict
        
        self._app = None
        self._initialized = False
    
    def _initialize_firebase(self) -> bool:
        """Initialize Firebase Admin SDK."""
        if self._initialized:
            return True
        
        try:
            import firebase_admin
            from firebase_admin import credentials
            
            # Check if already initialized
            try:
                firebase_admin.get_app()
                self._initialized = True
                return True
            except ValueError:
                pass
            
            # Initialize with credentials
            if self.credentials_dict:
                cred = credentials.Certificate(self.credentials_dict)
            elif self.credentials_path:
                cred = credentials.Certificate(self.credentials_path)
            else:
                # Try default credentials (e.g., on GCP)
                cred = credentials.ApplicationDefault()
            
            self._app = firebase_admin.initialize_app(cred, {
                "projectId": self.project_id
            })
            self._initialized = True
            logger.info("Firebase Admin SDK initialized")
            return True
            
        except ImportError:
            logger.error(
                "firebase-admin package not installed. "
                "Run: pip install firebase-admin"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            return False
    
    def send_to_device(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        priority: PushPriority = PushPriority.NORMAL,
        image_url: Optional[str] = None
    ) -> PushNotification:
        """
        Send push notification to a single device.
        
        Args:
            device_token: FCM device token
            title: Notification title
            body: Notification body
            data: Optional data payload
            priority: Notification priority
            image_url: Optional image URL
        
        Returns:
            PushNotification with delivery details
        """
        import uuid
        
        notification_id = str(uuid.uuid4())
        
        if not self._initialize_firebase():
            return PushNotification(
                notification_id=notification_id,
                device_token=device_token,
                title=title,
                body=body,
                status=PushDeliveryStatus.FAILED,
                error_message="Firebase not initialized"
            )
        
        try:
            from firebase_admin import messaging
            
            # Build notification
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )
            
            # Build Android config
            android_config = messaging.AndroidConfig(
                priority="high" if priority == PushPriority.HIGH else "normal",
                notification=messaging.AndroidNotification(
                    icon="ic_health_notification",
                    color="#4CAF50"
                )
            )
            
            # Build iOS config
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1
                    )
                )
            )
            
            # Build message
            message = messaging.Message(
                notification=notification,
                data=data or {},
                token=device_token,
                android=android_config,
                apns=apns_config
            )
            
            # Send
            response = messaging.send(message)
            
            logger.info(f"Push notification sent: {response}")
            
            return PushNotification(
                notification_id=notification_id,
                device_token=device_token,
                title=title,
                body=body,
                status=PushDeliveryStatus.SENT,
                sent_at=datetime.utcnow(),
                data=data or {}
            )
            
        except Exception as e:
            error_str = str(e)
            status = PushDeliveryStatus.FAILED
            
            # Check for invalid token
            if "not-registered" in error_str.lower() or "invalid" in error_str.lower():
                status = PushDeliveryStatus.INVALID_TOKEN
            
            logger.error(f"Push notification failed: {e}")
            
            return PushNotification(
                notification_id=notification_id,
                device_token=device_token,
                title=title,
                body=body,
                status=status,
                error_message=error_str,
                data=data or {}
            )
    
    async def send_to_device_async(
        self,
        device_token: str,
        message: str
    ) -> str:
        """
        Async version of send_to_device for scheduler compatibility.
        
        Args:
            device_token: FCM device token
            message: Notification message (used as body)
        
        Returns:
            Notification ID string
        """
        import asyncio
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.send_to_device(
                device_token=device_token,
                title="Health Summary",
                body=message[:100] + "..." if len(message) > 100 else message
            )
        )
        
        if result.status == PushDeliveryStatus.FAILED:
            raise Exception(result.error_message or "Failed to send push notification")
        
        return result.notification_id
    
    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Send push notification to a topic.
        
        Args:
            topic: Topic name (e.g., "weekly_summaries")
            title: Notification title
            body: Notification body
            data: Optional data payload
        
        Returns:
            True if successful
        """
        if not self._initialize_firebase():
            return False
        
        try:
            from firebase_admin import messaging
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                topic=topic
            )
            
            response = messaging.send(message)
            logger.info(f"Topic notification sent: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Topic notification failed: {e}")
            return False
    
    def send_to_multiple_devices(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> Dict[str, PushDeliveryStatus]:
        """
        Send push notification to multiple devices.
        
        Args:
            device_tokens: List of FCM device tokens
            title: Notification title
            body: Notification body
            data: Optional data payload
        
        Returns:
            Dict mapping token to delivery status
        """
        if not self._initialize_firebase():
            return {token: PushDeliveryStatus.FAILED for token in device_tokens}
        
        try:
            from firebase_admin import messaging
            
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                tokens=device_tokens
            )
            
            response = messaging.send_each_for_multicast(message)
            
            results = {}
            for idx, send_response in enumerate(response.responses):
                token = device_tokens[idx]
                if send_response.success:
                    results[token] = PushDeliveryStatus.SENT
                else:
                    error_str = str(send_response.exception)
                    if "not-registered" in error_str.lower():
                        results[token] = PushDeliveryStatus.INVALID_TOKEN
                    else:
                        results[token] = PushDeliveryStatus.FAILED
            
            logger.info(
                f"Multicast sent: {response.success_count} success, "
                f"{response.failure_count} failed"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Multicast notification failed: {e}")
            return {token: PushDeliveryStatus.FAILED for token in device_tokens}
    
    def subscribe_to_topic(
        self,
        device_tokens: List[str],
        topic: str
    ) -> bool:
        """
        Subscribe devices to a topic.
        
        Args:
            device_tokens: List of FCM device tokens
            topic: Topic name
        
        Returns:
            True if successful
        """
        if not self._initialize_firebase():
            return False
        
        try:
            from firebase_admin import messaging
            
            response = messaging.subscribe_to_topic(device_tokens, topic)
            
            logger.info(
                f"Subscribed {response.success_count} devices to topic '{topic}'"
            )
            
            return response.failure_count == 0
            
        except Exception as e:
            logger.error(f"Topic subscription failed: {e}")
            return False
    
    def unsubscribe_from_topic(
        self,
        device_tokens: List[str],
        topic: str
    ) -> bool:
        """
        Unsubscribe devices from a topic.
        
        Args:
            device_tokens: List of FCM device tokens
            topic: Topic name
        
        Returns:
            True if successful
        """
        if not self._initialize_firebase():
            return False
        
        try:
            from firebase_admin import messaging
            
            response = messaging.unsubscribe_from_topic(device_tokens, topic)
            
            logger.info(
                f"Unsubscribed {response.success_count} devices from topic '{topic}'"
            )
            
            return response.failure_count == 0
            
        except Exception as e:
            logger.error(f"Topic unsubscription failed: {e}")
            return False


class HealthPushNotificationService:
    """
    Specialized push notification service for health app.
    
    Features:
    - Weekly summary notifications
    - Medication reminders
    - Health alerts
    - Goal achievements
    """
    
    # Topics
    TOPIC_WEEKLY_SUMMARIES = "weekly_health_summaries"
    TOPIC_MEDICATION_REMINDERS = "medication_reminders"
    TOPIC_HEALTH_ALERTS = "health_alerts"
    
    def __init__(self, push_service: PushNotificationService):
        """Initialize with base push service."""
        self.push = push_service
    
    def send_weekly_summary_notification(
        self,
        device_token: str,
        user_name: Optional[str] = None
    ) -> PushNotification:
        """
        Send weekly summary ready notification.
        
        Args:
            device_token: User's device token
            user_name: User's name for personalization
        
        Returns:
            PushNotification result
        """
        title = "📊 Weekly Health Summary Ready"
        body = f"Hi {user_name}! " if user_name else ""
        body += "Your weekly health report is ready. Tap to view your progress!"
        
        return self.push.send_to_device(
            device_token=device_token,
            title=title,
            body=body,
            data={
                "type": "weekly_summary",
                "action": "view_summary"
            },
            priority=PushPriority.NORMAL
        )
    
    def send_medication_reminder(
        self,
        device_token: str,
        medication_name: str,
        dose: str
    ) -> PushNotification:
        """
        Send medication reminder notification.
        
        Args:
            device_token: User's device token
            medication_name: Name of medication
            dose: Dosage information
        
        Returns:
            PushNotification result
        """
        return self.push.send_to_device(
            device_token=device_token,
            title="💊 Medication Reminder",
            body=f"Time to take {medication_name} ({dose})",
            data={
                "type": "medication_reminder",
                "medication": medication_name,
                "dose": dose
            },
            priority=PushPriority.HIGH
        )
    
    def send_health_alert(
        self,
        device_token: str,
        alert_title: str,
        alert_message: str,
        severity: str = "warning"
    ) -> PushNotification:
        """
        Send health alert notification.
        
        Args:
            device_token: User's device token
            alert_title: Alert title
            alert_message: Alert message
            severity: "warning", "critical", or "info"
        
        Returns:
            PushNotification result
        """
        emoji = "⚠️" if severity == "warning" else "🚨" if severity == "critical" else "ℹ️"
        
        return self.push.send_to_device(
            device_token=device_token,
            title=f"{emoji} {alert_title}",
            body=alert_message,
            data={
                "type": "health_alert",
                "severity": severity
            },
            priority=PushPriority.HIGH if severity in ["warning", "critical"] else PushPriority.NORMAL
        )
    
    def send_goal_achievement(
        self,
        device_token: str,
        goal_name: str,
        achievement_message: str
    ) -> PushNotification:
        """
        Send goal achievement notification.
        
        Args:
            device_token: User's device token
            goal_name: Name of the goal achieved
            achievement_message: Congratulatory message
        
        Returns:
            PushNotification result
        """
        return self.push.send_to_device(
            device_token=device_token,
            title=f"🎉 Goal Achieved: {goal_name}",
            body=achievement_message,
            data={
                "type": "goal_achievement",
                "goal": goal_name
            },
            priority=PushPriority.NORMAL
        )
