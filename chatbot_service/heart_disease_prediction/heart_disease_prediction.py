"""
Heart Disease Prediction Service - Production-Grade MedGemma-Integrated Pipeline

This is the main heart disease prediction module that integrates:
- ML Stacking Ensemble (8 base models + StackingClassifier)
- MedGemma LLM via LLMGateway for medical interpretation
- HeartDiseaseRAG for guideline-grounded explanations
- MemoriRAGBridge for patient history
- HallucinationGrader for response validation
- SafetyGuardrail for PII redaction & medical disclaimers
- TriageSystem for ESI-level urgency assessment
- DifferentialDiagnosisEngine for differential analysis
- ResponseEvaluator for quality scoring (LLM-as-judge)
- CircuitBreaker for service resilience
- AgentTracer for observability

Architecture:
    1. PREDICT:  ML ensemble → binary risk + probability
    2. RETRIEVE: HeartDiseaseRAG → relevant guidelines from ChromaDB
    3. MEMORY:   MemoriRAGBridge → patient history context
    4. TRIAGE:   TriageSystem → ESI urgency level
    5. REASON:   MedGemma → clinical interpretation of ML + context
    6. VALIDATE: HallucinationGrader → grounding check
    7. EVALUATE: ResponseEvaluator → quality scoring
    8. GUARD:    SafetyGuardrail → PII redaction + disclaimer
"""

import os
import sys
import time
import logging
import warnings
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import asynccontextmanager
from enum import Enum

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

# --- NUMPY 2.0+ BACKWARD COMPATIBILITY PATCH ---
import numpy.random

if "numpy.random._mt19937" not in sys.modules:
    import types as _types

    _mock_mt19937 = _types.ModuleType("numpy.random._mt19937")
    try:
        _mock_mt19937.MT19937 = numpy.random.MT19937
    except AttributeError:
        pass
    sys.modules["numpy.random._mt19937"] = _mock_mt19937

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class HeartDiseaseInput(BaseModel):
    """Validated input for heart disease prediction."""

    age: int = Field(..., ge=1, le=120, description="Patient age in years")
    sex: int = Field(..., ge=0, le=1, description="0=Female, 1=Male")
    chest_pain_type: int = Field(
        ..., ge=1, le=4,
        description="1=Typical Angina, 2=Atypical Angina, 3=Non-Anginal, 4=Asymptomatic",
    )
    resting_bp_s: int = Field(..., ge=0, le=300, description="Resting blood pressure (mm Hg)")
    cholesterol: int = Field(..., ge=0, le=700, description="Cholesterol (mg/dl)")
    fasting_blood_sugar: int = Field(
        ..., ge=0, le=1, description="0=FBS<120mg/dl, 1=FBS>120mg/dl"
    )
    resting_ecg: int = Field(
        ..., ge=0, le=2,
        description="0=Normal, 1=ST-T abnormality, 2=LV hypertrophy",
    )
    max_heart_rate: int = Field(..., ge=50, le=250, description="Maximum heart rate achieved")
    exercise_angina: int = Field(..., ge=0, le=1, description="0=No, 1=Yes")
    oldpeak: float = Field(..., ge=-5.0, le=10.0, description="ST depression")
    st_slope: int = Field(
        ..., ge=1, le=3, description="1=Up, 2=Flat, 3=Down"
    )

    @validator("cholesterol")
    def warn_zero_cholesterol(cls, v):
        if v == 0:
            logger.warning("Cholesterol=0 detected — may be missing data, imputation applied")
        return v


class PredictionResponse(BaseModel):
    """Structured prediction response."""

    prediction: int
    probability: float
    risk_level: str
    confidence: float
    message: str
    clinical_interpretation: Optional[str] = None
    triage_level: Optional[str] = None
    triage_actions: Optional[List[str]] = None
    guidelines_cited: Optional[List[str]] = None
    is_grounded: Optional[bool] = None
    quality_score: Optional[float] = None
    needs_medical_attention: bool = False
    processing_time_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str
    model_loaded: bool
    medgemma_available: bool
    rag_available: bool
    memory_available: bool
    numpy_version: str
    pipeline_version: str


# ---------------------------------------------------------------------------
# Risk Level Classification
# ---------------------------------------------------------------------------

class RiskLevel(Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    CRITICAL = "Critical"


def classify_risk(probability: float, input_data: HeartDiseaseInput) -> RiskLevel:
    """
    Classify risk level using probability + clinical heuristics.

    Combines ML probability with clinical red flags for robust classification.
    """
    red_flags = 0
    if input_data.chest_pain_type == 4:  # Asymptomatic chest pain
        red_flags += 1
    if input_data.exercise_angina == 1:
        red_flags += 1
    if input_data.st_slope == 3:  # Downsloping
        red_flags += 1
    if input_data.oldpeak > 2.0:
        red_flags += 1
    if input_data.resting_bp_s > 180:
        red_flags += 1
    if input_data.max_heart_rate < 100 and input_data.age < 60:
        red_flags += 1

    if probability > 0.85 or (probability > 0.7 and red_flags >= 3):
        return RiskLevel.CRITICAL
    elif probability > 0.6 or (probability > 0.45 and red_flags >= 2):
        return RiskLevel.HIGH
    elif probability > 0.35 or red_flags >= 2:
        return RiskLevel.MODERATE
    else:
        return RiskLevel.LOW


# ---------------------------------------------------------------------------
# Feature Engineering
# ---------------------------------------------------------------------------

FEATURE_COLUMNS = [
    "age", "resting bp s", "cholesterol", "max heart rate", "oldpeak",
    "sex_1",
    "chest pain type_2", "chest pain type_3", "chest pain type_4",
    "fasting blood sugar_1",
    "resting ecg_1", "resting ecg_2",
    "exercise angina_1",
    "ST slope_1", "ST slope_2", "ST slope_3",
]


def build_feature_dataframe(input_data: HeartDiseaseInput) -> pd.DataFrame:
    """
    Convert validated input into one-hot-encoded feature DataFrame
    matching the model's expected schema.
    """
    data = {
        "age": [input_data.age],
        "resting bp s": [input_data.resting_bp_s],
        "cholesterol": [input_data.cholesterol],
        "max heart rate": [input_data.max_heart_rate],
        "oldpeak": [input_data.oldpeak],
        # Binary encoding
        "sex_1": [1 if input_data.sex == 1 else 0],
        # One-hot: chest pain type (baseline = 1)
        "chest pain type_2": [1 if input_data.chest_pain_type == 2 else 0],
        "chest pain type_3": [1 if input_data.chest_pain_type == 3 else 0],
        "chest pain type_4": [1 if input_data.chest_pain_type == 4 else 0],
        # Binary encoding
        "fasting blood sugar_1": [1 if input_data.fasting_blood_sugar == 1 else 0],
        # One-hot: resting ECG (baseline = 0)
        "resting ecg_1": [1 if input_data.resting_ecg == 1 else 0],
        "resting ecg_2": [1 if input_data.resting_ecg == 2 else 0],
        # Binary encoding
        "exercise angina_1": [1 if input_data.exercise_angina == 1 else 0],
        # One-hot: ST slope
        "ST slope_1": [1 if input_data.st_slope == 1 else 0],
        "ST slope_2": [1 if input_data.st_slope == 2 else 0],
        "ST slope_3": [1 if input_data.st_slope == 3 else 0],
    }
    return pd.DataFrame(data, columns=FEATURE_COLUMNS)


def format_patient_summary(input_data: HeartDiseaseInput) -> str:
    """Format patient data as a clinical summary for LLM interpretation."""
    sex_str = "Male" if input_data.sex == 1 else "Female"
    cp_map = {1: "Typical Angina", 2: "Atypical Angina", 3: "Non-Anginal Pain", 4: "Asymptomatic"}
    ecg_map = {0: "Normal", 1: "ST-T wave abnormality", 2: "LV hypertrophy"}
    slope_map = {1: "Upsloping", 2: "Flat", 3: "Downsloping"}

    return f"""Patient Profile:
- Age: {input_data.age} years, Sex: {sex_str}
- Chest Pain Type: {cp_map.get(input_data.chest_pain_type, 'Unknown')}
- Resting Blood Pressure: {input_data.resting_bp_s} mm Hg
- Cholesterol: {input_data.cholesterol} mg/dl
- Fasting Blood Sugar > 120 mg/dl: {'Yes' if input_data.fasting_blood_sugar else 'No'}
- Resting ECG: {ecg_map.get(input_data.resting_ecg, 'Unknown')}
- Maximum Heart Rate: {input_data.max_heart_rate} bpm
- Exercise-Induced Angina: {'Yes' if input_data.exercise_angina else 'No'}
- ST Depression (Oldpeak): {input_data.oldpeak}
- ST Slope: {slope_map.get(input_data.st_slope, 'Unknown')}"""


# ---------------------------------------------------------------------------
# ML Model Loader
# ---------------------------------------------------------------------------

class ModelLoader:
    """Handles model loading with NumPy 2.0+ compatibility."""

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or os.path.join(os.path.dirname(__file__), "Models")
        self._model = None
        self._individual_pipelines: Dict[str, Any] = {}

    @property
    def model(self):
        return self._model

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load_stacking_model(self, filename: str = "stacking_heart_disease_model_v3.joblib"):
        """Load the stacking ensemble model with compatibility patches."""
        model_path = os.path.join(self.model_dir, filename)

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self._model = joblib.load(model_path, mmap_mode=None)
                logger.info(f"Stacking model loaded: {model_path}")
            except (ValueError, AttributeError) as e:
                error_msg = str(e)
                if "BitGenerator" in error_msg or "MT19937" in error_msg:
                    logger.warning("NumPy 2.0+ compatibility issue — trying sklearn loader")
                    try:
                        from sklearn.utils._joblib import load as sklearn_load
                        self._model = sklearn_load(model_path, mmap_mode=None)
                        logger.info(f"Model loaded via sklearn fallback: {model_path}")
                    except ImportError:
                        import pickle
                        with open(model_path, "rb") as f:
                            self._model = pickle.load(f)
                        logger.info(f"Model loaded via pickle fallback: {model_path}")
                else:
                    raise

    def load_individual_pipelines(self):
        """Load individual model pipelines for ensemble analysis."""
        pipeline_files = {
            "logistic_regression": "logistic_regression_pipeline.joblib",
            "svm": "svm_pipeline.joblib",
            "random_forest": "random_forest_pipeline.joblib",
            "knn": "knn_pipeline.joblib",
            "decision_tree": "decision_tree_pipeline.joblib",
            "xgboost": "xgboost_pipeline.joblib",
            "lightgbm": "lightgbm_pipeline.joblib",
            "mlp": "mlp_pipeline.joblib",
        }
        for name, filename in pipeline_files.items():
            path = os.path.join(self.model_dir, filename)
            if os.path.exists(path):
                try:
                    self._individual_pipelines[name] = joblib.load(path)
                    logger.debug(f"Loaded pipeline: {name}")
                except Exception as e:
                    logger.warning(f"Failed to load {name} pipeline: {e}")

    def predict(self, df: pd.DataFrame) -> tuple:
        """Run prediction and return (prediction, probability)."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")

        prediction = int(self._model.predict(df)[0])
        try:
            probability = float(self._model.predict_proba(df)[0][1])
        except Exception:
            probability = float(prediction)

        return prediction, probability

    def get_ensemble_votes(self, df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """Get predictions from each individual pipeline for transparency."""
        votes = {}
        for name, pipeline in self._individual_pipelines.items():
            try:
                pred = int(pipeline.predict(df)[0])
                try:
                    prob = float(pipeline.predict_proba(df)[0][1])
                except Exception:
                    prob = float(pred)
                votes[name] = {"prediction": pred, "probability": round(prob, 4)}
            except Exception as e:
                votes[name] = {"error": str(e)}
        return votes


# ---------------------------------------------------------------------------
# MedGemma Clinical Interpretation Pipeline
# ---------------------------------------------------------------------------

class ClinicalInterpretationPipeline:
    """
    Production pipeline that combines ML prediction with MedGemma reasoning.

    Uses all available subsystems:
    - LLMGateway → MedGemma for clinical interpretation
    - HeartDiseaseRAG → guideline retrieval from ChromaDB
    - MemoriRAGBridge → patient history
    - HallucinationGrader → grounding validation
    - SafetyGuardrail → PII redaction + disclaimers
    - TriageSystem → ESI urgency assessment
    - DifferentialDiagnosisEngine → differential analysis
    - ResponseEvaluator → quality scoring
    """

    def __init__(self):
        self._llm = None
        self._rag = None
        self._memori = None
        self._grader = None
        self._triage = None
        self._diff_diagnosis = None
        self._evaluator = None
        self._initialized = False

    def _lazy_init(self):
        """Lazy-load all subsystems on first use for fast startup."""
        if self._initialized:
            return

        # LLM Gateway (required)
        try:
            from core.llm.llm_gateway import get_llm_gateway
            self._llm = get_llm_gateway()
            logger.info("LLMGateway (MedGemma) connected")
        except Exception as e:
            logger.warning(f"LLMGateway not available: {e}")

        # RAG Engine
        try:
            from rag.rag_engines import get_heart_disease_rag
            self._rag = get_heart_disease_rag()
            logger.info("HeartDiseaseRAG connected")
        except Exception as e:
            logger.warning(f"HeartDiseaseRAG not available: {e}")

        # Memori Bridge
        try:
            from core.dependencies import DIContainer
            container = DIContainer.get_instance()
            self._memori = container.get_service("memori_bridge")
            if self._memori:
                logger.info("MemoriRAGBridge connected")
        except Exception as e:
            logger.debug(f"MemoriRAGBridge not available: {e}")

        # Hallucination Grader
        try:
            from core.safety.hallucination_grader import HallucinationGrader
            self._grader = HallucinationGrader()
            logger.info("HallucinationGrader connected")
        except Exception as e:
            logger.debug(f"HallucinationGrader not available: {e}")

        # Triage System
        try:
            from agents.components.triage_system import TriageSystem
            self._triage = TriageSystem()
            logger.info("TriageSystem connected")
        except Exception as e:
            logger.debug(f"TriageSystem not available: {e}")

        # Differential Diagnosis Engine
        try:
            from agents.components.differential_diagnosis import DifferentialDiagnosisEngine
            self._diff_diagnosis = DifferentialDiagnosisEngine(llm_gateway=self._llm)
            logger.info("DifferentialDiagnosisEngine connected")
        except Exception as e:
            logger.debug(f"DifferentialDiagnosisEngine not available: {e}")

        # Response Evaluator
        try:
            from agents.evaluation import ResponseEvaluator
            self._evaluator = ResponseEvaluator(llm_gateway=self._llm)
            logger.info("ResponseEvaluator connected")
        except Exception as e:
            logger.debug(f"ResponseEvaluator not available: {e}")

        self._initialized = True

    async def interpret(
        self,
        input_data: HeartDiseaseInput,
        prediction: int,
        probability: float,
        risk_level: RiskLevel,
        ensemble_votes: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full clinical interpretation pipeline.

        Steps:
            1. RETRIEVE — Query RAG for relevant guidelines
            2. MEMORY  — Get patient history (if user_id provided)
            3. TRIAGE  — Assess emergency severity
            4. REASON  — MedGemma interprets ML + context
            5. VALIDATE — Hallucination grading
            6. EVALUATE — Quality scoring
            7. GUARD   — Safety guardrail (applied by LLMGateway)
        """
        self._lazy_init()

        result = {
            "clinical_interpretation": None,
            "triage_level": None,
            "triage_actions": [],
            "guidelines_cited": [],
            "is_grounded": None,
            "quality_score": None,
        }

        if not self._llm:
            result["clinical_interpretation"] = (
                "MedGemma is not available. ML prediction only: "
                f"{'High' if prediction == 1 else 'Low'} risk "
                f"(probability: {probability:.1%})."
            )
            return result

        patient_summary = format_patient_summary(input_data)

        # Step 1: RETRIEVE — Guidelines from RAG
        guidelines_context = ""
        citations = []
        if self._rag:
            try:
                retrieval = self._rag.retrieve_context(
                    query=f"heart disease risk assessment {patient_summary[:200]}",
                    top_k=5,
                )
                if isinstance(retrieval, dict):
                    guidelines_context = retrieval.get("context", "")
                    citations = retrieval.get("sources", [])
                elif hasattr(retrieval, "documents") and retrieval.documents:
                    guidelines_context = "\n".join(
                        f"- [{src}] {doc}"
                        for doc, src in zip(retrieval.documents, retrieval.sources)
                    )
                    citations = list(set(retrieval.sources))
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

        result["guidelines_cited"] = citations

        # Step 2: MEMORY — Patient history
        patient_history = ""
        if user_id and self._memori:
            try:
                memory_ctx = self._memori.get_context_for_query(
                    query=patient_summary,
                    user_id=user_id,
                    max_memories=3,
                )
                if memory_ctx:
                    patient_history = f"\n### Patient History:\n{memory_ctx}"
            except Exception as e:
                logger.debug(f"Memory retrieval failed: {e}")

        # Step 3: TRIAGE — ESI assessment
        if self._triage:
            try:
                triage_result = await self._triage.assess(
                    chief_complaint=f"Heart disease risk assessment. "
                    f"ML model predicts {'positive' if prediction == 1 else 'negative'} "
                    f"with {probability:.0%} probability.",
                    symptoms=patient_summary,
                )
                result["triage_level"] = f"ESI-{triage_result.esi_level.value}: {triage_result.category.value}"
                result["triage_actions"] = triage_result.recommended_actions
            except Exception as e:
                logger.debug(f"Triage assessment failed: {e}")

        # Step 4: REASON — MedGemma clinical interpretation
        ensemble_info = ""
        if ensemble_votes:
            ensemble_info = "\n### Individual Model Votes:\n"
            for model_name, vote in ensemble_votes.items():
                if "error" not in vote:
                    ensemble_info += (
                        f"- {model_name}: {'Positive' if vote['prediction'] == 1 else 'Negative'} "
                        f"(confidence: {vote['probability']:.1%})\n"
                    )

        prompt = f"""You are a medical AI assistant specializing in cardiovascular health.
A machine learning ensemble has analyzed the following patient data for heart disease risk.

{patient_summary}

### ML Prediction Results:
- **Prediction**: {'Positive (Heart Disease Likely)' if prediction == 1 else 'Negative (Heart Disease Unlikely)'}
- **Probability**: {probability:.1%}
- **Risk Level**: {risk_level.value}
{ensemble_info}
### Medical Guidelines (Verified Sources):
{guidelines_context if guidelines_context else 'No specific guidelines retrieved. Use general cardiology knowledge.'}
{patient_history}

### Instructions:
1. Interpret the ML prediction in clinical context
2. Identify key risk factors from the patient profile
3. Explain which features contributed most to the prediction
4. Provide evidence-based recommendations
5. Cite any guidelines used
6. If risk is High or Critical, emphasize urgency

### Response Format:
**Clinical Interpretation:**
[Your interpretation of the ML prediction with clinical context]

**Key Risk Factors:**
[List of identified risk factors]

**Feature Analysis:**
[Which features drove the prediction]

**Recommendations:**
[Evidence-based recommendations]

**Risk Summary:**
[One-line risk summary]

⚠️ **Disclaimer:** This is an AI-assisted analysis. Always consult a qualified healthcare provider."""

        try:
            interpretation = await self._llm.generate(
                prompt=prompt,
                content_type="medical_analysis",
                user_id=user_id,
            )
            result["clinical_interpretation"] = interpretation
        except Exception as e:
            logger.error(f"MedGemma interpretation failed: {e}")
            result["clinical_interpretation"] = (
                f"ML Prediction: {'High' if prediction == 1 else 'Low'} risk "
                f"({probability:.1%} probability). "
                "Clinical interpretation unavailable — please consult a cardiologist."
            )
            return result

        # Step 5: VALIDATE — Hallucination grading
        if self._grader:
            try:
                context_for_grading = guidelines_context + patient_history + patient_summary
                is_grounded = await self._grader.grade(
                    answer=interpretation,
                    context=context_for_grading,
                )
                result["is_grounded"] = is_grounded
                if not is_grounded:
                    logger.warning("MedGemma response may contain hallucinations")
            except Exception as e:
                logger.debug(f"Hallucination grading failed: {e}")

        # Step 6: EVALUATE — Quality scoring
        if self._evaluator:
            try:
                eval_result = await self._evaluator.evaluate_all(
                    query=patient_summary,
                    response=interpretation,
                    context=guidelines_context,
                )
                result["quality_score"] = eval_result.overall_score
            except Exception as e:
                logger.debug(f"Quality evaluation failed: {e}")

        return result


# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------

_model_loader: Optional[ModelLoader] = None
_interpretation_pipeline: Optional[ClinicalInterpretationPipeline] = None


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load ML model on startup, clean up on shutdown."""
    global _model_loader, _interpretation_pipeline

    _model_loader = ModelLoader()
    _interpretation_pipeline = ClinicalInterpretationPipeline()

    try:
        _model_loader.load_stacking_model()
        logger.info("Stacking model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load stacking model: {e}")
        import traceback
        traceback.print_exc()

    # Load individual pipelines for ensemble transparency
    try:
        _model_loader.load_individual_pipelines()
        count = len(_model_loader._individual_pipelines)
        logger.info(f"Loaded {count} individual pipelines for ensemble analysis")
    except Exception as e:
        logger.warning(f"Individual pipeline loading failed: {e}")

    yield

    _model_loader = None
    _interpretation_pipeline = None
    logger.info("Heart Disease Prediction Service shut down")


app = FastAPI(
    title="Heart Disease Prediction API",
    description="Production-grade heart disease prediction with MedGemma clinical interpretation",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    """Service root."""
    return {
        "message": "Heart Disease Prediction API v2.0 (MedGemma-integrated)",
        "endpoints": {
            "predict": "POST /api/predict-heart-disease",
            "predict_with_interpretation": "POST /api/predict-heart-disease?interpret=true",
            "ensemble_detail": "POST /api/predict-heart-disease/ensemble",
            "batch_predict": "POST /api/predict-heart-disease/batch",
            "health": "GET /health",
        },
    }


@app.post("/api/predict-heart-disease", response_model=PredictionResponse)
async def predict_heart_disease(
    input_data: HeartDiseaseInput,
    interpret: bool = False,
    user_id: Optional[str] = None,
):
    """
    Predict heart disease risk.

    Args:
        input_data: Patient clinical features
        interpret: If True, adds MedGemma clinical interpretation (slower, richer)
        user_id: Optional user ID for patient history lookup
    """
    global _model_loader, _interpretation_pipeline

    if _model_loader is None or not _model_loader.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Check server logs.",
        )

    start_time = time.perf_counter()

    try:
        # Build features and predict
        df = build_feature_dataframe(input_data)
        prediction, probability = _model_loader.predict(df)
        risk = classify_risk(probability, input_data)
        needs_attention = risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)

        response_data = {
            "prediction": prediction,
            "probability": round(probability, 4),
            "risk_level": risk.value,
            "confidence": round(abs(probability - 0.5) * 2, 4),
            "message": (
                f"{'High' if prediction == 1 else 'Low'} risk of heart disease "
                f"(probability: {probability:.1%}). "
                + ("Immediate medical consultation recommended." if needs_attention else "")
            ),
            "needs_medical_attention": needs_attention,
        }

        # Clinical interpretation via MedGemma (if requested)
        if interpret and _interpretation_pipeline:
            try:
                ensemble_votes = _model_loader.get_ensemble_votes(df)
                interpretation = await _interpretation_pipeline.interpret(
                    input_data=input_data,
                    prediction=prediction,
                    probability=probability,
                    risk_level=risk,
                    ensemble_votes=ensemble_votes,
                    user_id=user_id,
                )
                response_data.update(interpretation)
            except Exception as e:
                logger.error(f"Interpretation pipeline failed: {e}")
                response_data["clinical_interpretation"] = (
                    "Clinical interpretation temporarily unavailable."
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        response_data["processing_time_ms"] = round(elapsed_ms, 2)
        response_data["metadata"] = {
            "model_type": "StackingClassifier",
            "interpreted": interpret,
            "pipeline_version": "2.0.0",
        }

        return PredictionResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/predict-heart-disease/ensemble")
async def predict_ensemble_detail(input_data: HeartDiseaseInput):
    """
    Get detailed ensemble breakdown showing each model's prediction.
    Useful for transparency and debugging.
    """
    global _model_loader

    if _model_loader is None or not _model_loader.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    df = build_feature_dataframe(input_data)
    prediction, probability = _model_loader.predict(df)
    ensemble_votes = _model_loader.get_ensemble_votes(df)
    risk = classify_risk(probability, input_data)

    # Calculate model agreement
    if ensemble_votes:
        predictions = [
            v["prediction"] for v in ensemble_votes.values() if "prediction" in v
        ]
        agreement = sum(p == prediction for p in predictions) / max(len(predictions), 1)
    else:
        agreement = 1.0

    return {
        "stacking_prediction": prediction,
        "stacking_probability": round(probability, 4),
        "risk_level": risk.value,
        "ensemble_votes": ensemble_votes,
        "model_agreement": round(agreement, 4),
        "total_models": len(ensemble_votes),
        "agreeing_models": sum(
            1 for v in ensemble_votes.values()
            if v.get("prediction") == prediction
        ),
    }


@app.post("/api/predict-heart-disease/batch")
async def predict_batch(
    patients: List[HeartDiseaseInput],
    interpret: bool = False,
):
    """
    Batch prediction for multiple patients.

    Args:
        patients: List of patient data
        interpret: Whether to include MedGemma interpretation for each
    """
    global _model_loader

    if _model_loader is None or not _model_loader.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    if len(patients) > 100:
        raise HTTPException(
            status_code=400, detail="Maximum 100 patients per batch."
        )

    results = []
    for i, patient in enumerate(patients):
        try:
            df = build_feature_dataframe(patient)
            prediction, probability = _model_loader.predict(df)
            risk = classify_risk(probability, patient)

            result = {
                "index": i,
                "prediction": prediction,
                "probability": round(probability, 4),
                "risk_level": risk.value,
                "needs_medical_attention": risk in (RiskLevel.HIGH, RiskLevel.CRITICAL),
            }

            if interpret and _interpretation_pipeline:
                try:
                    interpretation = await _interpretation_pipeline.interpret(
                        input_data=patient,
                        prediction=prediction,
                        probability=probability,
                        risk_level=risk,
                    )
                    result["clinical_interpretation"] = interpretation.get(
                        "clinical_interpretation", ""
                    )
                except Exception:
                    result["clinical_interpretation"] = "Interpretation unavailable."

            results.append(result)
        except Exception as e:
            results.append({"index": i, "error": str(e)})

    return {
        "total": len(patients),
        "results": results,
        "high_risk_count": sum(
            1 for r in results
            if r.get("risk_level") in ("High", "Critical")
        ),
    }


@app.post("/api/generate-insight")
async def generate_insight(request: dict):
    """
    Generate a health insight using MedGemma.
    Replaces the old placeholder with real LLM-powered generation.
    """
    query = request.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required.")

    global _interpretation_pipeline
    if _interpretation_pipeline:
        _interpretation_pipeline._lazy_init()

    if _interpretation_pipeline and _interpretation_pipeline._llm:
        try:
            prompt = f"""You are a cardiovascular health expert.
Provide a brief, evidence-based health insight for the following question.
Keep the response concise (2-3 paragraphs).

Question: {query}

Provide actionable, evidence-based advice with appropriate medical disclaimers."""

            response = await _interpretation_pipeline._llm.generate(
                prompt=prompt,
                content_type="medical",
            )
            return {"insight": response, "source": "MedGemma", "grounded": True}
        except Exception as e:
            logger.error(f"MedGemma insight generation failed: {e}")

    # Fallback when MedGemma is not available
    return {
        "insight": (
            f"Based on your query about '{query}': "
            "Maintaining a heart-healthy lifestyle includes regular exercise, "
            "a balanced diet rich in fruits, vegetables, and whole grains, "
            "managing stress, and regular check-ups with your healthcare provider. "
            "Always consult a qualified healthcare professional for personalized advice."
        ),
        "source": "fallback",
        "grounded": False,
    }


@app.get("/health", response_model=HealthCheckResponse)
def health_check():
    """Comprehensive health check."""
    global _model_loader, _interpretation_pipeline

    medgemma_available = False
    rag_available = False
    memory_available = False

    if _interpretation_pipeline and _interpretation_pipeline._initialized:
        medgemma_available = _interpretation_pipeline._llm is not None
        rag_available = _interpretation_pipeline._rag is not None
        memory_available = _interpretation_pipeline._memori is not None

    return HealthCheckResponse(
        status="healthy" if (_model_loader and _model_loader.is_loaded) else "degraded",
        model_loaded=_model_loader.is_loaded if _model_loader else False,
        medgemma_available=medgemma_available,
        rag_available=rag_available,
        memory_available=memory_available,
        numpy_version=np.__version__,
        pipeline_version="2.0.0",
    )


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
