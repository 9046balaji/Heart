"""
Short-term Memory Module for Memori

Provides session-based memory buffering with Redis support.
Supports in-memory fallback when Redis is not available.
"""

from .redis_buffer import (
    RedisSessionBuffer,
    get_session_buffer,
)

__all__ = [
    "RedisSessionBuffer",
    "get_session_buffer",
]
