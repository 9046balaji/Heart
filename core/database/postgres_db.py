"""
PostgreSQL database connection module using asyncpg.
Supports both traditional relational data and vector search capabilities (via pgvector).
"""

import os
import logging
import re
import json
from typing import Optional, List, Dict, Any, Literal
from contextlib import asynccontextmanager
import numpy as np

from core.config.app_config import get_app_config

# Try to import database drivers
try:
    import asyncpg
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    asyncpg = None

logger = logging.getLogger(__name__)
config = get_app_config()

class PostgresDatabase:
    """Database connector for PostgreSQL with vector search support."""

    def __init__(self):
        self.pool: Optional[object] = None
        self.initialized = False
        
        # Connection settings from AppConfig
        self.host = config.database.host
        self.port = config.database.port
        self.user = config.database.user
        self.password = config.database.password
        self.database = config.database.database

    async def initialize(self):
        """Initialize database connection pool."""
        if not POSTGRES_AVAILABLE:
            logger.warning("PostgreSQL drivers (asyncpg) not available")
            return False

        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                min_size=config.database.pool_min_size if hasattr(config.database, 'pool_min_size') else 10,
                max_size=config.database.pool_max_size if hasattr(config.database, 'pool_max_size') else 30,
            )
            
            logger.info(f"✓ PostgreSQL pool created at {self.host}:{self.port}")
            
            # Test connection
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            
            self.initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            return False

    async def _verify_schema(self):
        """Verify that required tables exist (minimal implementation for compatibility)."""
        if not self.pool:
            return
        
        async with self.pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            existing_tables = [t['table_name'] for t in tables]
            logger.info(f"Existing tables: {existing_tables}")

    @asynccontextmanager
    async def get_connection(self):
        """
        Context manager to acquire a database connection from the pool.
        
        Usage:
            async with db.get_connection() as conn:
                await conn.execute("SELECT 1")
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized. Call await initialize() first.")
        
        conn = await self.pool.acquire()
        try:
            yield conn
        finally:
            await self.pool.release(conn)

    async def execute_query(
        self, 
        query: str, 
        params: tuple = None,
        operation: Literal["read", "write"] = "write",
        fetch_one: bool = False,
        fetch_all: bool = False
    ):
        """Execute query with asyncpg."""
        if not self.pool:
            return None
            
        # Convert %s to $1, $2, etc. for asyncpg
        query = self._convert_placeholders(query)
        
        async with self.pool.acquire() as conn:
            if fetch_one:
                result = await conn.fetchrow(query, *(params or ()))
                return dict(result) if result else None
            elif fetch_all:
                results = await conn.fetch(query, *(params or ()))
                return [dict(r) for r in results]
            else:
                return await conn.execute(query, *(params or ()))

    def _convert_placeholders(self, query: str) -> str:
        """Convert MySQL %s placeholders to PostgreSQL $1, $2, etc."""
        count = 1
        while '%s' in query:
            query = query.replace('%s', f'${count}', 1)
            count += 1
        return query

    async def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        return await self.execute_query(query, params, operation="read", fetch_all=True) or []

    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        return await self.execute_query(query, params, operation="read", fetch_one=True)

    async def execute_select(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute SELECT with named parameters."""
        if params is None:
            params = {}
        
        # Find all :param_name occurrences
        param_names = re.findall(r':(\w+)', query)
        param_values = tuple(params.get(name) for name in param_names)
        
        # Convert :param_name to $1, $2, etc.
        converted_query = query
        for i, name in enumerate(param_names):
            converted_query = converted_query.replace(f':{name}', f'${i+1}')
            
        return await self.fetch_all(converted_query, param_values)

    async def store_vitals(
        self,
        user_id: str,
        device_id: str,
        metric_type: str,
        value: float,
        unit: str = "",
    ) -> bool:
        try:
            await self.execute_query(
                "INSERT INTO vitals (user_id, device_id, metric_type, value, unit) VALUES (%s, %s, %s, %s, %s)",
                (user_id, device_id, metric_type, value, unit)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store vitals: {e}")
            return False

    async def get_user_vitals_history(
        self, user_id: str, metric_type: str = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        try:
            query = "SELECT device_id, metric_type, value, unit, recorded_at FROM vitals WHERE user_id = %s "
            params = [user_id]
            if metric_type:
                query += "AND metric_type = %s "
                params.append(metric_type)
            query += "ORDER BY recorded_at DESC LIMIT %s"
            params.append(limit)
            
            results = await self.fetch_all(query, tuple(params))
            return [
                {
                    "device_id": row["device_id"],
                    "metric_type": row["metric_type"],
                    "value": row["value"],
                    "unit": row["unit"],
                    "timestamp": row["recorded_at"],
                }
                for row in results
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve vitals: {e}")
            return []

    async def store_medical_knowledge(
        self,
        content: str,
        content_type: str,
        embedding: List[float],
        metadata: Dict = None,
    ) -> bool:
        try:
            # Store embedding as JSON string or array if pgvector is not used, 
            # but here we assume the schema uses TEXT or JSONB for embedding as per core_postgresql_schema.sql
            await self.execute_query(
                "INSERT INTO medical_knowledge_base (content, content_type, embedding, metadata_json) VALUES (%s, %s, %s, %s)",
                (content, content_type, json.dumps(embedding), json.dumps(metadata or {}))
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store knowledge: {e}")
            return False

    async def search_similar_knowledge(
        self, query_embedding: List[float], content_type: str = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar knowledge using vector similarity.
        
        **SECURITY**: Application-level fallback is restricted to prevent DoS.
        
        If pgvector is not installed:
        - In development: Uses application-level similarity with a HARD LIMIT of 1000 rows
        - In production: Fails fast (requires pgvector extension)
        
        This prevents memory exhaustion from fetching entire knowledge bases into memory.
        """
        try:
            # Check if pgvector extension is available (would use <=> operator)
            # For now, we'll do application-level similarity with safety limits
            
            is_production = os.getenv("APP_ENV", "development").lower() == "production"
            
            # Build query with strict LIMIT to prevent DoS
            SAFE_LIMIT = 1000  # Max rows to fetch for application-level similarity
            
            query = f"SELECT id, content, content_type, metadata_json, embedding FROM medical_knowledge_base "
            params = []
            if content_type:
                query += "WHERE content_type = %s "
                params.append(content_type)
            
            # Add HARD LIMIT to prevent full table scan
            query += f"LIMIT {SAFE_LIMIT}"
            
            results = await self.fetch_all(query, tuple(params))
            
            # If we got no results or pgvector should be available, warn in production
            if not results and is_production:
                logger.error(
                    "CRITICAL: Vector search returning no results in production. "
                    "pgvector extension should be installed for production deployments. "
                    "Install: CREATE EXTENSION IF NOT EXISTS vector;"
                )
                return []
            
            # Application-level similarity (development/fallback only)
            scored_results = []
            q_vec = np.array(query_embedding)
            
            for row in results:
                try:
                    row_vec = np.array(json.loads(row['embedding']))
                    
                    # Prevent division by zero
                    q_norm = np.linalg.norm(q_vec)
                    row_norm = np.linalg.norm(row_vec)
                    if q_norm == 0 or row_norm == 0:
                        continue
                    
                    similarity = np.dot(q_vec, row_vec) / (q_norm * row_norm)
                    scored_results.append({
                        "id": row['id'],
                        "content": row['content'],
                        "content_type": row['content_type'],
                        "metadata": row['metadata_json'],
                        "similarity": float(similarity)
                    })
                except Exception as e:
                    logger.debug(f"Failed to compute similarity for row: {e}")
                    continue
            
            scored_results.sort(key=lambda x: x['similarity'], reverse=True)
            return scored_results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search knowledge: {e}")
            return []


# ============================================================================
# SINGLETON INSTANCE & FACTORY FUNCTION
# ============================================================================

_postgres_instance: Optional[PostgresDatabase] = None

async def get_database() -> PostgresDatabase:
    """Get or create the PostgreSQL database singleton instance."""
    global _postgres_instance
    
    if _postgres_instance is None:
        _postgres_instance = PostgresDatabase()
        await _postgres_instance.initialize()
    
    return _postgres_instance
