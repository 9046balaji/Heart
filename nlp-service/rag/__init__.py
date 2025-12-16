"""
RAG (Retrieval-Augmented Generation) Module for Cardio AI Assistant

This module provides semantic search and knowledge retrieval capabilities
to enhance the LLM's responses with accurate medical information.

Components:
- EmbeddingService: Generate vector embeddings using SentenceTransformers
- VectorStore: ChromaDB-based storage for embeddings and documents
- RAGPipeline: End-to-end retrieval and generation pipeline
- MemoriRAGBridge: Connect RAG with existing Memori memory system

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │                    RAG Module                           │
    ├─────────────────────────────────────────────────────────┤
    │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │
    │  │ Embedding   │  │ VectorStore  │  │ RAGPipeline  │   │
    │  │ Service     │──│  (ChromaDB)  │──│              │   │
    │  └─────────────┘  └──────────────┘  └──────────────┘   │
    │         │                                   │           │
    │         │         ┌──────────────┐         │           │
    │         └─────────│ MemoriRAG    │─────────┘           │
    │                   │   Bridge     │                     │
    │                   └──────────────┘                     │
    └─────────────────────────────────────────────────────────┘

Usage:
    from rag import RAGPipeline, MemoriRAGBridge
    
    # Simple query
    rag = RAGPipeline()
    response = await rag.query("What are symptoms of heart disease?")
    
    # With Memori integration
    bridge = MemoriRAGBridge(memori=memori_instance, vector_store=rag.vector_store)
    results = await bridge.search("blood pressure history", user_id="user123")
"""

from .embedding_service import EmbeddingService, get_embedding_service
from .vector_store import VectorStore
from .rag_pipeline import RAGPipeline, RetrievedContext, RAGResponse, create_rag_pipeline
from .memori_integration import MemoriRAGBridge, SyncConfig, create_memori_rag_bridge

__all__ = [
    # Embedding
    "EmbeddingService",
    "get_embedding_service",
    # Vector Store
    "VectorStore",
    # RAG Pipeline
    "RAGPipeline",
    "RetrievedContext",
    "RAGResponse",
    "create_rag_pipeline",
    # Memori Integration
    "MemoriRAGBridge",
    "SyncConfig",
    "create_memori_rag_bridge",
]
