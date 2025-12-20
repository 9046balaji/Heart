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
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Optional ChromaDB import
try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None
    Settings = None
    CHROMADB_AVAILABLE = False
    logger.warning("chromadb not installed. " "Run: pip install chromadb")

from .embedding_service import EmbeddingService


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

    def __init__(
        self,
        persist_directory: str = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize Vector Store.

        Args:
            persist_directory: Directory for ChromaDB storage
            embedding_model: Model name for embeddings
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is required. Install with: pip install chromadb"
            )

        # Set persist directory
        if persist_directory is None:
            persist_directory = os.path.join(
                os.path.dirname(__file__), "..", "data", "chroma_db"
            )

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

        # Initialize embedding service
        self.embedding_service = EmbeddingService.get_instance(
            model_name=embedding_model
        )

        # Collection cache
        self._collections: Dict[str, Any] = {}

        logger.info("✅ VectorStore initialized successfully")

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

    def search_medical_knowledge(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict] = None,
        collection_name: str = None,
    ) -> List[Dict]:
        """
        Search medical knowledge base.

        Args:
            query: Search query
            top_k: Number of results
            filter_metadata: Metadata filters
            collection_name: Optional custom collection

        Returns:
            List of matching documents with scores

        Example:
            results = store.search_medical_knowledge(
                "heart failure treatment options",
                top_k=5,
                filter_metadata={"category": "guidelines"}
            )

            for doc in results:
                print(f"[{doc['score']:.2f}] {doc['content'][:100]}...")
        """
        collection = self.get_or_create_collection(
            collection_name or self.MEDICAL_COLLECTION
        )

        # Generate query embedding
        query_embedding = self.embedding_service.embed_text(query)

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
                        "score": 1
                        - results["distances"][0][i],  # Convert distance to similarity
                    }
                )

        return formatted

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
                        "score": 1 - results["distances"][0][i],
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
# TESTING
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("Testing VectorStore...")

    # Use temp directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_directory=tmpdir)

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

        # Test user memories
        print("\n👤 Testing User Memories:")
        store.store_user_memory(
            "user123", "mem_1", "User mentioned they have high blood pressure", "fact"
        )
        store.store_user_memory(
            "user123", "mem_2", "User takes Lisinopril for hypertension", "medication"
        )

        results = store.search_user_memories("user123", "blood pressure medication")
        print(f"  Found {len(results)} memories for 'blood pressure medication':")
        for r in results:
            print(f"    [{r['score']:.2f}] {r['content']}")

        # Stats
        print(f"\n📊 Stats: {store.get_stats()}")

        print("\n✅ VectorStore tests passed!")
