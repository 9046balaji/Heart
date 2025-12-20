"""
Machine Learning Model for Cardiac Anomaly Detection
Uses Isolation Forest for unsupervised anomaly detection.

This module provides ML-based pattern detection that complements
the rule-based system. It can detect subtle anomalies that may not
trigger threshold-based rules.
"""

import numpy as np
import joblib
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Optional: ONNX for faster inference
try:
    import onnxruntime as ort

    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

# Scikit-learn for training
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MLPrediction:
    """
    ML model prediction result.

    Attributes:
        is_anomaly: Whether the input is classified as anomalous
        anomaly_score: Score from -1 to 1 (higher = more anomalous)
        confidence: Confidence level of the prediction (0 to 1)
        model_type: Type of model used for prediction
    """

    is_anomaly: bool
    anomaly_score: float  # -1 to 1 (higher = more anomalous)
    confidence: float  # 0 to 1
    model_type: str  # "isolation_forest", "onnx", or "none"


class CardiacAnomalyModel:
    """
    ML-based cardiac anomaly detection using Isolation Forest.

    Features:
    - Unsupervised learning (no labeled data needed)
    - Fast inference (~1-5ms)
    - Can be exported to ONNX for even faster inference
    - Automatically creates a default model if none exists

    The model learns what "normal" health data looks like and can
    detect deviations from normal patterns.

    Example:
        model = CardiacAnomalyModel()
        features = np.array([[75, 75, 5, 70, 80, 0, 40, 35, 98, 98, 97, 0, 1, 0.77]])
        prediction = model.predict(features)
        print(f"Is anomaly: {prediction.is_anomaly}")
    """

    MODEL_DIR = Path(__file__).parent / "models"
    MODEL_PATH = MODEL_DIR / "cardiac_anomaly_model.joblib"
    SCALER_PATH = MODEL_DIR / "feature_scaler.joblib"
    ONNX_PATH = MODEL_DIR / "cardiac_anomaly_model.onnx"

    def __init__(self):
        """Initialize the model, loading from disk if available."""
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self.onnx_session = None

        # Try to load existing model
        self._load_model()

    def _load_model(self):
        """Load pre-trained model if available."""
        # Try ONNX first (faster)
        if ONNX_AVAILABLE and self.ONNX_PATH.exists():
            try:
                self.onnx_session = ort.InferenceSession(str(self.ONNX_PATH))
                logger.info("Loaded ONNX model for fast inference")
                return
            except Exception as e:
                logger.warning(f"Failed to load ONNX model: {e}")

        # Fall back to sklearn
        if SKLEARN_AVAILABLE:
            if self.MODEL_PATH.exists() and self.SCALER_PATH.exists():
                try:
                    self.model = joblib.load(self.MODEL_PATH)
                    self.scaler = joblib.load(self.SCALER_PATH)
                    logger.info("Loaded sklearn model from disk")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load sklearn model: {e}")

            # Create new model if none exists
            self._create_default_model()

    def _create_default_model(self):
        """Create a default model with synthetic normal data."""
        if not SKLEARN_AVAILABLE:
            logger.error("scikit-learn not available, cannot create model")
            return

        logger.info("Creating default model with synthetic data...")

        # Generate synthetic "normal" health data
        np.random.seed(42)
        n_samples = 1000

        # Normal ranges for each feature (14 features total)
        # [hr_current, hr_mean, hr_std, hr_min, hr_max, hr_trend,
        #  hrv_sdnn, hrv_rmssd, spo2_current, spo2_mean, spo2_min,
        #  steps, is_resting, hr_spo2_ratio]
        synthetic_data = np.column_stack(
            [
                np.random.normal(75, 10, n_samples),  # hr_current (60-90)
                np.random.normal(75, 8, n_samples),  # hr_mean_5min
                np.random.normal(5, 2, n_samples),  # hr_std_5min
                np.random.normal(65, 8, n_samples),  # hr_min_5min
                np.random.normal(85, 10, n_samples),  # hr_max_5min
                np.random.normal(0, 0.5, n_samples),  # hr_trend
                np.random.normal(40, 15, n_samples),  # hrv_sdnn
                np.random.normal(35, 12, n_samples),  # hrv_rmssd
                np.random.normal(97, 1.5, n_samples),  # spo2_current
                np.random.normal(97, 1, n_samples),  # spo2_mean_5min
                np.random.normal(96, 1.5, n_samples),  # spo2_min_5min
                np.random.normal(100, 200, n_samples),  # steps_last_5min
                np.random.choice([0, 1], n_samples, p=[0.7, 0.3]),  # is_resting
                np.random.normal(0.77, 0.1, n_samples),  # hr_spo2_ratio
            ]
        )

        # Clip to reasonable ranges
        synthetic_data[:, 0] = np.clip(synthetic_data[:, 0], 50, 100)  # hr_current
        synthetic_data[:, 6] = np.clip(synthetic_data[:, 6], 10, 80)  # hrv_sdnn
        synthetic_data[:, 8] = np.clip(synthetic_data[:, 8], 94, 100)  # spo2_current

        # Fit scaler
        self.scaler = StandardScaler()
        scaled_data = self.scaler.fit_transform(synthetic_data)

        # Train Isolation Forest
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.05,  # Expect 5% anomalies
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(scaled_data)

        # Save model
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, self.MODEL_PATH)
        joblib.dump(self.scaler, self.SCALER_PATH)

        logger.info(f"Model saved to {self.MODEL_PATH}")

    def predict(self, features: np.ndarray) -> MLPrediction:
        """
        Predict if the input features represent an anomaly.

        Args:
            features: Shape (1, 14) array of extracted features
                      Expected order: [hr_current, hr_mean, hr_std, hr_min,
                                      hr_max, hr_trend, hrv_sdnn, hrv_rmssd,
                                      spo2_current, spo2_mean, spo2_min,
                                      steps, is_resting, hr_spo2_ratio]

        Returns:
            MLPrediction with anomaly status and confidence
        """
        # Use ONNX if available
        if self.onnx_session is not None:
            return self._predict_onnx(features)

        # Fall back to sklearn
        if self.model is not None and self.scaler is not None:
            return self._predict_sklearn(features)

        # No model available - return default
        return MLPrediction(
            is_anomaly=False, anomaly_score=0.0, confidence=0.0, model_type="none"
        )

    def _predict_sklearn(self, features: np.ndarray) -> MLPrediction:
        """Predict using sklearn model."""
        # Scale features
        scaled = self.scaler.transform(features)

        # Get prediction (-1 = anomaly, 1 = normal)
        prediction = self.model.predict(scaled)[0]

        # Get anomaly score (lower = more anomalous)
        # Isolation Forest score_samples returns negative scores for anomalies
        score = self.model.score_samples(scaled)[0]

        # Convert score to 0-1 range (higher = more anomalous)
        # Typical scores range from -0.5 (anomaly) to 0.1 (normal)
        normalized_score = 1 - (score + 0.5) / 0.6
        normalized_score = float(np.clip(normalized_score, 0, 1))

        # Confidence based on how far from decision boundary
        confidence = float(min(abs(score) * 2, 1.0))

        return MLPrediction(
            is_anomaly=(prediction == -1),
            anomaly_score=normalized_score,
            confidence=confidence,
            model_type="isolation_forest",
        )

    def _predict_onnx(self, features: np.ndarray) -> MLPrediction:
        """Predict using ONNX model (faster)."""
        # ONNX inference
        input_name = self.onnx_session.get_inputs()[0].name
        output = self.onnx_session.run(None, {input_name: features.astype(np.float32)})

        prediction = output[0][0]
        score = output[1][0] if len(output) > 1 else 0.5

        return MLPrediction(
            is_anomaly=(prediction == -1),
            anomaly_score=float(score),
            confidence=0.85,
            model_type="onnx",
        )

    def train_on_user_data(self, normal_data: np.ndarray) -> bool:
        """
        Retrain model on user's personal data for better personalization.
        Call this with the user's normal health data.

        Args:
            normal_data: Array of shape (n_samples, 14) with user's normal readings

        Returns:
            True if training successful, False otherwise
        """
        if not SKLEARN_AVAILABLE:
            logger.error("scikit-learn not available")
            return False

        if len(normal_data) < 100:
            logger.warning("Need at least 100 samples to train")
            return False

        # Fit scaler on user data
        self.scaler = StandardScaler()
        scaled_data = self.scaler.fit_transform(normal_data)

        # Retrain model
        self.model = IsolationForest(
            n_estimators=100, contamination=0.05, random_state=42, n_jobs=-1
        )
        self.model.fit(scaled_data)

        # Save
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, self.MODEL_PATH)
        joblib.dump(self.scaler, self.SCALER_PATH)

        logger.info("Model retrained on user data")
        return True

    def get_status(self) -> dict:
        """Get model status information."""
        return {
            "sklearn_available": SKLEARN_AVAILABLE,
            "onnx_available": ONNX_AVAILABLE,
            "model_loaded": self.model is not None,
            "scaler_loaded": self.scaler is not None,
            "onnx_loaded": self.onnx_session is not None,
            "model_path": str(self.MODEL_PATH),
            "model_exists": self.MODEL_PATH.exists(),
        }
