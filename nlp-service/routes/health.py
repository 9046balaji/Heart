from fastapi import APIRouter, status
from datetime import datetime

from core.services.performance_monitor import get_performance_metrics, performance_health_check
from core.testing.performance_tester import run_performance_tests

router = APIRouter(prefix="/api")


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 OK if the service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "nlp-service",
    }


@router.get("/health/performance", status_code=status.HTTP_200_OK)
async def performance_health_check_endpoint():
    """
    Performance health check endpoint.
    Returns performance metrics and health status.
    """
    return performance_health_check()



@router.get("/health/performance/metrics", status_code=status.HTTP_200_OK)
async def performance_metrics():
    """
    Performance metrics endpoint.
    Returns detailed performance metrics.
    """
    return get_performance_metrics()


@router.get("/health/performance/test", status_code=status.HTTP_200_OK)
async def performance_test_endpoint():
    """
    Run comprehensive performance tests.
    Tests all three critical patterns: Caching, ONNX, Reranking.
    """
    tester = await run_performance_tests()
    return {
        "status": "completed",
        "summary": tester.get_summary_stats(),
        "report": tester.generate_report()
    }
