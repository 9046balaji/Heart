"""
PyTorch Embedding Service - Standard Implementation

This module provides vector embedding generation using SentenceTransformers
for local, fast, and free semantic search capabilities.

This is the standard PyTorch implementation, used as a fallback when ONNX is unavailable.
"""

import logging
import hashlib
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict

import numpy as np

try:
    from .interfaces.embedding_base import BaseEmbeddingService
except ImportError:
    # Handle direct import when run as script
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from rag.interfaces.embedding_base import BaseEmbeddingService

logger = logging.getLogger(__name__)

# Optional MultiTierCache import
try:
    from core.services.advanced_cache import MultiTierCache
    MULTI_TIER_CACHE_AVAILABLE = True
except ImportError:
    MultiTierCache = None
    MULTI_TIER_CACHE_AVAILABLE = False
    logger.info("MultiTierCache not available, using local cache fallback")

# Optional SentenceTransformers import
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "sentence-transformers not installed. " "Run: pip install sentence-transformers"
    )


class PyTorchEmbeddingService(BaseEmbeddingService):
    """
    Singleton embedding service using SentenceTransformers (PyTorch).
    """

    _instance: Optional["PyTorchEmbeddingService"] = None

    # Default models with different trade-offs
    MODELS = {
        "fast": "all-MiniLM-L6-v2",  # 384 dims, fastest
        "balanced": "all-mpnet-base-v2",  # 768 dims, better quality
        "medical": "pritamdeka/S-PubMedBert-MS-MARCO",  # Medical domain
    }

    # Shared MultiTierCache instance (singleton for all embedding services)
    _shared_multi_tier_cache: Optional["MultiTierCache"] = None

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_size: int = 10000,
        device: str = None,
        multi_tier_cache: Optional["MultiTierCache"] = None,
    ):
        """
        Initialize Embedding Service.

        Args:
            model_name: SentenceTransformer model name
            cache_size: Max cached embeddings (L1 fallback)
            device: 'cuda', 'cpu', or None (auto-detect)
            multi_tier_cache: Optional injected MultiTierCache instance
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )

        self.model_name = model_name
        self._local_cache: Dict[str, np.ndarray] = {}
        self._cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0
        
        # MultiTierCache integration
        if multi_tier_cache is not None:
            self._multi_tier_cache = multi_tier_cache
            self._use_multi_tier = True
            logger.info("✅ Using injected MultiTierCache for PyTorch embeddings")
        elif MULTI_TIER_CACHE_AVAILABLE:
            # Use shared singleton
            if PyTorchEmbeddingService._shared_multi_tier_cache is None:
                PyTorchEmbeddingService._shared_multi_tier_cache = MultiTierCache(
                    l1_max_size=cache_size,
                    enable_l2=True,  # Enable Redis L2 if available
                )
                logger.info("✅ Created shared MultiTierCache (L1 + L2 Redis)")
            self._multi_tier_cache = PyTorchEmbeddingService._shared_multi_tier_cache
            self._use_multi_tier = True
        else:
            self._multi_tier_cache = None
            self._use_multi_tier = False
            logger.info("⚠️ Using local Dict cache (MultiTierCache unavailable)")
        
        # Thread pool executor for non-blocking embedding operations
        self._executor = ThreadPoolExecutor(max_workers=4)

        # Load model
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name, device=device)
        self.dimension = self.model.get_sentence_embedding_dimension()

        cache_type = "MultiTierCache" if self._use_multi_tier else "LocalCache"
        logger.info(
            f"✅ PyTorchEmbeddingService initialized: "
            f"model={model_name}, dim={self.dimension}, device={self.model.device}, cache={cache_type}"
        )

    @classmethod
    def get_instance(
        cls, model_name: str = "all-MiniLM-L6-v2", **kwargs
    ) -> "PyTorchEmbeddingService":
        """
        Singleton pattern - reuse model across requests.
        """
        if cls._instance is None:
            cls._instance = cls(model_name=model_name, **kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (for testing)."""
        cls._instance = None
    
    def shutdown(self):
        """Shutdown the executor to free resources."""
        if hasattr(self, '_executor') and self._executor:
            self._executor.shutdown(wait=True)

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Prefix with 'emb:' for namespace in shared cache
        return f"emb:{hashlib.sha256(text.encode()).hexdigest()}"

    def _manage_local_cache(self):
        """Evict oldest entries if local cache is full."""
        if len(self._local_cache) >= self._cache_size:
            # Remove oldest 10%
            to_remove = int(self._cache_size * 0.1)
            keys_to_remove = list(self._local_cache.keys())[:to_remove]
            for key in keys_to_remove:
                del self._local_cache[key]

    def _get_from_local_cache(self, cache_key: str) -> Optional[np.ndarray]:
        """Get embedding from local cache (sync fallback)."""
        if cache_key in self._local_cache:
            self._cache_hits += 1
            return self._local_cache[cache_key]
        return None

    def _set_to_local_cache(self, cache_key: str, embedding: np.ndarray) -> None:
        """Set embedding in local cache (sync fallback)."""
        self._manage_local_cache()
        self._local_cache[cache_key] = embedding

    async def _get_from_multi_tier_cache(self, cache_key: str) -> Optional[List[float]]:
        """Get embedding from MultiTierCache (async)."""
        if self._use_multi_tier and self._multi_tier_cache:
            try:
                result = await self._multi_tier_cache.get(cache_key)
                if result is not None:
                    self._cache_hits += 1
                    return result
            except Exception as e:
                logger.warning(f"MultiTierCache get error: {e}")
        return None

    async def _set_to_multi_tier_cache(self, cache_key: str, embedding: List[float]) -> None:
        """Set embedding in MultiTierCache (async)."""
        if self._use_multi_tier and self._multi_tier_cache:
            try:
                await self._multi_tier_cache.set(cache_key, embedding, ttl_seconds=3600)
            except Exception as e:
                logger.warning(f"MultiTierCache set error: {e}")

    async def embed_text(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for single text (non-blocking).
        """
        if not text or not text.strip():
            return [0.0] * self.dimension

        cache_key = self._get_cache_key(text)

        # Check local cache first (sync, fast)
        if use_cache:
            cached = self._get_from_local_cache(cache_key)
            if cached is not None:
                return cached.tolist()
            
            # Try MultiTierCache
            multi_cached = await self._get_from_multi_tier_cache(cache_key)
            if multi_cached is not None:
                # Also populate local cache
                self._set_to_local_cache(cache_key, np.array(multi_cached))
                return multi_cached
            
            self._cache_misses += 1

        # Run blocking operation in thread pool
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        embedding = await loop.run_in_executor(
            self._executor,
            self._encode_sync,
            text
        )

        # Cache result
        if use_cache:
            self._set_to_local_cache(cache_key, np.array(embedding))
            # Also update MultiTier cache
            await self._set_to_multi_tier_cache(cache_key, embedding)

        return embedding
    
    def _encode_sync(self, text: str) -> List[float]:
        """
        Synchronous embedding method that runs in thread pool.
        """
        # Generate embedding
        embedding = self.model.encode(
            text,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
            show_progress_bar=False,
        )
        return embedding.tolist()

    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently (non-blocking).
        """
        if not texts:
            return []

        # Filter empty texts
        valid_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        valid_texts = [texts[i] for i in valid_indices]

        if not valid_texts:
            return [[0.0] * self.dimension] * len(texts)

        # Run blocking operation in thread pool
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        embeddings = await loop.run_in_executor(
            self._executor,
            self._encode_batch_sync,
            valid_texts,
            batch_size,
            show_progress
        )

        # Map back to original indices
        result = [[0.0] * self.dimension] * len(texts)
        for i, idx in enumerate(valid_indices):
            result[idx] = embeddings[i]
            # Cache
            cache_key = self._get_cache_key(valid_texts[i])
            self._set_to_local_cache(cache_key, np.array(embeddings[i]))
            # Also update MultiTier cache in background
            if self._use_multi_tier:
                asyncio.create_task(self._set_to_multi_tier_cache(cache_key, embeddings[i]))

        return result
    
    def _encode_batch_sync(
        self,
        valid_texts: List[str],
        batch_size: int,
        show_progress: bool
    ) -> List[List[float]]:
        """
        Synchronous batch embedding method that runs in thread pool.
        """
        # Generate embeddings
        embeddings = self.model.encode(
            valid_texts,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=show_progress,
        )
        
        return embeddings.tolist()

    async def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts (0-1).
        """
        emb1 = await self.embed_text(text1)
        emb2 = await self.embed_text(text2)
        
        # Convert to numpy arrays for dot product
        emb1_np = np.array(emb1)
        emb2_np = np.array(emb2)
        
        return float(np.dot(emb1_np, emb2_np))

    async def find_most_similar(
        self,
        query: str,
        candidates: List[str],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[Dict]:
        """
        Find most similar texts from candidates.
        """
        if not candidates:
            return []

        # Embed query
        query_emb = await self.embed_text(query)

        # Embed candidates
        candidate_embs = await self.embed_batch(
            candidates,
            show_progress=len(candidates) > 100,
        )

        # Calculate similarities
        query_emb_np = np.array(query_emb)
        candidate_embs_np = np.array(candidate_embs)
        similarities = np.dot(candidate_embs_np, query_emb_np)

        # Get top-k
        results = []
        for i, score in enumerate(similarities):
            if score >= threshold:
                results.append(
                    {
                        "text": candidates[i],
                        "score": float(score),
                        "index": i,
                    }
                )

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_k]

    async def compute_similarity_matrix(self, texts: List[str]) -> np.ndarray:
        """
        Compute pairwise similarity matrix for texts.
        """
        embeddings = await self.embed_batch(texts)
        embeddings_np = np.array(embeddings)
        return np.dot(embeddings_np, embeddings_np.T)

    def get_dimension(self) -> int:
        """
        Get the embedding dimension.
        
        Returns:
            Dimension of the embedding vectors
        """
        return self.dimension

    def get_model_info(self) -> Dict:
        """Get information about the loaded model."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0
        
        info = {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "device": str(self.model.device),
            "cache_size": len(self._local_cache),
            "max_cache_size": self._cache_size,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": hit_rate,
            "multi_tier_enabled": self._use_multi_tier,
        }
        
        if self._use_multi_tier and self._multi_tier_cache:
            info["multi_tier_stats"] = self._multi_tier_cache.get_statistics()
        
        return info

    async def warm_cache(self, texts: List[str]) -> int:
        """
        Pre-warm the embedding cache with commonly used texts.
        """
        if not texts:
            return 0

        try:
            # Generate embeddings for all texts in batch
            embeddings = await self.embed_batch(texts)

            # Cache each embedding
            warmed_count = 0
            for i, text in enumerate(texts):
                if text and text.strip():
                    cache_key = self._get_cache_key(text)
                    self._set_to_local_cache(cache_key, np.array(embeddings[i]))
                    # Also update MultiTier cache
                    if self._use_multi_tier:
                        await self._set_to_multi_tier_cache(cache_key, embeddings[i])
                    warmed_count += 1

            logger.info(f"Warmed {warmed_count} embeddings in cache")
            return warmed_count

        except Exception as e:
            logger.error(f"Failed to warm embedding cache: {e}")
            return 0
