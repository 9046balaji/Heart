"""
RAG (Retrieval-Augmented Generation) Module for Cardio AI Assistant

This module provides semantic search and knowledge retrieval capabilities
to enhance the LLM's responses with accurate medical information.

Components:
- EmbeddingService: Generate vector embeddings (Factory for ONNX/PyTorch)
- VectorStore: PostgreSQL/pgvector-based storage for embeddings and documents
- UnifiedRAGOrchestrator: Unified RAG orchestrator (Vector + Graph)
- MemoriRAGBridge: Connect RAG with existing Memori memory system

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │                    RAG Module                           │
    ├─────────────────────────────────────────────────────────┤
    │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │
    │  │ Embedding   │  │ VectorStore  │  │ Unified      │   │
    │  │ Service     │──│  (pgvector)  │──│ RAG Orch.    │   │
    │  └─────────────┘  └──────────────┘  └──────────────┘   │
    │         │                                   │           │
    │         │         ┌──────────────┐         │           │
    │         └─────────│ MemoriRAG    │─────────┘           │
    │                   │   Bridge     │                     │
    │                   └──────────────┘                     │
    └─────────────────────────────────────────────────────────┘

Usage:
    from rag import get_unified_orchestrator, MemoriRAGBridge

    # Simple query
    rag = get_unified_orchestrator()
    response = await rag.query("What are symptoms of heart disease?")

    # With Memori integration
    bridge = MemoriRAGBridge(memori=memori_instance, vector_store=rag.vector_store)
    results = await bridge.search("blood pressure history", user_id="user123")
"""

from .embedding_service import EmbeddingService, get_embedding_service
from .vector_store import VectorStore
from .context_assembler import ContextAssembler, AssembledContext, RetrievalResult
from .memori_integration import MemoriRAGBridge, SyncConfig, create_memori_rag_bridge
from .rag_engines import HeartDiseaseRAG

# Query optimization
from .rag_query_optimizer import (
    RAGQueryConfig,
    EmbeddingCache,
    RAGResultCache,
    BatchEmbeddingProcessor,
    OptimizedRAGQueries,
    RAGPerformanceMonitor,
    create_optimized_rag_queries,
)

# Multimodal processing (tables, images, equations)
from .multimodal import (
    MultimodalConfig,
    MultimodalIngestionService,
    MultimodalRetriever,
    VLMEnhancedRetriever,
    MultimodalQueryService,
    DirectContentInserter,
    FolderProcessor,
    EntityExtractor,
    TableProcessor,
    ImageProcessor,
    ContextExtractor,
)

__all__ = [
    # Embedding
    "EmbeddingService",
    "get_embedding_service",
    # Vector Store
    "VectorStore",
    # Context Assembly
    "ContextAssembler",
    "AssembledContext",
    "RetrievalResult",
    # Memori Integration
    "MemoriRAGBridge",
    "SyncConfig",
    "create_memori_rag_bridge",
    # Query Optimization
    "RAGQueryConfig",
    "EmbeddingCache",
    "RAGResultCache",
    "BatchEmbeddingProcessor",
    "OptimizedRAGQueries",
    "RAGPerformanceMonitor",
    "create_optimized_rag_queries",
    # Multimodal Processing
    "MultimodalConfig",
    "MultimodalIngestionService",
    "MultimodalRetriever",
    "VLMEnhancedRetriever",
    "MultimodalQueryService",
    "DirectContentInserter",
    "FolderProcessor",
    "EntityExtractor",
    "TableProcessor",
    "ImageProcessor",
    "ContextExtractor",
    # Specialized Engines
    "HeartDiseaseRAG",
]
