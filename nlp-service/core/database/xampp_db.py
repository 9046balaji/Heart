"""
Database connection module for XAMPP MySQL (MariaDB) integration.
Supports both traditional relational data and vector search capabilities.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import json
import math

# Try to import database drivers
try:
    import pymysql
    import aiomysql

    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    pymysql = None
    aiomysql = None

logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3307)),  # XAMPP default port
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "heartguard"),
    "charset": "utf8mb4",
    "autocommit": True,
}


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    if len(vec1) != len(vec2):
        raise ValueError("Vectors must have the same length")

    # Calculate dot product
    dot_product = sum(a * b for a, b in zip(vec1, vec2))

    # Calculate magnitudes
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    # Avoid division by zero
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


class XAMPPDatabase:
    """Database connector for XAMPP MySQL with vector search support."""

    def __init__(self):
        self.pool = None
        self.initialized = False

    async def initialize(self):
        """Initialize database connection pool."""
        if not MYSQL_AVAILABLE:
            logger.warning(
                "MySQL drivers not available, skipping database initialization"
            )
            return False

        try:
            # Create connection pool
            self.pool = await aiomysql.create_pool(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                db=DB_CONFIG["database"],
                charset=DB_CONFIG["charset"],
                autocommit=DB_CONFIG["autocommit"],
                minsize=1,
                maxsize=10,
            )

            # Test connection and initialize schema
            await self._initialize_schema()
            self.initialized = True
            logger.info("XAMPP MySQL database initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False

    async def _initialize_schema(self):
        """Initialize database schema with tables for healthcare data."""
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    # Drop tables in reverse order to avoid foreign key constraints
                    tables_to_drop = [
                        "chat_messages",
                        "chat_sessions",
                        "medical_knowledge_base",
                        "vitals_data",
                        "patient_records",
                        "users",
                    ]

                    for table in tables_to_drop:
                        try:
                            await cursor.execute(f"DROP TABLE IF EXISTS {table}")
                        except Exception as e:
                            logger.debug(f"Could not drop table {table}: {e}")

                    # Create users table
                    await cursor.execute(
                        """
                        CREATE TABLE users (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id VARCHAR(255) UNIQUE NOT NULL,
                            name VARCHAR(255),
                            email VARCHAR(255),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """
                    )

                    # Create patient records table
                    await cursor.execute(
                        """
                        CREATE TABLE patient_records (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id VARCHAR(255) NOT NULL,
                            record_type VARCHAR(100),
                            data JSON,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                        )
                    """
                    )

                    # Create vitals data table
                    await cursor.execute(
                        """
                        CREATE TABLE vitals_data (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id VARCHAR(255) NOT NULL,
                            device_id VARCHAR(255),
                            metric_type VARCHAR(50),
                            value FLOAT,
                            unit VARCHAR(20),
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                            INDEX idx_user_timestamp (user_id, timestamp),
                            INDEX idx_metric_type (metric_type)
                        )
                    """
                    )

                    # Create vector knowledge base table (for RAG)
                    # Try to create with VECTOR type first, fallback to BLOB if not supported
                    try:
                        await cursor.execute(
                            """
                            CREATE TABLE medical_knowledge_base (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                content TEXT,
                                content_type VARCHAR(100),
                                embedding VECTOR(1536) COMMENT 'Embedding vector for similarity search',
                                metadata JSON,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                INDEX idx_content_type (content_type)
                            )
                        """
                        )
                    except Exception as e:
                        logger.warning(
                            f"VECTOR type not supported, using BLOB instead: {e}"
                        )
                        await cursor.execute(
                            """
                            CREATE TABLE medical_knowledge_base (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                content TEXT,
                                content_type VARCHAR(100),
                                embedding BLOB,
                                metadata JSON,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                INDEX idx_content_type (content_type)
                            )
                        """
                        )

                    # Create chat sessions table
                    await cursor.execute(
                        """
                        CREATE TABLE chat_sessions (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            session_id VARCHAR(255) UNIQUE NOT NULL,
                            user_id VARCHAR(255) NOT NULL,
                            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            ended_at TIMESTAMP NULL,
                            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                        )
                    """
                    )

                    # Create chat messages table
                    await cursor.execute(
                        """
                        CREATE TABLE chat_messages (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            session_id VARCHAR(255) NOT NULL,
                            message_type ENUM('user', 'assistant') NOT NULL,
                            content TEXT,
                            metadata JSON,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                        )
                    """
                    )

                    logger.info("Database schema initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize database schema: {e}")
                    # Try a simpler approach without foreign keys for compatibility
                    try:
                        await self._initialize_schema_simple(cursor)
                    except Exception as e2:
                        logger.error(
                            f"Failed to initialize database schema (simple approach): {e2}"
                        )
                        raise

    async def _initialize_schema_simple(self, cursor):
        """Simple schema initialization without foreign keys for compatibility."""
        # Create users table
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255),
                email VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create patient records table (without foreign key)
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS patient_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                record_type VARCHAR(100),
                data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id)
            )
        """
        )

        # Create vitals data table (without foreign key)
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vitals_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                device_id VARCHAR(255),
                metric_type VARCHAR(50),
                value FLOAT,
                unit VARCHAR(20),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_user_timestamp (user_id, timestamp),
                INDEX idx_metric_type (metric_type)
            )
        """
        )

        # Create vector knowledge base table (for RAG)
        try:
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS medical_knowledge_base (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    content TEXT,
                    content_type VARCHAR(100),
                    embedding VECTOR(1536) COMMENT 'Embedding vector for similarity search',
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_content_type (content_type)
                )
            """
            )
        except Exception as e:
            logger.warning(f"VECTOR type not supported, using BLOB instead: {e}")
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS medical_knowledge_base (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    content TEXT,
                    content_type VARCHAR(100),
                    embedding BLOB,
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_content_type (content_type)
                )
            """
            )

        # Create chat sessions table (without foreign key)
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(255) UNIQUE NOT NULL,
                user_id VARCHAR(255) NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP NULL,
                INDEX idx_user_id (user_id)
            )
        """
        )

        # Create chat messages table (without foreign key)
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                message_type ENUM('user', 'assistant') NOT NULL,
                content TEXT,
                metadata JSON,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_session_id (session_id)
            )
        """
        )

        logger.info("Database schema initialized (simple approach)")

    async def store_vitals(
        self,
        user_id: str,
        device_id: str,
        metric_type: str,
        value: float,
        unit: str = "",
    ) -> bool:
        """Store vitals data in the database."""
        if not self.initialized or not self.pool:
            logger.warning("Database not initialized, skipping vitals storage")
            return False

        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO vitals_data (user_id, device_id, metric_type, value, unit)
                        VALUES (%s, %s, %s, %s, %s)
                    """,
                        (user_id, device_id, metric_type, value, unit),
                    )
                    return True
        except Exception as e:
            logger.error(f"Failed to store vitals data: {e}")
            return False

    async def get_user_vitals_history(
        self, user_id: str, metric_type: str = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve user vitals history."""
        if not self.initialized or not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    if metric_type:
                        await cursor.execute(
                            """
                            SELECT device_id, metric_type, value, unit, timestamp
                            FROM vitals_data
                            WHERE user_id = %s AND metric_type = %s
                            ORDER BY timestamp DESC
                            LIMIT %s
                        """,
                            (user_id, metric_type, limit),
                        )
                    else:
                        await cursor.execute(
                            """
                            SELECT device_id, metric_type, value, unit, timestamp
                            FROM vitals_data
                            WHERE user_id = %s
                            ORDER BY timestamp DESC
                            LIMIT %s
                        """,
                            (user_id, limit),
                        )

                    results = await cursor.fetchall()
                    return [
                        {
                            "device_id": row[0],
                            "metric_type": row[1],
                            "value": row[2],
                            "unit": row[3],
                            "timestamp": row[4],
                        }
                        for row in results
                    ]
        except Exception as e:
            logger.error(f"Failed to retrieve vitals history: {e}")
            return []

    async def store_medical_knowledge(
        self,
        content: str,
        content_type: str,
        embedding: List[float],
        metadata: Dict = None,
    ) -> bool:
        """Store medical knowledge with embedding vector for RAG."""
        if not self.initialized or not self.pool:
            logger.warning("Database not initialized, skipping knowledge storage")
            return False

        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Convert embedding to bytes for BLOB storage
                    embedding_bytes = json.dumps(embedding).encode("utf-8")

                    await cursor.execute(
                        """
                        INSERT INTO medical_knowledge_base (content, content_type, embedding, metadata)
                        VALUES (%s, %s, %s, %s)
                    """,
                        (
                            content,
                            content_type,
                            embedding_bytes,
                            json.dumps(metadata or {}),
                        ),
                    )
                    return True
        except Exception as e:
            logger.error(f"Failed to store medical knowledge: {e}")
            return False

    async def search_similar_knowledge(
        self, query_embedding: List[float], content_type: str = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar medical knowledge using vector similarity.

        This implementation handles both modern MariaDB with VECTOR support and older versions.
        For older versions, it performs application-level cosine similarity calculations.
        """
        if not self.initialized or not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # First, try to use native vector search (modern MariaDB)
                    try:
                        if content_type:
                            await cursor.execute(
                                """
                                SELECT id, content, content_type, metadata,
                                       VEC_DISTANCE_COSINE(embedding, %s) as similarity
                                FROM medical_knowledge_base
                                WHERE content_type = %s
                                ORDER BY similarity ASC
                                LIMIT %s
                            """,
                                (str(query_embedding), content_type, limit),
                            )
                        else:
                            await cursor.execute(
                                """
                                SELECT id, content, content_type, metadata,
                                       VEC_DISTANCE_COSINE(embedding, %s) as similarity
                                FROM medical_knowledge_base
                                ORDER BY similarity ASC
                                LIMIT %s
                            """,
                                (str(query_embedding), limit),
                            )

                        results = await cursor.fetchall()
                        return [
                            {
                                "id": row[0],
                                "content": row[1],
                                "content_type": row[2],
                                "metadata": json.loads(row[3]) if row[3] else {},
                                "similarity": (
                                    float(row[4]) if row[4] is not None else 1.0
                                ),
                            }
                            for row in results
                        ]
                    except Exception as e:
                        # Native vector search failed, fall back to application-level calculation
                        logger.debug(
                            f"Native vector search failed, using application-level calculation: {e}"
                        )
                        return await self._search_similar_knowledge_fallback(
                            query_embedding, content_type, limit
                        )
        except Exception as e:
            logger.error(f"Failed to search similar knowledge: {e}")
            return []

    async def _search_similar_knowledge_fallback(
        self, query_embedding: List[float], content_type: str = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Fallback search method using application-level cosine similarity calculation."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Retrieve all documents (or filter by content_type)
                    if content_type:
                        await cursor.execute(
                            """
                            SELECT id, content, content_type, embedding, metadata
                            FROM medical_knowledge_base
                            WHERE content_type = %s
                        """,
                            (content_type,),
                        )
                    else:
                        await cursor.execute(
                            """
                            SELECT id, content, content_type, embedding, metadata
                            FROM medical_knowledge_base
                        """
                        )

                    results = await cursor.fetchall()

                    # Calculate similarities for each document
                    similarities = []
                    for row in results:
                        try:
                            # Parse embedding from BLOB
                            embedding_str = (
                                row[3].decode("utf-8")
                                if isinstance(row[3], bytes)
                                else row[3]
                            )
                            doc_embedding = json.loads(embedding_str)

                            # Calculate cosine similarity
                            similarity = cosine_similarity(
                                query_embedding, doc_embedding
                            )
                            similarities.append((row, similarity))
                        except Exception as parse_error:
                            logger.warning(
                                f"Failed to parse embedding for document {row[0]}: {parse_error}"
                            )
                            continue

                    # Sort by similarity (higher is more similar)
                    similarities.sort(key=lambda x: x[1], reverse=True)

                    # Return top results
                    top_results = []
                    for row, similarity in similarities[:limit]:
                        top_results.append(
                            {
                                "id": row[0],
                                "content": row[1],
                                "content_type": row[2],
                                "metadata": json.loads(row[4]) if row[4] else {},
                                "similarity": similarity,
                            }
                        )

                    return top_results
        except Exception as e:
            logger.error(f"Fallback search also failed: {e}")
            return []

    async def store_chat_message(
        self, session_id: str, message_type: str, content: str, metadata: Dict = None
    ) -> bool:
        """Store chat message in the database."""
        if not self.initialized or not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO chat_messages (session_id, message_type, content, metadata)
                        VALUES (%s, %s, %s, %s)
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
        if not self.initialized or not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT message_type, content, metadata, timestamp
                        FROM chat_messages
                        WHERE session_id = %s
                        ORDER BY timestamp ASC
                        LIMIT %s
                    """,
                        (session_id, limit),
                    )

                    results = await cursor.fetchall()
                    return [
                        {
                            "message_type": row[0],
                            "content": row[1],
                            "metadata": json.loads(row[2]) if row[2] else {},
                            "timestamp": row[3],
                        }
                        for row in results
                    ]
        except Exception as e:
            logger.error(f"Failed to retrieve chat history: {e}")
            return []

    async def close(self):
        """Close database connections."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Database connections closed")


# Global database instance
db_instance: Optional[XAMPPDatabase] = None


async def get_database() -> XAMPPDatabase:
    """Get singleton database instance."""
    global db_instance
    if db_instance is None:
        db_instance = XAMPPDatabase()
        await db_instance.initialize()
    return db_instance


@asynccontextmanager
async def get_db_connection():
    """Async context manager for database connections."""
    db = await get_database()
    try:
        yield db
    finally:
        pass  # Connection pooling handles cleanup
