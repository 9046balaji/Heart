"""
Dependency manifest - declares required vs optional dependencies.
Service fails fast on missing required dependencies.
"""
import os
import sys
from loguru import logger

REQUIRED_DEPENDENCIES = [
    ("fastapi", "FastAPI web framework"),
    ("pydantic", "Data validation"),
    ("uvicorn", "ASGI server"),
]

OPTIONAL_DEPENDENCIES = {
    "ENABLE_RAG": [("chromadb", "Vector database for RAG")],
    "ENABLE_SPACY": [("spacy", "NLP entity extraction")],
    "ENABLE_TORCH": [("torch", "ML model inference")],
}

def validate_dependencies():
    """Validate all required dependencies are available."""
    missing = []
    
    for module_name, description in REQUIRED_DEPENDENCIES:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(f"{module_name} ({description})")
    
    if missing:
        logger.critical(f"Missing required dependencies: {missing}")
        logger.critical("Service cannot start. Install dependencies and retry.")
        sys.exit(1)
    
    logger.info("All required dependencies validated")

def get_enabled_features() -> dict:
    """Return dict of feature flags based on env vars and available deps."""
    features = {}
    
    for flag, deps in OPTIONAL_DEPENDENCIES.items():
        enabled = os.getenv(flag, "true").lower() == "true"
        if enabled:
            available = all(_check_import(mod) for mod, _ in deps)
            features[flag] = available
            if enabled and not available:
                logger.warning(f"{flag} enabled but dependencies missing")
        else:
            features[flag] = False
    
    return features

def _check_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception as e:
        logger.warning(f"Failed to import optional dependency {module_name}: {e}")
        return False

def check_optional_dependency(module_name: str) -> bool:
    """Public wrapper for _check_import."""
    return _check_import(module_name)