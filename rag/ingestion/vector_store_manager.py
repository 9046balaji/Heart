"""
Vector Store Manager for HeartGuard Medical Knowledge Base

Wraps PostgreSQL/pgvector and handles embedding generation using sentence-transformers.
This is the core semantic search layer.
OPTIMIZED: GPU Pre-computation + Batch Insertion.

Migration Note: Previously used ChromaDB, now uses PostgreSQL with pgvector extension.
"""

import logging
from typing import List, Dict, Any
import os
import torch
from tqdm import tqdm  # Progress bar

# Import the MedicalDocument schema
from rag.data_sources.models import MedicalDocument

# Import pgvector store
try:
    from rag.pgvector_store import PgVectorStore
    PGVECTOR_AVAILABLE = True
except ImportError:
    PgVectorStore = None
    PGVECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """
    Manages the PostgreSQL pgvector store for medical documents.
    OPTIMIZED: GPU Pre-computation + Batch Insertion.
    
    Migration Note: Replaced ChromaDB with PostgreSQL/pgvector for better
    integration with the HeartGuard PostgreSQL database.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(VectorStoreManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, db_path: str = None, collection_name: str = "medical_knowledge"):
        """
        Initialize the vector store manager.
        
        Args:
            db_path: Deprecated - PostgreSQL uses DATABASE_URL environment variable
            collection_name: Name of the collection/table to use
        """
        # Fix: Proper Singleton check using instance attribute
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.collection_name = collection_name
        
        # --- GPU SETUP ---
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"\n⚡ VECTOR ENGINE: {self.device.upper()} DETECTED ⚡")
        
        if self.device == "cpu":
            print("[WARNING] Running on CPU. This will be slow.")
            print("    Run: pip install torch --index-url https://download.pytorch.org/whl/cu121")
        
        # We use the raw SentenceTransformer model for pre-computation (It's faster)
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device=self.device)
        
        # Initialize PostgreSQL pgvector store
        if not PGVECTOR_AVAILABLE:
            raise ImportError("PgVectorStore not available. Check rag/pgvector_store.py")
        
        self.store = PgVectorStore()
        self._initialized = True
        
        # Get document count for logging
        stats = self.store.get_collection_stats()
        doc_count = stats.get(collection_name, 0)
        logger.info(f"[OK] Vector Store Manager initialized with PostgreSQL (Collection: {collection_name}, Count: {doc_count})")

    @classmethod
    def get_instance(cls, **kwargs) -> "VectorStoreManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    def insert_documents(self, documents: List[MedicalDocument], batch_size: int = 3000) -> int:
        """
        Two-Phase Ingestion:
        1. GPU Phase: Compute ALL embeddings at once (Max Throughput)
        2. I/O Phase: Write data to PostgreSQL (Max I/O)
        
        Args:
            documents: List of MedicalDocument objects
            batch_size: Batch size for GPU embedding (default 3000 for GPU memory)
            
        Returns:
            Number of documents successfully inserted
        """
        total = len(documents)
        print(f"\n🚀 STARTING ULTRA-FAST INGESTION ({total} docs)")
        
        # --- PHASE 1: GPU PRE-COMPUTE ---
        print(f"   [Phase 1] Generating Embeddings on {self.device.upper()}...")
        texts = [doc.content for doc in documents]
        
        # Compute embeddings with progress bar
        embeddings = self.model.encode(
            texts, 
            batch_size=batch_size, 
            show_progress_bar=True, 
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        # --- PHASE 2: DATABASE WRITE ---
        print(f"   [Phase 2] Saving to PostgreSQL...")
        
        # Insert using PgVectorStore batch method
        write_batch = 1000  # Smaller batches for PostgreSQL
        inserted = 0
        
        with tqdm(total=total, desc="Writing DB", unit="docs") as pbar:
            for i in range(0, total, write_batch):
                end = min(i + write_batch, total)
                batch_docs = documents[i:end]
                batch_embeddings = embeddings[i:end]
                
                for j, doc in enumerate(batch_docs):
                    try:
                        metadata = {
                            "title": doc.title or "",
                            "source": str(doc.source.value) if hasattr(doc.source, 'value') else str(doc.source),
                            "tier": str(doc.tier.value) if hasattr(doc.tier, 'value') else str(doc.tier),
                            "confidence": float(doc.confidence_score),
                            "url": doc.source_url or ""
                        }
                        
                        self.store.add_medical_document(
                            doc_id=doc.document_id,
                            content=doc.content,
                            metadata=metadata,
                            embedding=batch_embeddings[j].tolist()
                        )
                        inserted += 1
                    except Exception as e:
                        logger.warning(f"Failed to insert document {doc.document_id}: {e}")
                
                pbar.update(len(batch_docs))
                
        print(f"\n✅ COMPLETE. Indexed {inserted}/{total} documents.")
        logger.info(f"[OK] Ingestion complete. {inserted}/{total} documents indexed.")
        return inserted

    def search(self, query: str, top_k: int = 3, min_confidence: float = 0.0) -> List[Dict[str, Any]]:
        """
        Perform semantic search for relevant documents.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            min_confidence: Minimum confidence score filter (optional)
            
        Returns:
            List of matching documents with metadata
        """
        if not query.strip():
            return []
            
        try:
            # Use PgVectorStore search
            results = self.store.search_medical_knowledge(
                query=query,
                top_k=top_k
            )
            
            # Filter by confidence if specified
            if min_confidence > 0:
                results = [r for r in results if r.get('metadata', {}).get('confidence', 0) >= min_confidence]
            
            # Format results to match expected output format
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "id": r.get('id'),
                    "text": r.get('content', ''),
                    "metadata": r.get('metadata', {}),
                    "distance": 1.0 - r.get('score', 0)  # Convert similarity to distance
                })
                    
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        stats = self.store.get_collection_stats()
        return {
            "db_path": "PostgreSQL (via DATABASE_URL)",
            "collection_name": self.collection_name,
            "document_count": stats.get(self.collection_name, 0),
        }

    def clear(self):
        """Clear all documents from the collection."""
        try:
            # For PostgreSQL, we truncate the relevant table
            self.store._execute_sql(f"TRUNCATE TABLE vector_{self.collection_name} RESTART IDENTITY CASCADE")
            logger.info(f"Cleared collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            raise e

    def delete_collection(self):
        """
        Deletes all documents from the collection.
        Used for resetting the database or clearing corrupted data.
        """
        try:
            self.clear()
            logger.info(f"[WARNING] Collection '{self.collection_name}' cleared.")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise e


# Convenience function
def get_vector_store_manager(**kwargs) -> VectorStoreManager:
    """Get the default vector store manager instance."""
    return VectorStoreManager.get_instance(**kwargs)

