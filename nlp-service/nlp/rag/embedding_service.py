"""
Embedding Service - Foundation of Semantic Search

This module provides vector embedding generation using SentenceTransformers
for local, fast, and free semantic search capabilities.

Addresses GAP from MEMORI_VS_RAG_ANALYSIS.md:
- ❌ No embedding generation -> ✅ Local SentenceTransformers embeddings
- ❌ No semantic search -> ✅ Vector similarity calculations

Model: all-MiniLM-L6-v2
- 384 dimensions (fast)
- Good quality for semantic similarity
- Runs locally (no API costs)
- ~90MB model size
"""

import logging
import hashlib
from typing import List, Optional, Dict, Tuple
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

# Optional SentenceTransformers import
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "sentence-transformers not installed. "
        "Run: pip install sentence-transformers"
    )


class EmbeddingService:
    """
    Singleton embedding service using SentenceTransformers.
    
    Features:
    - Local embedding generation (no API costs)
    - Embedding cache for performance
    - Batch processing for efficiency
    - Similarity calculations
    
    Example:
        service = EmbeddingService.get_instance()
        
        # Single embedding
        embedding = service.embed_text("chest pain symptoms")
        
        # Semantic similarity
        sim = service.similarity("chest pain", "cardiac discomfort")
        # Returns ~0.78 (high similarity)
        
        # Batch embeddings
        embeddings = service.embed_batch(["text1", "text2", "text3"])
    """
    
    _instance: Optional["EmbeddingService"] = None
    
    # Default models with different trade-offs
    MODELS = {
        "fast": "all-MiniLM-L6-v2",           # 384 dims, fastest
        "balanced": "all-mpnet-base-v2",       # 768 dims, better quality
        "medical": "pritamdeka/S-PubMedBert-MS-MARCO",  # Medical domain
    }
    
    def __init__(
        self, 
        model_name: str = "all-MiniLM-L6-v2",
        cache_size: int = 10000,
        device: str = None,
    ):
        """
        Initialize Embedding Service.
        
        Args:
            model_name: SentenceTransformer model name
            cache_size: Max cached embeddings
            device: 'cuda', 'cpu', or None (auto-detect)
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name
        self._cache: Dict[str, np.ndarray] = {}
        self._cache_size = cache_size
        
        # Load model
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name, device=device)
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        logger.info(
            f"✅ EmbeddingService initialized: "
            f"model={model_name}, dim={self.dimension}, device={self.model.device}"
        )
    
    @classmethod
    def get_instance(
        cls, 
        model_name: str = "all-MiniLM-L6-v2",
        **kwargs
    ) -> "EmbeddingService":
        """
        Singleton pattern - reuse model across requests.
        
        This prevents loading the model multiple times,
        which can be slow and memory-intensive.
        """
        if cls._instance is None:
            cls._instance = cls(model_name=model_name, **kwargs)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (for testing)."""
        cls._instance = None
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _manage_cache(self):
        """Evict oldest entries if cache is full."""
        if len(self._cache) >= self._cache_size:
            # Remove oldest 10%
            to_remove = int(self._cache_size * 0.1)
            keys_to_remove = list(self._cache.keys())[:to_remove]
            for key in keys_to_remove:
                del self._cache[key]
    
    def embed_text(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for single text.
        
        Args:
            text: Input text to embed
            use_cache: Whether to use embedding cache
            
        Returns:
            List of floats (embedding vector)
            
        Example:
            embedding = service.embed_text("chest pain symptoms")
            # Returns: [0.023, -0.156, 0.089, ...] (384 floats)
        """
        if not text or not text.strip():
            return [0.0] * self.dimension
        
        cache_key = self._get_cache_key(text)
        
        # Check cache
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key].tolist()
        
        # Generate embedding
        embedding = self.model.encode(
            text,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
            show_progress_bar=False,
        )
        
        # Cache result
        if use_cache:
            self._manage_cache()
            self._cache[cache_key] = embedding
        
        return embedding.tolist()
    
    def embed_batch(
        self, 
        texts: List[str], 
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            show_progress: Show progress bar
            
        Returns:
            List of embedding vectors
            
        Example:
            embeddings = service.embed_batch([
                "chest pain",
                "cardiac discomfort", 
                "heart problems"
            ])
        """
        if not texts:
            return []
        
        # Filter empty texts
        valid_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        valid_texts = [texts[i] for i in valid_indices]
        
        if not valid_texts:
            return [[0.0] * self.dimension] * len(texts)
        
        # Generate embeddings
        embeddings = self.model.encode(
            valid_texts,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=show_progress,
        )
        
        # Map back to original indices
        result = [[0.0] * self.dimension] * len(texts)
        for i, idx in enumerate(valid_indices):
            result[idx] = embeddings[i].tolist()
            # Cache
            cache_key = self._get_cache_key(valid_texts[i])
            self._cache[cache_key] = embeddings[i]
        
        return result
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts (0-1).
        
        Uses cosine similarity of normalized embeddings.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0-1, higher = more similar)
            
        Example:
            sim = service.similarity("chest pain", "cardiac discomfort")
            # Returns: ~0.78 (high similarity)
            
            sim = service.similarity("chest pain", "headache")  
            # Returns: ~0.35 (lower similarity)
        """
        emb1 = self.model.encode(text1, normalize_embeddings=True)
        emb2 = self.model.encode(text2, normalize_embeddings=True)
        return float(np.dot(emb1, emb2))
    
    def find_most_similar(
        self,
        query: str,
        candidates: List[str],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[Dict]:
        """
        Find most similar texts from candidates.
        
        Args:
            query: Query text
            candidates: List of candidate texts
            top_k: Number of results to return
            threshold: Minimum similarity score
            
        Returns:
            List of dicts with text, score, and index
            
        Example:
            results = service.find_most_similar(
                "heart attack symptoms",
                ["chest pain", "headache", "cardiac arrest", "fever"]
            )
            # Returns: [
            #   {"text": "cardiac arrest", "score": 0.82, "index": 2},
            #   {"text": "chest pain", "score": 0.76, "index": 0},
            # ]
        """
        if not candidates:
            return []
        
        # Embed query
        query_emb = self.model.encode(query, normalize_embeddings=True)
        
        # Embed candidates
        candidate_embs = self.model.encode(
            candidates, 
            normalize_embeddings=True,
            show_progress_bar=len(candidates) > 100,
        )
        
        # Calculate similarities
        similarities = np.dot(candidate_embs, query_emb)
        
        # Get top-k
        results = []
        for i, score in enumerate(similarities):
            if score >= threshold:
                results.append({
                    "text": candidates[i],
                    "score": float(score),
                    "index": i,
                })
        
        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:top_k]
    
    def compute_similarity_matrix(
        self, 
        texts: List[str]
    ) -> np.ndarray:
        """
        Compute pairwise similarity matrix for texts.
        
        Args:
            texts: List of texts
            
        Returns:
            NxN similarity matrix
        """
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return np.dot(embeddings, embeddings.T)
    
    def get_model_info(self) -> Dict:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "device": str(self.model.device),
            "cache_size": len(self._cache),
            "max_cache_size": self._cache_size,
        }


# =============================================================================
# STANDALONE FUNCTIONS FOR QUICK USE
# =============================================================================

def embed(text: str) -> List[float]:
    """Quick embedding for single text."""
    return EmbeddingService.get_instance().embed_text(text)


def similarity(text1: str, text2: str) -> float:
    """Quick similarity calculation."""
    return EmbeddingService.get_instance().similarity(text1, text2)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    # Test the service
    print("Testing EmbeddingService...")
    
    service = EmbeddingService.get_instance()
    print(f"Model info: {service.get_model_info()}")
    
    # Test semantic similarity
    test_pairs = [
        ("chest pain", "cardiac discomfort"),
        ("chest pain", "heart problems"),
        ("chest pain", "headache"),
        ("blood pressure medication", "hypertension drugs"),
        ("blood pressure medication", "cooking recipes"),
    ]
    
    print("\n🧪 Semantic Similarity Tests:")
    for t1, t2 in test_pairs:
        sim = service.similarity(t1, t2)
        print(f"  '{t1}' ↔ '{t2}': {sim:.3f}")
    
    # Test find_most_similar
    print("\n🔍 Find Most Similar:")
    results = service.find_most_similar(
        "heart attack symptoms",
        [
            "chest pain and discomfort",
            "headache and fever",
            "cardiac arrest warning signs",
            "stomach ache",
            "shortness of breath",
            "arm numbness",
        ],
        top_k=3,
    )
    for r in results:
        print(f"  [{r['score']:.3f}] {r['text']}")
