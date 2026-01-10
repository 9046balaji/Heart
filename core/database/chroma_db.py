"""
ChromaDB Vector Store Integration for Heart Health AI Assistant.

Provides semantic search capabilities for medical knowledge retrieval
using ChromaDB as the vector store backend.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Try to import ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    logger.warning("ChromaDB not installed. Run: pip install chromadb")

# Try to import sentence-transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None
    logger.warning("sentence-transformers not installed. Run: pip install sentence-transformers")


@dataclass
class ChromaConfig:
    """Configuration for ChromaDB connection."""
    persist_directory: str = "./chroma_db"
    collection_name: str = "medical_knowledge"
    embedding_model: str = "all-MiniLM-L6-v2"
    distance_metric: str = "cosine"  # cosine, l2, ip


class ChromaDBService:
    """
    ChromaDB service for vector-based semantic search.
    
    Provides:
    - Document storage with embeddings
    - Semantic similarity search
    - Collection management for different content types
    """
    
    def __init__(self, config: Optional[ChromaConfig] = None):
        self.config = config or ChromaConfig()
        self.client = None
        self.collections: Dict[str, Any] = {}
        self.embedding_model = None
        self.initialized = False
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="embed")
        
    async def initialize(self) -> bool:
        """Initialize ChromaDB client and embedding model."""
        if not CHROMADB_AVAILABLE:
            logger.error("ChromaDB not available. Cannot initialize.")
            return False
            
        try:
            # Initialize ChromaDB client with persistence
            self.client = chromadb.PersistentClient(
                path=self.config.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Initialize embedding model
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                self.embedding_model = SentenceTransformer(self.config.embedding_model)
                logger.info(f"Loaded embedding model: {self.config.embedding_model}")
            else:
                logger.warning("Using default ChromaDB embeddings (slower)")
            
            # Create default collections
            await self._initialize_collections()
            
            self.initialized = True
            logger.info("ChromaDB service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            return False
    
    async def _initialize_collections(self):
        """Create or get existing collections for medical knowledge."""
        collection_configs = {
            "medical_guidelines": {
                "description": "Clinical guidelines and medical protocols",
                "metadata": {"type": "guideline"}
            },
            "drug_information": {
                "description": "Medication details, interactions, and dosing",
                "metadata": {"type": "drug"}
            },
            "symptom_knowledge": {
                "description": "Symptom-to-condition mapping and triage info",
                "metadata": {"type": "symptom"}
            },
            "heart_health_general": {
                "description": "General heart health and cardiovascular information",
                "metadata": {"type": "heart_health"}
            }
        }
        
        for name, config in collection_configs.items():
            try:
                collection = self.client.get_or_create_collection(
                    name=name,
                    metadata={"description": config["description"]}
                )
                self.collections[name] = collection
                logger.info(f"Initialized collection: {name}")
            except Exception as e:
                logger.error(f"Failed to create collection {name}: {e}")
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using sentence-transformers."""
        if self.embedding_model:
            loop = asyncio.get_running_loop()
            # Offload CPU-intensive embedding to thread pool
            embedding = await loop.run_in_executor(
                self._executor,
                lambda: self.embedding_model.encode(text).tolist()
            )
            return embedding
        else:
            # Return None to let ChromaDB use its default embedding
            return None
    
    async def add_document(
        self,
        content: str,
        collection_name: str = "medical_guidelines",
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a document to the specified collection.
        
        Args:
            content: The text content to store
            collection_name: Target collection name
            doc_id: Optional document ID (auto-generated if not provided)
            metadata: Optional metadata dict
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized:
            logger.warning("ChromaDB not initialized")
            return False
            
        try:
            collection = self.collections.get(collection_name)
            if not collection:
                logger.error(f"Collection not found: {collection_name}")
                return False
            
            # Generate document ID if not provided
            if not doc_id:
                import uuid
                doc_id = str(uuid.uuid4())
            
            # Prepare embedding
            embedding = await self._generate_embedding(content)
            
            # Add to collection
            if embedding:
                collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[metadata or {}]
                )
            else:
                collection.add(
                    ids=[doc_id],
                    documents=[content],
                    metadatas=[metadata or {}]
                )
            
            logger.debug(f"Added document {doc_id} to {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            return False
    
    async def search(
        self,
        query: str,
        collection_name: str = "medical_guidelines",
        limit: int = 5,
        where_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents using semantic similarity.
        
        Args:
            query: The search query text
            collection_name: Collection to search in
            limit: Maximum number of results
            where_filter: Optional metadata filter
            
        Returns:
            List of matching documents with similarity scores
        """
        if not self.initialized:
            logger.warning("ChromaDB not initialized")
            return []
            
        try:
            collection = self.collections.get(collection_name)
            if not collection:
                logger.error(f"Collection not found: {collection_name}")
                return []
            
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            
            # Perform search
            if query_embedding:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )
            else:
                results = collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )
            
            # Format results
            formatted_results = []
            if results and results.get("ids") and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    # Convert distance to similarity (for cosine, similarity = 1 - distance)
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    similarity = 1 - distance if distance <= 1 else 1 / (1 + distance)
                    
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i] if results.get("documents") else "",
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                        "similarity": round(similarity, 4),
                        "distance": round(distance, 4)
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def search_all_collections(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search across all collections and return combined results.
        
        Args:
            query: The search query text
            limit: Maximum number of results per collection
            
        Returns:
            Combined and sorted list of matching documents
        """
        all_results = []
        
        for collection_name in self.collections.keys():
            results = await self.search(
                query=query,
                collection_name=collection_name,
                limit=limit
            )
            for result in results:
                result["collection"] = collection_name
            all_results.extend(results)
        
        # Sort by similarity (highest first)
        all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        
        return all_results[:limit * 2]  # Return top results across all collections
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics for all collections."""
        stats = {}
        
        for name, collection in self.collections.items():
            try:
                count = collection.count()
                stats[name] = {
                    "document_count": count,
                    "metadata": collection.metadata
                }
            except Exception as e:
                stats[name] = {"error": str(e)}
        
        return stats
    
    async def seed_initial_knowledge(self):
        """Seed the database with initial medical knowledge."""
        initial_data = [
            # Heart Rate Guidelines
            {
                "collection": "medical_guidelines",
                "content": "Normal resting heart rate for adults ranges from 60 to 100 beats per minute. "
                          "A heart rate above 100 BPM at rest is called tachycardia and may indicate stress, "
                          "dehydration, caffeine intake, or underlying cardiac conditions. Athletes may have "
                          "lower resting heart rates (40-60 BPM) which is normal.",
                "metadata": {"topic": "heart_rate", "source": "AHA", "severity": "informational"}
            },
            {
                "collection": "medical_guidelines",
                "content": "A heart rate of 120 BPM at rest may be concerning and warrants evaluation. "
                          "Causes include anxiety, fever, anemia, hyperthyroidism, or cardiac arrhythmias. "
                          "If accompanied by chest pain, shortness of breath, or dizziness, seek immediate medical attention.",
                "metadata": {"topic": "tachycardia", "source": "ACC", "severity": "moderate"}
            },
            # SpO2 Guidelines
            {
                "collection": "medical_guidelines",
                "content": "Normal blood oxygen saturation (SpO2) is 95-100%. Levels below 95% may indicate "
                          "hypoxemia and require medical evaluation. Levels below 90% are considered critically low "
                          "and require immediate medical attention. Chronic conditions like COPD may have different baselines.",
                "metadata": {"topic": "spo2", "source": "WHO", "severity": "critical"}
            },
            # Symptom Information
            {
                "collection": "symptom_knowledge",
                "content": "Chest pain can have cardiac or non-cardiac causes. Cardiac chest pain is often described as "
                          "pressure, squeezing, or heaviness. It may radiate to the arm, jaw, or back. "
                          "Non-cardiac causes include GERD, muscle strain, or anxiety. Any new chest pain should be evaluated promptly.",
                "metadata": {"symptom": "chest_pain", "urgency": "high"}
            },
            {
                "collection": "symptom_knowledge",
                "content": "Palpitations are sensations of a racing, fluttering, or pounding heartbeat. "
                          "Common causes include stress, caffeine, alcohol, or arrhythmias. "
                          "Seek immediate care if accompanied by chest pain, shortness of breath, or fainting.",
                "metadata": {"symptom": "palpitations", "urgency": "moderate"}
            },
            # Drug Information
            {
                "collection": "drug_information",
                "content": "Metoprolol is a beta-blocker used to treat high blood pressure, angina, and heart failure. "
                          "Common side effects include fatigue, dizziness, and slow heart rate. "
                          "Do not stop taking suddenly as this may cause rebound hypertension. "
                          "Contraindicated in severe bradycardia and heart block.",
                "metadata": {"drug_name": "metoprolol", "drug_class": "beta_blocker"}
            },
            {
                "collection": "drug_information", 
                "content": "Aspirin 81mg daily is used for cardiovascular disease prevention in high-risk patients. "
                          "It works by preventing blood clots. Side effects include stomach upset and increased bleeding risk. "
                          "Contraindicated in aspirin allergy and active bleeding disorders.",
                "metadata": {"drug_name": "aspirin", "drug_class": "antiplatelet"}
            }
        ]
        
        for item in initial_data:
            await self.add_document(
                content=item["content"],
                collection_name=item["collection"],
                metadata=item["metadata"]
            )
        
        logger.info(f"Seeded {len(initial_data)} initial knowledge documents")
    
    def close(self):
        """Close the ChromaDB client and executor."""
        if self._executor:
            self._executor.shutdown(wait=False)
        if self.client:
            # ChromaDB PersistentClient doesn't need explicit close
            logger.info("ChromaDB service closed")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_chroma_service: Optional[ChromaDBService] = None


async def get_chroma_service() -> ChromaDBService:
    """Get singleton ChromaDB service instance."""
    global _chroma_service
    if _chroma_service is None:
        _chroma_service = ChromaDBService()
        initialized = await _chroma_service.initialize()
        if initialized:
            # Seed initial knowledge if collection is empty
            stats = await _chroma_service.get_collection_stats()
            total_docs = sum(s.get("document_count", 0) for s in stats.values() if isinstance(s, dict))
            if total_docs == 0:
                await _chroma_service.seed_initial_knowledge()
    return _chroma_service
