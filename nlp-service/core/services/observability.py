"""
Comprehensive Observability Stack

Implements:
- Structured logging with correlation IDs
- Performance metrics (Prometheus-compatible)
- Distributed tracing (OpenTelemetry-ready)
- Health checks
- SLO monitoring

Pattern: Telemetry, Instrumentation, Observability
Reference: The Three Pillars of Observability (O'Reilly)
"""

import logging
import time
import uuid
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from contextlib import asynccontextmanager
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Standard log levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class CorrelationID:
    """Unique identifier for request correlation"""

    request_id: str
    parent_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    @staticmethod
    def generate() -> "CorrelationID":
        """Generate new correlation ID"""
        return CorrelationID(
            request_id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
        )

    def to_dict(self) -> dict:
        """Export as dictionary"""
        return asdict(self)


@dataclass
class StructuredLog:
    """Structured log entry"""

    timestamp: datetime
    level: LogLevel
    message: str
    correlation_id: CorrelationID
    component: str
    context: Dict[str, Any]
    error: Optional[str] = None

    def to_json(self) -> str:
        """Export as JSON"""
        return json.dumps(
            {
                "timestamp": self.timestamp.isoformat(),
                "level": self.level.value,
                "message": self.message,
                "correlation_id": self.correlation_id.request_id,
                "trace_id": self.correlation_id.trace_id,
                "component": self.component,
                "context": self.context,
                "error": self.error,
            }
        )


class StructuredLogger:
    """Logger with structured output and correlation IDs"""

    def __init__(self, component_name: str):
        self.component_name = component_name
        self.correlation_context = None

    def set_correlation(self, correlation_id: CorrelationID) -> None:
        """Set correlation ID context"""
        self.correlation_context = correlation_id

    def get_correlation(self) -> CorrelationID:
        """Get current correlation ID"""
        if self.correlation_context is None:
            self.correlation_context = CorrelationID.generate()
        return self.correlation_context

    def log(
        self,
        level: LogLevel,
        message: str,
        context: Dict[str, Any] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """
        Log with structure.

        Args:
            level: Log level
            message: Log message
            context: Contextual data
            error: Exception if applicable
        """
        context = context or {}
        correlation = self.get_correlation()

        log_entry = StructuredLog(
            timestamp=datetime.now(),
            level=level,
            message=message,
            correlation_id=correlation,
            component=self.component_name,
            context=context,
            error=str(error) if error else None,
        )

        # Log using standard logger with context
        log_method = getattr(logger, level.value.lower())
        log_method(
            f"{message} [correlation_id={correlation.request_id}]",
            extra={
                "structured": log_entry.to_json(),
                "correlation_id": correlation.request_id,
                "context": context,
            },
        )

    def info(self, message: str, context: Dict[str, Any] = None) -> None:
        """Log info level"""
        self.log(LogLevel.INFO, message, context)

    def warning(self, message: str, context: Dict[str, Any] = None) -> None:
        """Log warning level"""
        self.log(LogLevel.WARNING, message, context)

    def error(
        self, message: str, context: Dict[str, Any] = None, error: Exception = None
    ) -> None:
        """Log error level"""
        self.log(LogLevel.ERROR, message, context, error)

    def debug(self, message: str, context: Dict[str, Any] = None) -> None:
        """Log debug level"""
        self.log(LogLevel.DEBUG, message, context)


@dataclass
class MetricPoint:
    """Single metric measurement"""

    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str]
    unit: str = "1"


class MetricsCollector:
    """
    Collect and store metrics.

    Tracks:
    - Latency percentiles (p50, p95, p99)
    - Request rates
    - Error rates
    - Resource usage
    """

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))

    def record(
        self, name: str, value: float, labels: Dict[str, str] = None, unit: str = "1"
    ) -> None:
        """
        Record metric value.

        Args:
            name: Metric name (e.g., 'request_duration_ms')
            value: Metric value
            labels: Labels for aggregation
            unit: Unit of measurement
        """
        key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=datetime.now(),
            labels=labels or {},
            unit=unit,
        )
        self.metrics[key].append(point)

    def record_latency(
        self, component: str, operation: str, duration_ms: float
    ) -> None:
        """Record operation latency"""
        self.record(
            "operation_duration_ms",
            duration_ms,
            labels={"component": component, "operation": operation},
            unit="ms",
        )

    def record_error(self, component: str, error_type: str) -> None:
        """Record error occurrence"""
        self.record(
            "errors_total", 1, labels={"component": component, "error_type": error_type}
        )

    def get_percentile(
        self,
        metric_name: str,
        percentile: float = 0.95,
        labels_filter: Dict[str, str] = None,
    ) -> Optional[float]:
        """
        Get percentile for metric.

        Args:
            metric_name: Name of metric
            percentile: Percentile (0.5 = p50, 0.95 = p95)
            labels_filter: Filter by labels

        Returns:
            Percentile value or None
        """
        import numpy as np

        values = []
        for key, points in self.metrics.items():
            # Check metric name and labels
            if not key.startswith(metric_name):
                continue

            # Check labels if provided
            if labels_filter:
                _, labels_json = key.split(":", 1)
                labels = json.loads(labels_json)
                if not all(labels.get(k) == v for k, v in labels_filter.items()):
                    continue

            # Collect values
            values.extend([p.value for p in points])

        if not values:
            return None

        return float(np.percentile(values, percentile * 100))

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
        import numpy as np

        summary = {}
        for key, points in self.metrics.items():
            if not points:
                continue

            values = [p.value for p in points]
            summary[key] = {
                "count": len(values),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "mean": float(np.mean(values)),
                "p50": float(np.percentile(values, 50)),
                "p95": float(np.percentile(values, 95)),
                "p99": float(np.percentile(values, 99)),
            }

        return summary


@dataclass
class HealthStatus:
    """Health status of a component"""

    component: str
    is_healthy: bool
    status_code: int  # 200=healthy, 500=unhealthy
    details: Dict[str, Any]
    last_check: datetime


class HealthChecker:
    """
    Check health of system components.

    Components:
    - Database connectivity
    - Cache availability
    - External service availability
    - Resource usage
    """

    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, HealthStatus] = {}

    def register_check(self, name: str, check_fn: Callable) -> None:
        """
        Register health check.

        Args:
            name: Check name
            check_fn: Async function returning (is_healthy, details)
        """
        self.checks[name] = check_fn

    async def run_checks(self) -> Dict[str, HealthStatus]:
        """
        Run all health checks.

        Returns:
            Dict mapping check name to HealthStatus
        """
        results = {}

        for name, check_fn in self.checks.items():
            try:
                is_healthy, details = await check_fn()
                status_code = 200 if is_healthy else 500

            except Exception as e:
                is_healthy = False
                details = {"error": str(e)}
                status_code = 500

            results[name] = HealthStatus(
                component=name,
                is_healthy=is_healthy,
                status_code=status_code,
                details=details,
                last_check=datetime.now(),
            )

            self.last_results[name] = results[name]

        return results

    def is_healthy(self) -> bool:
        """Check if all components are healthy"""
        return all(status.is_healthy for status in self.last_results.values())

    def get_summary(self) -> Dict[str, Any]:
        """Get health summary"""
        return {
            "overall_healthy": self.is_healthy(),
            "checks": {
                name: {
                    "healthy": status.is_healthy,
                    "status_code": status.status_code,
                    "last_check": status.last_check.isoformat(),
                    "details": status.details,
                }
                for name, status in self.last_results.items()
            },
        }


@dataclass
class SLOTarget:
    """SLO target for metric"""

    name: str
    metric_name: str
    threshold: float
    comparison: str  # 'lt' (less than), 'gt' (greater than)
    window_size: int  # How many measurements to check


class SLOMonitor:
    """
    Monitor SLO (Service Level Objective) compliance.

    Examples:
    - p95 latency < 500ms
    - Error rate < 1%
    - Availability > 99.9%
    """

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.slos: Dict[str, SLOTarget] = {}
        self.violations: List[str] = []

    def register_slo(self, slo: SLOTarget) -> None:
        """Register SLO"""
        self.slos[slo.name] = slo

    async def check_compliance(self) -> Dict[str, bool]:
        """
        Check compliance for all SLOs.

        Returns:
            Dict mapping SLO name to compliance (True = compliant)
        """
        results = {}

        for slo_name, slo in self.slos.items():
            # Get metric value
            value = self.metrics.get_percentile(
                slo.metric_name, percentile=0.95  # Check p95
            )

            if value is None:
                results[slo_name] = None  # Not enough data
                continue

            # Check threshold
            if slo.comparison == "lt":
                compliant = value < slo.threshold
            elif slo.comparison == "gt":
                compliant = value > slo.threshold
            else:
                compliant = False

            results[slo_name] = compliant

            if not compliant:
                self.violations.append(
                    f"SLO violation: {slo_name} - {value} vs {slo.threshold}"
                )

        return results


@asynccontextmanager
async def trace_operation(
    logger_inst: StructuredLogger,
    operation_name: str,
    metrics: MetricsCollector = None,
    component: str = "unknown",
):
    """
    Context manager to trace operation with logging and metrics.

    Example:
        async with trace_operation(logger, "intent_recognition", metrics):
            result = await recognize_intent(text)
    """
    start_time = time.time()
    correlation = logger_inst.get_correlation()

    logger_inst.info(
        f"Starting {operation_name}",
        context={"operation": operation_name, "trace_id": correlation.trace_id},
    )

    try:
        yield

        duration_ms = (time.time() - start_time) * 1000
        logger_inst.info(
            f"Completed {operation_name}",
            context={"operation": operation_name, "duration_ms": duration_ms},
        )

        if metrics:
            metrics.record_latency(component, operation_name, duration_ms)

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger_inst.error(
            f"Failed {operation_name}",
            context={"operation": operation_name, "duration_ms": duration_ms},
            error=e,
        )

        if metrics:
            metrics.record_error(component, type(e).__name__)

        raise


__all__ = [
    "StructuredLogger",
    "CorrelationID",
    "MetricsCollector",
    "HealthChecker",
    "SLOMonitor",
    "SLOTarget",
    "HealthStatus",
    "trace_operation",
]
