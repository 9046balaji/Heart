"""
Main Anomaly Detection Engine
Combines rule-based and ML-based detection for comprehensive analysis.

This is the core prediction system that processes incoming health data
and returns structured predictions with risk scores and recommendations.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from .feature_extractor import FeatureExtractor, HealthFeatures
from .rule_engine import RuleEngine, Anomaly, Severity, AnomalyType
from .ml_model import CardiacAnomalyModel, MLPrediction

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """
    Complete prediction result from the anomaly detector.
    
    This dataclass contains all the information about a health prediction,
    including rule-based analysis, ML predictions, and combined risk assessment.
    """
    timestamp: str
    device_id: str
    
    # Input Values
    hr_current: float
    spo2_current: float
    
    # Rule-Based Results
    rule_anomalies: List[Dict]
    rule_status: Dict
    
    # ML Results
    ml_prediction: Dict
    
    # Combined Result
    overall_risk: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    risk_score: float  # 0.0 to 1.0
    requires_alert: bool
    alert_message: Optional[str]
    recommendations: List[str]


class AnomalyDetector:
    """
    Main anomaly detection engine.
    
    Combines:
    1. Rule Engine - Fast, interpretable threshold checks (<1ms)
    2. ML Model - Pattern-based anomaly detection (5-15ms)
    
    The detector maintains a rolling buffer of health data and uses
    both systems to provide comprehensive health monitoring.
    
    Example:
        detector = AnomalyDetector(user_profile={'age': 35, 'is_athlete': False})
        
        # Feed data continuously
        for reading in readings:
            result = detector.analyze(
                device_id="watch_123",
                hr=reading['hr'],
                spo2=reading['spo2']
            )
            if result.requires_alert:
                print(f"Alert: {result.alert_message}")
    """
    
    def __init__(self, user_profile: dict = None):
        """
        Initialize the detector.
        
        Args:
            user_profile: Optional user data for personalized thresholds
                {
                    'age': 35,
                    'max_hr': 185,
                    'resting_hr': 65,
                    'is_athlete': False
                }
        """
        self.user_profile = user_profile or {}
        self.feature_extractor = FeatureExtractor()
        self.rule_engine = RuleEngine(user_profile)
        self.ml_model = CardiacAnomalyModel()
        
        # NEW: Initialize Redis store
        from core.services.redis_vitals_store import RedisVitalsStore
        self.vitals_store = RedisVitalsStore()
        
        logger.info("AnomalyDetector initialized")
    
    def analyze(
        self,
        device_id: str,
        hr: float,
        spo2: float = 98.0,
        steps: int = 0,
        ibi: float = None
    ) -> PredictionResult:
        """
        Analyze incoming health data and return prediction.
        
        This method:
        1. Adds the sample to the rolling buffer
        2. Extracts features if enough data available
        3. Runs rule-based checks
        4. Runs ML model prediction
        5. Combines results into a final risk assessment
        
        Args:
            device_id: Unique device identifier
            hr: Heart rate in BPM
            spo2: Blood oxygen percentage (default: 98.0)
            steps: Steps in this sample period (default: 0)
            ibi: Inter-beat interval in ms (optional)
        
        Returns:
            PredictionResult with all analysis details
        """
        # 1. Add sample to Redis (persistent storage)
        current_reading = {
            "hr": hr, 
            "spo2": spo2, 
            "steps": steps, 
            "ibi": ibi,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.vitals_store.add_reading(device_id, current_reading)
        
        # 2. Fetch full history from Redis (Stateless!)
        history = self.vitals_store.get_history(device_id)
        
        # 3. Rehydrate feature extractor with full history
        self.feature_extractor.clear()  # Clear local buffer
        for reading in history:
            self.feature_extractor.add_sample(
                reading["hr"], 
                reading["spo2"], 
                reading["steps"], 
                reading["ibi"]
            )
        
        # 4. Extract features
        features = self.feature_extractor.extract_features()
        
        # 3. Run rule engine (always works, even with limited data)
        rule_anomalies = []
        rule_status = {
            'status': 'INITIALIZING', 
            'color': 'gray', 
            'message': 'Collecting data...'
        }
        
        if features:
            rule_anomalies = self.rule_engine.analyze(features)
            rule_status = self.rule_engine.get_overall_status(rule_anomalies)
        else:
            # Quick check even without full features
            quick_anomalies = self._quick_threshold_check(hr, spo2)
            if quick_anomalies:
                rule_anomalies = quick_anomalies
                rule_status = self.rule_engine.get_overall_status(quick_anomalies)
        
        # 4. Run ML model (if we have features)
        ml_prediction = MLPrediction(
            is_anomaly=False,
            anomaly_score=0.0,
            confidence=0.0,
            model_type="none"
        )
        
        if features:
            model_input = self.feature_extractor.to_model_input(features)
            ml_prediction = self.ml_model.predict(model_input)
        
        # 5. Combine results
        overall_risk, risk_score = self._calculate_combined_risk(
            rule_anomalies, ml_prediction
        )
        
        # 6. Determine if alert is needed
        requires_alert = risk_score > 0.5 or any(
            a.severity.value >= Severity.WARNING.value for a in rule_anomalies
        )
        
        # 7. Build alert message
        alert_message = None
        if requires_alert and rule_anomalies:
            highest = max(rule_anomalies, key=lambda a: a.severity.value)
            alert_message = highest.message
        
        # 8. Collect recommendations
        recommendations = list(set(a.recommendation for a in rule_anomalies))
        
        return PredictionResult(
            timestamp=datetime.utcnow().isoformat() + "Z",
            device_id=device_id,
            hr_current=hr,
            spo2_current=spo2,
            rule_anomalies=[self._anomaly_to_dict(a) for a in rule_anomalies],
            rule_status=rule_status,
            ml_prediction=asdict(ml_prediction),
            overall_risk=overall_risk,
            risk_score=risk_score,
            requires_alert=requires_alert,
            alert_message=alert_message,
            recommendations=recommendations
        )
    
    def _anomaly_to_dict(self, anomaly: Anomaly) -> Dict:
        """Convert Anomaly dataclass to dict, handling enum values."""
        return {
            'anomaly_type': anomaly.anomaly_type.value,
            'severity': anomaly.severity.name,
            'confidence': anomaly.confidence,
            'value': anomaly.value,
            'threshold': anomaly.threshold,
            'message': anomaly.message,
            'recommendation': anomaly.recommendation
        }
    
    def _quick_threshold_check(self, hr: float, spo2: float) -> List[Anomaly]:
        """
        Quick threshold check without full features.
        Used when we don't have enough data for full feature extraction.
        Only checks for emergency-level conditions.
        """
        anomalies = []
        
        # Emergency thresholds only
        if hr > 180:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.TACHYCARDIA,
                severity=Severity.EMERGENCY,
                confidence=0.95,
                value=hr,
                threshold=180,
                message=f"🚨 CRITICAL: Heart rate at {hr:.0f} bpm",
                recommendation="Stop activity. Seek help if symptoms present."
            ))
        
        if hr < 40:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.BRADYCARDIA,
                severity=Severity.EMERGENCY,
                confidence=0.95,
                value=hr,
                threshold=40,
                message=f"🚨 CRITICAL: Heart rate at {hr:.0f} bpm",
                recommendation="Seek immediate medical attention."
            ))
        
        if spo2 < 90:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.HYPOXEMIA,
                severity=Severity.EMERGENCY,
                confidence=0.95,
                value=spo2,
                threshold=90,
                message=f"🚨 CRITICAL: Blood oxygen at {spo2:.0f}%",
                recommendation="Seek immediate medical attention."
            ))
        
        return anomalies
    
    def _calculate_combined_risk(
        self,
        rule_anomalies: List[Anomaly],
        ml_prediction: MLPrediction
    ) -> tuple:
        """
        Calculate overall risk from rule and ML results.
        
        Combines rule-based severity with ML anomaly score, weighting
        rules higher since they are more interpretable and clinically validated.
        
        Returns:
            Tuple of (risk_level, risk_score)
        """
        # Start with rule-based severity
        rule_score = 0.0
        if rule_anomalies:
            max_severity = max(a.severity.value for a in rule_anomalies)
            rule_score = max_severity / 4.0  # Normalize to 0-1
        
        # Add ML score (weighted lower since rules are more reliable)
        ml_score = ml_prediction.anomaly_score * ml_prediction.confidence
        
        # Combined score (rules weighted higher: 70% rules, 30% ML)
        combined_score = (rule_score * 0.7) + (ml_score * 0.3)
        combined_score = min(combined_score, 1.0)
        
        # Map to risk level
        if combined_score >= 0.75:
            risk_level = "CRITICAL"
        elif combined_score >= 0.5:
            risk_level = "HIGH"
        elif combined_score >= 0.25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return risk_level, combined_score
    
    def get_status(self) -> dict:
        """Get current detector status."""
        return {
            'buffer_size': self.feature_extractor.get_buffer_size(),
            'min_samples_needed': 30,
            'ready': self.feature_extractor.is_ready(),
            'ml_model_status': self.ml_model.get_status(),
            'thresholds': self.rule_engine.get_thresholds()
        }
    
    def reset(self) -> None:
        """Reset the detector state (clear buffers)."""
        self.feature_extractor.clear()
        logger.info("AnomalyDetector reset")
