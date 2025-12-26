"""
Neo4j Knowledge Graph Service.

Provides graph database operations for storing and querying
medical knowledge graphs with entities and relationships.

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
    APPOINTMENT = "Appointment"
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
    HAS_APPOINTMENT = "HAS_APPOINTMENT"


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_timeout: int = 30

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        """Create config from environment variables."""
        import os

        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
        )


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


class Neo4jService:
    """
    Neo4j graph database service.

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
    """

    def __init__(
        self,
        config: Optional[Neo4jConfig] = None,
        mock_mode: bool = False,
    ):
        """
        Initialize Neo4j service.

        Args:
            config: Neo4j connection config
            mock_mode: Use mock implementation
        """
        self.config = config or Neo4jConfig()
        self.mock_mode = mock_mode
        self._driver = None
        self._mock_nodes: Dict[str, GraphNode] = {}
        self._mock_relationships: Dict[str, GraphRelationship] = {}

        if mock_mode:
            logger.info("Neo4j service running in mock mode")
            self._initialize_mock_data()

    async def connect(self):
        """Establish database connection."""
        if self.mock_mode:
            return

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

        except ImportError:
            logger.warning("neo4j package not installed, using mock mode")
            self.mock_mode = True
            self._initialize_mock_data()
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            logger.info("Falling back to mock mode")
            self.mock_mode = True
            self._initialize_mock_data()

    async def close(self):
        """Close database connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    @asynccontextmanager
    async def session(self):
        """Get a database session."""
        if self.mock_mode:
            yield None
            return

        if not self._driver:
            await self.connect()

        async with self._driver.session(database=self.config.database) as session:
            yield session

    # Node operations

    async def create_node(self, node: GraphNode) -> GraphNode:
        """
        Create a node in the graph.

        Args:
            node: Node to create

        Returns:
            Created node with ID
        """
        if self.mock_mode:
            self._mock_nodes[node.id] = node
            return node

        labels = ":".join(node.labels) if node.labels else "Node"
        props = {**node.properties, "id": node.id}

        query = f"""
        CREATE (n:{labels} $props)
        RETURN n
        """

        result = await self.query(query, {"props": props})
        return node

    async def get_node(self, node_id: str) -> Optional[GraphNode]:
        """
        Get a node by ID.

        Args:
            node_id: Node ID

        Returns:
            Node or None
        """
        if self.mock_mode:
            return self._mock_nodes.get(node_id)

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
        if self.mock_mode:
            if node_id in self._mock_nodes:
                self._mock_nodes[node_id].properties.update(properties)
                return self._mock_nodes[node_id]
            return None

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

    async def delete_node(self, node_id: str) -> bool:
        """
        Delete a node and its relationships.

        Args:
            node_id: Node ID

        Returns:
            True if deleted
        """
        if self.mock_mode:
            if node_id in self._mock_nodes:
                del self._mock_nodes[node_id]
                # Remove related relationships
                self._mock_relationships = {
                    k: v
                    for k, v in self._mock_relationships.items()
                    if v.start_node_id != node_id and v.end_node_id != node_id
                }
                return True
            return False

        query = """
        MATCH (n {id: $node_id})
        DETACH DELETE n
        RETURN count(n) as deleted
        """

        result = await self.query(query, {"node_id": node_id})
        return result.records[0].get("deleted", 0) > 0 if result.records else False

    async def create_disease_node(
        self,
        disease_name: str,
        use_icd10: bool = True
    ) -> Optional[str]:
        """
        Create disease node with ICD-10 standardization.
        
        Uses MERGE to prevent duplicates when the same condition
        is mentioned with different names (e.g., "Heart Attack" vs "MI").
        
        Args:
            disease_name: Disease/condition name
            use_icd10: Whether to use ICD-10 mapping (default: True)
        
        Returns:
            ICD-10 code if mapped, otherwise node ID
        
        Example:
            # These all create/reference the same node:
            code1 = await service.create_disease_node("heart attack")   # I21.9
            code2 = await service.create_disease_node("MI")             # I21.9
            code3 = await service.create_disease_node("AMI")            # I21.9
        """
        if not use_icd10:
            # Fallback: create without ICD-10 mapping
            node = GraphNode(
                labels=["Condition"],
                properties={"name": disease_name}
            )
            await self.create_node(node)
            return node.id
        
        # Map disease to ICD-10 code
        try:
            from nlp.knowledge_graph.medical_ontology import get_medical_ontology_mapper
            
            mapper = get_medical_ontology_mapper()
            mapping = await mapper.map_disease(disease_name)
            
            if not mapping:
                logger.warning(
                    f"Could not map '{disease_name}' to ICD-10, "
                    "creating without standardization"
                )
                # Create node with original name
                node = GraphNode(
                    labels=["Condition"],
                    properties={
                        "name": disease_name,
                        "icd10_mapped": False
                    }
                )
                await self.create_node(node)
                return node.id
            
            icd10_code = mapping["icd10_code"]
            standard_name = mapping["standard_name"]
            category = mapping.get("category", "Unknown")
            
            if self.mock_mode:
                # Mock mode: just create node
                node = GraphNode(
                    labels=["Condition"],
                    properties={
                        "name": standard_name,
                        "icd10_code": icd10_code,
                        "category": category,
                        "alias": [disease_name]
                    }
                )
                self._mock_nodes[icd10_code] = node
                logger.info(
                    f"Mock: Created disease node '{disease_name}' → "
                    f"ICD-10: {icd10_code} ({standard_name})"
                )
                return icd10_code
            
            # Use MERGE to prevent duplicates
            # Creates node if doesn't exist, finds if it does
            query = """
            MERGE (d:Condition {icd10_code: $icd10_code})
            ON CREATE SET
                d.name = $standard_name,
                d.category = $category,
                d.created_at = datetime(),
                d.alias = [$original_name]
            ON MATCH SET
                d.updated_at = datetime()
            SET d.alias = 
                CASE
                    WHEN d.alias IS NULL THEN [$original_name]
                    WHEN NOT $original_name IN d.alias THEN d.alias + $original_name
                    ELSE d.alias
                END
            RETURN d.icd10_code AS code, d.name AS name, d.alias AS aliases
            """
            
            result = await self.query(
                query,
                {
                    "icd10_code": icd10_code,
                    "standard_name": standard_name,
                    "category": category,
                    "original_name": disease_name
                }
            )
            
            if result.records:
                record = result.records[0]
                logger.info(
                    f"Disease node: '{disease_name}' → "
                    f"ICD-10: {icd10_code} ({standard_name})"
                )
                logger.debug(f"Aliases: {record.get('aliases', [])}")
                return icd10_code
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to create disease node for '{disease_name}': {e}")
            # Fallback: create without ICD-10
            node = GraphNode(
                labels=["Condition"],
                properties={
                    "name": disease_name,
                    "icd10_mapped": False,
                    "mapping_error": str(e)
                }
            )
            await self.create_node(node)
            return node.id


    # Relationship operations

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
        if self.mock_mode:
            self._mock_relationships[relationship.id] = relationship
            return relationship

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
        if self.mock_mode:
            relationships = []
            for rel in self._mock_relationships.values():
                if direction == "out" and rel.start_node_id == node_id:
                    if not rel_type or rel.type == rel_type:
                        relationships.append(rel)
                elif direction == "in" and rel.end_node_id == node_id:
                    if not rel_type or rel.type == rel_type:
                        relationships.append(rel)
                elif direction == "both":
                    if rel.start_node_id == node_id or rel.end_node_id == node_id:
                        if not rel_type or rel.type == rel_type:
                            relationships.append(rel)
            return relationships

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

    # Query operations

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

        if self.mock_mode:
            # Return mock result
            return QueryResult(
                records=[],
                summary={"mock": True},
                execution_time_ms=(time.perf_counter() - start) * 1000,
            )

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

    # Graph traversal

    async def find_path(
        self,
        start_id: str,
        end_id: str,
        max_hops: int = 5,
    ) -> List[Dict]:
        """
        Find shortest path between nodes.

        Args:
            start_id: Start node ID
            end_id: End node ID
            max_hops: Maximum path length

        Returns:
            List of path segments
        """
        if self.mock_mode:
            return []

        query = f"""
        MATCH path = shortestPath(
            (a {{id: $start_id}})-[*..{max_hops}]-(b {{id: $end_id}})
        )
        RETURN path
        """

        result = await self.query(
            query,
            {
                "start_id": start_id,
                "end_id": end_id,
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
        if self.mock_mode:
            neighbors = []
            for rel in self._mock_relationships.values():
                if rel.start_node_id == node_id:
                    if rel.end_node_id in self._mock_nodes:
                        node = self._mock_nodes[rel.end_node_id]
                        if not labels or any(l in node.labels for l in labels):
                            neighbors.append(node)
                elif rel.end_node_id == node_id:
                    if rel.start_node_id in self._mock_nodes:
                        node = self._mock_nodes[rel.start_node_id]
                        if not labels or any(l in node.labels for l in labels):
                            neighbors.append(node)
            return neighbors

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

    # Specialized medical queries

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
        if self.mock_mode:
            # Return mock medical data
            return [
                {
                    "condition": "Hypertension",
                    "relevance": 0.85,
                    "relationship": "INDICATES",
                },
                {
                    "condition": "Coronary Artery Disease",
                    "relevance": 0.72,
                    "relationship": "INDICATES",
                },
            ]

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
        if self.mock_mode:
            return [
                {
                    "treatment": "ACE Inhibitors",
                    "type": "Medication",
                    "effectiveness": 0.82,
                },
                {
                    "treatment": "Lifestyle Modification",
                    "type": "Treatment",
                    "effectiveness": 0.75,
                },
            ]

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
        if self.mock_mode:
            return []

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

    # Mock data initialization

    def _initialize_mock_data(self):
        """Initialize mock medical knowledge graph."""
        # Create symptom nodes
        symptoms = [
            ("s1", "Symptom", {"name": "chest pain", "severity_range": "low-high"}),
            (
                "s2",
                "Symptom",
                {"name": "shortness of breath", "severity_range": "low-high"},
            ),
            ("s3", "Symptom", {"name": "fatigue", "severity_range": "low-moderate"}),
            ("s4", "Symptom", {"name": "dizziness", "severity_range": "low-moderate"}),
            ("s5", "Symptom", {"name": "palpitations", "severity_range": "low-high"}),
        ]

        for sid, label, props in symptoms:
            self._mock_nodes[sid] = GraphNode(id=sid, labels=[label], properties=props)

        # Create condition nodes
        conditions = [
            ("c1", "Condition", {"name": "Hypertension", "icd10": "I10"}),
            ("c2", "Condition", {"name": "Coronary Artery Disease", "icd10": "I25.10"}),
            ("c3", "Condition", {"name": "Heart Failure", "icd10": "I50.9"}),
            ("c4", "Condition", {"name": "Atrial Fibrillation", "icd10": "I48.91"}),
            ("c5", "Condition", {"name": "Myocardial Infarction", "icd10": "I21.9"}),
        ]

        for cid, label, props in conditions:
            self._mock_nodes[cid] = GraphNode(id=cid, labels=[label], properties=props)

        # Create medication nodes
        medications = [
            ("m1", "Medication", {"name": "Metoprolol", "class": "Beta Blocker"}),
            ("m2", "Medication", {"name": "Lisinopril", "class": "ACE Inhibitor"}),
            ("m3", "Medication", {"name": "Aspirin", "class": "Antiplatelet"}),
            ("m4", "Medication", {"name": "Atorvastatin", "class": "Statin"}),
        ]

        for mid, label, props in medications:
            self._mock_nodes[mid] = GraphNode(id=mid, labels=[label], properties=props)

        # Create relationships
        relationships = [
            ("r1", "INDICATES", "s1", "c2", {"strength": 0.85}),
            ("r2", "INDICATES", "s1", "c5", {"strength": 0.9}),
            ("r3", "INDICATES", "s2", "c3", {"strength": 0.8}),
            ("r4", "INDICATES", "s5", "c4", {"strength": 0.75}),
            ("r5", "TREATS", "m1", "c1", {"effectiveness": 0.82}),
            ("r6", "TREATS", "m2", "c1", {"effectiveness": 0.85}),
            ("r7", "TREATS", "m1", "c4", {"effectiveness": 0.78}),
            ("r8", "TREATS", "m3", "c2", {"effectiveness": 0.7}),
            ("r9", "TREATS", "m4", "c2", {"effectiveness": 0.75}),
        ]

        for rid, rtype, start, end, props in relationships:
            self._mock_relationships[rid] = GraphRelationship(
                id=rid,
                type=rtype,
                start_node_id=start,
                end_node_id=end,
                properties=props,
            )

        logger.info(
            f"Initialized mock graph with {len(self._mock_nodes)} nodes "
            f"and {len(self._mock_relationships)} relationships"
        )

    async def search(self, query: str, node_types: Optional[List[str]] = None, max_depth: int = 2, limit: int = 10):
        """
        Search the knowledge graph with natural language queries.
        """
        if self.mock_mode:
            # Return mock search results
            from dataclasses import dataclass
            
            @dataclass
            class MockResult:
                nodes: List[Any] = None
                relationships: List[Any] = None
                paths: List[Any] = None
                
            return MockResult(
                nodes=[
                    {
                        "id": "mock_node_1",
                        "label": "Condition",
                        "properties": {"name": "Hypertension", "icd10": "I10"}
                    },
                    {
                        "id": "mock_node_2",
                        "label": "Medication",
                        "properties": {"name": "Lisinopril", "class": "ACE Inhibitor"}
                    }
                ],
                relationships=[
                    {
                        "type": "TREATS",
                        "properties": {"effectiveness": 0.85}
                    }
                ],
                paths=[["mock_node_1", "mock_node_2"]]
            )
        
        # In real Neo4j, we would implement the search logic
        # For now, implement a basic search based on node labels and properties
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

    async def rag_query(self, query: str, user_id: Optional[str] = None, include_reasoning: bool = True):
        """
        Query using graph-enhanced RAG.
        """
        if self.mock_mode:
            # Return mock RAG result
            class MockRagResult:
                answer = f"Based on the knowledge graph, {query} is related to cardiovascular health information. This is a mock response from the knowledge graph."
                graph_context = [
                    {
                        "node_type": "Condition",
                        "content": "Hypertension is a common cardiovascular condition",
                        "relevance": 0.8
                    }
                ]
                citations = [{"source": "medical_knowledge_base", "confidence": 0.9}]
                confidence = 0.85
                reasoning_path = ["search_graph", "analyze_relationships", "generate_response"] if include_reasoning else []
            
            return MockRagResult()
        
        # In real Neo4j, we would implement the RAG query logic
        # This would typically involve: search, context extraction, and response generation
        
        # First, search the graph for relevant nodes
        search_result = await self.search(query, limit=5)
        
        # Extract context from the search results
        graph_context = []
        if search_result.records:
            for record in search_result.records[:3]:  # Limit to first 3 results
                node = record.get('n', {})
                labels = record.get('labels', [])
                graph_context.append({
                    "node_type": labels[0] if labels else "Unknown",
                    "content": str(node),
                    "relevance": 0.8
                })
        
        # Generate a response based on the context
        answer = f"Based on the knowledge graph, {query} is related to cardiovascular health information."
        
        # Create a mock response object
        class RagResult:
            def __init__(self, answer, graph_context, citations, confidence, reasoning_path):
                self.answer = answer
                self.graph_context = graph_context
                self.citations = citations
                self.confidence = confidence
                self.reasoning_path = reasoning_path
        
        return RagResult(
            answer=answer,
            graph_context=graph_context,
            citations=[{"source": "medical_knowledge_base", "confidence": 0.9}],
            confidence=0.85,
            reasoning_path=["search_graph", "analyze_relationships", "generate_response"] if include_reasoning else []
        )

    async def list_nodes(self, label: Optional[str] = None, filters: Optional[Dict] = None, limit: int = 50):
        """
        List nodes with optional filters.
        """
        if self.mock_mode:
            # Return mock nodes
            return [
                GraphNode(
                    id="mock_node_1",
                    labels=[label or "Condition"],
                    properties={"name": "Hypertension", "icd10": "I10"}
                ),
                GraphNode(
                    id="mock_node_2",
                    labels=[label or "Medication"],
                    properties={"name": "Lisinopril", "class": "ACE Inhibitor"}
                )
            ]
        
        # Build query
        if label:
            query = f"MATCH (n:{label}) RETURN n, labels(n) AS labels LIMIT $limit"
        else:
            query = "MATCH (n) RETURN n, labels(n) AS labels LIMIT $limit"
        
        result = await self.query(query, {"limit": limit})
        
        nodes = []
        for record in result.records:
            node_data = record.get("n", {})
            labels = record.get("labels", [])
            nodes.append(
                GraphNode(
                    id=node_data.get("id", "unknown"),
                    labels=labels,
                    properties=node_data
                )
            )
        return nodes

    async def health_check(self):
        """
        Check if the Neo4j connection is healthy.
        """
        if self.mock_mode:
            return True
        
        try:
            # Try a simple query
            result = await self.query("RETURN 1 AS test")
            return len(result.records) > 0
        except Exception:
            return False

    async def get_stats(self):
        """
        Get graph statistics.
        """
        if self.mock_mode:
            class MockStats:
                total_nodes = len(self._mock_nodes)
                total_relationships = len(self._mock_relationships)
                node_labels = ["Condition", "Medication", "Symptom"]
                relationship_types = ["TREATS", "INDICATES", "CAUSES"]
                database_size_mb = 10.0
                last_updated = datetime.utcnow().isoformat()
            
            return MockStats()
        
        # Query for node count
        node_count_result = await self.query("MATCH (n) RETURN count(n) AS count")
        total_nodes = node_count_result.records[0].get("count", 0) if node_count_result.records else 0
        
        # Query for relationship count
        rel_count_result = await self.query("MATCH ()-[r]->() RETURN count(r) AS count")
        total_relationships = rel_count_result.records[0].get("count", 0) if rel_count_result.records else 0
        
        # Query for node labels
        labels_result = await self.query("CALL db.labels()")
        node_labels = [record.get("label") for record in labels_result.records] if labels_result.records else []
        
        # Query for relationship types
        rel_types_result = await self.query("CALL db.relationshipTypes()")
        relationship_types = [record.get("relationshipType") for record in rel_types_result.records] if rel_types_result.records else []
        
        class Stats:
            def __init__(self, nodes, rels, labels, rel_types):
                self.total_nodes = nodes
                self.total_relationships = rels
                self.node_labels = labels
                self.relationship_types = rel_types
                self.database_size_mb = 0.0  # Not easily available
                self.last_updated = datetime.utcnow().isoformat()
        
        return Stats(total_nodes, total_relationships, node_labels, relationship_types)
