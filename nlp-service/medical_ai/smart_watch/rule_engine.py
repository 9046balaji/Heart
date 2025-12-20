"""
Rule-Based Anomaly Detection Engine
Fast, interpretable rules for immediate health alerts.

This module provides threshold-based detection that runs in <1ms
and provides explainable results with medical context.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

from .feature_extractor import HealthFeatures


class Severity(Enum):
    """Alert severity levels matching clinical urgency."""

    NORMAL = 0
    INFO = 1
    WARNING = 2
    CRITICAL = 3
    EMERGENCY = 4


class AnomalyType(Enum):
    """Types of cardiac anomalies that can be detected."""

    NORMAL = "normal"
    TACHYCARDIA = "tachycardia"  # High HR
    BRADYCARDIA = "bradycardia"  # Low HR
    HYPOXEMIA = "hypoxemia"  # Low SpO2
    LOW_HRV = "low_hrv"  # Low heart rate variability
    HIGH_HRV = "high_hrv"  # Irregular rhythm
    SUDDEN_HR_SPIKE = "sudden_hr_spike"  # Rapid HR increase
    SUDDEN_HR_DROP = "sudden_hr_drop"  # Rapid HR decrease
    RESTING_TACHYCARDIA = "resting_tachy"  # High HR while resting


@dataclass
class Anomaly:
    """
    Detected anomaly with metadata.

    Attributes:
        anomaly_type: Type of anomaly detected
        severity: How urgent/serious this anomaly is
        confidence: How confident the detection is (0.0 to 1.0)
        value: The actual value that triggered the anomaly
        threshold: The threshold that was exceeded
        message: Human-readable description of the anomaly
        recommendation: Suggested action for the user
    """

    anomaly_type: AnomalyType
    severity: Severity
    confidence: float  # 0.0 to 1.0
    value: float  # The anomalous value
    threshold: float  # The threshold that was exceeded
    message: str  # Human-readable description
    recommendation: str  # What the user should do


class RuleEngine:
    """
    Rule-based anomaly detection with medical thresholds.
    Provides instant detection (< 1ms) with explainable results.

    The engine uses clinically-informed thresholds that can be
    personalized based on user profile (age, athletic status, etc.).

    Example:
        engine = RuleEngine(user_profile={'age': 35, 'is_athlete': False})
        anomalies = engine.analyze(features)
        status = engine.get_overall_status(anomalies)
    """

    def __init__(self, user_profile: dict = None):
        """
        Initialize with optional user profile for personalized thresholds.

        Args:
            user_profile: Dictionary containing user data for personalization
                {
                    'age': 35,
                    'max_hr': 185,  # 220 - age by default
                    'resting_hr': 65,
                    'is_athlete': False
                }
        """
        self.profile = user_profile or {}

        # Calculate age-adjusted max HR if age is provided
        age = self.profile.get("age", 30)
        default_max_hr = 220 - age

        # Default thresholds (can be personalized)
        self.thresholds = {
            # Heart Rate thresholds
            "hr_critical_high": self.profile.get("max_hr", default_max_hr),
            "hr_warning_high": 120,
            "hr_normal_high": 100,
            "hr_normal_low": 60,
            "hr_warning_low": 50,
            "hr_critical_low": 40,
            # Blood oxygen thresholds
            "spo2_normal": 95,
            "spo2_warning": 92,
            "spo2_critical": 88,
            # Heart Rate Variability thresholds
            "hrv_low_warning": 20,
            "hrv_low_critical": 10,
            "hrv_high_warning": 100,
            # Sudden change thresholds (BPM change per minute)
            "hr_spike_threshold": 30,
            "hr_drop_threshold": 25,
        }

        # Adjust for athletes (they typically have lower resting HR)
        if self.profile.get("is_athlete"):
            self.thresholds["hr_normal_low"] = 50
            self.thresholds["hr_warning_low"] = 40
            self.thresholds["hr_critical_low"] = 35

    def analyze(self, features: HealthFeatures) -> List[Anomaly]:
        """
        Analyze features and return list of detected anomalies.
        Runs all rules and returns all triggered anomalies.

        Args:
            features: Extracted health features to analyze

        Returns:
            List of Anomaly objects for all detected issues
        """
        anomalies = []

        # Rule 1: Heart Rate (Tachycardia / Bradycardia)
        hr_anomaly = self._check_heart_rate(features)
        if hr_anomaly:
            anomalies.append(hr_anomaly)

        # Rule 2: Blood Oxygen (Hypoxemia)
        spo2_anomaly = self._check_spo2(features)
        if spo2_anomaly:
            anomalies.append(spo2_anomaly)

        # Rule 3: Heart Rate Variability
        hrv_anomaly = self._check_hrv(features)
        if hrv_anomaly:
            anomalies.append(hrv_anomaly)

        # Rule 4: Sudden Changes
        spike_anomaly = self._check_sudden_changes(features)
        if spike_anomaly:
            anomalies.append(spike_anomaly)

        # Rule 5: Resting Tachycardia (context-aware)
        resting_anomaly = self._check_resting_context(features)
        if resting_anomaly:
            anomalies.append(resting_anomaly)

        return anomalies

    def _check_heart_rate(self, features: HealthFeatures) -> Optional[Anomaly]:
        """Check for abnormal heart rate (tachycardia/bradycardia)."""
        hr = features.hr_current

        # Critical High
        if hr >= self.thresholds["hr_critical_high"]:
            return Anomaly(
                anomaly_type=AnomalyType.TACHYCARDIA,
                severity=Severity.EMERGENCY,
                confidence=0.95,
                value=hr,
                threshold=self.thresholds["hr_critical_high"],
                message=f"🚨 CRITICAL: Heart rate extremely high at {hr:.0f} bpm",
                recommendation="Stop activity immediately. Sit down. Seek medical attention if persists.",
            )

        # Warning High
        if hr >= self.thresholds["hr_warning_high"]:
            return Anomaly(
                anomaly_type=AnomalyType.TACHYCARDIA,
                severity=Severity.WARNING,
                confidence=0.85,
                value=hr,
                threshold=self.thresholds["hr_warning_high"],
                message=f"⚠️ Heart rate elevated at {hr:.0f} bpm",
                recommendation="Consider slowing down. Take deep breaths.",
            )

        # Critical Low
        if hr <= self.thresholds["hr_critical_low"]:
            return Anomaly(
                anomaly_type=AnomalyType.BRADYCARDIA,
                severity=Severity.EMERGENCY,
                confidence=0.95,
                value=hr,
                threshold=self.thresholds["hr_critical_low"],
                message=f"🚨 CRITICAL: Heart rate dangerously low at {hr:.0f} bpm",
                recommendation="Seek immediate medical attention.",
            )

        # Warning Low
        if hr <= self.thresholds["hr_warning_low"]:
            return Anomaly(
                anomaly_type=AnomalyType.BRADYCARDIA,
                severity=Severity.WARNING,
                confidence=0.80,
                value=hr,
                threshold=self.thresholds["hr_warning_low"],
                message=f"⚠️ Heart rate low at {hr:.0f} bpm",
                recommendation="Monitor closely. Normal for athletes or during sleep.",
            )

        return None

    def _check_spo2(self, features: HealthFeatures) -> Optional[Anomaly]:
        """Check for low blood oxygen (hypoxemia)."""
        spo2 = features.spo2_current

        # Critical
        if spo2 < self.thresholds["spo2_critical"]:
            return Anomaly(
                anomaly_type=AnomalyType.HYPOXEMIA,
                severity=Severity.EMERGENCY,
                confidence=0.95,
                value=spo2,
                threshold=self.thresholds["spo2_critical"],
                message=f"🚨 CRITICAL: Blood oxygen dangerously low at {spo2:.0f}%",
                recommendation="Seek immediate medical attention. Possible respiratory issue.",
            )

        # Warning
        if spo2 < self.thresholds["spo2_warning"]:
            return Anomaly(
                anomaly_type=AnomalyType.HYPOXEMIA,
                severity=Severity.WARNING,
                confidence=0.85,
                value=spo2,
                threshold=self.thresholds["spo2_warning"],
                message=f"⚠️ Blood oxygen below normal at {spo2:.0f}%",
                recommendation="Take deep breaths. Move to fresh air. Monitor closely.",
            )

        return None

    def _check_hrv(self, features: HealthFeatures) -> Optional[Anomaly]:
        """Check heart rate variability."""
        hrv = features.hrv_sdnn

        # Very Low HRV (potential cardiac stress)
        if hrv > 0 and hrv < self.thresholds["hrv_low_critical"]:
            return Anomaly(
                anomaly_type=AnomalyType.LOW_HRV,
                severity=Severity.WARNING,
                confidence=0.75,
                value=hrv,
                threshold=self.thresholds["hrv_low_critical"],
                message=f"⚠️ Very low heart rate variability ({hrv:.1f}ms)",
                recommendation="May indicate stress or fatigue. Consider rest.",
            )

        # High HRV (potential irregular rhythm)
        if hrv > self.thresholds["hrv_high_warning"]:
            return Anomaly(
                anomaly_type=AnomalyType.HIGH_HRV,
                severity=Severity.INFO,
                confidence=0.70,
                value=hrv,
                threshold=self.thresholds["hrv_high_warning"],
                message=f"ℹ️ High heart rate variability ({hrv:.1f}ms)",
                recommendation="May indicate irregular rhythm. Consult doctor if frequent.",
            )

        return None

    def _check_sudden_changes(self, features: HealthFeatures) -> Optional[Anomaly]:
        """Check for sudden HR changes (spikes or drops)."""
        # HR Trend is in BPM per sample, multiply by 60 for per-minute rate
        trend_per_min = features.hr_trend * 60

        # Sudden spike
        if trend_per_min > self.thresholds["hr_spike_threshold"]:
            return Anomaly(
                anomaly_type=AnomalyType.SUDDEN_HR_SPIKE,
                severity=Severity.WARNING,
                confidence=0.80,
                value=trend_per_min,
                threshold=self.thresholds["hr_spike_threshold"],
                message=f"⚠️ Rapid heart rate increase (+{trend_per_min:.0f} bpm/min)",
                recommendation="Slow down activity. Take a break.",
            )

        # Sudden drop
        if trend_per_min < -self.thresholds["hr_drop_threshold"]:
            return Anomaly(
                anomaly_type=AnomalyType.SUDDEN_HR_DROP,
                severity=Severity.INFO,
                confidence=0.75,
                value=abs(trend_per_min),
                threshold=self.thresholds["hr_drop_threshold"],
                message=f"ℹ️ Rapid heart rate decrease ({trend_per_min:.0f} bpm/min)",
                recommendation="Normal during cooldown. Monitor if unexpected.",
            )

        return None

    def _check_resting_context(self, features: HealthFeatures) -> Optional[Anomaly]:
        """Check HR in context of activity (resting vs active)."""
        # High HR while resting is concerning
        if (
            features.is_resting
            and features.hr_current > self.thresholds["hr_normal_high"]
        ):
            return Anomaly(
                anomaly_type=AnomalyType.RESTING_TACHYCARDIA,
                severity=Severity.WARNING,
                confidence=0.85,
                value=features.hr_current,
                threshold=self.thresholds["hr_normal_high"],
                message=f"⚠️ Elevated resting heart rate ({features.hr_current:.0f} bpm while inactive)",
                recommendation="May indicate stress, dehydration, or illness. Rest and hydrate.",
            )

        return None

    def get_overall_status(self, anomalies: List[Anomaly]) -> dict:
        """
        Get overall health status summary.

        Args:
            anomalies: List of detected anomalies

        Returns:
            Dictionary with status, color, message, severity, and anomaly count
        """
        if not anomalies:
            return {
                "status": "NORMAL",
                "color": "green",
                "message": "✅ All vitals normal",
                "severity": Severity.NORMAL.value,
            }

        # Find highest severity
        max_severity = max(a.severity.value for a in anomalies)

        status_map = {
            Severity.INFO.value: ("INFO", "blue", "ℹ️ Minor observations"),
            Severity.WARNING.value: ("WARNING", "yellow", "⚠️ Attention needed"),
            Severity.CRITICAL.value: ("CRITICAL", "orange", "🔶 Immediate attention"),
            Severity.EMERGENCY.value: ("EMERGENCY", "red", "🚨 Seek medical help"),
        }

        status, color, message = status_map.get(max_severity, ("UNKNOWN", "gray", "?"))

        return {
            "status": status,
            "color": color,
            "message": message,
            "severity": max_severity,
            "anomaly_count": len(anomalies),
        }

    def get_thresholds(self) -> dict:
        """Get current threshold values."""
        return self.thresholds.copy()

    def update_threshold(self, key: str, value: float) -> bool:
        """
        Update a specific threshold.

        Args:
            key: Threshold key to update
            value: New threshold value

        Returns:
            True if updated successfully, False if key not found
        """
        if key in self.thresholds:
            self.thresholds[key] = value
            return True
        return False
