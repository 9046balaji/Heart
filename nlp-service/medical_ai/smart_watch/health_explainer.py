"""
Health Explainer - Main orchestrator combining ML + Chatbot

This is the main entry point for the prediction system.
It combines anomaly detection, alert pipeline, and chatbot
into a unified interface.
"""

import logging
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, asdict

from .anomaly_detector import AnomalyDetector, PredictionResult
from .alert_pipeline import AlertPipeline, Alert, AlertChannel
from .chatbot_connector import ChatbotManager
from .prompt_templates import get_normal_response

logger = logging.getLogger(__name__)


@dataclass
class HealthAnalysis:
    """
    Complete health analysis result.

    Combines ML prediction, alert information, and chatbot explanation
    into a single comprehensive response.
    """

    # Prediction Data
    prediction: Dict[str, Any]

    # Alert (if generated)
    alert: Optional[Dict[str, Any]]

    # Chatbot Response (if requested)
    explanation: Optional[str]

    # Status
    status: str  # "normal", "warning", "alert", "emergency"

    # Metadata
    processing_time_ms: float


class HealthExplainer:
    """
    Main orchestrator for the health prediction system.

    Combines:
    - AnomalyDetector (ML)
    - AlertPipeline (routing)
    - ChatbotManager (explanations)

    This is the primary class to use for health data analysis.
    It provides a simple interface that handles all the complexity
    of ML prediction, alert routing, and natural language generation.

    Example:
        explainer = HealthExplainer(user_profile={'name': 'John', 'age': 35})

        # Analyze health data
        result = await explainer.analyze(
            device_id='watch_1',
            hr=145,
            spo2=94
        )

        # Get explanation
        print(result.explanation)

        # Check if alert was triggered
        if result.alert:
            print(f"Alert: {result.alert['title']}")
    """

    def __init__(
        self,
        user_profile: dict = None,
        enable_chatbot: bool = True,
        alert_throttle_seconds: int = 300,
    ):
        """
        Initialize the health explainer.

        Args:
            user_profile: User data for personalization
                {
                    'name': 'John',
                    'age': 35,
                    'max_hr': 185,
                    'is_athlete': False
                }
            enable_chatbot: Whether to use chatbot for explanations
            alert_throttle_seconds: Cooldown between similar alerts
        """
        self.user_profile = user_profile or {}
        self.enable_chatbot = enable_chatbot

        # Initialize components
        self.detector = AnomalyDetector(user_profile)
        self.chatbot = ChatbotManager() if enable_chatbot else None
        self.pipeline = AlertPipeline(
            chatbot_manager=self.chatbot,
            throttle_seconds=alert_throttle_seconds,
            user_profile=user_profile,
        )

        logger.info("HealthExplainer initialized")

    def register_alert_handler(self, channel: AlertChannel, handler: Callable) -> None:
        """
        Register a handler for alert delivery.

        Args:
            channel: Alert channel to handle
            handler: Function to call with Alert object
        """
        self.pipeline.register_handler(channel, handler)

    async def analyze(
        self,
        device_id: str,
        hr: float,
        spo2: float = 98.0,
        steps: int = 0,
        ibi: float = None,
        generate_explanation: bool = True,
    ) -> HealthAnalysis:
        """
        Analyze health data and return comprehensive result.

        This is the main method for health analysis. It:
        1. Runs ML prediction on the incoming data
        2. Processes alerts if needed
        3. Generates natural language explanations
        4. Returns a unified result

        Args:
            device_id: Device identifier
            hr: Heart rate in BPM
            spo2: Blood oxygen percentage
            steps: Step count
            ibi: Inter-beat interval (optional)
            generate_explanation: Whether to generate chatbot explanation

        Returns:
            HealthAnalysis with prediction, alert, and explanation
        """
        start = time.time()

        # 1. Run ML prediction
        prediction = await self.detector.analyze(
            device_id=device_id, hr=hr, spo2=spo2, steps=steps, ibi=ibi
        )

        # 2. Process through alert pipeline
        alert = None
        if prediction.requires_alert:
            alert = await self.pipeline.process_prediction(
                prediction,
                generate_explanation=generate_explanation and self.enable_chatbot,
            )

        # 3. Get explanation
        explanation = None
        if alert and alert.chatbot_explanation:
            explanation = alert.chatbot_explanation
        elif generate_explanation and not prediction.requires_alert:
            # Generate a positive message for normal readings
            explanation = self._get_normal_message(hr, spo2)

        # 4. Determine status
        status = self._determine_status(prediction, alert)

        # Calculate processing time
        processing_time = (time.time() - start) * 1000

        # Convert alert to dict if present
        alert_dict = None
        if alert:
            alert_dict = asdict(alert)
            alert_dict["channels"] = [c.value for c in alert.channels]

        return HealthAnalysis(
            prediction=asdict(prediction),
            alert=alert_dict,
            explanation=explanation,
            status=status,
            processing_time_ms=processing_time,
        )

    def _determine_status(
        self, prediction: PredictionResult, alert: Optional[Alert]
    ) -> str:
        """Determine overall status string."""
        if alert:
            severity = alert.severity
            if severity in ["EMERGENCY", "CRITICAL"]:
                return "emergency"
            elif severity == "WARNING":
                return "alert"
            else:
                return "warning"
        elif prediction.risk_score > 0.25:
            return "warning"
        else:
            return "normal"

    def _get_normal_message(self, hr: float, spo2: float) -> str:
        """Get a positive message for normal readings."""
        name = self.user_profile.get("name", "")
        return get_normal_response(name, hr, spo2)

    async def ask_question(self, question: str, include_vitals: bool = True) -> str:
        """
        Allow user to ask a health question to the chatbot.

        Args:
            question: User's question
            include_vitals: Whether to include recent vitals in context

        Returns:
            Chatbot response
        """
        if not self.chatbot or not self.chatbot.is_available():
            return "I'm unable to answer questions right now. Please try again later."

        # Build context
        vitals_context = ""
        if include_vitals:
            status = self.detector.get_status()
            if status["ready"]:
                features = self.detector.feature_extractor.extract_features()
                if features:
                    vitals_context = f"""
Current vitals:
- Heart Rate: {features.hr_current:.0f} bpm
- SpO2: {features.spo2_current:.0f}%
- HRV: {features.hrv_sdnn:.1f} ms
- Resting: {'Yes' if features.is_resting else 'No'}
"""

        system_prompt = """You are CardioAI, a friendly cardiac health assistant.
Answer the user's question helpfully but always remind them to consult a doctor for medical advice.
Keep responses concise and actionable."""

        user_prompt = f"""User question: {question}

{vitals_context}

Provide a helpful, clear response."""

        response = await self.chatbot.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=300,
        )

        if response.success:
            return response.content
        else:
            return "I'm having trouble answering that. Please try again."

    def get_status(self) -> Dict[str, Any]:
        """
        Get system status.

        Returns information about all components including
        detector readiness, chatbot availability, and alert stats.
        """
        return {
            "detector": self.detector.get_status(),
            "chatbot": (
                self.chatbot.get_status() if self.chatbot else {"available": False}
            ),
            "alerts": self.pipeline.get_stats(),
            "user_profile": bool(self.user_profile),
        }

    def get_recent_alerts(self, limit: int = 10) -> list:
        """Get recent alerts."""
        return self.pipeline.get_recent_alerts(limit)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        return self.pipeline.acknowledge_alert(alert_id)

    def reset(self) -> None:
        """Reset the explainer state."""
        self.detector.reset()
        self.pipeline.throttler.reset()


# ============== CONVENIENCE FUNCTION ==============


async def create_health_explainer(
    gemini_api_key: str = None, user_profile: dict = None
) -> HealthExplainer:
    """
    Factory function to create a configured HealthExplainer.

    Convenience function that sets up the API key and creates
    a ready-to-use explainer instance.

    Args:
        gemini_api_key: Optional Gemini API key
        user_profile: Optional user profile for personalization

    Returns:
        Configured HealthExplainer instance

    Example:
        import os
        explainer = await create_health_explainer(
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            user_profile={'name': 'John', 'age': 35}
        )
    """
    import os

    # Set API key if provided
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key

    return HealthExplainer(user_profile=user_profile)
