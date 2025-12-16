"""
RAG API Endpoints

This module provides FastAPI endpoints for the RAG (Retrieval-Augmented Generation) system,
enabling semantic search, knowledge base management, and context-augmented responses.

Endpoints:
- POST /api/rag/query - Query with RAG context
- GET  /api/rag/stats - Get knowledge base statistics
- POST /api/rag/knowledge/index - Index new medical knowledge
- GET  /api/rag/search - Semantic search endpoint
- POST /api/rag/initialize - Initialize/reload knowledge base
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class RAGQueryRequest(BaseModel):
    """Request model for RAG query."""
    query: str = Field(..., min_length=1, max_length=5000, description="User query")
    user_id: Optional[str] = Field(None, description="User ID for memory lookup")
    include_medical: bool = Field(True, description="Include medical knowledge")
    include_drugs: bool = Field(True, description="Include drug information")
    include_user_memory: bool = Field(True, description="Include user memories")
    top_k: int = Field(5, ge=1, le=20, description="Number of results per source")
    generate_response: bool = Field(True, description="Generate LLM response or just retrieve")


class RAGSearchRequest(BaseModel):
    """Request model for semantic search."""
    query: str = Field(..., min_length=1, max_length=2000)
    collection: str = Field("medical_knowledge", description="Collection to search")
    top_k: int = Field(5, ge=1, le=50)
    filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")


class RAGIndexRequest(BaseModel):
    """Request model for indexing documents."""
    documents: List[Dict[str, Any]] = Field(..., description="Documents to index")
    collection: str = Field("medical_knowledge", description="Target collection")


class Citation(BaseModel):
    """Citation model."""
    type: str
    source: Optional[str] = None
    category: Optional[str] = None
    drug_name: Optional[str] = None
    score: float


class RAGQueryResponse(BaseModel):
    """Response model for RAG query."""
    response: str
    citations: List[Citation]
    sources: Dict[str, Any]
    query: str
    processing_time_ms: float
    timestamp: str


class RAGStatsResponse(BaseModel):
    """Response model for knowledge base statistics."""
    status: str
    medical_knowledge_count: int
    drug_knowledge_count: int
    symptoms_count: int
    user_memories_count: int
    embedding_model: str
    embedding_dimension: int
    vector_store_path: str
    last_indexed: Optional[str]


class RAGSearchResponse(BaseModel):
    """Response model for semantic search."""
    results: List[Dict[str, Any]]
    query: str
    collection: str
    count: int
    processing_time_ms: float


class UnifiedSearchRequest(BaseModel):
    """Request model for unified Memori + RAG search."""
    query: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = Field(None, description="User ID for personalized results")
    top_k: int = Field(10, ge=1, le=50)
    use_memori: bool = Field(True, description="Search in Memori memories")
    use_rag: bool = Field(True, description="Search in RAG knowledge base")
    hybrid_mode: str = Field("rrf", description="Ranking mode: rrf, interleave, or score_weighted")


class UnifiedSearchResponse(BaseModel):
    """Response model for unified search."""
    results: List[Dict[str, Any]]
    query: str
    sources_used: Dict[str, bool]
    result_counts: Dict[str, int]
    processing_time_ms: float


class RAGInitializeResponse(BaseModel):
    """Response model for knowledge base initialization."""
    status: str
    message: str
    documents_indexed: Dict[str, int]
    duration_seconds: float


# =============================================================================
# RAG API ROUTER
# =============================================================================

# Global RAG instances (initialized in lifespan)
_rag_pipeline = None
_vector_store = None
_knowledge_loader = None
_memori_rag_bridge = None  # Bridge for unified Memori + RAG search
_is_initialized = False

def get_rag_pipeline():
    """Get the RAG pipeline instance."""
    global _rag_pipeline
    if _rag_pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="RAG system not initialized. Call /api/rag/initialize first."
        )
    return _rag_pipeline

def get_vector_store():
    """Get the vector store instance."""
    global _vector_store
    if _vector_store is None:
        raise HTTPException(
            status_code=503,
            detail="Vector store not initialized."
        )
    return _vector_store


def get_memori_rag_bridge():
    """Get the Memori-RAG bridge instance."""
    global _memori_rag_bridge
    return _memori_rag_bridge


def set_memori_for_bridge(memori_instance):
    """
    Connect a Memori instance to the RAG bridge.
    
    Call this after initializing MemoryManager to enable unified search.
    """
    global _memori_rag_bridge, _vector_store
    if _memori_rag_bridge is not None:
        _memori_rag_bridge.set_memori(memori_instance)
        logger.info("Memori instance connected to RAG bridge")
    elif _vector_store is not None:
        # Create bridge if vector store exists
        try:
            from rag.memori_integration import MemoriRAGBridge
            _memori_rag_bridge = MemoriRAGBridge(
                memori=memori_instance,
                vector_store=_vector_store
            )
            logger.info("Created MemoriRAGBridge with Memori instance")
        except Exception as e:
            logger.warning(f"Could not create MemoriRAGBridge: {e}")


# Create router
router = APIRouter(prefix="/api/rag", tags=["RAG - Retrieval Augmented Generation"])


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """
    Query the RAG system with context-augmented generation.
    
    This endpoint:
    1. Retrieves relevant medical knowledge
    2. Retrieves relevant user memories (if user_id provided)
    3. Checks drug interactions (if relevant)
    4. Generates a response with the LLM
    5. Returns response with source citations
    """
    start_time = time.time()
    
    try:
        pipeline = get_rag_pipeline()
        
        # Query the RAG pipeline
        result = await pipeline.query(
            query=request.query,
            user_id=request.user_id,
            search_medical=request.include_medical,
            search_drugs=request.include_drugs,
            search_user_memory=request.include_user_memory,
            top_k=request.top_k,
            generate=request.generate_response,
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return RAGQueryResponse(
            response=result.response,
            citations=[Citation(**c) for c in result.citations],
            sources=result.to_dict().get("sources", {}),
            query=request.query,
            processing_time_ms=processing_time,
            timestamp=datetime.now().isoformat(),
        )
        
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=RAGStatsResponse)
async def get_rag_stats():
    """
    Get statistics about the RAG knowledge base.
    
    Returns counts for each collection and embedding info.
    """
    try:
        store = get_vector_store()
        stats = store.get_stats()
        
        return RAGStatsResponse(
            status="healthy" if _is_initialized else "not_initialized",
            medical_knowledge_count=stats.get("medical_knowledge", 0),
            drug_knowledge_count=stats.get("drug_interactions", 0),
            symptoms_count=stats.get("symptoms_conditions", 0),
            user_memories_count=stats.get("user_memories", 0),
            embedding_model=store.embedding_service.model_name,
            embedding_dimension=store.embedding_service.dimension,
            vector_store_path=store.persist_directory,
            last_indexed=stats.get("last_indexed"),
        )
        
    except Exception as e:
        logger.error(f"Failed to get RAG stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=RAGSearchResponse)
async def semantic_search(request: RAGSearchRequest):
    """
    Perform semantic search on a specific collection.
    
    This is a lower-level endpoint for direct vector search.
    """
    start_time = time.time()
    
    try:
        store = get_vector_store()
        
        # Determine which search method to use based on collection
        if request.collection == "medical_knowledge":
            results = store.search_medical_knowledge(
                query=request.query,
                top_k=request.top_k,
                filters=request.filters,
            )
        elif request.collection == "drug_interactions":
            results = store.search_drug_info(
                query=request.query,
                top_k=request.top_k,
            )
        else:
            # Generic collection search
            results = store.search_collection(
                collection_name=request.collection,
                query=request.query,
                top_k=request.top_k,
                filters=request.filters,
            )
        
        processing_time = (time.time() - start_time) * 1000
        
        return RAGSearchResponse(
            results=results,
            query=request.query,
            collection=request.collection,
            count=len(results),
            processing_time_ms=processing_time,
        )
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unified-search", response_model=UnifiedSearchResponse)
async def unified_search(request: UnifiedSearchRequest):
    """
    Unified search across Memori memories and RAG knowledge base.
    
    This endpoint uses the MemoriRAGBridge to combine:
    - Structured memories from Memori (user history, conversations)
    - Semantic knowledge from RAG (medical guidelines, drug info)
    
    Hybrid ranking modes:
    - rrf: Reciprocal Rank Fusion (default, best for diverse results)
    - interleave: Round-robin interleaving
    - score_weighted: Weighted by similarity scores
    """
    start_time = time.time()
    
    try:
        bridge = get_memori_rag_bridge()
        
        if bridge is None:
            # Fallback to RAG-only search if bridge not available
            logger.warning("MemoriRAGBridge not available, using RAG-only search")
            store = get_vector_store()
            results = store.search_medical_knowledge(
                query=request.query,
                top_k=request.top_k,
            )
            processing_time = (time.time() - start_time) * 1000
            return UnifiedSearchResponse(
                results=results,
                query=request.query,
                sources_used={"memori": False, "rag": True},
                result_counts={"rag": len(results)},
                processing_time_ms=processing_time,
            )
        
        # Use bridge for unified search
        search_result = await bridge.search(
            query=request.query,
            user_id=request.user_id,
            top_k=request.top_k,
            use_memori=request.use_memori,
            use_rag=request.use_rag,
            hybrid_mode=request.hybrid_mode,
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return UnifiedSearchResponse(
            results=search_result.get("results", []),
            query=request.query,
            sources_used={
                "memori": request.use_memori and bridge.memori is not None,
                "rag": request.use_rag,
            },
            result_counts=search_result.get("counts", {}),
            processing_time_ms=processing_time,
        )
        
    except Exception as e:
        logger.error(f"Unified search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge/index")
async def index_documents(
    request: RAGIndexRequest,
    background_tasks: BackgroundTasks,
):
    """
    Index documents into the knowledge base.
    
    Documents should have 'content' and optional 'metadata' fields.
    """
    try:
        store = get_vector_store()
        
        indexed_count = 0
        for doc in request.documents:
            content = doc.get("content")
            if not content:
                continue
                
            metadata = doc.get("metadata", {})
            doc_id = doc.get("id") or f"doc_{indexed_count}"
            
            if request.collection == "medical_knowledge":
                store.add_medical_document(
                    doc_id=doc_id,
                    content=content,
                    category=metadata.get("category", "general"),
                    source=metadata.get("source", "user_uploaded"),
                    metadata=metadata,
                )
            else:
                store.add_to_collection(
                    collection_name=request.collection,
                    doc_id=doc_id,
                    content=content,
                    metadata=metadata,
                )
            indexed_count += 1
        
        return {
            "status": "success",
            "message": f"Indexed {indexed_count} documents to {request.collection}",
            "count": indexed_count,
        }
        
    except Exception as e:
        logger.error(f"Document indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize", response_model=RAGInitializeResponse)
async def initialize_knowledge_base(force_reload: bool = False):
    """
    Initialize or reload the RAG knowledge base.
    
    This loads the cardiovascular guidelines, drug database,
    and symptom checker into the vector store.
    
    Args:
        force_reload: If True, clear existing data and reload
    """
    global _rag_pipeline, _vector_store, _knowledge_loader, _is_initialized
    
    start_time = time.time()
    
    try:
        # Import RAG components
        from rag import RAGPipeline, VectorStore, create_rag_pipeline
        from rag.knowledge_base import KnowledgeLoader
        
        # Create/get instances
        if _vector_store is None or force_reload:
            _vector_store = VectorStore()
            
        if _rag_pipeline is None or force_reload:
            _rag_pipeline = RAGPipeline(vector_store=_vector_store)
        
        # Initialize knowledge loader
        _knowledge_loader = KnowledgeLoader(_vector_store)
        
        # Load all knowledge bases
        results = _knowledge_loader.load_all(force_reload=force_reload)
        
        _is_initialized = True
        duration = time.time() - start_time
        
        logger.info(f"RAG knowledge base initialized in {duration:.2f}s")
        
        return RAGInitializeResponse(
            status="success",
            message="Knowledge base initialized successfully",
            documents_indexed=results,
            duration_seconds=duration,
        )
        
    except ImportError as e:
        logger.error(f"RAG dependencies not installed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"RAG dependencies not installed: {e}. Install with: pip install sentence-transformers chromadb"
        )
    except Exception as e:
        logger.error(f"Knowledge base initialization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def rag_health():
    """Check RAG system health."""
    global _is_initialized, _rag_pipeline, _vector_store
    
    health_status = {
        "status": "healthy" if _is_initialized else "not_initialized",
        "vector_store": _vector_store is not None,
        "rag_pipeline": _rag_pipeline is not None,
        "timestamp": datetime.now().isoformat(),
    }
    
    if _is_initialized and _vector_store:
        try:
            stats = _vector_store.get_stats()
            health_status["collections"] = stats
        except Exception as e:
            health_status["error"] = str(e)
            health_status["status"] = "degraded"
    
    return health_status


# =============================================================================
# INITIALIZATION HELPER
# =============================================================================

async def initialize_rag_on_startup():
    """
    Initialize RAG system on application startup.
    
    Call this from the FastAPI lifespan event.
    """
    global _rag_pipeline, _vector_store, _memori_rag_bridge, _is_initialized
    
    try:
        from rag import RAGPipeline, VectorStore
        
        logger.info("Initializing RAG system on startup...")
        
        # Create vector store
        _vector_store = VectorStore()
        
        # Create RAG pipeline
        _rag_pipeline = RAGPipeline(vector_store=_vector_store)
        
        # Create MemoriRAGBridge (Memori will be connected later if available)
        try:
            from rag.memori_integration import MemoriRAGBridge
            _memori_rag_bridge = MemoriRAGBridge(
                memori=None,  # Will be set when MemoryManager initializes
                vector_store=_vector_store
            )
            logger.info("MemoriRAGBridge created (awaiting Memori connection)")
        except Exception as e:
            logger.warning(f"Could not create MemoriRAGBridge: {e}")
            _memori_rag_bridge = None
        
        # Check if knowledge base needs to be loaded
        stats = _vector_store.get_stats()
        total_docs = sum(stats.values()) if isinstance(stats, dict) else 0
        
        if total_docs == 0:
            logger.info("Knowledge base empty, loading default knowledge...")
            from rag.knowledge_base import KnowledgeLoader
            loader = KnowledgeLoader(_vector_store)
            loader.load_all()
            logger.info("Default knowledge loaded")
        else:
            logger.info(f"Knowledge base has {total_docs} documents")
        
        _is_initialized = True
        logger.info("✅ RAG system initialized successfully")
        
    except ImportError as e:
        logger.warning(f"RAG dependencies not available: {e}")
        logger.warning("RAG features will be disabled. Install with: pip install sentence-transformers chromadb")
        _is_initialized = False
        
    except Exception as e:
        logger.error(f"Failed to initialize RAG system: {e}")
        _is_initialized = False


async def shutdown_rag():
    """Cleanup RAG resources on shutdown."""
    global _rag_pipeline, _vector_store, _memori_rag_bridge, _is_initialized
    
    logger.info("Shutting down RAG system...")
    _rag_pipeline = None
    _vector_store = None
    _memori_rag_bridge = None
    _is_initialized = False


# Alias for main.py import
initialize_rag_service = initialize_rag_on_startup

# Export the router with common name
rag_router = router
