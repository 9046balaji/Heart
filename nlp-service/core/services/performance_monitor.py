"""
Performance Monitoring Service

Monitors and reports key performance metrics for the healthcare AI system
based on the performance architecture standards defined in PERFORMANCE_ARCHITECTURE.md

Key Metrics Tracked:
- Cache performance (hit rates, latency)
- ONNX embedding performance (latency, throughput)
- Reranking performance (latency, accuracy)
- Overall system response times
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import deque
import threading

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    timestamp: datetime = field(default_factory=datetime.now)
    cache_hit_rate: float = 0.0
    cache_avg_get_latency_ms: float = 0.0
    cache_avg_set_latency_ms: float = 0.0
    embedding_avg_latency_ms: float = 0.0
    rerank_avg_latency_ms: float = 0.0
    query_avg_latency_ms: float = 0.0
    total_requests: int = 0
    cache_requests: int = 0
    embedding_requests: int = 0
    rerank_requests: int = 0
    query_requests: int = 0


class PerformanceMonitor:
    """
    Performance monitoring service that tracks key metrics
    for the healthcare AI system according to architecture standards.
    """
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._lock = threading.Lock()
        
        # Performance tracking
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_get_times = deque(maxlen=window_size)
        self.cache_set_times = deque(maxlen=window_size)
        self.embedding_times = deque(maxlen=window_size)
        self.rerank_times = deque(maxlen=window_size)
        self.query_times = deque(maxlen=window_size)
        
        # Statistics cache for performance
        self._last_stats = None
        self._last_stats_time = 0
        self._stats_cache_ttl = 1.0  # 1 second cache
        
    def record_cache_operation(self, operation: str, hit: bool = False, latency_ms: float = 0.0):
        """Record cache operation performance"""
        with self._lock:
            if operation == "get":
                self.cache_get_times.append(latency_ms)
                if hit:
                    self.cache_hits += 1
                else:
                    self.cache_misses += 1
            elif operation == "set":
                self.cache_set_times.append(latency_ms)
    
    def record_embedding_operation(self, latency_ms: float):
        """Record embedding operation performance"""
        with self._lock:
            self.embedding_times.append(latency_ms)
    
    def record_rerank_operation(self, latency_ms: float):
        """Record rerank operation performance"""
        with self._lock:
            self.rerank_times.append(latency_ms)
    
    def record_query_operation(self, latency_ms: float):
        """Record query operation performance"""
        with self._lock:
            self.query_times.append(latency_ms)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        with self._lock:
            total_requests = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
            
            avg_get_latency = (
                sum(self.cache_get_times) / len(self.cache_get_times) if self.cache_get_times else 0
            )
            avg_set_latency = (
                sum(self.cache_set_times) / len(self.cache_set_times) if self.cache_set_times else 0
            )
            
            return {
                "hit_rate_percent": hit_rate,
                "total_requests": total_requests,
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "avg_get_latency_ms": avg_get_latency,
                "avg_set_latency_ms": avg_set_latency,
                "current_window_size": len(self.cache_get_times)
            }
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding performance statistics"""
        with self._lock:
            avg_latency = (
                sum(self.embedding_times) / len(self.embedding_times) if self.embedding_times else 0
            )
            return {
                "avg_latency_ms": avg_latency,
                "total_operations": len(self.embedding_times),
                "current_window_size": len(self.embedding_times)
            }
    
    def get_rerank_stats(self) -> Dict[str, Any]:
        """Get reranking performance statistics"""
        with self._lock:
            avg_latency = (
                sum(self.rerank_times) / len(self.rerank_times) if self.rerank_times else 0
            )
            return {
                "avg_latency_ms": avg_latency,
                "total_operations": len(self.rerank_times),
                "current_window_size": len(self.rerank_times)
            }
    
    def get_query_stats(self) -> Dict[str, Any]:
        """Get query performance statistics"""
        with self._lock:
            avg_latency = (
                sum(self.query_times) / len(self.query_times) if self.query_times else 0
            )
            return {
                "avg_latency_ms": avg_latency,
                "total_operations": len(self.query_times),
                "current_window_size": len(self.query_times)
            }
    
    def get_overall_metrics(self) -> PerformanceMetrics:
        """Get comprehensive performance metrics"""
        cache_stats = self.get_cache_stats()
        embedding_stats = self.get_embedding_stats()
        rerank_stats = self.get_rerank_stats()
        query_stats = self.get_query_stats()
        
        return PerformanceMetrics(
            cache_hit_rate=cache_stats["hit_rate_percent"],
            cache_avg_get_latency_ms=cache_stats["avg_get_latency_ms"],
            cache_avg_set_latency_ms=cache_stats["avg_set_latency_ms"],
            embedding_avg_latency_ms=embedding_stats["avg_latency_ms"],
            rerank_avg_latency_ms=rerank_stats["avg_latency_ms"],
            query_avg_latency_ms=query_stats["avg_latency_ms"],
            total_requests=cache_stats["total_requests"] + query_stats["total_operations"],
            cache_requests=cache_stats["total_requests"],
            embedding_requests=embedding_stats["total_operations"],
            rerank_requests=rerank_stats["total_operations"],
            query_requests=query_stats["total_operations"]
        )
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check against performance benchmarks"""
        metrics = self.get_overall_metrics()
        issues = []
        
        # Check cache performance
        if metrics.cache_hit_rate < 50:
            issues.append(f"Low cache hit rate: {metrics.cache_hit_rate:.1f}% (target: >50%)")
        if metrics.cache_avg_get_latency_ms > 20:
            issues.append(f"High cache GET latency: {metrics.cache_avg_get_latency_ms:.2f}ms (target: <20ms)")
        if metrics.cache_avg_set_latency_ms > 20:
            issues.append(f"High cache SET latency: {metrics.cache_avg_set_latency_ms:.2f}ms (target: <20ms)")
            
        # Check ONNX embedding performance
        if metrics.embedding_avg_latency_ms > 50:
            issues.append(f"High embedding latency: {metrics.embedding_avg_latency_ms:.2f}ms (target: <50ms)")
            
        # Check reranking performance
        if metrics.rerank_avg_latency_ms > 200:
            issues.append(f"High rerank latency: {metrics.rerank_avg_latency_ms:.2f}ms (target: <200ms)")
            
        # Check query performance
        if metrics.query_avg_latency_ms > 1000:
            issues.append(f"High query latency: {metrics.query_avg_latency_ms:.2f}ms (target: <1000ms)")
            
        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "metrics": metrics.__dict__
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary for API endpoints"""
        return {
            "timestamp": datetime.now().isoformat(),
            "cache_stats": self.get_cache_stats(),
            "embedding_stats": self.get_embedding_stats(),
            "rerank_stats": self.get_rerank_stats(),
            "query_stats": self.get_query_stats(),
            "health": self.health_check()
        }


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def record_cache_operation(operation: str, hit: bool = False, latency_ms: float = 0.0):
    """Convenience function to record cache operation"""
    monitor = get_performance_monitor()
    monitor.record_cache_operation(operation, hit, latency_ms)


def record_embedding_operation(latency_ms: float):
    """Convenience function to record embedding operation"""
    monitor = get_performance_monitor()
    monitor.record_embedding_operation(latency_ms)


def record_rerank_operation(latency_ms: float):
    """Convenience function to record rerank operation"""
    monitor = get_performance_monitor()
    monitor.record_rerank_operation(latency_ms)


def record_query_operation(latency_ms: float):
    """Convenience function to record query operation"""
    monitor = get_performance_monitor()
    monitor.record_query_operation(latency_ms)


def get_performance_metrics() -> Dict[str, Any]:
    """Convenience function to get performance metrics"""
    monitor = get_performance_monitor()
    return monitor.to_dict()


def performance_health_check() -> Dict[str, Any]:
    """Convenience function to perform health check"""
    monitor = get_performance_monitor()
    return monitor.health_check()


# Context managers for timing operations
class CacheTimer:
    """Context manager for timing cache operations"""
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency_ms = (time.time() - self.start_time) * 1000
            record_cache_operation(self.operation, latency_ms=latency_ms)


class EmbeddingTimer:
    """Context manager for timing embedding operations"""
    def __init__(self):
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency_ms = (time.time() - self.start_time) * 1000
            record_embedding_operation(latency_ms)


class RerankTimer:
    """Context manager for timing rerank operations"""
    def __init__(self):
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency_ms = (time.time() - self.start_time) * 1000
            record_rerank_operation(latency_ms)


class QueryTimer:
    """Context manager for timing query operations"""
    def __init__(self):
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency_ms = (time.time() - self.start_time) * 1000
            record_query_operation(latency_ms)