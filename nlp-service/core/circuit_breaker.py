"""
Production-grade Circuit Breaker Pattern Implementation

Prevents cascading failures by protecting calls to external services (APIs, databases).

Features:
- State machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
- Automatic recovery detection
- Fallback strategies
- Comprehensive metrics and monitoring
- Configurable thresholds and timeouts

Failure Modes Handled:
- Network timeouts
- Service unavailability
- Connection pool exhaustion
- Cascading failures in microservices
"""

import logging
from datetime import datetime, timedelta
from typing import Callable, TypeVar, Optional, Tuple, List
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states with state machine semantics."""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Rejecting calls
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open - service unavailable."""


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # When circuit was OPEN
    state_changes: List[Tuple[datetime, CircuitState]] = None

    def __post_init__(self):
        if self.state_changes is None:
            self.state_changes = []

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100

    @property
    def failure_rate(self) -> float:
        """Failure rate as percentage."""
        return 100 - self.success_rate


class CircuitBreaker:
    """
    Production-grade Circuit Breaker Pattern Implementation

    State Transitions:
    CLOSED -> (failures >= threshold) -> OPEN
    OPEN -> (recovery_timeout elapsed) -> HALF_OPEN
    HALF_OPEN -> (success) -> CLOSED
    HALF_OPEN -> (failure) -> OPEN

    Key Concepts:
    - Failure Threshold: Number of failures before opening (fast-fail)
    - Recovery Timeout: Time to wait before testing recovery
    - Expected Exception: Only these exceptions trigger failures (configurable)

    Failure Modes Prevented:
    1. Cascading Failures: OPEN state prevents calls to failing service
    2. Connection Pool Exhaustion: Fast-fail prevents resource waste
    3. Thundering Herd: Rejected calls let system recover
    4. Wasted Latency: Don't wait for doomed requests

    Complexity:
    - call(): O(1) state check + function execution
    - state transitions: O(1) timestamp comparison
    """

    def __init__(
        self,
        name: str = "CircuitBreaker",
        failure_threshold: int = 3,
        recovery_timeout: int = 30,
        expected_exception: type = Exception,
        fallback_func: Optional[Callable] = None,
    ):
        """
        Initialize Circuit Breaker with resilience parameters.

        Args:
            name: Name for logging and identification
            failure_threshold: Failures before opening (3-5 recommended)
            recovery_timeout: Seconds before HALF_OPEN state (30-60 recommended)
            expected_exception: Exception type that triggers failures
            fallback_func: Optional fallback callable if circuit is open

        Example:
            def fallback_response(*args, **kwargs):
                return {"status": "service_unavailable", "cached": True}

            breaker = CircuitBreaker(
                name="ollama_service",
                failure_threshold=3,
                recovery_timeout=30,
                fallback_func=fallback_response
            )
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.fallback_func = fallback_func

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics()

        # Record initial state
        self.metrics.state_changes.append((datetime.now(), self.state))

        logger.info(
            f"CircuitBreaker '{name}' initialized: "
            f"threshold={failure_threshold}, timeout={recovery_timeout}s, "
            f"exception={expected_exception.__name__}, "
            f"fallback={'enabled' if fallback_func else 'disabled'}"
        )

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker with state protection.

        Flow:
        1. Check if circuit should recover (OPEN -> HALF_OPEN)
        2. If OPEN, either reject or use fallback
        3. Execute function
        4. Update metrics on success/failure
        5. Update state based on results

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result or fallback result

        Raises:
            CircuitBreakerOpen: If circuit open and no fallback
            expected_exception: If function raises expected exception

        Example:
            breaker = CircuitBreaker(name="api_call")
            try:
                result = breaker.call(requests.get, url, timeout=5)
            except CircuitBreakerOpen:
                logger.warning("API service is down")
                result = get_cached_response()
        """
        # Check if should attempt recovery
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(
                    f"CircuitBreaker '{self.name}' entering HALF_OPEN (testing recovery)"
                )
            else:
                # Circuit still open - use fallback or reject
                self.metrics.rejected_calls += 1
                if self.fallback_func:
                    logger.warning(
                        f"CircuitBreaker '{self.name}' OPEN - using fallback"
                    )
                    return self.fallback_func(*args, **kwargs)
                else:
                    logger.error(f"CircuitBreaker '{self.name}' OPEN - rejecting call")
                    raise CircuitBreakerOpen(
                        f"CircuitBreaker '{self.name}' is OPEN. "
                        f"Service unavailable. Recovering in "
                        f"{self._time_until_reset().total_seconds():.0f}s"
                    )

        # Execute function
        self.metrics.total_calls += 1
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            logger.warning(
                f"CircuitBreaker '{self.name}' caught exception "
                f"(failure {self.failure_count}/{self.failure_threshold}): {type(e).__name__}"
            )
            raise e

    async def call_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute async function through circuit breaker.

        Same semantics as call() but for async functions.

        Example:
            breaker = CircuitBreaker(name="async_api")
            result = await breaker.call_async(async_http_get, url)
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"CircuitBreaker '{self.name}' entering HALF_OPEN (async)")
            else:
                self.metrics.rejected_calls += 1
                if self.fallback_func:
                    logger.warning(
                        f"CircuitBreaker '{self.name}' OPEN - using fallback (async)"
                    )
                    return self.fallback_func(*args, **kwargs)
                else:
                    raise CircuitBreakerOpen(
                        f"CircuitBreaker '{self.name}' is OPEN (async)"
                    )

        self.metrics.total_calls += 1
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        """Handle successful call - may close circuit if half-open."""
        self.metrics.successful_calls += 1

        if self.state == CircuitState.HALF_OPEN:
            # Recovery successful!
            self._reset()
            logger.info(f"CircuitBreaker '{self.name}' RECOVERED - returning to CLOSED")
        elif self.state == CircuitState.CLOSED:
            # Reset failure counter on success (sliding window behavior)
            if self.failure_count > 0:
                self.failure_count = 0
                logger.debug(f"CircuitBreaker '{self.name}' failure count reset")

    def _on_failure(self) -> None:
        """Handle failed call - may open circuit if threshold exceeded."""
        self.metrics.failed_calls += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        logger.warning(
            f"CircuitBreaker '{self.name}' failure #{self.failure_count}/{self.failure_threshold}"
        )

        # Check if threshold exceeded
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.metrics.state_changes.append((datetime.now(), self.state))
            logger.error(
                f"CircuitBreaker '{self.name}' TRIPPED - entering OPEN state. "
                f"Recovery attempt in {self.recovery_timeout}s"
            )

    def _should_attempt_reset(self) -> bool:
        """Check if recovery timeout has elapsed."""
        if self.last_failure_time is None:
            return True

        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure >= timedelta(seconds=self.recovery_timeout)

    def _time_until_reset(self) -> timedelta:
        """Calculate time remaining until recovery attempt."""
        if self.last_failure_time is None:
            return timedelta(seconds=0)

        time_since_failure = datetime.now() - self.last_failure_time
        recovery_time = timedelta(seconds=self.recovery_timeout)

        if time_since_failure >= recovery_time:
            return timedelta(seconds=0)

        return recovery_time - time_since_failure

    def _reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.metrics.state_changes.append((datetime.now(), self.state))

    def reset(self) -> None:
        """Manually reset circuit breaker (useful for testing/operations)."""
        old_state = self.state
        self._reset()
        logger.info(
            f"CircuitBreaker '{self.name}' manually reset ({old_state} -> CLOSED)"
        )

    # ========================================================================
    # STATUS & MONITORING
    # ========================================================================

    @property
    def is_open(self) -> bool:
        """Check if circuit is OPEN (rejecting calls)."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is CLOSED (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is HALF_OPEN (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    def get_status(self) -> dict:
        """Get comprehensive circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "recovery_timeout_seconds": self.recovery_timeout,
            "time_until_recovery_seconds": self._time_until_reset().total_seconds(),
            "fallback_available": self.fallback_func is not None,
        }

    def get_metrics(self) -> dict:
        """Get detailed metrics for monitoring and debugging."""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.metrics.total_calls,
            "successful_calls": self.metrics.successful_calls,
            "failed_calls": self.metrics.failed_calls,
            "rejected_calls": self.metrics.rejected_calls,
            "success_rate_percent": f"{self.metrics.success_rate:.1f}%",
            "failure_rate_percent": f"{self.metrics.failure_rate:.1f}%",
            "state_changes": len(self.metrics.state_changes),
        }
