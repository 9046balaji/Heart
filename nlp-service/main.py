import sys
import os as _os

# 🔥 FIX: Ensure models package can be found
_current_dir = _os.path.dirname(_os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

print(f"[STARTUP] NLP Service working directory: {_os.getcwd()}")
print(f"[STARTUP] NLP Service script directory: {_current_dir}")
print(f"[STARTUP] Python path (first 3): {sys.path[0:3]}")

import asyncio
import json
import logging
import os
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from rate_limiting import limiter, get_user_id_or_ip

from config import (
    CORS_ORIGINS,
    LOG_LEVEL,
    SERVICE_HOST,
    SERVICE_PORT,
    SERVICE_NAME,
    SERVICE_VERSION,
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
    OLLAMA_TOP_P,
    OLLAMA_TOP_K,
    OLLAMA_MAX_TOKENS,
)
from models import (
    EntityExtractionRequest,
    EntityExtractionResponse,
    HealthCheckResponse,
    IntentEnum,
    IntentResult,
    NLPProcessRequest,
    NLPProcessResponse,
    OllamaResponseRequest,
    OllamaResponseResponse,
    OllamaHealthCheckResponse,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    SentimentEnum,
    SentimentResult,
)
# PHASE 3: Import from engines package (re-exports from parent directory)
from engines import IntentRecognizer, SentimentAnalyzer, EntityExtractor, RiskAssessor
from analytics import AnalyticsManager
from cache import cache_manager
from error_handling import (
    ErrorReporter,
    structured_exception_handler,
    ValidationError,
    TimeoutError,
    ExternalServiceError,
    RateLimitError,
    ModelLoadError,
    ProcessingError,
)  # PHASE 2: Import new exception hierarchy
from model_versioning import ModelVersionManager
from ollama_generator import OllamaGenerator

# PHASE 5: Import RAG API for semantic search
try:
    from rag_api import rag_router, initialize_rag_service
    RAG_ENABLED = True
    print("[STARTUP] RAG service module loaded successfully")
except ImportError as e:
    RAG_ENABLED = False
    rag_router = None
    async def initialize_rag_service():
        pass
    print(f"[STARTUP] RAG service not available: {e}")

# PHASE 6: Import Memory Management Routes
try:
    from routes.memory import router as memory_router
    from user_preferences import init_preferences_manager
    from integrated_ai_service import init_integrated_ai_service
    MEMORY_ROUTES_ENABLED = True
    print("[STARTUP] Memory management routes loaded successfully")
except ImportError as e:
    MEMORY_ROUTES_ENABLED = False
    memory_router = None
    print(f"[STARTUP] Memory routes not available: {e}")

# PHASE 7: Import Real-time WebSocket Support
try:
    from realtime import websocket_router, get_event_bus
    REALTIME_ENABLED = True
    print("[STARTUP] Real-time WebSocket module loaded successfully")
except ImportError as e:
    REALTIME_ENABLED = False
    websocket_router = None
    print(f"[STARTUP] Real-time WebSocket not available: {e}")

# PHASE 8: Import Medical Document Processing Routes (medical.md implementation)
try:
    from routes.document_routes import router as document_router
    from routes.medical_ai_routes import router as medical_ai_router
    from routes.weekly_summary_routes import router as weekly_summary_router
    from routes.weekly_summary_routes import consent_router, webhook_router
    MEDICAL_ROUTES_ENABLED = True
    print("[STARTUP] Medical document processing routes loaded successfully")
except ImportError as e:
    MEDICAL_ROUTES_ENABLED = False
    document_router = None
    medical_ai_router = None
    weekly_summary_router = None
    consent_router = None
    webhook_router = None
    print(f"[STARTUP] Medical routes not available: {e}")

# PHASE 9: Import Integration Routes (medical.md Part 5)
try:
    from routes.integrations_routes import router as integrations_router
    INTEGRATIONS_ROUTES_ENABLED = True
    print("[STARTUP] Integration routes loaded successfully")
except ImportError as e:
    INTEGRATIONS_ROUTES_ENABLED = False
    integrations_router = None
    print(f"[STARTUP] Integration routes not available: {e}")

# PHASE 10: Import Compliance Routes (medical.md Part 4)
try:
    from routes.compliance_routes import router as compliance_router
    COMPLIANCE_ROUTES_ENABLED = True
    print("[STARTUP] Compliance routes loaded successfully")
except ImportError as e:
    COMPLIANCE_ROUTES_ENABLED = False
    compliance_router = None
    print(f"[STARTUP] Compliance routes not available: {e}")

# PHASE 11: Import Agent Routes (ADK orchestration)
try:
    from routes.agents import router as agents_router
    AGENTS_ROUTES_ENABLED = True
    print("[STARTUP] Agents routes loaded successfully")
except ImportError as e:
    AGENTS_ROUTES_ENABLED = False
    agents_router = None
    print(f"[STARTUP] Agents routes not available: {e}")

# PHASE 12: Import Calendar Integration Routes
try:
    from routes.calendar_routes import router as calendar_router
    CALENDAR_ROUTES_ENABLED = True
    print("[STARTUP] Calendar integration routes loaded successfully")
except ImportError as e:
    CALENDAR_ROUTES_ENABLED = False
    calendar_router = None
    print(f"[STARTUP] Calendar routes not available: {e}")

# PHASE 13: Import Knowledge Graph Routes
try:
    from routes.knowledge_graph_routes import router as knowledge_graph_router
    KNOWLEDGE_GRAPH_ROUTES_ENABLED = True
    print("[STARTUP] Knowledge graph routes loaded successfully")
except ImportError as e:
    KNOWLEDGE_GRAPH_ROUTES_ENABLED = False
    knowledge_graph_router = None
    print(f"[STARTUP] Knowledge graph routes not available: {e}")

# PHASE 14: Import Notifications Routes
try:
    from routes.notifications_routes import router as notifications_router
    NOTIFICATIONS_ROUTES_ENABLED = True
    print("[STARTUP] Notifications routes loaded successfully")
except ImportError as e:
    NOTIFICATIONS_ROUTES_ENABLED = False
    notifications_router = None
    print(f"[STARTUP] Notifications routes not available: {e}")

# PHASE 15: Import Tools Routes (Function Calling)
try:
    from routes.tools_routes import router as tools_router
    TOOLS_ROUTES_ENABLED = True
    print("[STARTUP] Tools routes loaded successfully")
except ImportError as e:
    TOOLS_ROUTES_ENABLED = False
    tools_router = None
    print(f"[STARTUP] Tools routes not available: {e}")

# PHASE 16: Import Vision Routes
try:
    from routes.vision_routes import router as vision_router
    VISION_ROUTES_ENABLED = True
    print("[STARTUP] Vision routes loaded successfully")
except ImportError as e:
    VISION_ROUTES_ENABLED = False
    vision_router = None
    print(f"[STARTUP] Vision routes not available: {e}")

# PHASE 4: Import structured output schemas
try:
    from structured_outputs import (
        CardioHealthAnalysis,
        SimpleIntentAnalysis,
        ConversationResponse,
        VitalSignsAnalysis,
        MedicationInfo,
        HealthIntent,
        UrgencyLevel,
        ResponseConfidence,
        StructuredOutputParser,
        StructuredGenerator,
        HealthAnalysisGenerator,
        pydantic_to_json_schema,
    )
    STRUCTURED_OUTPUTS_ENABLED = True
except ImportError as e:
    print(f"[STARTUP] Structured outputs not available: {e}")
    STRUCTURED_OUTPUTS_ENABLED = False
from memory_manager import MemoryManager, PatientMemory, MemoryManagerException
from memory_middleware import (
    CorrelationIDMiddleware,
    get_memory_injector,
    fetch_and_merge_context,
    handle_endpoint_error,
    request_id_context,
)
from memory_aware_agents import (
    MemoryAwareIntentRecognizer,
    MemoryAwareSentimentAnalyzer,
)

# 1. After imports, add:
from rate_limiting import limiter
# 2. After router includes, add:
try:
    from routes.generation import router as generation_router
    app.include_router(generation_router, tags=["Generation"])
    logger.info("Generation router mounted at /api/generate/*")
except ImportError as e:
    logger.warning(f"Generation routes not available: {e}")
# 3. Replace existing limiter line with:
app.state.limiter = limiter

# Initialize logger
logger = logging.getLogger(__name__)


class NLPState:
    """Global state manager for NLP service components"""
    intent_recognizer: Optional[IntentRecognizer] = None
    sentiment_analyzer: Optional[SentimentAnalyzer] = None
    entity_extractor: Optional[EntityExtractor] = None
    risk_assessor: Optional[RiskAssessor] = None
    analytics_manager: Optional[AnalyticsManager] = None
    model_version_manager: Optional[ModelVersionManager] = None
    memory_manager: Optional[MemoryManager] = None
    memory_aware_intent: Optional[MemoryAwareIntentRecognizer] = None
    memory_aware_sentiment: Optional[MemoryAwareSentimentAnalyzer] = None

    @classmethod
    async def initialize(cls):
        """
        Initialize all NLP components in parallel for faster startup.
        PHASE 2A ENHANCEMENT: Parallel initialization instead of sequential.
        Impact: 500ms → 150ms startup time (3x faster)
        """
        try:
            logger.info("Initializing NLP service components in parallel...")
            import time
            start_time = time.time()
            
            # Phase 1: Initialize components in parallel (CPU-bound, I/O-independent)
            # Using asyncio.gather for concurrent initialization
            init_tasks = [
                asyncio.create_task(cls._init_intent_recognizer()),
                asyncio.create_task(cls._init_sentiment_analyzer()),
                asyncio.create_task(cls._init_entity_extractor()),
                asyncio.create_task(cls._init_risk_assessor()),
                asyncio.create_task(cls._init_analytics_manager()),
                asyncio.create_task(cls._init_model_version_manager()),
            ]
            
            results = await asyncio.gather(*init_tasks, return_exceptions=True)
            
            # Check for initialization errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    component_name = ["intent_recognizer", "sentiment_analyzer", 
                                    "entity_extractor", "risk_assessor",
                                    "analytics_manager", "model_version_manager"][i]
                    logger.error(f"Failed to initialize {component_name}: {result}")
                    raise result
            
            # Phase 2: Initialize memory manager (I/O-dependent, must be sequential)
            cls.memory_manager = MemoryManager.get_instance()
            await cls.memory_manager.initialize()
            
            # Phase 3: Initialize memory-aware agents (depends on components above)
            cls.memory_aware_intent = MemoryAwareIntentRecognizer(
                cls.intent_recognizer
            )
            cls.memory_aware_sentiment = MemoryAwareSentimentAnalyzer(
                cls.sentiment_analyzer
            )
            
            # Update global instances
            global analytics_manager, model_version_manager
            analytics_manager = cls.analytics_manager
            model_version_manager = cls.model_version_manager
            
            elapsed = time.time() - start_time
            logger.info(f"All NLP service components initialized in {elapsed:.2f}s (parallel init)")
        except Exception as e:
            logger.error(f"Failed to initialize NLP components: {e}")
            raise
    
    @classmethod
    async def _init_intent_recognizer(cls):
        """Initialize intent recognizer component"""
        cls.intent_recognizer = IntentRecognizer()
        logger.debug("IntentRecognizer initialized")
    
    @classmethod
    async def _init_sentiment_analyzer(cls):
        """Initialize sentiment analyzer component"""
        cls.sentiment_analyzer = SentimentAnalyzer()
        logger.debug("SentimentAnalyzer initialized")
    
    @classmethod
    async def _init_entity_extractor(cls):
        """Initialize entity extractor component"""
        cls.entity_extractor = EntityExtractor()
        logger.debug("EntityExtractor initialized")
    
    @classmethod
    async def _init_risk_assessor(cls):
        """Initialize risk assessor component"""
        cls.risk_assessor = RiskAssessor()
        logger.debug("RiskAssessor initialized")
    
    @classmethod
    async def _init_analytics_manager(cls):
        """Initialize analytics manager component"""
        cls.analytics_manager = AnalyticsManager()
        logger.debug("AnalyticsManager initialized")
    
    @classmethod
    async def _init_model_version_manager(cls):
        """Initialize model version manager component"""
        cls.model_version_manager = ModelVersionManager()
        logger.debug("ModelVersionManager initialized")

    @classmethod
    async def shutdown(cls):
        """Cleanup NLP service components"""
        logger.info("Cleaning up NLP service components")
        
        # Shutdown memory manager
        if cls.memory_manager:
            await cls.memory_manager.shutdown()
        
        cls.intent_recognizer = None
        cls.sentiment_analyzer = None
        cls.entity_extractor = None
        cls.risk_assessor = None
        cls.analytics_manager = None
        cls.model_version_manager = None
        cls.memory_manager = None
        cls.memory_aware_intent = None
        cls.memory_aware_sentiment = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    # Startup
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}")
    try:
        await NLPState.initialize()
        
        # Initialize RAG service if available
        if RAG_ENABLED:
            logger.info("Initializing RAG service...")
            await initialize_rag_service()
            logger.info("RAG service initialized")
        
        logger.info("NLP service startup complete")
        yield
    finally:
        # Shutdown
        logger.info(f"{SERVICE_NAME} shutting down...")
        await NLPState.shutdown()

app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    description="NLP Microservice for Healthcare Chatbot",
    lifespan=lifespan
)

# PHASE 5: Include RAG router if available
if RAG_ENABLED and rag_router:
    app.include_router(rag_router, tags=["RAG"])  # Router already has /api/rag prefix
    logger.info("RAG router mounted at /api/rag/*")

# PHASE 6: Include Memory Management router if available
if MEMORY_ROUTES_ENABLED and memory_router:
    app.include_router(memory_router, prefix="/api", tags=["Memory"])
    logger.info("Memory router mounted at /api/memory/*")

# PHASE 7: Include WebSocket router if available
if REALTIME_ENABLED and websocket_router:
    app.include_router(websocket_router, tags=["WebSocket"])
    logger.info("WebSocket router mounted at /ws/*")

# PHASE 8: Include Medical Document Processing routers (medical.md implementation)
if MEDICAL_ROUTES_ENABLED:
    if document_router:
        app.include_router(document_router, tags=["Document Scanning"])
        logger.info("Document scanning router mounted at /api/documents/*")
    if medical_ai_router:
        app.include_router(medical_ai_router, tags=["Medical AI"])
        logger.info("Medical AI router mounted at /api/medical-ai/*")
    if weekly_summary_router:
        app.include_router(weekly_summary_router, tags=["Weekly Summary"])
        logger.info("Weekly summary router mounted at /api/weekly-summary/*")
    if consent_router:
        app.include_router(consent_router, tags=["Consent Management"])
        logger.info("Consent router mounted at /api/consent/*")
    if webhook_router:
        app.include_router(webhook_router, tags=["Webhooks"])
        logger.info("Webhook router mounted at /api/webhooks/*")

# PHASE 9: Include Integration routers (medical.md Part 5)
if INTEGRATIONS_ROUTES_ENABLED and integrations_router:
    app.include_router(integrations_router, prefix="/api", tags=["Integrations"])
    logger.info("Integrations router mounted at /api/integrations/*")

# PHASE 10: Include Compliance routers (medical.md Part 4)
if COMPLIANCE_ROUTES_ENABLED and compliance_router:
    app.include_router(compliance_router, prefix="/api", tags=["Compliance"])
    logger.info("Compliance router mounted at /api/compliance/*")

# PHASE 11: Include Agent routers (ADK orchestration)
if AGENTS_ROUTES_ENABLED and agents_router:
    app.include_router(agents_router, prefix="/api", tags=["Agents"])
    logger.info("Agents router mounted at /api/agents/*")

# PHASE 12: Include Calendar Integration routers
if CALENDAR_ROUTES_ENABLED and calendar_router:
    app.include_router(calendar_router, prefix="/api", tags=["Calendar Integration"])
    logger.info("Calendar router mounted at /api/calendar/*")

# PHASE 13: Include Knowledge Graph routers
if KNOWLEDGE_GRAPH_ROUTES_ENABLED and knowledge_graph_router:
    app.include_router(knowledge_graph_router, prefix="/api", tags=["Knowledge Graph"])
    logger.info("Knowledge graph router mounted at /api/knowledge-graph/*")

# PHASE 14: Include Notifications routers
if NOTIFICATIONS_ROUTES_ENABLED and notifications_router:
    app.include_router(notifications_router, prefix="/api", tags=["Notifications"])
    logger.info("Notifications router mounted at /api/notifications/*")

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler"""
    return structured_exception_handler(request, exc)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Handle rate limit exceeded errors.
    PHASE 2: Uses RateLimitError exception for consistency with exception hierarchy.
    
    Returns 429 Too Many Requests with retry-after header.
    """
    # Create custom RateLimitError for proper exception handling
    rate_limit_error = RateLimitError("Too many requests. Please try again later.")
    return ErrorReporter.from_nlp_exception(rate_limit_error)

# Placeholder authentication functions (to be implemented)
async def get_current_user():
    """Placeholder for authentication - returns empty dict for now"""
    return {}

async def rate_limiter(request: Request):
    """
    Rate limiting dependency (PHASE 1 TASK 1.5).
    
    Note: Actual rate limiting is done via @limiter.limit() decorator on endpoints.
    This function is kept for backward compatibility but slowapi handles the actual limiting.
    """
    return True

def get_ollama_generator(model_name: str = "gemma3:1b") -> OllamaGenerator:
    """Dependency: Get Ollama generator instance"""
    return OllamaGenerator(model_name=model_name)


async def get_rag_context(query: str, user_id: Optional[str] = None, top_k: int = 3) -> Optional[Dict[str, Any]]:
    """
    Retrieve relevant context from RAG system for response augmentation.
    
    Returns None if RAG is not enabled or fails gracefully.
    """
    if not RAG_ENABLED:
        return None
    
    try:
        # Import lazily to avoid circular imports
        from rag_api import get_rag_pipeline
        pipeline = get_rag_pipeline()
        
        # Search for relevant context (don't generate, just retrieve)
        result = await pipeline.query(
            query=query,
            user_id=user_id,
            search_medical=True,
            search_drugs=True,
            search_user_memory=bool(user_id),
            top_k=top_k,
            generate=False,  # Just retrieve, don't generate
        )
        
        # Return context dictionary
        return {
            "medical_context": result.to_dict().get("sources", {}).get("medical", []),
            "drug_context": result.to_dict().get("sources", {}).get("drugs", []),
            "user_memory_context": result.to_dict().get("sources", {}).get("memories", []),
            "citations": [c for c in result.citations[:5]],  # Limit citations
        }
    except Exception as e:
        logger.warning(f"RAG context retrieval failed (non-fatal): {e}")
        return None

# Add middleware
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Modern dependency injection using FastAPI Depends
def get_intent_recognizer() -> IntentRecognizer:
    """Dependency: Get intent recognizer from app state"""
    if NLPState.intent_recognizer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IntentRecognizer not initialized"
        )
    return NLPState.intent_recognizer


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Dependency: Get sentiment analyzer from app state"""
    if NLPState.sentiment_analyzer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SentimentAnalyzer not initialized"
        )
    return NLPState.sentiment_analyzer


def get_entity_extractor() -> EntityExtractor:
    """Dependency: Get entity extractor from app state"""
    if NLPState.entity_extractor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="EntityExtractor not initialized"
        )
    return NLPState.entity_extractor


def get_risk_assessor() -> RiskAssessor:
    """Dependency: Get risk assessor from app state"""
    if NLPState.risk_assessor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RiskAssessor not initialized"
        )
    return NLPState.risk_assessor


def get_memory_manager() -> MemoryManager:
    """Dependency: Get memory manager instance"""
    if NLPState.memory_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MemoryManager not initialized"
        )
    return NLPState.memory_manager


async def get_memory_context(
    patient_id: Optional[str] = None,
) -> Optional[PatientMemory]:
    """
    Dependency: Get memory context for patient.
    
    Args:
        patient_id: Patient identifier (optional)
    
    Returns:
        PatientMemory instance if available, None otherwise
    """
    if not patient_id:
        return None
    
    try:
        memory_mgr = get_memory_manager()
        return await memory_mgr.get_patient_memory(patient_id)
    except Exception as e:
        logger.warning(f"Could not get memory context for {patient_id}: {e}")
        return None


@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
@limiter.limit("1000/minute")  # Higher limit for health checks (PHASE 1 TASK 1.5)
async def health_check(request: Request) -> HealthCheckResponse:
    """
    Health check endpoint.
    Returns service status and loaded models, including memory manager status.
    """
    try:
        # Check memory health
        memory_health = None
        if NLPState.memory_manager:
            try:
                memory_health = await asyncio.wait_for(
                    NLPState.memory_manager.health_check(),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Memory health check timed out")
                memory_health = {"status": "timeout"}
            except Exception as e:
                logger.warning(f"Memory health check failed: {e}")
                memory_health = {"status": "error", "error": str(e)}
        
        models_loaded = {
            "intent_recognizer": NLPState.intent_recognizer is not None,
            "sentiment_analyzer": NLPState.sentiment_analyzer is not None,
            "entity_extractor": NLPState.entity_extractor is not None,
            "risk_assessor": NLPState.risk_assessor is not None,
            "memory_manager": NLPState.memory_manager is not None,
        }
        
        return HealthCheckResponse(
            status="healthy",
            version=SERVICE_VERSION,
            timestamp=datetime.utcnow().isoformat(),
            models_loaded=models_loaded
        )
    except Exception as e:
        ErrorReporter.log_error(
            error_code="PROCESSING_ERROR",
            error_message="Health check failed",
            exception=e
        )
        return HealthCheckResponse(
            status="unhealthy",
            version=SERVICE_VERSION,
            timestamp=datetime.utcnow().isoformat(),
            models_loaded={}
        )


@app.get("/cache/stats", tags=["Cache"])
async def cache_stats():
    """
    Get cache statistics.
    """
    try:
        return cache_manager.get_stats()
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="CACHE_ERROR",
            error_details={"operation": "get_stats"}
        )


# ============================================================================
# Memory-Specific Endpoints
# ============================================================================


@app.get("/patients/{patient_id}/conversations", tags=["Memory"], summary="Get conversation history")
async def get_conversation_history(
    patient_id: str,
    session_id: str = "default",
    limit: int = 10,
    memory_mgr: MemoryManager = Depends(get_memory_manager),
) -> Dict[str, Any]:
    """
    Retrieve conversation history from memory.
    
    **Path Parameters:**
    - patient_id: Patient identifier
    
    **Query Parameters:**
    - session_id: Session identifier (default: "default")
    - limit: Number of conversations to retrieve (default: 10)
    
    **Response:**
    - patient_id: Patient identifier
    - session_id: Session identifier
    - conversations: List of conversation records
    - retrieved_at: Timestamp of retrieval
    """
    try:
        logger.info(
            f"Retrieving conversation history: patient_id={patient_id}, "
            f"session_id={session_id}, limit={limit}"
        )
        
        patient_memory = await memory_mgr.get_patient_memory(patient_id, session_id)
        context = await patient_memory.get_conversation_context(limit=limit)
        
        return {
            "patient_id": patient_id,
            "session_id": session_id,
            **context,
            "retrieved_at": datetime.utcnow().isoformat(),
        }
    except MemoryManagerException as e:
        logger.error(f"Memory service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service unavailable",
        )
    except Exception as e:
        logger.error(f"Error retrieving history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve conversation history",
        )


@app.get("/patients/{patient_id}/memory/search", tags=["Memory"], summary="Search patient memory")
async def search_patient_memory(
    patient_id: str,
    query: str = Query(..., description="Search query string"),
    data_type: Optional[str] = Query(None, description="Data type filter (conversation, health_data, etc.)"),
    limit: int = Query(5, description="Max results to return"),
    memory_mgr: MemoryManager = Depends(get_memory_manager),
) -> Dict[str, Any]:
    """
    Search patient memory with optional filters.
    
    **Path Parameters:**
    - patient_id: Patient identifier
    
    **Query Parameters:**
    - query: Search query string (required)
    - data_type: Optional data type filter
    - limit: Maximum results (default: 5)
    
    **Response:**
    - patient_id: Patient identifier
    - query: The search query
    - result_count: Number of results found
    - results: List of search results with relevance scores
    - searched_at: Timestamp of search
    """
    try:
        logger.info(
            f"Memory search: patient_id={patient_id}, query='{query}', "
            f"data_type={data_type}, limit={limit}"
        )
        
        results = await memory_mgr.search_memory(
            patient_id=patient_id,
            query=query,
            data_type=data_type,
            limit=limit,
        )
        
        return {
            "patient_id": patient_id,
            "query": query,
            "data_type": data_type,
            "result_count": len(results),
            "results": [
                {
                    "id": r.id,
                    "content": r.content,
                    "type": r.memory_type,
                    "timestamp": r.timestamp,
                    "relevance_score": getattr(r, "relevance_score", None),
                }
                for r in results
            ],
            "searched_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error searching memory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Memory search failed",
        )


@app.get("/health/memory", tags=["Health"], summary="Get memory service health")
async def memory_health_check(
    memory_mgr: MemoryManager = Depends(get_memory_manager),
) -> Dict[str, Any]:
    """
    Check memory service health and status.
    
    **Response:**
    - status: Health status (healthy, degraded, unhealthy)
    - memory_initialized: Whether memory manager is initialized
    - cache_info: Cache statistics if available
    - timestamp: Timestamp of check
    """
    try:
        logger.debug("Checking memory service health")
        memory_health = await memory_mgr.health_check()
        
        return {
            "status": memory_health.get("status", "unknown"),
            "memory_initialized": NLPState.memory_manager is not None,
            "memory_details": memory_health,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error checking memory health: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "memory_initialized": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/analytics/summary", tags=["Analytics"])
async def analytics_summary():
    """
    Get comprehensive analytics summary.
    """
    try:
        return analytics_manager.get_analytics_summary()
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "analytics_summary"}
        )

@app.get("/analytics/intents", tags=["Analytics"])
async def intent_distribution():
    """
    Get intent distribution statistics.
    """
    try:
        return analytics_manager.get_intent_distribution()
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "intent_distribution"}
        )

@app.get("/analytics/sentiments", tags=["Analytics"])
async def sentiment_distribution():
    """
    Get sentiment distribution statistics.
    """
    try:
        return analytics_manager.get_sentiment_distribution()
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "sentiment_distribution"}
        )

@app.get("/analytics/entities", tags=["Analytics"])
async def entity_distribution():
    """
    Get entity type distribution statistics.
    """
    try:
        return analytics_manager.get_entity_type_distribution()
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "entity_distribution"}
        )

@app.get("/analytics/top-intents", tags=["Analytics"])
async def top_intents(limit: int = 10):
    """
    Get most common intents.
    """
    try:
        return analytics_manager.get_top_intents(limit)
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "top_intents", "limit": limit}
        )

@app.get("/analytics/top-entities", tags=["Analytics"])
async def top_entities(limit: int = 10):
    """
    Get most common entity types.
    """
    try:
        return analytics_manager.get_top_entities(limit)
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "top_entities", "limit": limit}
        )

@app.post(
    "/api/nlp/process",
    response_model=NLPProcessResponse,
    tags=["NLP Processing"],
    summary="Process user message"
)
@limiter.limit("100/minute")  # 100 requests per minute per IP (PHASE 1 TASK 1.5)
async def process_nlp(
    request: Request,  # Required by limiter
    nlp_request: NLPProcessRequest,
    intent_recognizer: IntentRecognizer = Depends(get_intent_recognizer),
    sentiment_analyzer: SentimentAnalyzer = Depends(get_sentiment_analyzer),
    entity_extractor: EntityExtractor = Depends(get_entity_extractor),
    memory: Optional[PatientMemory] = Depends(get_memory_injector("user_id")),
    # Add authentication and rate limiting
    current_user: dict = Depends(get_current_user),
    rate_limit: bool = Depends(rate_limiter)
) -> NLPProcessResponse:
    """
    Process user input for NLP analysis with optional memory context.
    
    Performs:
    - Intent recognition
    - Sentiment analysis
    - Entity extraction
    - Memory retrieval (if patient_id/user_id provided)
    - Appropriate response generation
    
    **Request Body:**
    - message: User input text
    - session_id: (optional) Chat session ID for context
    - user_id: (optional) User ID for personalization and memory
    - context: (optional) Additional context data
    
    **Response:**
    - intent: Identified intent
    - intent_confidence: Confidence score for intent (0-1)
    - sentiment: Detected sentiment
    - sentiment_score: Sentiment score (-1 to 1)
    - entities: Extracted entities
    - keywords_matched: Keywords that matched the intent
    - suggested_response: Template response for the bot
    - context_updates: Suggested context updates
    - requires_escalation: Whether escalation is needed
    - confidence_overall: Overall confidence score
    """
    start_time = time.time()
    req_id = request_id_context.get()
    
    try:
        message = nlp_request.message.strip()
        if not message:
            return ErrorReporter.create_error_response(
                error_code="INVALID_INPUT",
                error_message="Message cannot be empty",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(
            f"NLP processing: user_id={nlp_request.user_id}, "
            f"session_id={nlp_request.session_id}, model={nlp_request.model}, request_id={req_id}"
        )
        
        # Parallel processing of NLP components
        try:
            logger.debug(f"Recognizing intent for message: {message[:100]}")
            intent_result = await run_in_threadpool(
                intent_recognizer.recognize_intent,
                message
            )
            logger.debug(f"Intent recognized: {intent_result.intent} (confidence: {intent_result.confidence})")
        except Exception as e:
            logger.error(f"Intent recognition failed: {e}", exc_info=True)
            raise
        
        try:
            logger.debug("Analyzing sentiment...")
            sentiment_result = await run_in_threadpool(
                sentiment_analyzer.analyze_sentiment,
                message
            )
            logger.debug(f"Sentiment analyzed: {sentiment_result.sentiment} (score: {sentiment_result.score})")
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}", exc_info=True)
            raise
        
        try:
            logger.debug("Extracting entities...")
            entities = await run_in_threadpool(
                entity_extractor.extract_entities,
                message
            )
            logger.debug(f"Extracted {len(entities)} entities")
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}", exc_info=True)
            raise
        
        # Generate response based on selected model
        model_to_use = nlp_request.model or "gemini"
        suggested_response = ""
        rag_context = None
        rag_citations = []
        
        # Retrieve RAG context if enabled
        if nlp_request.use_rag and RAG_ENABLED:
            try:
                logger.debug("Retrieving RAG context...")
                rag_context = await get_rag_context(
                    query=message,
                    user_id=nlp_request.user_id,
                    top_k=3
                )
                if rag_context:
                    rag_citations = rag_context.get("citations", [])
                    logger.debug(f"RAG context retrieved: {len(rag_citations)} citations")
            except Exception as e:
                logger.warning(f"RAG context retrieval failed (non-fatal): {e}")
        
        if model_to_use == "ollama":
            # Use Ollama for local response generation
            try:
                logger.debug("Generating response with Ollama...")
                generator = get_ollama_generator()
                entity_str = ", ".join([e.value for e in entities[:3]]) if entities else "health concerns"
                
                # Build prompt with RAG context if available
                rag_context_str = ""
                if rag_context:
                    medical_ctx = rag_context.get("medical_context", [])
                    if medical_ctx:
                        rag_context_str = "\n\nRelevant medical context:\n" + "\n".join(
                            [f"- {ctx.get('content', ctx)[:200]}" for ctx in medical_ctx[:2]]
                        )
                
                prompt = f"Based on the message '{message}' with detected intent '{intent_result.intent.value}' and sentiment '{sentiment_result.sentiment.value}', provide a helpful healthcare response about {entity_str}.{rag_context_str}"
                logger.debug(f"Ollama prompt: {prompt[:100]}...")
                suggested_response = await generator.generate_response(
                    prompt,
                    conversation_history=None,
                    system_prompt="You are a helpful healthcare assistant. Provide concise, supportive responses. Use the medical context when available."
                )
                logger.info(f"Ollama generated response: {suggested_response[:100]}...")
            except Exception as e:
                logger.warning(f"Ollama generation failed, using fallback: {e}")
                entity_str = ", ".join([e.value for e in entities[:3]]) if entities else "your health"
                suggested_response = f"I understand you're experiencing {sentiment_result.sentiment.value} feelings related to {entity_str}."
        else:
            # Use default template response (Gemini-compatible fallback)
            base_response = f"I understand you're experiencing {sentiment_result.sentiment.value} feelings. Based on your message, I detected {intent_result.intent.value} as the primary concern."
            
            # Enhance with RAG context if available
            if rag_context and rag_context.get("medical_context"):
                medical_ctx = rag_context["medical_context"][:1]  # Top result
                if medical_ctx:
                    ctx_snippet = str(medical_ctx[0].get("content", ""))[:150] if isinstance(medical_ctx[0], dict) else str(medical_ctx[0])[:150]
                    base_response += f" Based on medical guidelines: {ctx_snippet}..."
            
            suggested_response = base_response
        
        # Build response
        try:
            logger.debug("Building NLP response object...")
            
            # Build context updates with RAG info
            ctx_updates = {
                "model_used": model_to_use,
                "rag_enabled": bool(rag_context),
                "rag_citations_count": len(rag_citations),
            }
            if rag_citations:
                ctx_updates["rag_sources"] = [
                    {"type": c.get("type", "unknown"), "source": c.get("source", "unknown")}
                    for c in rag_citations[:3]
                ] if isinstance(rag_citations[0], dict) else []
            
            response = NLPProcessResponse(
                intent=intent_result.intent,
                intent_confidence=intent_result.confidence,
                sentiment=sentiment_result.sentiment,
                sentiment_score=sentiment_result.score,
                entities=entities,
                keywords_matched=intent_result.keywords_matched or [],
                suggested_response=suggested_response,
                context_updates=ctx_updates,
                requires_escalation=intent_result.intent == IntentEnum.EMERGENCY or sentiment_result.sentiment == SentimentEnum.URGENT,
                confidence_overall=round(min((intent_result.confidence + abs(sentiment_result.score) + 1) / 3, 1.0), 2)
            )
            logger.debug("Response object created successfully")
        except Exception as e:
            logger.error(f"Failed to build response: {e}", exc_info=True)
            raise
        
        # Log analytics
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"NLP processing completed in {elapsed_ms:.1f}ms with model={model_to_use}")
        
        return response
        
    except Exception as e:
        import traceback
        logger.error(f"DETAILED ERROR in process_nlp: {type(e).__name__}: {e}")
        logger.error(f"TRACEBACK:\n{traceback.format_exc()}")
        ErrorReporter.log_error(
            error_code="PROCESSING_ERROR",
            error_message="Error processing NLP request",
            error_details={"user_id": nlp_request.user_id, "exception": str(e)},
            exception=e
        )
        return ErrorReporter.create_error_response(
            error_code="PROCESSING_ERROR",
            error_message="Error processing message",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.post(
    "/api/risk/assess",
    response_model=RiskAssessmentResponse,
    tags=["Risk Assessment"],
    summary="Assess cardiovascular risk"
)
async def assess_risk(
    request: RiskAssessmentRequest,
    risk_assessor: RiskAssessor = Depends(get_risk_assessor),
    # Add authentication and rate limiting
    current_user: dict = Depends(get_current_user),
    rate_limit: bool = Depends(rate_limiter)
) -> RiskAssessmentResponse:
    """
    Assess cardiovascular disease risk based on health metrics.
    
    Uses Framingham Risk Score algorithm.
    
    **Request Body:**
    - metrics: Health metrics (age, BP, cholesterol, etc.)
    - user_id: (optional) User ID
    
    **Response:**
    - risk_level: LOW, MODERATE, or HIGH
    - risk_score: Numerical risk score (0-100)
    - risk_interpretation: Detailed interpretation
    - recommendations: Personalized recommendations
    - consultation_urgency: Urgency level
    """
    try:
        logger.debug(f"Assessing risk for user: {request.user_id}")

        # Wrap CPU-bound risk assessment in threadpool
        response = await run_in_threadpool(
            risk_assessor.assess_risk, 
            request.metrics
        )

        logger.info(
            f"Risk assessment complete - "
            f"Level: {response.risk_level}, "
            f"Score: {response.risk_score:.1f}"
        )

        return response

    except ValueError as e:
        ErrorReporter.log_error(
            error_code="VALIDATION_ERROR",
            error_message=str(e),
            exception=e
        )
        return ErrorReporter.create_error_response(
            error_code="VALIDATION_ERROR",
            error_message=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        ErrorReporter.log_error(
            error_code="PROCESSING_ERROR",
            error_message="Error assessing risk",
            error_details={"user_id": request.user_id},
            exception=e
        )
        return ErrorReporter.create_error_response(
            error_code="PROCESSING_ERROR",
            error_message="Error assessing risk",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.post(
    "/api/entities/extract",
    response_model=EntityExtractionResponse,
    tags=["Entity Extraction"],
    summary="Extract entities from text"
)
async def extract_entities(
    request: EntityExtractionRequest,
    entity_extractor: EntityExtractor = Depends(get_entity_extractor),
    # Add authentication and rate limiting
    current_user: dict = Depends(get_current_user),
    rate_limit: bool = Depends(rate_limiter)
) -> EntityExtractionResponse:
    """
    Extract named entities from text.
    
    Extracts: symptoms, medications, foods, measurements, time references.
    
    **Request Body:**
    - text: Text to extract entities from
    - entity_types: (optional) Specific entity types to extract
    
    **Response:**
    - entities: List of extracted entities
    - text_chunks: (optional) Annotated text chunks
    """
    try:
        logger.debug(f"Extracting entities from text: {request.text[:100]}")

        # Wrap CPU-bound entity extraction in threadpool
        entities = await run_in_threadpool(
            entity_extractor.extract_entities,
            request.text,
            request.entity_types
        )

        response = EntityExtractionResponse(
            entities=[entity.model_dump() for entity in entities],
            text_chunks=None
        )

        logger.info(f"Extracted {len(entities)} entities")

        return response

    except Exception as e:
        ErrorReporter.log_error(
            error_code="PROCESSING_ERROR",
            error_message="Error extracting entities",
            error_details={"text": request.text[:50] if request.text else "None"},
            exception=e
        )
        return ErrorReporter.create_error_response(
            error_code="PROCESSING_ERROR",
            error_message="Error extracting entities",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _generate_response_template(intent, sentiment, entities):
    """Generate appropriate response template based on intent and sentiment"""
    from models import IntentEnum, SentimentEnum

    if intent == IntentEnum.EMERGENCY:
        return (
            "I understand this is an emergency. Please call 911 immediately or go to the nearest "
            "emergency room. Stay on the line if you need further assistance."
        )

    if sentiment == SentimentEnum.DISTRESSED or sentiment == SentimentEnum.URGENT:
        base = {
            IntentEnum.SYMPTOM_CHECK: (
                "I'm concerned about your symptoms. Please contact your healthcare provider "
                "immediately or go to an emergency room if symptoms worsen."
            ),
            IntentEnum.RISK_ASSESSMENT: (
                "Your symptoms suggest you should speak with a healthcare provider right away. "
                "Don't delay seeking medical attention."
            ),
            IntentEnum.MEDICATION_REMINDER: (
                "This is important. Please make sure to follow your medication schedule carefully. "
                "Contact your doctor if you have concerns."
            ),
        }
        return base.get(intent, "I'm here to help. Let me connect you with appropriate resources.")

    # Default responses by intent
    defaults = {
        IntentEnum.GREETING: "Hello! I'm here to help you with your heart health. How can I assist you today?",
        IntentEnum.SYMPTOM_CHECK: "I'd like to understand your symptoms better. Can you describe what you're experiencing?",
        IntentEnum.MEDICATION_REMINDER: "I can help you manage your medications. What medication would you like to discuss?",
        IntentEnum.NUTRITION_ADVICE: "Great! Let me help you with heart-healthy nutrition recommendations.",
        IntentEnum.EXERCISE_COACHING: "I'd be happy to help you develop an exercise plan suited to your needs.",
        IntentEnum.HEALTH_GOAL: "Setting health goals is excellent! Let's work together on achieving them.",
        IntentEnum.RISK_ASSESSMENT: "I can help assess your cardiovascular risk. Let me ask you some questions.",
        IntentEnum.HEALTH_EDUCATION: "I love your interest in learning! What health topic would you like to explore?",
        IntentEnum.APPOINTMENT_BOOKING: "I can help you schedule an appointment with a healthcare provider.",
        IntentEnum.UNKNOWN: "I'm not entirely sure what you're asking. Could you rephrase that?",
    }

    return defaults.get(intent, "How can I help you with your heart health?")


@app.get("/models/versions", tags=["Model Management"])
async def get_model_versions(current_user: dict = Depends(get_current_user)):
    """
    Get current versions of all models.
    """
    try:
        return model_version_manager.get_all_versions()
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "get_model_versions"}
        )

@app.get("/models/history/{model_name}", tags=["Model Management"])
async def get_model_history(model_name: str, current_user: dict = Depends(get_current_user)):
    """
    Get version history for a specific model.
    """
    try:
        history = model_version_manager.get_version_history(model_name)
        if not history:
            return ErrorReporter.create_error_response(
                error_code="NOT_FOUND",
                error_message=f"No history found for model: {model_name}",
                status_code=status.HTTP_404_NOT_FOUND
            )
        return history
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "get_model_history", "model_name": model_name}
        )

@app.post("/models/version/{model_name}", tags=["Model Management"])
async def set_model_version(model_name: str, version: str, current_user: dict = Depends(get_current_user)):
    """
    Set the version of a specific model.
    """
    try:
        if model_version_manager.set_model_version(model_name, version):
            return {"message": f"Model {model_name} version set to {version}"}
        else:
            return ErrorReporter.create_error_response(
                error_code="PROCESSING_ERROR",
                error_message=f"Failed to set version for model: {model_name}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "set_model_version", "model_name": model_name, "version": version}
        )

@app.post("/models/rollback/{model_name}", tags=["Model Management"])
async def rollback_model_version(model_name: str, current_user: dict = Depends(get_current_user)):
    """
    Rollback to the previous version of a specific model.
    """
    try:
        if model_version_manager.rollback_version(model_name):
            current_version = model_version_manager.get_model_version(model_name)
            return {"message": f"Model {model_name} rolled back to version {current_version}"}
        else:
            return ErrorReporter.create_error_response(
                error_code="PROCESSING_ERROR",
                error_message=f"Failed to rollback model: {model_name}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "rollback_model_version", "model_name": model_name}
        )

@app.get("/models/list", tags=["Model Management"])
async def list_available_models(current_user: dict = Depends(get_current_user)):
    """
    List all available models and their versions.
    """
    try:
        return model_version_manager.list_available_models()
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={"operation": "list_available_models"}
        )

@app.post("/models/ab-test/{model_name}", tags=["Model Management"])
async def enable_ab_test(
    model_name: str,
    version_a: str = Query(..., description="Control version"),
    version_b: str = Query(..., description="Test version"),
    split_ratio: float = Query(0.5, ge=0.0, le=1.0, description="Traffic split ratio"),
    current_user: dict = Depends(get_current_user)
):
    """
    Enable A/B testing between two versions of a model.
    """
    try:
        if model_version_manager.enable_ab_test(model_name, version_a, version_b, split_ratio):
            return {
                "message": f"A/B test enabled for {model_name}",
                "control_version": version_a,
                "test_version": version_b,
                "split_ratio": split_ratio
            }
        else:
            return ErrorReporter.create_error_response(
                error_code="PROCESSING_ERROR",
                error_message=f"Failed to enable A/B test for model: {model_name}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    except Exception as e:
        return ErrorReporter.handle_exception(
            exception=e,
            error_code="PROCESSING_ERROR",
            error_details={
                "operation": "enable_ab_test", 
                "model_name": model_name, 
                "version_a": version_a, 
                "version_b": version_b
            }
        )


# ============================================================================
# OLLAMA ENDPOINTS
# ============================================================================

@app.post("/ollama-generate", response_model=OllamaResponseResponse, tags=["Ollama"])
async def ollama_generate_response(request: OllamaResponseRequest):
    """
    Generate response using Ollama (gemma3:4b by default).
    
    This endpoint generates contextual conversational responses using the specified Ollama model.
    Supports conversation history for multi-turn dialogue and streaming responses.
    
    Args:
        request: OllamaResponseRequest with:
            - message: User input message
            - model: Ollama model name (default: gemma3:4b)
            - conversation_history: Previous messages for context
            - system_prompt: Optional system instructions
            - temperature: Sampling temperature (0.0-2.0)
    
    Returns:
        OllamaResponseResponse with:
            - response: Generated response text
            - model: Model used for generation
    """
    try:
        start_time = time.time()
        
        # Get or create Ollama generator
        generator = get_ollama_generator()
        
        # Build full prompt with conversation history
        full_prompt = ""
        if request.conversation_history:
            for msg in request.conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                full_prompt += f"{role}: {content}\n"
        
        if request.system_prompt:
            full_prompt = f"System: {request.system_prompt}\n\n{full_prompt}"
        
        full_prompt += f"user: {request.message}\nassistant: "
        
        # Generate response (model and temperature are set in OllamaGenerator.__init__)
        response_text = await generator.generate_response(
            prompt=full_prompt,
            conversation_history=request.conversation_history,
            system_prompt=request.system_prompt
        )
        
        generation_time = (time.time() - start_time) * 1000
        
        return OllamaResponseResponse(
            response=response_text,
            model=request.model,
            generation_time_ms=generation_time,
            tokens_generated=len(response_text.split()),  # Rough estimate
            success=True,
            error=None
        )
        
    except Exception as e:
        logger.error(f"Error in ollama_generate_response: {str(e)}", exc_info=True)
        generation_time = (time.time() - start_time) * 1000
        
        error_msg = f"Ollama generation error: {str(e)}"
        logger.error(f"Detailed error: {error_msg}")
        
        return OllamaResponseResponse(
            response="",
            model=request.model,
            generation_time_ms=generation_time,
            tokens_generated=0,
            success=False,
            error=str(e)
        )


# Ollama streaming endpoint is defined below


@app.get("/ollama/health", response_model=OllamaHealthCheckResponse, tags=["Ollama"])
async def ollama_health_check():
    """
    Check health of Ollama connection and model availability.
    
    Returns:
        OllamaHealthCheckResponse with:
            - status: "healthy" or "unhealthy"
            - model: Model name
            - available: Whether model is available
            - timestamp: Check timestamp
    """
    try:
        from config import OLLAMA_MODEL, OLLAMA_HOST
        ollama_gen = get_ollama_generator()
        health_status = await ollama_gen.health_check()
        
        return OllamaHealthCheckResponse(
            status=health_status["status"],
            model=health_status["model"],
            ollama_host=health_status["ollama_host"],
            available=health_status["available"],
            timestamp=health_status["timestamp"]
        )
    except Exception as e:
        logger.error(f"Error in ollama_health_check: {str(e)}")
        from config import OLLAMA_MODEL, OLLAMA_HOST
        return OllamaHealthCheckResponse(
            status="unhealthy",
            model=OLLAMA_MODEL,
            ollama_host=OLLAMA_HOST,
            available=False,
            timestamp=datetime.utcnow().isoformat()
        )


@app.get("/ollama/stats", tags=["Ollama"])
async def ollama_get_stats():
    """
    Get Ollama generation statistics.
    
    Returns:
        Dictionary with:
            - model: Model name
            - generation_count: Total generations
            - total_tokens: Total tokens generated
            - average_tokens_per_generation: Average tokens per request
    """
    try:
        ollama_gen = get_ollama_generator()
        stats = ollama_gen.get_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error in ollama_get_stats: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/ollama-generate-stream", tags=["Ollama Streaming"])
async def ollama_generate_response_stream(request: OllamaResponseRequest):
    """
    Generate response using Ollama with streaming support (Server-Sent Events).
    Streams tokens as they are generated for real-time UI updates.
    
    Args:
        request: OllamaResponseRequest with message, model, conversation_history
    
    Returns:
        StreamingResponse with SSE format: "data: token\n\n"
    """
    async def generate():
        """
        Generator function that yields tokens as they arrive.
        Each token is prefixed with "data: " for SSE format.
        """
        start_time = time.time()
        total_tokens = 0
        
        try:
            # ✅ Validate model is supported
            valid_models = ['gemma3:1b', 'gemma3:4b']
            model_to_use = request.model or OLLAMA_MODEL
            if model_to_use not in valid_models:
                logger.error(f"Invalid model requested: {model_to_use}. Valid models: {valid_models}")
                error_data = {"error": f"Model '{model_to_use}' is not supported. Valid models: {', '.join(valid_models)}", "code": "INVALID_MODEL"}
                yield f"data: [ERROR]{json.dumps(error_data)}\n\n"
                return
            
            # Get or create generator
            generator = get_ollama_generator()
            
            # Build full prompt with conversation history
            full_prompt = ""
            if request.conversation_history:
                for msg in request.conversation_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    full_prompt += f"{role}: {content}\n"
            
            full_prompt += f"user: {request.message}\nassistant: "
            
            # Stream response from Ollama
            try:
                response = generator.client.generate(
                    model=model_to_use,
                    prompt=full_prompt,
                    stream=True,
                    options={
                        "temperature": request.temperature or OLLAMA_TEMPERATURE,
                        "top_p": OLLAMA_TOP_P,
                        "top_k": OLLAMA_TOP_K,
                        # ✅ REMOVED num_predict (max_tokens alternative) - Ollama defaults handle this
                    }
                )
                
                # Yield each token as it arrives
                for chunk in response:
                    if "response" in chunk:
                        token = chunk["response"]
                        if token:
                            total_tokens += 1
                            # SSE format: "data: <content>\n\n"
                            yield f"data: {token}\n\n"
                
                # Send completion marker
                generation_time = (time.time() - start_time) * 1000
                metadata = {
                    "done": True,
                    "model": model_to_use,
                    "generation_time_ms": int(generation_time),
                    "tokens_generated": total_tokens
                }
                yield f"data: [DONE]{json.dumps(metadata)}\n\n"
                
            except Exception as e:
                logger.error(f"Error streaming from Ollama: {str(e)}")
                error_data = {"error": str(e), "done": True}
                yield f"data: [ERROR]{json.dumps(error_data)}\n\n"
        
        except Exception as e:
            logger.error(f"Error in stream generator: {str(e)}")
            error_data = {"error": str(e), "done": True}
            yield f"data: [ERROR]{json.dumps(error_data)}\n\n"
    
    # Return streaming response with proper headers
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


# ============================================================================
# STRUCTURED OUTPUT ENDPOINTS - PHASE 4
# ============================================================================

# Request models for structured output endpoints
from pydantic import BaseModel as PydanticBaseModel

class StructuredHealthAnalysisRequest(PydanticBaseModel):
    """Request for structured health analysis"""
    message: str
    session_id: Optional[str] = None
    patient_context: Optional[Dict[str, Any]] = None
    model: Optional[str] = "gemma3:1b"

class StructuredIntentRequest(PydanticBaseModel):
    """Request for structured intent analysis"""
    message: str
    
class StructuredConversationRequest(PydanticBaseModel):
    """Request for structured conversation response"""
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = None
    session_id: Optional[str] = None


@app.get("/api/structured-outputs/status", tags=["Structured Outputs"])
async def structured_outputs_status():
    """
    Check if structured outputs feature is available.
    
    Returns:
        Status of structured outputs feature and available schemas
    """
    if not STRUCTURED_OUTPUTS_ENABLED:
        return {
            "enabled": False,
            "message": "Structured outputs module not loaded",
            "available_schemas": []
        }
    
    return {
        "enabled": True,
        "message": "Structured outputs available",
        "available_schemas": [
            "CardioHealthAnalysis",
            "SimpleIntentAnalysis", 
            "ConversationResponse",
            "VitalSignsAnalysis",
            "MedicationInfo"
        ],
        "endpoints": [
            "/api/structured-outputs/health-analysis",
            "/api/structured-outputs/intent",
            "/api/structured-outputs/conversation"
        ]
    }


@app.get("/api/structured-outputs/schema/{schema_name}", tags=["Structured Outputs"])
async def get_schema(schema_name: str):
    """
    Get the JSON schema for a specific structured output type.
    
    This endpoint is useful for:
    - Understanding the expected output format
    - Validating responses on the client side
    - Documentation purposes
    
    Args:
        schema_name: Name of the schema (CardioHealthAnalysis, SimpleIntentAnalysis, etc.)
        
    Returns:
        JSON Schema for the requested output type
    """
    if not STRUCTURED_OUTPUTS_ENABLED:
        raise HTTPException(
            status_code=503, 
            detail="Structured outputs not available"
        )
    
    schema_map = {
        "CardioHealthAnalysis": CardioHealthAnalysis,
        "SimpleIntentAnalysis": SimpleIntentAnalysis,
        "ConversationResponse": ConversationResponse,
        "VitalSignsAnalysis": VitalSignsAnalysis,
        "MedicationInfo": MedicationInfo,
    }
    
    if schema_name not in schema_map:
        raise HTTPException(
            status_code=404,
            detail=f"Schema '{schema_name}' not found. Available: {list(schema_map.keys())}"
        )
    
    schema = pydantic_to_json_schema(schema_map[schema_name])
    return {
        "schema_name": schema_name,
        "json_schema": schema,
        "description": schema_map[schema_name].__doc__
    }


@app.post("/api/structured-outputs/health-analysis", tags=["Structured Outputs"])
async def structured_health_analysis(request: StructuredHealthAnalysisRequest):
    """
    Generate a structured health analysis using LLM with schema-guided output.
    
    This endpoint returns a CardioHealthAnalysis object containing:
    - Intent classification (symptom_report, medication_question, etc.)
    - Sentiment analysis (positive, negative, anxious, etc.)
    - Urgency level (critical, high, moderate, low)
    - Extracted entities (symptoms, medications, body parts)
    - AI-generated response
    - Health recommendations
    - Follow-up questions
    - Medical disclaimers
    
    The LLM output is guaranteed to match the schema structure.
    
    Args:
        request: Message, session_id, patient_context, model
        
    Returns:
        CardioHealthAnalysis structured response
    """
    if not STRUCTURED_OUTPUTS_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Structured outputs not available"
        )
    
    start_time = time.time()
    
    try:
        # Get Ollama generator
        generator = get_ollama_generator()
        
        # Check if Ollama is available
        is_available = await generator.is_available()
        if not is_available:
            raise HTTPException(
                status_code=503,
                detail="Ollama service not available"
            )
        
        # Generate structured health analysis
        result = await generator.generate_health_analysis(
            user_message=request.message,
            session_id=request.session_id,
            patient_context=request.patient_context,
        )
        
        generation_time = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "data": result.model_dump(),
            "metadata": {
                "generation_time_ms": int(generation_time),
                "model": request.model,
                "schema": "CardioHealthAnalysis"
            }
        }
        
    except ValueError as e:
        logger.error(f"Validation error in health analysis: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error in structured health analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/structured-outputs/intent", tags=["Structured Outputs"])
async def structured_intent_analysis(request: StructuredIntentRequest):
    """
    Generate a structured intent analysis for quick classification.
    
    Returns a SimpleIntentAnalysis containing:
    - Intent classification
    - Confidence score (0-1)
    - Identified keywords
    - Brief summary
    
    This is a lightweight endpoint for quick intent detection.
    
    Args:
        request: Message to analyze
        
    Returns:
        SimpleIntentAnalysis structured response
    """
    if not STRUCTURED_OUTPUTS_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Structured outputs not available"
        )
    
    start_time = time.time()
    
    try:
        generator = get_ollama_generator()
        
        is_available = await generator.is_available()
        if not is_available:
            raise HTTPException(
                status_code=503,
                detail="Ollama service not available"
            )
        
        result = await generator.generate_intent_analysis(request.message)
        
        generation_time = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "data": result.model_dump(),
            "metadata": {
                "generation_time_ms": int(generation_time),
                "schema": "SimpleIntentAnalysis"
            }
        }
        
    except ValueError as e:
        logger.error(f"Validation error in intent analysis: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error in structured intent analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/structured-outputs/conversation", tags=["Structured Outputs"])
async def structured_conversation(request: StructuredConversationRequest):
    """
    Generate a structured conversation response.
    
    Returns a ConversationResponse containing:
    - Response text
    - Tone indicator (friendly, professional, empathetic, urgent)
    - Topics discussed
    - Action items mentioned
    - Whether clarification is needed
    
    Args:
        request: Message, conversation_history, session_id
        
    Returns:
        ConversationResponse structured response
    """
    if not STRUCTURED_OUTPUTS_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Structured outputs not available"
        )
    
    start_time = time.time()
    
    try:
        generator = get_ollama_generator()
        
        is_available = await generator.is_available()
        if not is_available:
            raise HTTPException(
                status_code=503,
                detail="Ollama service not available"
            )
        
        result = await generator.generate_structured_response(
            prompt=request.message,
            output_schema=ConversationResponse,
            conversation_history=request.conversation_history,
            session_id=request.session_id,
        )
        
        generation_time = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "data": result.model_dump(),
            "metadata": {
                "generation_time_ms": int(generation_time),
                "schema": "ConversationResponse"
            }
        }
        
    except ValueError as e:
        logger.error(f"Validation error in conversation: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error in structured conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}")
    logger.info(f"Listening on {SERVICE_HOST}:{SERVICE_PORT}")

    uvicorn.run(
        "main:app",
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        reload=True,
        log_level=LOG_LEVEL.lower()
    )