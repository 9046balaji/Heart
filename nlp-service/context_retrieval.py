"""
Context Retrieval Service for Healthcare AI Memory Management.

Implements intelligent context retrieval based on chat.md architecture:
"Retrieve selectively - Pull only relevant history"

This module provides:
- ContextType enum for different context categories
- RetrievedContext dataclass for context items
- ContextRetriever class for query-aware context retrieval

Author: AI Memory System Implementation
Version: 1.0.0
"""

from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio
import hashlib

logger = logging.getLogger(__name__)


class ContextType(Enum):
    """Types of context that can be retrieved for AI queries."""
    RECENT_VITALS = "recent_vitals"
    LAST_CONSULTATION = "last_consultation"
    MEDICAL_HISTORY = "medical_history"
    MEDICATIONS = "medications"
    RECENT_CONVERSATIONS = "recent_conversations"
    USER_PREFERENCES = "user_preferences"
    RISK_ASSESSMENTS = "risk_assessments"
    LIFESTYLE_DATA = "lifestyle_data"
    EMERGENCY_INFO = "emergency_info"


@dataclass
class RetrievedContext:
    """
    Container for a piece of retrieved context.
    
    Attributes:
        context_type: Type category of this context
        data: The actual context data
        relevance_score: Score from 0.0-1.0 indicating query relevance
        timestamp: When this context was generated
        source: Where this context came from (e.g., "vitals_db", "chat_history")
        token_estimate: Estimated token count for this context
    """
    context_type: ContextType
    data: Dict[str, Any]
    relevance_score: float  # 0.0 to 1.0
    timestamp: datetime
    source: str
    token_estimate: int = field(default=0)
    
    def __post_init__(self):
        """Calculate token estimate if not provided."""
        if self.token_estimate == 0:
            # Rough estimate: 4 characters per token
            import json
            self.token_estimate = len(json.dumps(self.data)) // 4


# ============================================================================
# Keyword Maps for Query Analysis
# ============================================================================

CONTEXT_KEYWORDS: Dict[ContextType, List[str]] = {
    ContextType.RECENT_VITALS: [
        'blood pressure', 'bp', 'heart rate', 'pulse', 'bpm',
        'temperature', 'oxygen', 'spo2', 'vitals', 'reading',
        'systolic', 'diastolic', 'measurement'
    ],
    ContextType.MEDICATIONS: [
        'medication', 'medicine', 'drug', 'prescription', 
        'dosage', 'taking', 'pill', 'tablet', 'dose',
        'pharmaceutical', 'rx', 'pharmacy'
    ],
    ContextType.RISK_ASSESSMENTS: [
        'risk', 'assessment', 'score', 'prediction', 
        'likelihood', 'chance', 'probability', 'cardiac',
        'heart disease', 'cardiovascular'
    ],
    ContextType.MEDICAL_HISTORY: [
        'history', 'diagnosis', 'condition', 'chronic',
        'disease', 'surgery', 'operation', 'hospital',
        'illness', 'disorder', 'treatment'
    ],
    ContextType.LAST_CONSULTATION: [
        'doctor', 'appointment', 'consultation', 'visit',
        'checkup', 'examination', 'clinic', 'last time',
        'physician', 'specialist'
    ],
    ContextType.LIFESTYLE_DATA: [
        'exercise', 'workout', 'diet', 'nutrition', 'sleep',
        'activity', 'steps', 'calories', 'fitness', 'lifestyle',
        'habit', 'routine'
    ],
    ContextType.USER_PREFERENCES: [
        'prefer', 'preference', 'like', 'settings', 'style',
        'communication', 'units', 'metric', 'imperial'
    ],
    ContextType.EMERGENCY_INFO: [
        'emergency', 'urgent', 'critical', 'severe', 'pain',
        'chest pain', 'breathing', 'unconscious', 'help'
    ],
}


class ContextRetriever:
    """
    Intelligently retrieves relevant context for AI calls.
    
    Implements Section 8.B from chat.md:
    "Retrieve selectively - Pull only relevant history"
    
    Key Features:
    - Query analysis to determine needed context
    - Multiple data source integration
    - Token budget management
    - Relevance scoring and sorting
    - Async parallel retrieval for performance
    
    Complexity: O(k*n) where k = context types, n = records per type
    """
    
    def __init__(
        self,
        chat_history_manager=None,
        patient_data_service=None,
        vitals_service=None,
        preferences_manager=None,
        max_context_tokens: int = 2000,
        retrieval_timeout: float = 5.0
    ):
        """
        Initialize context retriever.
        
        Args:
            chat_history_manager: Chat history storage manager
            patient_data_service: Service for patient medical data
            vitals_service: Service for vital signs data
            preferences_manager: User preferences manager
            max_context_tokens: Maximum tokens to include in context
            retrieval_timeout: Timeout for retrieval operations (seconds)
        """
        self.chat_history = chat_history_manager
        self.patient_data = patient_data_service
        self.vitals = vitals_service
        self.preferences = preferences_manager
        self.max_tokens = max_context_tokens
        self.timeout = retrieval_timeout
        
        # Retrieval stats for monitoring
        self._retrieval_count = 0
        self._total_retrieval_time = 0.0
        self._cache_hits = 0
        
        # Simple in-memory cache for recent queries
        self._cache: Dict[str, tuple] = {}  # query_hash -> (contexts, timestamp)
        self._cache_ttl = 60  # seconds
    
    async def retrieve_for_query(
        self,
        user_id: str,
        session_id: str,
        query: str,
        context_types: Optional[List[ContextType]] = None,
        include_preferences: bool = True
    ) -> List[RetrievedContext]:
        """
        Retrieve relevant context based on user query.
        
        This is the main entry point for context retrieval. It:
        1. Analyzes the query to determine needed context types
        2. Retrieves context from multiple sources in parallel
        3. Scores and sorts by relevance
        4. Trims to fit within token budget
        
        Args:
            user_id: Patient/User identifier
            session_id: Current conversation session
            query: The user's current query
            context_types: Specific context types to retrieve (optional)
            include_preferences: Whether to always include user preferences
        
        Returns:
            List of relevant context items, sorted by relevance
        """
        start_time = datetime.utcnow()
        self._retrieval_count += 1
        
        # Check cache first
        cache_key = self._make_cache_key(user_id, session_id, query)
        cached = self._get_cached(cache_key)
        if cached is not None:
            self._cache_hits += 1
            logger.debug(f"Cache hit for query context retrieval")
            return cached
        
        # Determine what context is needed based on query analysis
        needed_types = context_types or self._analyze_query_needs(query)
        
        # Always include preferences if requested
        if include_preferences and ContextType.USER_PREFERENCES not in needed_types:
            needed_types.append(ContextType.USER_PREFERENCES)
        
        # Always include recent conversations for continuity
        if ContextType.RECENT_CONVERSATIONS not in needed_types:
            needed_types.append(ContextType.RECENT_CONVERSATIONS)
        
        logger.info(
            f"Retrieving context for user={user_id}, session={session_id}, "
            f"types={[t.value for t in needed_types]}"
        )
        
        # Retrieve context from multiple sources in parallel
        contexts = await self._parallel_retrieve(
            user_id=user_id,
            session_id=session_id,
            query=query,
            context_types=needed_types
        )
        
        # Calculate relevance scores
        contexts = self._calculate_relevance_scores(contexts, query)
        
        # Sort by relevance and trim to token limit
        contexts.sort(key=lambda x: x.relevance_score, reverse=True)
        trimmed_contexts = self._trim_to_token_limit(contexts)
        
        # Update stats
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        self._total_retrieval_time += elapsed
        
        # Cache the result
        self._set_cached(cache_key, trimmed_contexts)
        
        logger.info(
            f"Retrieved {len(trimmed_contexts)} context items in {elapsed:.3f}s, "
            f"total_tokens≈{sum(c.token_estimate for c in trimmed_contexts)}"
        )
        
        return trimmed_contexts
    
    def _analyze_query_needs(self, query: str) -> List[ContextType]:
        """
        Analyze query to determine what context types are needed.
        
        Uses keyword matching and pattern detection.
        
        Args:
            query: User's query text
        
        Returns:
            List of relevant ContextType values
        """
        query_lower = query.lower()
        needs = []
        
        # Check each context type for keyword matches
        for context_type, keywords in CONTEXT_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                needs.append(context_type)
        
        # Default: include basic context if nothing specific detected
        if not needs:
            needs = [
                ContextType.RECENT_VITALS,
                ContextType.USER_PREFERENCES
            ]
        
        # Check for emergency keywords - prioritize emergency info
        emergency_keywords = CONTEXT_KEYWORDS[ContextType.EMERGENCY_INFO]
        if any(kw in query_lower for kw in emergency_keywords):
            # Emergency: include medical history and medications
            if ContextType.MEDICAL_HISTORY not in needs:
                needs.insert(0, ContextType.MEDICAL_HISTORY)
            if ContextType.MEDICATIONS not in needs:
                needs.insert(1, ContextType.MEDICATIONS)
        
        return needs
    
    async def _parallel_retrieve(
        self,
        user_id: str,
        session_id: str,
        query: str,
        context_types: List[ContextType]
    ) -> List[RetrievedContext]:
        """
        Retrieve context from multiple sources in parallel.
        
        Uses asyncio.gather for concurrent retrieval with timeout.
        """
        tasks = []
        
        # Create retrieval tasks for each context type
        for ctx_type in context_types:
            task = self._retrieve_single_type(
                user_id=user_id,
                session_id=session_id,
                query=query,
                context_type=ctx_type
            )
            tasks.append(task)
        
        # Execute all retrievals in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Context retrieval timed out after {self.timeout}s")
            results = []
        
        # Flatten results and filter out exceptions
        contexts = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Retrieval error: {result}")
                continue
            if isinstance(result, list):
                contexts.extend(result)
            elif result is not None:
                contexts.append(result)
        
        return contexts
    
    async def _retrieve_single_type(
        self,
        user_id: str,
        session_id: str,
        query: str,
        context_type: ContextType
    ) -> List[RetrievedContext]:
        """Retrieve a single context type."""
        try:
            if context_type == ContextType.RECENT_VITALS:
                return await self._get_recent_vitals(user_id)
            
            elif context_type == ContextType.LAST_CONSULTATION:
                return await self._get_last_consultation(user_id)
            
            elif context_type == ContextType.MEDICATIONS:
                return await self._get_medications(user_id)
            
            elif context_type == ContextType.RECENT_CONVERSATIONS:
                return await self._get_recent_conversations(session_id, limit=5)
            
            elif context_type == ContextType.USER_PREFERENCES:
                return await self._get_user_preferences(user_id)
            
            elif context_type == ContextType.RISK_ASSESSMENTS:
                return await self._get_risk_assessments(user_id)
            
            elif context_type == ContextType.MEDICAL_HISTORY:
                return await self._get_medical_history(user_id)
            
            elif context_type == ContextType.LIFESTYLE_DATA:
                return await self._get_lifestyle_data(user_id)
            
            elif context_type == ContextType.EMERGENCY_INFO:
                return await self._get_emergency_info(user_id)
            
            else:
                logger.warning(f"Unknown context type: {context_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving {context_type.value}: {e}")
            return []
    
    # ========================================================================
    # Individual Context Retrieval Methods
    # ========================================================================
    
    async def _get_recent_vitals(
        self, 
        user_id: str, 
        hours: int = 24
    ) -> List[RetrievedContext]:
        """Get recent vital signs."""
        if not self.vitals:
            # Return mock data if service not available
            return [RetrievedContext(
                context_type=ContextType.RECENT_VITALS,
                data={
                    "message": "No vitals service connected",
                    "available": False
                },
                relevance_score=0.3,
                timestamp=datetime.utcnow(),
                source="mock"
            )]
        
        try:
            # Call vitals service
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            vitals = await self.vitals.get_recent_vitals(
                user_id=user_id,
                since=cutoff
            )
            
            if not vitals:
                return []
            
            return [RetrievedContext(
                context_type=ContextType.RECENT_VITALS,
                data={"vitals": vitals},
                relevance_score=0.8,
                timestamp=datetime.utcnow(),
                source="vitals_db"
            )]
        except Exception as e:
            logger.error(f"Error getting vitals for {user_id}: {e}")
            return []
    
    async def _get_last_consultation(
        self, 
        user_id: str
    ) -> List[RetrievedContext]:
        """Get last doctor consultation summary."""
        if not self.patient_data:
            return []
        
        try:
            consultation = await self.patient_data.get_last_consultation(user_id)
            
            if not consultation:
                return []
            
            return [RetrievedContext(
                context_type=ContextType.LAST_CONSULTATION,
                data=consultation,
                relevance_score=0.7,
                timestamp=datetime.utcnow(),
                source="consultations_db"
            )]
        except Exception as e:
            logger.error(f"Error getting consultation for {user_id}: {e}")
            return []
    
    async def _get_medications(
        self, 
        user_id: str
    ) -> List[RetrievedContext]:
        """Get current medications list."""
        if not self.patient_data:
            return []
        
        try:
            medications = await self.patient_data.get_medications(user_id)
            
            if not medications:
                return []
            
            return [RetrievedContext(
                context_type=ContextType.MEDICATIONS,
                data={"medications": medications},
                relevance_score=0.8,
                timestamp=datetime.utcnow(),
                source="medications_db"
            )]
        except Exception as e:
            logger.error(f"Error getting medications for {user_id}: {e}")
            return []
    
    async def _get_recent_conversations(
        self, 
        session_id: str, 
        limit: int = 5
    ) -> List[RetrievedContext]:
        """Get recent conversation messages."""
        if not self.chat_history:
            return []
        
        try:
            history = self.chat_history.get_history(session_id, limit=limit)
            
            if not history:
                return []
            
            return [RetrievedContext(
                context_type=ContextType.RECENT_CONVERSATIONS,
                data={"messages": history},
                relevance_score=0.9,  # High relevance for conversation continuity
                timestamp=datetime.utcnow(),
                source="chat_history"
            )]
        except Exception as e:
            logger.error(f"Error getting conversations for {session_id}: {e}")
            return []
    
    async def _get_user_preferences(
        self, 
        user_id: str
    ) -> List[RetrievedContext]:
        """Get user preferences and settings."""
        if not self.preferences:
            return []
        
        try:
            prefs = self.preferences.get_all_preferences(
                user_id=user_id,
                include_sensitive=False
            )
            
            if not prefs:
                return []
            
            return [RetrievedContext(
                context_type=ContextType.USER_PREFERENCES,
                data={"preferences": prefs},
                relevance_score=0.6,  # Lower priority but always useful
                timestamp=datetime.utcnow(),
                source="preferences_db"
            )]
        except Exception as e:
            logger.error(f"Error getting preferences for {user_id}: {e}")
            return []
    
    async def _get_risk_assessments(
        self, 
        user_id: str
    ) -> List[RetrievedContext]:
        """Get cardiac risk assessment results."""
        if not self.patient_data:
            return []
        
        try:
            assessments = await self.patient_data.get_risk_assessments(
                user_id=user_id,
                limit=3
            )
            
            if not assessments:
                return []
            
            return [RetrievedContext(
                context_type=ContextType.RISK_ASSESSMENTS,
                data={"assessments": assessments},
                relevance_score=0.75,
                timestamp=datetime.utcnow(),
                source="risk_assessments_db"
            )]
        except Exception as e:
            logger.error(f"Error getting risk assessments for {user_id}: {e}")
            return []
    
    async def _get_medical_history(
        self, 
        user_id: str
    ) -> List[RetrievedContext]:
        """Get patient medical history."""
        if not self.patient_data:
            return []
        
        try:
            history = await self.patient_data.get_medical_history(user_id)
            
            if not history:
                return []
            
            return [RetrievedContext(
                context_type=ContextType.MEDICAL_HISTORY,
                data=history,
                relevance_score=0.7,
                timestamp=datetime.utcnow(),
                source="medical_history_db"
            )]
        except Exception as e:
            logger.error(f"Error getting medical history for {user_id}: {e}")
            return []
    
    async def _get_lifestyle_data(
        self, 
        user_id: str
    ) -> List[RetrievedContext]:
        """Get lifestyle data (exercise, diet, sleep)."""
        if not self.patient_data:
            return []
        
        try:
            lifestyle = await self.patient_data.get_lifestyle_data(
                user_id=user_id,
                days=7
            )
            
            if not lifestyle:
                return []
            
            return [RetrievedContext(
                context_type=ContextType.LIFESTYLE_DATA,
                data=lifestyle,
                relevance_score=0.5,
                timestamp=datetime.utcnow(),
                source="lifestyle_db"
            )]
        except Exception as e:
            logger.error(f"Error getting lifestyle data for {user_id}: {e}")
            return []
    
    async def _get_emergency_info(
        self, 
        user_id: str
    ) -> List[RetrievedContext]:
        """Get emergency contact and critical health info."""
        if not self.patient_data:
            return []
        
        try:
            emergency = await self.patient_data.get_emergency_info(user_id)
            
            if not emergency:
                return []
            
            return [RetrievedContext(
                context_type=ContextType.EMERGENCY_INFO,
                data=emergency,
                relevance_score=1.0,  # Highest priority
                timestamp=datetime.utcnow(),
                source="emergency_db"
            )]
        except Exception as e:
            logger.error(f"Error getting emergency info for {user_id}: {e}")
            return []
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def _calculate_relevance_scores(
        self,
        contexts: List[RetrievedContext],
        query: str
    ) -> List[RetrievedContext]:
        """
        Calculate relevance scores based on query similarity.
        
        Uses keyword overlap and recency weighting.
        """
        query_words = set(query.lower().split())
        
        for ctx in contexts:
            # Start with base relevance
            score = ctx.relevance_score
            
            # Boost based on keyword overlap with context data
            data_str = str(ctx.data).lower()
            overlap = len(query_words & set(data_str.split()))
            if overlap > 0:
                score += min(0.2, overlap * 0.05)
            
            # Recency boost for recent data
            age_hours = (datetime.utcnow() - ctx.timestamp).total_seconds() / 3600
            if age_hours < 1:
                score += 0.1
            elif age_hours < 24:
                score += 0.05
            
            # Cap at 1.0
            ctx.relevance_score = min(1.0, score)
        
        return contexts
    
    def _trim_to_token_limit(
        self, 
        contexts: List[RetrievedContext]
    ) -> List[RetrievedContext]:
        """Trim context list to fit within token budget."""
        result = []
        total_tokens = 0
        
        for ctx in contexts:
            if total_tokens + ctx.token_estimate <= self.max_tokens:
                result.append(ctx)
                total_tokens += ctx.token_estimate
            else:
                # Try to include partial context
                remaining = self.max_tokens - total_tokens
                if remaining > 100:  # Worth including if >100 tokens remain
                    # Truncate data to fit
                    ctx.token_estimate = remaining
                    result.append(ctx)
                break
        
        return result
    
    def _make_cache_key(
        self, 
        user_id: str, 
        session_id: str, 
        query: str
    ) -> str:
        """Generate cache key for query."""
        key_str = f"{user_id}:{session_id}:{query[:100]}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached(self, key: str) -> Optional[List[RetrievedContext]]:
        """Get cached result if not expired."""
        if key in self._cache:
            contexts, timestamp = self._cache[key]
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age < self._cache_ttl:
                return contexts
            else:
                del self._cache[key]
        return None
    
    def _set_cached(self, key: str, contexts: List[RetrievedContext]) -> None:
        """Cache result with timestamp."""
        self._cache[key] = (contexts, datetime.utcnow())
        
        # Simple cache eviction - keep last 100 entries
        if len(self._cache) > 100:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k][1]
            )
            del self._cache[oldest_key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        return {
            "retrieval_count": self._retrieval_count,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": (
                self._cache_hits / max(1, self._retrieval_count) * 100
            ),
            "avg_retrieval_time_ms": (
                self._total_retrieval_time / max(1, self._retrieval_count) * 1000
            ),
            "cache_size": len(self._cache)
        }


# ============================================================================
# Singleton Instance
# ============================================================================

# Default context retriever instance
context_retriever = ContextRetriever()
