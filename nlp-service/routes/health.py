from fastapi import APIRouter, status, Depends
from datetime import datetime

from core.services.performance_monitor import get_performance_metrics, performance_health_check
from core.testing.performance_tester import run_performance_tests
from core.database.xampp_db import get_database, XAMPPDatabase

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


@router.get("/health/database", status_code=status.HTTP_200_OK)
async def database_health(db: XAMPPDatabase = Depends(get_database)):
    """
    Database pool health check endpoint.
    Returns database connection pool statistics and health status.
    """
    pool_status = await db.get_pool_status()
    
    # Check if pools are healthy
    write_pool = pool_status["write_pool"]
    is_healthy = write_pool["free"] > 0  # At least one free connection
    
    return {
        "status": "healthy" if is_healthy else "degraded",
        "pools": pool_status,
        "warnings": [
            f"Write pool at {write_pool['used']}/{write_pool['max']} capacity"
        ] if write_pool["used"] / write_pool["max"] > 0.8 else []
    }
