"""
Production-grade In-Memory Cache for NLP Service

Features:
- Thread-safe LRU eviction policy
- Per-entry TTL (Time-To-Live)
- Metrics and observability
- Health monitoring
- Policy-based TTL for different data types
"""
import json
import logging
import time
import threading
from typing import Any, Optional, Dict
from collections import OrderedDict
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from error_handling import CacheError  # PHASE 2: Import exception hierarchy

logger = logging.getLogger(__name__)


class CacheTTLPolicy(Enum):
    """TTL policies for different data types in healthcare."""
    
    # Short TTL: Volatile data that changes frequently
    INTENT_RESULTS = 300  # 5 minutes (user requests change intent)
    SENTIMENT_ANALYSIS = 300  # 5 minutes (per-session analysis)
    
    # Medium TTL: Data that changes occasionally
    VITAL_SIGNS = 1800  # 30 minutes (measurements stay valid)
    ENTITY_EXTRACTION = 900  # 15 minutes (per-text basis)
    HEALTH_ASSESSMENT = 1800  # 30 minutes
    
    # Long TTL: Stable reference data
    PROVIDER_SCHEDULES = 7200  # 2 hours (updated batch-wise)
    PATIENT_PREFERENCES = 86400  # 24 hours (rarely changes)


@dataclass
class CacheMetrics:
    """Metrics for cache performance monitoring."""
    
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    errors: int = 0
    total_set_duration_ms: float = 0
    total_get_duration_ms: float = 0
    
    @property
    def total_requests(self) -> int:
        """Total cache requests."""
        return self.hits + self.misses
    
    @property
    def hit_rate(self) -> float:
        """Cache hit rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100
    
    @property
    def avg_get_duration_ms(self) -> float:
        """Average GET duration in milliseconds."""
        if self.hits == 0:
            return 0.0
        return self.total_get_duration_ms / self.hits
    
    @property
    def avg_set_duration_ms(self) -> float:
        """Average SET duration in milliseconds."""
        if self.hits + self.evictions == 0:
            return 0.0
        return self.total_set_duration_ms / (self.hits + self.evictions)


class InMemoryCache:
    """
    Production-grade in-memory cache with LRU eviction policy.
    
    Features:
    - Thread-safe operations (RLock for re-entrant access)
    - Per-entry TTL (Time-To-Live) tracking
    - LRU (Least Recently Used) eviction
    - Comprehensive metrics and monitoring
    - Support for TTL policies
    
    Complexity Analysis:
    - get(): O(1) amortized (dict lookup + OrderedDict move)
    - set(): O(1) amortized (dict insert + LRU eviction)
    - delete(): O(1) (dict deletion)
    - flush(): O(n) where n = cache size
    
    Space Complexity: O(max_size) bounded memory usage
    """

    def __init__(self, max_size: int = 1000):
        """Initialize in-memory cache with thread safety and metrics.
        
        Args:
            max_size: Maximum number of entries before LRU eviction
        """
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.max_size = max_size
        self._lock = threading.RLock()  # Re-entrant lock for nested method calls
        self.metrics = CacheMetrics()
        self.creation_time = datetime.now()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache (thread-safe).
        
        Implements LRU behavior:
        - Cache hits move item to end (most recently used)
        - Expired items are removed and counted as misses

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        start_time = time.time()
        with self._lock:
            try:
                if key not in self.cache:
                    self.metrics.misses += 1
                    return None
                
                item = self.cache[key]
                
                # Check if expired
                age_seconds = time.time() - item['timestamp']
                if age_seconds >= item['ttl']:
                    # Expired - remove and count as miss
                    del self.cache[key]
                    self.metrics.misses += 1
                    logger.debug(f"Cache expired: {key} (age={age_seconds:.1f}s, ttl={item['ttl']}s)")
                    return None
                
                # Valid cache hit - move to end (most recently used)
                self.cache.move_to_end(key)
                self.metrics.hits += 1
                
                # Track performance
                duration_ms = (time.time() - start_time) * 1000
                self.metrics.total_get_duration_ms += duration_ms
                
                return item['value']
                
            except Exception as e:
                logger.error(f"Cache get failed for key '{key}': {e}", exc_info=True)
                self.metrics.errors += 1
                return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        ttl_policy: Optional[CacheTTLPolicy] = None
    ) -> bool:
        """
        Set value in cache with TTL (thread-safe).
        
        Implements LRU eviction:
        - When cache is full, removes least recently used item
        - Supports both explicit TTL and policy-based TTL

        Args:
            key: Cache key
            value: Value to cache
            ttl: Explicit TTL in seconds (overrides policy)
            ttl_policy: CacheTTLPolicy enum for policy-based TTL

        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        
        # Determine TTL
        if ttl is None:
            if ttl_policy is not None:
                ttl = ttl_policy.value
            else:
                ttl = 3600  # Default 1 hour
        
        with self._lock:
            try:
                # Remove existing entry if present
                if key in self.cache:
                    del self.cache[key]
                
                # Evict LRU items if at capacity
                while len(self.cache) >= self.max_size:
                    evicted_key, _ = self.cache.popitem(last=False)
                    self.metrics.evictions += 1
                    logger.debug(f"Cache eviction (LRU): {evicted_key}")
                
                # Add new entry
                self.cache[key] = {
                    'value': value,
                    'timestamp': time.time(),
                    'ttl': ttl,
                }
                
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                
                # Track performance
                duration_ms = (time.time() - start_time) * 1000
                self.metrics.total_set_duration_ms += duration_ms
                
                logger.debug(f"Cache set: {key} (ttl={ttl}s)")
                return True
                
            except Exception as e:
                logger.error(f"Cache set failed for key '{key}': {e}", exc_info=True)
                self.metrics.errors += 1
                return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache (thread-safe).

        Args:
            key: Cache key to delete

        Returns:
            True if key existed and was deleted, False otherwise
        """
        with self._lock:
            try:
                if key in self.cache:
                    del self.cache[key]
                    logger.debug(f"Cache delete: {key}")
                    return True
                return False
            except Exception as e:
                logger.error(f"Cache delete failed for key '{key}': {e}")
                self.metrics.errors += 1
                return False

    def clear(self) -> bool:
        """
        Clear all cache entries (thread-safe).
        
        Resets hit/miss counters but preserves error tracking.

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                size_before = len(self.cache)
                self.cache.clear()
                self.metrics.hits = 0
                self.metrics.misses = 0
                self.metrics.total_set_duration_ms = 0
                self.metrics.total_get_duration_ms = 0
                logger.info(f"Cache cleared: removed {size_before} entries")
                return True
            except Exception as e:
                logger.error(f"Cache clear failed: {e}")
                self.metrics.errors += 1
                return False
    
    # Alias for backward compatibility
    flush = clear

    def get_stats(self) -> dict:
        """
        Get comprehensive cache statistics (thread-safe).
        
        Returns detailed metrics for monitoring and debugging.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            try:
                uptime_seconds = (datetime.now() - self.creation_time).total_seconds()
                
                return {
                    "status": "healthy",
                    "enabled": True,
                    "size": len(self.cache),
                    "max_size": self.max_size,
                    "utilization_percent": (len(self.cache) / self.max_size * 100) if self.max_size > 0 else 0,
                    "hits": self.metrics.hits,
                    "misses": self.metrics.misses,
                    "hit_rate_percent": f"{self.metrics.hit_rate:.2f}%",
                    "total_requests": self.metrics.total_requests,
                    "evictions": self.metrics.evictions,
                    "errors": self.metrics.errors,
                    "avg_get_duration_ms": f"{self.metrics.avg_get_duration_ms:.3f}",
                    "avg_set_duration_ms": f"{self.metrics.avg_set_duration_ms:.3f}",
                    "uptime_seconds": uptime_seconds,
                }
            except Exception as e:
                logger.error(f"Cache stats failed: {e}")
                return {
                    "status": "error",
                    "enabled": False,
                    "error": str(e),
                }
    
    def warm_up(self, warmup_data: Dict[str, tuple]) -> int:
        """
        Pre-populate cache with warmup data.
        
        Benefits:
        - Reduce cold start latency
        - Avoid thundering herd on startup
        - Pre-load frequently accessed data
        
        Complexity: O(n) where n = number of warmup entries
        
        Args:
            warmup_data: Dict mapping cache_key -> (value, ttl_policy)
            
        Returns:
            Number of entries loaded
            
        Example:
            warmup_data = {
                'intent:greeting': ('GREETING intent', CacheTTLPolicy.INTENT_RESULTS),
                'symptom:chest_pain': ('chest pain entity', CacheTTLPolicy.ENTITY_EXTRACTION),
            }
            loaded = cache_manager.warm_up(warmup_data)
            print(f"Warmed up {loaded} cache entries")
        """
        loaded = 0
        with self._lock:
            try:
                for cache_key, (value, ttl_policy) in warmup_data.items():
                    if self.set(cache_key, value, ttl_policy=ttl_policy):
                        loaded += 1
                
                logger.info(f"Cache warm-up complete: {loaded}/{len(warmup_data)} entries loaded")
                return loaded
                
            except Exception as e:
                logger.error(f"Cache warm-up failed: {e}")
                return loaded


# ============================================================================
# CACHE USAGE EXAMPLES WITH TTL POLICIES
# ============================================================================

def cache_with_policy(ttl_policy: CacheTTLPolicy):
    """
    Decorator for caching function results with policy-based TTL.
    
    Usage:
        @cache_with_policy(CacheTTLPolicy.VITAL_SIGNS)
        def get_patient_vitals(patient_id: str):
            # Expensive operation
            return fetch_vitals_from_db(patient_id)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args if isinstance(arg, (str, int)))
            cache_key = "|".join(key_parts)
            
            # Try cache first
            cached = cache_manager.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached
            
            # Execute and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl_policy=ttl_policy)
            
            return result
        return wrapper
    return decorator


# Global cache manager instance
cache_manager = InMemoryCache(max_size=1000)