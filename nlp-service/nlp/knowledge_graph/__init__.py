"""
Knowledge Graph Package.

Provides graph-based knowledge representation and retrieval
for enhanced context understanding and semantic search.

Components:
- neo4j_service: Neo4j database operations
- graph_rag: Graph-enhanced RAG pipeline
"""

from .neo4j_service import (
    Neo4jService,
    GraphNode,
    GraphRelationship,
    Neo4jConfig,
)
from .graph_rag import (
    GraphRAGService,
    GraphContext,
    GraphSearchResult,
)

__all__ = [
    # Neo4j
    "Neo4jService",
    "GraphNode",
    "GraphRelationship",
    "Neo4jConfig",
    # Graph RAG
    "GraphRAGService",
    "GraphContext",
    "GraphSearchResult",
]
