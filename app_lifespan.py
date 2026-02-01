"""
FastAPI Lifespan Context Manager for Proper Resource Initialization

This module provides an async context manager for FastAPI startup and shutdown events.
It replaces global state initialization patterns with proper ASGI lifespan management.

**Benefits:**
✅ Works correctly with multi-worker deployments (Gunicorn, Uvicorn with multiple workers)
✅ Every worker runs initialization, not just the first one
✅ Proper resource cleanup on shutdown
✅ Predictable initialization order
✅ Exception handling prevents crashed workers

**Architecture:**
- Startup: Initialize all services (orchestrator, feedback store, embedding engine, auth DB)
- Running: Request handling with all services available
- Shutdown: Clean up resources, close connections

**Scalability Services (New):**
- ARQ Redis Pool: Job queue for async processing
- WebSocket Manager: Real-time result delivery with heartbeat
- Job Store: Redis-based job metadata tracking

**Usage in main.py:**
```python
from contextlib import asynccontextmanager
from app_lifespan import lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await app_lifespan.startup()
    yield
    # Shutdown
    await app_lifespan.shutdown()

app = FastAPI(lifespan=lifespan)
```
"""

import logging
import os
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI

logger = logging.getLogger(__name__)


# ============================================================================
# Global Service Instances (Initialized during startup)
# ============================================================================

_orchestrator: Optional[Any] = None
_feedback_store: Optional[Any] = None
_embedding_search_engine: Optional[Any] = None
_auth_db_service: Optional[Any] = None

# Scalability Services (New)
_arq_pool: Optional[Any] = None
_websocket_manager: Optional[Any] = None
_job_store: Optional[Any] = None


def get_orchestrator() -> Optional[Any]:
    """Get orchestrator instance (initialized during startup)."""
    if _orchestrator is None:
        logger.error("❌ Orchestrator not initialized! Did you forget to start the app?")
    return _orchestrator


def get_feedback_store() -> Optional[Any]:
    """Get feedback store instance (initialized during startup)."""
    if _feedback_store is None:
        logger.warning("⚠️  Feedback store not initialized")
    return _feedback_store


def get_embedding_search_engine() -> Optional[Any]:
    """Get embedding search engine instance (initialized during startup)."""
    if _embedding_search_engine is None:
        logger.warning("⚠️  Embedding search engine not initialized")
    return _embedding_search_engine


def get_auth_db_service() -> Optional[Any]:
    """Get auth database service instance (initialized during startup)."""
    if _auth_db_service is None:
        logger.error("❌ Auth DB service not initialized! User authentication will fail.")
    return _auth_db_service


def get_arq_pool() -> Optional[Any]:
    """Get ARQ Redis pool for job enqueueing (initialized during startup)."""
    if _arq_pool is None:
        logger.error("❌ ARQ pool not initialized! Async job processing unavailable.")
    return _arq_pool


def get_websocket_manager() -> Optional[Any]:
    """Get WebSocket connection manager (initialized during startup)."""
    if _websocket_manager is None:
        logger.warning("⚠️ WebSocket manager not initialized - real-time updates unavailable")
    return _websocket_manager


def get_job_store() -> Optional[Any]:
    """Get job store for job metadata (initialized during startup)."""
    if _job_store is None:
        logger.warning("⚠️ Job store not initialized - job tracking unavailable")
    return _job_store


# ============================================================================
# Startup & Shutdown Handlers
# ============================================================================

async def startup_event():
    """
    Initialize all services during application startup.
    
    Runs ONCE per worker in a multi-worker deployment.
    This is the key difference from global initialization - every worker
    runs this code, ensuring all services are available in every worker.
    """
    global _orchestrator, _feedback_store, _embedding_search_engine, _auth_db_service
    
    logger.info("🚀 Starting up application services...")
    
    try:
        # 0a. Run Alembic migrations (ensure database schema is up to date)
        logger.info("📦 Checking database migrations...")
        import subprocess
        import os
        
        # Get the project root directory
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        try:
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            if result.returncode == 0:
                logger.info("✅ Database migrations applied successfully")
                if result.stdout:
                    logger.debug(f"Migration output: {result.stdout}")
            else:
                logger.warning(f"⚠️ Migration returned non-zero: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ Migration timed out - continuing without migration")
        except FileNotFoundError:
            logger.warning("⚠️ Alembic not found in PATH - skipping migrations")
        except Exception as e:
            logger.warning(f"⚠️ Migration check failed: {e} - continuing")
    except Exception as e:
        logger.error(f"❌ Migration initialization error: {e}")
    
    try:
        # 0b. Initialize PostgreSQL database connection (MUST be first!)
        logger.info("📦 Initializing PostgreSQL database connection...")
        from core.database.postgres_db import PostgresDatabase
        from core.dependencies import DIContainer
        
        container = DIContainer.get_instance()
        db_manager = PostgresDatabase()
        
        # Initialize the database connection pool
        db_init_success = await db_manager.initialize()
        if not db_init_success:
            logger.error("❌ PostgreSQL pool initialization failed - auth DB will fail")
        else:
            # Register in DIContainer BEFORE auth tries to use it
            container.register_service('db_manager', db_manager)
            logger.info("✅ PostgreSQL database registered in DIContainer")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize PostgreSQL: {e}")
        logger.error("   Auth DB service will fail without database connection")
    
    try:
        # 1. Initialize authentication database service
        logger.info("📦 Initializing authentication database...")
        from routes.auth_db_service import init_auth_db_service
        from core.dependencies import DIContainer
        
        container = DIContainer.get_instance()
        db_manager = container.get_service('db_manager')
        
        if db_manager is None:
            raise RuntimeError(
                "db_manager not registered in DIContainer! "
                "PostgreSQL initialization must run first."
            )
        
        redis_client = getattr(container, 'redis_client', None)
        
        _auth_db_service = await init_auth_db_service(db_manager, redis_client)
        logger.info("✅ Auth DB service initialized")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize auth DB service: {e}")
        logger.warning("   Authentication will be unavailable but app will continue")
        # Don't raise - allow app to start but auth will fail gracefully
    
    try:
        # 2. Initialize LangGraph orchestrator
        logger.info("📦 Initializing LangGraph orchestrator...")
        from agents.langgraph_orchestrator import LangGraphOrchestrator
        from core.dependencies import DIContainer
        
        container = DIContainer.get_instance()
        
        # Resolve dependencies
        db_manager = container.get_service('db_manager')
        vector_store = container.vector_store
        llm_gateway = container.llm_gateway
        memory_manager = container.memory_manager
        interaction_checker = container.interaction_checker
        
        # Initialize interaction checker's PostgreSQL fallback
        await container.initialize_interaction_checker()
        
        # Update Neo4j schema with default values for missing properties
        # This is idempotent and can run on every startup
        try:
            neo4j_service = container.neo4j_service
            if neo4j_service and hasattr(neo4j_service, 'enabled') and neo4j_service.enabled:
                logger.info("📦 Updating Neo4j schema with default property values...")
                await neo4j_service.run_query("""
                    MATCH ()-[r:INTERACTS_WITH]->()
                    WHERE r.mechanism IS NULL
                    SET r.mechanism = 'Not specified'
                """)
                await neo4j_service.run_query("""
                    MATCH ()-[r:INTERACTS_WITH]->()
                    WHERE r.management IS NULL
                    SET r.management = 'Consult healthcare provider'
                """)
                logger.info("✅ Neo4j schema updated with default property values")
        except Exception as e:
            logger.warning(f"⚠️ Neo4j schema update skipped: {e}")
        
        # Get MemoriRAGBridge from DIContainer (properly initialized)
        memori_bridge = container.memori_bridge
        if memori_bridge:
            logger.info("✅ MemoriRAGBridge loaded from DIContainer")
            container.register_service('memori_bridge', memori_bridge)
        else:
            logger.warning("⚠️ MemoriRAGBridge not available - memory integration disabled")
        
        _orchestrator = LangGraphOrchestrator(
            db_manager=db_manager,
            llm_gateway=llm_gateway,
            vector_store=vector_store,
            memory_manager=memory_manager,
            interaction_checker=interaction_checker,
            memori_bridge=memori_bridge
        )
        logger.info("✅ Orchestrator initialized")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize orchestrator: {e}")
        # Don't raise - allow app to start but chat endpoints will fail gracefully
    
    try:
        # 3. Initialize feedback store
        logger.info("📦 Initializing feedback store...")
        from core.dependencies import DIContainer
        from rag.feedback_store import FeedbackStore
        
        container = DIContainer.get_instance()
        
        # Get storage implementation from DIContainer
        try:
            storage = container.storage
            feedback_store = FeedbackStore(storage=storage)
            _feedback_store = feedback_store
            
            # Also register in container for global access
            container.register_service('feedback_store', feedback_store)
            logger.info("✅ Feedback store initialized with storage backend")
        except Exception as e:
            logger.error(f"Failed to initialize feedback store: {e}")
            logger.warning("⚠️  Feedback store not available - feedback recording disabled")
        
    except Exception as e:
        logger.error(f"⚠️  Failed to initialize feedback store: {e}")
        # Non-critical, continue
    
    try:
        # 4. Initialize embedding search engine (heavy model loading)
        logger.info("📦 Initializing embedding search engine (this may take 10-30 seconds)...")
        
        try:
            from memori.agents.retrieval_agent import EmbeddingSearchEngine
            
            _embedding_search_engine = EmbeddingSearchEngine(
                use_local=True,  # Use sentence-transformers locally
                similarity_threshold=0.5,
            )
            logger.info("✅ Embedding search engine initialized")
            
        except ImportError:
            logger.warning("⚠️  Memori not available - embedding search disabled")
        except Exception as e:
            logger.warning(f"⚠️  Failed to initialize embedding engine: {e}")
            # Non-critical, continue
        
    except Exception as e:
        logger.error(f"⚠️  Embedding engine initialization error: {e}")
    
    # ========================================================================
    # Scalability Services Initialization (ARQ, WebSocket, Job Store)
    # ========================================================================
    
    try:
        # 5. Initialize ARQ Redis pool for async job processing
        logger.info("📦 Initializing ARQ Redis pool for async job queue...")
        
        from arq import create_pool
        from arq.connections import RedisSettings
        
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        
        # Parse Redis URL to extract components
        # Format: redis://[:password@]host[:port][/db]
        if redis_url.startswith("redis://"):
            redis_url_parsed = redis_url.replace("redis://", "")
        else:
            redis_url_parsed = redis_url
        
        # Simple parsing - handle common formats
        redis_host = "localhost"
        redis_port = 6379
        redis_password = None
        redis_db = 0
        
        if "@" in redis_url_parsed:
            auth_part, host_part = redis_url_parsed.rsplit("@", 1)
            redis_password = auth_part.lstrip(":")
        else:
            host_part = redis_url_parsed
        
        if "/" in host_part:
            host_port, db_part = host_part.split("/", 1)
            redis_db = int(db_part) if db_part else 0
        else:
            host_port = host_part
        
        if ":" in host_port:
            redis_host, port_str = host_port.split(":", 1)
            redis_port = int(port_str) if port_str else 6379
        else:
            redis_host = host_port if host_port else "localhost"
        
        arq_settings = RedisSettings(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            database=redis_db
        )
        
        _arq_pool = await create_pool(arq_settings)
        logger.info(f"✅ ARQ Redis pool initialized ({redis_host}:{redis_port})")
        
        # Wire up ARQ pool to orchestrated chat routes
        try:
            from routes.orchestrated_chat import set_arq_pool
            set_arq_pool(_arq_pool)
            logger.info("✅ ARQ pool wired to orchestrated chat routes")
        except ImportError as e:
            logger.warning(f"⚠️ Could not wire ARQ to routes: {e}")
        
    except ImportError:
        logger.warning("⚠️  ARQ not installed - async job processing unavailable")
        logger.warning("   Install with: pip install arq")
    except Exception as e:
        logger.error(f"❌ Failed to initialize ARQ pool: {e}")
        logger.warning("   Async job processing unavailable - falling back to sync mode")
    
    try:
        # 6. Initialize WebSocket connection manager
        logger.info("📦 Initializing WebSocket connection manager...")
        
        from core.services.websocket_manager import WebSocketConnectionManager
        
        _websocket_manager = WebSocketConnectionManager()
        
        # Register in DIContainer for route access
        from core.dependencies import DIContainer
        container = DIContainer.get_instance()
        container.register_service('websocket_manager', _websocket_manager)
        
        logger.info("✅ WebSocket manager initialized")
        
    except ImportError as e:
        logger.warning(f"⚠️  WebSocket manager import failed: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize WebSocket manager: {e}")
    
    try:
        # 7. Initialize Job Store for job metadata tracking
        logger.info("📦 Initializing Job Store...")
        
        if _arq_pool:
            from core.services.job_store import JobStore
            
            # JobStore expects a Redis URL, not the ARQ pool
            # It creates its own Redis connection internally
            _job_store = JobStore()  # Uses default REDIS_URL from config
            await _job_store.initialize()
            
            # Register in DIContainer
            from core.dependencies import DIContainer
            container = DIContainer.get_instance()
            container.register_service('job_store', _job_store)
            
            logger.info("✅ Job Store initialized")
        else:
            logger.warning("⚠️  Job Store not initialized (ARQ pool unavailable)")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Job Store: {e}")
    
    logger.info("🎉 Application startup complete")


async def shutdown_event():
    """
    Clean up resources during application shutdown.
    
    Runs ONCE per worker during graceful shutdown.
    """
    global _orchestrator, _feedback_store, _embedding_search_engine, _auth_db_service
    global _arq_pool, _websocket_manager, _job_store
    
    logger.info("🛑 Shutting down application services...")
    
    try:
        # Clean up WebSocket manager (close all connections gracefully)
        if _websocket_manager:
            try:
                await _websocket_manager.close_all()
                logger.info("✅ WebSocket manager cleaned up")
            except Exception as e:
                logger.error(f"Error closing WebSocket connections: {e}")
    except Exception as e:
        logger.error(f"Error cleaning up WebSocket manager: {e}")
    
    try:
        # Clean up ARQ pool
        if _arq_pool:
            await _arq_pool.close()
            logger.info("✅ ARQ pool closed")
    except Exception as e:
        logger.error(f"Error closing ARQ pool: {e}")
    
    try:
        # Clean up orchestrator
        if _orchestrator:
            if hasattr(_orchestrator, 'cleanup'):
                await _orchestrator.cleanup()
            logger.info("✅ Orchestrator cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up orchestrator: {e}")
    
    try:
        # Clean up feedback store
        if _feedback_store:
            if hasattr(_feedback_store, 'cleanup'):
                await _feedback_store.cleanup()
            elif hasattr(_feedback_store, 'close'):
                await _feedback_store.close()
            logger.info("✅ Feedback store cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up feedback store: {e}")
    
    try:
        # Clean up auth DB
        if _auth_db_service:
            # DB connections are managed by DIContainer, no explicit cleanup needed
            logger.info("✅ Auth DB service cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up auth DB: {e}")
    
    # Note: Embedding engine doesn't need cleanup (models cached in memory)
    
    logger.info("🎉 Application shutdown complete")


@asynccontextmanager
async def lifespan(app):
    """
    ASGI lifespan context manager for FastAPI.
    
    Ensures proper initialization and shutdown of all services.
    
    **Key Benefits:**
    ✅ Runs on every worker (not just first one)
    ✅ Services available before request handling
    ✅ Proper cleanup on shutdown
    ✅ Exception-safe (failures don't crash workers)
    
    **Usage:**
    ```python
    from app_lifespan import lifespan
    app = FastAPI(lifespan=lifespan)
    ```
    """
    # STARTUP
    await startup_event()
    
    # RUNNING (yield to FastAPI)
    yield
    
    # SHUTDOWN
    await shutdown_event()


# ============================================================================
# Helper: Register lifespan in FastAPI app
# ============================================================================

def setup_lifespan(app: 'FastAPI') -> None:
    """
    Convenience function to register lifespan with FastAPI app.
    
    Alternative to passing lifespan parameter in FastAPI constructor.
    
    **Usage:**
    ```python
    app = FastAPI()
    from app_lifespan import setup_lifespan
    setup_lifespan(app)
    ```
    """
    app.lifespan = lifespan
    logger.info("✅ Lifespan context manager registered with FastAPI")
