"""
Cardio AI - NLP Service Main Application
"""

import sys
import os
import logging
import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("nlp-service")

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import configuration
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
    RAG_ENABLED,
    MEMORY_ENABLED,
    AGENTS_ENABLED,
    REALTIME_ENABLED,
    MEDICAL_ROUTES_ENABLED,
    INTEGRATIONS_ENABLED,
    COMPLIANCE_ENABLED,
    CALENDAR_ENABLED,
    KNOWLEDGE_GRAPH_ENABLED,
    NOTIFICATIONS_ENABLED,
    TOOLS_ENABLED,
    VISION_ENABLED,
    NEW_AI_FRAMEWORKS_ENABLED,
    EVALUATION_ENABLED,
    STRUCTURED_OUTPUTS_ENABLED,
    GENERATION_ENABLED,
)

# Import core dependencies
from core.dependencies import (
    validate_dependencies,
    get_enabled_features,
    check_optional_dependency
)

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
    risk_assessor = None
    model_version_manager = None
    memory_manager = None
    memory_observability = None
    nlp_service = None  # Add NLPService instance

# Validate dependencies on startup
validate_dependencies()

# Import NLP components
from nlp.intent_recognizer import IntentRecognizer
from nlp.entity_extractor import EntityExtractor
from nlp.sentiment_analyzer import SentimentAnalyzer
from nlp.ollama_generator import OllamaGenerator, ExternalServiceError
from nlp.integrated_ai_service import IntegratedAIService
# Import NLPService
from core.services.nlp_service import NLPService

# Import Medical AI components
from medical_ai.risk_assessor import RiskAssessor
from medical_ai.model_versioning import ModelVersionManager

# Import Routes
# PHASE 1: Core Routes
from routes.health import router as health_router
from medical_ai.smart_watch.router import router as smartwatch_router
from medical_ai.smart_watch.router import init_smartwatch_module, shutdown_smartwatch_module
from routes.generation import router as generation_router, chat_router
from routes.structured_outputs import router as structured_outputs_router

# PHASE 2: RAG & Memory Routes
if RAG_ENABLED:
    from routes.document_routes import router as document_router
    print("[STARTUP] Document routes loaded successfully")
else:
    document_router = None
    print("[STARTUP] Document routes DISABLED via config")

if MEMORY_ENABLED:
    from routes.memory import router as memory_router
    print("[STARTUP] Memory routes loaded successfully")
else:
    memory_router = None
    print("[STARTUP] Memory routes DISABLED via config")

# PHASE 3: Agent Routes
if AGENTS_ENABLED:
    from routes.agents import router as agents_router
    print("[STARTUP] Agent routes loaded successfully")
else:
    agents_router = None
    print("[STARTUP] Agent routes DISABLED via config")

# PHASE 10: Realtime Routes
if REALTIME_ENABLED:
    from routes.realtime_routes import router as realtime_router
    print("[STARTUP] Realtime routes loaded successfully")
else:
    realtime_router = None
    print("[STARTUP] Realtime routes DISABLED via config")

# PHASE 11: Medical Routes
if MEDICAL_ROUTES_ENABLED:
    from routes.medical_routes import router as medical_router
    print("[STARTUP] Medical routes loaded successfully")
else:
    medical_router = None
    print("[STARTUP] Medical routes DISABLED via config")

# PHASE 12: Integration Routes
if INTEGRATIONS_ENABLED:
    from routes.integration_routes import router as integration_router
    print("[STARTUP] Integration routes loaded successfully")
else:
    integration_router = None
    print("[STARTUP] Integration routes DISABLED via config")

# PHASE 13: Compliance Routes
if COMPLIANCE_ENABLED:
    from routes.compliance_routes import router as compliance_router
    print("[STARTUP] Compliance routes loaded successfully")
else:
    compliance_router = None
    print("[STARTUP] Compliance routes DISABLED via config")

# PHASE 14: Calendar Routes
if CALENDAR_ENABLED:
    from routes.calendar_routes import router as calendar_router
    print("[STARTUP] Calendar routes loaded successfully")
else:
    calendar_router = None
    print("[STARTUP] Calendar routes DISABLED via config")

# PHASE 14: Knowledge Graph Routes
if KNOWLEDGE_GRAPH_ENABLED:
    from routes.knowledge_graph_routes import router as knowledge_graph_router
    print("[STARTUP] Knowledge Graph routes loaded successfully")
else:
    knowledge_graph_router = None
    print("[STARTUP] Knowledge Graph routes DISABLED via config")

# PHASE 14: Notifications Routes
if NOTIFICATIONS_ENABLED:
    from routes.notifications_routes import router as notifications_router
    print("[STARTUP] Notifications routes loaded successfully")
else:
    notifications_router = None
    print("[STARTUP] Notifications routes DISABLED via config")

# PHASE 15: Import Tools Routes
if TOOLS_ENABLED:
    from routes.tools_routes import router as tools_router
    print("[STARTUP] Tools routes loaded successfully")
else:
    tools_router = None
    print("[STARTUP] Tools routes DISABLED via config")

# PHASE 16: Import Vision Routes
if VISION_ENABLED:
    from routes.vision_routes import router as vision_router
    print("[STARTUP] Vision routes loaded successfully")
else:
    vision_router = None
    print("[STARTUP] Vision routes DISABLED via config")

# PHASE 18: Import New AI Frameworks (LangGraph, CrewAI, etc.)
if NEW_AI_FRAMEWORKS_ENABLED:
    from nlp.agents.langgraph_orchestrator import create_langgraph_orchestrator
    # Use unified LLM gateway instead of observable_llm_gateway
    from core.llm.llm_gateway import get_llm_gateway
    from nlp.agents.crew_simulation import create_healthcare_crew
    print("[STARTUP] New AI frameworks loaded successfully")
else:
    print("[STARTUP] New AI frameworks DISABLED via config")

# PHASE 19: Import Evaluation Routes
if EVALUATION_ENABLED:
    from routes.evaluation_routes import router as evaluation_router
    print("[STARTUP] Evaluation routes loaded successfully")
else:
    evaluation_router = None
    print("[STARTUP] Evaluation routes DISABLED via config")

# PHASE 4: Import structured output schemas
if STRUCTURED_OUTPUTS_ENABLED:
    from core.structured_outputs import (
        CardioHealthAnalysis,
        SimpleIntentAnalysis,
        ConversationResponse,
        # VitalSignsAnalysis,
        # MedicationInfo,
        # HealthIntent,
        # UrgencyLevel,
        # ResponseConfidence,
        # StructuredOutputParser,
        # StructuredGenerator,
        # HealthAnalysisGenerator,
        # pydantic_to_json_schema,
    )
else:
    print("[STARTUP] Structured outputs DISABLED via config")

from nlp.memory_manager import MemoryManager, PatientMemory, MemoryManagerException
# from nlp.memory_middleware import (
#     # MemoryMiddleware, 
#     # MemoryContext, 
#     # MemoryOperation,
# )
from nlp.memory_observability import (
    MemoriMetricsCollector,
    # MemoryObservability, 
    # MemoryMetricType, 
    # MemoryEvent
)

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
    """
    # Startup
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}...")
    
    global intent_recognizer, entity_extractor, sentiment_analyzer, ollama_generator
    global integrated_ai, risk_assessor, model_version_manager, memory_manager
    global memory_observability
    
    try:
        # Initialize Memory Components
        memory_manager = MemoryManager()
        memory_observability = MemoriMetricsCollector()
        logger.info("Memory components initialized")
        
        # Initialize NLP Components
        intent_recognizer = IntentRecognizer()
        entity_extractor = EntityExtractor()
        sentiment_analyzer = SentimentAnalyzer()
        
        # Initialize Ollama Generator with retry logic
        try:
            ollama_generator = OllamaGenerator(
                model_name=OLLAMA_MODEL,
                temperature=OLLAMA_TEMPERATURE,
                top_p=OLLAMA_TOP_P,
                top_k=OLLAMA_TOP_K,
                context_window=OLLAMA_MAX_TOKENS
            )
            logger.info(f"Ollama Generator initialized with model: {OLLAMA_MODEL}")
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama Generator: {e}")
            # Continue without Ollama - will fail gracefully on generation requests
        
        # Initialize Medical AI Components
        risk_assessor = RiskAssessor()
        model_version_manager = ModelVersionManager()
        
        # Initialize NLP Service for parallel processing
        nlp_service = NLPService(
            intent_recognizer=intent_recognizer,
            sentiment_analyzer=sentiment_analyzer,
            entity_extractor=entity_extractor,
            risk_assessor=risk_assessor
        )
        
        # Initialize Integrated AI Service
        integrated_ai = IntegratedAIService(
            ollama_client=ollama_generator,
            default_ai_provider="ollama" if ollama_generator else "gemini"
        )
        
        # Populate Global State for Dependency Injection
        NLPState.intent_recognizer = intent_recognizer
        NLPState.entity_extractor = entity_extractor
        NLPState.sentiment_analyzer = sentiment_analyzer
        NLPState.ollama_generator = ollama_generator
        NLPState.integrated_ai = integrated_ai
        NLPState.risk_assessor = risk_assessor
        NLPState.model_version_manager = model_version_manager
        NLPState.memory_manager = memory_manager
        NLPState.memory_observability = memory_observability
        NLPState.nlp_service = nlp_service  # Add NLPService to global state
        
        NLPState.memory_observability = memory_observability
        
        # Initialize Smart Watch Module
        await init_smartwatch_module()
        
        logger.info("All AI components initialized successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Don't raise exception to allow service to start in degraded mode
        
    yield
    
    # Shutdown
    logger.info(f"Shutting down {SERVICE_NAME}...")
    logger.info(f"Shutting down {SERVICE_NAME}...")
    # Cleanup resources
    await shutdown_smartwatch_module()

# Create FastAPI app
app = FastAPI(
    title=SERVICE_NAME,
    description="NLP Service for Cardio AI with Advanced Agentic Capabilities",
    version=SERVICE_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, tags=["Health"])
app.include_router(smartwatch_router)  # Already has prefix /api/smartwatch
app.include_router(generation_router, tags=["Generation"])
app.include_router(chat_router, tags=["Chat"])
app.include_router(structured_outputs_router, tags=["Structured Outputs"])

if document_router:
    app.include_router(document_router, tags=["Documents"])

if memory_router:
    app.include_router(memory_router, prefix="/api", tags=["Memory"])

if agents_router:
    app.include_router(agents_router, tags=["Agents"])

if realtime_router:
    app.include_router(realtime_router, prefix="/api", tags=["Realtime"])

if medical_router:
    app.include_router(medical_router, prefix="/api", tags=["Medical"])

if integration_router:
    app.include_router(integration_router, prefix="/api", tags=["Integration"])

if compliance_router:
    app.include_router(compliance_router, prefix="/api", tags=["Compliance"])

if calendar_router:
    app.include_router(calendar_router, prefix="/api", tags=["Calendar"])

if knowledge_graph_router:
    app.include_router(knowledge_graph_router, prefix="/api", tags=["Knowledge Graph"])

if notifications_router:
    app.include_router(notifications_router, prefix="/api", tags=["Notifications"])

if tools_router:
    app.include_router(tools_router, prefix="/api", tags=["Tools"])

if vision_router:
    app.include_router(vision_router, prefix="/api", tags=["Vision"])

if evaluation_router:
    app.include_router(evaluation_router, prefix="/api", tags=["Evaluation"])

# Initialize LLM Gateway (unified implementation)
llm_gateway = None
try:
    from core.llm.llm_gateway import get_llm_gateway
    llm_gateway = get_llm_gateway()
    logger.info("✅ LLM Gateway (unified) initialized")
except ImportError as e:
    logger.warning(f"LLM Gateway not available: {e}")

# Root endpoint
@app.get("/")
async def root():
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "running",
        "features": get_enabled_features()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        reload=True,
        log_level=LOG_LEVEL.lower()
    )