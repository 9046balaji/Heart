"""
Production Pipeline Configuration for Heart Disease Prediction

Provides production-ready pipeline wrappers that integrate the heart disease
prediction service with the main chatbot_service infrastructure.

This module bridges the standalone prediction API with the orchestrator's
heart_analyst worker node and the main FastAPI application.

Usage from main.py or LangGraph orchestrator:
    from heart_disease_prediction.pipeline import (
        get_prediction_service,
        predict_with_medgemma,
        PredictionPipelineConfig,
    )

    service = get_prediction_service()
    result = await predict_with_medgemma(patient_data, user_id="user_123")
"""

import os
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline Configuration
# ---------------------------------------------------------------------------

@dataclass
class PredictionPipelineConfig:
    """Production pipeline configuration."""

    # Model settings
    model_filename: str = "stacking_heart_disease_model_v3.joblib"
    load_individual_pipelines: bool = True

    # MedGemma interpretation
    enable_interpretation: bool = True
    interpretation_timeout_seconds: float = 30.0

    # RAG settings
    enable_rag: bool = True
    max_guidelines: int = 5

    # Memory settings
    enable_memory: bool = True
    max_memories: int = 3

    # Safety settings
    enable_hallucination_check: bool = True
    enable_triage: bool = True
    enable_quality_evaluation: bool = False  # Expensive, off by default

    # Batch settings
    max_batch_size: int = 100

    # Observability
    enable_tracing: bool = True

    @classmethod
    def production(cls) -> "PredictionPipelineConfig":
        """Production defaults — safe, observable, quality-checked."""
        return cls(
            enable_interpretation=True,
            enable_rag=True,
            enable_memory=True,
            enable_hallucination_check=True,
            enable_triage=True,
            enable_quality_evaluation=True,
            enable_tracing=True,
        )

    @classmethod
    def fast(cls) -> "PredictionPipelineConfig":
        """Fast mode — ML only, no LLM interpretation."""
        return cls(
            enable_interpretation=False,
            enable_rag=False,
            enable_memory=False,
            enable_hallucination_check=False,
            enable_triage=False,
            enable_quality_evaluation=False,
            enable_tracing=False,
            load_individual_pipelines=False,
        )

    @classmethod
    def from_env(cls) -> "PredictionPipelineConfig":
        """Load configuration from environment variables."""
        return cls(
            enable_interpretation=os.getenv("HEART_ENABLE_INTERPRETATION", "true").lower() == "true",
            enable_rag=os.getenv("HEART_ENABLE_RAG", "true").lower() == "true",
            enable_memory=os.getenv("HEART_ENABLE_MEMORY", "true").lower() == "true",
            enable_hallucination_check=os.getenv("HEART_ENABLE_HALLUCINATION_CHECK", "true").lower() == "true",
            enable_triage=os.getenv("HEART_ENABLE_TRIAGE", "true").lower() == "true",
            enable_quality_evaluation=os.getenv("HEART_ENABLE_QUALITY_EVAL", "false").lower() == "true",
            enable_tracing=os.getenv("HEART_ENABLE_TRACING", "true").lower() == "true",
            max_batch_size=int(os.getenv("HEART_MAX_BATCH_SIZE", "100")),
            interpretation_timeout_seconds=float(os.getenv("HEART_INTERPRETATION_TIMEOUT", "30")),
        )


# ---------------------------------------------------------------------------
# Production Prediction Service
# ---------------------------------------------------------------------------

class PredictionService:
    """
    Production-grade prediction service.

    Wraps ModelLoader + ClinicalInterpretationPipeline with:
    - Configuration management
    - Observability (AgentTracer integration)
    - Error handling with graceful degradation
    - Metrics collection
    """

    def __init__(self, config: Optional[PredictionPipelineConfig] = None):
        self.config = config or PredictionPipelineConfig.from_env()
        self._model_loader = None
        self._interpretation_pipeline = None
        self._initialized = False
        self._metrics = {
            "total_predictions": 0,
            "successful_predictions": 0,
            "failed_predictions": 0,
            "interpreted_predictions": 0,
            "total_latency_ms": 0.0,
            "high_risk_count": 0,
        }

    def initialize(self):
        """Initialize the prediction service."""
        if self._initialized:
            return

        from heart_disease_prediction.heart_disease_prediction import (
            ModelLoader,
            ClinicalInterpretationPipeline,
        )

        # Load ML model
        self._model_loader = ModelLoader()
        try:
            self._model_loader.load_stacking_model(self.config.model_filename)
            logger.info("PredictionService: ML model loaded")
        except Exception as e:
            logger.error(f"PredictionService: Failed to load model: {e}")
            raise

        if self.config.load_individual_pipelines:
            try:
                self._model_loader.load_individual_pipelines()
                logger.info(
                    f"PredictionService: {len(self._model_loader._individual_pipelines)} "
                    "individual pipelines loaded"
                )
            except Exception as e:
                logger.warning(f"PredictionService: Individual pipelines failed: {e}")

        # Initialize interpretation pipeline
        if self.config.enable_interpretation:
            self._interpretation_pipeline = ClinicalInterpretationPipeline()

        self._initialized = True
        logger.info("PredictionService initialized")

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._model_loader is not None and self._model_loader.is_loaded

    @property
    def metrics(self) -> Dict[str, Any]:
        avg_latency = (
            self._metrics["total_latency_ms"] / max(self._metrics["total_predictions"], 1)
        )
        return {
            **self._metrics,
            "avg_latency_ms": round(avg_latency, 2),
        }

    async def predict(
        self,
        input_data: dict,
        interpret: bool = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run prediction with optional MedGemma interpretation.

        Args:
            input_data: Patient data dict matching HeartDiseaseInput schema
            interpret: Override config's enable_interpretation
            user_id: For patient history lookup

        Returns:
            Prediction result dict
        """
        if not self.is_ready:
            self.initialize()

        from heart_disease_prediction.heart_disease_prediction import (
            HeartDiseaseInput,
            build_feature_dataframe,
            classify_risk,
            RiskLevel,
        )

        start = time.perf_counter()
        self._metrics["total_predictions"] += 1

        try:
            # Validate input
            patient = HeartDiseaseInput(**input_data)

            # ML Prediction
            df = build_feature_dataframe(patient)
            prediction, probability = self._model_loader.predict(df)
            risk = classify_risk(probability, patient)

            result = {
                "prediction": prediction,
                "probability": round(probability, 4),
                "risk_level": risk.value,
                "confidence": round(abs(probability - 0.5) * 2, 4),
                "needs_medical_attention": risk in (RiskLevel.HIGH, RiskLevel.CRITICAL),
            }

            if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                self._metrics["high_risk_count"] += 1

            # MedGemma interpretation
            should_interpret = interpret if interpret is not None else self.config.enable_interpretation
            if should_interpret and self._interpretation_pipeline:
                try:
                    import asyncio

                    ensemble_votes = self._model_loader.get_ensemble_votes(df)
                    interpretation = await asyncio.wait_for(
                        self._interpretation_pipeline.interpret(
                            input_data=patient,
                            prediction=prediction,
                            probability=probability,
                            risk_level=risk,
                            ensemble_votes=ensemble_votes,
                            user_id=user_id,
                        ),
                        timeout=self.config.interpretation_timeout_seconds,
                    )
                    result.update(interpretation)
                    self._metrics["interpreted_predictions"] += 1
                except asyncio.TimeoutError:
                    logger.warning("MedGemma interpretation timed out")
                    result["clinical_interpretation"] = "Interpretation timed out."
                except Exception as e:
                    logger.error(f"Interpretation failed: {e}")
                    result["clinical_interpretation"] = "Interpretation unavailable."

            elapsed_ms = (time.perf_counter() - start) * 1000
            result["processing_time_ms"] = round(elapsed_ms, 2)
            self._metrics["total_latency_ms"] += elapsed_ms
            self._metrics["successful_predictions"] += 1

            # Trace
            if self.config.enable_tracing:
                self._trace_prediction(result, elapsed_ms)

            return result

        except Exception as e:
            self._metrics["failed_predictions"] += 1
            logger.error(f"Prediction failed: {e}")
            raise

    async def predict_batch(
        self, patients: List[dict], interpret: bool = False
    ) -> Dict[str, Any]:
        """Batch prediction."""
        if len(patients) > self.config.max_batch_size:
            raise ValueError(
                f"Batch size {len(patients)} exceeds max {self.config.max_batch_size}"
            )

        results = []
        for i, patient_data in enumerate(patients):
            try:
                result = await self.predict(patient_data, interpret=interpret)
                result["index"] = i
                results.append(result)
            except Exception as e:
                results.append({"index": i, "error": str(e)})

        return {
            "total": len(patients),
            "results": results,
            "high_risk_count": sum(
                1 for r in results if r.get("risk_level") in ("High", "Critical")
            ),
        }

    def _trace_prediction(self, result: Dict, latency_ms: float):
        """Record prediction in AgentTracer."""
        try:
            from app_lifespan import get_agent_tracer

            tracer = get_agent_tracer()
            if tracer:
                tracer.record_tool_call(
                    tool_name="heart_disease_prediction",
                    input_data={"risk_level": result.get("risk_level")},
                    output_data={"probability": result.get("probability")},
                    latency_ms=latency_ms,
                )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: Optional[PredictionService] = None


def get_prediction_service(
    config: Optional[PredictionPipelineConfig] = None,
) -> PredictionService:
    """Get or create the singleton PredictionService."""
    global _service
    if _service is None:
        _service = PredictionService(config)
    return _service


async def predict_with_medgemma(
    patient_data: dict, user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function for one-shot prediction with MedGemma.

    This is the recommended entry point for the LangGraph orchestrator's
    heart_analyst worker node.

    Example:
        result = await predict_with_medgemma({
            "age": 55, "sex": 1, "chest_pain_type": 4,
            "resting_bp_s": 140, "cholesterol": 250,
            "fasting_blood_sugar": 1, "resting_ecg": 1,
            "max_heart_rate": 130, "exercise_angina": 1,
            "oldpeak": 2.5, "st_slope": 2,
        }, user_id="user_123")
    """
    service = get_prediction_service()
    return await service.predict(patient_data, interpret=True, user_id=user_id)
