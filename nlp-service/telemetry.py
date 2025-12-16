"""
OpenTelemetry Integration for Cardio AI Assistant

Provides distributed tracing, metrics, and logging across all services:
- Automatic FastAPI instrumentation
- Custom span decorators
- Correlation ID propagation
- Health metrics collection
- Error tracking

Usage:
    from telemetry import setup_telemetry, trace_span, get_tracer
    
    # Initialize at startup
    setup_telemetry(service_name="nlp-service")
    
    # Use decorators
    @trace_span("process_request")
    async def my_function():
        pass
"""

import os
import time
import functools
import logging
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from contextlib import contextmanager
from datetime import datetime
import uuid

# OpenTelemetry imports
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.trace import Status, StatusCode, SpanKind
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.propagate import set_global_textmap, get_global_textmap
    from opentelemetry.context import Context
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

try:
    from loguru import logger
except ImportError:
    logger = logging.getLogger(__name__)

# Type variable for decorators
F = TypeVar('F', bound=Callable[..., Any])


class TelemetryConfig:
    """Configuration for OpenTelemetry setup."""
    
    def __init__(
        self,
        service_name: str = "cardio-ai-assistant",
        environment: str = "development",
        version: str = "1.0.0",
        otlp_endpoint: Optional[str] = None,
        enable_console_export: bool = True,
        enable_metrics: bool = True,
        sample_rate: float = 1.0,
    ):
        self.service_name = service_name
        self.environment = environment
        self.version = version
        self.otlp_endpoint = otlp_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        self.enable_console_export = enable_console_export
        self.enable_metrics = enable_metrics
        self.sample_rate = sample_rate


# Global state
_tracer: Optional[Any] = None
_meter: Optional[Any] = None
_config: Optional[TelemetryConfig] = None
_initialized: bool = False

# Correlation ID context
_correlation_id_key = "correlation_id"


def generate_correlation_id() -> str:
    """Generate a unique correlation ID."""
    return f"corr_{uuid.uuid4().hex[:16]}"


def setup_telemetry(
    service_name: str = "cardio-ai-assistant",
    config: Optional[TelemetryConfig] = None,
    **kwargs
) -> bool:
    """
    Initialize OpenTelemetry for the service.
    
    Args:
        service_name: Name of the service
        config: Optional TelemetryConfig object
        **kwargs: Additional config options
    
    Returns:
        True if initialization succeeded
    """
    global _tracer, _meter, _config, _initialized
    
    if _initialized:
        logger.warning("Telemetry already initialized")
        return True
    
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry packages not available. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi")
        return False
    
    try:
        _config = config or TelemetryConfig(service_name=service_name, **kwargs)
        
        # Create resource with service information
        resource = Resource.create({
            SERVICE_NAME: _config.service_name,
            "service.version": _config.version,
            "deployment.environment": _config.environment,
        })
        
        # Setup tracing
        tracer_provider = TracerProvider(resource=resource)
        
        # Add OTLP exporter if configured
        if _config.otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=_config.otlp_endpoint)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP exporter configured: {_config.otlp_endpoint}")
        
        # Add console exporter for development
        if _config.enable_console_export:
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
        
        trace.set_tracer_provider(tracer_provider)
        _tracer = trace.get_tracer(_config.service_name, _config.version)
        
        # Setup metrics
        if _config.enable_metrics:
            if _config.otlp_endpoint:
                metric_reader = PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=_config.otlp_endpoint)
                )
            else:
                metric_reader = PeriodicExportingMetricReader(
                    ConsoleMetricExporter()
                )
            
            meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader]
            )
            metrics.set_meter_provider(meter_provider)
            _meter = metrics.get_meter(_config.service_name, _config.version)
        
        # Set up context propagation
        set_global_textmap(TraceContextTextMapPropagator())
        
        _initialized = True
        logger.info(f"OpenTelemetry initialized for service: {_config.service_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        return False


def get_tracer() -> Any:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        if not _initialized:
            setup_telemetry()
        if _tracer is None and OTEL_AVAILABLE:
            _tracer = trace.get_tracer("cardio-ai-assistant")
    return _tracer


def get_meter() -> Any:
    """Get the global meter instance."""
    global _meter
    return _meter


# ============================================================================
# Decorators
# ============================================================================

def trace_span(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to trace a function with a span.
    
    Args:
        name: Span name (defaults to function name)
        kind: Span kind (INTERNAL, SERVER, CLIENT, etc.)
        attributes: Additional span attributes
        record_exception: Whether to record exceptions
    
    Usage:
        @trace_span("process_health_query")
        async def process_query(query: str):
            ...
    """
    def decorator(func: F) -> F:
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            if tracer is None:
                return await func(*args, **kwargs)
            
            with tracer.start_as_current_span(
                span_name,
                kind=kind,
                attributes=attributes or {}
            ) as span:
                try:
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    span.set_attribute("duration_ms", duration * 1000)
                    span.set_status(Status(StatusCode.OK))
                    return result
                    
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            if tracer is None:
                return func(*args, **kwargs)
            
            with tracer.start_as_current_span(
                span_name,
                kind=kind,
                attributes=attributes or {}
            ) as span:
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    span.set_attribute("duration_ms", duration * 1000)
                    span.set_status(Status(StatusCode.OK))
                    return result
                    
                except Exception as e:
                    if record_exception:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


def trace_method(cls_name: Optional[str] = None):
    """
    Class decorator to trace all methods.
    
    Usage:
        @trace_method("HealthAgent")
        class HealthAgent:
            def analyze(self, ...):
                ...
    """
    def decorator(cls):
        name = cls_name or cls.__name__
        
        for attr_name in dir(cls):
            if attr_name.startswith('_'):
                continue
            
            attr = getattr(cls, attr_name)
            if callable(attr):
                setattr(cls, attr_name, trace_span(f"{name}.{attr_name}")(attr))
        
        return cls
    
    return decorator


# ============================================================================
# Context Manager
# ============================================================================

@contextmanager
def trace_context(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: SpanKind = SpanKind.INTERNAL,
):
    """
    Context manager for tracing a block of code.
    
    Usage:
        with trace_context("process_data", {"user_id": user_id}):
            # code to trace
            pass
    """
    tracer = get_tracer()
    if tracer is None:
        yield None
        return
    
    with tracer.start_as_current_span(
        name,
        kind=kind,
        attributes=attributes or {}
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise


# ============================================================================
# Span Utilities
# ============================================================================

def get_current_span() -> Optional[Any]:
    """Get the current active span."""
    if not OTEL_AVAILABLE:
        return None
    return trace.get_current_span()


def add_span_attribute(key: str, value: Any) -> None:
    """Add an attribute to the current span."""
    span = get_current_span()
    if span:
        span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    """Add an event to the current span."""
    span = get_current_span()
    if span:
        span.add_event(name, attributes or {})


def set_span_error(error: Exception, message: Optional[str] = None) -> None:
    """Set error status on the current span."""
    span = get_current_span()
    if span:
        span.record_exception(error)
        span.set_status(Status(StatusCode.ERROR, message or str(error)))


# ============================================================================
# Correlation ID Management
# ============================================================================

class CorrelationContext:
    """Manage correlation IDs for request tracing."""
    
    _context: Dict[str, str] = {}
    
    @classmethod
    def set(cls, correlation_id: str) -> None:
        """Set correlation ID for current context."""
        cls._context[_correlation_id_key] = correlation_id
        add_span_attribute("correlation_id", correlation_id)
    
    @classmethod
    def get(cls) -> Optional[str]:
        """Get correlation ID from current context."""
        return cls._context.get(_correlation_id_key)
    
    @classmethod
    def ensure(cls) -> str:
        """Get or create correlation ID."""
        cid = cls.get()
        if not cid:
            cid = generate_correlation_id()
            cls.set(cid)
        return cid
    
    @classmethod
    def clear(cls) -> None:
        """Clear correlation ID."""
        cls._context.pop(_correlation_id_key, None)


# ============================================================================
# Metrics
# ============================================================================

class MetricsRegistry:
    """Registry for application metrics."""
    
    _counters: Dict[str, Any] = {}
    _histograms: Dict[str, Any] = {}
    _gauges: Dict[str, Any] = {}
    
    @classmethod
    def counter(cls, name: str, description: str = "", unit: str = "") -> Any:
        """Get or create a counter metric."""
        if name not in cls._counters:
            meter = get_meter()
            if meter:
                cls._counters[name] = meter.create_counter(
                    name, description=description, unit=unit
                )
        return cls._counters.get(name)
    
    @classmethod
    def histogram(cls, name: str, description: str = "", unit: str = "") -> Any:
        """Get or create a histogram metric."""
        if name not in cls._histograms:
            meter = get_meter()
            if meter:
                cls._histograms[name] = meter.create_histogram(
                    name, description=description, unit=unit
                )
        return cls._histograms.get(name)
    
    @classmethod
    def gauge(cls, name: str, callback: Callable, description: str = "", unit: str = "") -> Any:
        """Get or create an observable gauge metric."""
        if name not in cls._gauges:
            meter = get_meter()
            if meter:
                cls._gauges[name] = meter.create_observable_gauge(
                    name, callbacks=[callback], description=description, unit=unit
                )
        return cls._gauges.get(name)


# Predefined metrics for health assistant
def get_request_counter():
    """Counter for API requests."""
    return MetricsRegistry.counter(
        "nlp_requests_total",
        "Total number of NLP requests",
        "requests"
    )


def get_response_histogram():
    """Histogram for response times."""
    return MetricsRegistry.histogram(
        "nlp_response_duration_seconds",
        "Response time in seconds",
        "s"
    )


def get_error_counter():
    """Counter for errors."""
    return MetricsRegistry.counter(
        "nlp_errors_total",
        "Total number of errors",
        "errors"
    )


def record_request(endpoint: str, method: str = "POST") -> None:
    """Record an API request."""
    counter = get_request_counter()
    if counter:
        counter.add(1, {"endpoint": endpoint, "method": method})


def record_response_time(endpoint: str, duration: float) -> None:
    """Record response time."""
    histogram = get_response_histogram()
    if histogram:
        histogram.record(duration, {"endpoint": endpoint})


def record_error(endpoint: str, error_type: str) -> None:
    """Record an error."""
    counter = get_error_counter()
    if counter:
        counter.add(1, {"endpoint": endpoint, "error_type": error_type})


# ============================================================================
# FastAPI Middleware
# ============================================================================

def create_telemetry_middleware():
    """Create FastAPI middleware for telemetry."""
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class TelemetryMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Extract or generate correlation ID
            correlation_id = request.headers.get("X-Correlation-ID")
            if not correlation_id:
                correlation_id = generate_correlation_id()
            
            CorrelationContext.set(correlation_id)
            
            # Add correlation ID to span
            add_span_attribute("http.correlation_id", correlation_id)
            add_span_attribute("http.method", request.method)
            add_span_attribute("http.url", str(request.url))
            
            start_time = time.time()
            
            try:
                response = await call_next(request)
                duration = time.time() - start_time
                
                # Record metrics
                record_request(request.url.path, request.method)
                record_response_time(request.url.path, duration)
                
                # Add response info
                add_span_attribute("http.status_code", response.status_code)
                
                # Add correlation ID to response
                response.headers["X-Correlation-ID"] = correlation_id
                
                return response
                
            except Exception as e:
                duration = time.time() - start_time
                record_error(request.url.path, type(e).__name__)
                set_span_error(e)
                raise
            finally:
                CorrelationContext.clear()
    
    return TelemetryMiddleware


def instrument_fastapi(app) -> None:
    """Instrument FastAPI app with OpenTelemetry."""
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available for FastAPI instrumentation")
        return
    
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")


def instrument_requests() -> None:
    """Instrument requests library."""
    if not OTEL_AVAILABLE:
        return
    
    try:
        RequestsInstrumentor().instrument()
        logger.info("Requests library instrumented")
    except Exception as e:
        logger.error(f"Failed to instrument requests: {e}")


def instrument_sqlalchemy(engine) -> None:
    """Instrument SQLAlchemy engine."""
    if not OTEL_AVAILABLE:
        return
    
    try:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy instrumented")
    except Exception as e:
        logger.error(f"Failed to instrument SQLAlchemy: {e}")


# ============================================================================
# Health Specific Spans
# ============================================================================

@contextmanager
def trace_llm_call(
    model: str,
    prompt_tokens: int = 0,
    provider: str = "gemini"
):
    """Trace an LLM API call."""
    with trace_context(
        "llm_call",
        attributes={
            "llm.model": model,
            "llm.provider": provider,
            "llm.prompt_tokens": prompt_tokens,
        },
        kind=SpanKind.CLIENT
    ) as span:
        start_time = time.time()
        try:
            yield span
            duration = time.time() - start_time
            if span:
                span.set_attribute("llm.duration_ms", duration * 1000)
        except Exception:
            raise


@contextmanager  
def trace_rag_retrieval(
    query: str,
    collection: str = "default",
    top_k: int = 5
):
    """Trace a RAG retrieval operation."""
    with trace_context(
        "rag_retrieval",
        attributes={
            "rag.collection": collection,
            "rag.top_k": top_k,
            "rag.query_length": len(query),
        }
    ) as span:
        yield span


@contextmanager
def trace_agent_execution(
    agent_name: str,
    action: str
):
    """Trace an agent execution."""
    with trace_context(
        f"agent.{agent_name}",
        attributes={
            "agent.name": agent_name,
            "agent.action": action,
        }
    ) as span:
        yield span


# Need asyncio for decorator
import asyncio
