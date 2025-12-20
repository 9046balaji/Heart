"""
Structured concurrency patterns for high-performance async operations.

Implements best practices from asyncio, trio, curio patterns and healthcare
workload requirements (predictable performance, bounded concurrency).

Features:
- AsyncBatcher: Control concurrency to prevent resource exhaustion
- AsyncTimeout: Ensure operations complete within time bounds
- AsyncResourcePool: Manage pool of async resources
- Metrics: Track active/completed tasks
"""

import asyncio
import logging
from typing import Callable, TypeVar, List, Any, Optional, Coroutine, Generic
from contextlib import asynccontextmanager
from functools import wraps
import time
from core.error_handling import (
    TimeoutError,
    ProcessingError,
)  # PHASE 2: Import exception hierarchy

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncBatcher:
    """
    Batch multiple async operations with controlled concurrency.

    Prevents:
    - Connection pool exhaustion
    - Database query storms
    - API rate limit violations
    - Event loop overload

    Complexity:
    - Enqueue: O(1)
    - Acquire: O(1) semaphore wait
    - Batch: O(n) for n tasks

    Example:
        batcher = AsyncBatcher(max_concurrent=10)
        results = await batcher.batch([
            process_health_data(data1),
            process_health_data(data2),
            ...
        ])
    """

    def __init__(self, max_concurrent: int = 10, timeout: Optional[int] = None):
        """Initialize AsyncBatcher with concurrency limit.

        Args:
            max_concurrent: Maximum concurrent tasks
            timeout: Global timeout for batch operations (seconds)
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = timeout

        # Metrics
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_duration_ms = 0

    async def _run_with_limit(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run coroutine with concurrency limiting."""
        async with self.semaphore:
            self.active_tasks += 1
            start_time = time.time()

            try:
                result = await coro
                self.completed_tasks += 1
                return result
            except Exception as e:
                self.failed_tasks += 1
                logger.error(f"Batched task failed: {e}", exc_info=True)
                raise
            finally:
                self.active_tasks -= 1
                duration_ms = (time.time() - start_time) * 1000
                self.total_duration_ms += duration_ms

    async def batch(
        self,
        coros: List[Coroutine[Any, Any, T]],
        timeout: Optional[int] = None,
        return_exceptions: bool = False,
    ) -> List[T]:
        """Execute multiple coroutines with concurrency limit.

        Args:
            coros: List of coroutines to execute
            timeout: Override default timeout (seconds)
            return_exceptions: If True, return exceptions as results

        Returns:
            List of results (may contain exceptions if return_exceptions=True)

        Raises:
            asyncio.TimeoutError: If batch exceeds timeout
        """
        timeout = timeout or self.timeout

        # Create tasks with semaphore limits
        tasks = [asyncio.create_task(self._run_with_limit(coro)) for coro in coros]

        try:
            if timeout:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=return_exceptions),
                    timeout=timeout,
                )
            else:
                results = await asyncio.gather(
                    *tasks, return_exceptions=return_exceptions
                )

            return results
        except asyncio.TimeoutError:
            logger.error(
                f"Batch operation timed out after {timeout}s "
                f"({len(tasks)} tasks, {self.active_tasks} still active)"
            )
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            raise

    def get_stats(self) -> dict:
        """Get batcher statistics."""
        return {
            "max_concurrent": self.max_concurrent,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "avg_duration_ms": (
                self.total_duration_ms / self.completed_tasks
                if self.completed_tasks > 0
                else 0
            ),
        }


class AsyncTimeout:
    """
    Decorator for adding timeouts to async functions.

    Ensures operations complete within time bounds (critical for healthcare).

    Example:
        @AsyncTimeout(timeout_seconds=30)
        async def slow_operation():
            ...

        # Or dynamic timeout:
        @AsyncTimeout()
        async def operation():
            ...

        result = await operation(_timeout=15)  # Override default
    """

    def __init__(self, timeout_seconds: Optional[int] = 30):
        self.default_timeout = timeout_seconds

    def __call__(self, func: Callable[..., Coroutine[Any, Any, T]]) -> Callable:
        @wraps(func)
        async def wrapper(*args, _timeout: Optional[int] = None, **kwargs) -> T:
            timeout = _timeout or self.default_timeout

            try:
                if timeout:
                    return await asyncio.wait_for(
                        func(*args, **kwargs), timeout=timeout
                    )
                else:
                    return await func(*args, **kwargs)
            except asyncio.TimeoutError:
                logger.error(
                    f"Async operation '{func.__name__}' timed out " f"after {timeout}s"
                )
                raise

        return wrapper


class AsyncResourcePool(Generic[T]):
    """
    Manage pool of async resources (connections, clients, etc.)

    Ensures:
    - Proper lifecycle management
    - Prevention of resource exhaustion
    - Fair distribution of resources
    - Timeout on resource acquisition

    Example:
        async def create_connection():
            return await aiohttp.ClientSession()

        pool = AsyncResourcePool(create_connection, max_size=10)
        await pool.initialize()

        async with pool.acquire() as client:
            result = await client.get("http://...")
    """

    def __init__(
        self, factory: Callable[[], Coroutine[Any, Any, T]], max_size: int = 10
    ):
        """Initialize resource pool.

        Args:
            factory: Async callable that creates resources
            max_size: Maximum resources in pool
        """
        self.factory = factory
        self.max_size = max_size
        self.available: asyncio.Queue = asyncio.Queue(max_size)
        self.all_resources: List[T] = []
        self.initialized = False

    async def initialize(self):
        """Pre-create all resources in the pool.

        Must be called before using pool.acquire().
        """
        if self.initialized:
            return

        for _ in range(self.max_size):
            try:
                resource = await self.factory()
                self.all_resources.append(resource)
                await self.available.put(resource)
            except Exception as e:
                logger.error(f"Failed to create pool resource: {e}")
                # Clean up partially initialized pool
                await self.close()
                raise

        self.initialized = True
        logger.info(f"Resource pool initialized with {self.max_size} resources")

    @asynccontextmanager
    async def acquire(self, timeout: int = 30):
        """Acquire a resource from the pool.

        Usage:
            async with pool.acquire() as resource:
                await resource.operation()

        Args:
            timeout: Timeout for acquiring resource (seconds)

        Yields:
            Resource from pool

        Raises:
            asyncio.TimeoutError: If resource acquisition times out
        """
        if not self.initialized:
            raise RuntimeError(
                "Pool not initialized. Call await pool.initialize() first."
            )

        try:
            resource = await asyncio.wait_for(self.available.get(), timeout=timeout)
            yield resource
        except asyncio.TimeoutError:
            logger.error(f"Resource acquisition timed out after {timeout}s")
            raise
        finally:
            await self.available.put(resource)

    async def close(self):
        """Clean up all resources gracefully."""
        logger.info(f"Closing {len(self.all_resources)} pool resources")

        for resource in self.all_resources:
            try:
                if hasattr(resource, "close"):
                    if asyncio.iscoroutinefunction(resource.close):
                        await resource.close()
                    else:
                        resource.close()
                elif hasattr(resource, "aclose"):
                    await resource.aclose()
            except Exception as e:
                logger.warning(f"Error closing pool resource: {e}")

        self.all_resources.clear()
        self.initialized = False


async def run_sync_in_executor(
    func: Callable[..., T], *args, timeout: Optional[int] = None, **kwargs
) -> T:
    """
    Run sync function in thread pool executor without blocking event loop.

    Critical for CPU-intensive or blocking operations:
    - Database queries
    - File I/O
    - Encryption/decryption
    - ML inference

    Complexity:
    - Enqueue: O(1)
    - Execution: O(f) where f is function complexity
    - Thread pool limit prevents resource exhaustion

    Example:
        # Don't do this (blocks event loop):
        result = expensive_sync_operation()

        # Do this instead (non-blocking):
        result = await run_sync_in_executor(expensive_sync_operation)

    Args:
        func: Sync function to run
        *args: Positional arguments for function
        timeout: Timeout for operation (seconds)
        **kwargs: Keyword arguments for function

    Returns:
        Function result

    Raises:
        asyncio.TimeoutError: If operation exceeds timeout
    """
    loop = asyncio.get_event_loop()

    try:
        coro = loop.run_in_executor(None, func, *args)

        if timeout:
            result = await asyncio.wait_for(coro, timeout=timeout)
        else:
            result = await coro

        return result
    except asyncio.TimeoutError:
        logger.error(f"Sync operation '{func.__name__}' timed out after {timeout}s")
        raise
    except Exception as e:
        logger.error(f"Sync operation '{func.__name__}' failed: {e}", exc_info=True)
        raise


async def collect_with_timeout(
    coros: List[Coroutine[Any, Any, T]],
    timeout: int = 30,
    return_exceptions: bool = True,
) -> List[T]:
    """
    Gather multiple coroutines with timeout and error handling.

    Useful for collecting results from multiple async operations
    where individual timeouts aren't sufficient.

    Args:
        coros: List of coroutines
        timeout: Total timeout in seconds
        return_exceptions: If True, return exceptions as results

    Returns:
        List of results (may contain exceptions if return_exceptions=True)

    Raises:
        asyncio.TimeoutError: If total time exceeds timeout

    Example:
        results = await collect_with_timeout([
            fetch_vital_signs(patient_id),
            fetch_medications(patient_id),
            assess_risk(patient_id),
        ], timeout=30)
    """
    tasks = [asyncio.create_task(coro) for coro in coros]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=return_exceptions), timeout=timeout
        )
        return results
    except asyncio.TimeoutError:
        logger.error(
            f"Collection timed out after {timeout}s "
            f"({len(tasks)} tasks, {sum(1 for t in tasks if not t.done())} still active)"
        )
        # Cancel remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        raise


async def gather_with_retry(
    coros: List[Coroutine[Any, Any, T]],
    max_retries: int = 3,
    timeout: Optional[int] = None,
) -> List[T]:
    """
    Gather coroutines with automatic retry on failure.

    Useful for operations that may fail transiently:
    - Network requests
    - Database operations
    - External API calls

    Args:
        coros: List of coroutines
        max_retries: Maximum retry attempts per coroutine
        timeout: Optional timeout per retry (seconds)

    Returns:
        List of results

    Raises:
        Exception: If all retries exhausted for any operation
    """
    results = []

    for coro in coros:
        for attempt in range(max_retries):
            try:
                if timeout:
                    result = await asyncio.wait_for(coro, timeout=timeout)
                else:
                    result = await coro
                results.append(result)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Operation failed after {max_retries} attempts: {e}")
                    raise
                wait_time = 2**attempt  # Exponential backoff
                logger.warning(
                    f"Operation failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)

    return results


# ============================================================================
# ASYNC CONTEXT MANAGERS FOR COMMON PATTERNS
# ============================================================================


@asynccontextmanager
async def async_timer(operation_name: str):
    """Context manager for timing async operations.

    Usage:
        async with async_timer("database_query"):
            result = await db.query(...)
    """
    start = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start) * 1000
        logger.debug(f"Operation '{operation_name}' completed in {duration_ms:.2f}ms")


# ============================================================================
# EXAMPLE: PRODUCTION HEALTH WORKFLOW
# ============================================================================


async def example_health_check_workflow(patient_id: str):
    """
    Example: Concurrent health check workflow with proper async patterns.

    Shows:
    - AsyncTimeout for individual operations
    - AsyncBatcher for controlled concurrency
    - run_sync_in_executor for blocking operations
    - collect_with_timeout for aggregation
    """

    # Operation 1: Run CPU-bound operation in thread pool (non-blocking)
    def get_patient_vitals_sync(p_id):
        # Simulate sync database query
        return {"heart_rate": 72, "bp": "120/80"}

    vital_signs = await run_sync_in_executor(
        get_patient_vitals_sync, patient_id, timeout=10
    )

    # Operation 2: Batch multiple async operations with concurrency limit
    async def check_medication_interactions(medications):
        await asyncio.sleep(0.5)  # Simulate async API call
        return {"safe": True}

    async def assess_risk_score(vitals):
        await asyncio.sleep(0.3)  # Simulate ML inference
        return {"risk_score": 0.25}

    async def generate_recommendations(vitals):
        await asyncio.sleep(0.4)  # Simulate AI generation
        return {"recommendations": ["increase_water_intake"]}

    batcher = AsyncBatcher(max_concurrent=5)
    results = await batcher.batch(
        [
            check_medication_interactions(vital_signs.get("medications", [])),
            assess_risk_score(vital_signs),
            generate_recommendations(vital_signs),
        ],
        timeout=20,
    )

    return {
        "vital_signs": vital_signs,
        "assessment": results,
    }
