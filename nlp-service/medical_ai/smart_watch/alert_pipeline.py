"""
Alert Pipeline - Routes anomalies to appropriate handlers

This module provides intelligent alert routing with throttling to prevent
alert fatigue. Supports multiple delivery channels (in-app, push, WebSocket, SMS).
"""

import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

# Redis imports for distributed throttling
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from .anomaly_detector import PredictionResult
from .chatbot_connector import ChatbotManager
from .prompt_templates import (
    get_prompt_for_anomaly,
    get_quick_response,
    PromptContext,
    ResponseTone,
)

logger = logging.getLogger(__name__)


class AlertChannel(Enum):
    """Channels for delivering alerts."""

    IN_APP = "in_app"  # Show in app UI
    PUSH_NOTIFICATION = "push"  # Mobile push notification
    WEBSOCKET = "websocket"  # Real-time WebSocket
    SMS = "sms"  # For emergencies
    SILENT_LOG = "log"  # Just log, no alert


@dataclass
class Alert:
    """
    An alert to be delivered to the user.

    Contains all information needed to display and route an alert,
    including chatbot-generated explanations.
    """

    id: str
    timestamp: str
    anomaly_type: str
    severity: str
    risk_score: float

    # Content
    title: str
    message: str
    recommendation: str
    chatbot_explanation: Optional[str]

    # Delivery
    channels: List[AlertChannel]
    acknowledged: bool = False

    # Metadata
    raw_value: float = 0
    threshold: float = 0


class AlertThrottler:
    """
    Prevents alert fatigue by throttling similar alerts.

    Uses a cooldown period to avoid bombarding users with repeated
    alerts for the same condition. Emergency alerts bypass throttling.
    Now uses Redis for distributed throttling across multiple workers.
    """

    def __init__(self, cooldown_seconds: int = 300):  # 5 min default
        """
        Initialize throttler.

        Args:
            cooldown_seconds: Minimum time between similar alerts
        """
        self.cooldown_seconds = cooldown_seconds
        self.redis_client = None
        
        # Try to initialize Redis client for distributed throttling
        if REDIS_AVAILABLE:
            try:
                from core.config import REDIS_URL
                from core.cache.redis_client import RedisClient
                self.redis_client = RedisClient
            except Exception as e:
                logger.warning(f"Could not initialize Redis for alert throttling: {e}")
                logger.info("Falling back to in-memory throttling")
        else:
            logger.info("Redis not available, using in-memory throttling")

    def _get_throttle_key(self, alert_type: str, severity: str) -> str:
        """Generate Redis key for throttling."""
        return f"alert:throttle:{alert_type}:{severity}"

    async def should_send(self, alert_type: str, severity: str) -> bool:
        """
        Check if we should send this alert or throttle it.
        Uses Redis for distributed throttling across multiple workers.

        Args:
            alert_type: Type of alert (e.g., "TACHYCARDIA")
            severity: Severity level

        Returns:
            True if alert should be sent, False if throttled
        """
        # Always send emergencies
        if severity in ["CRITICAL", "EMERGENCY"]:
            if self.redis_client:
                try:
                    redis = await self.redis_client.get_client()
                    key = self._get_throttle_key(alert_type, severity)
                    await redis.setex(key, self.cooldown_seconds, str(time.time()))
                except Exception as e:
                    logger.error(f"Redis error in emergency alert: {e}")
            return True

        # For non-emergency alerts, check throttling
        if self.redis_client:
            try:
                # Use Redis for distributed throttling
                redis = await self.redis_client.get_client()
                key = self._get_throttle_key(alert_type, severity)
                
                # Try to set the key with NX (only if not exists) and EX (expiration)
                # This is atomic - only one worker succeeds
                result = await redis.set(
                    key,
                    str(time.time()),
                    nx=True,  # Only set if key doesn't exist
                    ex=self.cooldown_seconds  # Auto-expire after cooldown period
                )
                
                # If result is True, we successfully set the key (not in cooldown)
                # If result is None, key already exists (in cooldown)
                return result is not None
            except Exception as e:
                logger.error(f"Redis error in throttling: {e}")
                # Fall back to in-memory throttling
        
        # Fallback to in-memory throttling if Redis is not available
        logger.debug(f"Throttling alert: {alert_type}:{severity}")
        return False

    async def reset(self, alert_type: str = None) -> None:
        """
        Reset throttle for specific type or all.

        Args:
            alert_type: Optional specific type to reset, or None for all
        """
        if self.redis_client and alert_type:
            try:
                redis = await self.redis_client.get_client()
                # Use pattern to find and delete keys
                pattern = f"alert:throttle:{alert_type}:*"
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
            except Exception as e:
                logger.error(f"Redis error in reset: {e}")
        elif self.redis_client:
            # This is more complex with Redis - would need to scan all keys
            logger.warning("Resetting all throttles not implemented for Redis")

    async def get_throttle_status(self) -> Dict[str, str]:
        """Get current throttle status for debugging."""
        if self.redis_client:
            try:
                redis = await self.redis_client.get_client()
                # Get all alert throttle keys
                keys = await redis.keys("alert:throttle:*")
                status = {}
                for key in keys:
                    ttl = await redis.ttl(key)
                    if ttl > 0:
                        status[key] = f"expires_in_{ttl}_seconds"
                return status
            except Exception as e:
                logger.error(f"Redis error getting throttle status: {e}")
                return {"error": str(e)}
        else:
            return {"status": "using_fallback_in_memory"}


class AlertPipeline:
    """
    Main pipeline for processing and delivering health alerts.

    Flow:
    1. Receive prediction from ML model
    2. Determine if alert is needed
    3. Generate chatbot explanation (if severe enough)
    4. Route to appropriate channels
    5. Log and track

    Example:
        pipeline = AlertPipeline(chatbot_manager=ChatbotManager())

        # Register handlers for different channels
        pipeline.register_handler(AlertChannel.WEBSOCKET, my_ws_handler)

        # Process predictions
        alert = await pipeline.process_prediction(prediction)
        if alert:
            print(f"Alert sent: {alert.title}")
    """

    def __init__(
        self,
        chatbot_manager: ChatbotManager = None,
        throttle_seconds: int = 300,
        user_profile: dict = None,
    ):
        """
        Initialize the alert pipeline.

        Args:
            chatbot_manager: Optional chatbot manager for explanations
            throttle_seconds: Cooldown between similar alerts
            user_profile: User data for personalization
        """
        self.chatbot = chatbot_manager or ChatbotManager()
        self.throttler = AlertThrottler(throttle_seconds)
        self.user_profile = user_profile or {}

        # Alert history for analytics
        self.alert_history: List[Alert] = []

        # Callback handlers for different channels
        self.handlers: Dict[AlertChannel, Callable] = {}

        # Thread pool executor for sync handlers
        self._executor = ThreadPoolExecutor(max_workers=4)

        logger.info("AlertPipeline initialized")

    def register_handler(self, channel: AlertChannel, handler: Callable) -> None:
        """
        Register a handler for a specific channel.

        Args:
            channel: Alert channel to handle
            handler: Async or sync function to call with Alert
        """
        self.handlers[channel] = handler
        logger.info(f"Registered handler for {channel.value}")

    async def process_prediction(
        self, prediction: PredictionResult, generate_explanation: bool = True
    ) -> Optional[Alert]:
        """
        Process a prediction and generate alert if needed.

        Args:
            prediction: Result from AnomalyDetector
            generate_explanation: Whether to call chatbot for explanation

        Returns:
            Alert if one was generated, None otherwise
        """
        # Check if alert is needed
        if not prediction.requires_alert:
            logger.debug("No alert needed for this prediction")
            return None

        # Determine alert type and severity
        if prediction.rule_anomalies:
            primary_anomaly = prediction.rule_anomalies[0]
            anomaly_type = primary_anomaly.get("anomaly_type", "UNKNOWN")
            severity = primary_anomaly.get("severity", "WARNING")
            raw_value = primary_anomaly.get("value", prediction.hr_current)
            threshold = primary_anomaly.get("threshold", 0)
            recommendation = primary_anomaly.get("recommendation", "")
        else:
            anomaly_type = "ANOMALY"
            severity = prediction.overall_risk
            raw_value = prediction.hr_current
            threshold = 0
            recommendation = "Monitor your vitals and rest."

        # Check throttling
        if not await self.throttler.should_send(str(anomaly_type), severity):
            logger.debug(f"Alert throttled: {anomaly_type}")
            return None

        # Determine channels based on severity
        channels = self._determine_channels(severity)

        # Generate chatbot explanation
        chatbot_explanation = None
        if generate_explanation and severity not in ["INFO", "NORMAL"]:
            chatbot_explanation = await self._generate_explanation(
                anomaly_type=str(anomaly_type),
                severity=severity,
                value=raw_value,
                threshold=threshold,
            )

        # Create alert
        alert = Alert(
            id=f"alert_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{anomaly_type}",
            timestamp=prediction.timestamp,
            anomaly_type=str(anomaly_type),
            severity=severity,
            risk_score=prediction.risk_score,
            title=self._generate_title(str(anomaly_type), severity),
            message=prediction.alert_message
            or f"Health anomaly detected: {anomaly_type}",
            recommendation=recommendation,
            chatbot_explanation=chatbot_explanation,
            channels=channels,
            raw_value=raw_value,
            threshold=threshold,
        )

        # Store in history
        self.alert_history.append(alert)

        # Keep history manageable (last 100 alerts)
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]

        # Deliver to channels
        await self._deliver_alert(alert)

        return alert

    def _determine_channels(self, severity: str) -> List[AlertChannel]:
        """Determine which channels to use based on severity."""
        channel_map = {
            "INFO": [AlertChannel.SILENT_LOG],
            "WARNING": [AlertChannel.IN_APP, AlertChannel.WEBSOCKET],
            "CRITICAL": [
                AlertChannel.IN_APP,
                AlertChannel.PUSH_NOTIFICATION,
                AlertChannel.WEBSOCKET,
            ],
            "EMERGENCY": [
                AlertChannel.IN_APP,
                AlertChannel.PUSH_NOTIFICATION,
                AlertChannel.WEBSOCKET,
                AlertChannel.SMS,
            ],
        }
        return channel_map.get(severity, [AlertChannel.IN_APP])

    def _generate_title(self, anomaly_type: str, severity: str) -> str:
        """Generate alert title with appropriate emoji."""
        severity_emoji = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "CRITICAL": "🔶",
            "EMERGENCY": "🚨",
        }

        type_names = {
            "tachycardia": "High Heart Rate",
            "bradycardia": "Low Heart Rate",
            "hypoxemia": "Low Blood Oxygen",
            "low_hrv": "Low Heart Rate Variability",
            "high_hrv": "Irregular Heart Rhythm",
            "sudden_hr_spike": "Rapid HR Increase",
            "sudden_hr_drop": "Rapid HR Decrease",
            "resting_tachy": "Elevated Resting HR",
        }

        emoji = severity_emoji.get(severity, "")
        name = type_names.get(
            anomaly_type.lower(), anomaly_type.replace("_", " ").title()
        )

        return f"{emoji} {name} Detected"

    async def _generate_explanation(
        self, anomaly_type: str, severity: str, value: float, threshold: float
    ) -> str:
        """Generate chatbot explanation for the anomaly."""

        # First, get quick response (instant fallback)
        quick = get_quick_response(anomaly_type.lower(), value)

        # If chatbot available, get better explanation
        if self.chatbot.is_available():
            try:
                # Build context
                context = PromptContext(
                    anomaly_type=anomaly_type,
                    severity=severity,
                    current_value=value,
                    threshold=threshold,
                    user_name=self.user_profile.get("name", "there"),
                    user_age=self.user_profile.get("age"),
                    is_resting=True,
                    tone=(
                        ResponseTone.URGENT
                        if severity in ["CRITICAL", "EMERGENCY"]
                        else ResponseTone.CONCERNED
                    ),
                )

                system_prompt, user_prompt = get_prompt_for_anomaly(
                    anomaly_type.lower(), severity, context
                )

                response = await self.chatbot.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.7,
                    max_tokens=200,
                )

                if response.success and response.content:
                    return response.content

            except Exception as e:
                logger.error(f"Chatbot explanation failed: {e}")

        # Fall back to quick response
        return quick

    async def _deliver_alert(self, alert: Alert) -> None:
        """Deliver alert to all specified channels (event-loop safe)."""
        delivery_tasks = []

        for channel in alert.channels:
            handler = self.handlers.get(channel)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    # Native async handler
                    delivery_tasks.append(
                        self._deliver_with_timeout(handler, alert, channel)
                    )
                else:
                    # ✅ FIX: Run sync handlers in thread pool
                    delivery_tasks.append(
                        self._deliver_sync_in_thread(handler, alert, channel)
                    )
            else:
                # Default logging
                if channel == AlertChannel.SILENT_LOG:
                    logger.info(f"Alert logged: {alert.title}")
                else:
                    logger.debug(f"No handler for channel {channel.value}")

        # Deliver all channels concurrently
        if delivery_tasks:
            await asyncio.gather(*delivery_tasks, return_exceptions=True)

    async def _deliver_with_timeout(
        self, handler, alert: Alert, channel: AlertChannel, timeout: float = 10.0
    ):
        """Deliver with timeout to prevent hanging."""
        try:
            await asyncio.wait_for(handler(alert), timeout=timeout)
            logger.info(f"Alert delivered via {channel.value}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout delivering alert via {channel.value}")
        except Exception as e:
            logger.error(f"Failed to deliver alert via {channel.value}: {e}")

    async def _deliver_sync_in_thread(
        self, handler, alert: Alert, channel: AlertChannel
    ):
        """Run synchronous handler in thread pool."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(self._executor, handler, alert)
            logger.info(f"Alert delivered via {channel.value} (threaded)")
        except Exception as e:
            logger.error(f"Failed to deliver alert via {channel.value}: {e}")

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """
        Get recent alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries
        """
        alerts = self.alert_history[-limit:]
        result = []
        for a in alerts:
            d = asdict(a)
            # Convert enum values to strings
            d["channels"] = [c.value for c in a.channels]
            result.append(d)
        return result

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Mark an alert as acknowledged.

        Args:
            alert_id: ID of alert to acknowledge

        Returns:
            True if found and acknowledged, False otherwise
        """
        for alert in self.alert_history:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_unacknowledged_count(self) -> int:
        """Get count of unacknowledged alerts."""
        return sum(1 for a in self.alert_history if not a.acknowledged)

    def get_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        if not self.alert_history:
            return {
                "total_alerts": 0,
                "unacknowledged": 0,
                "by_severity": {},
                "by_type": {},
            }

        by_severity = {}
        by_type = {}

        for alert in self.alert_history:
            by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
            by_type[alert.anomaly_type] = by_type.get(alert.anomaly_type, 0) + 1

        return {
            "total_alerts": len(self.alert_history),
            "unacknowledged": self.get_unacknowledged_count(),
            "by_severity": by_severity,
            "by_type": by_type,
        }
