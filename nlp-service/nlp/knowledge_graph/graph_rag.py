"""
Graph-Enhanced RAG Service.

Combines traditional vector-based RAG with knowledge graph
traversal for richer context and better reasoning.

Features:
- Hybrid search: vector + graph
- Entity extraction and linking
- Context enrichment from graph
- Reasoning path construction
- Relevance scoring with graph signals
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .neo4j_service import (
    Neo4jService,
    NodeLabel,
)

logger = logging.getLogger(__name__)


@dataclass
class GraphSearchResult:
    """Result from graph-enhanced search."""

    entity: str
    entity_type: str
    relevance_score: float
    context: str
    related_entities: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_path: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "entity": self.entity,
            "entity_type": self.entity_type,
            "relevance_score": self.relevance_score,
            "context": self.context,
            "related_entities": self.related_entities,
            "reasoning_path": self.reasoning_path,
        }


@dataclass
class GraphContext:
    """Context assembled from graph traversal."""

    primary_entities: List[GraphSearchResult]
    supporting_facts: List[str]
    entity_relationships: List[Dict[str, str]]
    confidence_score: float
    graph_depth: int
    total_nodes_visited: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "primary_entities": [e.to_dict() for e in self.primary_entities],
            "supporting_facts": self.supporting_facts,
            "entity_relationships": self.entity_relationships,
            "confidence_score": self.confidence_score,
            "graph_depth": self.graph_depth,
            "total_nodes_visited": self.total_nodes_visited,
            "timestamp": self.timestamp,
        }

    def to_context_string(self) -> str:
        """Convert to string for LLM context."""
        parts = []

        if self.primary_entities:
            parts.append("**Relevant Medical Entities:**")
            for entity in self.primary_entities[:5]:
                parts.append(f"- {entity.entity} ({entity.entity_type})")
                if entity.related_entities:
                    for rel in entity.related_entities[:3]:
                        parts.append(
                            f"  → {rel.get('relationship', '')}: {rel.get('entity', '')}"
                        )

        if self.supporting_facts:
            parts.append("\n**Supporting Facts:**")
            for fact in self.supporting_facts[:5]:
                parts.append(f"- {fact}")

        return "\n".join(parts)


class GraphRAGService:
    """
    Graph-enhanced RAG service.

    Combines vector search with knowledge graph traversal
    to provide richer, more contextual responses.

    Example:
        graph_rag = GraphRAGService(neo4j_service, embedding_service)
        context = await graph_rag.get_enriched_context(
            query="What causes chest pain?",
            max_depth=2
        )
    """

    # Entity type mappings
    ENTITY_KEYWORDS = {
        NodeLabel.SYMPTOM.value: [
            "pain",
            "ache",
            "fatigue",
            "dizziness",
            "nausea",
            "shortness",
            "breath",
            "swelling",
            "palpitation",
        ],
        NodeLabel.CONDITION.value: [
            "disease",
            "syndrome",
            "disorder",
            "condition",
            "hypertension",
            "diabetes",
            "failure",
            "attack",
        ],
        NodeLabel.MEDICATION.value: [
            "drug",
            "medication",
            "medicine",
            "pill",
            "tablet",
            "dose",
            "prescription",
            "aspirin",
            "statin",
        ],
        NodeLabel.TREATMENT.value: [
            "treatment",
            "therapy",
            "surgery",
            "procedure",
            "intervention",
            "lifestyle",
            "diet",
            "exercise",
        ],
    }

    def __init__(
        self,
        neo4j_service: Optional[Neo4jService] = None,
        embedding_service: Optional[Any] = None,
        max_context_entities: int = 5,
        max_graph_depth: int = 3,
    ):
        """
        Initialize Graph RAG service.

        Args:
            neo4j_service: Neo4j service for graph ops
            embedding_service: Service for text embeddings
            max_context_entities: Max entities in context
            max_graph_depth: Max traversal depth
        """
        self.neo4j = neo4j_service or Neo4jService(mock_mode=True)
        self.embedding_service = embedding_service
        self.max_context_entities = max_context_entities
        self.max_graph_depth = max_graph_depth

    async def initialize(self):
        """Initialize services."""
        await self.neo4j.connect()

    async def close(self):
        """Clean up resources."""
        await self.neo4j.close()

    async def get_enriched_context(
        self,
        query: str,
        max_depth: int = None,
        entity_types: Optional[List[str]] = None,
    ) -> GraphContext:
        """
        Get graph-enriched context for a query.

        Args:
            query: User query
            max_depth: Max graph traversal depth
            entity_types: Filter by entity types

        Returns:
            GraphContext with assembled context
        """
        max_depth = max_depth or self.max_graph_depth

        # Extract entities from query
        extracted_entities = self._extract_entities(query)

        # Search graph for relevant entities
        primary_results = []
        total_nodes = 0

        for entity_name, entity_type in extracted_entities:
            results = await self._search_entity(
                entity_name,
                entity_type,
                max_depth,
            )
            primary_results.extend(results)
            total_nodes += len(results)

        # If no specific entities found, do general search
        if not primary_results:
            primary_results = await self._semantic_graph_search(query, max_depth)
            total_nodes = len(primary_results)

        # Rank and filter results
        primary_results = self._rank_results(primary_results, query)
        primary_results = primary_results[: self.max_context_entities]

        # Build supporting facts
        supporting_facts = await self._get_supporting_facts(primary_results)

        # Extract relationships
        relationships = self._extract_relationships(primary_results)

        # Calculate confidence
        confidence = self._calculate_confidence(primary_results)

        return GraphContext(
            primary_entities=primary_results,
            supporting_facts=supporting_facts,
            entity_relationships=relationships,
            confidence_score=confidence,
            graph_depth=max_depth,
            total_nodes_visited=total_nodes,
        )

    def _extract_entities(self, query: str) -> List[Tuple[str, str]]:
        """
        Extract potential entities from query.

        Args:
            query: User query

        Returns:
            List of (entity_name, entity_type) tuples
        """
        entities = []
        query_lower = query.lower()

        # Check for known entity keywords
        for entity_type, keywords in self.ENTITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    # Extract phrase around keyword
                    words = query_lower.split()
                    for i, word in enumerate(words):
                        if keyword in word:
                            # Get surrounding context
                            start = max(0, i - 1)
                            end = min(len(words), i + 2)
                            phrase = " ".join(words[start:end])
                            entities.append((phrase, entity_type))
                            break

        # Medical term detection (simple patterns)
        medical_terms = [
            ("chest pain", NodeLabel.SYMPTOM.value),
            ("heart rate", NodeLabel.VITAL_SIGN.value),
            ("blood pressure", NodeLabel.VITAL_SIGN.value),
            ("shortness of breath", NodeLabel.SYMPTOM.value),
            ("heart attack", NodeLabel.CONDITION.value),
            ("heart failure", NodeLabel.CONDITION.value),
            ("coronary artery disease", NodeLabel.CONDITION.value),
            ("atrial fibrillation", NodeLabel.CONDITION.value),
            ("hypertension", NodeLabel.CONDITION.value),
            ("diabetes", NodeLabel.CONDITION.value),
        ]

        for term, entity_type in medical_terms:
            if term in query_lower:
                entities.append((term, entity_type))

        # Deduplicate
        seen = set()
        unique_entities = []
        for entity, etype in entities:
            if entity not in seen:
                seen.add(entity)
                unique_entities.append((entity, etype))

        return unique_entities

    async def _search_entity(
        self,
        entity_name: str,
        entity_type: str,
        max_depth: int,
    ) -> List[GraphSearchResult]:
        """
        Search for an entity in the graph.

        Args:
            entity_name: Entity to search
            entity_type: Type of entity
            max_depth: Traversal depth

        Returns:
            List of search results
        """
        results = []

        # Search in Neo4j
        query = """
        MATCH (n)
        WHERE toLower(n.name) CONTAINS toLower($name)
        RETURN n, labels(n) as labels
        LIMIT 5
        """

        query_result = await self.neo4j.query(query, {"name": entity_name})

        for record in query_result.records:
            node_props = record.get("n", {})
            labels = record.get("labels", [])

            # Get related entities
            node_id = node_props.get("id")
            related = []

            if node_id:
                neighbors = await self.neo4j.get_neighbors(
                    node_id,
                    depth=min(max_depth, 2),
                )

                for neighbor in neighbors[:5]:
                    rel_type = "related to"
                    rels = await self.neo4j.get_relationships(node_id)
                    for rel in rels:
                        if (
                            rel.end_node_id == neighbor.id
                            or rel.start_node_id == neighbor.id
                        ):
                            rel_type = rel.type
                            break

                    related.append(
                        {
                            "entity": neighbor.properties.get("name", "Unknown"),
                            "type": (
                                neighbor.labels[0] if neighbor.labels else "Unknown"
                            ),
                            "relationship": rel_type,
                        }
                    )

            # Build reasoning path
            reasoning = self._build_reasoning_path(
                entity_name,
                labels[0] if labels else "Entity",
                related,
            )

            results.append(
                GraphSearchResult(
                    entity=node_props.get("name", entity_name),
                    entity_type=labels[0] if labels else entity_type,
                    relevance_score=0.8,  # Base score
                    context=f"{entity_name} is a {labels[0] if labels else 'medical entity'}",
                    related_entities=related,
                    reasoning_path=reasoning,
                )
            )

        # If no results, create from mock knowledge
        if not results:
            results = self._get_mock_results(entity_name, entity_type)

        return results

    async def _semantic_graph_search(
        self,
        query: str,
        max_depth: int,
    ) -> List[GraphSearchResult]:
        """
        Semantic search across the graph.

        Args:
            query: User query
            max_depth: Traversal depth

        Returns:
            List of search results
        """
        # In production, this would use embeddings
        # For now, use keyword matching on common medical terms

        results = []

        # Check for common medical queries
        query_lower = query.lower()

        if "cause" in query_lower or "why" in query_lower:
            # User asking about causes
            results.extend(self._get_mock_results("causes", NodeLabel.SYMPTOM.value))

        if "treat" in query_lower or "medication" in query_lower:
            # User asking about treatments
            results.extend(
                self._get_mock_results("treatments", NodeLabel.TREATMENT.value)
            )

        if "risk" in query_lower or "factor" in query_lower:
            # User asking about risk factors
            results.extend(
                self._get_mock_results("risk factors", NodeLabel.RISK_FACTOR.value)
            )

        return results

    def _get_mock_results(
        self,
        entity_name: str,
        entity_type: str,
    ) -> List[GraphSearchResult]:
        """Generate mock results for testing."""
        mock_data = {
            "chest pain": GraphSearchResult(
                entity="Chest Pain",
                entity_type=NodeLabel.SYMPTOM.value,
                relevance_score=0.9,
                context="Chest pain is a common symptom that can indicate various cardiac conditions.",
                related_entities=[
                    {
                        "entity": "Coronary Artery Disease",
                        "type": "Condition",
                        "relationship": "INDICATES",
                    },
                    {
                        "entity": "Myocardial Infarction",
                        "type": "Condition",
                        "relationship": "INDICATES",
                    },
                    {
                        "entity": "Angina",
                        "type": "Condition",
                        "relationship": "INDICATES",
                    },
                ],
                reasoning_path=[
                    "Chest pain is a symptom",
                    "Often indicates cardiac conditions",
                    "May require immediate evaluation",
                ],
            ),
            "hypertension": GraphSearchResult(
                entity="Hypertension",
                entity_type=NodeLabel.CONDITION.value,
                relevance_score=0.85,
                context="Hypertension (high blood pressure) is a major risk factor for cardiovascular disease.",
                related_entities=[
                    {
                        "entity": "ACE Inhibitors",
                        "type": "Medication",
                        "relationship": "TREATS",
                    },
                    {
                        "entity": "Beta Blockers",
                        "type": "Medication",
                        "relationship": "TREATS",
                    },
                    {
                        "entity": "Stroke",
                        "type": "Condition",
                        "relationship": "RISK_FOR",
                    },
                ],
                reasoning_path=[
                    "Hypertension is a chronic condition",
                    "Increases cardiovascular risk",
                    "Treatable with medication and lifestyle changes",
                ],
            ),
            "shortness of breath": GraphSearchResult(
                entity="Shortness of Breath",
                entity_type=NodeLabel.SYMPTOM.value,
                relevance_score=0.85,
                context="Dyspnea can indicate heart failure, pulmonary, or anxiety conditions.",
                related_entities=[
                    {
                        "entity": "Heart Failure",
                        "type": "Condition",
                        "relationship": "INDICATES",
                    },
                    {
                        "entity": "COPD",
                        "type": "Condition",
                        "relationship": "INDICATES",
                    },
                ],
                reasoning_path=[
                    "Shortness of breath is a symptom",
                    "Can indicate cardiac or pulmonary issues",
                    "Severity determines urgency",
                ],
            ),
        }

        # Check for matches
        entity_lower = entity_name.lower()
        for key, result in mock_data.items():
            if key in entity_lower or entity_lower in key:
                return [result]

        # Generic result
        return [
            GraphSearchResult(
                entity=entity_name.title(),
                entity_type=entity_type,
                relevance_score=0.5,
                context=f"Information about {entity_name}",
                related_entities=[],
                reasoning_path=[f"Found reference to {entity_name}"],
            )
        ]

    def _build_reasoning_path(
        self,
        entity: str,
        entity_type: str,
        related: List[Dict],
    ) -> List[str]:
        """Build reasoning path for transparency."""
        path = [f"Identified {entity} as {entity_type}"]

        for rel in related[:3]:
            path.append(
                f"{rel.get('relationship', 'relates to')} "
                f"{rel.get('entity', 'unknown')} ({rel.get('type', '')})"
            )

        return path

    def _rank_results(
        self,
        results: List[GraphSearchResult],
        query: str,
    ) -> List[GraphSearchResult]:
        """Rank results by relevance."""
        query_lower = query.lower()

        for result in results:
            # Boost score if entity appears in query
            if result.entity.lower() in query_lower:
                result.relevance_score += 0.2

            # Boost for more related entities
            result.relevance_score += len(result.related_entities) * 0.02

            # Cap at 1.0
            result.relevance_score = min(result.relevance_score, 1.0)

        # Sort by relevance
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results

    async def _get_supporting_facts(
        self,
        results: List[GraphSearchResult],
    ) -> List[str]:
        """Extract supporting facts from results."""
        facts = []

        for result in results:
            # Add context as fact
            if result.context:
                facts.append(result.context)

            # Add relationship facts
            for rel in result.related_entities[:2]:
                fact = f"{result.entity} {rel.get('relationship', 'is related to').lower().replace('_', ' ')} {rel.get('entity', '')}"
                facts.append(fact)

        # Deduplicate
        return list(dict.fromkeys(facts))[:10]

    def _extract_relationships(
        self,
        results: List[GraphSearchResult],
    ) -> List[Dict[str, str]]:
        """Extract entity relationships."""
        relationships = []

        for result in results:
            for rel in result.related_entities:
                relationships.append(
                    {
                        "source": result.entity,
                        "relationship": rel.get("relationship", "related_to"),
                        "target": rel.get("entity", "unknown"),
                    }
                )

        return relationships

    def _calculate_confidence(
        self,
        results: List[GraphSearchResult],
    ) -> float:
        """Calculate overall confidence score."""
        if not results:
            return 0.0

        # Average relevance scores
        avg_relevance = sum(r.relevance_score for r in results) / len(results)

        # Boost for more results
        completeness = min(len(results) / self.max_context_entities, 1.0)

        return avg_relevance * 0.7 + completeness * 0.3

    async def enrich_response(
        self,
        response: str,
        context: GraphContext,
    ) -> Dict[str, Any]:
        """
        Enrich an LLM response with graph citations.

        Args:
            response: Original LLM response
            context: Graph context used

        Returns:
            Enriched response with citations
        """
        citations = []

        for entity in context.primary_entities:
            if entity.entity.lower() in response.lower():
                citations.append(
                    {
                        "entity": entity.entity,
                        "type": entity.entity_type,
                        "confidence": entity.relevance_score,
                    }
                )

        return {
            "response": response,
            "citations": citations,
            "context_summary": context.to_context_string(),
            "confidence": context.confidence_score,
        }
