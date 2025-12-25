"""
Database connection module for XAMPP MySQL (MariaDB) integration.
Supports both traditional relational data and vector search capabilities.
"""

import os
import logging
from typing import Optional, List, Dict, Any, Literal
from contextlib import asynccontextmanager
import json
import math
import numpy as np

from config import get_settings

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

settings = get_settings()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors using NumPy.
    
    Performance: ~100x faster than pure Python for 1536-dim vectors.
    
    Args:
        vec1: First vector (can be list or numpy array)
        vec2: Second vector (can be list or numpy array)
        
    Returns:
        Cosine similarity score between -1 and 1
    """
    # Convert to numpy arrays (no-op if already arrays)
    a = np.asarray(vec1, dtype=np.float32)
    b = np.asarray(vec2, dtype=np.float32)
    
    if a.shape != b.shape:
        raise ValueError(f"Vectors must have same shape: {a.shape} vs {b.shape}")
    
    # Compute norms
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    # Handle zero vectors
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    # Cosine similarity via dot product
    return float(np.dot(a, b) / (norm_a * norm_b))


def batch_cosine_similarity(query: List[float], vectors: List[List[float]]) -> List[float]:
    """
    Calculate cosine similarity between query and multiple vectors.
    
    Uses vectorized operations for maximum performance.
    
    Args:
        query: Query vector
        vectors: List of vectors to compare against
        
    Returns:
        List of similarity scores (same order as input vectors)
    """
    if not vectors:
        return []
    
    query_arr = np.asarray(query, dtype=np.float32)
    vectors_arr = np.asarray(vectors, dtype=np.float32)
    
    # Normalize query
    query_norm = query_arr / (np.linalg.norm(query_arr) + 1e-10)
    
    # Normalize all vectors at once
    norms = np.linalg.norm(vectors_arr, axis=1, keepdims=True)
    vectors_normalized = vectors_arr / (norms + 1e-10)
    
    # Dot product of query with all vectors
    similarities = np.dot(vectors_normalized, query_norm)
    
    return similarities.tolist()


class XAMPPDatabase:
    """Database connector for XAMPP MySQL with vector search support."""

    def __init__(self):
        self.write_pool: Optional[aiomysql.Pool] = None
        self.read_pool: Optional[aiomysql.Pool] = None
        self.initialized = False
        
        # Parse connection URL
        # For compatibility, we'll extract from the DATABASE_URL setting
        database_url = settings.DATABASE_URL
        if database_url.startswith('mysql://'):
            # Parse mysql://user:password@host:port/database format
            import re
            match = re.match(r'mysql://([^:]+):([^@]+)@([^:]+):([0-9]+)/(.+)', database_url)
            if match:
                self.user = match.group(1)
                self.password = match.group(2)
                self.host = match.group(3)
                self.port = int(match.group(4))
                self.database = match.group(5)
            else:
                # Fallback to environment variables
                self.host = os.getenv("MYSQL_HOST", "localhost")
                self.port = int(os.getenv("MYSQL_PORT", 3307))  # XAMPP default port
                self.user = os.getenv("MYSQL_USER", "root")
                self.password = os.getenv("MYSQL_PASSWORD", "")
                self.database = os.getenv("MYSQL_DATABASE", "heartguard")
        else:
            # Fallback to environment variables
            self.host = os.getenv("MYSQL_HOST", "localhost")
            self.port = int(os.getenv("MYSQL_PORT", 3307))  # XAMPP default port
            self.user = os.getenv("MYSQL_USER", "root")
            self.password = os.getenv("MYSQL_PASSWORD", "")
            self.database = os.getenv("MYSQL_DATABASE", "heartguard")

    async def initialize(self):
        """Initialize database connection pools with read/write splitting."""
        if not MYSQL_AVAILABLE:
            logger.warning(
                "MySQL drivers not available, skipping database initialization"
            )
            return False

        try:
            # Write pool (Master)
            self.write_pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                minsize=settings.DB_POOL_MIN_SIZE,
                maxsize=settings.DB_POOL_MAX_SIZE,
                pool_recycle=settings.DB_POOL_RECYCLE,
                autocommit=False,
                charset='utf8mb4'
            )
            
            logger.info(
                f"✓ Write pool created (min={settings.DB_POOL_MIN_SIZE}, "
                f"max={settings.DB_POOL_MAX_SIZE})"
            )
            
            # Read pool (Replica) - optional
            if settings.DB_READ_REPLICA_URL:
                # Parse replica URL
                import re
                replica_match = re.match(r'mysql://([^:]+):([^@]+)@([^:]+):([0-9]+)/(.+)', settings.DB_READ_REPLICA_URL)
                if replica_match:
                    replica_user = replica_match.group(1)
                    replica_password = replica_match.group(2)
                    replica_host = replica_match.group(3)
                    replica_port = int(replica_match.group(4))
                    
                    self.read_pool = await aiomysql.create_pool(
                        host=replica_host,
                        port=replica_port,
                        user=replica_user,
                        password=replica_password,
                        db=self.database,  # Same database name
                        minsize=settings.DB_POOL_MIN_SIZE * 2,  # More read connections
                        maxsize=settings.DB_POOL_MAX_SIZE * 2,
                        pool_recycle=settings.DB_POOL_RECYCLE,
                        autocommit=True,  # Read-only, can autocommit
                        charset='utf8mb4'
                    )
                    
                    logger.info("✓ Read pool created (replica)")
                else:
                    logger.error("Invalid DB_READ_REPLICA_URL format")
                    return False
            else:
                # Use write pool for reads if no replica
                self.read_pool = self.write_pool
                logger.info("✓ Using write pool for reads (no replica configured)")

            # Test connection and initialize schema
            await self._initialize_schema()
            self.initialized = True
            logger.info("XAMPP MySQL database initialized successfully with read/write splitting")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False

    async def _initialize_schema(self):
        """Initialize database schema with tables for healthcare data."""
        if not self.pool:
            return

        logger.warning(
            "_initialize_schema() is deprecated. "
            "Schema management now handled by Alembic migrations. "
            "Run 'alembic upgrade head' to ensure schema is up to date."
        )
        
        # Verify that required tables exist
        await self._verify_schema()
        
        logger.info("Database schema verification completed")

    async def _verify_schema(self):
        """Verify that required tables exist in the database."""
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    # Check if users table exists
                    await cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = 'users'
                        """,
                        (DB_CONFIG["database"],),
                    )
                    if not await cursor.fetchone():
                        logger.error("Table 'users' does not exist")
                        return

                    # Check if devices table exists
                    await cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = 'devices'
                        """,
                        (DB_CONFIG["database"],),
                    )
                    if not await cursor.fetchone():
                        logger.error("Table 'devices' does not exist")
                        return

                    # Check if patient_records table exists
                    await cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = 'patient_records'
                        """,
                        (DB_CONFIG["database"],),
                    )
                    if not await cursor.fetchone():
                        logger.error("Table 'patient_records' does not exist")
                        return

                    # Check if vitals table exists
                    await cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = 'vitals'
                        """,
                        (DB_CONFIG["database"],),
                    )
                    if not await cursor.fetchone():
                        logger.error("Table 'vitals' does not exist")
                        return

                    # Check if health_alerts table exists
                    await cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = 'health_alerts'
                        """,
                        (DB_CONFIG["database"],),
                    )
                    if not await cursor.fetchone():
                        logger.error("Table 'health_alerts' does not exist")
                        return

                    # Check if medical_knowledge_base table exists
                    await cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = 'medical_knowledge_base'
                        """,
                        (DB_CONFIG["database"],),
                    )
                    if not await cursor.fetchone():
                        logger.error("Table 'medical_knowledge_base' does not exist")
                        return

                    # Check if chat_sessions table exists
                    await cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = 'chat_sessions'
                        """,
                        (DB_CONFIG["database"],),
                    )
                    if not await cursor.fetchone():
                        logger.error("Table 'chat_sessions' does not exist")
                        return

                    # Check if chat_messages table exists
                    await cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = 'chat_messages'
                        """,
                        (DB_CONFIG["database"],),
                    )
                    if not await cursor.fetchone():
                        logger.error("Table 'chat_messages' does not exist")
                        return

                    # Check if notification_failures table exists
                    await cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = 'notification_failures'
                        """,
                        (DB_CONFIG["database"],),
                    )
                    if not await cursor.fetchone():
                        logger.error("Table 'notification_failures' does not exist")
                        return

                    logger.info("All required tables exist")

                except Exception as e:
                    logger.error(f"Failed to verify database schema: {e}")

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
                date_of_birth DATE,
                gender VARCHAR(20),
                weight_kg FLOAT,
                height_cm FLOAT,
                known_conditions JSON,
                medications JSON,
                allergies JSON,
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

        # Create vitals table (without foreign key)
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vitals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                device_id VARCHAR(255),
                metric_type VARCHAR(50),
                value FLOAT,
                unit VARCHAR(20),
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_user_recorded (user_id, recorded_at),
                INDEX idx_metric_type (metric_type)
            )
        """
        )
        
        # Create health alerts table
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                alert_type VARCHAR(50),
                severity VARCHAR(20),
                message TEXT,
                is_resolved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP NULL,
                INDEX idx_user_id (user_id)
            )
        """)

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
        
        # Create notification_failures table (for dead letter queue)
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_failures (
                id INT AUTO_INCREMENT PRIMARY KEY,
                
                -- Notification details
                notification_type VARCHAR(50) NOT NULL,  -- 'email', 'push', 'sms'
                recipient VARCHAR(255) NOT NULL,         -- Email or phone number
                subject VARCHAR(500),
                content TEXT,
                
                -- Failure tracking
                original_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                retry_count INT DEFAULT 0,
                max_retries INT DEFAULT 5,
                next_retry_at TIMESTAMP,
                
                -- Error details
                last_error TEXT,
                status ENUM('pending', 'retrying', 'failed', 'succeeded') DEFAULT 'pending',
                
                -- Metadata
                user_id VARCHAR(255),
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                
                -- Indexes for efficient querying
                INDEX idx_status_next_retry (status, next_retry_at),
                INDEX idx_user_id (user_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # Seed default user
        await cursor.execute("""
            INSERT IGNORE INTO users (user_id, name, email, date_of_birth, gender, weight_kg, height_cm)
            VALUES ('user123', 'John Doe', 'john@example.com', '1980-01-01', 'Male', 80.0, 180.0)
        """)

        logger.info("Database schema initialized (simple approach)")

    def get_pool(self, operation: Literal["read", "write"] = "write") -> aiomysql.Pool:
        """Get appropriate pool for operation."""
        if operation == "read":
            return self.read_pool
        return self.write_pool
    
    async def execute_query(
        self, 
        query: str, 
        params: tuple = None,
        operation: Literal["read", "write"] = "write",
        fetch_one: bool = False,
        fetch_all: bool = False
    ):
        """
        Execute query with appropriate pool.
        
        Args:
            query: SQL query
            params: Query parameters
            operation: "read" or "write"
            fetch_one: Return single row
            fetch_all: Return all rows
        """
        pool = self.get_pool(operation)
        
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params or ())
                
                if fetch_one:
                    return await cursor.fetchone()
                elif fetch_all:
                    return await cursor.fetchall()
                else:
                    if operation == "write":
                        await conn.commit()
                    return cursor.lastrowid
    
    async def store_vitals(
        self,
        user_id: str,
        device_id: str,
        metric_type: str,
        value: float,
        unit: str = "",
    ) -> bool:
        """Store vitals data in the database."""
        if not self.initialized or not self.write_pool:
            logger.warning("Database not initialized, skipping vitals storage")
            return False

        try:
            async with self.write_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO vitals (user_id, device_id, metric_type, value, unit)
                        VALUES (%s, %s, %s, %s, %s)
                    """,
                        (user_id, device_id, metric_type, value, unit),
                    )
                    await conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Failed to store vitals data: {e}")
            return False

    async def get_user_vitals_history(
        self, user_id: str, metric_type: str = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve user vitals history."""
        if not self.initialized or not self.read_pool:
            return []

        try:
            query = """
                SELECT device_id, metric_type, value, unit, recorded_at
                FROM vitals
                WHERE user_id = %s
            """
            params = [user_id]
            
            if metric_type:
                query += "AND metric_type = %s "
                params.append(metric_type)
            
            query += "ORDER BY recorded_at DESC LIMIT %s"
            params.append(limit)
            
            results = await self.execute_query(
                query,
                tuple(params),
                operation="read",
                fetch_all=True
            )
            
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
        if not self.initialized or not self.write_pool:
            logger.warning("Database not initialized, skipping knowledge storage")
            return False

        try:
            # Convert embedding to bytes for BLOB storage
            embedding_bytes = json.dumps(embedding).encode("utf-8")

            await self.execute_query(
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
                operation="write"
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

                    # Parse embeddings in batch
                    parsed_results = []
                    embeddings = []
                    for row in results:
                        try:
                            # Parse embedding from BLOB
                            embedding_str = (
                                row[3].decode("utf-8")
                                if isinstance(row[3], bytes)
                                else row[3]
                            )
                            doc_embedding = json.loads(embedding_str)
                            embeddings.append(doc_embedding)
                            parsed_results.append(row)
                        except Exception as parse_error:
                            logger.warning(
                                f"Failed to parse embedding for document {row[0]}: {parse_error}"
                            )
                            continue

                    # Calculate all similarities in one vectorized operation
                    if embeddings:
                        similarities = batch_cosine_similarity(query_embedding, embeddings)
                    else:
                        return []

                    # Combine results with similarities and sort
                    scored_results = list(zip(parsed_results, similarities))
                    scored_results.sort(key=lambda x: x[1], reverse=True)

                    # Return top results
                    top_results = []
                    for row, similarity in scored_results[:limit]:
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
        if not self.initialized or not self.write_pool:
            return False

        try:
            # Ensure session exists first
            await self.execute_query(
                """
                INSERT IGNORE INTO chat_sessions (session_id, user_id)
                VALUES (%s, %s)
                """,
                (session_id, "user123"), # Default to user123 if not provided, or extract from metadata if possible
                operation="write"
            )
            
            await self.execute_query(
                """
                INSERT INTO chat_messages (session_id, message_type, content, metadata)
                VALUES (%s, %s, %s, %s)
            """,
                (session_id, message_type, content, json.dumps(metadata or {})),
                operation="write"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store chat message: {e}")
            return False

    async def get_chat_history(
        self, session_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve chat history for a session."""
        if not self.initialized or not self.read_pool:
            return []

        try:
            results = await self.execute_query(
                """
                SELECT message_type, content, metadata, timestamp
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY timestamp ASC
                LIMIT %s
            """,
                (session_id, limit),
                operation="read",
                fetch_all=True
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
        if not self.initialized:
            return {"error": "Database not initialized"}
        
        return {
            "write_pool": {
                "size": self.write_pool.size(),
                "free": self.write_pool.freesize(),
                "used": self.write_pool.size() - self.write_pool.freesize(),
                "max": settings.DB_POOL_MAX_SIZE
            },
            "read_pool": {
                "size": self.read_pool.size() if self.read_pool != self.write_pool else "N/A",
                "free": self.read_pool.freesize() if self.read_pool != self.write_pool else "N/A",
            } if settings.DB_READ_REPLICA_URL else "shared_with_write"
        }
    
    async def close(self):
        """Close all pools."""
        if self.write_pool:
            self.write_pool.close()
            await self.write_pool.wait_closed()
        
        if self.read_pool and self.read_pool != self.write_pool:
            self.read_pool.close()
            await self.read_pool.wait_closed()
            
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
