"""
Sentiment Analysis Engine using VADER
VADER (Valence Aware Dictionary and sEntiment Reasoner) is optimized for social media
and conversational text, making it ideal for healthcare chatbot applications.
"""
import re
import logging
import asyncio
import gc
from typing import Dict, List, Tuple, Any, Optional, Literal, TypedDict, Pattern
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache

try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    SentimentIntensityAnalyzer = None

from config import (
    SENTIMENT_THRESHOLD_POSITIVE,
    SENTIMENT_THRESHOLD_NEGATIVE,
    SENTIMENT_THRESHOLD_DISTRESSED,
    SENTIMENT_THRESHOLD_URGENT
)
from core.models import SentimentEnum, SentimentResult
from core.async_patterns import AsyncTimeout, run_sync_in_executor
from core.error_handling import (
    ProcessingError,
    CacheError,
    ExternalServiceError,
)  # PHASE 2: Import exception hierarchy
from nlp.keywords import UnifiedKeywordDatabase, SentimentKeywords  # PHASE 2.4: Unified keywords

logger = logging.getLogger(__name__)


# ============================================================================
# TYPE DEFINITIONS & ERROR HANDLING
# ============================================================================

@dataclass
class SentimentError:
    """Structured error context for sentiment operations."""
    error_type: str
    message: str
    timestamp: datetime
    request_id: Optional[str] = None
    original_error: Optional[Exception] = None

    def __str__(self) -> str:
        return f"[{self.error_type}] {self.message}"


class SentimentAnalysisError(Exception):
    """Custom exception for sentiment analysis errors."""
    
    def __init__(self, error: SentimentError):
        self.error = error
        super().__init__(str(error))


class PatternCompiledError(SentimentAnalysisError):
    """Error during regex pattern compilation."""
    pass


class AnalysisError(SentimentAnalysisError):
    """Error during sentiment analysis."""
    pass


@dataclass
class SentimentMetrics:
    """Metrics for sentiment analysis operations."""
    analysis_count: int = 0
    total_analysis_time: float = 0.0
    distressed_count: int = 0
    urgent_count: int = 0
    avg_confidence: float = 0.0
    
    @property
    def average_analysis_time_ms(self) -> float:
        """Average time per analysis in milliseconds."""
        if self.analysis_count == 0:
            return 0.0
        return (self.total_analysis_time / self.analysis_count) * 1000

class SentimentAnalyzer:
    """
    Sentiment analysis engine using VADER (Valence Aware Dictionary and sEntiment Reasoner).
    Optimized for healthcare chatbot conversational text.
    
    Features:
    - Type-safe analysis with structured error handling
    - Regex patterns compiled once for performance
    - Async support for non-blocking operations
    - Healthcare-specific sentiment context
    - Comprehensive metrics and logging
    """

    def __init__(self) -> None:
        """Initialize sentiment analyzer with pre-compiled patterns and keyword sets."""
        if not NLTK_AVAILABLE:
            raise ImportError("NLTK is not available. Please install nltk to use sentiment analysis.")
        
        # Pre-compile regex patterns for performance (O(1) matching)
        self._urgent_patterns: List[Pattern[str]] = [
            re.compile(r'\b(emergency|911|urgent|immediately|right now)\b', re.IGNORECASE),
            re.compile(r'\b(can\'t breathe|cannot breathe)\b', re.IGNORECASE),
            re.compile(r'\b(severe chest pain|heart attack|stroke)\b', re.IGNORECASE),
            re.compile(r'\b(critical condition|life threatening)\b', re.IGNORECASE)
        ]
        
        self._distress_patterns: List[Pattern[str]] = [
            re.compile(r'\b(help|suffering|agonizing|unbearable)\b', re.IGNORECASE),
            re.compile(r'\b(can\'t|cannot) \b(stand|take|handle|cope)\b', re.IGNORECASE),
            re.compile(r'\b(scared|terrified|frightened|afraid)\b', re.IGNORECASE)
        ]

        # Initialize VADER analyzer (lazy)
        self._analyzer: Any = None
        self._analyzer_initialized = False
        
        # Metrics tracking
        self._metrics = SentimentMetrics()
        self._created_at = datetime.now()

        # Keyword sets for O(1) membership testing
        self.distress_keywords: set = {
            "help", "emergency", "urgent", "severe", "terrible",
            "awful", "horrible", "unbearable", "can't take it",
            "dying", "scared", "afraid", "worried", "anxious",
            "distressed", "suffering", "pain", "agony"
        }

        self.urgency_keywords: set = {
            "immediately", "right now", "urgent", "emergency",
            "critical", "severe", "life threatening", "911"
        }

        self.positive_health_keywords: set = {
            "better", "improving", "improved", "good", "great",
            "excellent", "well", "fine", "healthy", "strong"
        }

        self.negative_health_keywords: set = {
            "worse", "worsening", "bad", "terrible", "sick",
            "ill", "unwell", "poor", "weak", "struggling"
        }
        
        # Negation words for context adjustment
        self.negations: set = {
            "not", "no", "don't", "doesn't", "won't", "can't", "cannot"
        }
        
        self._initialize_analyzer()

    def _initialize_analyzer(self) -> None:
        """Initialize VADER analyzer."""
        try:
            if self._analyzer is None:
                self._analyzer = SentimentIntensityAnalyzer()
                self._analyzer_initialized = True
                logger.info("VADER SentimentIntensityAnalyzer initialized successfully")
        except Exception as e:
            error = SentimentError(
                error_type="InitializationFailed",
                message=f"Failed to initialize VADER analyzer: {type(e).__name__}: {str(e)}",
                timestamp=datetime.now(),
                original_error=e
            )
            logger.error(f"Sentiment analyzer initialization failed: {error}")
            raise SentimentAnalysisError(error) from e

    def analyze_sentiment(self, text: str) -> SentimentResult:
        """
        Analyze sentiment of text using VADER (BLOCKING).

        Args:
            text: Text to analyze

        Returns:
            SentimentResult with detected sentiment and score
            
        Raises:
            ValueError: If text is None or not a string
            AnalysisError: If analysis fails
        """
        # Input validation
        if not isinstance(text, str):
            raise ValueError(f"text must be a string, got: {type(text).__name__}")
        
        if not text or not text.strip():
            logger.warning("Empty text provided for sentiment analysis")
            return SentimentResult(
                sentiment=SentimentEnum.NEUTRAL,
                score=0.0,
                intensity="unknown"
            )
        
        # Truncate very long texts
        max_length = 512
        if len(text) > max_length:
            text = text[:max_length]
            logger.debug(f"Text truncated to {max_length} characters")
        
        return self._analyze_sentiment_sync(text)
    
    async def analyze_sentiment_async(self, text: str) -> SentimentResult:
        """
        Analyze sentiment of text asynchronously (NON-BLOCKING).

        Args:
            text: Text to analyze

        Returns:
            SentimentResult with detected sentiment and score
            
        Raises:
            ValueError: If text is None or not a string
            asyncio.TimeoutError: If analysis exceeds timeout
            AnalysisError: If analysis fails
        """
        # Input validation
        if not isinstance(text, str):
            raise ValueError(f"text must be a string, got: {type(text).__name__}")
        
        if not text or not text.strip():
            return SentimentResult(
                sentiment=SentimentEnum.NEUTRAL,
                score=0.0,
                intensity="unknown"
            )
        
        @AsyncTimeout(timeout_seconds=10)
        async def _analyze_with_timeout() -> SentimentResult:
            """Run analysis in thread pool with timeout."""
            return await run_sync_in_executor(
                self._analyze_sentiment_sync,
                text
            )
        
        try:
            return await _analyze_with_timeout()
        except asyncio.TimeoutError:
            logger.error(f"Sentiment analysis timeout for text: {text[:50]}")
            error = SentimentError(
                error_type="AnalysisTimeout",
                message=f"Sentiment analysis exceeded 10 second timeout",
                timestamp=datetime.now()
            )
            raise AnalysisError(error) from None
        except AnalysisError:
            raise
        except Exception as e:
            error = SentimentError(
                error_type="AnalysisError",
                message=f"Unexpected error during async analysis: {str(e)}",
                timestamp=datetime.now(),
                original_error=e
            )
            logger.error(f"Async analysis failed: {error}")
            raise AnalysisError(error) from e

    def _analyze_sentiment_sync(self, text: str) -> SentimentResult:
        """
        Internal blocking sentiment analysis logic (runs in thread pool when called async).

        Args:
            text: Input text (pre-validated and normalized)

        Returns:
            SentimentResult with sentiment and score
        """
        import time
        start_time = time.time()
        
        try:
            if self._analyzer is None:
                error = SentimentError(
                    error_type="AnalyzerNotInitialized",
                    message="VADER analyzer is not initialized",
                    timestamp=datetime.now()
                )
                logger.error(f"Analysis failed: {error}")
                raise AnalysisError(error)
            
            # Check for emergency/urgent indicators first
            if self._is_urgent(text):
                elapsed = time.time() - start_time
                self._metrics.analysis_count += 1
                self._metrics.total_analysis_time += elapsed
                self._metrics.urgent_count += 1
                
                return SentimentResult(
                    sentiment=SentimentEnum.URGENT,
                    score=0.95,
                    intensity="severe"
                )

            if self._is_distressed(text):
                elapsed = time.time() - start_time
                self._metrics.analysis_count += 1
                self._metrics.total_analysis_time += elapsed
                self._metrics.distressed_count += 1
                
                return SentimentResult(
                    sentiment=SentimentEnum.DISTRESSED,
                    score=-0.85,
                    intensity="severe"
                )

            # Use VADER for general sentiment
            vader_scores: Dict[str, float] = self._analyzer.polarity_scores(text)
            compound_score: float = vader_scores['compound']  # Range: -1 to 1

            # Adjust score based on health context
            adjusted_score = self._adjust_score_for_health_context(text, compound_score)

            # Classify sentiment based on adjusted score
            if adjusted_score >= SENTIMENT_THRESHOLD_POSITIVE:
                sentiment = SentimentEnum.POSITIVE
                intensity = self._calculate_intensity(adjusted_score, "positive")
            elif adjusted_score <= SENTIMENT_THRESHOLD_NEGATIVE:
                sentiment = SentimentEnum.NEGATIVE
                intensity = self._calculate_intensity(adjusted_score, "negative")
            else:
                sentiment = SentimentEnum.NEUTRAL
                intensity = "moderate"

            # Track metrics
            elapsed = time.time() - start_time
            self._metrics.analysis_count += 1
            self._metrics.total_analysis_time += elapsed
            
            logger.debug(
                f"Sentiment analysis completed: {sentiment.value} "
                f"(score: {adjusted_score:.2f}, time: {elapsed:.3f}s)"
            )
            
            result = SentimentResult(
                sentiment=sentiment,
                score=round(adjusted_score, 2),
                intensity=intensity
            )
            
            return result
            
        except AnalysisError:
            raise
        except Exception as e:
            error = SentimentError(
                error_type="AnalysisError",
                message=f"Error during sentiment analysis: {type(e).__name__}: {str(e)}",
                timestamp=datetime.now(),
                original_error=e
            )
            logger.error(f"Analysis failed: {error}")
            raise AnalysisError(error) from e

        # Classify sentiment based on adjusted score
        if adjusted_score >= SENTIMENT_THRESHOLD_POSITIVE:
            sentiment = SentimentEnum.POSITIVE
            intensity = self._calculate_intensity(adjusted_score, "positive")
        elif adjusted_score <= SENTIMENT_THRESHOLD_NEGATIVE:
            sentiment = SentimentEnum.NEGATIVE
            intensity = self._calculate_intensity(adjusted_score, "negative")
        else:
            sentiment = SentimentEnum.NEUTRAL
            intensity = "moderate"

        return SentimentResult(
            sentiment=sentiment,
            score=round(adjusted_score, 2),
            intensity=intensity
        )

    def _is_urgent(self, text: str) -> bool:
        """
        Check if text indicates urgency (optimized with pre-compiled patterns).

        Args:
            text: Input text to check

        Returns:
            True if text contains urgent indicators
        """
        # Check for urgent regex patterns (O(1) lookup)
        for pattern in self._urgent_patterns:
            if pattern.search(text):
                return True

        # Check for multiple urgency keywords (set membership is O(1))
        text_lower = text.lower()
        urgency_count = sum(
            1 for keyword in self.urgency_keywords 
            if keyword in text_lower
        )
        return urgency_count >= 2

    def _is_distressed(self, text: str) -> bool:
        """
        Check if text indicates distress (optimized with pre-compiled patterns).

        Args:
            text: Input text to check

        Returns:
            True if text contains distress indicators
        """
        # Check distress patterns (O(1) lookup)
        for pattern in self._distress_patterns:
            if pattern.search(text):
                return True

        # Check for multiple distress keywords (set membership is O(1))
        text_lower = text.lower()
        distress_count = sum(
            1 for keyword in self.distress_keywords 
            if keyword in text_lower
        )
        return distress_count >= 3

    def _adjust_score_for_health_context(self, text: str, base_score: float) -> float:
        """
        Adjust sentiment score based on health context.

        Args:
            text: Input text
            base_score: Base sentiment score from VADER

        Returns:
            Adjusted sentiment score (clamped to [-1, 1])
        """
        text_lower = text.lower()
        adjustment = 0.0

        # Negative health context amplifies negative sentiment
        negative_count = sum(
            1 for keyword in self.negative_health_keywords 
            if keyword in text_lower
        )
        adjustment -= negative_count * 0.15

        # Positive health context amplifies positive sentiment
        positive_count = sum(
            1 for keyword in self.positive_health_keywords 
            if keyword in text_lower
        )
        adjustment += positive_count * 0.15

        # Negation handling (simple but effective)
        for negation in self.negations:
            if negation in text_lower:
                # If positive statement is negated, make it more negative
                if base_score > 0:
                    adjustment -= 0.3
                # If negative statement is negated, make it more positive
                elif base_score < 0:
                    adjustment += 0.3

        adjusted = base_score + adjustment
        return max(-1.0, min(1.0, adjusted))  # Clamp between -1 and 1

    def _calculate_intensity(self, score: float, sentiment_type: str) -> str:
        """
        Calculate intensity level based on score.

        Args:
            score: Sentiment score
            sentiment_type: Type of sentiment ("positive" or "negative")

        Returns:
            Intensity level (str)
        """
        if sentiment_type == "positive":
            if score >= 0.8:
                return "very_strong"
            elif score >= 0.6:
                return "strong"
            elif score >= 0.4:
                return "moderate"
            else:
                return "mild"
        elif sentiment_type == "negative":
            if score <= -0.8:
                return "very_strong"
            elif score <= -0.6:
                return "strong"
            elif score <= -0.4:
                return "moderate"
            else:
                return "mild"
        else:
            return "moderate"

    def get_emotion_from_sentiment(self, sentiment: SentimentEnum) -> str:
        """
        Get emoji or emotion word from sentiment.

        Args:
            sentiment: Sentiment type

        Returns:
            Emotion representation with emoji
        """
        emotion_map: Dict[SentimentEnum, str] = {
            SentimentEnum.POSITIVE: "😊 Happy/Satisfied",
            SentimentEnum.NEUTRAL: "😐 Neutral",
            SentimentEnum.NEGATIVE: "😞 Sad/Dissatisfied",
            SentimentEnum.DISTRESSED: "😰 Distressed/Worried",
            SentimentEnum.URGENT: "🚨 Urgent/Critical"
        }
        return emotion_map.get(sentiment, "❓ Unknown")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance and analysis metrics.

        Returns:
            Dictionary with sentiment analysis metrics
        """
        uptime = (datetime.now() - self._created_at).total_seconds()
        
        return {
            "analysis_count": self._metrics.analysis_count,
            "total_analysis_time_seconds": self._metrics.total_analysis_time,
            "average_analysis_time_ms": self._metrics.average_analysis_time_ms,
            "distressed_count": self._metrics.distressed_count,
            "urgent_count": self._metrics.urgent_count,
            "uptime_seconds": uptime,
            "created_at": self._created_at.isoformat()
        }

    def __del__(self) -> None:
        """Cleanup on object destruction."""
        if self._analyzer is not None:
            del self._analyzer
            self._analyzer = None
            gc.collect()
            logger.debug("Sentiment analyzer resources cleaned up")
