"""
pgvector-based Vector Store for HeartGuard AI

This module provides PostgreSQL/pgvector-based vector storage,
replacing ChromaDB for semantic search over medical knowledge and user memories.

Features:
- PostgreSQL native vector storage using pgvector extension
- HNSW indexing for fast similarity search
- Multi-tenant support with user_id isolation
- Async and sync query support
- LRU + Redis caching for repeated queries
- Drop-in replacement for ChromaDB VectorStore

Performance:
- L1: In-memory LRU cache (100 entries)
- L2: Redis cache with 300s TTL
- Target: <300ms p95 latency for vector search

Collections (as PostgreSQL tables):
1. vector_user_memories - Per-user memory embeddings
2. vector_medical_knowledge - Medical guidelines/protocols
3. vector_drug_interactions - Medication information
4. vector_symptoms_conditions - Symptom-to-condition mapping
"""

import asyncio
import hashlib
import json
import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Redis cache configuration
VECTOR_CACHE_TTL = int(os.getenv("VECTOR_CACHE_TTL", "300"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Lazy Redis client
_vector_redis_client = None
_vector_redis_available = None


def _get_sync_redis_client():
    """Get synchronous Redis client for vector store caching."""
    global _vector_redis_client, _vector_redis_available
    
    if _vector_redis_available is False:
        return None
    
    if _vector_redis_client is not None:
        return _vector_redis_client
    
    try:
        import redis
        _vector_redis_client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2.0,
        )
        _vector_redis_client.ping()
        _vector_redis_available = True
        logger.info(f"✅ Vector cache Redis connected (TTL={VECTOR_CACHE_TTL}s)")
        return _vector_redis_client
    except Exception as e:
        logger.warning(f"⚠️ Redis unavailable for vector caching: {e}")
        _vector_redis_available = False
        return None


# Import embedding services
try:
    from .embedding_service import EmbeddingService
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from rag.embedding_service import EmbeddingService

try:
    from .embedding_onnx import ONNXEmbeddingService
    ONNX_AVAILABLE = True
except ImportError:
    try:
        from rag.embedding_onnx import ONNXEmbeddingService
        ONNX_AVAILABLE = True
    except ImportError:
        ONNX_AVAILABLE = False


class PgVectorStore:
    """
    PostgreSQL pgvector-based vector store for healthcare RAG.
    
    Replaces ChromaDB with native PostgreSQL vector storage using pgvector extension.
    
    Features:
    - Persistent storage with ACID guarantees
    - HNSW indexing for fast approximate nearest neighbor search
    - Multi-tenant user isolation via user_id
    - Hybrid queries (vector + SQL filters)
    - Connection pooling support
    
    Tables:
    - vector_medical_knowledge: Medical guidelines, protocols
    - vector_drug_interactions: Medication information  
    - vector_symptoms_conditions: Symptom-condition mapping
    - vector_user_memories: Per-user memory storage
    
    Example:
        store = PgVectorStore()
        
        # Store medical document
        await store.add_medical_document(
            doc_id="aha_guidelines_2024",
            content="Heart failure treatment guidelines...",
            metadata={"source": "AHA", "year": 2024}
        )
        
        # Search
        results = await store.search_medical_knowledge(
            "heart failure treatment",
            top_k=5
        )
    """
    
    # Table names
    MEDICAL_TABLE = "vector_medical_knowledge"
    DRUG_TABLE = "vector_drug_interactions"
    SYMPTOMS_TABLE = "vector_symptoms_conditions"
    MEMORIES_TABLE = "vector_user_memories"
    
    # Embedding dimension (all-MiniLM-L6-v2)
    EMBEDDING_DIMENSION = 384
    
    def __init__(
        self,
        database_url: str = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        pool_size: int = 10,
        max_overflow: int = 20,
    ):
        """
        Initialize pgvector store.
        
        Args:
            database_url: PostgreSQL connection URL. If None, uses DATABASE_URL env.
            embedding_model: Model name for embeddings (default: all-MiniLM-L6-v2)
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
        """
        # Get database URL
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL not provided")
        
        # Initialize embedding service
        if ONNX_AVAILABLE:
            try:
                self.embedding_service = ONNXEmbeddingService.get_instance(
                    model_type="fast" if "mini" in embedding_model.lower() else "quality"
                )
                logger.info("✅ Using ONNX-optimized embedding service")
            except Exception as e:
                logger.warning(f"ONNX failed, using standard: {e}")
                self.embedding_service = EmbeddingService.get_instance(
                    model_name=embedding_model
                )
        else:
            self.embedding_service = EmbeddingService.get_instance(
                model_name=embedding_model
            )
        
        # Query result cache
        self._query_cache: OrderedDict[str, List[Dict]] = OrderedDict()
        self._query_cache_max_size = 100
        self._query_cache_lock = threading.Lock()
        
        # Connection pool (lazy initialization)
        self._engine = None
        self._async_engine = None
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        
        # Verify pgvector extension on first use
        self._pgvector_verified = False
        
        logger.info("✅ PgVectorStore initialized")
    
    def _get_sync_engine(self):
        """Get synchronous SQLAlchemy engine."""
        if self._engine is None:
            from sqlalchemy import create_engine
            self._engine = create_engine(
                self.database_url,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._engine
    
    def _get_async_engine(self):
        """Get asynchronous SQLAlchemy engine."""
        if self._async_engine is None:
            from sqlalchemy.ext.asyncio import create_async_engine
            # Convert sync URL to async
            async_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            ).replace(
                "postgres://", "postgresql+asyncpg://"
            )
            self._async_engine = create_async_engine(
                async_url,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._async_engine
    
    def _verify_pgvector(self):
        """Verify pgvector extension is installed."""
        if self._pgvector_verified:
            return
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ))
            row = result.fetchone()
            if row:
                logger.info(f"✅ pgvector extension verified (v{row[0]})")
                self._pgvector_verified = True
            else:
                raise RuntimeError(
                    "pgvector extension not installed. "
                    "Run: CREATE EXTENSION vector;"
                )
    
    def _format_embedding(self, embedding: Union[List[float], np.ndarray]) -> str:
        """Format embedding as PostgreSQL vector string."""
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
        return "[" + ",".join(str(x) for x in embedding) + "]"
    
    def _cache_key(self, query: str, table: str, top_k: int, filters: dict = None) -> str:
        """Generate cache key for query."""
        key_data = f"{query}:{table}:{top_k}:{json.dumps(filters or {}, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _check_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Check L1 (memory) and L2 (Redis) cache."""
        # L1: Memory cache
        with self._query_cache_lock:
            if cache_key in self._query_cache:
                logger.debug(f"⚡ L1 cache HIT: {cache_key[:8]}")
                return self._query_cache[cache_key]
        
        # L2: Redis cache
        redis_client = _get_sync_redis_client()
        if redis_client:
            try:
                cached = redis_client.get(f"pgvec:{cache_key}")
                if cached:
                    results = json.loads(cached)
                    logger.debug(f"⚡ L2 cache HIT: {cache_key[:8]}")
                    # Promote to L1
                    with self._query_cache_lock:
                        if len(self._query_cache) >= self._query_cache_max_size:
                            self._query_cache.popitem(last=False)
                        self._query_cache[cache_key] = results
                    return results
            except Exception as e:
                logger.debug(f"Redis cache get failed: {e}")
        
        return None
    
    def _update_cache(self, cache_key: str, results: List[Dict]):
        """Update L1 and L2 cache."""
        # L1: Memory cache
        with self._query_cache_lock:
            if len(self._query_cache) >= self._query_cache_max_size:
                self._query_cache.popitem(last=False)
            self._query_cache[cache_key] = results
        
        # L2: Redis cache
        redis_client = _get_sync_redis_client()
        if redis_client:
            try:
                redis_client.setex(
                    f"pgvec:{cache_key}",
                    VECTOR_CACHE_TTL,
                    json.dumps(results)
                )
            except Exception as e:
                logger.debug(f"Redis cache set failed: {e}")
    
    # =========================================================================
    # MEDICAL KNOWLEDGE BASE
    # =========================================================================
    
    def add_medical_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Add a medical document to the knowledge base.
        
        Args:
            doc_id: Unique document ID
            content: Document text content
            metadata: Additional metadata
            
        Returns:
            Document ID
        """
        self._verify_pgvector()
        
        # Generate embedding
        embedding = self.embedding_service.embed_text(content)
        embedding_str = self._format_embedding(embedding)
        
        # Prepare metadata
        meta = metadata or {}
        meta["added_at"] = datetime.now().isoformat()
        meta["content_length"] = len(content)
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO vector_medical_knowledge 
                (doc_id, content, embedding, metadata, created_at, updated_at)
                VALUES (:doc_id, :content, :embedding::vector, :metadata, NOW(), NOW())
                ON CONFLICT (doc_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """), {
                "doc_id": doc_id,
                "content": content,
                "embedding": embedding_str,
                "metadata": json.dumps(meta),
            })
            conn.commit()
        
        logger.debug(f"Added medical document: {doc_id}")
        return doc_id
    
    async def add_medical_document_async(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Async version of add_medical_document."""
        # Run sync method in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.add_medical_document, doc_id, content, metadata
        )
    
    def search_medical_knowledge(
        self,
        query: str = None,
        top_k: int = 5,
        filter_metadata: Optional[Dict] = None,
        query_embedding: List[float] = None,
    ) -> List[Dict]:
        """
        Search medical knowledge base using vector similarity.
        
        Args:
            query: Search query text (optional if query_embedding provided)
            top_k: Number of results to return
            filter_metadata: Metadata filters (applied as JSONB conditions)
            query_embedding: Pre-computed embedding vector
            
        Returns:
            List of matching documents with scores
        """
        self._verify_pgvector()
        
        # Check cache
        if query:
            cache_key = self._cache_key(query, self.MEDICAL_TABLE, top_k, filter_metadata)
            cached = self._check_cache(cache_key)
            if cached:
                return cached
        
        # Generate embedding if needed
        if query_embedding is None:
            if query:
                query_embedding = self.embedding_service.embed_text(query)
            else:
                raise ValueError("Either query or query_embedding required")
        
        embedding_str = self._format_embedding(query_embedding)
        
        # Build SQL query
        sql = """
            SELECT 
                doc_id,
                content,
                metadata,
                1 - (embedding <=> :embedding::vector) AS similarity
            FROM vector_medical_knowledge
            WHERE 1=1
        """
        params = {"embedding": embedding_str, "limit": top_k}
        
        # Add metadata filters
        if filter_metadata:
            for key, value in filter_metadata.items():
                sql += f" AND metadata->>'{key}' = :filter_{key}"
                params[f"filter_{key}"] = str(value)
        
        sql += " ORDER BY embedding <=> :embedding::vector LIMIT :limit"
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            rows = result.fetchall()
        
        # Format results
        results = []
        for row in rows:
            results.append({
                "id": row.doc_id,
                "content": row.content,
                "metadata": row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}"),
                "score": float(row.similarity),
            })
        
        # Update cache
        if query:
            self._update_cache(cache_key, results)
        
        return results
    
    async def search_medical_knowledge_async(
        self,
        query: str = None,
        top_k: int = 5,
        filter_metadata: Optional[Dict] = None,
        query_embedding: List[float] = None,
    ) -> List[Dict]:
        """Async version of search_medical_knowledge."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.search_medical_knowledge(query, top_k, filter_metadata, query_embedding)
        )
    
    # Alias for compatibility with ChromaDB VectorStore
    async def async_search(
        self,
        query: str,
        collection_name: str = None,
        top_k: int = 5,
        **kwargs
    ) -> List[Dict]:
        """Async search wrapper for compatibility."""
        # Map collection name to table
        if collection_name == "drug_interactions":
            return await self.search_drug_interactions_async(query, top_k)
        elif collection_name == "symptoms_conditions":
            return await self.search_symptoms_async(query, top_k)
        elif collection_name == "user_memories":
            user_id = kwargs.get("user_id", "default")
            return await self.search_user_memories_async(query, user_id, top_k)
        else:
            return await self.search_medical_knowledge_async(query, top_k)
    
    # =========================================================================
    # DRUG INTERACTIONS
    # =========================================================================
    
    def add_drug_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Add a drug interaction document."""
        self._verify_pgvector()
        
        embedding = self.embedding_service.embed_text(content)
        embedding_str = self._format_embedding(embedding)
        
        meta = metadata or {}
        meta["added_at"] = datetime.now().isoformat()
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO vector_drug_interactions 
                (doc_id, content, embedding, metadata, created_at)
                VALUES (:doc_id, :content, :embedding::vector, :metadata, NOW())
                ON CONFLICT (doc_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata
            """), {
                "doc_id": doc_id,
                "content": content,
                "embedding": embedding_str,
                "metadata": json.dumps(meta),
            })
            conn.commit()
        
        return doc_id
    
    def search_drug_interactions(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict]:
        """Search drug interactions."""
        self._verify_pgvector()
        
        cache_key = self._cache_key(query, self.DRUG_TABLE, top_k)
        cached = self._check_cache(cache_key)
        if cached:
            return cached
        
        embedding = self.embedding_service.embed_text(query)
        embedding_str = self._format_embedding(embedding)
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    doc_id,
                    content,
                    metadata,
                    1 - (embedding <=> :embedding::vector) AS similarity
                FROM vector_drug_interactions
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """), {"embedding": embedding_str, "limit": top_k})
            rows = result.fetchall()
        
        results = [
            {
                "id": row.doc_id,
                "content": row.content,
                "metadata": row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}"),
                "score": float(row.similarity),
            }
            for row in rows
        ]
        
        self._update_cache(cache_key, results)
        return results
    
    async def search_drug_interactions_async(self, query: str, top_k: int = 5) -> List[Dict]:
        """Async version of search_drug_interactions."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search_drug_interactions, query, top_k)
    
    # =========================================================================
    # SYMPTOMS CONDITIONS
    # =========================================================================
    
    def search_symptoms(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search symptoms and conditions."""
        self._verify_pgvector()
        
        cache_key = self._cache_key(query, self.SYMPTOMS_TABLE, top_k)
        cached = self._check_cache(cache_key)
        if cached:
            return cached
        
        embedding = self.embedding_service.embed_text(query)
        embedding_str = self._format_embedding(embedding)
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    doc_id,
                    content,
                    metadata,
                    1 - (embedding <=> :embedding::vector) AS similarity
                FROM vector_symptoms_conditions
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """), {"embedding": embedding_str, "limit": top_k})
            rows = result.fetchall()
        
        results = [
            {
                "id": row.doc_id,
                "content": row.content,
                "metadata": row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}"),
                "score": float(row.similarity),
            }
            for row in rows
        ]
        
        self._update_cache(cache_key, results)
        return results
    
    async def search_symptoms_async(self, query: str, top_k: int = 5) -> List[Dict]:
        """Async version of search_symptoms."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search_symptoms, query, top_k)
    
    # =========================================================================
    # USER MEMORIES (Multi-tenant)
    # =========================================================================
    
    def add_user_memory(
        self,
        memory_id: str,
        user_id: str,
        content: str,
        memory_type: str = "general",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Add a user-specific memory with isolation.
        
        Args:
            memory_id: Unique memory ID
            user_id: User ID for multi-tenant isolation
            content: Memory content
            memory_type: Type of memory (general, preference, context, etc.)
            metadata: Additional metadata
            
        Returns:
            Memory ID
        """
        self._verify_pgvector()
        
        embedding = self.embedding_service.embed_text(content)
        embedding_str = self._format_embedding(embedding)
        
        meta = metadata or {}
        meta["added_at"] = datetime.now().isoformat()
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO vector_user_memories 
                (memory_id, user_id, content, embedding, memory_type, metadata, created_at)
                VALUES (:memory_id, :user_id, :content, :embedding::vector, :memory_type, :metadata, NOW())
                ON CONFLICT (memory_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    memory_type = EXCLUDED.memory_type,
                    metadata = EXCLUDED.metadata
            """), {
                "memory_id": memory_id,
                "user_id": user_id,
                "content": content,
                "embedding": embedding_str,
                "memory_type": memory_type,
                "metadata": json.dumps(meta),
            })
            conn.commit()
        
        logger.debug(f"Added user memory: {memory_id} for user: {user_id}")
        return memory_id
    
    def search_user_memories(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search user memories with multi-tenant isolation.
        
        Args:
            query: Search query
            user_id: User ID for isolation (REQUIRED)
            top_k: Number of results
            memory_type: Optional filter by memory type
            
        Returns:
            List of matching memories
        """
        self._verify_pgvector()
        
        cache_key = self._cache_key(
            f"{query}:{user_id}", 
            self.MEMORIES_TABLE, 
            top_k, 
            {"memory_type": memory_type} if memory_type else None
        )
        cached = self._check_cache(cache_key)
        if cached:
            return cached
        
        embedding = self.embedding_service.embed_text(query)
        embedding_str = self._format_embedding(embedding)
        
        sql = """
            SELECT 
                memory_id,
                content,
                memory_type,
                metadata,
                1 - (embedding <=> :embedding::vector) AS similarity
            FROM vector_user_memories
            WHERE user_id = :user_id
        """
        params = {
            "embedding": embedding_str,
            "user_id": user_id,
            "limit": top_k
        }
        
        if memory_type:
            sql += " AND memory_type = :memory_type"
            params["memory_type"] = memory_type
        
        sql += " ORDER BY embedding <=> :embedding::vector LIMIT :limit"
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            rows = result.fetchall()
        
        results = [
            {
                "id": row.memory_id,
                "content": row.content,
                "memory_type": row.memory_type,
                "metadata": row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}"),
                "score": float(row.similarity),
            }
            for row in rows
        ]
        
        self._update_cache(cache_key, results)
        return results
    
    async def search_user_memories_async(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
    ) -> List[Dict]:
        """Async version of search_user_memories."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.search_user_memories(query, user_id, top_k, memory_type)
        )
    
    def delete_user_memory(self, memory_id: str, user_id: str) -> bool:
        """Delete a user memory (with ownership check)."""
        self._verify_pgvector()
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                DELETE FROM vector_user_memories
                WHERE memory_id = :memory_id AND user_id = :user_id
            """), {"memory_id": memory_id, "user_id": user_id})
            conn.commit()
            
            return result.rowcount > 0
    
    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================
    
    def add_documents_batch(
        self,
        documents: List[Dict],
        table: str = None,
        batch_size: int = 100,
    ) -> Dict[str, int]:
        """
        Batch insert documents.
        
        Args:
            documents: List of dicts with 'id', 'content', 'metadata'
            table: Target table (default: vector_medical_knowledge)
            batch_size: Insert batch size
            
        Returns:
            Dict with 'added' and 'errors' counts
        """
        self._verify_pgvector()
        
        table = table or self.MEDICAL_TABLE
        added = 0
        errors = 0
        
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            with engine.connect() as conn:
                for doc in batch:
                    try:
                        embedding = self.embedding_service.embed_text(doc["content"])
                        embedding_str = self._format_embedding(embedding)
                        
                        meta = doc.get("metadata", {})
                        meta["added_at"] = datetime.now().isoformat()
                        
                        conn.execute(text(f"""
                            INSERT INTO {table} 
                            (doc_id, content, embedding, metadata, created_at)
                            VALUES (:doc_id, :content, :embedding::vector, :metadata, NOW())
                            ON CONFLICT (doc_id) DO UPDATE SET
                                content = EXCLUDED.content,
                                embedding = EXCLUDED.embedding,
                                metadata = EXCLUDED.metadata
                        """), {
                            "doc_id": doc["id"],
                            "content": doc["content"],
                            "embedding": embedding_str,
                            "metadata": json.dumps(meta),
                        })
                        added += 1
                    except Exception as e:
                        errors += 1
                        logger.warning(f"Failed to insert document {doc.get('id')}: {e}")
                
                conn.commit()
        
        logger.info(f"Batch insert complete: {added} added, {errors} errors")
        return {"added": added, "errors": errors}
    
    # =========================================================================
    # STATS & UTILITIES
    # =========================================================================
    
    def get_collection_stats(self) -> Dict[str, int]:
        """Get document counts for all tables."""
        self._verify_pgvector()
        
        tables = [
            self.MEDICAL_TABLE,
            self.DRUG_TABLE,
            self.SYMPTOMS_TABLE,
            self.MEMORIES_TABLE,
        ]
        
        stats = {}
        engine = self._get_sync_engine()
        from sqlalchemy import text
        
        with engine.connect() as conn:
            for table in tables:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    stats[table] = result.fetchone()[0]
                except Exception as e:
                    logger.warning(f"Failed to get stats for {table}: {e}")
                    stats[table] = -1
        
        return stats
    
    def clear_cache(self):
        """Clear query cache."""
        with self._query_cache_lock:
            self._query_cache.clear()
        
        redis_client = _get_sync_redis_client()
        if redis_client:
            try:
                # Clear Redis keys matching our prefix
                keys = redis_client.keys("pgvec:*")
                if keys:
                    redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Failed to clear Redis cache: {e}")
        
        logger.info("Vector store cache cleared")


# ============================================================================
# Singleton instance
# ============================================================================

_pgvector_store_instance = None
_pgvector_store_lock = threading.Lock()


def get_pgvector_store(**kwargs) -> PgVectorStore:
    """Get singleton PgVectorStore instance."""
    global _pgvector_store_instance
    
    if _pgvector_store_instance is None:
        with _pgvector_store_lock:
            if _pgvector_store_instance is None:
                _pgvector_store_instance = PgVectorStore(**kwargs)
    
    return _pgvector_store_instance


# ============================================================================
# Compatibility aliases for ChromaDB migration
# ============================================================================

# These allow gradual migration from ChromaDB VectorStore to PgVectorStore
VectorStore = PgVectorStore
get_vector_store = get_pgvector_store
