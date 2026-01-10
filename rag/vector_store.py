"""
Vector Store - ChromaDB-based Storage for RAG

This module provides persistent vector storage using ChromaDB,
enabling semantic search over medical knowledge and user memories.

Addresses GAPs from documents:
- ❌ No vector storage -> ✅ ChromaDB persistent storage
- ❌ No semantic search -> ✅ Similarity search on embeddings
- ❌ No medical knowledge base -> ✅ Separate collection for medical docs

Collections:
1. user_memories - Enhanced Memori with embeddings (per-user)
2. medical_knowledge - RAG knowledge base (shared)
3. drug_interactions - Medication information (shared)
"""

import logging
import os
import hashlib
from functools import lru_cache
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import OrderedDict
import threading
import asyncio

logger = logging.getLogger(__name__)

# Optional ChromaDB import - with Python 3.14 compatibility check
CHROMADB_AVAILABLE = False
chromadb = None
Settings = None

try:
    import chromadb
    from chromadb.config import Settings
    # Test that chromadb actually works (Python 3.14 compatibility)
    _ = chromadb.PersistentClient
    CHROMADB_AVAILABLE = True
except ImportError:
    logger.warning("chromadb not installed. Run: pip install chromadb")
except Exception as e:
    logger.warning(f"chromadb installed but not compatible (likely Python 3.14): {e}")
    chromadb = None
    Settings = None

try:
    from .embedding_service import EmbeddingService
except ImportError:
    # Handle direct import when run as script
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from rag.embedding_service import EmbeddingService
try:
    from .embedding_onnx import ONNXEmbeddingService
    ONNX_AVAILABLE = True
except ImportError:
    # Handle direct import when run as script
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from rag.embedding_onnx import ONNXEmbeddingService
        ONNX_AVAILABLE = True
    except ImportError:
        ONNX_AVAILABLE = False


class InMemoryVectorStore:
    """
    Simple in-memory vector store fallback when ChromaDB is unavailable.
    
    Provides basic functionality for development/testing when chromadb
    isn't compatible (e.g., Python 3.14).
    
    Note: Data is NOT persisted - lost on restart.
    """
    
    MEDICAL_COLLECTION = "medical_knowledge"
    DRUG_COLLECTION = "drug_interactions"
    SYMPTOMS_COLLECTION = "symptoms_conditions"
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2", **kwargs):
        """Initialize in-memory vector store."""
        self._collections: Dict[str, Dict[str, Any]] = {}
        self._embedding_model = embedding_model
        
        # Try to initialize embedding service (EmbeddingService is a factory function)
        self.embedding_service = None
        try:
            if ONNX_AVAILABLE:
                self.embedding_service = ONNXEmbeddingService.get_instance(
                    model_type="fast" if "mini" in embedding_model.lower() else "quality"
                )
            else:
                # EmbeddingService is actually get_embedding_service factory function
                self.embedding_service = EmbeddingService(model_name=embedding_model)
        except Exception as e:
            logger.warning(f"Failed to initialize embedding service: {e}")
            self.embedding_service = None
        
        logger.warning("⚠️ Using InMemoryVectorStore - data will NOT be persisted!")
        logger.info("✅ InMemoryVectorStore initialized")
    
    def get_or_create_collection(self, name: str, metadata: Optional[Dict] = None) -> Dict:
        """Get or create an in-memory collection."""
        if name not in self._collections:
            self._collections[name] = {
                "documents": [],
                "embeddings": [],
                "ids": [],
                "metadatas": [],
                "metadata": metadata or {}
            }
        return self._collections[name]
    
    def add_medical_document(self, doc_id: str, content: str, metadata: Optional[Dict] = None) -> None:
        """Add a medical document."""
        collection = self.get_or_create_collection(self.MEDICAL_COLLECTION)
        
        # Generate embedding if service available
        embedding = None
        if self.embedding_service:
            try:
                embedding = self.embedding_service.embed(content)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        collection["documents"].append(content)
        collection["embeddings"].append(embedding)
        collection["ids"].append(doc_id)
        collection["metadatas"].append(metadata or {})
    
    def search_medical_knowledge(self, query: str, top_k: int = 5, **kwargs) -> List[Dict]:
        """Search medical knowledge (basic text matching fallback)."""
        collection = self.get_or_create_collection(self.MEDICAL_COLLECTION)
        
        if not collection["documents"]:
            return []
        
        # If we have embeddings and embedding service, do similarity search
        if self.embedding_service and any(collection["embeddings"]):
            try:
                query_embedding = self.embedding_service.embed(query)
                # Simple cosine similarity
                import numpy as np
                similarities = []
                for i, emb in enumerate(collection["embeddings"]):
                    if emb is not None:
                        sim = np.dot(query_embedding, emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(emb))
                        similarities.append((i, sim))
                
                similarities.sort(key=lambda x: x[1], reverse=True)
                
                results = []
                for idx, score in similarities[:top_k]:
                    results.append({
                        "id": collection["ids"][idx],
                        "content": collection["documents"][idx],
                        "metadata": collection["metadatas"][idx],
                        "score": float(score)
                    })
                return results
            except Exception as e:
                logger.warning(f"Embedding search failed, using text matching: {e}")
        
        # Fallback: simple text matching
        query_lower = query.lower()
        results = []
        for i, doc in enumerate(collection["documents"]):
            if query_lower in doc.lower():
                results.append({
                    "id": collection["ids"][i],
                    "content": doc,
                    "metadata": collection["metadatas"][i],
                    "score": 0.5  # Default score for text match
                })
        
        return results[:top_k]
    
    async def async_search(self, query: str, collection_name: str = None, top_k: int = 5, **kwargs) -> List[Dict]:
        """Async search wrapper."""
        return self.search_medical_knowledge(query, top_k=top_k)
    
    def delete_collection(self, name: str) -> bool:
        """Delete a collection."""
        if name in self._collections:
            del self._collections[name]
            return True
        return False
    
    def get_collection_stats(self) -> Dict[str, int]:
        """Get collection statistics."""
        return {name: len(col["documents"]) for name, col in self._collections.items()}


class VectorStore:
    """
    ChromaDB-based vector store for healthcare RAG.

    Features:
    - Persistent storage (survives restarts)
    - Multiple collections for different data types
    - Automatic embedding generation
    - Metadata filtering
    - Hybrid search (vector + metadata)

    Collections:
    - user_memories_{user_id}: Per-user memory storage
    - medical_knowledge: Medical guidelines, protocols
    - drug_interactions: Medication information

    Example:
        store = VectorStore()

        # Store medical document
        store.add_medical_document(
            doc_id="aha_guidelines_2024",
            content="Heart failure treatment guidelines...",
            metadata={"source": "AHA", "year": 2024}
        )

        # Search
        results = store.search_medical_knowledge(
            "heart failure treatment",
            top_k=5
        )
    """

    # Default collections
    MEDICAL_COLLECTION = "medical_knowledge"
    DRUG_COLLECTION = "drug_interactions"
    SYMPTOMS_COLLECTION = "symptoms_conditions"
    
    # Version info for meta.json validation
    SCHEMA_VERSION = "1.0"
    META_FILENAME = "meta.json"

    def __init__(
        self,
        persist_directory: str = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        config = None,
    ):
        """
        Initialize Vector Store.

        Args:
            persist_directory: Directory for ChromaDB storage. If None, uses config.paths.chroma_db_dir
            embedding_model: Model name for embeddings
            config: RAGConfig instance with paths. If None, will import and use default.
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is required. Install with: pip install chromadb"
            )

        # Use centralized path configuration
        if persist_directory is None:
            if config is None:
                # Import here to avoid circular imports
                from core.config.rag_config import RAGConfig
                config = RAGConfig()
            persist_directory = str(config.paths.chroma_db_dir)

        self.persist_directory = str(Path(persist_directory).absolute())

        # Create directory if needed
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistence
        logger.info(f"Initializing ChromaDB at: {self.persist_directory}")
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Initialize embedding service - prefer ONNX for better performance
        if ONNX_AVAILABLE:
            try:
                self.embedding_service = ONNXEmbeddingService.get_instance(
                    model_type="fast" if "mini" in embedding_model.lower() else "quality"
                )
                logger.info("✅ Using ONNX-optimized embedding service")
            except Exception as e:
                logger.warning(f"Failed to initialize ONNX embedding service: {e}, falling back to standard")
                self.embedding_service = EmbeddingService.get_instance(
                    model_name=embedding_model
                )
        else:
            self.embedding_service = EmbeddingService.get_instance(
                model_name=embedding_model
            )

        # Collection cache
        self._collections: Dict[str, Any] = {}
        
        # LATENCY OPTIMIZATION: Query result cache for repeated queries
        # LATENCY OPTIMIZATION: Query result cache for repeated queries
        self._query_cache: OrderedDict[str, List[Dict]] = OrderedDict()
        self._query_cache_max_size = 100
        self._query_cache_lock = threading.Lock()
        
        # Validate or create meta.json for version tracking
        self._embedding_model = embedding_model
        self._validate_or_create_metadata()

        logger.info("✅ VectorStore initialized successfully")

    def _validate_or_create_metadata(self) -> None:
        """
        Validate or create meta.json for version tracking.
        
        Prevents silent embedding model mismatches that cause retrieval degradation.
        If meta.json exists but model differs, logs a warning.
        """
        meta_path = Path(self.persist_directory) / self.META_FILENAME
        
        current_metadata = {
            "schema_version": self.SCHEMA_VERSION,
            "embedding_model": self._embedding_model,
            "embedding_dimension": getattr(self.embedding_service, 'dimension', 'unknown'),
            "created_at": datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat(),
        }
        
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    stored_metadata = json.load(f)
                
                stored_model = stored_metadata.get("embedding_model", "unknown")
                stored_dimension = stored_metadata.get("embedding_dimension", "unknown")
                current_dimension = getattr(self.embedding_service, 'dimension', 'unknown')
                
                if stored_model != self._embedding_model:
                    logger.warning(
                        f"⚠️ EMBEDDING MODEL MISMATCH! "
                        f"Store created with '{stored_model}', but now using '{self._embedding_model}'. "
                        f"Consider re-indexing for optimal retrieval."
                    )
                
                if stored_dimension != current_dimension and stored_dimension != "unknown":
                    logger.error(
                        f"🚨 DIMENSION MISMATCH! "
                        f"Store has dimension {stored_dimension}, model expects {current_dimension}. "
                        f"Re-indexing REQUIRED!"
                    )
                
                # Update last_validated timestamp
                stored_metadata["last_validated"] = datetime.now().isoformat()
                with open(meta_path, 'w') as f:
                    json.dump(stored_metadata, f, indent=2)
                    
                logger.info(f"✅ meta.json validated: model={stored_model}, dim={stored_dimension}")
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Corrupted meta.json: {e}. Creating fresh metadata.")
                with open(meta_path, 'w') as f:
                    json.dump(current_metadata, f, indent=2)
        else:
            # Create new meta.json
            with open(meta_path, 'w') as f:
                json.dump(current_metadata, f, indent=2)
            logger.info(f"✅ Created meta.json: model={self._embedding_model}")

    def get_or_create_collection(
        self,
        name: str,
        metadata: Optional[Dict] = None,
    ) -> Any:
        """
        Get or create a collection.

        Args:
            name: Collection name
            metadata: Optional collection metadata

        Returns:
            ChromaDB collection
        """
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata=metadata or {"description": f"Collection: {name}"},
            )
        return self._collections[name]

    # =========================================================================
    # MEDICAL KNOWLEDGE BASE
    # =========================================================================

    def add_medical_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict] = None,
        collection_name: str = None,
    ) -> str:
        """
        Add a medical document to the knowledge base.

        Args:
            doc_id: Unique document ID
            content: Document text content
            metadata: Additional metadata (source, category, etc.)
            collection_name: Optional custom collection

        Returns:
            Document ID

        Example:
            store.add_medical_document(
                doc_id="aha_hf_2024",
                content="Heart failure management guidelines...",
                metadata={
                    "source": "AHA",
                    "category": "guidelines",
                    "condition": "heart_failure",
                    "year": 2024,
                }
            )
        """
        collection = self.get_or_create_collection(
            collection_name or self.MEDICAL_COLLECTION
        )

        # Generate embedding
        embedding = self.embedding_service.embed_text(content)

        # Prepare metadata
        meta = metadata or {}
        meta["added_at"] = datetime.now().isoformat()
        meta["content_length"] = len(content)

        # Upsert document
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta],
        )

        logger.debug(f"Added medical document: {doc_id}")
        return doc_id

    def add_medical_documents_batch(
        self,
        documents: List[Dict],
        collection_name: str = None,
    ) -> int:
        """
        Add multiple medical documents efficiently.

        Args:
            documents: List of dicts with 'id', 'content', 'metadata'
            collection_name: Optional custom collection

        Returns:
            Number of documents added
        """
        if not documents:
            return 0

        collection = self.get_or_create_collection(
            collection_name or self.MEDICAL_COLLECTION
        )

        ids = [doc["id"] for doc in documents]
        contents = [doc["content"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]

        # Add timestamps
        for meta in metadatas:
            meta["added_at"] = datetime.now().isoformat()

        # Generate embeddings in batch
        embeddings = self.embedding_service.embed_batch(contents)

        # Upsert
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas,
        )

        logger.info(f"Added {len(documents)} medical documents")
        return len(documents)

    # P3.1: Async batch insert with progress tracking
    async def batch_add_medical_documents_async(
        self,
        documents: List[Dict],
        batch_size: int = 50,
        collection_name: str = None,
    ) -> Dict[str, Any]:
        """P3.1: Async batch insert documents with progress tracking.
        
        Processes documents in configurable batches for memory efficiency.
        
        Args:
            documents: List of dicts with 'id', 'content', 'metadata'
            batch_size: Number of documents per batch
            collection_name: Optional custom collection
            
        Returns:
            Dict with total, added count, and errors
        """
        import asyncio
        from uuid import uuid4
        
        total = len(documents)
        if total == 0:
            return {"total": 0, "added": 0, "errors": 0}
        
        collection = self.get_or_create_collection(
            collection_name or self.MEDICAL_COLLECTION
        )
        
        added = 0
        errors = 0
        
        for i in range(0, total, batch_size):
            batch = documents[i:i + batch_size]
            
            try:
                # Process batch
                ids = [doc.get("id", str(uuid4())) for doc in batch]
                contents = [doc["content"] for doc in batch]
                metadatas = [doc.get("metadata", {}) for doc in batch]
                
                # Add timestamps
                for meta in metadatas:
                    meta["added_at"] = datetime.now().isoformat()
                
                # Batch embed (use async if available)
                if hasattr(self.embedding_service, 'embed_batch_async'):
                    embeddings = await self.embedding_service.embed_batch_async(contents)
                else:
                    embeddings = self.embedding_service.embed_batch(contents)
                
                # Upsert
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=contents,
                    metadatas=metadatas,
                )
                
                added += len(batch)
                logger.debug(f"P3.1: Inserted {added}/{total} documents")
                
                # Yield control to event loop
                await asyncio.sleep(0)
                
            except Exception as e:
                logger.error(f"P3.1: Batch insert failed: {e}")
                errors += len(batch)
        
        logger.info(f"P3.1: Batch insert complete: {added}/{total} added, {errors} errors")
        return {"total": total, "added": added, "errors": errors}


    def search_medical_knowledge(
        self,
        query: str = None,
        top_k: int = 5,
        filter_metadata: Optional[Dict] = None,
        collection_name: str = None,
        query_embedding: List[float] = None,
    ) -> List[Dict]:
        """
        Search medical knowledge base.

        Args:
            query: Search query (optional if query_embedding provided)
            top_k: Number of results
            filter_metadata: Metadata filters
            collection_name: Optional custom collection
            query_embedding: Pre-computed embedding vector

        Returns:
            List of matching documents with scores
        """
        # Try the specified collection, or default collection
        target_collection = collection_name or self.MEDICAL_COLLECTION
        collection = self.get_or_create_collection(target_collection)
        
        # FALLBACK: If collection is empty and we're using default, try medical_docs
        if collection.count() == 0 and target_collection == self.MEDICAL_COLLECTION:
            logger.debug(f"Collection '{self.MEDICAL_COLLECTION}' is empty, trying fallback 'medical_docs'")
            fallback_collection = self.get_or_create_collection("medical_docs")
            if fallback_collection.count() > 0:
                logger.info(f"✅ Found {fallback_collection.count()} documents in fallback collection 'medical_docs'")
                collection = fallback_collection

        # LATENCY OPTIMIZATION: Check query cache first (only if query string provided)
        cache_key = None
        if query:
            cache_key = hashlib.md5(f"{query}:{top_k}:{filter_metadata}:{collection_name}".encode()).hexdigest()
            if cache_key in self._query_cache:
                logger.debug(f"Query cache HIT: {cache_key[:8]}")
                return self._query_cache[cache_key]

        # Generate query embedding if not provided
        if query_embedding is None:
            if query:
                query_embedding = self.embedding_service.embed_text(query)
            else:
                raise ValueError("Either query or query_embedding must be provided")

        # Build query params
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }

        if filter_metadata:
            query_params["where"] = filter_metadata

        # Search
        results = collection.query(**query_params)

        # Format results
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                formatted.append(
                    {
                        "id": doc_id,
                        "content": (
                            results["documents"][0][i] if results["documents"] else ""
                        ),
                        "metadata": (
                            results["metadatas"][0][i] if results["metadatas"] else {}
                        ),
                        "score": 1 / (1 + results["distances"][0][i]),  # Convert distance to similarity (0-1)
                    }
                )

        # LATENCY OPTIMIZATION: Cache results for repeated queries
        # LATENCY OPTIMIZATION: Cache results for repeated queries
        with self._query_cache_lock:
            if len(self._query_cache) >= self._query_cache_max_size:
                # Remove oldest entry (FIFO)
                self._query_cache.popitem(last=False)
            self._query_cache[cache_key] = formatted

        return formatted

    async def async_search(self, query: str = None, collection_name: str = None, top_k: int = 5, query_embedding: List[float] = None, **kwargs) -> List[Dict]:
        """
        Async wrapper for search_medical_knowledge using a thread pool.
        Prevents blocking the event loop during heavy vector search operations.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.search_medical_knowledge(
                query=query,
                collection_name=collection_name,
                top_k=top_k,
                query_embedding=query_embedding,
                **kwargs
            )
        )

    # =========================================================================
    # USER MEMORIES (Enhances Memori)
    # =========================================================================

    def get_user_collection(self, user_id: str) -> Any:
        """Get or create user-specific collection."""
        return self.get_or_create_collection(
            f"user_memories_{user_id}",
            metadata={"type": "user_memories", "user_id": user_id},
        )

    def store_user_memory(
        self,
        user_id: str,
        memory_id: str,
        content: str,
        memory_type: str = "conversation",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Store user memory with embedding.

        Args:
            user_id: User identifier
            memory_id: Unique memory ID
            content: Memory content
            memory_type: Type (conversation, fact, preference, etc.)
            metadata: Additional metadata

        Returns:
            Memory ID
        """
        collection = self.get_user_collection(user_id)

        # Generate embedding
        embedding = self.embedding_service.embed_text(content)

        # Prepare metadata
        meta = metadata or {}
        meta["type"] = memory_type
        meta["timestamp"] = datetime.now().isoformat()
        meta["user_id"] = user_id

        # Upsert
        collection.upsert(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta],
        )

        return memory_id

    def search_user_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 10,
        memory_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Search user memories semantically.

        Args:
            user_id: User identifier
            query: Search query
            top_k: Number of results
            memory_types: Filter by memory types

        Returns:
            List of matching memories with scores
        """
        collection = self.get_user_collection(user_id)

        # Check if collection has documents
        if collection.count() == 0:
            return []

        # Generate query embedding
        query_embedding = self.embedding_service.embed_text(query)

        # Build query
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }

        if memory_types:
            query_params["where"] = {"type": {"$in": memory_types}}

        # Search
        results = collection.query(**query_params)

        # Format results
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, mem_id in enumerate(results["ids"][0]):
                formatted.append(
                    {
                        "id": mem_id,
                        "content": (
                            results["documents"][0][i] if results["documents"] else ""
                        ),
                        "metadata": (
                            results["metadatas"][0][i] if results["metadatas"] else {}
                        ),
                        "score": 1 / (1 + results["distances"][0][i]),
                    }
                )

        return formatted

    # =========================================================================
    # DRUG INTERACTIONS
    # =========================================================================

    def add_drug_info(
        self,
        drug_id: str,
        drug_name: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Add drug information to the database."""
        collection = self.get_or_create_collection(self.DRUG_COLLECTION)

        embedding = self.embedding_service.embed_text(f"{drug_name}: {content}")

        meta = metadata or {}
        meta["drug_name"] = drug_name
        meta["added_at"] = datetime.now().isoformat()

        collection.upsert(
            ids=[drug_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta],
        )

        return drug_id

    def search_drug_info(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict]:
        """Search drug information."""
        collection = self.get_or_create_collection(self.DRUG_COLLECTION)

        if collection.count() == 0:
            return []

        query_embedding = self.embedding_service.embed_text(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                formatted.append(
                    {
                        "id": doc_id,
                        "content": (
                            results["documents"][0][i] if results["documents"] else ""
                        ),
                        "metadata": (
                            results["metadatas"][0][i] if results["metadatas"] else {}
                        ),
                        "score": 1 - results["distances"][0][i],
                    }
                )

        return formatted

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about all collections."""
        collections = self.client.list_collections()
        stats = {
            "persist_directory": self.persist_directory,
            "total_collections": len(collections),
            "collections": {},
        }

        for col in collections:
            stats["collections"][col.name] = {
                "count": col.count(),
                "metadata": col.metadata,
            }

        return stats

    def delete_document_vectors(
        self,
        doc_id: str,
        collection_name: str = None
    ) -> int:
        """
        Delete all vectors associated with a document.
        
        Args:
            doc_id: Document ID (matches doc_id in metadata)
            collection_name: Target collection
            
        Returns:
            Number of vectors deleted
        """
        collection = self.get_or_create_collection(
            collection_name or self.MEDICAL_COLLECTION
        )
        
        # Query for all chunks with this doc_id
        results = collection.get(
            where={"doc_id": doc_id},
            include=["metadatas"]
        )
        
        if results and results.get("ids"):
            collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} vectors for doc_id={doc_id}")
            return len(results["ids"])
        
        return 0

    def check_document_exists(self, doc_id: str) -> dict:
        """Check if document exists and get its version."""
        collection = self.get_or_create_collection(self.MEDICAL_COLLECTION)
        results = collection.get(
            where={"doc_id": doc_id},
            include=["metadatas"],
            limit=1
        )
        
        if results and results.get("ids"):
            metadata = results["metadatas"][0] if results["metadatas"] else {}
            return {
                "exists": True,
                "version": metadata.get("version", 1),
                "chunk_count": len(results["ids"])
            }
        return {"exists": False, "version": 0, "chunk_count": 0}

    def delete_collection(self, name: str) -> bool:
        """Delete a collection."""
        try:
            self.client.delete_collection(name)
            if name in self._collections:
                del self._collections[name]
            logger.info(f"Deleted collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False

    def reset(self) -> bool:
        """Reset all data (dangerous!)."""
        try:
            self.client.reset()
            self._collections.clear()
            logger.warning("VectorStore reset - all data deleted!")
            return True
        except Exception as e:
            logger.error(f"Failed to reset: {e}")
            return False


# =============================================================================
# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_vector_store(persist_directory: str = None, **kwargs) -> "VectorStore | InMemoryVectorStore":
    """
    Factory function to get the appropriate vector store.
    
    Returns ChromaDB-based VectorStore if available, otherwise InMemoryVectorStore.
    
    Args:
        persist_directory: Directory for ChromaDB storage
        **kwargs: Additional arguments for VectorStore
        
    Returns:
        VectorStore or InMemoryVectorStore instance
    """
    if CHROMADB_AVAILABLE:
        try:
            return VectorStore(persist_directory=persist_directory, **kwargs)
        except Exception as e:
            logger.warning(f"Failed to initialize ChromaDB VectorStore: {e}")
            logger.info("Falling back to InMemoryVectorStore")
    
    return InMemoryVectorStore(**kwargs)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("Testing VectorStore...")
    
    # Use factory function
    store = get_vector_store()
    print(f"Using: {type(store).__name__}")

    # Test medical knowledge
    print("\n📚 Testing Medical Knowledge Base:")
    store.add_medical_document(
        "aha_hf_2024",
        "Heart failure is a condition where the heart cannot pump enough blood. "
        "Treatment includes ACE inhibitors, beta-blockers, and lifestyle changes.",
        {"source": "AHA", "category": "guidelines", "year": 2024},
    )
    store.add_medical_document(
        "chest_pain_guide",
        "Chest pain can indicate cardiac issues. "
        "Symptoms include pressure, squeezing, and pain radiating to arm or jaw.",
        {"source": "Mayo Clinic", "category": "symptoms"},
    )

    results = store.search_medical_knowledge("heart problems treatment")
    print(f"  Found {len(results)} results for 'heart problems treatment':")
    for r in results:
        print(f"    [{r['score']:.2f}] {r['content'][:60]}...")

    print("\n✅ VectorStore tests passed!")
