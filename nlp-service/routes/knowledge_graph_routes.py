"""
Knowledge Graph API Routes.

FastAPI routes for graph-based knowledge representation and queries:
- Neo4j graph operations
- Graph-enhanced RAG
- Entity relationship queries
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Graph"])


# ==================== Request/Response Models ====================


class GraphNodeRequest(BaseModel):
    """Request to create a graph node."""

    label: str = Field(
        ..., description="Node label (e.g., Symptom, Medication, Condition)"
    )
    properties: Dict[str, Any] = Field(..., description="Node properties")

    class Config:
        json_schema_extra = {
            "example": {
                "label": "Symptom",
                "properties": {
                    "name": "chest pain",
                    "severity_range": "1-10",
                    "body_system": "cardiovascular",
                },
            }
        }


class GraphRelationshipRequest(BaseModel):
    """Request to create a relationship between nodes."""

    from_node_id: str
    to_node_id: str
    relationship_type: str = Field(
        ..., description="Relationship type (e.g., INDICATES, TREATS, CAUSES)"
    )
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "from_node_id": "symptom_123",
                "to_node_id": "condition_456",
                "relationship_type": "INDICATES",
                "properties": {"confidence": 0.85, "source": "medical_literature"},
            }
        }


class GraphSearchRequest(BaseModel):
    """Request for graph-based search."""

    query: str = Field(..., description="Natural language query")
    node_types: Optional[List[str]] = Field(None, description="Filter by node types")
    max_depth: int = Field(
        2, ge=1, le=5, description="Max relationship traversal depth"
    )
    limit: int = Field(10, ge=1, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What medications treat hypertension?",
                "node_types": ["Medication", "Condition"],
                "max_depth": 2,
                "limit": 10,
            }
        }


class GraphNodeResponse(BaseModel):
    """Graph node information."""

    id: str
    label: str
    properties: Dict[str, Any]
    created_at: Optional[str] = None


class GraphRelationshipResponse(BaseModel):
    """Graph relationship information."""

    id: str
    from_node: GraphNodeResponse
    to_node: GraphNodeResponse
    relationship_type: str
    properties: Dict[str, Any]


class GraphSearchResponse(BaseModel):
    """Graph search results."""

    query: str
    nodes: List[GraphNodeResponse]
    relationships: List[Dict[str, Any]]
    paths: List[List[str]]
    total_results: int
    search_time_ms: float


class GraphRAGResponse(BaseModel):
    """Graph-enhanced RAG response."""

    answer: str
    graph_context: List[Dict[str, Any]]
    citations: List[Dict[str, str]]
    confidence: float
    reasoning_path: List[str]


# ==================== Node Endpoints ====================


@router.post("/nodes", response_model=GraphNodeResponse)
async def create_node(request: GraphNodeRequest):
    """
    Create a new node in the knowledge graph.
    """
    try:
        from knowledge_graph import Neo4jService

        service = Neo4jService()
        node = await service.create_node(
            label=request.label,
            properties=request.properties,
        )

        return GraphNodeResponse(
            id=node.id,
            label=node.label,
            properties=node.properties,
            created_at=datetime.utcnow().isoformat(),
        )

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Knowledge graph service not available"
        )
    except Exception as e:
        logger.error(f"Error creating node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/{node_id}", response_model=GraphNodeResponse)
async def get_node(node_id: str):
    """
    Get a node by ID.
    """
    try:
        from knowledge_graph import Neo4jService

        service = Neo4jService()
        node = await service.get_node(node_id)

        if not node:
            raise HTTPException(status_code=404, detail="Node not found")

        return GraphNodeResponse(
            id=node.id,
            label=node.label,
            properties=node.properties,
        )

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Knowledge graph service not available"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes", response_model=List[GraphNodeResponse])
async def list_nodes(
    label: Optional[str] = Query(None, description="Filter by label"),
    property_filter: Optional[str] = Query(None, description="Property filter as JSON"),
    limit: int = Query(50, ge=1, le=500),
):
    """
    List nodes with optional filters.
    """
    try:
        from knowledge_graph import Neo4jService
        import json

        service = Neo4jService()

        filters = {}
        if property_filter:
            filters = json.loads(property_filter)

        nodes = await service.list_nodes(
            label=label,
            filters=filters,
            limit=limit,
        )

        return [
            GraphNodeResponse(
                id=n.id,
                label=n.label,
                properties=n.properties,
            )
            for n in nodes
        ]

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Knowledge graph service not available"
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid property_filter JSON")
    except Exception as e:
        logger.error(f"Error listing nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str):
    """
    Delete a node and its relationships.
    """
    try:
        from knowledge_graph import Neo4jService

        service = Neo4jService()
        await service.delete_node(node_id)

        return {
            "status": "deleted",
            "node_id": node_id,
            "deleted_at": datetime.utcnow().isoformat(),
        }

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Knowledge graph service not available"
        )
    except Exception as e:
        logger.error(f"Error deleting node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Relationship Endpoints ====================


@router.post("/relationships", response_model=GraphRelationshipResponse)
async def create_relationship(request: GraphRelationshipRequest):
    """
    Create a relationship between two nodes.
    """
    try:
        from knowledge_graph import Neo4jService

        service = Neo4jService()
        rel = await service.create_relationship(
            from_node_id=request.from_node_id,
            to_node_id=request.to_node_id,
            relationship_type=request.relationship_type,
            properties=request.properties,
        )

        return GraphRelationshipResponse(
            id=rel.id,
            from_node=GraphNodeResponse(
                id=rel.from_node.id,
                label=rel.from_node.label,
                properties=rel.from_node.properties,
            ),
            to_node=GraphNodeResponse(
                id=rel.to_node.id,
                label=rel.to_node.label,
                properties=rel.to_node.properties,
            ),
            relationship_type=rel.relationship_type,
            properties=rel.properties,
        )

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Knowledge graph service not available"
        )
    except Exception as e:
        logger.error(f"Error creating relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/{node_id}/relationships")
async def get_node_relationships(
    node_id: str,
    direction: str = Query("both", description="in, out, or both"),
    relationship_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get relationships for a node.
    """
    try:
        from knowledge_graph import Neo4jService

        service = Neo4jService()
        relationships = await service.get_relationships(
            node_id=node_id,
            direction=direction,
            relationship_type=relationship_type,
            limit=limit,
        )

        return {
            "node_id": node_id,
            "relationships": [
                {
                    "id": r.id,
                    "type": r.relationship_type,
                    "direction": r.direction,
                    "connected_node": {
                        "id": r.connected_node.id,
                        "label": r.connected_node.label,
                    },
                    "properties": r.properties,
                }
                for r in relationships
            ],
            "count": len(relationships),
        }

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Knowledge graph service not available"
        )
    except Exception as e:
        logger.error(f"Error getting relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Search & Query Endpoints ====================


@router.post("/search", response_model=GraphSearchResponse)
async def search_graph(request: GraphSearchRequest):
    """
    Search the knowledge graph with natural language queries.

    Returns relevant nodes, relationships, and paths.
    """
    import time

    start_time = time.time()

    try:
        from knowledge_graph import GraphRAGService

        service = GraphRAGService()
        result = await service.search(
            query=request.query,
            node_types=request.node_types,
            max_depth=request.max_depth,
            limit=request.limit,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return GraphSearchResponse(
            query=request.query,
            nodes=[
                GraphNodeResponse(
                    id=n.id,
                    label=n.label,
                    properties=n.properties,
                )
                for n in result.nodes
            ],
            relationships=result.relationships,
            paths=result.paths,
            total_results=len(result.nodes),
            search_time_ms=elapsed_ms,
        )

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Knowledge graph service not available"
        )
    except Exception as e:
        logger.error(f"Graph search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/cypher")
async def execute_cypher_query(
    query: str = Body(..., embed=True, description="Cypher query"),
    parameters: Optional[Dict[str, Any]] = Body(None, embed=True),
):
    """
    Execute a raw Cypher query (for advanced users).

    ⚠️ Use with caution - queries are validated but not sandboxed.
    """
    try:
        from knowledge_graph import Neo4jService

        service = Neo4jService()

        # Basic validation to prevent destructive queries
        query_upper = query.upper()
        if any(kw in query_upper for kw in ["DELETE", "DETACH", "DROP", "REMOVE"]):
            raise HTTPException(
                status_code=403,
                detail="Destructive queries not allowed via this endpoint",
            )

        result = await service.execute_query(query, parameters or {})

        return {
            "query": query,
            "result": result,
            "executed_at": datetime.utcnow().isoformat(),
        }

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Knowledge graph service not available"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cypher query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Graph RAG Endpoints ====================


@router.post("/rag", response_model=GraphRAGResponse)
async def graph_rag_query(
    query: str = Body(..., embed=True),
    user_id: Optional[str] = Body(None, embed=True),
    include_reasoning: bool = Body(True, embed=True),
):
    """
    Query using graph-enhanced RAG.

    Combines knowledge graph traversal with RAG for more accurate,
    explainable answers about medical relationships.
    """
    try:
        from knowledge_graph import GraphRAGService

        service = GraphRAGService()
        result = await service.rag_query(
            query=query,
            user_id=user_id,
            include_reasoning=include_reasoning,
        )

        return GraphRAGResponse(
            answer=result.answer,
            graph_context=result.graph_context,
            citations=result.citations,
            confidence=result.confidence,
            reasoning_path=result.reasoning_path if include_reasoning else [],
        )

    except ImportError:
        raise HTTPException(status_code=503, detail="Graph RAG service not available")
    except Exception as e:
        logger.error(f"Graph RAG error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Statistics & Health ====================


@router.get("/stats")
async def get_graph_stats():
    """
    Get knowledge graph statistics.
    """
    try:
        from knowledge_graph import Neo4jService

        service = Neo4jService()
        stats = await service.get_stats()

        return {
            "total_nodes": stats.total_nodes,
            "total_relationships": stats.total_relationships,
            "node_labels": stats.node_labels,
            "relationship_types": stats.relationship_types,
            "database_size_mb": stats.database_size_mb,
            "last_updated": stats.last_updated,
        }

    except ImportError:
        raise HTTPException(
            status_code=503, detail="Knowledge graph service not available"
        )
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def graph_health():
    """
    Check knowledge graph service health.
    """
    try:
        from knowledge_graph import Neo4jService

        service = Neo4jService()
        is_connected = await service.health_check()

        return {
            "status": "healthy" if is_connected else "unhealthy",
            "neo4j_connected": is_connected,
            "checked_at": datetime.utcnow().isoformat(),
        }

    except ImportError:
        return {
            "status": "unavailable",
            "neo4j_connected": False,
            "error": "Knowledge graph module not installed",
            "checked_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "neo4j_connected": False,
            "error": str(e),
            "checked_at": datetime.utcnow().isoformat(),
        }
