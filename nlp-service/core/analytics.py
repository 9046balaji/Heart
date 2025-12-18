"""
Analytics Module for NLP Service
Tracks intent/sentiment patterns and usage statistics
"""
import json
import logging
import time
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from core.models import IntentEnum, SentimentEnum
from config import LOG_LEVEL
from core.error_handling import ProcessingError  # PHASE 2: Import exception hierarchy
import numpy as np

logger = logging.getLogger(__name__)


class AnalyticsManager:
    """
    Analytics manager for tracking NLP service usage patterns.
    Collects data on intents, sentiments, entities, and performance.
    """

    def __init__(self):
        """Initialize analytics manager"""
        self.intent_counter = Counter()
        self.sentiment_counter = Counter()
        self.entity_type_counter = Counter()
        self.processing_time_samples: List[float] = []
        self.request_timestamps: List[float] = []
        self.session_patterns: Dict[str, Dict] = defaultdict(lambda: {
            'intents': Counter(),
            'sentiments': Counter(),
            'entities': Counter(),
            'request_count': 0
        })
        
        # Trend analysis data
        self.hourly_intent_trends: Dict[str, List[Tuple[datetime, int]]] = defaultdict(list)
        self.daily_intent_trends: Dict[str, List[Tuple[datetime, int]]] = defaultdict(list)
        self.sentiment_trends: List[Tuple[datetime, Dict[str, int]]] = []
        
        # Performance trends
        self.performance_trends: List[Tuple[datetime, float]] = []
        
        # Configure logging for analytics
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def track_nlp_request(
        self,
        intent: IntentEnum,
        sentiment: SentimentEnum,
        entities: List[Any],
        processing_time: float,
        session_id: str = None,
        user_id: str = None
    ):
        """
        Track an NLP processing request.

        Args:
            intent: Detected intent
            sentiment: Detected sentiment
            entities: Extracted entities
            processing_time: Time taken to process request
            session_id: Session identifier (optional)
            user_id: User identifier (optional)
        """
        try:
            current_time = datetime.now()
            
            # Track overall patterns
            self.intent_counter[intent.value] += 1
            self.sentiment_counter[sentiment.value] += 1
            self.processing_time_samples.append(processing_time)
            self.request_timestamps.append(time.time())
            
            # Track entity types
            for entity in entities:
                self.entity_type_counter[entity.type] += 1
            
            # Track session patterns
            if session_id:
                session_data = self.session_patterns[session_id]
                session_data['intents'][intent.value] += 1
                session_data['sentiments'][sentiment.value] += 1
                session_data['request_count'] += 1
                
                for entity in entities:
                    session_data['entities'][entity.type] += 1
            
            # Track trends
            self._track_intent_trend(current_time, intent.value)
            self._track_sentiment_trend(current_time, sentiment.value)
            self._track_performance_trend(current_time, processing_time)
            
            # Log the request for detailed analysis
            logger.info(
                f"NLP_ANALYTICS - Intent: {intent.value}, "
                f"Sentiment: {sentiment.value}, "
                f"Entities: {len(entities)}, "
                f"ProcessingTime: {processing_time:.3f}s"
            )
            
        except Exception as e:
            logger.warning(f"Failed to track analytics: {e}")

    def _track_intent_trend(self, timestamp: datetime, intent: str):
        """Track intent trends over time"""
        # Hourly trends
        hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
        self.hourly_intent_trends[intent].append((hour_key, 1))
        
        # Daily trends
        day_key = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        self.daily_intent_trends[intent].append((day_key, 1))
        
        # Keep only recent data (last 24 hours for hourly, last 30 days for daily)
        cutoff_hour = datetime.now() - timedelta(hours=24)
        cutoff_day = datetime.now() - timedelta(days=30)
        
        self.hourly_intent_trends[intent] = [
            (t, count) for t, count in self.hourly_intent_trends[intent] 
            if t >= cutoff_hour
        ]
        
        self.daily_intent_trends[intent] = [
            (t, count) for t, count in self.daily_intent_trends[intent] 
            if t >= cutoff_day
        ]

    def _track_sentiment_trend(self, timestamp: datetime, sentiment: str):
        """Track sentiment trends over time"""
        # For simplicity, we'll just track the current sentiment counts
        # In a production system, you might want more sophisticated tracking
        self.sentiment_trends.append((timestamp, dict(self.sentiment_counter)))
        
        # Keep only recent data (last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        self.sentiment_trends = [
            (t, data) for t, data in self.sentiment_trends 
            if t >= cutoff
        ]

    def _track_performance_trend(self, timestamp: datetime, processing_time: float):
        """Track performance trends over time"""
        self.performance_trends.append((timestamp, processing_time))
        
        # Keep only recent data (last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        self.performance_trends = [
            (t, pt) for t, pt in self.performance_trends 
            if t >= cutoff
        ]

    def get_intent_distribution(self) -> Dict[str, int]:
        """
        Get distribution of detected intents.

        Returns:
            Dictionary with intent counts
        """
        return dict(self.intent_counter)

    def get_sentiment_distribution(self) -> Dict[str, int]:
        """
        Get distribution of detected sentiments.

        Returns:
            Dictionary with sentiment counts
        """
        return dict(self.sentiment_counter)

    def get_entity_type_distribution(self) -> Dict[str, int]:
        """
        Get distribution of entity types.

        Returns:
            Dictionary with entity type counts
        """
        return dict(self.entity_type_counter)

    def get_processing_time_stats(self) -> Dict[str, float]:
        """
        Get processing time statistics.

        Returns:
            Dictionary with processing time stats
        """
        if not self.processing_time_samples:
            return {"count": 0}
        
        samples = self.processing_time_samples
        return {
            "count": len(samples),
            "average": sum(samples) / len(samples),
            "min": min(samples),
            "max": max(samples),
            "median": sorted(samples)[len(samples) // 2]
        }

    def get_request_rate(self, minutes: int = 60) -> float:
        """
        Get request rate per minute.

        Args:
            minutes: Time window in minutes

        Returns:
            Requests per minute
        """
        cutoff_time = time.time() - (minutes * 60)
        recent_requests = [ts for ts in self.request_timestamps if ts > cutoff_time]
        return len(recent_requests) / minutes if minutes > 0 else 0

    def get_session_patterns(self, session_id: str) -> Dict:
        """
        Get analytics for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session analytics
        """
        return dict(self.session_patterns[session_id]) if session_id in self.session_patterns else {}

    def get_top_intents(self, limit: int = 10) -> List[tuple]:
        """
        Get most common intents.

        Args:
            limit: Number of top intents to return

        Returns:
            List of (intent, count) tuples
        """
        return self.intent_counter.most_common(limit)

    def get_top_entities(self, limit: int = 10) -> List[tuple]:
        """
        Get most common entity types.

        Args:
            limit: Number of top entity types to return

        Returns:
            List of (entity_type, count) tuples
        """
        return self.entity_type_counter.most_common(limit)

    def get_active_sessions(self) -> int:
        """
        Get number of active sessions.

        Returns:
            Count of active sessions
        """
        # Sessions active in last 30 minutes
        cutoff_time = time.time() - (30 * 60)
        active_count = 0
        for session_data in self.session_patterns.values():
            # This is a simplification - in a real implementation, we'd track last activity
            active_count += 1
        return active_count

    def get_analytics_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive analytics summary.

        Returns:
            Dictionary with all analytics data
        """
        return {
            "intent_distribution": self.get_intent_distribution(),
            "sentiment_distribution": self.get_sentiment_distribution(),
            "entity_type_distribution": self.get_entity_type_distribution(),
            "processing_time_stats": self.get_processing_time_stats(),
            "request_rate_per_minute": self.get_request_rate(),
            "total_requests": len(self.request_timestamps),
            "active_sessions": self.get_active_sessions(),
            "top_intents": self.get_top_intents(5),
            "top_entities": self.get_top_entities(5)
        }

    def get_intent_trends(self, intent: str = None, period: str = "hourly") -> Dict[str, Any]:
        """
        Get intent trends over time.

        Args:
            intent: Specific intent to get trends for (optional)
            period: Period type - 'hourly' or 'daily'

        Returns:
            Dictionary with trend data
        """
        if intent:
            if period == "hourly":
                data = self.hourly_intent_trends.get(intent, [])
            else:
                data = self.daily_intent_trends.get(intent, [])
            
            return {
                "intent": intent,
                "period": period,
                "data": [{"timestamp": t.isoformat(), "count": count} for t, count in data]
            }
        else:
            # Return trends for all intents
            result = {}
            trends = self.hourly_intent_trends if period == "hourly" else self.daily_intent_trends
            for intent_name, data in trends.items():
                result[intent_name] = {
                    "period": period,
                    "data": [{"timestamp": t.isoformat(), "count": count} for t, count in data]
                }
            return result

    def get_sentiment_trends(self) -> List[Dict[str, Any]]:
        """
        Get sentiment trends over time.

        Returns:
            List of sentiment trend data points
        """
        return [
            {
                "timestamp": t.isoformat(),
                "sentiments": data
            }
            for t, data in self.sentiment_trends
        ]

    def get_performance_trends(self) -> List[Dict[str, Any]]:
        """
        Get performance trends over time.

        Returns:
            List of performance trend data points
        """
        return [
            {
                "timestamp": t.isoformat(),
                "processing_time": pt
            }
            for t, pt in self.performance_trends
        ]

    def detect_anomalies(self) -> Dict[str, Any]:
        """
        Detect anomalies in the analytics data.

        Returns:
            Dictionary with detected anomalies
        """
        anomalies = {
            "high_request_rate": False,
            "slow_performance": False,
            "unusual_intent_distribution": False,
            "details": {}
        }
        
        # Check for high request rate (more than 2 standard deviations above average)
        if len(self.request_timestamps) > 10:
            current_rate = self.get_request_rate(5)  # Last 5 minutes
            recent_rates = [self.get_request_rate(i) for i in range(1, 11)]  # Last 10 minutes
            avg_rate = sum(recent_rates) / len(recent_rates)
            std_rate = np.std(recent_rates) if len(recent_rates) > 1 else 0
            
            if std_rate > 0 and current_rate > avg_rate + 2 * std_rate:
                anomalies["high_request_rate"] = True
                anomalies["details"]["request_rate_spike"] = {
                    "current_rate": current_rate,
                    "average_rate": avg_rate,
                    "threshold": avg_rate + 2 * std_rate
                }
        
        # Check for slow performance (more than 2 standard deviations above average)
        if len(self.processing_time_samples) > 10:
            current_avg_time = self.get_processing_time_stats()["average"]
            recent_avg_times = []
            for i in range(1, 11):
                # Get average of last i*10 samples
                samples = self.processing_time_samples[-(i*10):]
                if len(samples) > 0:
                    recent_avg_times.append(sum(samples) / len(samples))
            
            if len(recent_avg_times) > 1:
                avg_time = sum(recent_avg_times) / len(recent_avg_times)
                std_time = np.std(recent_avg_times)
                
                if std_time > 0 and current_avg_time > avg_time + 2 * std_time:
                    anomalies["slow_performance"] = True
                    anomalies["details"]["performance_degradation"] = {
                        "current_avg_time": current_avg_time,
                        "historical_avg_time": avg_time,
                        "threshold": avg_time + 2 * std_time
                    }
        
        return anomalies

    def reset_analytics(self):
        """Reset all analytics data"""
        self.intent_counter.clear()
        self.sentiment_counter.clear()
        self.entity_type_counter.clear()
        self.processing_time_samples.clear()
        self.request_timestamps.clear()
        self.session_patterns.clear()
        self.hourly_intent_trends.clear()
        self.daily_intent_trends.clear()
        self.sentiment_trends.clear()
        self.performance_trends.clear()


# Global analytics manager instance
analytics_manager = AnalyticsManager()