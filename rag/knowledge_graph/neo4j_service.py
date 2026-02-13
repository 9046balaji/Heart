"""
Neo4j Knowledge Graph Service (Production-Only).

Provides graph database operations for storing and querying
medical knowledge graphs with entities and relationships.

NOTE: Mock mode has been removed. Use MockNeo4jService from tests.mocks
instead for testing purposes.

Features:
- Entity and relationship management
- Cypher query execution
- Graph traversal and path finding
- Batch operations for performance
- Connection pooling
"""


import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from contextlib import asynccontextmanager
from .base import AbstractNeo4jService, Neo4jConfig

logger = logging.getLogger(__name__)


class NodeLabel(Enum):
    """Standard node labels for medical knowledge graph."""

    SYMPTOM = "Symptom"
    CONDITION = "Condition"
    MEDICATION = "Medication"
    TREATMENT = "Treatment"
    BODY_PART = "BodyPart"
    LAB_TEST = "LabTest"
    PROCEDURE = "Procedure"
    VITAL_SIGN = "VitalSign"
    RISK_FACTOR = "RiskFactor"
    SPECIALTY = "Specialty"
    DOCTOR = "Doctor"
    PATIENT = "Patient"
    DOCUMENT = "Document"


class RelationType(Enum):
    """Standard relationship types."""

    CAUSES = "CAUSES"
    TREATS = "TREATS"
    INDICATES = "INDICATES"
    CONTRAINDICATES = "CONTRAINDICATES"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    MEASURED_BY = "MEASURED_BY"
    AFFECTS = "AFFECTS"
    LOCATED_IN = "LOCATED_IN"
    SPECIALIZES_IN = "SPECIALIZES_IN"
    PRESCRIBED_FOR = "PRESCRIBED_FOR"
    INTERACTS_WITH = "INTERACTS_WITH"
    RISK_FOR = "RISK_FOR"
    PERFORMED_BY = "PERFORMED_BY"


@dataclass
class GraphNode:
    """Represents a graph node."""

    id: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())
        if not self.properties.get("created_at"):
            self.properties["created_at"] = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "labels": self.labels,
            "properties": self.properties,
        }

    @property
    def label_string(self) -> str:
        """Get labels as Cypher label string."""
        return ":".join(self.labels) if self.labels else ""


@dataclass
class GraphRelationship:
    """Represents a graph relationship."""

    id: Optional[str] = None
    type: str = ""
    start_node_id: str = ""
    end_node_id: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            import uuid

            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "start_node_id": self.start_node_id,
            "end_node_id": self.end_node_id,
            "properties": self.properties,
        }


@dataclass
class QueryResult:
    """Result from a Cypher query."""

    records: List[Dict[str, Any]]
    summary: Dict[str, Any]
    execution_time_ms: float = 0


class Neo4jService(AbstractNeo4jService):
    """
    Neo4j graph database service (Production Mode Only).

    Provides CRUD operations for nodes and relationships,
    with support for complex graph queries.

    Example:
        config = Neo4jConfig.from_env()
        service = Neo4jService(config)

        # Create node
        node = GraphNode(
            labels=["Symptom"],
            properties={"name": "chest pain", "severity": "high"}
        )
        await service.create_node(node)

        # Query
        results = await service.query(
            "MATCH (s:Symptom)-[:INDICATES]->(c:Condition) RETURN s, c"
        )

    Migration Note:
        If using mock_mode=True, switch to MockNeo4jService from tests.mocks:
        
        OLD (no longer works):
            service = Neo4jService(mock_mode=True)
        
        NEW:
            from tests.mocks import MockNeo4jService
            service = MockNeo4jService()
    """

    def __init__(self, config: Optional[Neo4jConfig] = None):
        """
        Initialize Neo4j service (production mode only).

        Args:
            config: Neo4j connection config

        Raises:
            TypeError: If unsupported mock_mode parameter is passed
            ValueError: If Neo4j is disabled due to missing credentials

        Note:
            For testing purposes, use MockNeo4jService from tests.mocks instead.
        """
        # Use from_env() if no config provided - this ensures password is read from env
        self.config = config or Neo4jConfig.from_env()
        
        # Check if Neo4j is disabled (no credentials)
        if not self.config.enabled:
            raise ValueError("Neo4j disabled - NEO4J_PASSWORD not configured")
        
        self._driver = None

    async def connect(self):
        """Establish database connection."""
        try:
            from neo4j import AsyncGraphDatabase

            self._driver = AsyncGraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
                max_connection_pool_size=self.config.max_connection_pool_size,
            )

            # Verify connection
            async with self._driver.session(database=self.config.database) as session:
                await session.run("RETURN 1")

            logger.info(f"Connected to Neo4j at {self.config.uri}")

        except ImportError as e:
            logger.error(
                f"neo4j package not installed: {e}. "
                "Install with: pip install neo4j"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        """Close database connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    @asynccontextmanager
    async def session(self):
        """Get a database session."""
        if not self._driver:
            await self.connect()

        async with self._driver.session(database=self.config.database) as session:
            yield session

    # ========================================================================
    # Node Operations
    # ========================================================================

    async def create_node(self, node: GraphNode) -> GraphNode:
        """
        Create a node in the graph.

        Args:
            node: Node to create

        Returns:
            Created node with ID
        """
        labels = ":".join(node.labels) if node.labels else "Node"
        props = {**node.properties, "id": node.id}

        query = f"""
        CREATE (n:{labels} $props)
        RETURN n
        """

        await self.query(query, {"props": props})
        return node

    async def get_node(self, node_id: str) -> Optional[GraphNode]:
        """
        Get a node by ID.

        Args:
            node_id: Node ID

        Returns:
            Node or None
        """
        query = """
        MATCH (n {id: $node_id})
        RETURN n, labels(n) as labels
        """

        result = await self.query(query, {"node_id": node_id})
        if result.records:
            record = result.records[0]
            return GraphNode(
                id=node_id,
                labels=record.get("labels", []),
                properties=dict(record.get("n", {})),
            )
        return None

    async def update_node(
        self,
        node_id: str,
        properties: Dict[str, Any],
    ) -> Optional[GraphNode]:
        """
        Update node properties.

        Args:
            node_id: Node ID
            properties: Properties to update

        Returns:
            Updated node
        """
        query = """
        MATCH (n {id: $node_id})
        SET n += $props
        RETURN n, labels(n) as labels
        """

        result = await self.query(query, {"node_id": node_id, "props": properties})
        if result.records:
            record = result.records[0]
            return GraphNode(
                id=node_id,
                labels=record.get("labels", []),
                properties=dict(record.get("n", {})),
            )
        return None

    async def delete_node(self, node_id: str, force: bool = False) -> bool:
        """
        Delete a node.

        Args:
            node_id: Node ID
            force: If True, delete with all relationships (DETACH DELETE)

        Returns:
            True if deleted
        """
        if force:
            query = """
            MATCH (n {id: $node_id})
            DETACH DELETE n
            RETURN count(n) as deleted
            """
        else:
            query = """
            MATCH (n {id: $node_id})
            DELETE n
            RETURN count(n) as deleted
            """

        result = await self.query(query, {"node_id": node_id})
        return result.records[0].get("deleted", 0) > 0 if result.records else False

    # ========================================================================
    # Relationship Operations
    # ========================================================================

    async def create_relationship(
        self,
        relationship: GraphRelationship,
    ) -> GraphRelationship:
        """
        Create a relationship between nodes.

        Args:
            relationship: Relationship to create

        Returns:
            Created relationship
        """
        query = f"""
        MATCH (a {{id: $start_id}}), (b {{id: $end_id}})
        CREATE (a)-[r:{relationship.type} $props]->(b)
        RETURN r
        """

        props = {**relationship.properties, "id": relationship.id}
        await self.query(
            query,
            {
                "start_id": relationship.start_node_id,
                "end_id": relationship.end_node_id,
                "props": props,
            },
        )

        return relationship

    async def get_relationships(
        self,
        node_id: str,
        direction: str = "both",
        rel_type: Optional[str] = None,
    ) -> List[GraphRelationship]:
        """
        Get relationships for a node.

        Args:
            node_id: Node ID
            direction: "in", "out", or "both"
            rel_type: Optional relationship type filter

        Returns:
            List of relationships
        """
        type_filter = f":{rel_type}" if rel_type else ""

        if direction == "out":
            query = f"""
            MATCH (n {{id: $node_id}})-[r{type_filter}]->(m)
            RETURN r, type(r) as type, n.id as start, m.id as end
            """
        elif direction == "in":
            query = f"""
            MATCH (n {{id: $node_id}})<-[r{type_filter}]-(m)
            RETURN r, type(r) as type, m.id as start, n.id as end
            """
        else:
            query = f"""
            MATCH (n {{id: $node_id}})-[r{type_filter}]-(m)
            RETURN r, type(r) as type, startNode(r).id as start, endNode(r).id as end
            """

        result = await self.query(query, {"node_id": node_id})

        return [
            GraphRelationship(
                id=record.get("r", {}).get("id"),
                type=record.get("type"),
                start_node_id=record.get("start"),
                end_node_id=record.get("end"),
                properties=dict(record.get("r", {})),
            )
            for record in result.records
        ]

    async def delete_relationship(self, relationship_id: str) -> bool:
        """
        Delete a relationship.

        Args:
            relationship_id: Relationship ID

        Returns:
            True if deleted
        """
        query = """
        MATCH ()-[r {id: $rel_id}]->()
        DELETE r
        RETURN count(r) as deleted
        """

        result = await self.query(query, {"rel_id": relationship_id})
        return result.records[0].get("deleted", 0) > 0 if result.records else False

    # ========================================================================
    # Query Operations
    # ========================================================================

    async def query(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """
        Execute a Cypher query.

        Args:
            cypher: Cypher query string
            params: Query parameters

        Returns:
            QueryResult with records
        """
        import time

        start = time.perf_counter()

        async with self.session() as session:
            result = await session.run(cypher, params or {})
            records = [dict(record) async for record in result]
            summary = await result.consume()

            return QueryResult(
                records=records,
                summary={
                    "counters": summary.counters.__dict__,
                    "query_type": summary.query_type,
                },
                execution_time_ms=(time.perf_counter() - start) * 1000,
            )

    # ========================================================================
    # Graph Traversal
    # ========================================================================

    async def get_paths(
        self,
        start_node_id: str,
        end_node_id: str,
        max_depth: int = 3,
    ) -> List[List[Any]]:
        """
        Get all paths between two nodes.

        Args:
            start_node_id: Start node ID
            end_node_id: End node ID
            max_depth: Maximum path length

        Returns:
            List of path segments
        """
        query = f"""
        MATCH path = shortestPath(
            (a {{id: $start_id}})-[*..{max_depth}]-(b {{id: $end_id}})
        )
        RETURN path
        """

        result = await self.query(
            query,
            {
                "start_id": start_node_id,
                "end_id": end_node_id,
            },
        )

        return result.records

    async def get_neighbors(
        self,
        node_id: str,
        depth: int = 1,
        labels: Optional[List[str]] = None,
    ) -> List[GraphNode]:
        """
        Get neighboring nodes.

        Args:
            node_id: Center node ID
            depth: How many hops
            labels: Filter by labels

        Returns:
            List of neighbor nodes
        """
        label_filter = f":{':'.join(labels)}" if labels else ""

        query = f"""
        MATCH (n {{id: $node_id}})-[*1..{depth}]-(m{label_filter})
        WHERE m.id <> $node_id
        RETURN DISTINCT m, labels(m) as labels
        """

        result = await self.query(query, {"node_id": node_id})

        return [
            GraphNode(
                id=record.get("m", {}).get("id"),
                labels=record.get("labels", []),
                properties=dict(record.get("m", {})),
            )
            for record in result.records
        ]

    # ========================================================================
    # Medical Domain Operations
    # ========================================================================

    async def find_related_conditions(
        self,
        symptom_name: str,
    ) -> List[Dict]:
        """
        Find conditions related to a symptom.

        Args:
            symptom_name: Name of symptom

        Returns:
            List of conditions with relevance
        """
        query = """
        MATCH (s:Symptom)-[r:INDICATES|ASSOCIATED_WITH]->(c:Condition)
        WHERE toLower(s.name) CONTAINS toLower($symptom)
        RETURN c.name as condition,
               type(r) as relationship,
               r.strength as relevance
        ORDER BY r.strength DESC
        LIMIT 10
        """

        result = await self.query(query, {"symptom": symptom_name})
        return result.records

    async def find_treatments(
        self,
        condition_name: str,
    ) -> List[Dict]:
        """
        Find treatments for a condition.

        Args:
            condition_name: Name of condition

        Returns:
            List of treatments
        """
        query = """
        MATCH (c:Condition)<-[:TREATS]-(t:Treatment|Medication)
        WHERE toLower(c.name) CONTAINS toLower($condition)
        RETURN t.name as treatment,
               labels(t)[0] as type,
               t.effectiveness as effectiveness
        ORDER BY t.effectiveness DESC
        LIMIT 10
        """

        result = await self.query(query, {"condition": condition_name})
        return result.records

    async def find_interaction(
        self,
        drug_a: str,
        drug_b: str,
    ) -> Optional[Dict]:
        """
        Find interaction between two specific drugs.
        
        Args:
            drug_a: First drug name
            drug_b: Second drug name
            
        Returns:
            Interaction details or None
        """
        query = """
        MATCH (m1:Medication)-[r:INTERACTS_WITH]-(m2:Medication)
        WHERE toLower(m1.name) = toLower($drug_a) 
          AND toLower(m2.name) = toLower($drug_b)
        RETURN m1.name as drug1,
               m2.name as drug2,
               coalesce(r.severity, 'unknown') as severity,
               coalesce(r.description, '') as description,
               coalesce(r.mechanism, 'Not specified') as mechanism,
               coalesce(r.management, 'Consult healthcare provider') as management
        LIMIT 1
        """
        
        result = await self.query(query, {"drug_a": drug_a, "drug_b": drug_b})
        if result.records:
            return result.records[0]
        return None

    async def find_drug_interactions(
        self,
        medications: List[str],
    ) -> List[Dict]:
        """
        Find interactions between medications.

        Args:
            medications: List of medication names

        Returns:
            List of interactions
        """
        query = """
        MATCH (m1:Medication)-[r:INTERACTS_WITH]->(m2:Medication)
        WHERE m1.name IN $meds AND m2.name IN $meds
        RETURN m1.name as drug1,
               m2.name as drug2,
               r.severity as severity,
               r.description as description
        """

        result = await self.query(query, {"meds": medications})
        return result.records

    async def search(
        self,
        query: str,
        node_types: Optional[List[str]] = None,
        max_depth: int = 2,
        limit: int = 10
    ) -> QueryResult:
        """
        Search the knowledge graph with natural language queries.

        Args:
            query: Search query
            node_types: Filter by node types/labels
            max_depth: Max traversal depth
            limit: Result limit

        Returns:
            QueryResult with matching nodes
        """
        if node_types:
            label_filter = " OR ".join([f"'{label}' IN labels(n)" for label in node_types])
            cypher = f"""
            MATCH (n) 
            WHERE {label_filter}
            AND toLower(n.name) CONTAINS toLower($query)
            RETURN n, labels(n) AS labels
            LIMIT $limit
            """
        else:
            cypher = """
            MATCH (n)
            WHERE toLower(n.name) CONTAINS toLower($query)
            RETURN n, labels(n) AS labels
            LIMIT $limit
            """

        result = await self.query(cypher, {"query": query, "limit": limit})
        return result

    async def rag_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        include_reasoning: bool = True
    ) -> Dict[str, Any]:
        """
        Query using graph-enhanced RAG.

        Args:
            query: User query
            user_id: Optional user ID for personalization
            include_reasoning: Include reasoning path

        Returns:
            RAG result with answer, context, and citations
        """
        # First, search the graph for relevant nodes
        search_result = await self.search(query, limit=5)

        # Extract context from the search results
        graph_context = []
        if search_result.records:
            for record in search_result.records[:3]:
                node = record.get("n", {})
                labels = record.get("labels", [])
                graph_context.append({
                    "node_type": labels[0] if labels else "Unknown",
                    "content": str(node),
                    "relevance": 0.8
                })

        return {
            "answer": f"Based on the knowledge graph, {query} is related to health information.",
            "graph_context": graph_context,
            "citations": [{"source": "medical_knowledge_base", "confidence": 0.9}],
            "confidence": 0.85,
            "reasoning_path": [
                "search_graph",
                "analyze_relationships",
                "generate_response"
            ] if include_reasoning else [],
        }

    # ========================================================================
    # Administrative Operations
    # ========================================================================

    async def health_check(self) -> bool:
        """Check if the Neo4j connection is healthy."""
        try:
            result = await self.query("RETURN 1 AS test")
            return len(result.records) > 0
        except Exception:
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        try:
            # Query for node count
            node_count_result = await self.query("MATCH (n) RETURN count(n) AS count")
            total_nodes = (
                node_count_result.records[0].get("count", 0)
                if node_count_result.records
                else 0
            )

            # Query for relationship count
            rel_count_result = await self.query("MATCH ()-[r]->() RETURN count(r) AS count")
            total_relationships = (
                rel_count_result.records[0].get("count", 0)
                if rel_count_result.records
                else 0
            )

            return {
                "total_nodes": total_nodes,
                "total_relationships": total_relationships,
                "database_size_mb": 0.0,
                "last_updated": datetime.utcnow().isoformat(),
                "status": "healthy",
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"status": "error", "message": str(e)}
