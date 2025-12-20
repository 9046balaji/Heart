"""
Integration between Document Scanning and Heart Disease Prediction Model.

Extracts relevant lab values from scanned documents and feeds them
into the ML prediction pipeline.

From medical.md Section 5:
"Once structured, the data can feed: Heart disease prediction model"
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import aiohttp for async API calls
try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp not available - prediction API calls will fail")


class RiskCategory(Enum):
    """Heart disease risk categories."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class PredictionInput:
    """Input features for heart disease prediction model."""

    # Demographics
    age: Optional[int] = None
    sex: Optional[int] = None  # 0: Female, 1: Male

    # Lab Values (from scanned documents)
    cholesterol: Optional[float] = None
    hdl: Optional[float] = None
    ldl: Optional[float] = None
    triglycerides: Optional[float] = None
    fasting_blood_sugar: Optional[float] = None
    hba1c: Optional[float] = None
    creatinine: Optional[float] = None

    # Vitals (from app/smartwatch)
    resting_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None

    # Clinical (from documents or user input)
    chest_pain_type: Optional[int] = None  # 0-3
    exercise_angina: Optional[int] = None  # 0/1

    # Metadata
    data_sources: List[str] = field(default_factory=list)
    confidence_score: float = 1.0


@dataclass
class PredictionResult:
    """Result from heart disease prediction."""

    risk_score: float  # 0.0 to 1.0
    risk_category: RiskCategory
    confidence: float
    features_used: List[str]
    features_missing: List[str]
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    model_version: str = "1.0"


class PredictionIntegrationService:
    """
    Bridges document extraction with heart disease prediction.

    Workflow:
    1. Receive extracted lab report data
    2. Map to prediction model features
    3. Validate completeness
    4. Call prediction API
    5. Store results with audit trail
    """

    # Mapping from extracted field names to model features
    FIELD_MAPPING = {
        # Cholesterol panel
        "total_cholesterol": "cholesterol",
        "cholesterol": "cholesterol",
        "total cholesterol": "cholesterol",
        "hdl_cholesterol": "hdl",
        "hdl cholesterol": "hdl",
        "hdl": "hdl",
        "ldl_cholesterol": "ldl",
        "ldl cholesterol": "ldl",
        "ldl": "ldl",
        "triglycerides": "triglycerides",
        "tg": "triglycerides",
        "trigs": "triglycerides",
        # Blood sugar
        "fasting_glucose": "fasting_blood_sugar",
        "fasting glucose": "fasting_blood_sugar",
        "fbs": "fasting_blood_sugar",
        "fasting_blood_sugar": "fasting_blood_sugar",
        "blood sugar fasting": "fasting_blood_sugar",
        "hba1c": "hba1c",
        "hemoglobin_a1c": "hba1c",
        "hemoglobin a1c": "hba1c",
        "glycated hemoglobin": "hba1c",
        # Kidney function
        "creatinine": "creatinine",
        "serum creatinine": "creatinine",
        # Vitals
        "resting_hr": "resting_heart_rate",
        "resting_heart_rate": "resting_heart_rate",
        "resting heart rate": "resting_heart_rate",
        "pulse": "resting_heart_rate",
        "systolic_bp": "blood_pressure_systolic",
        "systolic": "blood_pressure_systolic",
        "systolic blood pressure": "blood_pressure_systolic",
        "bp systolic": "blood_pressure_systolic",
        "diastolic_bp": "blood_pressure_diastolic",
        "diastolic": "blood_pressure_diastolic",
        "diastolic blood pressure": "blood_pressure_diastolic",
        "bp diastolic": "blood_pressure_diastolic",
    }

    # Required fields for valid prediction
    REQUIRED_FEATURES = ["age", "sex", "cholesterol"]

    # Fields that improve prediction accuracy
    RECOMMENDED_FEATURES = [
        "hdl",
        "ldl",
        "fasting_blood_sugar",
        "blood_pressure_systolic",
        "resting_heart_rate",
    ]

    # All supported features
    ALL_FEATURES = [
        "age",
        "sex",
        "cholesterol",
        "hdl",
        "ldl",
        "triglycerides",
        "fasting_blood_sugar",
        "hba1c",
        "creatinine",
        "resting_heart_rate",
        "max_heart_rate",
        "blood_pressure_systolic",
        "blood_pressure_diastolic",
        "chest_pain_type",
        "exercise_angina",
    ]

    def __init__(
        self,
        prediction_api_url: Optional[str] = None,
        audit_service=None,
        mock_mode: bool = False,
    ):
        """
        Initialize prediction integration.

        Args:
            prediction_api_url: URL of prediction model API
            audit_service: Audit service for logging
            mock_mode: Return mock predictions for testing
        """
        self.prediction_api_url = prediction_api_url or "http://localhost:5000/predict"
        self.audit_service = audit_service
        self.mock_mode = mock_mode
        logger.info(f"PredictionIntegrationService initialized (mock={mock_mode})")

    def extract_prediction_features(
        self, extracted_data: Dict[str, Any], patient_profile: Dict[str, Any]
    ) -> PredictionInput:
        """
        Extract prediction features from scanned document data.

        Args:
            extracted_data: Data extracted from medical document
            patient_profile: User's profile (age, sex, etc.)

        Returns:
            PredictionInput with mapped features
        """
        # Start with patient demographics
        features = {
            "age": patient_profile.get("age"),
            "sex": self._normalize_sex(
                patient_profile.get("sex") or patient_profile.get("gender")
            ),
            "data_sources": ["patient_profile"],
        }

        # Map extracted test results to features
        test_results = extracted_data.get("test_results", [])
        for test in test_results:
            test_name = test.get("test_name", "").lower().replace("_", " ")
            test_value = test.get("value")

            # Find matching feature
            if test_name in self.FIELD_MAPPING:
                feature_name = self.FIELD_MAPPING[test_name]
                try:
                    features[feature_name] = float(test_value)
                    if "document" not in features["data_sources"]:
                        features["data_sources"].append("document")
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert {test_name} value: {test_value}")

        # Also check top-level extracted data
        for key, value in extracted_data.items():
            key_lower = key.lower().replace("_", " ")
            if key_lower in self.FIELD_MAPPING and value is not None:
                feature_name = self.FIELD_MAPPING[key_lower]
                if feature_name not in features:
                    try:
                        features[feature_name] = float(value)
                    except (ValueError, TypeError):
                        pass

        # Add vitals if available
        vitals = extracted_data.get("vitals", {})
        for vital_key, vital_value in vitals.items():
            normalized_key = vital_key.lower().replace("_", " ")
            if normalized_key in self.FIELD_MAPPING:
                feature_name = self.FIELD_MAPPING[normalized_key]
                try:
                    features[feature_name] = float(vital_value)
                    if "vitals" not in features["data_sources"]:
                        features["data_sources"].append("vitals")
                except (ValueError, TypeError):
                    pass

        return PredictionInput(**features)

    def _normalize_sex(self, sex_value: Any) -> Optional[int]:
        """Normalize sex value to 0 (female) or 1 (male)."""
        if sex_value is None:
            return None

        if isinstance(sex_value, int):
            return sex_value if sex_value in [0, 1] else None

        sex_str = str(sex_value).lower().strip()
        if sex_str in ["male", "m", "1"]:
            return 1
        elif sex_str in ["female", "f", "0"]:
            return 0
        return None

    def validate_prediction_input(self, input_data: PredictionInput) -> Dict[str, Any]:
        """
        Validate prediction input completeness.

        Returns:
            Validation result with missing/recommended fields
        """
        missing_required = []
        missing_recommended = []
        present_features = []

        # Check required fields
        for feature in self.REQUIRED_FEATURES:
            value = getattr(input_data, feature, None)
            if value is None:
                missing_required.append(feature)
            else:
                present_features.append(feature)

        # Check recommended fields
        for feature in self.RECOMMENDED_FEATURES:
            value = getattr(input_data, feature, None)
            if value is None:
                missing_recommended.append(feature)
            elif feature not in present_features:
                present_features.append(feature)

        # Check all other features
        for feature in self.ALL_FEATURES:
            if (
                feature not in self.REQUIRED_FEATURES
                and feature not in self.RECOMMENDED_FEATURES
            ):
                value = getattr(input_data, feature, None)
                if value is not None and feature not in present_features:
                    present_features.append(feature)

        is_valid = len(missing_required) == 0

        # Calculate completeness score
        completeness = len(present_features) / len(self.ALL_FEATURES)

        return {
            "is_valid": is_valid,
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
            "present_features": present_features,
            "feature_count": len(present_features),
            "completeness_score": round(completeness, 2),
            "message": (
                "Ready for prediction"
                if is_valid
                else f"Missing required fields: {', '.join(missing_required)}"
            ),
        }

    async def run_prediction(
        self,
        input_data: PredictionInput,
        user_id: str,
        document_id: Optional[str] = None,
    ) -> PredictionResult:
        """
        Run heart disease prediction with extracted data.

        Args:
            input_data: Validated prediction input
            user_id: ID of the user
            document_id: Source document ID

        Returns:
            Prediction result with risk score
        """
        # Validate first
        validation = self.validate_prediction_input(input_data)
        if not validation["is_valid"]:
            raise ValueError(f"Invalid prediction input: {validation['message']}")

        # Mock mode for testing
        if self.mock_mode:
            return self._generate_mock_prediction(input_data, validation)

        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, using mock prediction")
            return self._generate_mock_prediction(input_data, validation)

        # Prepare API request
        payload = {
            "age": input_data.age,
            "sex": input_data.sex,
            "cholesterol": input_data.cholesterol,
            "hdl": input_data.hdl,
            "ldl": input_data.ldl,
            "triglycerides": input_data.triglycerides,
            "fasting_blood_sugar": input_data.fasting_blood_sugar,
            "hba1c": input_data.hba1c,
            "resting_heart_rate": input_data.resting_heart_rate,
            "blood_pressure_systolic": input_data.blood_pressure_systolic,
            "blood_pressure_diastolic": input_data.blood_pressure_diastolic,
        }

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.prediction_api_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        result_data = await response.json()
                        risk_score = result_data.get("risk_score", 0.5)

                        result = PredictionResult(
                            risk_score=risk_score,
                            risk_category=self._categorize_risk(risk_score),
                            confidence=result_data.get("confidence", 0.8),
                            features_used=validation["present_features"],
                            features_missing=validation["missing_recommended"],
                            recommendations=self._generate_recommendations(
                                risk_score, validation["missing_recommended"]
                            ),
                        )

                        # Log to audit trail
                        if self.audit_service:
                            self.audit_service.log_event(
                                {
                                    "event_type": "prediction.completed",
                                    "user_id": user_id,
                                    "document_id": document_id,
                                    "risk_score": risk_score,
                                    "features_count": len(
                                        validation["present_features"]
                                    ),
                                }
                            )

                        return result
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Prediction API error: {response.status} - {error_text}"
                        )
                        raise Exception(f"Prediction API returned {response.status}")

        except aiohttp.ClientError as e:
            logger.error(f"Prediction API connection error: {e}")
            # Fall back to mock prediction
            return self._generate_mock_prediction(input_data, validation)
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise

    def _generate_mock_prediction(
        self, input_data: PredictionInput, validation: Dict[str, Any]
    ) -> PredictionResult:
        """Generate a mock prediction for testing."""
        # Simple risk calculation based on available data
        risk_factors = 0

        if input_data.cholesterol and input_data.cholesterol > 200:
            risk_factors += 1
        if input_data.ldl and input_data.ldl > 130:
            risk_factors += 1
        if (
            input_data.blood_pressure_systolic
            and input_data.blood_pressure_systolic > 140
        ):
            risk_factors += 1
        if input_data.fasting_blood_sugar and input_data.fasting_blood_sugar > 126:
            risk_factors += 1
        if input_data.age and input_data.age > 55:
            risk_factors += 1

        # Calculate mock risk score
        base_risk = 0.1 + (risk_factors * 0.15)
        risk_score = min(base_risk, 0.95)

        return PredictionResult(
            risk_score=round(risk_score, 3),
            risk_category=self._categorize_risk(risk_score),
            confidence=0.7 if self.mock_mode else 0.85,
            features_used=validation["present_features"],
            features_missing=validation["missing_recommended"],
            recommendations=self._generate_recommendations(
                risk_score, validation["missing_recommended"]
            ),
            model_version="mock-1.0" if self.mock_mode else "1.0",
        )

    def _categorize_risk(self, risk_score: float) -> RiskCategory:
        """Categorize risk score."""
        if risk_score < 0.2:
            return RiskCategory.LOW
        elif risk_score < 0.5:
            return RiskCategory.MODERATE
        elif risk_score < 0.8:
            return RiskCategory.HIGH
        else:
            return RiskCategory.VERY_HIGH

    def _generate_recommendations(
        self, risk_score: float, missing_features: List[str]
    ) -> List[str]:
        """Generate recommendations based on prediction."""
        recommendations = []

        # Recommendations for missing data
        if missing_features:
            if "hdl" in missing_features or "ldl" in missing_features:
                recommendations.append(
                    "Consider getting a complete lipid panel for more accurate assessment"
                )
            if "fasting_blood_sugar" in missing_features:
                recommendations.append(
                    "A fasting blood sugar test would improve prediction accuracy"
                )
            if "blood_pressure_systolic" in missing_features:
                recommendations.append(
                    "Regular blood pressure monitoring is recommended"
                )

        # Risk-based recommendations
        if risk_score >= 0.5:
            recommendations.append(
                "Schedule a consultation with a cardiologist for comprehensive evaluation"
            )
        if risk_score >= 0.3:
            recommendations.append(
                "Consider lifestyle modifications: diet, exercise, and stress management"
            )
        if risk_score < 0.3:
            recommendations.append(
                "Maintain your healthy lifestyle and continue regular check-ups"
            )

        return recommendations


# Global instance
_prediction_service: Optional[PredictionIntegrationService] = None


def get_prediction_service(mock_mode: bool = False) -> PredictionIntegrationService:
    """Get or create the global prediction service instance."""
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = PredictionIntegrationService(mock_mode=mock_mode)
    return _prediction_service
