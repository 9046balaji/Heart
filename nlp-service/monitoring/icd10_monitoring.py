"""
ICD-10 Mapping Service Performance Monitoring.

Provides metrics for cache hit rates, processing times, and overall performance
of the ICD-10 mapping service.
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict, deque
import threading

from nlp.knowledge_graph.medical_ontology import MedicalOntologyMapper, get_medical_ontology_mapper

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for ICD-10 mapping service."""
    
    # Cache metrics
    cache_hits: int = 0
    cache_misses: int = 0
    cache_size: int = 0
    cache_hit_rate: float = 0.0
    
    # Processing metrics
    total_requests: int = 0
    total_processing_time_ms: float = 0.0
    avg_processing_time_ms: float = 0.0
    min_processing_time_ms: float = float('inf')
    max_processing_time_ms: float = 0.0
    
    # Mapping method distribution
    exact_matches: int = 0
    fuzzy_matches: int = 0
    llm_calls: int = 0
    
    # Top diseases (by lookup count)
    top_diseases: list = None
    
    # Current timestamp
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class ICD10PerformanceMonitor:
    """
    Monitors performance of the ICD-10 mapping service.
    
    Tracks cache hit rates, processing times, and other key metrics.
    """
    
    def __init__(self, mapper: Optional[MedicalOntologyMapper] = None):
        self.mapper = mapper or get_medical_ontology_mapper()
        self.metrics_lock = threading.Lock()
        
        # Track processing times for trending
        self.processing_times = deque(maxlen=1000)  # Keep last 1000 measurements
        
        # Track cache hit/miss ratio over time
        self.cache_history = deque(maxlen=100)  # Keep last 100 cache stats
        
        # Track method distribution
        self.method_distribution = defaultdict(int)
        
        logger.info("ICD-10 Performance Monitor initialized")
    
    async def monitor_mapping(self, disease_name: str) -> Tuple[Optional[Dict], float]:
        """
        Monitor a single mapping operation and return both result and processing time.
        
        Args:
            disease_name: Disease name to map
            
        Returns:
            Tuple of (mapping_result, processing_time_ms)
        """
        start_time = time.time()
        
        try:
            # Perform the mapping
            result = await self.mapper.map_disease(disease_name)
            
            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000
            
            # Update metrics based on the mapping result
            with self.metrics_lock:
                self.processing_times.append(processing_time_ms)
                
                # Update method distribution if we have a result
                if result and 'match_method' in result:
                    method = result['match_method']
                    self.method_distribution[method] += 1
                
                # Determine if it was a cache hit or miss
                # Note: The mapper itself tracks analytics internally
                # We'll use the mapper's analytics for cache stats
                analytics = self.mapper.analytics
                
                # Update our own metrics
                if result is not None:
                    # For simplicity, we'll assume it was a hit if we got a result
                    # In reality, the mapper tracks this internally
                    pass
            
            return result, processing_time_ms
            
        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Mapping failed for '{disease_name}': {e}")
            return None, processing_time_ms
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """
        Get current performance metrics.
        
        Returns:
            PerformanceMetrics object with current statistics
        """
        # Get analytics from the mapper
        mapper_stats = self.mapper.get_stats()
        
        with self.metrics_lock:
            # Calculate metrics
            total_requests = mapper_stats.get('total_lookups', 0)
            cache_hits = mapper_stats.get('cache_hits', 0)
            cache_misses = mapper_stats.get('cache_misses', 0)
            cache_size = len(self.mapper.cache)
            
            cache_hit_rate = 0.0
            if total_requests > 0:
                cache_hit_rate = (cache_hits / total_requests) * 100
            
            # Calculate processing time metrics
            if self.processing_times:
                total_processing_time = sum(self.processing_times)
                avg_processing_time = total_processing_time / len(self.processing_times)
                min_processing_time = min(self.processing_times)
                max_processing_time = max(self.processing_times)
            else:
                total_processing_time = 0.0
                avg_processing_time = 0.0
                min_processing_time = 0.0
                max_processing_time = 0.0
            
            # Get method distribution counts
            exact_matches = self.method_distribution.get('exact', 0)
            fuzzy_matches = self.method_distribution.get('fuzzy', 0)
            llm_calls = self.method_distribution.get('llm', 0)
            
            # Get top diseases
            top_diseases = self.mapper.get_popular_diseases(10)
        
        return PerformanceMetrics(
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            cache_size=cache_size,
            cache_hit_rate=cache_hit_rate,
            total_requests=total_requests,
            total_processing_time_ms=total_processing_time,
            avg_processing_time_ms=avg_processing_time,
            min_processing_time_ms=min_processing_time,
            max_processing_time_ms=max_processing_time,
            exact_matches=exact_matches,
            fuzzy_matches=fuzzy_matches,
            llm_calls=llm_calls,
            top_diseases=top_diseases,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def get_detailed_report(self) -> Dict[str, Any]:
        """
        Get detailed performance report.
        
        Returns:
            Dictionary with detailed performance metrics
        """
        metrics = self.get_current_metrics()
        
        return {
            "timestamp": metrics.timestamp,
            "cache_performance": {
                "cache_size": metrics.cache_size,
                "cache_hit_rate_percent": metrics.cache_hit_rate,
                "cache_hits": metrics.cache_hits,
                "cache_misses": metrics.cache_misses,
                "total_requests": metrics.total_requests
            },
            "processing_performance": {
                "total_processing_time_ms": metrics.total_processing_time_ms,
                "average_processing_time_ms": metrics.avg_processing_time_ms,
                "min_processing_time_ms": metrics.min_processing_time_ms,
                "max_processing_time_ms": metrics.max_processing_time_ms,
                "total_requests": metrics.total_requests
            },
            "mapping_distribution": {
                "exact_matches": metrics.exact_matches,
                "fuzzy_matches": metrics.fuzzy_matches,
                "llm_calls": metrics.llm_calls
            },
            "top_diseases": metrics.top_diseases,
            "health_status": self._get_health_status(metrics)
        }
    
    def _get_health_status(self, metrics: PerformanceMetrics) -> str:
        """
        Determine health status based on performance metrics.
        
        Returns:
            Health status string (healthy, warning, critical)
        """
        # Define health criteria
        if metrics.cache_hit_rate < 50:
            return "critical"  # Too many cache misses
        elif metrics.cache_hit_rate < 80:
            return "warning"  # Could be better
        elif metrics.avg_processing_time_ms > 500:  # >500ms is slow
            return "warning"
        elif metrics.max_processing_time_ms > 2000:  # >2s is very slow
            return "warning"
        else:
            return "healthy"
    
    def reset_metrics(self):
        """Reset all performance metrics."""
        with self.metrics_lock:
            self.processing_times.clear()
            self.cache_history.clear()
            self.method_distribution.clear()
        
        # Also reset the mapper's analytics
        self.mapper.analytics = self.mapper.__class__().analytics
        logger.info("Performance metrics reset")


# Global instance for singleton access
_monitor_instance: Optional[ICD10PerformanceMonitor] = None


def get_icd10_monitor() -> ICD10PerformanceMonitor:
    """
    Get singleton ICD-10 performance monitor instance.
    
    Returns:
        ICD10PerformanceMonitor instance
    """
    global _monitor_instance
    
    if _monitor_instance is None:
        mapper = get_medical_ontology_mapper()
        _monitor_instance = ICD10PerformanceMonitor(mapper)
    
    return _monitor_instance


# Convenience functions for common monitoring tasks
async def get_current_performance_metrics() -> PerformanceMetrics:
    """
    Get current ICD-10 mapping performance metrics.
    
    Returns:
        PerformanceMetrics object
    """
    monitor = get_icd10_monitor()
    return monitor.get_current_metrics()


async def get_detailed_performance_report() -> Dict[str, Any]:
    """
    Get detailed ICD-10 mapping performance report.
    
    Returns:
        Dictionary with detailed metrics
    """
    monitor = get_icd10_monitor()
    return monitor.get_detailed_report()


async def monitor_disease_mapping(disease_name: str) -> Tuple[Optional[Dict], float]:
    """
    Monitor a single disease mapping operation.
    
    Args:
        disease_name: Disease name to map
        
    Returns:
        Tuple of (mapping_result, processing_time_ms)
    """
    monitor = get_icd10_monitor()
    return await monitor.monitor_mapping(disease_name)


# Example usage and testing
async def test_monitoring():
    """
    Test the monitoring functionality.
    """
    logger.info("Testing ICD-10 performance monitoring...")
    
    # Get monitor instance
    monitor = get_icd10_monitor()
    
    # Test a few mappings
    test_diseases = [
        "heart attack",
        "myocardial infarction",
        "MI",
        "hypertension",
        "atrial fibrillation"
    ]
    
    for disease in test_diseases:
        result, processing_time = await monitor_disease_mapping(disease)
        logger.info(f"Mapping '{disease}': {processing_time:.2f}ms")
    
    # Get and display metrics
    metrics = await get_current_performance_metrics()
    report = await get_detailed_performance_report()
    
    print(f"Cache Hit Rate: {metrics.cache_hit_rate:.2f}%")
    print(f"Avg Processing Time: {metrics.avg_processing_time_ms:.2f}ms")
    print(f"Cache Size: {metrics.cache_size}")
    print(f"Health Status: {report['health_status']}")
    
    return metrics, report


if __name__ == "__main__":
    import asyncio
    
    # Run test
    asyncio.run(test_monitoring())