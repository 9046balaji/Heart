"""
RAG Evaluator using Ragas Framework.

This module implements automated RAG evaluation using the Ragas framework
for quality assessment and continuous improvement.

Features:
- Automated RAG quality assessment
- Hallucination detection
- Context relevance scoring
- Continuous improvement feedback
"""

import json
from pathlib import Path
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# Ragas imports
try:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )

    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Ragas not available - evaluation features disabled")

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """
    RAG Evaluator using Ragas framework.

    Features:
    - Automated quality assessment
    - Hallucination detection
    - Context relevance scoring
    - Continuous improvement feedback
    """
    
    QUERIES_FILE = Path(__file__).parent / "real_world_queries.json"

    def __init__(self, rag_pipeline=None):
        """
        Initialize RAG Evaluator.

        Args:
            rag_pipeline: RAG pipeline to evaluate (optional)
        """
        self.rag_pipeline = rag_pipeline
        self.metrics = (
            [faithfulness, answer_relevancy, context_precision, context_recall]
            if RAGAS_AVAILABLE
            else []
        )

        if RAGAS_AVAILABLE:
            logger.info("✅ RAGEvaluator initialized with Ragas")
        else:
            logger.warning("❌ RAGEvaluator initialized without Ragas (not installed)")

    async def evaluate_dataset(
        self,
        test_questions: List[str],
        ground_truths: List[str],
        contexts: Optional[List[List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate RAG pipeline on a dataset.

        Args:
            test_questions: List of test questions
            ground_truths: List of ground truth answers
            contexts: Optional list of contexts for each question

        Returns:
            Dict with evaluation results
        """
        if not RAGAS_AVAILABLE:
            return {
                "error": "Ragas not available",
                "timestamp": datetime.now().isoformat(),
            }

        logger.info(f"Evaluating RAG pipeline on {len(test_questions)} questions")

        try:
            # Generate responses if RAG pipeline provided
            responses = []
            generated_contexts = []

            if self.rag_pipeline:
                for question in test_questions:
                    try:
                        result = await self.rag_pipeline.query(question)
                        responses.append(result.get("response", ""))

                        # Extract contexts from RAG result
                        sources = result.get("sources", [])
                        if sources:
                            generated_contexts.append(
                                [str(source) for source in sources]
                            )
                        else:
                            generated_contexts.append(["No context available"])
                    except Exception as e:
                        logger.warning(
                            f"Failed to generate response for '{question[:30]}...': {e}"
                        )
                        responses.append("")
                        generated_contexts.append(["Error generating context"])
            else:
                # Use provided contexts or dummy contexts
                responses = ["Sample response"] * len(test_questions)
                generated_contexts = contexts or [["Sample context"]] * len(
                    test_questions
                )

            # Create dataset
            dataset_dict = {
                "question": test_questions,
                "answer": responses,
                "contexts": generated_contexts,
                "ground_truth": ground_truths,
            }

            dataset = Dataset.from_dict(dataset_dict)

            # Evaluate using Ragas
            try:
                result = evaluate(dataset, metrics=self.metrics)

                # Convert result to dict
                result_dict = (
                    result.to_dict() if hasattr(result, "to_dict") else dict(result)
                )

                return {
                    "results": result_dict,
                    "questions_count": len(test_questions),
                    "evaluation_completed_at": datetime.now().isoformat(),
                    "success": True,
                }
            except Exception as eval_error:
                logger.error(f"Ragas evaluation failed: {eval_error}")
                return {
                    "error": f"Evaluation failed: {str(eval_error)}",
                    "questions_count": len(test_questions),
                    "evaluation_completed_at": datetime.now().isoformat(),
                    "success": False,
                }

        except Exception as e:
            logger.error(f"Dataset evaluation failed: {e}")
            return {
                "error": str(e),
                "questions_count": len(test_questions),
                "evaluation_completed_at": datetime.now().isoformat(),
                "success": False,
            }

    def create_test_dataset(self) -> Dict[str, List[str]]:
        """Load test dataset from external file or fallback to defaults."""
        if self.QUERIES_FILE.exists():
            return self._load_external_dataset()
        return self._get_default_dataset()
    
    def _load_external_dataset(self) -> Dict[str, List[str]]:
        """Load queries from JSON file."""
        with open(self.QUERIES_FILE, 'r') as f:
            data = json.load(f)
        
        queries = data.get("queries", [])
        return {
            "questions": [q["question"] for q in queries],
            "contexts": [q.get("context", [""]) for q in queries],
            "ground_truths": [q["ground_truth"] for q in queries]
        }
    
    def _get_default_dataset(self) -> Dict[str, List[str]]:
        """Fallback hardcoded dataset."""
        return {
            "questions": ["What are the symptoms of heart failure?"],
            "contexts": [["Heart failure symptoms include..."]],
            "ground_truths": ["Heart failure symptoms include..."]
        }
    
    def log_low_confidence_query(
        self, 
        question: str, 
        confidence: float,
        threshold: float = 0.5
    ) -> None:
        """Log query for expert review if below threshold."""
        if confidence >= threshold:
            return
            
        entry = {
            "id": f"lcq_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "question": question,
            "captured_at": datetime.now().isoformat(),
            "original_confidence": confidence,
            "status": "pending_review"
        }
        
        # Append to queue
        if self.QUERIES_FILE.exists():
            with open(self.QUERIES_FILE, 'r+') as f:
                data = json.load(f)
                data.setdefault("low_confidence_queue", []).append(entry)
                f.seek(0)
                json.dump(data, f, indent=2)

    async def run_continuous_evaluation(self, interval_minutes: int = 60) -> None:
        """
        Run continuous evaluation at specified intervals.

        Args:
            interval_minutes: Interval between evaluations in minutes
        """
        if not RAGAS_AVAILABLE:
            logger.warning("Cannot run continuous evaluation - Ragas not available")
            return

        import asyncio

        logger.info(f"Starting continuous evaluation every {interval_minutes} minutes")

        while True:
            try:
                # Create test dataset
                test_data = self.create_test_dataset()

                # Run evaluation
                result = await self.evaluate_dataset(
                    test_questions=test_data["questions"],
                    ground_truths=test_data["ground_truths"],
                    contexts=test_data["contexts"],
                )

                if result["success"]:
                    logger.info(
                        f"Continuous evaluation completed - Scores: {result['results']}"
                    )
                else:
                    logger.error(
                        f"Continuous evaluation failed: {result.get('error', 'Unknown error')}"
                    )

                # Wait for next interval
                await asyncio.sleep(interval_minutes * 60)

            except Exception as e:
                logger.error(f"Continuous evaluation error: {e}")
                await asyncio.sleep(interval_minutes * 60)


# Factory function
def create_rag_evaluator(rag_pipeline=None) -> RAGEvaluator:
    """
    Factory function to create a RAGEvaluator.

    Args:
        rag_pipeline: RAG pipeline to evaluate (optional)

    Returns:
        Configured RAGEvaluator
    """
    return RAGEvaluator(rag_pipeline=rag_pipeline)
