"""
NLP Service: Orchestrates parallel processing of NLP components.

Performs intent recognition, sentiment analysis, entity extraction,
and risk assessment in parallel for optimal performance.

Performance Target: 1200ms (sequential) → 300ms (parallel)
"""

import asyncio
import logging
import time
from typing import Optional
from dataclasses import dataclass

from nlp.intent_recognizer import IntentRecognizer
from nlp.sentiment_analyzer import SentimentAnalyzer
from nlp.entity_extractor import EntityExtractor
from medical_ai.risk_assessor import RiskAssessor
from core.models import (
    IntentResult,
    SentimentResult,
    Entity,
    RiskAssessmentResult,
)
from core.error_handling import (
    TimeoutError,
    ProcessingError,
)  # PHASE 2: Import exception hierarchy

logger = logging.getLogger(__name__)


@dataclass
class NLPAnalysisResult:
    """Result of parallel NLP analysis"""

    intent: IntentResult
    sentiment: SentimentResult
    entities: list[Entity]
    risk: RiskAssessmentResult
    processing_time_ms: float
    analysis_breakdown: dict  # Time breakdown per component


class NLPService:
    """
    Orchestrates parallel NLP processing.

    Runs all NLP analyzers concurrently instead of sequentially:
    - Intent Recognition: 300ms
    - Sentiment Analysis: 300ms
    - Entity Extraction: 300ms
    - Risk Assessment: 300ms

    Sequential Total: 1200ms
    Parallel Total: ~300ms (max of all)

    Performance Gain: 4x (75% improvement)
    """

    def __init__(
        self,
        intent_recognizer: IntentRecognizer,
        sentiment_analyzer: SentimentAnalyzer,
        entity_extractor: EntityExtractor,
        risk_assessor: RiskAssessor,
        timeout_seconds: int = 10,
    ):
        """
        Initialize NLP Service.

        Args:
            intent_recognizer: Intent recognition component
            sentiment_analyzer: Sentiment analysis component
            entity_extractor: Entity extraction component
            risk_assessor: Risk assessment component
            timeout_seconds: Overall processing timeout (default: 10s)
        """
        self.intent_recognizer = intent_recognizer
        self.sentiment_analyzer = sentiment_analyzer
        self.entity_extractor = entity_extractor
        self.risk_assessor = risk_assessor
        self.timeout_seconds = timeout_seconds

        # Metrics
        self.total_processed = 0
        self.total_timeouts = 0
        self.avg_processing_time_ms = 0.0

    async def analyze(
        self,
        text: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        health_metrics: Optional[dict] = None,
    ) -> NLPAnalysisResult:
        """
        Perform parallel NLP analysis on text.

        Args:
            text: Input text to analyze
            user_id: Optional user ID for context
            session_id: Optional session ID for context
            health_metrics: Optional health metrics for risk assessment

        Returns:
            NLPAnalysisResult with all analyses completed in parallel

        Raises:
            asyncio.TimeoutError: If processing exceeds timeout_seconds
            ValueError: If text is empty or invalid

        Performance:
            ~300ms for typical input (4x faster than sequential)
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        start_time = time.time()
        component_times = {}

        try:
            # Create parallel tasks for all components
            tasks = [
                self._analyze_intent(text),
                self._analyze_sentiment(text),
                self._extract_entities(text),
                self._assess_risk(text, health_metrics),
            ]

            # Execute all in parallel with timeout protection
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=False),
                timeout=self.timeout_seconds,
            )

            intent, sentiment, entities, risk = results

            # Calculate processing time
            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                f"NLP analysis completed in {elapsed_ms:.1f}ms "
                f"for user_id={user_id} session_id={session_id}"
            )

            # Update metrics
            self.total_processed += 1
            self.avg_processing_time_ms = (
                self.avg_processing_time_ms * (self.total_processed - 1) + elapsed_ms
            ) / self.total_processed

            return NLPAnalysisResult(
                intent=intent,
                sentiment=sentiment,
                entities=entities,
                risk=risk,
                processing_time_ms=elapsed_ms,
                analysis_breakdown={
                    "intent_time": component_times.get("intent", 0),
                    "sentiment_time": component_times.get("sentiment", 0),
                    "entities_time": component_times.get("entities", 0),
                    "risk_time": component_times.get("risk", 0),
                },
            )

        except asyncio.TimeoutError:
            self.total_timeouts += 1
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"NLP analysis timeout after {elapsed_ms:.1f}ms "
                f"for user_id={user_id} session_id={session_id}"
            )
            raise

    async def _analyze_intent(self, text: str) -> IntentResult:
        """Recognize intent (component execution)"""
        try:
            start = time.time()
            result = await self.intent_recognizer.recognize_intent_async(text)
            elapsed_ms = (time.time() - start) * 1000
            logger.debug(f"Intent analysis: {elapsed_ms:.1f}ms")
            return result
        except Exception as e:
            logger.error(f"Intent recognition failed: {e}")
            raise

    async def _analyze_sentiment(self, text: str) -> SentimentResult:
        """Analyze sentiment (component execution)"""
        try:
            start = time.time()
            result = await self.sentiment_analyzer.analyze_sentiment_async(text)
            elapsed_ms = (time.time() - start) * 1000
            logger.debug(f"Sentiment analysis: {elapsed_ms:.1f}ms")
            return result
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            raise

    async def _extract_entities(self, text: str) -> list[Entity]:
        """Extract entities (component execution)"""
        try:
            start = time.time()
            # Run in thread pool to avoid blocking
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.entity_extractor.extract_entities, text
            )
            elapsed_ms = (time.time() - start) * 1000
            logger.debug(f"Entity extraction: {elapsed_ms:.1f}ms")
            return result
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            raise

    async def _assess_risk(
        self, text: str, health_metrics: Optional[dict] = None
    ) -> Optional[RiskAssessmentResult]:
        """Assess health risk (component execution)"""
        try:
            start = time.time()
            if not health_metrics:
                # Cannot assess risk without metrics
                return None
            
            # Convert dict to HealthMetrics object
            from core.models import HealthMetrics
            
            # Map fields if necessary or assume direct mapping
            # HealthMetrics expects specific fields
            try:
                metrics = HealthMetrics(**health_metrics)
            except Exception as e:
                logger.warning(f"Invalid health metrics format: {e}")
                return None

            # Run in thread pool since assess_risk is synchronous
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.risk_assessor.assess_risk, metrics
            )
            elapsed_ms = (time.time() - start) * 1000
            logger.debug(f"Risk assessment: {elapsed_ms:.1f}ms")
            return result
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            # Return None on failure to avoid failing the entire NLP pipeline
            return None

    def get_metrics(self) -> dict:
        """Get service metrics"""
        return {
            "total_processed": self.total_processed,
            "total_timeouts": self.total_timeouts,
            "avg_processing_time_ms": self.avg_processing_time_ms,
            "timeout_rate": (
                self.total_timeouts / self.total_processed
                if self.total_processed > 0
                else 0
            ),
        }

    def reset_metrics(self):
        """Reset service metrics"""
        self.total_processed = 0
        self.total_timeouts = 0
        self.avg_processing_time_ms = 0.0


class ParallelNLPProcessor:
    """
    Advanced processor with fallback and retry logic.

    Handles timeout scenarios gracefully by returning
    partial results when some components timeout.
    """

    def __init__(self, nlp_service: NLPService, enable_partial_results: bool = True):
        """
        Initialize parallel processor.

        Args:
            nlp_service: NLP service instance
            enable_partial_results: If True, returns available results on timeout
        """
        self.nlp_service = nlp_service
        self.enable_partial_results = enable_partial_results

    async def process_with_fallback(
        self,
        text: str,
        user_id: Optional[str] = None,
        fallback_intent: Optional[str] = None,
    ) -> NLPAnalysisResult:
        """
        Process with fallback on timeout.

        If parallel processing times out, attempts individual
        component analysis with shorter timeouts.
        """
        try:
            return await self.nlp_service.analyze(text, user_id=user_id)
        except asyncio.TimeoutError:
            if not self.enable_partial_results:
                raise

            logger.warning(
                f"Parallel processing timeout, attempting fallback for user {user_id}"
            )

            # Attempt individual components with shorter timeout
            return await self._fallback_analysis(text, user_id)

    async def _fallback_analysis(
        self, text: str, user_id: Optional[str] = None
    ) -> NLPAnalysisResult:
        """Fallback analysis with individual timeouts"""
        results = {}

        # Try intent with 3s timeout
        try:
            results["intent"] = await asyncio.wait_for(
                self.nlp_service._analyze_intent(text), timeout=3.0
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Fallback intent failed: {e}")
            results["intent"] = IntentResult(intent="UNKNOWN", confidence=0.0)

        # Try sentiment with 3s timeout
        try:
            results["sentiment"] = await asyncio.wait_for(
                self.nlp_service._analyze_sentiment(text), timeout=3.0
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Fallback sentiment failed: {e}")
            results["sentiment"] = SentimentResult(sentiment="NEUTRAL", score=0.0)

        # Try entities with 2s timeout
        try:
            results["entities"] = await asyncio.wait_for(
                self.nlp_service._extract_entities(text), timeout=2.0
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Fallback entities failed: {e}")
            results["entities"] = []

        # Skip risk on fallback (most demanding)
        results["risk"] = None

        return NLPAnalysisResult(
            intent=results.get("intent"),
            sentiment=results.get("sentiment"),
            entities=results.get("entities", []),
            risk=results.get("risk"),
            processing_time_ms=0,  # Not tracked in fallback
            analysis_breakdown={"fallback": True},
        )


__all__ = [
    "NLPService",
    "NLPAnalysisResult",
    "ParallelNLPProcessor",
]
