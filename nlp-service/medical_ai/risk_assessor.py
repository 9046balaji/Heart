"""
Risk Assessment Engine
"""

from typing import Dict, List, Tuple
import os
from core.models import HealthMetrics, RiskAssessmentResponse
from core.error_handling import (
    ProcessingError,
    ExternalServiceError,
)  # PHASE 2: Import exception hierarchy

# Conditional import for ML models
try:
    from medical_ai.ml_risk_assessor import MLRiskAssessor

    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    MLRiskAssessor = None
    print(f"ML models not available: {e}")


class RiskAssessor:
    """
    Risk assessment engine for cardiovascular disease risk calculation.
    Uses Framingham Risk Score algorithm as base.
    """

    def __init__(self):
        """Initialize risk assessor"""
        # Framingham coefficients (simplified)
        self.age_coefficient = 0.05
        self.bp_coefficient = 0.01
        self.cholesterol_coefficient = 0.005
        self.smoking_coefficient = 0.3
        self.diabetes_coefficient = 0.2
        self.family_history_coefficient = 0.15
        self.activity_coefficient = -0.001

        # Check if we should use ML models
        self.use_ml = os.getenv("USE_ML_RISK_MODELS", "false").lower() == "true"
        self.ml_assessor = None

        if self.use_ml and ML_AVAILABLE:
            try:
                ml_model_type = os.getenv("ML_RISK_MODEL_TYPE", "random_forest")
                self.ml_assessor = MLRiskAssessor(ml_model_type)
                print(f"ML risk assessor initialized with model: {ml_model_type}")
            except Exception as e:
                print(f"Failed to initialize ML risk assessor: {e}")
                self.use_ml = False

        # PHASE 2B ENHANCEMENT: Risk assessment result caching
        self._assessment_cache = {}  # Key: hash(metrics), Value: RiskAssessmentResponse
        self._cache_hits = 0
        self._cache_misses = 0

    def assess_risk(self, metrics: HealthMetrics) -> RiskAssessmentResponse:
        """
        Calculate cardiovascular disease risk based on health metrics.

        PHASE 2B ENHANCEMENT: Cache risk assessment results to avoid recalculation
        for identical metrics.

        Args:
            metrics: User health metrics

        Returns:
            RiskAssessmentResponse with risk level, score, and recommendations
        """
        # Create cache key from metrics tuple
        cache_key = hash(
            (
                metrics.age,
                metrics.blood_pressure_systolic,
                metrics.blood_pressure_diastolic,
                metrics.cholesterol_total,
                metrics.cholesterol_ldl,
                metrics.cholesterol_hdl,
                metrics.smoking_status,
                metrics.diabetes,
                metrics.family_history_heart_disease,
                metrics.physical_activity_minutes_per_week,
            )
        )

        # Check cache first (avoid recalculation)
        if cache_key in self._assessment_cache:
            self._cache_hits += 1
            return self._assessment_cache[cache_key]

        self._cache_misses += 1

        # Use ML model if enabled and available
        if self.use_ml and self.ml_assessor:
            try:
                result = self.ml_assessor.assess_risk(metrics)
                # Cache the result
                self._assessment_cache[cache_key] = result
                return result
            except Exception as e:
                print(f"ML model failed, falling back to Framingham Risk Score: {e}")

        # Calculate base risk score (0-100)
        risk_score = self._calculate_framingham_score(metrics)

        # Classify risk level
        risk_level, risk_interpretation = self._classify_risk(risk_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, risk_score)

        # Determine consultation urgency
        consultation_urgency = self._determine_urgency(risk_level, metrics)

        result = RiskAssessmentResponse(
            risk_level=risk_level,
            risk_score=min(100, risk_score),  # Cap at 100
            risk_interpretation=risk_interpretation,
            recommendations=recommendations,
            consultation_urgency=consultation_urgency,
        )

        # Cache the result
        self._assessment_cache[cache_key] = result

        # Limit cache size to prevent memory bloat (keep last 500 assessments)
        if len(self._assessment_cache) > 500:
            # Remove oldest entries (FIFO eviction)
            oldest_keys = list(self._assessment_cache.keys())[:50]
            for key in oldest_keys:
                del self._assessment_cache[key]

        return result

    def _calculate_framingham_score(self, metrics: HealthMetrics) -> float:
        """
        Calculate Framingham Risk Score.

        Args:
            metrics: User health metrics

        Returns:
            Risk score (0-100)
        """
        score = 0.0

        # Age factor (strongest predictor)
        if metrics.age < 30:
            score += 0
        elif metrics.age < 40:
            score += 5
        elif metrics.age < 50:
            score += 10
        elif metrics.age < 60:
            score += 15
        else:
            score += 20

        # Blood pressure (if available)
        if metrics.blood_pressure_systolic and metrics.blood_pressure_diastolic:
            sys_bp = metrics.blood_pressure_systolic
            dias_bp = metrics.blood_pressure_diastolic

            if sys_bp < 120 and dias_bp < 80:
                score += 0  # Normal
            elif sys_bp < 130 and dias_bp < 80:
                score += 5  # Elevated
            elif sys_bp < 140 or dias_bp < 90:
                score += 10  # Stage 1 hypertension
            else:
                score += 15  # Stage 2 hypertension

        # Cholesterol (if available)
        if metrics.cholesterol_total:
            total_chol = metrics.cholesterol_total
            if total_chol < 200:
                score += 0  # Desirable
            elif total_chol < 240:
                score += 5  # Borderline high
            else:
                score += 10  # High

        # LDL and HDL
        if metrics.cholesterol_ldl:
            if metrics.cholesterol_ldl < 100:
                score += 0
            elif metrics.cholesterol_ldl < 130:
                score += 3
            elif metrics.cholesterol_ldl < 160:
                score += 6
            else:
                score += 10

        if metrics.cholesterol_hdl:
            if metrics.cholesterol_hdl >= 60:
                score -= 5  # Protective
            elif metrics.cholesterol_hdl >= 40:
                score += 0
            else:
                score += 10

        # Smoking status
        if metrics.smoking_status == "current":
            score += 15
        elif metrics.smoking_status == "former":
            score += 5

        # Diabetes
        if metrics.diabetes:
            score += 15

        # Family history
        if metrics.family_history_heart_disease:
            score += 10

        # Physical activity (protective factor)
        if metrics.physical_activity_minutes_per_week >= 150:
            score -= 10
        elif metrics.physical_activity_minutes_per_week >= 75:
            score -= 5

        return max(0, score)  # Ensure non-negative

    def _classify_risk(self, risk_score: float) -> Tuple[str, str]:
        """
        Classify risk level based on score.

        Args:
            risk_score: Calculated risk score

        Returns:
            Tuple of (risk_level, interpretation)
        """
        if risk_score < 10:
            return "LOW", (
                "Your cardiovascular risk is low. Continue maintaining healthy lifestyle habits "
                "including regular exercise, healthy diet, and stress management."
            )
        elif risk_score < 20:
            return "MODERATE", (
                "Your cardiovascular risk is moderate. Focus on lifestyle modifications such as "
                "increasing physical activity, improving diet, and managing stress. "
                "Consult with your healthcare provider about additional preventive measures."
            )
        else:
            return "HIGH", (
                "Your cardiovascular risk is high. It's important to work closely with your "
                "healthcare provider to develop a comprehensive prevention plan. "
                "Consider medication therapy and intensive lifestyle modifications."
            )

    def _generate_recommendations(
        self, metrics: HealthMetrics, risk_score: float
    ) -> List[str]:
        """
        Generate personalized recommendations.

        Args:
            metrics: User health metrics
            risk_score: Calculated risk score

        Returns:
            List of recommendations
        """
        recommendations = []

        # Age-based recommendations
        if metrics.age >= 60:
            recommendations.append(
                "Schedule regular health screenings every 6-12 months"
            )

        # Blood pressure recommendations
        if metrics.blood_pressure_systolic and metrics.blood_pressure_systolic >= 140:
            recommendations.append("Reduce sodium intake to less than 2,300mg per day")
            recommendations.append(
                "Monitor blood pressure regularly (daily if possible)"
            )
            recommendations.append(
                "Consult your doctor about blood pressure medications"
            )

        # Cholesterol recommendations
        if metrics.cholesterol_total and metrics.cholesterol_total >= 240:
            recommendations.append("Follow a heart-healthy diet low in saturated fats")
            recommendations.append(
                "Increase intake of fruits, vegetables, and whole grains"
            )
            recommendations.append(
                "Consider statin therapy - discuss with your healthcare provider"
            )

        # Smoking recommendations
        if metrics.smoking_status == "current":
            recommendations.append(
                "URGENT: Quit smoking - consult smoking cessation programs"
            )
            recommendations.append(
                "Speak with your doctor about nicotine replacement options"
            )

        # Diabetes recommendations
        if metrics.diabetes:
            recommendations.append("Maintain blood glucose levels within target range")
            recommendations.append("Monitor blood sugar regularly")
            recommendations.append(
                "Work with an endocrinologist or diabetes specialist"
            )

        # Activity recommendations
        if metrics.physical_activity_minutes_per_week < 150:
            recommendations.append(
                "Aim for at least 150 minutes of moderate aerobic activity per week"
            )
            recommendations.append("Incorporate strength training 2-3 times per week")
            recommendations.append("Start gradually if currently sedentary")

        # Family history recommendations
        if metrics.family_history_heart_disease:
            recommendations.append("Inform your doctor about family history")
            recommendations.append(
                "Consider genetic screening if multiple family members affected"
            )

        # General recommendations
        if risk_score < 10:
            recommendations.append("Maintain current lifestyle habits")
            recommendations.append("Annual wellness visits recommended")
        elif risk_score < 20:
            recommendations.append(
                "Schedule consultation with cardiologist for risk assessment"
            )
            recommendations.append(
                "Consider stress management techniques (meditation, yoga)"
            )
        else:
            recommendations.append(
                "URGENT: Schedule immediate consultation with cardiologist"
            )
            recommendations.append(
                "May require medication therapy and intensive monitoring"
            )

        return recommendations[:5]  # Return top 5 recommendations

    def get_cache_stats(self) -> Dict[str, any]:
        """
        PHASE 2B ENHANCEMENT: Get risk assessment cache statistics.

        Returns:
            Dictionary with cache hit rate, size, and performance metrics
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (
            (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_cache_requests": total_requests,
            "cache_hit_rate_percent": hit_rate,
            "cache_size": len(self._assessment_cache),
            "max_cache_size": 500,
        }

    def _determine_urgency(self, risk_level: str, metrics: HealthMetrics) -> str:
        """
        Determine consultation urgency.

        Args:
            risk_level: Risk level classification
            metrics: User health metrics

        Returns:
            Urgency level
        """
        if risk_level == "HIGH":
            if metrics.smoking_status == "current" or metrics.diabetes:
                return "URGENT_IMMEDIATE"
            else:
                return "URGENT_WITHIN_WEEK"
        elif risk_level == "MODERATE":
            return "RECOMMENDED_WITHIN_MONTH"
        else:
            return "ANNUAL_CHECKUP"
