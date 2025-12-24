"""
Synchronous Cache Implementation with Advanced Features

This provides the same interface as the old cache_manager but with advanced features
like LRU eviction, thread safety, and performance metrics similar to the advanced cache.
"""

import time
import threading
from typing import Any, Optional, Dict
from collections import OrderedDict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SyncCacheManager:
    """
    Synchronous cache with LRU eviction, TTL, and thread safety.
    Provides the same interface as the old cache_manager but with enhanced features.
    """

    def __init__(self, max_size: int = 10000):
        self._cache: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._access_times: Dict[str, float] = {}  # For LRU tracking
        self._max_size = max_size
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            if key in self._expiry and time.time() > self._expiry[key]:
                del self._cache[key]
                del self._expiry[key]
                if key in self._access_times:
                    del self._access_times[key]
                self._misses += 1
                return None

            # Update access time for LRU
            self._access_times[key] = time.time()
            self._hits += 1
            return self._cache[key]

    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache with TTL, with LRU eviction when full."""
        with self._lock:
            # Check if we need to evict due to size limit
            if len(self._cache) >= self._max_size and key not in self._cache:
                # Find least recently used item
                if self._access_times:
                    lru_key = min(self._access_times, key=self._access_times.get)
                    del self._cache[lru_key]
                    del self._expiry[lru_key]
                    del self._access_times[lru_key]
                    logger.debug(f"Cache eviction (LRU): {lru_key}")

            self._cache[key] = value
            if ttl:
                self._expiry[key] = time.time() + ttl
            self._access_times[key] = time.time()

    def delete(self, key: str):
        """Delete a key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._expiry:
                    del self._expiry[key]
                if key in self._access_times:
                    del self._access_times[key]

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._expiry.clear()
            self._access_times.clear()

    def get_stats(self):
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "utilization": len(self._cache) / self._max_size * 100 if self._max_size > 0 else 0
            }


# Global cache manager instance
cache_manager = SyncCacheManager(max_size=10000)