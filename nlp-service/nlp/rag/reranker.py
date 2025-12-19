"""
Cross-Encoder Reranker for RAG Pipeline.

Rerank retrieved documents using cross-encoder for higher accuracy
than bi-encoder similarity search.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import sentence-transformers for cross-encoder
try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    CROSS_ENCODER_AVAILABLE = False
    logger.warning("sentence-transformers not available for cross-encoder reranking.")


class MedicalReranker:
    """
    Rerank retrieved documents using cross-encoder.
    
    Cross-encoders are more accurate than bi-encoders for ranking
    but slower, so we use them only on top-k results.
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize medical reranker.
        
        Args:
            model_name: Cross-encoder model name
        """
        if not CROSS_ENCODER_AVAILABLE:
            logger.warning("Cross-encoder reranking disabled due to missing dependencies.")
            self.model = None
            return
            
        try:
            self.model = CrossEncoder(model_name)
            logger.info(f"Medical reranker initialized with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize cross-encoder: {e}")
            self.model = None
    
    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Rerank documents by relevance to query.
        
        Args:
            query: User query
            documents: List of retrieved docs with 'content' field
            top_k: Number of top results to return
            
        Returns:
            Reranked documents with updated scores
        """
        # If no model or no documents, return early
        if not self.model or not documents:
            return documents[:top_k] if documents else []
        
        try:
            # Create query-document pairs
            pairs = [(query, doc["content"][:512]) for doc in documents]
            
            # Score with cross-encoder
            scores = self.model.predict(pairs)
            
            # Add scores and sort
            for doc, score in zip(documents, scores):
                doc["rerank_score"] = float(score)
            
            # Sort by rerank score (descending) and return top-k
            return sorted(
                documents, 
                key=lambda x: x["rerank_score"], 
                reverse=True
            )[:top_k]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Return original documents truncated to top_k
            return documents[:top_k]
    
    def is_available(self) -> bool:
        """Check if reranker is available."""
        return self.model is not None