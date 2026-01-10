"""
Knowledge Graph Package.

Provides graph-based knowledge representation and retrieval
for enhanced context understanding and semantic search.

Components:
- base: Abstract base class for Neo4j service
- neo4j_service: Neo4j database operations
- graph_rag: Graph-enhanced RAG pipeline
"""

from .base import AbstractNeo4jService, Neo4jConfig
from .neo4j_service import (
    Neo4jService,
    GraphNode,
    GraphRelationship,
)
from .graph_rag import (
    GraphRAGService,
    GraphContext,
    GraphSearchResult,
)

__all__ = [
    # Abstract Base
    "AbstractNeo4jService",
    "Neo4jConfig",
    # Neo4j
    "Neo4jService",
    "GraphNode",
    "GraphRelationship",
    # Graph RAG
    "GraphRAGService",
    "GraphContext",
    "GraphSearchResult",
]
