"""
Monitoring Routes for Performance Metrics.

Provides endpoints for monitoring system performance including:
- ICD-10 mapping performance
- Cache hit rates
- Processing times
- System health metrics
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from monitoring.icd10_monitoring import (
    get_current_performance_metrics,
    get_detailed_performance_report,
    monitor_disease_mapping
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/icd10/performance")
async def get_icd10_performance_metrics():
    """
    Get current ICD-10 mapping performance metrics.
    
    Returns:
        Performance metrics including cache hit rates, processing times, etc.
    """
    try:
        metrics = await get_current_performance_metrics()
        return {
            "status": "success",
            "data": {
                "cache_hit_rate_percent": metrics.cache_hit_rate,
                "cache_size": metrics.cache_size,
                "cache_hits": metrics.cache_hits,
                "cache_misses": metrics.cache_misses,
                "total_requests": metrics.total_requests,
                "average_processing_time_ms": metrics.avg_processing_time_ms,
                "min_processing_time_ms": metrics.min_processing_time_ms,
                "max_processing_time_ms": metrics.max_processing_time_ms,
                "total_processing_time_ms": metrics.total_processing_time_ms,
                "exact_matches": metrics.exact_matches,
                "fuzzy_matches": metrics.fuzzy_matches,
                "llm_calls": metrics.llm_calls,
                "top_diseases": metrics.top_diseases,
                "timestamp": metrics.timestamp
            }
        }
    except Exception as e:
        logger.error(f"Error getting ICD-10 performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/icd10/performance/detailed")
async def get_detailed_icd10_performance():
    """
    Get detailed ICD-10 mapping performance report.
    
    Returns:
        Detailed performance report with health status
    """
    try:
        report = await get_detailed_performance_report()
        return {
            "status": "success",
            "data": report
        }
    except Exception as e:
        logger.error(f"Error getting detailed ICD-10 performance report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/icd10/test-mapping")
async def test_icd10_mapping(disease_name: str):
    """
    Test a single ICD-10 mapping and return performance metrics.
    
    Args:
        disease_name: Disease name to map
        
    Returns:
        Mapping result and performance metrics
    """
    try:
        result, processing_time = await monitor_disease_mapping(disease_name)
        return {
            "status": "success",
            "data": {
                "disease_name": disease_name,
                "mapping_result": result,
                "processing_time_ms": processing_time
            }
        }
    except Exception as e:
        logger.error(f"Error testing ICD-10 mapping for '{disease_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_system_health():
    """
    Get overall system health status.
    
    Returns:
        Health status and key metrics
    """
    try:
        # Get performance report to determine health
        report = await get_detailed_performance_report()
        
        health_status = report.get("health_status", "unknown")
        
        return {
            "status": "success",
            "data": {
                "health_status": health_status,
                "timestamp": report.get("timestamp"),
                "service": "nlp-service",
                "components": {
                    "icd10_mapping": health_status
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_monitoring_status():
    """
    Get monitoring system status.
    
    Returns:
        Monitoring system status information
    """
    try:
        return {
            "status": "running",
            "service": "monitoring-service",
            "endpoints": [
                "/monitoring/icd10/performance",
                "/monitoring/icd10/performance/detailed", 
                "/monitoring/icd10/test-mapping",
                "/monitoring/health",
                "/monitoring/status",
                "/monitoring/metrics"
            ],
            "features": [
                "ICD-10 mapping performance tracking",
                "Cache hit rate monitoring",
                "Processing time analytics",
                "System health monitoring",
                "System metrics"
            ]
        }
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_system_metrics():
    """
    Get detailed system metrics.
    """
    try:
        from core.analytics import analytics_manager
        return analytics_manager.get_analytics_summary()
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Include additional monitoring endpoints as needed