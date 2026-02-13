"""
Embedding Service Factory
Prioritizes optimized ONNX runtime, falls back to PyTorch SentenceTransformers.
Supports remote Colab-hosted embeddings via ngrok.

Configuration:
    EMBEDDING_BACKEND: 'onnx' | 'pytorch' | 'remote' (env var)
    EMBEDDING_MODEL: model name (env var)
    COLAB_API_URL: ngrok URL for remote backend (env var)
    
    From AppConfig:
        config.rag.embedding_backend
        config.rag.embedding_model_name
"""


import os
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
    prefer_remote: Optional[bool] = None,
) -> BaseEmbeddingService:
    """
    Factory function to get the best available embedding service.
    
    Uses AppConfig for backend selection if not explicitly specified.
    Falls back to auto-detection if config not available.
    
    Args:
        model_name: Name of the model to load (overrides AppConfig)
        force_backend: 'onnx', 'pytorch', or 'remote' (optional override)
        prefer_remote: When ``True``, the auto-detection path will try the
            remote backend first if ``COLAB_API_URL`` is set **and** a
            health-check succeeds.  Reads from
            ``AppConfig.rag.use_remote_embeddings`` when not supplied.
            
    Returns:
        Singleton instance of the embedding service
    
    Migration note:
        ``prefer_remote`` replaces the previous behaviour where the
        factory unconditionally selected the remote backend whenever
        ``COLAB_API_URL`` was set.  Set
        ``RAGConfig.use_remote_embeddings = True`` (or pass
        ``prefer_remote=True``) to opt in.
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
            if prefer_remote is None:
                prefer_remote = getattr(config.rag, "use_remote_embeddings", False)
            logger.info(
                f"Loaded embedding config from AppConfig: "
                f"backend={force_backend}, model={model_name}, "
                f"prefer_remote={prefer_remote}"
            )
        except Exception as e:
            logger.warning(f"Failed to load AppConfig: {e}. Using auto-detection.")
            model_name = model_name or "all-MiniLM-L6-v2"
            force_backend = None  # Auto-detect

    if prefer_remote is None:
        prefer_remote = False

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

    elif force_backend == "remote":
        try:
            colab_url = os.getenv("COLAB_API_URL", "").strip()
            if not colab_url:
                logger.error(
                    "Remote backend requested but COLAB_API_URL environment "
                    "variable is not set or empty."
                )
                raise RuntimeError(
                    "Remote backend cannot be used: COLAB_API_URL environment "
                    "variable is not set. Export it before starting the service "
                    "(e.g. export COLAB_API_URL=https://your-ngrok-url.app)."
                )
            if not colab_url.startswith(("http://", "https://")):
                logger.error(
                    f"COLAB_API_URL is not a valid URL: {colab_url!r}. "
                    "It must start with http:// or https://."
                )
                raise RuntimeError(
                    f"Remote backend cannot be used: COLAB_API_URL is not a "
                    f"valid URL ({colab_url!r}). It must start with "
                    f"http:// or https://."
                )
            from .embedding_remote import RemoteEmbeddingService
            logger.info(
                f"Initializing Remote Embedding Service "
                f"(url={colab_url})"
            )
            _service_instance = RemoteEmbeddingService.get_instance(
                base_url=colab_url
            )
            return _service_instance
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Failed to initialize remote backend: {e}")
            raise RuntimeError(
                f"Remote backend requested but not available: {e}"
            ) from e

    # 2. No specific backend requested — try remote if opted in and healthy
    colab_url = os.getenv("COLAB_API_URL", "")
    if colab_url and prefer_remote:
        try:
            from .embedding_remote import RemoteEmbeddingService
            svc = RemoteEmbeddingService(base_url=colab_url)
            if svc.health_check():
                logger.info(
                    f"Initializing Remote Embedding Service (auto-selected, "
                    f"url={colab_url})"
                )
                _service_instance = RemoteEmbeddingService.get_instance(
                    base_url=colab_url
                )
                return _service_instance
            else:
                logger.warning(
                    "Remote server at %s failed health check. Trying local...",
                    colab_url,
                )
        except Exception as e:
            logger.warning(f"Remote initialization failed: {e}. Trying local...")

    # 3. Try ONNX
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

    # 4. Fallback to PyTorch / SentenceTransformers
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
        logger.error("No embedding backends available (remote, ONNX, or PyTorch).")
        raise RuntimeError(
            "Critical: Failed to initialize any embedding service. "
            "Set COLAB_API_URL for remote, or install onnxruntime/transformers."
        )


# Alias for backward compatibility
EmbeddingService = get_embedding_service
