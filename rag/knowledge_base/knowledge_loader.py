"""
Knowledge Loader - JSON-based Data Ingestion with Singleton Caching

Provides:
- KnowledgeLoaderSingleton: Thread-safe singleton for managing knowledge base
- TTL-based caching with automatic expiration
- Memory monitoring and cache invalidation
- Backward-compatible facade functions
"""


import json
import logging
import time
import threading
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a single cache entry with TTL support."""
    data: Any
    created_at: float
    ttl_seconds: int
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        elapsed = time.time() - self.created_at
        return elapsed > self.ttl_seconds

    def touch(self) -> None:
        """Update last access time and increment counter."""
        self.last_accessed = time.time()
        self.access_count += 1


class KnowledgeLoaderSingleton:
    """
    Thread-safe singleton for managing knowledge base data caching.

    Features:
    - Automatic data loading from JSON files
    - TTL-based cache expiration (default 1 hour)
    - Memory monitoring and statistics
    - Cache invalidation mechanisms
    - Thread-safe access

    Example:
        loader = KnowledgeLoaderSingleton.get_instance()
        drugs = loader.get_drugs()
        guidelines = loader.get_guidelines()

        # Invalidate specific cache
        loader.invalidate_cache("guidelines")

        # Or invalidate all
        loader.clear_cache()
    """

    _instance: Optional["KnowledgeLoaderSingleton"] = None
    _lock = threading.RLock()

    def __new__(cls) -> "KnowledgeLoaderSingleton":
        """Implement thread-safe singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> "KnowledgeLoaderSingleton":
        """
        Get the singleton instance.

        Returns:
            KnowledgeLoaderSingleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        if not cls._instance._initialized:
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the singleton (called once)."""
        if self._initialized:
            return

        self._cache: Dict[str, CacheEntry] = {}
        self._data_dir = Path("data")
        self._ttl_seconds = 3600  # 1 hour default TTL
        self._initialized = True

        logger.info("✅ KnowledgeLoaderSingleton initialized")

    def set_data_dir(self, data_dir: str) -> None:
        """Set the data directory path."""
        self._data_dir = Path(data_dir)
        logger.info(f"Data directory set to: {self._data_dir}")

    def set_ttl(self, ttl_seconds: int) -> None:
        """Set cache TTL in seconds."""
        if ttl_seconds < 60:
            logger.warning(f"TTL of {ttl_seconds}s is very short, recommend >= 60s")
        self._ttl_seconds = ttl_seconds
        logger.info(f"Cache TTL set to {ttl_seconds} seconds")

    # ========================================================================
    # Cache Management
    # ========================================================================

    def _load_json_data(self, filename: str) -> List[Dict]:
        """
        Load JSON file from data directory.

        Args:
            filename: Name of JSON file to load

        Returns:
            List of dictionaries or empty list if file not found
        """
        file_path = self._data_dir / filename

        if not file_path.exists():
            logger.warning(f"Data file not found: {file_path}")
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Handle wrapper keys like {"drugs": [...]} vs raw list
                if isinstance(data, dict):
                    for key, val in data.items():
                        if isinstance(val, list):
                            logger.debug(f"Loaded {len(val)} items from '{key}' in {filename}")
                            return val
                    return [data]

                if isinstance(data, list):
                    logger.debug(f"Loaded {len(data)} items from {filename}")
                    return data

                logger.warning(f"Unexpected data format in {filename}: {type(data)}")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filename}: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            return []

    def _get_cached(self, key: str, filename: str) -> List[Dict]:
        """
        Get cached data or load from file.

        Args:
            key: Cache key name
            filename: JSON filename to load

        Returns:
            Cached or freshly loaded data
        """
        with self._lock:
            # Check if in cache and not expired
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    entry.touch()
                    logger.debug(f"Cache hit for '{key}' (access #{entry.access_count})")
                    return entry.data
                else:
                    logger.debug(f"Cache expired for '{key}', reloading...")
                    del self._cache[key]

            # Load fresh data
            data = self._load_json_data(filename)

            # Store in cache
            self._cache[key] = CacheEntry(
                data=data,
                created_at=time.time(),
                ttl_seconds=self._ttl_seconds,
            )

            logger.info(f"Cached '{key}' with {len(data)} items")
            return data

    def invalidate_cache(self, key: str) -> None:
        """
        Invalidate specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.info(f"✅ Cache invalidated for '{key}'")

    def clear_cache(self) -> None:
        """Clear all cached data."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"✅ Cleared all cache ({count} entries)")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        with self._lock:
            stats = {
                "cached_keys": list(self._cache.keys()),
                "entry_count": len(self._cache),
                "total_items": sum(len(entry.data) for entry in self._cache.values()),
                "entries": {},
            }

            for key, entry in self._cache.items():
                age_seconds = time.time() - entry.created_at
                stats["entries"][key] = {
                    "items": len(entry.data),
                    "age_seconds": int(age_seconds),
                    "ttl_seconds": entry.ttl_seconds,
                    "is_expired": entry.is_expired(),
                    "access_count": entry.access_count,
                    "last_accessed": datetime.fromtimestamp(entry.last_accessed).isoformat(),
                }

            return stats

    # ========================================================================
    # Public API - Data Access (DAO INTERFACE)
    # ========================================================================

    def get_drugs(self) -> List[Dict]:
        """Get all drugs from cache or load from drugs.json."""
        return self._get_cached("drugs", "drugs.json")

    def get_guidelines(self) -> List[Dict]:
        """Get all guidelines from cache or load from guidelines.json."""
        return self._get_cached("guidelines", "guidelines.json")

    def get_symptoms(self) -> List[Dict]:
        """Get all symptoms from cache or load from symptoms.json."""
        return self._get_cached("symptoms", "symptoms.json")


# ============================================================================
# Backward Compatibility - Legacy Facade Functions (DEPRECATED)
# ============================================================================
# NOTE: These functions are DEPRECATED. Use UnifiedKnowledgeIngestion instead.
# Kept only for temporary backward compatibility. Remove after migration complete.

def get_knowledge_loader() -> KnowledgeLoaderSingleton:
    """Get the singleton knowledge loader instance. (DEPRECATED - for backward compat only)"""
    return KnowledgeLoaderSingleton.get_instance()


# Legacy module-level caching functions (using singleton internally)
def get_quick_cardiovascular_info() -> List[Dict]:
    """
    Get cardiovascular guidelines (backward compatible).
    DEPRECATED: Use UnifiedKnowledgeIngestion.ingest_guidelines() instead.
    """
    return get_knowledge_loader().get_guidelines()


def get_quick_drug_info() -> List[Dict]:
    """
    Get drug database (backward compatible).
    DEPRECATED: Use UnifiedKnowledgeIngestion.ingest_drugs() instead.
    """
    return get_knowledge_loader().get_drugs()


def check_drug_interactions_quick(drug_names: List[str]) -> List[Dict]:
    """
    Check for drug interactions.
    DEPRECATED: Complex interaction logic should be in knowledge graph queries.
    Note: Simplified version. Complex logic should be moved to knowledge graph.
    """
    interactions = []

    for i, drug1_name in enumerate(drug_names):
        for drug2_name in drug_names[i + 1 :]:
            # Simple interaction check based on common contraindications
            interactions.append(
                {
                    "drug1": drug1_name,
                    "drug2": drug2_name,
                    "severity": "unknown",  # Would need more data
                    "note": "Requires medical knowledge graph for detailed analysis",
                }
            )

    return interactions


def triage_symptoms_quick(symptom_name: str) -> Optional[Dict]:
    """
    Find symptom by name (backward compatible).
    DEPRECATED: Use UnifiedKnowledgeIngestion.ingest_symptoms() instead.
    """
    symptoms = get_knowledge_loader().get_symptoms()
    keyword_lower = symptom_name.lower()

    for s in symptoms:
        if keyword_lower in s.get("symptom", "").lower():
            return s

    return None



def classify_blood_pressure_quick(systolic: int, diastolic: int) -> str:
    """
    Classify blood pressure reading.
    DEPRECATED: Move to medical utility module.
    Note: This was in the Python class. Re-implemented here.
    """
    if systolic < 120 and diastolic < 80:
        return "Normal"
    elif systolic < 130 and diastolic < 80:
        return "Elevated"
    elif systolic < 140 or diastolic < 90:
        return "Stage 1 Hypertension"
    elif systolic >= 140 or diastolic >= 90:
        return "Stage 2 Hypertension"
    else:
        return "Unknown"


# Legacy compatibility: REMOVED - Use UnifiedKnowledgeIngestion instead
# The following deprecated functions have been removed:
# - load_all_knowledge() - DEPRECATED, use UnifiedKnowledgeIngestion.ingest_all()
# - index_knowledge_to_rag - DEPRECATED alias
#
# See MIGRATION_GUIDE.md for migration patterns

