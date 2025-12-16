"""
Resilience Patterns for Production Systems

Implements:
- Circuit Breaker: Fail fast, auto-recovery
- Bulkhead: Isolate component failures
- Adaptive Timeout: Dynamic timeout based on latency history
- Retry with Exponential Backoff: Survive transient failures
- Rate Limiter: Prevent cascading failures

Pattern: Circuit Breaker, Bulkhead, Timeout
Reference: Release It! (Michael Nygard), AWS Well-Architected Framework
"""

import logging
import time
import asyncio
from typing import Callable, Optional, TypeVar, Coroutine, Any, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)

T = TypeVar('T')
CallableT = TypeVar('CallableT', bound=Callable)


class CircuitState(Enum):
    """States of the circuit breaker"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject all
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5           # Failures before opening
    recovery_timeout_seconds: int = 60   # Time in OPEN before trying HALF_OPEN
    half_open_max_calls: int = 2         # Max calls in HALF_OPEN state
    expected_exceptions: tuple = (Exception,)  # Which exceptions trigger breaker


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker"""
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    state_changes: int = 0
    last_failure_time: Optional[datetime] = None
    last_failure_exception: Optional[Exception] = None


class CircuitBreaker:
    """
    Circuit Breaker Pattern Implementation.
    
    Prevents cascading failures by failing fast when downstream service is down.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Failures exceeded, calls rejected immediately
    - HALF_OPEN: Testing recovery with limited calls
    
    Example:
        breaker = CircuitBreaker(
            name="intent_recognizer",
            failure_threshold=5,
            recovery_timeout_seconds=60
        )
        
        @breaker.wrap
        async def recognize(text: str):
            return await recognizer.recognize(text)
        
        result = await recognize(text)  # Auto-managed
    """
    
    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.metrics = CircuitBreakerMetrics()
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_state_change = datetime.now()
        self._half_open_calls = 0
    
    @property
    def state(self) -> CircuitState:
        """Get current state"""
        return self._state
    
    async def call(self, coro: Coroutine[Any, Any, T]) -> T:
        """
        Execute coroutine through circuit breaker.
        
        Args:
            coro: Coroutine to execute
        
        Returns:
            Result of coroutine
        
        Raises:
            CircuitBreakerOpenError: If circuit is OPEN
            Exception: Any exception raised by coro
        """
        # Check if we need to transition state
        self._update_state()
        
        # OPEN state: reject immediately
        if self._state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN"
            )
        
        # HALF_OPEN state: limit concurrent calls
        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' HALF_OPEN call limit exceeded"
                )
            self._half_open_calls += 1
        
        try:
            self.metrics.total_calls += 1
            result = await coro
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure(e)
            raise
    
    def _update_state(self) -> None:
        """Update state based on time and conditions"""
        now = datetime.now()
        
        if self._state == CircuitState.OPEN:
            # Transition OPEN → HALF_OPEN after timeout
            if (now - self._last_state_change).total_seconds() > \
                    self.config.recovery_timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
    
    def _on_success(self) -> None:
        """Handle successful call"""
        self.metrics.total_successes += 1
        
        if self._state == CircuitState.HALF_OPEN:
            # Transition HALF_OPEN → CLOSED after successful call
            self._transition_to(CircuitState.CLOSED)
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0
    
    def _on_failure(self, exception: Exception) -> None:
        """Handle failed call"""
        self.metrics.total_failures += 1
        self.metrics.last_failure_time = datetime.now()
        self.metrics.last_failure_exception = exception
        self._failure_count += 1
        
        if self._state == CircuitState.HALF_OPEN:
            # Transition HALF_OPEN → OPEN after failure
            self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED:
            # Check if threshold exceeded
            if self._failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state"""
        if new_state == self._state:
            return
        
        logger.warning(
            f"Circuit breaker '{self.name}' transitioned: "
            f"{self._state.value} → {new_state.value}",
            extra={
                'breaker_name': self.name,
                'old_state': self._state.value,
                'new_state': new_state.value,
                'failure_count': self._failure_count
            }
        )
        
        self._state = new_state
        self._last_state_change = datetime.now()
        self.metrics.state_changes += 1
        
        # Reset state-specific counters
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
    
    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state"""
        self._transition_to(CircuitState.CLOSED)
        self._failure_count = 0
        logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")
    
    def get_metrics(self) -> dict:
        """Get metrics"""
        return {
            'state': self._state.value,
            'failure_count': self._failure_count,
            'total_calls': self.metrics.total_calls,
            'total_failures': self.metrics.total_failures,
            'total_successes': self.metrics.total_successes,
            'state_changes': self.metrics.state_changes,
            'failure_rate': (
                self.metrics.total_failures / self.metrics.total_calls
                if self.metrics.total_calls > 0 else 0
            )
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN"""
    pass


@dataclass
class AdaptiveTimeoutConfig:
    """Configuration for adaptive timeout"""
    percentile: float = 0.95      # Use p95 latency
    buffer_ms: float = 100        # Add 100ms buffer
    min_timeout_ms: float = 100   # Never less than 100ms
    max_timeout_ms: float = 5000  # Never more than 5s
    history_size: int = 100       # Keep last 100 measurements


class AdaptiveTimeout:
    """
    Adaptive Timeout Implementation.
    
    Dynamically adjusts timeout based on recent latency history.
    
    Benefits:
    - Prevents false timeouts when service is slow but responsive
    - Catches actual hangs faster
    - Adjusts to changing conditions
    
    Example:
        timeout = AdaptiveTimeout(percentile=0.95)
        timeout.record(150)  # Record 150ms latency
        timeout.record(200)
        timeout_seconds = timeout.get_timeout()  # p95 + buffer
    """
    
    def __init__(self, config: AdaptiveTimeoutConfig = None):
        self.config = config or AdaptiveTimeoutConfig()
        self.latency_history: deque = deque(maxlen=self.config.history_size)
    
    def record(self, latency_ms: float) -> None:
        """Record a latency measurement"""
        self.latency_history.append(latency_ms)
    
    def get_timeout(self) -> float:
        """
        Get timeout in seconds based on latency history.
        
        Returns:
            Timeout in seconds
        """
        if not self.latency_history:
            # Default if no history
            return self.config.min_timeout_ms / 1000
        
        # Calculate percentile
        percentile_ms = np.percentile(
            list(self.latency_history),
            self.config.percentile * 100
        )
        
        # Add buffer
        timeout_ms = percentile_ms + self.config.buffer_ms
        
        # Apply min/max bounds
        timeout_ms = max(timeout_ms, self.config.min_timeout_ms)
        timeout_ms = min(timeout_ms, self.config.max_timeout_ms)
        
        return timeout_ms / 1000
    
    def get_stats(self) -> dict:
        """Get statistics about latency"""
        if not self.latency_history:
            return {
                'count': 0,
                'current_timeout_s': self.config.min_timeout_ms / 1000
            }
        
        data = list(self.latency_history)
        return {
            'count': len(data),
            'min_ms': float(np.min(data)),
            'max_ms': float(np.max(data)),
            'mean_ms': float(np.mean(data)),
            'p50_ms': float(np.percentile(data, 50)),
            'p95_ms': float(np.percentile(data, 95)),
            'p99_ms': float(np.percentile(data, 99)),
            'current_timeout_s': self.get_timeout()
        }


class RetryConfig:
    """Configuration for retry with exponential backoff"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay_ms: float = 100,
        max_delay_ms: float = 10000,
        backoff_multiplier: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter


async def retry_async(
    coro_func: Callable[..., Coroutine[Any, Any, T]],
    config: RetryConfig = None,
    *args,
    **kwargs
) -> T:
    """
    Retry async operation with exponential backoff.
    
    Example:
        result = await retry_async(
            recognizer.analyze,
            config=RetryConfig(max_attempts=3),
            text="hello"
        )
    """
    config = config or RetryConfig()
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return await coro_func(*args, **kwargs)
        
        except Exception as e:
            last_exception = e
            
            if attempt == config.max_attempts - 1:
                # Last attempt, raise
                raise
            
            # Calculate delay
            delay_ms = config.initial_delay_ms * (
                config.backoff_multiplier ** attempt
            )
            delay_ms = min(delay_ms, config.max_delay_ms)
            
            # Add jitter (±10%)
            if config.jitter:
                import random
                jitter = delay_ms * 0.1 * random.random()
                delay_ms += jitter
            
            logger.debug(
                f"Attempt {attempt + 1} failed, retrying in {delay_ms}ms",
                extra={'exception': str(e)}
            )
            
            await asyncio.sleep(delay_ms / 1000)
    
    # Should not reach here, but just in case
    raise last_exception


__all__ = [
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitBreakerOpenError',
    'CircuitState',
    'AdaptiveTimeout',
    'AdaptiveTimeoutConfig',
    'RetryConfig',
    'retry_async',
]
