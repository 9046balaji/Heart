"""
Performance Monitor Stub

Stub implementation for performance monitoring.
"""


def record_rerank_operation(elapsed_ms: float):
    """Record rerank operation duration."""
    pass

def record_embedding_operation(elapsed_ms: float):
    """Record embedding operation duration."""
    pass

def record_cache_operation(operation: str, hit: bool = False, latency_ms: float = 0.0):
    """Record cache operation metrics."""
    pass

class CacheTimer:
    """Context manager for timing cache operations."""
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass