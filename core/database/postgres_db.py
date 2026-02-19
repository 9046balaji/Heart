"""
PostgreSQL database connection module using asyncpg.
Supports traditional relational data storage.
Vector search is handled by ChromaDB (see rag/chromadb_store.py).
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
            # Store embedding as JSON string or array (vector search handled by ChromaDB), 
            # here we use JSONB for embedding as per schema
            await self.execute_query(
                "INSERT INTO medical_knowledge_base (content, content_type, embedding, metadata) VALUES ($1, $2, $3, $4)",
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
        
        Note: Primary vector search is handled by ChromaDB (rag/chromadb_store.py).
        This is a PostgreSQL-level fallback for the medical_knowledge_base table.
        
        In development: Uses application-level similarity with a HARD LIMIT of 1000 rows.
        In production: Should use ChromaDB vector store instead.
        
        This prevents memory exhaustion from fetching entire knowledge bases into memory.
        """
        try:
            # Application-level similarity (fallback only; use ChromaDB for production)
            
            is_production = os.getenv("APP_ENV", "development").lower() == "production"
            
            # Build query with strict LIMIT to prevent DoS
            SAFE_LIMIT = 1000  # Max rows to fetch for application-level similarity
            
            query = f"SELECT id, content, content_type, metadata, embedding FROM medical_knowledge_base "
            params = []
            if content_type:
                query += "WHERE content_type = $1 "
                params.append(content_type)
            
            # Add HARD LIMIT to prevent full table scan
            query += f"LIMIT {SAFE_LIMIT}"
            
            results = await self.fetch_all(query, tuple(params))
            
            # If we got no results in production, warn
            if not results and is_production:
                logger.error(
                    "CRITICAL: Vector search returning no results in production. "
                    "Consider using ChromaDB vector store (rag/chromadb_store.py) "
                    "for production vector search."
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
                        "metadata": row['metadata'] if isinstance(row['metadata'], dict) else json.loads(row['metadata'] or '{}'),
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


    async def store_chat_message(
        self, session_id: str, message_type: str, content: str, metadata: Dict = None
    ) -> bool:
        """Store chat message in the database."""
        if not self.pool:
            return False

        try:
            # Ensure session exists first
            await self.execute_query(
                """
                INSERT INTO chat_sessions (session_id, user_id)
                VALUES ($1, $2)
                ON CONFLICT (session_id) DO NOTHING
                """,
                (session_id, "user123"), # Default to user123 if not provided
            )
            
            await self.execute_query(
                """
                INSERT INTO chat_messages (session_id, message_type, content, metadata)
                VALUES ($1, $2, $3, $4)
                """,
                (session_id, message_type, content, json.dumps(metadata or {})),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store chat message: {e}")
            return False

    async def get_chat_history(
        self, session_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve chat history for a session."""
        if not self.pool:
            return []

        try:
            results = await self.fetch_all(
                """
                SELECT message_type, content, metadata, timestamp
                FROM chat_messages
                WHERE session_id = $1
                ORDER BY timestamp ASC
                LIMIT $2
                """,
                (session_id, limit),
            )
            
            return [
                {
                    "message_type": row["message_type"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "timestamp": row["timestamp"],
                }
                for row in results
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve chat history: {e}")
            return []

    async def get_pool_status(self) -> dict:
        """Get pool connection statistics."""
        if not self.pool:
            return {"error": "Database not initialized"}
        
        return {
            "min_size": self.pool._min_size,
            "max_size": self.pool._max_size,
            "current_size": len(self.pool._holders),
            "free": self.pool._queue.qsize(), # Approx
        }

    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.initialized = False
            logger.info("PostgreSQL pool closed")

    async def _ensure_schema(self):
        """Ensure all required tables exist."""
        if not self.pool:
            return

        # Define tables to create
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255),
                email VARCHAR(255),
                date_of_birth DATE,
                gender VARCHAR(20),
                weight_kg FLOAT,
                height_cm FLOAT,
                known_conditions JSONB,
                medications JSONB,
                allergies JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS patient_records (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                record_type VARCHAR(100),
                data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vitals (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                device_id VARCHAR(255),
                metric_type VARCHAR(50),
                value FLOAT,
                unit VARCHAR(20),
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS health_alerts (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                alert_type VARCHAR(50),
                severity VARCHAR(20),
                message TEXT,
                is_resolved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP NULL
            )
            """,
             """
            CREATE TABLE IF NOT EXISTS medical_knowledge_base (
                id SERIAL PRIMARY KEY,
                content TEXT,
                content_type VARCHAR(100),
                embedding JSONB, 
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) UNIQUE NOT NULL,
                user_id VARCHAR(255) NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                message_type VARCHAR(50) NOT NULL,
                content TEXT,
                metadata JSONB,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS notification_failures (
                id SERIAL PRIMARY KEY,
                notification_type VARCHAR(50) NOT NULL,
                recipient VARCHAR(255) NOT NULL,
                subject VARCHAR(500),
                content TEXT,
                original_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                retry_count INT DEFAULT 0,
                max_retries INT DEFAULT 5,
                next_retry_at TIMESTAMP,
                last_error TEXT,
                status VARCHAR(50) DEFAULT 'pending',
                user_id VARCHAR(255),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        try:
            async with self.pool.acquire() as conn:
                # 1. Run migrations for legacy schema compatibility
                # Check for metadata_json in chat_messages and rename to metadata
                try:
                    chat_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'chat_messages'")
                    chat_col_names = [r['column_name'] for r in chat_cols]
                    
                    if 'metadata_json' in chat_col_names and 'metadata' not in chat_col_names:
                        logger.info("Migrating chat_messages: metadata_json -> metadata")
                        await conn.execute("ALTER TABLE chat_messages RENAME COLUMN metadata_json TO metadata")
                except Exception as e:
                    logger.warning(f"Migration check for chat_messages failed: {e}")

                # Check for metadata_json in medical_knowledge_base and rename to metadata
                try:
                    kb_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'medical_knowledge_base'")
                    kb_col_names = [r['column_name'] for r in kb_cols]
                    
                    if 'metadata_json' in kb_col_names and 'metadata' not in kb_col_names:
                        logger.info("Migrating medical_knowledge_base: metadata_json -> metadata")
                        await conn.execute("ALTER TABLE medical_knowledge_base RENAME COLUMN metadata_json TO metadata")
                except Exception as e:
                    logger.warning(f"Migration check for medical_knowledge_base failed: {e}")

                # 2. Create tables if not exist
                for sql in tables_sql:
                    await conn.execute(sql)
                
                # Seed default user if not exists
                await conn.execute("""
                    INSERT INTO users (user_id, name, email, date_of_birth, gender, weight_kg, height_cm)
                    VALUES ('user123', 'John Doe', 'john@example.com', '1980-01-01', 'Male', 80.0, 180.0)
                    ON CONFLICT (user_id) DO NOTHING
                """)
                
            logger.info("Schema ensured (tables created/migrated)")
        except Exception as e:
            logger.error(f"Failed to ensure schema: {e}")

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
        await _postgres_instance._ensure_schema()
    
    return _postgres_instance
