"""
Timeout middleware and decorators for NLP service.

Provides decorators and middleware to handle request timeouts gracefully.
"""

import asyncio
import logging
from functools import wraps
from typing import Optional, Callable, Any
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout"""
    pass


def with_timeout(
    seconds: float = 10.0,
    fallback: Optional[Any] = None,
    log_level: str = "warning"
) -> Callable:
    """
    Decorator to add timeout to async functions.
    
    Args:
        seconds: Timeout duration in seconds
        fallback: Value to return on timeout (if None, raises TimeoutError)
        log_level: Logging level for timeout events
    
    Returns:
        Decorated async function with timeout protection
    
    Usage:
        @with_timeout(seconds=10)
        async def slow_operation():
            await asyncio.sleep(30)  # Will timeout after 10s
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                async with asyncio.timeout(seconds):
                    return await func(*args, **kwargs)
            except asyncio.TimeoutError:
                log_fn = getattr(logger, log_level)
                log_fn(
                    f"Timeout in {func.__name__} after {seconds}s "
                    f"(args: {len(args)}, kwargs: {len(kwargs)})"
                )
                
                if fallback is not None:
                    return fallback
                
                raise TimeoutError(
                    f"Operation {func.__name__} exceeded {seconds}s timeout"
                )
        
        return wrapper
    
    return decorator


def with_timeout_context(
    seconds: float = 10.0,
    error_callback: Optional[Callable] = None
):
    """
    Context manager for timeout protection.
    
    Usage:
        async with with_timeout_context(5.0):
            result = await long_operation()
    """
    class TimeoutContextManager:
        def __init__(self, timeout_seconds: float, callback: Optional[Callable]):
            self.timeout_seconds = timeout_seconds
            self.error_callback = callback
        
        async def __aenter__(self):
            self._timeout_handle = asyncio.timeout(self.timeout_seconds)
            return await self._timeout_handle.__aenter__()
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            try:
                return await self._timeout_handle.__aexit__(exc_type, exc_val, exc_tb)
            except asyncio.TimeoutError:
                logger.warning(f"Operation timeout after {self.timeout_seconds}s")
                
                if self.error_callback:
                    await self.error_callback() if asyncio.iscoroutinefunction(self.error_callback) else self.error_callback()
                
                raise
    
    return TimeoutContextManager(seconds, error_callback)


async def timeout_wrapper(
    coro,
    timeout_seconds: float = 10.0,
    on_timeout: Optional[Callable] = None,
    default_value: Optional[Any] = None
) -> Any:
    """
    Wrap a coroutine with timeout protection.
    
    Args:
        coro: Coroutine to execute
        timeout_seconds: Timeout duration
        on_timeout: Optional callback when timeout occurs
        default_value: Value to return on timeout
    
    Returns:
        Result of coroutine or default_value on timeout
    
    Usage:
        result = await timeout_wrapper(
            slow_coro(),
            timeout_seconds=5,
            default_value={"status": "timeout"}
        )
    """
    try:
        async with asyncio.timeout(timeout_seconds):
            return await coro
    except asyncio.TimeoutError:
        logger.warning(f"Coroutine timeout after {timeout_seconds}s")
        
        if on_timeout:
            if asyncio.iscoroutinefunction(on_timeout):
                await on_timeout()
            else:
                on_timeout()
        
        return default_value


class TimeoutMiddleware:
    """
    FastAPI middleware for request-level timeout handling.
    
    Adds timeout protection to all requests and provides detailed
    timeout error responses.
    """
    
    def __init__(
        self,
        app,
        timeout_seconds: float = 30.0,
        exclude_paths: Optional[list] = None
    ):
        """
        Initialize timeout middleware.
        
        Args:
            app: FastAPI application
            timeout_seconds: Global timeout for all requests
            exclude_paths: List of paths to exclude from timeout
        """
        self.app = app
        self.timeout_seconds = timeout_seconds
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json"
        ]
    
    async def __call__(self, request: Request, call_next):
        """
        Process request with timeout.
        
        Returns error response if request exceeds timeout.
        """
        # Skip timeout for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await call_next(request)
        
        except asyncio.TimeoutError:
            logger.error(
                f"Request timeout: {request.method} {request.url.path} "
                f"after {self.timeout_seconds}s"
            )
            
            return JSONResponse(
                status_code=504,
                content={
                    "error_code": "SERVICE_TIMEOUT",
                    "error_message": f"Request timeout after {self.timeout_seconds}s",
                    "timestamp": str(__import__('datetime').datetime.utcnow())
                }
            )
        
        except Exception as e:
            logger.exception(f"Unexpected error in timeout middleware: {e}")
            raise


async def parallel_with_timeout(
    *coroutines,
    timeout_seconds: float = 10.0,
    return_exceptions: bool = False
) -> list:
    """
    Execute multiple coroutines in parallel with timeout.
    
    Args:
        *coroutines: Variable number of coroutines to execute
        timeout_seconds: Overall timeout for all operations
        return_exceptions: If True, exceptions are returned instead of raised
    
    Returns:
        List of results in same order as coroutines
    
    Raises:
        asyncio.TimeoutError: If timeout exceeded
    
    Usage:
        results = await parallel_with_timeout(
            intent_coro(),
            sentiment_coro(),
            entities_coro(),
            timeout_seconds=10.0
        )
    """
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*coroutines, return_exceptions=return_exceptions),
            timeout=timeout_seconds
        )
        return results
    except asyncio.TimeoutError:
        logger.error(f"Parallel execution timeout after {timeout_seconds}s")
        raise


class TimeoutStats:
    """Track timeout statistics"""
    
    def __init__(self):
        self.total_timeouts = 0
        self.total_requests = 0
        self.timeout_by_endpoint = {}
    
    def record_timeout(self, endpoint: str):
        """Record a timeout for an endpoint"""
        self.total_timeouts += 1
        self.timeout_by_endpoint[endpoint] = self.timeout_by_endpoint.get(endpoint, 0) + 1
    
    def record_request(self):
        """Record a processed request"""
        self.total_requests += 1
    
    def get_timeout_rate(self) -> float:
        """Get overall timeout rate"""
        if self.total_requests == 0:
            return 0.0
        return self.total_timeouts / self.total_requests
    
    def get_stats(self) -> dict:
        """Get detailed statistics"""
        return {
            'total_timeouts': self.total_timeouts,
            'total_requests': self.total_requests,
            'timeout_rate': self.get_timeout_rate(),
            'timeout_by_endpoint': self.timeout_by_endpoint
        }


# Global timeout stats instance
timeout_stats = TimeoutStats()


__all__ = [
    'TimeoutError',
    'with_timeout',
    'with_timeout_context',
    'timeout_wrapper',
    'TimeoutMiddleware',
    'parallel_with_timeout',
    'timeout_stats',
    'TimeoutStats',
]
