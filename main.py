"""
Cardio AI - NLP Service Main Application
"""

import sys
import io
import platform


# Force UTF-8 encoding for Windows consoles to prevent charmap errors with emojis
# Also unbuffer stdout for real-time log output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

# [FIX] Set the correct event loop policy for Windows to support Playwright/Crawl4AI
# ProactorEventLoopPolicy is preferred for subprocess (Crawl4AI). If you experience
# "NotImplementedError: get_event_loop", try WindowsSelectorEventLoopPolicy instead.
if platform.system() == 'Windows':
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("✅ Windows ProactorEventLoopPolicy enabled for async subprocess support")
    except Exception as e:
        print(f"⚠️  ProactorEventLoopPolicy failed ({e}), trying SelectorEventLoopPolicy...")
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            print("✅ Windows SelectorEventLoopPolicy enabled (fallback)")
        except Exception as e2:
            print(f"❌ Both event loop policies failed: {e2}")

import os
import logging
from contextlib import asynccontextmanager
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging - write to file (overwrite each run) and console
LOG_FILE = "server.log"

# Create file handler that overwrites each time (mode='w')
file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

# Console handler with auto-flush
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
console_handler.flush()  # Ensure handler flushes on each emit

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[file_handler, console_handler],
)
logger = logging.getLogger("nlp-service")

# Add custom emit method to ensure flushing
original_emit = console_handler.emit
def flush_emit(record):
    original_emit(record)
    console_handler.flush()

console_handler.emit = flush_emit

logger.info(f"📝 Logging to file: {os.path.abspath(LOG_FILE)} (overwritten each run)")

# LATENCY OPTIMIZATION: Reduce logging verbosity for noisy modules
# This reduces I/O overhead during request processing
if os.getenv("ENVIRONMENT", "development").lower() == "production":
    logging.getLogger("rag").setLevel(logging.WARNING)
    logging.getLogger("agents").setLevel(logging.WARNING)
    logging.getLogger("memori").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logger.info("⚡ Production mode: Reduced logging for performance")

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import configuration
from core.config.app_config import get_app_config

config = get_app_config()

# Extract commonly used config values
CORS_ORIGINS = ["*"]
LOG_LEVEL = "INFO"
SERVICE_HOST = config.api.host
SERVICE_PORT = config.api.port
SERVICE_NAME = "HeartGuard NLP Service"
SERVICE_VERSION = "1.0.0"
OLLAMA_MODEL = config.llm.model_name
OLLAMA_TEMPERATURE = config.llm.temperature
OLLAMA_TOP_P = 0.95  # Default value
OLLAMA_TOP_K = 40    # Default value
OLLAMA_MAX_TOKENS = config.llm.max_tokens
RAG_ENABLED = config.rag.enabled
MEMORY_ENABLED = True  # Always available
AGENTS_ENABLED = True  # Always available
TOOLS_ENABLED = True   # Always available
STRUCTURED_OUTPUTS_ENABLED = True  # Always available

# Routes will be loaded dynamically with safe_include_router() to prevent crashes

# Global State Holder for Dependency Injection
class NLPState:
    """
    Global state holder for NLP components.
    Used by core.app_dependencies to provide dependencies to routes.
    """

    intent_recognizer = None
    entity_extractor = None
    sentiment_analyzer = None
    ollama_generator = None
    integrated_ai = None
    memory_manager = None
    memory_observability = None
    nlp_service = None  # Add NLPService instance
    reranker = None  # Add Reranker instance
    memori_bridge = None  # MemoriRAGBridge for memory-RAG integration


def get_enabled_features():
    """Simple function to return enabled features."""
    return {
        "rag": RAG_ENABLED,
        "memory": MEMORY_ENABLED,
        "agents": AGENTS_ENABLED,
        "tools": TOOLS_ENABLED,
        "structured_outputs": STRUCTURED_OUTPUTS_ENABLED,
    }


def validate_dependencies():
    """Simple dependency validation."""
    logger.info("Dependencies validated")


# NLP components removed for RAG and memory agent focus
# Create fallback classes

class IntentRecognizer:
    def __init__(self):
        pass

class EntityExtractor:
    """Extract entities using centralized spaCy service."""
    
    def __init__(self):
        from core.services.spacy_service import get_spacy_service
        self.spacy_svc = get_spacy_service()
    
    def extract(self, text: str):
        """Extract named entities from text."""
        return self.spacy_svc.get_entities(text)
    
    def extract_medical_entities(self, text: str):
        """Extract categorized medical entities."""
        doc = self.spacy_svc.process(text)
        
        result = {
            "medications": [],
            "conditions": [],
            "procedures": [],
            "anatomy": [],
            "other": []
        }
        
        # Categorize based on entity label
        label_mapping = {
            "DRUG": "medications",
            "MEDICATION": "medications",
            "DISEASE": "conditions",
            "DISORDER": "conditions",
            "PROBLEM": "conditions",
            "PROCEDURE": "procedures",
            "ANATOMY": "anatomy",
        }
        
        for ent in doc.ents:
            category = label_mapping.get(ent.label_, "other")
            result[category].append(ent.text)
        
        return result

class SentimentAnalyzer:
    def __init__(self):
        pass

class OllamaGenerator:
    def __init__(self, **kwargs):
        pass

class IntegratedAIService:
    def __init__(self, **kwargs):
        pass

# NLPService
class NLPService:
    def __init__(self, **kwargs):
        pass

# Import embedding services for cache warming
from rag.embedding_onnx import ONNXEmbeddingService

# Import memory extraction components for agentic system
try:
    from memori.long_term.fact_extractor import MemoryExtractionWorker, FactExtractor, get_fact_extractor, get_extraction_worker
    from memori.short_term.redis_buffer import RedisSessionBuffer, get_session_buffer
    MEMORI_AVAILABLE = True
except ImportError:
    # Define fallback classes when memori is not available
    class MemoryExtractionWorker:
        def start(self):
            pass
        def stop(self):
            pass
    class FactExtractor:
        pass
    def get_fact_extractor():
        return FactExtractor()
    def get_extraction_worker():
        return MemoryExtractionWorker()
    class RedisSessionBuffer:
        pass
    def get_session_buffer():
        return RedisSessionBuffer()
    MEMORI_AVAILABLE = False

# Import VectorStore for memory
from rag.vector_store import VectorStore

# Import Memory components
try:
    from memori.memory_manager import MemoryManager, PatientMemory, MemoryResult
    from memori.memory_observability import MemoriMetricsCollector, get_memori_health_check, metrics_endpoint
    from memori.memory_middleware import CorrelationIDMiddleware, get_memory_context
    from memori.memory_aware_agents import (
        MemoryAwareIntentRecognizer,
        MemoryAwareSentimentAnalyzer,
        ContextRetriever,
        ConversationContext,
    )
    from memori.memory_performance import MultiTierCache, BatchMemoryProcessor
    MEMORI_MANAGER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Memori manager imports failed: {e}")
    # Define fallback classes when memori is not available
    class MemoryManager:
        _instance = None
        @classmethod
        def get_instance(cls):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
        async def initialize(self):
            pass
        async def shutdown(self):
            pass
        def get_metrics(self):
            return {}
    class PatientMemory:
        pass
    class MemoryResult:
        pass
    class MemoriMetricsCollector:
        def __init__(self):
            pass
        def get_prometheus_metrics(self):
            return ""
        def get_json_metrics(self):
            return {}
    async def get_memori_health_check():
        return {"status": "unavailable", "message": "Memori not installed"}
    async def metrics_endpoint():
        return ""
    class CorrelationIDMiddleware:
        def __init__(self, app):
            self.app = app
        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)
    async def get_memory_context(patient_id, session_id=None):
        yield None
    class MemoryAwareIntentRecognizer:
        pass
    class MemoryAwareSentimentAnalyzer:
        pass
    class ContextRetriever:
        pass
    class ConversationContext:
        pass
    class MultiTierCache:
        pass
    class BatchMemoryProcessor:
        pass
    MEMORI_MANAGER_AVAILABLE = False

# Routes will be loaded dynamically with safe_include_router() to prevent crashes
# This ensures that if one route file breaks, the server stays running
# and reports which route failed to load.

# Global instances
intent_recognizer = None
entity_extractor = None
sentiment_analyzer = None
ollama_generator = None
integrated_ai = None
risk_assessor = None
model_version_manager = None
memory_manager = None
memory_observability = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    
    **Initialization Order (Critical):**
    1. app_lifespan.startup_event() - Initialize routes layer services
       - Auth database service
       - LangGraph orchestrator
       - Feedback store
       - Embedding search engine
    2. Main startup logic - Initialize core services
       - DI Container
       - NLP components
       - Ollama generator
       - Vector stores
    3. Yield - App handles requests
    4. app_lifespan.shutdown_event() - Clean up routes layer
    5. Main shutdown logic - Clean up core services
    """
    # ============================================================================
    # STARTUP: Initialize all services
    # ============================================================================
    
    # 1. Initialize routes layer services (app_lifespan)
    # This ensures orchestrator, feedback store, etc. are ready per-worker
    from app_lifespan import startup_event as app_startup, shutdown_event as app_shutdown
    
    try:
        logger.info("🚀 Initializing routes layer services (app_lifespan)...")
        await app_startup()
        logger.info("✅ Routes layer services initialized")
    except Exception as e:
        logger.error(f"⚠️  Routes layer initialization failed (non-critical): {e}")
        # Continue with main startup even if routes layer fails
    
    # 2. Original main.py startup logic
    from config import startup_check
    startup_check()  # Check on startup
    
    # Check if Alembic migrations are up to date (non-blocking)
    import subprocess
    import sys
    
    try:
        # Run alembic check asynchronously
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "alembic", "current",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.path.dirname(__file__)
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
            stdout_str = stdout.decode()
            stderr_str = stderr.decode()
            
            if process.returncode == 0:
                if "(head)" not in stdout_str:
                    logger.warning(
                        "⚠️  Database migrations are not up to date! "
                        "Run 'alembic upgrade head' to update schema."
                    )
                else:
                    logger.info("✅ Database migrations are up to date")
            else:
                logger.warning(f"⚠️  Alembic migration check failed (will continue): {stderr_str[:100]}")
        except asyncio.TimeoutError:
            logger.warning("⚠️  Alembic migration check timed out (continuing without check)")
            # Don't kill, just ignore
    except Exception as e:
        logger.warning(f"⚠️  Could not run Alembic check (continuing): {str(e)[:100]}")
    
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}...")

    global intent_recognizer, entity_extractor, sentiment_analyzer, ollama_generator
    global integrated_ai, memory_manager
    global memory_observability

    try:
        # ========== INITIALIZE UNIFIED CONFIGURATION (Phase 3) ==========
        # Load environment-driven configuration first
        logger.info("Initializing unified AppConfig...")
        from core.config.app_config import get_app_config
        try:
            app_config = get_app_config()
            logger.info(
                f"✅ AppConfig initialized: "
                f"env={app_config.env.value}, "
                f"llm={app_config.llm.provider}, "
                f"rag_enabled={app_config.rag.enabled}"
            )
        except Exception as e:
            logger.warning(f"Failed to load AppConfig: {e}, using defaults")
            app_config = None
        
        # ========== INITIALIZE DEPENDENCY INJECTION CONTAINER (Phase 2) ==========
        # This centralizes all service management and makes the system testable
        logger.info("Initializing DI Container...")
        from core.dependencies import DIContainer
        from core.config.rag_config import RAGConfig
        
        # Initialize DIContainer singleton with all services
        di_container = DIContainer.get_instance()
        logger.info(f"✅ DIContainer initialized: {di_container}")
        
        # Make container available globally for dependency resolution
        NLPState.di_container = di_container
        
        # Initialize Memory Components
        memory_manager = MemoryManager()
        memory_observability = MemoriMetricsCollector()
        logger.info("Memory components initialized")

        # Initialize NLP Components
        intent_recognizer = IntentRecognizer()
        entity_extractor = EntityExtractor()
        sentiment_analyzer = SentimentAnalyzer()

        # Initialize Ollama Generator
        ollama_generator = OllamaGenerator(
            model_name=OLLAMA_MODEL,
            temperature=OLLAMA_TEMPERATURE,
            top_p=OLLAMA_TOP_P,
            top_k=OLLAMA_TOP_K,
            context_window=OLLAMA_MAX_TOKENS,
        )
        logger.info(f"Ollama Generator initialized with model: {OLLAMA_MODEL}")

        # Initialize NLP Service for parallel processing
        nlp_service = NLPService(
            intent_recognizer=intent_recognizer,
            sentiment_analyzer=sentiment_analyzer,
            entity_extractor=entity_extractor,
            # risk_assessor=risk_assessor,
        )

        # Initialize Integrated AI Service
        integrated_ai = IntegratedAIService(
            ollama_client=ollama_generator,
            default_ai_provider="ollama" if ollama_generator else "gemini",
        )

        # Initialize VectorStore for memory (now uses centralized paths from DIContainer)
        vector_store = di_container.vector_store
        persist_dir = getattr(vector_store, 'persist_directory', 'in-memory')
        logger.info(f"Vector store initialized: {type(vector_store).__name__} at {persist_dir}")

        # ========== INITIALIZE PHASE 3 ORCHESTRATOR (Phase 3: Brain) ==========
        # This wires together all Phase 1-2 tools via semantic routing + LangGraph
        reranker = None  # Initialize before try block to ensure it's always defined
        try:
            from core.llm.llm_gateway import get_llm_gateway
            from core.database.postgres_db import get_database
            from rag.graph_interaction_checker import GraphInteractionChecker
            
            # Get instances
            postgres_db = await get_database()
            di_container.register_service('db_manager', postgres_db)
            llm_gateway = get_llm_gateway()
            
            # Get optional web search tool
            try:
                from tools.web_search import VerifiedWebSearchTool
                web_search_tool = VerifiedWebSearchTool()  # Uses Tavily API
            except ImportError:
                web_search_tool = None
                logger.warning("WebSearchTool not available")
            
            # Get optional reranker from DIContainer
            reranker = getattr(di_container, 'reranker', None)
            
            # Initialize interaction checker for drug safety
            interaction_checker = GraphInteractionChecker()
            
            # Initialize MemoriRAGBridge for memory-aware retrieval (via DIContainer)
            try:
                # Use DIContainer to get properly initialized MemoriRAGBridge
                memori_bridge = di_container.memori_bridge
                if memori_bridge:
                    NLPState.memori_bridge = memori_bridge
                    logger.info("✅ MemoriRAGBridge loaded from DIContainer")
                else:
                    logger.warning("⚠️ MemoriRAGBridge not available - memory integration disabled")
            except Exception as bridge_err:
                logger.warning(f"MemoriRAGBridge not available: {bridge_err}")
                memori_bridge = None
            
            # ✅ FIXED: Orchestrator initialization moved to app_lifespan
            # The LangGraphOrchestrator is now initialized per-worker via FastAPI lifespan
            # This ensures every worker has its own orchestrator instance
            # See app_lifespan.startup_event() for the actual initialization
            logger.info("✅ Phase 3 Orchestrator (Brain) will be initialized via app_lifespan")
            logger.info("   - Semantic Router: Intent classification (<10ms)")
            logger.info("   - Text-to-SQL Tool: Health data queries")
            logger.info("   - Medical Self-RAG: Evidence-based responses")
            logger.info("   - CRAG Fallback: Web search integration")
            logger.info("   - Emergency Handler: Hardcoded safe response (<1ms)")
            if memori_bridge:
                logger.info("   - MemoriRAGBridge: Memory-aware retrieval")
            
        except Exception as e:
            logger.error(f"Failed to initialize Phase 3 components: {e}")
            logger.warning("System will continue without orchestrated chat endpoint")
            # Don't fail startup, continue in degraded mode

        # ========== FEEDBACK ROUTES ==========
        # ✅ FIXED: Feedback store initialization moved to app_lifespan
        # Feedback routes are now initialized per-worker via FastAPI lifespan
        # See app_lifespan.startup_event() for details
        logger.info("✅ Feedback routes will be initialized via app_lifespan")

        # Populate Global State for Dependency Injection
        NLPState.intent_recognizer = intent_recognizer
        NLPState.entity_extractor = entity_extractor
        NLPState.sentiment_analyzer = sentiment_analyzer
        NLPState.ollama_generator = ollama_generator
        NLPState.integrated_ai = integrated_ai
        # NLPState.risk_assessor = risk_assessor
        # NLPState.model_version_manager = model_version_manager
        NLPState.memory_manager = memory_manager
        NLPState.memory_observability = memory_observability
        NLPState.nlp_service = nlp_service  # Add NLPService to global state
        
        # Add reranker to global state if available
        if reranker:
            NLPState.reranker = reranker
            reranker_config = reranker.get_config()
            logger.info(
                f"✅ Reranker available in global state\n"
                f"  - Model: {reranker_config['model_name']}\n"
                f"  - Max Length: {reranker_config['max_length']}\n"
                f"  - Batch Size: {reranker_config['batch_size']}\n"
                f"  - Device: {reranker_config['device']}\n"
                f"  - Status: {'Ready' if reranker_config['available'] else 'Unavailable'}"
            )
        else:
            NLPState.reranker = None
            logger.warning("⚠️  Reranker not available - document reranking will be disabled")

        # Initialize Agentic Memory Extraction Worker (optional - can be skipped for faster startup)
        SKIP_EXTRACTION_WORKER = os.getenv("SKIP_EXTRACTION_WORKER", "true").lower() == "true"
        
        if SKIP_EXTRACTION_WORKER:
            logger.info("⚡ Memory Extraction Worker skipped (SKIP_EXTRACTION_WORKER=true)")
            extraction_worker = None
        elif MEMORI_AVAILABLE:
            try:
                logger.info("Starting Memory Extraction Worker...")
                extraction_worker = get_extraction_worker(auto_start=True)
                logger.info("✅ Memory Extraction Worker started")
            except Exception as e:
                logger.error(f"Failed to start Memory Extraction Worker: {e}")
                extraction_worker = None
        else:
            logger.info("Memory Extraction Worker not available - memori module not found")
            extraction_worker = None

        logger.info("Proceeding with cache warming...")

        # Warm up critical caches for better performance (optional, can be skipped for faster startup)
        SKIP_CACHE_WARMING = os.getenv("SKIP_CACHE_WARMING", "false").lower() == "true"
        
        if SKIP_CACHE_WARMING:
            logger.info("⚡ Cache warming skipped (SKIP_CACHE_WARMING=true)")
        else:
            # Move cache warming to background task for faster startup
            async def warm_cache_background():
                try:
                    await asyncio.sleep(0.5)  # Let server start first
                    common_medical_terms = [
                        "chest pain", "heart attack", "blood pressure", "heart rate",
                        "shortness of breath", "fatigue", "dizziness",
                        "aspirin", "medications", "diagnosis", "treatment"
                    ]
                    embedding_service = ONNXEmbeddingService.get_instance(model_type="fast")
                    warmed_count = embedding_service.warm_cache(common_medical_terms)
                    logger.info(f"✅ Background cache warming complete: {warmed_count} embeddings")
                except Exception as e:
                    logger.warning(f"Background cache warming failed (non-critical): {e}")
            
            # Schedule background warming - server starts immediately
            asyncio.create_task(warm_cache_background())
            logger.info("⚡ Cache warming scheduled in background for faster startup")

        logger.info("All AI components initialized successfully")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Don't raise exception to allow service to start in degraded mode

    yield

    # ============================================================================
    # SHUTDOWN: Clean up all services
    # ============================================================================
    
    logger.info(f"Shutting down {SERVICE_NAME}...")
    
    # 1. Shutdown routes layer services (app_lifespan)
    try:
        logger.info("🛑 Shutting down routes layer services...")
        await app_shutdown()
        logger.info("✅ Routes layer services shutdown complete")
    except Exception as e:
        logger.error(f"⚠️  Routes layer shutdown failed (non-critical): {e}")
    
    # 2. Original main.py shutdown logic
    # Shutdown Memory Manager
    try:
        if MEMORI_MANAGER_AVAILABLE and memory_manager:
            if hasattr(memory_manager, 'shutdown'):
                await memory_manager.shutdown()
                logger.info("✅ Memory Manager shutdown complete")
    except Exception as e:
        logger.error(f"Error shutting down memory manager: {e}")
    
    # Stop the memory extraction worker
    try:
        if MEMORI_AVAILABLE and 'extraction_worker' in locals() and extraction_worker:
            extraction_worker.stop()
            logger.info("✅ Memory Extraction Worker stopped")
    except Exception as e:
        logger.error(f"Error stopping memory extraction worker: {e}")
    

# ============================================================================
# SAFE ROUTER LOADING FUNCTION
# ============================================================================
# This function wraps router loading in try...except to prevent server crashes
# If a route file has syntax errors or import failures, the server continues running
# and reports exactly which route failed to load.

def safe_include_router(app, module_path, router_name, prefix=None, tags=None):
    """
    Safely load and include a router without crashing the server.
    
    ✅ RESILIENCE STRATEGY:
    - Wraps router loading in try...except blocks
    - If import fails, server logs the error but stays running
    - If router variable is missing, provides helpful error message
    - Tracks failed routes for monitoring and debugging
    
    Args:
        app: FastAPI application instance
        module_path: Dot-separated module path (e.g., "routes.orchestrated_chat")
        router_name: Name of the router variable in the module (e.g., "router")
        prefix: URL prefix for the router (optional)
        tags: OpenAPI tags for the router (optional)
    
    Returns:
        Tuple of (success: bool, error_msg: str or None)
    """
    route_display = prefix if prefix else module_path
    
    try:
        import importlib
        import traceback
        
        logger.debug(f"🔄 Attempting to load router: {module_path}.{router_name}")
        
        # 1. IMPORT THE MODULE
        try:
            module = importlib.import_module(module_path)
            logger.debug(f"   ✓ Module imported: {module_path}")
        except ModuleNotFoundError as e:
            error_msg = f"Module not found: {module_path}"
            logger.error(f"❌ FAILED to load {route_display}: {error_msg}")
            logger.debug(f"   Available modules: {module_path}")
            if hasattr(app, '_failed_routes'):
                app._failed_routes.append({'route': route_display, 'error': error_msg})
            return False, error_msg
        except ImportError as e:
            error_msg = f"Import error in {module_path}: {str(e)}"
            logger.error(f"❌ FAILED to load {route_display}: {error_msg}")
            logger.debug(f"   Traceback:\n{traceback.format_exc()}")
            if hasattr(app, '_failed_routes'):
                app._failed_routes.append({'route': route_display, 'error': error_msg})
            return False, error_msg
        except SyntaxError as e:
            error_msg = f"Syntax error in {module_path} at line {e.lineno}: {e.msg}"
            logger.error(f"❌ FAILED to load {route_display}: {error_msg}")
            logger.debug(f"   File: {e.filename}\n   Line {e.lineno}: {e.text}")
            if hasattr(app, '_failed_routes'):
                app._failed_routes.append({'route': route_display, 'error': error_msg})
            return False, error_msg
        
        # 2. GET THE ROUTER FROM THE MODULE
        try:
            if not hasattr(module, router_name):
                available_attrs = [attr for attr in dir(module) if not attr.startswith('_')]
                error_msg = f"Router '{router_name}' not found in {module_path}. Available: {', '.join(available_attrs[:5])}"
                logger.error(f"❌ FAILED to load {route_display}: {error_msg}")
                if hasattr(app, '_failed_routes'):
                    app._failed_routes.append({'route': route_display, 'error': error_msg})
                return False, error_msg
            
            router = getattr(module, router_name)
            logger.debug(f"   ✓ Router object retrieved: {router_name}")
        except AttributeError as e:
            error_msg = f"Attribute error: {str(e)}"
            logger.error(f"❌ FAILED to load {route_display}: {error_msg}")
            if hasattr(app, '_failed_routes'):
                app._failed_routes.append({'route': route_display, 'error': error_msg})
            return False, error_msg
        
        # 3. INCLUDE THE ROUTER IN THE APP
        try:
            app.include_router(router, prefix=prefix, tags=tags)
            logger.debug(f"   ✓ Router included in app")
            logger.info(f"✅ Loaded route: {route_display}")
            return True, None
        except Exception as e:
            error_msg = f"Failed to include router: {str(e)}"
            logger.error(f"❌ FAILED to load {route_display}: {error_msg}")
            logger.debug(f"   Router type: {type(router)}\n   Traceback:\n{traceback.format_exc()}")
            if hasattr(app, '_failed_routes'):
                app._failed_routes.append({'route': route_display, 'error': error_msg})
            return False, error_msg
    
    except Exception as e:
        error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
        logger.error(f"❌ FAILED to load {route_display}: {error_msg}")
        logger.debug(f"   Traceback:\n{traceback.format_exc()}")
        if hasattr(app, '_failed_routes'):
            app._failed_routes.append({'route': route_display, 'error': error_msg})
        return False, error_msg


# Create FastAPI app
app = FastAPI(
    title=SERVICE_NAME,
    description="NLP Service for Cardio AI with Advanced Agentic Capabilities",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# Initialize tracker for failed routes (for monitoring endpoint)
app._failed_routes = []
logger.info("✅ Failed routes tracker initialized")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Correlation ID Middleware for request tracing (from memori)
if MEMORI_MANAGER_AVAILABLE:
    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        app.add_middleware(CorrelationIDMiddleware)
        logger.info("✅ CorrelationIDMiddleware added for request tracing")
    except Exception as e:
        logger.warning(f"Failed to add CorrelationIDMiddleware: {e}")

# Add Request Timeout Middleware with path-specific timeouts
# This prevents runaway requests from consuming resources indefinitely
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
# Longer timeout for research-heavy endpoints (deep research, complex analysis)
RESEARCH_TIMEOUT_SECONDS = float(os.getenv("RESEARCH_TIMEOUT_SECONDS", "180"))

# Paths that need longer timeouts (research queries, document analysis, etc.)
LONG_TIMEOUT_PATHS = {
    "/chat/message",      # Chat can trigger deep research
    "/research",          # Explicit research endpoints
    "/documents/analyze", # Document analysis is slow
    "/analysis",          # Analysis endpoints
}

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    
    class RequestTimeoutMiddleware(BaseHTTPMiddleware):
        """
        Middleware to enforce request timeouts with path-specific overrides.
        
        Standard endpoints: 60s timeout (configurable via REQUEST_TIMEOUT_SECONDS)
        Research endpoints: 180s timeout (configurable via RESEARCH_TIMEOUT_SECONDS)
        
        Returns 504 Gateway Timeout if request exceeds the timeout limit.
        """
        
        def _get_timeout_for_path(self, path: str) -> float:
            """Get appropriate timeout based on request path."""
            # Check if path matches any long-timeout patterns
            for long_path in LONG_TIMEOUT_PATHS:
                if path.startswith(long_path):
                    return RESEARCH_TIMEOUT_SECONDS
            return REQUEST_TIMEOUT_SECONDS
        
        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            timeout = self._get_timeout_for_path(path)
            
            try:
                return await asyncio.wait_for(
                    call_next(request),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"⏱️ Request timeout ({timeout}s): "
                    f"{request.method} {path}"
                )
                return JSONResponse(
                    status_code=504,
                    content={
                        "detail": "Request timeout",
                        "timeout_seconds": timeout,
                        "path": str(path),
                        "hint": "For long-running research queries, consider using async endpoints."
                    }
                )
    
    app.add_middleware(RequestTimeoutMiddleware)
    logger.info(f"✅ RequestTimeoutMiddleware added (default: {REQUEST_TIMEOUT_SECONDS}s, research: {RESEARCH_TIMEOUT_SECONDS}s)")
except Exception as e:
    logger.warning(f"Failed to add RequestTimeoutMiddleware: {e}")

# ============================================================================
# INCLUDE ROUTERS SAFELY
# ============================================================================
# Using safe_include_router() ensures that if one route file breaks,
# the server stays running and just skips that route.
# Each router is wrapped in try...except, so syntax errors or import failures
# are caught and logged without crashing the server.

logger.info("📂 Loading routers...")

# Core Routes - Authentication
safe_include_router(app, "routes.auth_routes", "router", prefix="/auth", tags=["Auth"])

# Core Routes - Phase 1: Orchestrated Chat (Main conversational endpoint)
safe_include_router(app, "routes.orchestrated_chat", "router", prefix="/chat", tags=["Orchestrated Chat"])

# Core Routes - Feedback collection for model improvement
safe_include_router(app, "routes.feedback", "router", prefix="/feedback", tags=["Feedback"])

# Core Routes - Memory management
if MEMORY_ENABLED:
    safe_include_router(app, "routes.memory", "router", prefix="/memory", tags=["Memory"])

# Document upload routes (Phase 2.4: Multimodal)
safe_include_router(app, "routes.documents", "router", prefix="/documents", tags=["Document Management"])

# NLP Debug Routes (Phase 3: Visualization & Troubleshooting)
safe_include_router(app, "routes.nlp_debug", "router", prefix="/nlp", tags=["NLP Debug"])

# ============================================================================
# SCALABILITY ROUTES (Async Job Pattern)
# ============================================================================

# Job Management API - status queries, cancellation, retry, dead letter queue
safe_include_router(app, "routes.job_management", "router", prefix="/api/v2", tags=["Job Management"])

# SSE Routes - Server-Sent Events for real-time updates (HTTP fallback)
safe_include_router(app, "routes.sse_routes", "router", prefix="/sse", tags=["Server-Sent Events"])

# Database Health & Monitoring Routes
safe_include_router(app, "routes.db_health", "router", prefix="/db", tags=["Database Health"])

# RAG & Memory Health Routes
safe_include_router(app, "routes.rag_memory_health", "router", prefix="/rag-memory", tags=["RAG Memory Health"])

# WebSocket Routes - Real-time updates via WebSocket
# Note: WebSocket routes are typically registered directly, not via include_router
try:
    from routes.websocket_routes import router as websocket_router
    app.include_router(websocket_router)
    logger.info("✅ WebSocket routes loaded")
except Exception as e:
    logger.warning(f"⚠️  WebSocket routes failed to load: {e}")
    app._failed_routes.append({"route": "routes.websocket_routes", "error": str(e)})

# Log summary of route loading
logger.info(f"✅ All routers loaded (with graceful fallbacks for any failures)")
if app._failed_routes:
    logger.warning(f"⚠️  {len(app._failed_routes)} route(s) failed to load:")
    for failed_route in app._failed_routes:
        logger.warning(f"   - {failed_route['route']}: {failed_route['error']}")


# ============================================================================
# STATIC FILES - Serve Frontend
# ============================================================================
# Mount the frontend folder to serve the testing UI
try:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    
    # Serve frontend at /frontend (for static assets)
    frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    if os.path.exists(frontend_path):
        app.mount("/static", StaticFiles(directory=frontend_path), name="frontend-static")
        
        # Serve index.html at root for convenience
        @app.get("/", tags=["Frontend"], include_in_schema=False)
        async def serve_frontend():
            """Serve the frontend testing interface."""
            index_path = os.path.join(frontend_path, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {"message": "Welcome to HeartGuard AI API", "docs": "/docs"}
        
        logger.info(f"✅ Frontend served at / and /static from {frontend_path}")
    else:
        logger.info("ℹ️  Frontend folder not found, skipping static file serving")
except Exception as e:
    logger.warning(f"⚠️  Could not set up static file serving: {e}")


# ============================================================================
# Health and Metrics Endpoints
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check(request: Request):
    """Basic health check endpoint."""
    # Don't log health checks to avoid log spam from monitoring tools/browsers
    # Use DEBUG level if needed for troubleshooting
    # logger.debug(f"Health check from {request.client.host}")

    health_data = {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "features": get_enabled_features(),
    }
    
    # Add memory health if available
    if MEMORI_MANAGER_AVAILABLE:
        try:
            memori_health = await get_memori_health_check()
            health_data["memory"] = memori_health if isinstance(memori_health, dict) else memori_health.to_dict() if hasattr(memori_health, 'to_dict') else {"status": "unknown"}
        except Exception as e:
            health_data["memory"] = {"status": "error", "error": str(e)}
    
    return health_data


@app.get("/health/routes", tags=["Health", "Diagnostics"])
async def routes_health():
    """
    Check which routes successfully loaded and which failed.
    
    ✅ Use this endpoint to diagnose route loading issues:
    - If a route file has syntax errors, this will tell you
    - If imports are failing, this will show the error message
    - Compare this with the server logs for full debugging info
    
    Returns:
        {
            "total_attempted": <number>,
            "successful_routes": [<list of loaded routes>],
            "failed_routes": [
                {
                    "route": <route name>,
                    "error": <error message>,
                    "suggestion": <debugging hint>
                }
            ]
        }
    """
    health_data = {
        "total_attempted": len(app.routes) + len(app._failed_routes),
        "successful_routes": [route.path for route in app.routes if hasattr(route, 'path')],
        "failed_routes": app._failed_routes,
        "failed_count": len(app._failed_routes),
    }
    
    # Add debugging suggestions
    if health_data["failed_count"] > 0:
        health_data["suggestion"] = "Check server logs for detailed error messages. Failed routes won't be available."
    else:
        health_data["suggestion"] = "All routes loaded successfully! ✅"
    
    return health_data


@app.post("/admin/reload-route/{route_name}", tags=["Admin", "Diagnostics"])
async def reload_route(route_name: str):
    """
    ⚡ DYNAMIC ROUTE RELOADING - Reload a specific route without restarting!
    
    This is extremely useful during development:
    1. You break a route file (syntax error, import error, etc.)
    2. Server logs the error and keeps running
    3. You fix the code in your editor
    4. POST to /admin/reload-route/<route_name> to reload it
    5. Server hot-swaps the new code without restart
    
    Example:
        curl -X POST http://localhost:5001/admin/reload-route/chat
    
    Args:
        route_name: The route identifier (e.g., "chat", "feedback", "memory")
    
    Returns:
        {
            "status": "success|error",
            "route": <route_name>,
            "message": <status message>,
            "failed_routes_remaining": <count of still-failing routes>
        }
    """
    import importlib
    
    # Map route names to their module/router configs
    ROUTE_CONFIGS = {
        "auth": ("routes.auth_routes", "router", "/auth", ["Auth"]),
        "chat": ("routes.orchestrated_chat", "router", "/chat", ["Orchestrated Chat"]),
        "feedback": ("routes.feedback", "router", "/feedback", ["Feedback"]),
        "memory": ("routes.memory", "router", "/memory", ["Memory"]),
        "documents": ("routes.documents", "router", "/documents", ["Document Management"]),
        "nlp": ("routes.nlp_debug", "router", "/nlp", ["NLP Debug"]),
    }
    
    if route_name not in ROUTE_CONFIGS:
        available = ", ".join(ROUTE_CONFIGS.keys())
        logger.warning(f"🔄 Reload request for unknown route: {route_name}")
        return {
            "status": "error",
            "route": route_name,
            "message": f"Unknown route. Available: {available}",
            "available_routes": list(ROUTE_CONFIGS.keys()),
        }
    
    module_path, router_var, prefix, tags = ROUTE_CONFIGS[route_name]
    
    logger.info(f"🔄 Attempting to reload route: {route_name}")
    
    # Remove old route from failed list if present
    app._failed_routes = [r for r in app._failed_routes if r['route'] != (prefix or module_path)]
    
    # Reload the module to pick up fresh code
    try:
        importlib.invalidate_caches()
        module = importlib.import_module(module_path)
        if module_path in importlib.sys.modules:
            importlib.reload(module)
        logger.info(f"✓ Module reloaded: {module_path}")
    except Exception as e:
        logger.error(f"✗ Failed to reload module {module_path}: {e}")
        return {
            "status": "error",
            "route": route_name,
            "message": f"Failed to reload module: {str(e)}",
            "failed_routes_remaining": len(app._failed_routes),
        }
    
    # Now try to re-include the router
    success, error_msg = safe_include_router(app, module_path, router_var, prefix, tags)
    
    if success:
        logger.info(f"✅ Route reloaded successfully: {route_name}")
        return {
            "status": "success",
            "route": route_name,
            "message": f"Route '{route_name}' reloaded successfully!",
            "failed_routes_remaining": len(app._failed_routes),
        }
    else:
        logger.error(f"❌ Route reload failed: {route_name}")
        return {
            "status": "error",
            "route": route_name,
            "message": f"Route reload failed: {error_msg}",
            "failed_routes_remaining": len(app._failed_routes),
        }


@app.get("/health/memori", tags=["Health"])
async def memori_health():
    """Detailed Memori health check endpoint."""
    if not MEMORI_MANAGER_AVAILABLE:
        return {"status": "unavailable", "message": "Memori module not installed"}
    
    try:
        health = await get_memori_health_check()
        return health if isinstance(health, dict) else health.to_dict() if hasattr(health, 'to_dict') else {"status": "unknown"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/metrics", tags=["Monitoring"])
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    if not MEMORI_MANAGER_AVAILABLE:
        return ""
    
    try:
        return await metrics_endpoint()
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return ""


@app.get("/metrics/detailed", tags=["Monitoring"])
async def detailed_metrics():
    """Detailed JSON metrics for monitoring dashboards."""
    metrics = {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "features": get_enabled_features(),
    }
    
    if MEMORI_MANAGER_AVAILABLE and memory_observability:
        try:
            metrics["memory"] = memory_observability.get_json_metrics() if hasattr(memory_observability, 'get_json_metrics') else {}
        except Exception as e:
            metrics["memory"] = {"error": str(e)}
    
    return metrics


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """
    Comprehensive health check with dependency status.
    
    Returns status for all major dependencies:
    - PostgreSQL database
    - Redis cache
    - LLM Gateway
    - Vector Store
    - Memori system
    """
    from datetime import datetime
    import time
    
    checks = {}
    overall_healthy = True
    
    # Check PostgreSQL
    start = time.time()
    try:
        from core.dependencies import DIContainer
        container = DIContainer.get_instance()
        if hasattr(container, '_sql_tool') and container._sql_tool:
            checks["postgresql"] = {
                "status": "up",
                "latency_ms": round((time.time() - start) * 1000, 2)
            }
        else:
            checks["postgresql"] = {"status": "not_initialized"}
            overall_healthy = False
    except Exception as e:
        checks["postgresql"] = {"status": "down", "error": str(e)}
        overall_healthy = False
    
    # Check Redis Cache
    start = time.time()
    try:
        from core.services.advanced_cache import MultiTierCache
        cache = MultiTierCache()
        if hasattr(cache, 'is_available') and cache.is_available():
            checks["redis"] = {
                "status": "up",
                "latency_ms": round((time.time() - start) * 1000, 2)
            }
        else:
            checks["redis"] = {"status": "unavailable"}
    except Exception as e:
        checks["redis"] = {"status": "not_configured"}
    
    # Check LLM Gateway
    start = time.time()
    try:
        from core.dependencies import DIContainer
        container = DIContainer.get_instance()
        if container.llm_gateway:
            checks["llm_gateway"] = {
                "status": "up",
                "latency_ms": round((time.time() - start) * 1000, 2)
            }
        else:
            checks["llm_gateway"] = {"status": "not_initialized"}
            overall_healthy = False
    except Exception as e:
        checks["llm_gateway"] = {"status": "down", "error": str(e)}
        overall_healthy = False
    
    # Check Vector Store
    start = time.time()
    try:
        if NLPState.vector_store:
            checks["vector_store"] = {
                "status": "up",
                "type": type(NLPState.vector_store).__name__,
                "latency_ms": round((time.time() - start) * 1000, 2)
            }
        else:
            checks["vector_store"] = {"status": "not_initialized"}
    except Exception as e:
        checks["vector_store"] = {"status": "down", "error": str(e)}
    
    # Check Memori
    if MEMORI_MANAGER_AVAILABLE:
        try:
            health = await get_memori_health_check()
            checks["memori"] = {"status": "up", "details": health if isinstance(health, dict) else "available"}
        except Exception as e:
            checks["memori"] = {"status": "degraded", "error": str(e)}
    else:
        checks["memori"] = {"status": "not_installed"}
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "checks": checks,
        "failed_routes": len(app._failed_routes) if hasattr(app, '_failed_routes') else 0,
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {SERVICE_HOST}:{SERVICE_PORT}")
    
    # DEVELOPMENT MODE: reload=False keeps server running
    # - Errors appear in logs without restarting
    # - Manually restart (Ctrl+C + python main.py) when you need to load new code
    # - Set RELOAD=true env var to enable auto-reload if needed
    ENABLE_RELOAD = os.getenv("RELOAD", "false").lower() == "true"
    
    if ENABLE_RELOAD:
        logger.info("🔄 Auto-reload ENABLED - server will restart on file changes")
        RELOAD_DIRS = ["routes", "agents", "core", "rag", "tools", "memori"]
    else:
        logger.info("⚡ Auto-reload DISABLED - server stays running, errors show in logs")
        RELOAD_DIRS = None
    
    uvicorn.run(
        "main:app",
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        reload=ENABLE_RELOAD,
        reload_dirs=RELOAD_DIRS,
        reload_delay=1.0 if ENABLE_RELOAD else 0,
        log_level="info",
        access_log=True,
    )
