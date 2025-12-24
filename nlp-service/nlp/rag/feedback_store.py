"""
Database-backed Feedback Store for RAG Response Quality Tracking.

Stores user feedback in MySQL for durability across container restarts.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)

# Import database utilities
try:
    from core.database.xampp_db import get_database
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database not available, feedback will not be persisted")


@dataclass
class FeedbackEntry:
    feedback_id: str
    query: str
    response_preview: str
    rating: int  # 1 = thumbs up, -1 = thumbs down, 0 = neutral
    user_id: Optional[str]
    timestamp: str
    citations_count: int
    context_sources: List[str]
    user_comment: Optional[str] = None


class FeedbackStore:
    """
    Database-backed feedback storage.
    
    Persists RAG feedback to MySQL for durability and analytics.
    Falls back to in-memory storage if database unavailable.
    """
    
    def __init__(self):
        self._db = None
        self._memory_fallback: List[FeedbackEntry] = []
    
    async def _ensure_db(self):
        """Lazy initialize database connection."""
        if self._db is None and DB_AVAILABLE:
            self._db = await get_database()
    
    async def record_feedback(
        self,
        feedback_id: str,
        rating: int,
        query: str,
        response: str,
        citations: List[Dict],
        user_id: Optional[str] = None,
        comment: Optional[str] = None
    ) -> bool:
        """
        Record user feedback for a RAG response.
        
        Args:
            feedback_id: UUID from RAGResponse
            rating: 1 (positive), -1 (negative), 0 (neutral)
            query: Original user query
            response: Generated response (first 500 chars stored)
            citations: List of citations used
            user_id: Optional user identifier
            comment: Optional user comment
            
        Returns:
            Success status
        """
        entry = FeedbackEntry(
            feedback_id=feedback_id,
            query=query,
            response_preview=response[:500],
            rating=rating,
            user_id=user_id,
            timestamp=datetime.now().isoformat(),
            citations_count=len(citations),
            context_sources=[c.get("source", "unknown") for c in citations[:5]],
            user_comment=comment
        )
        
        await self._ensure_db()
        
        if self._db and self._db.initialized:
            try:
                async with self._db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""INSERT INTO rag_feedback 
                            (feedback_id, query, response_preview, rating, user_id, 
                             timestamp, citations_count, context_sources, user_comment)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                rating = VALUES(rating),
                                user_comment = VALUES(user_comment)
                        """, (
                            entry.feedback_id,
                            entry.query,
                            entry.response_preview,
                            entry.rating,
                            entry.user_id,
                            entry.timestamp,
                            entry.citations_count,
                            json.dumps(entry.context_sources),
                            entry.user_comment
                        ))
                
                logger.info(f"Feedback persisted to database: {feedback_id} rating={rating}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to persist feedback to database: {e}")
                # Fall through to memory fallback
        
        # Memory fallback
        self._memory_fallback.append(entry)
        logger.warning(f"Feedback stored in memory (database unavailable): {feedback_id}")
        return True
    
    async def get_negative_feedback(self, limit: int = 100) -> List[Dict]:
        """Get recent negative feedback for debugging."""
        await self._ensure_db()
        
        if self._db and self._db.initialized:
            try:
                async with self._db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""SELECT feedback_id, query, response_preview, rating,
                               user_id, timestamp, citations_count, 
                               context_sources, user_comment
                        FROM rag_feedback
                        WHERE rating = -1
                        ORDER BY timestamp DESC
                        LIMIT %s""", (limit,))
                        
                        results = await cursor.fetchall()
                        return [
                            {
                                "feedback_id": row[0],
                                "query": row[1],
                                "response_preview": row[2],
                                "rating": row[3],
                                "user_id": row[4],
                                "timestamp": row[5],
                                "citations_count": row[6],
                                "context_sources": json.loads(row[7]) if row[7] else [],
                                "user_comment": row[8]
                            }
                            for row in results
                        ]
            except Exception as e:
                logger.error(f"Failed to query negative feedback: {e}")
        
        # Memory fallback
        return [
            asdict(e) for e in self._memory_fallback 
            if e.rating == -1
        ][-limit:]
    
    async def get_feedback_stats(self) -> Dict:
        """Get aggregate feedback statistics."""
        await self._ensure_db()
        
        if self._db and self._db.initialized:
            try:
                async with self._db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as positive,
                            SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) as negative,
                            SUM(CASE WHEN rating = 0 THEN 1 ELSE 0 END) as neutral
                        FROM rag_feedback""")
                        
                        row = await cursor.fetchone()
                        total, positive, negative, neutral = row
                        
                        return {
                            "total": total or 0,
                            "positive": positive or 0,
                            "negative": negative or 0,
                            "neutral": neutral or 0,
                            "satisfaction_rate": (positive / total) if total > 0 else 0,
                            "source": "database"
                        }
            except Exception as e:
                logger.error(f"Failed to get feedback stats: {e}")
        
        # Memory fallback
        positive = sum(1 for e in self._memory_fallback if e.rating == 1)
        negative = sum(1 for e in self._memory_fallback if e.rating == -1)
        neutral = sum(1 for e in self._memory_fallback if e.rating == 0)
        total = len(self._memory_fallback)
        
        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "satisfaction_rate": (positive / total) if total > 0 else 0,
            "source": "memory_fallback"
        }


# Singleton instance
_feedback_store: Optional[FeedbackStore] = None

async def get_feedback_store() -> FeedbackStore:
    """Get singleton feedback store instance."""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStore()
    return _feedback_store