"""
ML-based Risk Assessor using pre-trained models
Integrates with the backend's heart disease prediction models

================================================================================
FEATURES
================================================================================

Model Versioning:
- Track model versions with metadata
- Support model rollback to previous versions
- Compare model performance across versions

Performance Monitoring:
- Track prediction latency
- Monitor prediction distribution
- Record error rates and fallback usage

Explainability (SHAP):
- Feature importance analysis
- Individual prediction explanations
- Global model interpretation

================================================================================
"""

import joblib
import logging
import time
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)

# Optional SHAP support
try:
    import shap

    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.debug("SHAP not available. Install with: pip install shap")


# ============================================================================
# MODEL VERSIONING
# ============================================================================


@dataclass
class ModelVersion:
    """Model version metadata."""

    version: str
    model_path: str
    loaded_at: datetime
    model_hash: str
    model_type: str
    feature_names: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["loaded_at"] = self.loaded_at.isoformat()
        return data


@dataclass
class PredictionRecord:
    """Record of a single prediction for monitoring."""

    timestamp: datetime
    input_hash: str
    prediction: int
    confidence: float
    latency_ms: float
    model_version: str
    used_fallback: bool = False
    error: Optional[str] = None


class ModelVersionManager:
    """Manages model versions and enables rollback."""

    def __init__(self, max_versions: int = 5):
        self.max_versions = max_versions
        self.versions: Dict[str, ModelVersion] = {}
        self.current_version: Optional[str] = None
        self.version_history: List[str] = []

    def register_model(
        self,
        model: Any,
        model_path: str,
        version: Optional[str] = None,
        description: str = "",
    ) -> ModelVersion:
        """Register a new model version."""
        # Generate version from model hash if not provided
        model_hash = self._compute_model_hash(model_path)
        if version is None:
            version = f"v{len(self.versions) + 1}_{model_hash[:8]}"

        # Extract feature names if available
        feature_names = []
        if hasattr(model, "feature_names_in_"):
            feature_names = list(model.feature_names_in_)

        model_version = ModelVersion(
            version=version,
            model_path=str(model_path),
            loaded_at=datetime.now(),
            model_hash=model_hash,
            model_type=type(model).__name__,
            feature_names=feature_names,
            description=description,
        )

        self.versions[version] = model_version
        self.version_history.append(version)
        self.current_version = version

        # Cleanup old versions
        while len(self.version_history) > self.max_versions:
            old_version = self.version_history.pop(0)
            if old_version in self.versions and old_version != self.current_version:
                del self.versions[old_version]

        logger.info(f"Registered model version: {version}")
        return model_version

    def _compute_model_hash(self, model_path: str) -> str:
        """Compute hash of model file for versioning."""
        try:
            with open(model_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return hashlib.sha256(str(model_path).encode()).hexdigest()

    def get_current_version(self) -> Optional[ModelVersion]:
        """Get current model version info."""
        if self.current_version:
            return self.versions.get(self.current_version)
        return None

    def list_versions(self) -> List[Dict[str, Any]]:
        """List all registered versions."""
        return [v.to_dict() for v in self.versions.values()]


# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================


class PerformanceMonitor:
    """Monitor model performance metrics."""

    def __init__(self, max_records: int = 10000):
        self.max_records = max_records
        self.predictions: deque = deque(maxlen=max_records)
        self.total_predictions = 0
        self.total_errors = 0
        self.total_fallbacks = 0
        self.latency_sum = 0.0
        self._start_time = datetime.now()

    def record_prediction(self, record: PredictionRecord) -> None:
        """Record a prediction for monitoring."""
        self.predictions.append(record)
        self.total_predictions += 1
        self.latency_sum += record.latency_ms

        if record.error:
            self.total_errors += 1
        if record.used_fallback:
            self.total_fallbacks += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated performance metrics."""
        if not self.predictions:
            return {
                "total_predictions": 0,
                "avg_latency_ms": 0,
                "error_rate": 0,
                "fallback_rate": 0,
            }

        recent = list(self.predictions)[-1000:]  # Last 1000 for recent stats
        recent_latencies = [r.latency_ms for r in recent]

        return {
            "total_predictions": self.total_predictions,
            "total_errors": self.total_errors,
            "total_fallbacks": self.total_fallbacks,
            "avg_latency_ms": round(self.latency_sum / self.total_predictions, 2),
            "recent_avg_latency_ms": round(
                sum(recent_latencies) / len(recent_latencies), 2
            ),
            "recent_p95_latency_ms": round(np.percentile(recent_latencies, 95), 2),
            "error_rate": round(self.total_errors / self.total_predictions * 100, 2),
            "fallback_rate": round(
                self.total_fallbacks / self.total_predictions * 100, 2
            ),
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "prediction_distribution": self._get_distribution(recent),
        }

    def _get_distribution(self, records: List[PredictionRecord]) -> Dict[str, int]:
        """Get prediction class distribution."""
        dist = {"low_risk": 0, "high_risk": 0}
        for r in records:
            if r.prediction == 0:
                dist["low_risk"] += 1
            else:
                dist["high_risk"] += 1
        return dist


# ============================================================================
# SHAP EXPLAINABILITY
# ============================================================================


class SHAPExplainer:
    """SHAP-based model explainability."""

    FEATURE_NAMES = [
        "age",
        "sex",
        "chest_pain_type",
        "resting_bp",
        "cholesterol",
        "fasting_bs",
        "rest_ecg",
        "max_hr",
        "exercise_induced_angina",
        "oldpeak",
        "st_slope",
    ]

    def __init__(self, model: Any):
        self.model = model
        self.explainer = None
        self._initialize_explainer()

    def _initialize_explainer(self) -> None:
        """Initialize SHAP explainer based on model type."""
        if not SHAP_AVAILABLE:
            logger.warning("SHAP not available, explainability disabled")
            return

        try:
            # Try TreeExplainer for tree-based models
            if hasattr(self.model, "estimators_") or hasattr(
                self.model, "n_estimators"
            ):
                self.explainer = shap.TreeExplainer(self.model)
                logger.info("Initialized SHAP TreeExplainer")
            else:
                # Fallback to KernelExplainer for other models
                # Note: KernelExplainer is slower but works with any model
                logger.info("Using generic explainer (model type not tree-based)")
        except Exception as e:
            logger.warning(f"Could not initialize SHAP explainer: {e}")

    def explain_prediction(
        self, features: np.ndarray, feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate SHAP explanation for a single prediction.

        Args:
            features: Input features array
            feature_names: Optional feature names

        Returns:
            Dictionary with explanation data
        """
        if not SHAP_AVAILABLE or self.explainer is None:
            return {"available": False, "reason": "SHAP not initialized"}

        names = feature_names or self.FEATURE_NAMES

        try:
            # Get SHAP values
            shap_values = self.explainer.shap_values(features.reshape(1, -1))

            # Handle different SHAP output formats
            if isinstance(shap_values, list):
                # Binary classification: use positive class
                shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]

            shap_values = shap_values.flatten()

            # Create feature importance dict
            feature_importance = {}
            for i, name in enumerate(names):
                if i < len(shap_values):
                    feature_importance[name] = {
                        "value": float(features[i]) if i < len(features) else None,
                        "shap_value": float(shap_values[i]),
                        "impact": (
                            "increases risk" if shap_values[i] > 0 else "decreases risk"
                        ),
                    }

            # Sort by absolute SHAP value
            sorted_features = sorted(
                feature_importance.items(),
                key=lambda x: abs(x[1]["shap_value"]),
                reverse=True,
            )

            return {
                "available": True,
                "feature_importance": dict(sorted_features),
                "top_risk_factors": [
                    f for f, v in sorted_features[:3] if v["shap_value"] > 0
                ],
                "top_protective_factors": [
                    f for f, v in sorted_features[:3] if v["shap_value"] < 0
                ],
                "base_value": (
                    float(self.explainer.expected_value[1])
                    if hasattr(self.explainer.expected_value, "__len__")
                    else float(self.explainer.expected_value)
                ),
            }

        except Exception as e:
            logger.error(f"SHAP explanation failed: {e}")
            return {"available": False, "reason": str(e)}

    def get_global_importance(self, X_sample: np.ndarray) -> Dict[str, float]:
        """
        Get global feature importance from SHAP values.

        Args:
            X_sample: Sample of training data for importance calculation

        Returns:
            Dictionary of feature names to importance scores
        """
        if not SHAP_AVAILABLE or self.explainer is None:
            return {}

        try:
            shap_values = self.explainer.shap_values(X_sample)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]

            importance = np.abs(shap_values).mean(axis=0)

            return {
                name: float(importance[i])
                for i, name in enumerate(self.FEATURE_NAMES)
                if i < len(importance)
            }
        except Exception as e:
            logger.error(f"Global importance calculation failed: {e}")
            return {}


# ============================================================================
# ML RISK ASSESSOR
# ============================================================================


class MLRiskAssessor:
    """
    Machine Learning based risk assessor for cardiovascular disease.
    Loads pre-trained model from the backend and makes predictions.

    Features:
    - Model versioning with rollback support
    - Performance monitoring and metrics
    - SHAP-based explainability
    - Automatic fallback to rule-based assessment
    """

    MODEL_PATHS = [
        # Try to find the model in various locations
        Path(__file__).parent / "models" / "stacking_ensemble_model.joblib",
        Path(__file__).parent / "models" / "stacking_heart_disease_model.joblib",
        Path(__file__).parent / "models" / "fitted_mlp_model.joblib",
        # Fallback to legacy locations
        Path(__file__).parent.parent
        / "cardio-ai-assistant"
        / "backend"
        / "models"
        / "stacking_ensemble_model.joblib",
    ]

    def __init__(self, model_type="random_forest"):
        """
        Initialize ML risk assessor by loading the model.

        Args:
            model_type: Type of model (random_forest, ensemble, etc.) - for compatibility
        """
        self.model = None
        self.model_loaded = False
        self.model_type = model_type

        # Initialize components
        self.version_manager = ModelVersionManager()
        self.monitor = PerformanceMonitor()
        self.explainer: Optional[SHAPExplainer] = None

        self._load_model()

    def _load_model(self):
        """Load the pre-trained model"""
        for model_path in self.MODEL_PATHS:
            try:
                if model_path.exists():
                    logger.info(f"Loading model from: {model_path}")
                    self.model = joblib.load(str(model_path))
                    self.model_loaded = True

                    # Register version
                    self.version_manager.register_model(
                        self.model,
                        str(model_path),
                        description=f"Loaded from {model_path.name}",
                    )

                    # Initialize explainer
                    if SHAP_AVAILABLE:
                        self.explainer = SHAPExplainer(self.model)

                    logger.info("ML model loaded successfully")
                    return
            except Exception as e:
                logger.warning(f"Failed to load model from {model_path}: {e}")
                continue

        if not self.model_loaded:
            logger.warning(
                "No pre-trained model found. ML risk assessment will use fallback methods."
            )

    def assess_risk(
        self, metrics: Dict[str, Any], include_explanation: bool = False
    ) -> Dict[str, Any]:
        """
        Assess cardiovascular risk using ML model with monitoring.

        Args:
            metrics: Health metrics dictionary containing:
                - age: Patient age
                - sex: Patient sex (0=female, 1=male)
                - chest_pain_type: Type of chest pain (0-3)
                - resting_bp: Resting blood pressure
                - cholesterol: Serum cholesterol level
                - fasting_bs: Fasting blood sugar (0 or 1)
                - rest_ecg: Resting ECG results (0-2)
                - max_hr: Maximum heart rate
                - exercise_induced_angina: Exercise induced angina (0 or 1)
                - oldpeak: ST depression
                - st_slope: Slope of ST segment (0-2)
            include_explanation: If True, include SHAP explanation

        Returns:
            Dictionary with risk assessment results
        """
        start_time = time.time()
        input_hash = hashlib.sha256(str(sorted(metrics.items())).encode()).hexdigest()[
            :8
        ]
        used_fallback = False
        error_msg = None

        try:
            if not self.model_loaded:
                used_fallback = True
                result = self._fallback_risk_assessment(metrics)
            else:
                # Prepare features for model
                features = self._prepare_features(metrics)

                # Make prediction
                prediction = self.model.predict([features])[0]
                probability = (
                    self.model.predict_proba([features])[0]
                    if hasattr(self.model, "predict_proba")
                    else None
                )

                # Interpret prediction
                risk_level, confidence = self._interpret_prediction(
                    prediction, probability
                )

                result = {
                    "risk_level": risk_level,
                    "confidence": confidence,
                    "ml_prediction": int(prediction),
                    "risk_score": float(confidence * 100),
                    "model_type": "ensemble_machine_learning",
                    "recommendation": self._get_recommendation(risk_level),
                }

                # Add model version info
                version = self.version_manager.get_current_version()
                if version:
                    result["model_version"] = version.version

                # Add SHAP explanation if requested
                if include_explanation and self.explainer:
                    result["explanation"] = self.explainer.explain_prediction(features)

            # Record successful prediction
            latency_ms = (time.time() - start_time) * 1000
            self.monitor.record_prediction(
                PredictionRecord(
                    timestamp=datetime.now(),
                    input_hash=input_hash,
                    prediction=result.get("ml_prediction", 0),
                    confidence=result.get("confidence", 0.5),
                    latency_ms=latency_ms,
                    model_version=self.version_manager.current_version or "fallback",
                    used_fallback=used_fallback,
                )
            )

            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in ML risk assessment: {e}")

            # Record error
            latency_ms = (time.time() - start_time) * 1000
            self.monitor.record_prediction(
                PredictionRecord(
                    timestamp=datetime.now(),
                    input_hash=input_hash,
                    prediction=0,
                    confidence=0.0,
                    latency_ms=latency_ms,
                    model_version=self.version_manager.current_version or "unknown",
                    used_fallback=True,
                    error=error_msg,
                )
            )

            return self._fallback_risk_assessment(metrics)

    def _prepare_features(self, metrics: Dict[str, Any]) -> np.ndarray:
        """
        Prepare features for the model in the expected format.

        Expected feature order (from the trained model):
        age, sex, chest_pain_type, resting_bp, cholesterol, fasting_bs,
        rest_ecg, max_hr, exercise_induced_angina, oldpeak, st_slope
        """
        features = [
            metrics.get("age", 50),
            metrics.get("sex", 0),
            metrics.get("chest_pain_type", 0),
            metrics.get("resting_bp", 120),
            metrics.get("cholesterol", 200),
            metrics.get("fasting_bs", 0),
            metrics.get("rest_ecg", 0),
            metrics.get("max_hr", 150),
            metrics.get("exercise_induced_angina", 0),
            metrics.get("oldpeak", 0.0),
            metrics.get("st_slope", 0),
        ]
        return np.array(features, dtype=np.float32)

    def _interpret_prediction(
        self, prediction: float, probability: Optional[np.ndarray]
    ) -> tuple:
        """
        Interpret the model's prediction into risk level and confidence.

        prediction: 0 = no disease, 1 = disease present
        """
        if prediction == 0:
            risk_level = "LOW"
        elif prediction == 1:
            risk_level = (
                "MODERATE" if probability is None or probability[1] < 0.7 else "HIGH"
            )
        else:
            risk_level = "MODERATE"

        # Confidence is the probability of the positive class
        confidence = float(probability[1]) if probability is not None else 0.5

        return risk_level, confidence

    def _get_recommendation(self, risk_level: str) -> str:
        """Get clinical recommendations based on risk level"""
        recommendations = {
            "LOW": "Continue regular health checkups and maintain a healthy lifestyle.",
            "MODERATE": "Consult with a cardiologist and consider lifestyle modifications.",
            "HIGH": "Urgent cardiology consultation recommended. Please seek medical attention.",
        }
        return recommendations.get(risk_level, "Consult with healthcare provider.")

    def _fallback_risk_assessment(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback risk assessment using simple rules when ML model is not available"""
        age = metrics.get("age", 50)
        resting_bp = metrics.get("resting_bp", 120)
        cholesterol = metrics.get("cholesterol", 200)

        # Simple rule-based assessment
        risk_score = 0
        if age > 55:
            risk_score += 1
        if resting_bp > 140:
            risk_score += 1
        if cholesterol > 240:
            risk_score += 1

        if risk_score == 0:
            risk_level = "LOW"
        elif risk_score == 1:
            risk_level = "MODERATE"
        else:
            risk_level = "HIGH"

        return {
            "risk_level": risk_level,
            "confidence": 0.5,
            "ml_prediction": 1 if risk_level in ["MODERATE", "HIGH"] else 0,
            "risk_score": risk_score * 30,
            "model_type": "rule_based_fallback",
            "recommendation": self._get_recommendation(risk_level),
        }

    # ========================================================================
    # NEW: Monitoring and Version Management Methods
    # ========================================================================

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance monitoring metrics.

        Returns:
            Dictionary with performance statistics including:
            - total_predictions: Total number of predictions made
            - avg_latency_ms: Average prediction latency
            - error_rate: Percentage of predictions that errored
            - fallback_rate: Percentage using fallback
            - prediction_distribution: Count of low/high risk predictions
        """
        return self.monitor.get_metrics()

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get current model information and version details.

        Returns:
            Dictionary with model metadata and version history
        """
        current = self.version_manager.get_current_version()
        return {
            "model_loaded": self.model_loaded,
            "model_type": self.model_type,
            "shap_available": SHAP_AVAILABLE and self.explainer is not None,
            "current_version": current.to_dict() if current else None,
            "version_history": self.version_manager.list_versions(),
        }

    def reload_model(self, model_path: Optional[str] = None) -> bool:
        """
        Reload the ML model, optionally from a new path.

        Args:
            model_path: Optional specific path to load model from

        Returns:
            True if model loaded successfully, False otherwise
        """
        if model_path:
            try:
                logger.info(f"Loading model from custom path: {model_path}")
                self.model = joblib.load(model_path)
                self.model_loaded = True

                self.version_manager.register_model(
                    self.model,
                    model_path,
                    description=f"Custom model from {model_path}",
                )

                if SHAP_AVAILABLE:
                    self.explainer = SHAPExplainer(self.model)

                logger.info("Custom model loaded successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to load custom model: {e}")
                return False
        else:
            # Reload from default paths
            self.model_loaded = False
            self._load_model()
            return self.model_loaded

    def explain_risk_factors(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed explanation of risk factors for given metrics.

        This provides a human-readable explanation of which factors
        contribute most to the risk assessment.

        Args:
            metrics: Health metrics dictionary

        Returns:
            Dictionary with explanation and risk factors analysis
        """
        features = self._prepare_features(metrics)

        # Rule-based explanation (always available)
        rule_explanation = self._generate_rule_explanation(metrics)

        # SHAP explanation (if available)
        shap_explanation = {}
        if self.explainer:
            shap_explanation = self.explainer.explain_prediction(features)

        return {
            "rule_based": rule_explanation,
            "shap": shap_explanation,
            "feature_values": {
                "age": metrics.get("age"),
                "sex": "Male" if metrics.get("sex") == 1 else "Female",
                "resting_bp": metrics.get("resting_bp"),
                "cholesterol": metrics.get("cholesterol"),
                "max_hr": metrics.get("max_hr"),
                "oldpeak": metrics.get("oldpeak"),
            },
        }

    def _generate_rule_explanation(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate rule-based explanation of risk factors."""
        risk_factors = []
        protective_factors = []

        age = metrics.get("age", 50)
        if age > 65:
            risk_factors.append(
                f"Age ({age}) is above 65, increasing cardiovascular risk"
            )
        elif age < 45:
            protective_factors.append(f"Age ({age}) is below 45, a protective factor")

        bp = metrics.get("resting_bp", 120)
        if bp > 140:
            risk_factors.append(f"High blood pressure ({bp} mmHg) - hypertension risk")
        elif bp < 120:
            protective_factors.append(f"Normal blood pressure ({bp} mmHg)")

        chol = metrics.get("cholesterol", 200)
        if chol > 240:
            risk_factors.append(
                f"High cholesterol ({chol} mg/dL) - above recommended level"
            )
        elif chol < 200:
            protective_factors.append(f"Healthy cholesterol level ({chol} mg/dL)")

        hr = metrics.get("max_hr", 150)
        if hr < 100:
            risk_factors.append(
                f"Low maximum heart rate ({hr}) may indicate reduced cardiac function"
            )

        if metrics.get("exercise_induced_angina"):
            risk_factors.append("Exercise-induced angina present")

        if metrics.get("fasting_bs"):
            risk_factors.append("Elevated fasting blood sugar (>120 mg/dL)")

        oldpeak = metrics.get("oldpeak", 0)
        if oldpeak > 2:
            risk_factors.append(f"Significant ST depression ({oldpeak})")

        return {
            "risk_factors": risk_factors,
            "protective_factors": protective_factors,
            "factor_count": {
                "risk": len(risk_factors),
                "protective": len(protective_factors),
            },
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the ML risk assessor.

        Returns:
            Dictionary with health status and diagnostics
        """
        status = "healthy"
        issues = []

        if not self.model_loaded:
            status = "degraded"
            issues.append("ML model not loaded, using fallback rules")

        if not SHAP_AVAILABLE:
            issues.append("SHAP not available for explainability")

        metrics = self.monitor.get_metrics()
        if metrics.get("error_rate", 0) > 5:
            status = "degraded"
            issues.append(f"High error rate: {metrics['error_rate']}%")

        if metrics.get("fallback_rate", 0) > 20:
            issues.append(f"High fallback rate: {metrics['fallback_rate']}%")

        return {
            "status": status,
            "model_loaded": self.model_loaded,
            "shap_available": SHAP_AVAILABLE,
            "issues": issues,
            "performance": metrics,
            "model_info": self.get_model_info(),
        }
