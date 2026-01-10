"""
Embedding Service Factory
Prioritizes optimized ONNX runtime, falls back to PyTorch SentenceTransformers.

Configuration:
    EMBEDDING_BACKEND: 'onnx' | 'pytorch' (env var)
    EMBEDDING_MODEL: model name (env var)
    
    From AppConfig:
        config.rag.embedding_backend
        config.rag.embedding_model_name
"""

import logging
from typing import Any, Union, Optional

try:
    from .interfaces.embedding_base import BaseEmbeddingService
except ImportError:
    # Handle direct import when run as script
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from rag.interfaces.embedding_base import BaseEmbeddingService

logger = logging.getLogger(__name__)

_service_instance: Optional[BaseEmbeddingService] = None


def get_embedding_service(
    model_name: Optional[str] = None,
    force_backend: Optional[str] = None,
) -> BaseEmbeddingService:
    """
    Factory function to get the best available embedding service.
    
    Uses AppConfig for backend selection if not explicitly specified.
    Falls back to auto-detection if config not available.
    
    Args:
        model_name: Name of the model to load (overrides AppConfig)
        force_backend: 'onnx' or 'pytorch' (optional override)
        
    Returns:
        Singleton instance of the embedding service
    """
    global _service_instance
    if _service_instance is not None:
        return _service_instance

    # Load config if not specified
    if model_name is None or force_backend is None:
        try:
            from core.config.app_config import get_app_config
            config = get_app_config()
            model_name = model_name or config.rag.embedding_model_name
            force_backend = force_backend or config.rag.embedding_backend
            logger.info(
                f"Loaded embedding config from AppConfig: "
                f"backend={force_backend}, model={model_name}"
            )
        except Exception as e:
            logger.warning(f"Failed to load AppConfig: {e}. Using auto-detection.")
            model_name = model_name or "all-MiniLM-L6-v2"
            force_backend = None  # Auto-detect

    # 1. If force_backend specified, use only that
    if force_backend == "onnx":
        try:
            from .embedding_onnx import ONNXEmbeddingService, ONNX_AVAILABLE
            if ONNX_AVAILABLE:
                logger.info(
                    f"Initializing ONNX Embedding Service "
                    f"(model={model_name})"
                )
                _service_instance = ONNXEmbeddingService.get_instance(
                    model_name=model_name
                )
                return _service_instance
            else:
                raise ImportError("ONNX not available")
        except Exception as e:
            logger.error(f"Failed to initialize ONNX backend: {e}")
            raise RuntimeError(
                f"ONNX backend requested but not available: {e}"
            ) from e

    elif force_backend == "pytorch":
        try:
            from .embedding_pytorch import PyTorchEmbeddingService
            logger.info(
                f"Initializing PyTorch Embedding Service "
                f"(model={model_name})"
            )
            _service_instance = PyTorchEmbeddingService.get_instance(
                model_name=model_name
            )
            return _service_instance
        except Exception as e:
            logger.error(f"Failed to initialize PyTorch backend: {e}")
            raise RuntimeError(
                f"PyTorch backend requested but not available: {e}"
            ) from e

    # 2. No specific backend requested - try ONNX first
    try:
        from .embedding_onnx import ONNXEmbeddingService, ONNX_AVAILABLE
        if ONNX_AVAILABLE:
            logger.info(
                f"Initializing ONNX Embedding Service (auto-selected, "
                f"model={model_name})"
            )
            _service_instance = ONNXEmbeddingService.get_instance(
                model_name=model_name
            )
            return _service_instance
    except Exception as e:
        logger.warning(f"ONNX initialization failed: {e}. Trying PyTorch...")

    # 3. Fallback to PyTorch / SentenceTransformers
    try:
        from .embedding_pytorch import PyTorchEmbeddingService
        logger.info(
            f"Initializing PyTorch Embedding Service (fallback, "
            f"model={model_name})"
        )
        _service_instance = PyTorchEmbeddingService.get_instance(
            model_name=model_name
        )
        return _service_instance

    except ImportError:
        logger.error("No embedding backends available (ONNX or PyTorch).")
        raise RuntimeError(
            "Critical: Failed to initialize any embedding service. "
            "Install onnxruntime or transformers."
        )


# Alias for backward compatibility
EmbeddingService = get_embedding_service
