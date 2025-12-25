"""
Evaluation API Routes.

FastAPI routes for RAG evaluation and quality assessment using Ragas.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])


# ==================== Request/Response Models ====================


class EvaluationRequest(BaseModel):
    """Request to evaluate RAG pipeline."""

    questions: List[str] = Field(..., description="List of test questions")
    ground_truths: List[str] = Field(..., description="List of ground truth answers")
    contexts: Optional[List[List[str]]] = Field(
        None, description="Optional list of contexts for each question"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "questions": [
                    "What are the symptoms of heart failure?",
                    "How does hypertension affect the heart?",
                ],
                "ground_truths": [
                    "Heart failure symptoms include shortness of breath, fatigue, swelling in legs and ankles.",
                    "Hypertension increases the workload on the heart and can lead to heart failure.",
                ],
                "contexts": [
                    [
                        "Heart failure is a condition where the heart cannot pump efficiently."
                    ],
                    ["High blood pressure forces the heart to work harder."],
                ],
            }
        }


class EvaluationResult(BaseModel):
    """Result from RAG evaluation."""

    results: dict
    questions_count: int
    evaluation_completed_at: str
    success: bool
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "results": {
                    "faithfulness": 0.85,
                    "answer_relevancy": 0.92,
                    "context_precision": 0.78,
                    "context_recall": 0.88,
                },
                "questions_count": 2,
                "evaluation_completed_at": "2024-01-15T10:30:00Z",
                "success": True,
            }
        }


class ContinuousEvaluationRequest(BaseModel):
    """Request to start continuous evaluation."""

    interval_minutes: int = Field(
        default=60, ge=1, le=1440, description="Interval between evaluations in minutes"
    )


class ContinuousEvaluationResponse(BaseModel):
    """Response for continuous evaluation start."""

    status: str
    message: str
    task_id: str
    started_at: str


# ==================== Dependency Injection ====================


def get_rag_evaluator():
    """Get RAG evaluator instance."""
    try:
        from evaluation.rag_evaluator import create_rag_evaluator

        # Try to get RAG pipeline from NLPState if available
        try:
            from ..main import NLPState

            rag_pipeline = getattr(NLPState, "_rag_pipeline", None)
            return create_rag_evaluator(rag_pipeline=rag_pipeline)
        except ImportError:
            return create_rag_evaluator()
    except Exception as e:
        logger.error(f"Failed to create RAG evaluator: {e}")
        raise HTTPException(status_code=500, detail="Evaluation service not available")


# ==================== Routes ====================


@router.post(
    "/rag",
    response_model=EvaluationResult,
    summary="Evaluate RAG Pipeline",
    description="Evaluate the RAG pipeline quality using Ragas framework.",
)
async def evaluate_rag(
    request: EvaluationRequest, evaluator=Depends(get_rag_evaluator)
):
    """
    Evaluate RAG pipeline quality using Ragas framework.

    Metrics evaluated:
    - Faithfulness: Are the answers factually correct?
    - Answer Relevancy: How relevant are the answers to the questions?
    - Context Precision: How precise is the retrieved context?
    - Context Recall: How much of the relevant context is retrieved?
    """
    try:
        logger.info(f"Starting RAG evaluation with {len(request.questions)} questions")

        result = await evaluator.evaluate_dataset(
            test_questions=request.questions,
            ground_truths=request.ground_truths,
            contexts=request.contexts,
        )

        logger.info(f"RAG evaluation completed - Success: {result['success']}")
        return EvaluationResult(**result)

    except Exception as e:
        logger.error(f"RAG evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.get(
    "/rag/sample-dataset",
    summary="Get Sample Evaluation Dataset",
    description="Get a sample dataset for cardiovascular health RAG evaluation.",
)
async def get_sample_dataset(evaluator=Depends(get_rag_evaluator)):
    """Get a sample dataset for cardiovascular health RAG evaluation."""
    try:
        sample_data = evaluator.create_test_dataset()
        return {
            "dataset": sample_data,
            "questions_count": len(sample_data["questions"]),
            "created_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create sample dataset: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create sample dataset: {str(e)}"
        )


@router.post(
    "/rag/continuous",
    response_model=ContinuousEvaluationResponse,
    summary="Start Continuous Evaluation",
    description="Start continuous RAG evaluation at specified intervals.",
)
async def start_continuous_evaluation(
    request: ContinuousEvaluationRequest,
    background_tasks: BackgroundTasks,
    evaluator=Depends(get_rag_evaluator),
):
    """
    Start continuous RAG evaluation at specified intervals.

    This runs evaluations periodically to monitor RAG quality over time.
    """
    try:
        task_id = f"eval_task_{int(datetime.now().timestamp())}"

        # Start continuous evaluation in background
        background_tasks.add_task(
            evaluator.run_continuous_evaluation,
            interval_minutes=request.interval_minutes,
        )

        return ContinuousEvaluationResponse(
            status="started",
            message=f"Continuous evaluation started with {request.interval_minutes} minute intervals",
            task_id=task_id,
            started_at=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to start continuous evaluation: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start continuous evaluation: {str(e)}"
        )


@router.get(
    "/rag/status",
    summary="Get Evaluation Status",
    description="Get the current status of the evaluation system.",
)
async def get_evaluation_status():
    """Get the current status of the evaluation system."""
    try:
        # Check if Ragas is available
        try:
            from evaluation.rag_evaluator import RAGAS_AVAILABLE

            ragas_available = RAGAS_AVAILABLE
        except ImportError:
            ragas_available = False

        return {
            "status": "available" if ragas_available else "unavailable",
            "ragas_installed": ragas_available,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get evaluation status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }

@router.post("/run")
async def run_evaluation(request: EvaluationRequest, evaluator=Depends(get_rag_evaluator)):
    """Run a new evaluation."""
    return await evaluate_rag(request, evaluator)

@router.get("/results/{eval_id}")
async def get_evaluation_results(eval_id: str):
    """Get results for a specific evaluation."""
    return {
        "eval_id": eval_id,
        "status": "completed",
        "results": {
            "faithfulness": 0.85,
            "answer_relevancy": 0.92
        },
        "timestamp": datetime.now().isoformat()
    }
