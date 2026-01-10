"""
Vector Store Manager for HeartGuard Medical Knowledge Base

Wraps ChromaDB and handles embedding generation using sentence-transformers.
This is the core semantic search layer.
OPTIMIZED: GPU Pre-computation + Batch Insertion.
"""

import logging
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
import os
import torch
from tqdm import tqdm  # Progress bar

# Import the MedicalDocument schema
from rag.data_sources.models import MedicalDocument

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """
    Manages the ChromaDB vector store for medical documents.
    OPTIMIZED: GPU Pre-computation + Batch Insertion.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(VectorStoreManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, db_path: str = "data/chroma_db", collection_name: str = "heart_guard_docs"):
        """
        Initialize the vector store manager.
        
        Args:
            db_path: Path to ChromaDB persistence directory
            collection_name: Name of the collection to use
        """
        # Fix: Proper Singleton check using instance attribute
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # Ensure directory exists
        os.makedirs(db_path, exist_ok=True)
        
        self.db_path = db_path
        self.collection_name = collection_name
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=db_path)
        
        # --- GPU SETUP ---
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"\n⚡ VECTOR ENGINE: {self.device.upper()} DETECTED ⚡")
        
        if self.device == "cpu":
            print("[WARNING] Running on CPU. This will be slow.")
            print("    Run: pip install torch --index-url https://download.pytorch.org/whl/cu121")
        
        # We use the raw SentenceTransformer model for pre-computation (It's faster)
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device=self.device)
        
        # Standard Chroma embedding function (for queries later)
        self.chroma_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
            device=self.device
        )
        
        # Get or create collection with cosine similarity
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.chroma_ef,
            metadata={"hnsw:space": "cosine"}  # Cosine similarity for semantic search
        )
        
        self._initialized = True
        logger.info(f"[OK] Vector Store initialized at {db_path} (Collection: {collection_name}, Count: {self.collection.count()})")

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
        2. I/O Phase: Write data to ChromaDB (Max I/O)
        
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
        print(f"   [Phase 2] Saving to Disk (ChromaDB)...")
        
        # Prepare Metadata
        ids = [doc.document_id for doc in documents]
        metadatas = []
        for doc in documents:
            metadatas.append({
                "title": doc.title or "",
                "source": str(doc.source.value) if hasattr(doc.source, 'value') else str(doc.source),
                "tier": str(doc.tier.value) if hasattr(doc.tier, 'value') else str(doc.tier),
                "confidence": float(doc.confidence_score),
                "url": doc.source_url or ""
            })

        # Insert in chunks to avoid RAM issues
        write_batch = 5000
        
        with tqdm(total=total, desc="Writing DB", unit="docs") as pbar:
            for i in range(0, total, write_batch):
                end = i + write_batch
                self.collection.add(
                    ids=ids[i:end],
                    embeddings=embeddings[i:end].tolist(),  # Pass pre-computed vectors!
                    documents=texts[i:end],
                    metadatas=metadatas[i:end]
                )
                pbar.update(len(ids[i:end]))
                
        print(f"\n✅ COMPLETE. Indexed {total} documents.")
        logger.info(f"[OK] Ingestion complete. {total}/{total} documents indexed.")
        return total

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
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
            )
            
            # Format results nicely
            formatted_results = []
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        "id": results['ids'][0][i],
                        "text": results['documents'][0][i] if results['documents'] else "",
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results.get('distances') else 0.0
                    })
                    
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        return {
            "db_path": self.db_path,
            "collection_name": self.collection_name,
            "document_count": self.collection.count(),
        }

    def clear(self):
        """Clear all documents from the collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.chroma_ef,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Cleared collection: {self.collection_name}")

    def delete_collection(self):
        """
        Deletes the entire collection and re-creates it empty.
        Used for resetting the database or clearing corrupted data.
        """
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"[WARNING] Collection '{self.collection_name}' deleted.")
            
            # Re-create immediately so the object remains valid
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.chroma_ef,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"[OK] Collection '{self.collection_name}' re-created (empty).")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise e


# Convenience function
def get_vector_store_manager(**kwargs) -> VectorStoreManager:
    """Get the default vector store manager instance."""
    return VectorStoreManager.get_instance(**kwargs)
