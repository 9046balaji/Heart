"""
Abstract Base Class for Neo4j Service.

Defines the interface contract for Neo4j service implementations,
enabling proper testing and dependency injection.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = None  # Will be set by inheriting classes


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""  # Must be set via env var
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_timeout: int = 30
    enabled: bool = True  # Flag to indicate if Neo4j should be used

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        """Create config from environment variables.
        
        If NEO4J_PASSWORD is not set, returns a disabled config instead of raising.
        This allows graceful fallback to PostgreSQL.
        """
        import os
        import logging
        
        # Get password from environment
        password = os.getenv("NEO4J_PASSWORD", "")
        
        if not password:
            # Log warning and return disabled config (graceful degradation)
            logging.getLogger(__name__).warning(
                "NEO4J_PASSWORD not set - Neo4j disabled, using PostgreSQL fallback. "
                "To enable Neo4j, set: export NEO4J_PASSWORD=your_password"
            )
            return cls(enabled=False)

        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=password,
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            enabled=True,
        )


class AbstractNeo4jService(ABC):
    """
    Abstract base class defining the interface for Neo4j service implementations.

    This interface ensures consistent method signatures across different
    implementations (production, mock, etc.) and enables proper dependency
    injection and testing.

    Implementing classes must provide:
    - Connection management (connect, close)
    - Node operations (create, read, update, delete)
    - Relationship operations
    - Query execution
    - Graph traversal
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish database connection."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    async def create_node(self, node: Any) -> Any:
        """Create a node in the graph."""
        pass

    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[Any]:
        """Retrieve a node by ID."""
        pass

    @abstractmethod
    async def update_node(self, node_id: str, properties: Dict[str, Any]) -> Optional[Any]:
        """Update node properties."""
        pass

    @abstractmethod
    async def delete_node(self, node_id: str, force: bool = False) -> bool:
        """Delete a node."""
        pass

    @abstractmethod
    async def create_relationship(self, relationship: Any) -> Any:
        """Create a relationship between nodes."""
        pass

    @abstractmethod
    async def get_relationships(
        self,
        node_id: str,
        direction: str = "both",
        rel_type: Optional[str] = None,
    ) -> List[Any]:
        """Get relationships for a node."""
        pass

    @abstractmethod
    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        pass

    @abstractmethod
    async def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a Cypher query."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        node_types: Optional[List[str]] = None,
        max_depth: int = 2,
        limit: int = 10
    ) -> Any:
        """Search the knowledge graph."""
        pass

    @abstractmethod
    async def rag_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        include_reasoning: bool = True
    ) -> Any:
        """Query using graph-enhanced RAG."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the service is healthy."""
        pass

    @abstractmethod
    async def get_stats(self) -> Any:
        """Get graph statistics."""
        pass

    @abstractmethod
    async def get_neighbors(
        self,
        node_id: str,
        depth: int = 1,
        labels: Optional[List[str]] = None
    ) -> List[Any]:
        """Get neighboring nodes."""
        pass

    @abstractmethod
    async def get_paths(
        self,
        start_node_id: str,
        end_node_id: str,
        max_depth: int = 3
    ) -> List[List[Any]]:
        """Get all paths between two nodes."""
        pass

    @abstractmethod
    @asynccontextmanager
    async def session(self):
        """Get a database session."""
        pass
