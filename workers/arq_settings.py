"""
ARQ Worker Configuration

ARQ is the 2025 standard for async Python task queues.
Native asyncio integration ensures seamless LangGraph compatibility.

Why ARQ over Celery:
- ARQ is native to asyncio - seamless integration with FastAPI and async LangGraph
- Celery is process-based and creates sync-async boundary issues with LangGraph agents
- ARQ handles 20k+ jobs/sec with lower overhead than Celery
- No need for separate broker (Flower, RabbitMQ) - uses Redis native structures

Usage:
    # Start ARQ worker (can run multiple for scaling)
    arq workers.arq_settings.WorkerSettings

    # Or with specific settings
    arq workers.arq_settings.WorkerSettings --max-jobs 20
"""

import os
import sys
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime
from arq import cron
from arq.connections import RedisSettings

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# ============================================================================
# Redis Configuration
# ============================================================================

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# ARQ Redis Settings
redis_settings = RedisSettings(
    host=REDIS_HOST,
    port=REDIS_PORT,
    database=REDIS_DB,
    password=REDIS_PASSWORD,
)

# ============================================================================
# Worker Configuration
# ============================================================================

# Number of concurrent jobs per worker (asyncio tasks)
MAX_JOBS = int(os.getenv("ARQ_MAX_JOBS", "10"))

# Job timeout (max time for a single job)
JOB_TIMEOUT = int(os.getenv("ARQ_JOB_TIMEOUT", "300"))  # 5 minutes

# Health check interval
HEALTH_CHECK_INTERVAL = int(os.getenv("ARQ_HEALTH_CHECK_INTERVAL", "60"))

# Retry settings
MAX_RETRIES = int(os.getenv("ARQ_MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("ARQ_RETRY_DELAY", "5"))  # seconds


# ============================================================================
# Job Functions (registered with ARQ worker)
# ============================================================================

async def process_chat_message(
    ctx: Dict[str, Any],
    job_id: str,
    user_id: str,
    message: str,
    session_id: Optional[str] = None,
    priority: str = "normal",
    metadata: Optional[Dict[str, Any]] = None,
    thinking: bool = False,
    web_search: bool = False,
    deep_search: bool = False,
    file_ids: Optional[list] = None
) -> Dict[str, Any]:
    """
    Process a chat message through LangGraph orchestrator.
    
    This runs as an async task in the ARQ worker pool.
    Native asyncio means no sync-async boundary issues with LangGraph.
    
    Args:
        ctx: ARQ context with worker resources
        job_id: Unique job identifier
        user_id: User who submitted the request
        query: The chat message/query
        session_id: Optional session for conversation context
        priority: Job priority level
        metadata: Additional metadata
    
    Returns:
        Job result dictionary
    """
    start_time = time.time()
    
    # Get resources from worker context
    orchestrator = ctx.get("orchestrator")
    job_store = ctx.get("job_store")
    ws_manager = ctx.get("ws_manager")
    heartbeat_manager = ctx.get("heartbeat_manager")
    
    try:
        # Update job status to processing
        await job_store.update_job_status(
            job_id, 
            "processing", 
            worker_id=ctx.get("worker_id")
        )
        
        # Start heartbeat for this job (prevents load balancer disconnect)
        if heartbeat_manager:
            await heartbeat_manager.start_heartbeat(job_id)
        
        # Progress callback for real-time updates
        async def on_progress(step: int, total: int, node: str, message: str = ""):
            """Send progress updates via WebSocket."""
            if ws_manager:
                await ws_manager.broadcast_job_progress(job_id, step, total, node, message)
            
            # Update job progress in store
            await job_store.update_job_progress(job_id, step, total, node, message)
        
        # Execute LangGraph orchestrator (fully async)
        # thread_id = job_id for checkpointing - enables crash recovery
        result = await orchestrator.execute(
            query=message,
            user_id=user_id,
            thread_id=job_id,  # Use job_id as thread_id for checkpointing
            progress_callback=on_progress,
            thinking=thinking,
            web_search=web_search,
            deep_search=deep_search,
            file_ids=file_ids
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Build result
        job_result = {
            "job_id": job_id,
            "status": "completed",
            "response": result.get("response", ""),
            "sources": result.get("citations", []),
            "metadata": {
                "intent": result.get("intent"),
                "confidence": result.get("confidence"),
                "pii_scrubbed": result.get("pii_scrubbed"),
                "source": result.get("metadata", {}).get("source"),
                "thread_id": result.get("metadata", {}).get("thread_id"),
            },
            "processing_time_ms": processing_time_ms,
            "completed_at": datetime.utcnow().isoformat(),
        }
        
        # Store result and update status
        await job_store.complete_job(job_id, job_result)
        
        # Stop heartbeat
        if heartbeat_manager:
            await heartbeat_manager.stop_heartbeat(job_id)
        
        # Broadcast via WebSocket
        if ws_manager:
            await ws_manager.broadcast_job_result(job_id, user_id, job_result)
        
        logger.info(f"✅ Job {job_id} completed in {processing_time_ms}ms")
        
        return job_result
        
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        error_result = {
            "job_id": job_id,
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__,
            "processing_time_ms": processing_time_ms,
        }
        
        await job_store.fail_job(job_id, error_result)
        
        # Stop heartbeat
        if heartbeat_manager:
            await heartbeat_manager.stop_heartbeat(job_id)
        
        # Broadcast error via WebSocket
        if ws_manager:
            await ws_manager.broadcast_job_result(job_id, user_id, error_result)
        
        logger.error(f"❌ Job {job_id} failed: {e}")
        
        # Re-raise for ARQ retry mechanism
        raise


async def process_deep_research(
    ctx: Dict[str, Any],
    job_id: str,
    user_id: str,
    query: str,
    session_id: Optional[str] = None,
    depth: str = "standard"
) -> Dict[str, Any]:
    """
    Process a deep research task (longer running, more comprehensive).
    
    Uses the same pattern as chat but with extended timeout and depth.
    
    Args:
        ctx: ARQ context
        job_id: Unique job identifier
        user_id: User who submitted the request
        query: Research query
        session_id: Optional session ID
        depth: Research depth (quick, standard, deep)
    
    Returns:
        Research result dictionary
    """
    start_time = time.time()
    
    orchestrator = ctx.get("orchestrator")
    job_store = ctx.get("job_store")
    heartbeat_manager = ctx.get("heartbeat_manager")
    
    try:
        await job_store.update_job_status(
            job_id, 
            "processing", 
            metadata={"type": "research", "depth": depth}
        )
        
        if heartbeat_manager:
            await heartbeat_manager.start_heartbeat(job_id)
        
        # Run research workflow (if implemented in orchestrator)
        if hasattr(orchestrator, 'run_research'):
            result = await orchestrator.run_research(
                query=query,
                user_id=user_id,
                depth=depth
            )
        else:
            # Fall back to regular execute with research hint
            result = await orchestrator.execute(
                query=f"[RESEARCH MODE - {depth.upper()}] {query}",
                user_id=user_id,
                session_id=session_id
            )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        research_result = {
            "job_id": job_id,
            "status": "completed",
            "type": "research",
            "depth": depth,
            "response": result.get("response", ""),
            "sources": result.get("citations", []),
            "processing_time_ms": processing_time_ms,
            "completed_at": datetime.utcnow().isoformat(),
        }
        
        await job_store.complete_job(job_id, research_result)
        
        if heartbeat_manager:
            await heartbeat_manager.stop_heartbeat(job_id)
        
        logger.info(f"✅ Research job {job_id} completed in {processing_time_ms}ms")
        
        return research_result
        
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        await job_store.fail_job(job_id, {
            "job_id": job_id,
            "error": str(e),
            "error_type": type(e).__name__,
            "processing_time_ms": processing_time_ms,
        })
        
        if heartbeat_manager:
            await heartbeat_manager.stop_heartbeat(job_id)
        
        logger.error(f"❌ Research job {job_id} failed: {e}")
        raise


async def resume_workflow(
    ctx: Dict[str, Any],
    job_id: str,
    thread_id: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Resume a workflow from its last checkpoint.
    
    Used for crash recovery or retrying failed jobs.
    
    Args:
        ctx: ARQ context
        job_id: Job identifier
        thread_id: LangGraph thread ID (for checkpoint)
        user_id: User who owns the workflow
    
    Returns:
        Resumed workflow result
    """
    orchestrator = ctx.get("orchestrator")
    job_store = ctx.get("job_store")
    
    try:
        await job_store.update_job_status(job_id, "processing", metadata={"resumed": True})
        
        result = await orchestrator.resume_from_checkpoint(thread_id)
        
        job_result = {
            "job_id": job_id,
            "status": "completed",
            "resumed": True,
            "thread_id": thread_id,
            "response": result.get("response", ""),
            "completed_at": datetime.utcnow().isoformat(),
        }
        
        await job_store.complete_job(job_id, job_result)
        
        logger.info(f"✅ Job {job_id} resumed and completed from thread {thread_id}")
        
        return job_result
        
    except Exception as e:
        await job_store.fail_job(job_id, {
            "job_id": job_id,
            "error": str(e),
            "error_type": type(e).__name__,
        })
        logger.error(f"❌ Job {job_id} resume failed: {e}")
        raise


# ============================================================================
# Startup/Shutdown Hooks
# ============================================================================

async def startup(ctx: Dict[str, Any]):
    """
    Initialize worker context on startup.
    
    Runs once when the worker starts.
    Creates shared resources (orchestrator, connections).
    """
    import uuid
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger.info("🚀 ARQ Worker starting up...")
    
    # Generate worker ID
    ctx["worker_id"] = f"arq-worker-{uuid.uuid4().hex[:8]}"
    
    try:
        # Initialize LangGraph Orchestrator
        from agents.langgraph_orchestrator import LangGraphOrchestrator
        ctx["orchestrator"] = LangGraphOrchestrator()
        logger.info("✅ LangGraph Orchestrator initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize orchestrator: {e}")
        raise
    
    try:
        # Initialize Job Store
        from core.services.job_store import get_job_store
        ctx["job_store"] = await get_job_store()
        logger.info("✅ Job Store initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize job store: {e}")
        raise
    
    try:
        # Initialize WebSocket Manager (for broadcasting results)
        from core.services.websocket_manager import initialize_ws_manager
        ws_manager = await initialize_ws_manager()
        ctx["ws_manager"] = ws_manager
        ctx["heartbeat_manager"] = ws_manager.heartbeat_manager if ws_manager else None
        logger.info("✅ WebSocket Manager initialized")
    except Exception as e:
        logger.warning(f"⚠️ WebSocket Manager not available: {e}")
        ctx["ws_manager"] = None
        ctx["heartbeat_manager"] = None
    
    logger.info(f"✅ ARQ Worker {ctx['worker_id']} ready")


async def shutdown(ctx: Dict[str, Any]):
    """
    Cleanup worker context on shutdown.
    
    Runs once when the worker is stopping.
    Gracefully closes connections.
    """
    logger.info(f"🛑 ARQ Worker {ctx.get('worker_id')} shutting down...")
    
    # Cleanup WebSocket manager
    ws_manager = ctx.get("ws_manager")
    if ws_manager:
        await ws_manager.shutdown()
    
    # Cleanup job store
    job_store = ctx.get("job_store")
    if job_store:
        await job_store.shutdown()
    
    logger.info("✅ ARQ Worker shutdown complete")


# ============================================================================
# Cron Jobs (scheduled tasks)
# ============================================================================

async def cleanup_old_jobs(ctx: Dict[str, Any]):
    """Periodic cleanup of old completed jobs."""
    job_store = ctx.get("job_store")
    if job_store:
        deleted_count = await job_store.cleanup_old_jobs(hours=24)
        logger.info(f"🧹 Cleaned up {deleted_count} old jobs")


async def health_check(ctx: Dict[str, Any]):
    """Periodic health check logging."""
    worker_id = ctx.get("worker_id", "unknown")
    logger.info(f"💓 Worker {worker_id} health check OK")


# ============================================================================
# ARQ Worker Class
# ============================================================================

class WorkerSettings:
    """
    ARQ Worker Settings - this is what ARQ looks for.
    
    To start the worker:
        arq workers.arq_settings.WorkerSettings
    """
    
    # Redis connection
    redis_settings = redis_settings
    
    # Job functions to register
    functions = [
        process_chat_message,
        process_deep_research,
        resume_workflow,
    ]
    
    # Cron jobs (scheduled tasks)
    cron_jobs = [
        cron(cleanup_old_jobs, hour={0, 12}, minute=0),  # Run at midnight and noon
        cron(health_check, minute={0, 15, 30, 45}),  # Every 15 minutes
    ]
    
    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown
    
    # Worker settings
    max_jobs = MAX_JOBS
    job_timeout = JOB_TIMEOUT
    health_check_interval = HEALTH_CHECK_INTERVAL
    
    # Retry settings
    max_tries = MAX_RETRIES
    retry_delay = RETRY_DELAY
    
    # Queue name
    queue_name = "arq:queue"
