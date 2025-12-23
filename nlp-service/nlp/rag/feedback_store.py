"""
Feedback Store for RAG Response Quality Tracking.

Stores user feedback (thumbs up/down) linked to RAG responses
for debugging and continuous improvement.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


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
    """JSON-based feedback storage."""
    
    def __init__(self, storage_path: str = "./feedback_data"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.feedback_file = self.storage_path / "feedback_log.jsonl"
    
    def record_feedback(
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
            response: Generated response (first 500 chars)
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
        
        try:
            with open(self.feedback_file, 'a') as f:
                f.write(json.dumps(asdict(entry)) + '\n')
            
            logger.info(f"Feedback recorded: {feedback_id} rating={rating}")
            return True
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
            return False
    
    def get_negative_feedback(self, limit: int = 100) -> List[Dict]:
        """Get recent negative feedback for debugging."""
        entries = []
        if not self.feedback_file.exists():
            return entries
            
        with open(self.feedback_file, 'r') as f:
            for line in f:
                entry = json.loads(line)
                if entry["rating"] == -1:
                    entries.append(entry)
        
        return entries[-limit:]
    
    def get_feedback_stats(self) -> Dict:
        """Get aggregate feedback statistics."""
        if not self.feedback_file.exists():
            return {"total": 0, "positive": 0, "negative": 0}
        
        positive = negative = neutral = 0
        with open(self.feedback_file, 'r') as f:
            for line in f:
                entry = json.loads(line)
                if entry["rating"] == 1:
                    positive += 1
                elif entry["rating"] == -1:
                    negative += 1
                else:
                    neutral += 1
        
        total = positive + negative + neutral
        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "satisfaction_rate": positive / total if total > 0 else 0
        }


# Singleton instance
_feedback_store = None

def get_feedback_store() -> FeedbackStore:
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStore()
    return _feedback_store