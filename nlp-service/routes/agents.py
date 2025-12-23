"""
FastAPI routes for ADK agent orchestration.
Bridges nlp-service API with ADK agents.

Phase 1: Foundation - Agent endpoints
Updated: Integrated IntentRecognizer for smart routing (Phase 5)
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
import os
from enum import Enum

logger = logging.getLogger(__name__)

# Import app dependencies for cleaner dependency injection
from core.app_dependencies import get_nlp_service

from nlp.agents.base import HealthAgent, AppointmentAgent, HealthAppointmentOrchestrator

# Import IntentRecognizer for smart query routing
from core.models import IntentEnum

# Import NLPService for parallel processing
from core.services.nlp_service import NLPService, NLPAnalysisResult

# Import semantic router for intent detection
from core.routing.semantic_router import get_semantic_router, AgentType, IntentCategory

# Import web search tool
from nlp.tools.web_search import search_verified_sources, WEB_SEARCH_TOOL_DEFINITION

# Feature flag for LangChain Gateway
# Feature flag for LangChain Gateway
USE_LANGCHAIN_GATEWAY = os.getenv("USE_LANGCHAIN_GATEWAY", "false").lower() == "true"

# Initialize LangChain Gateway if enabled
langchain_gateway = None

try:
    from core.llm.llm_gateway import get_llm_gateway

    langchain_gateway = get_llm_gateway()
    logger.info("✅ LLM Gateway (unified) initialized")
except ImportError as e:
    logger.warning(f"LLM Gateway not available: {e}")


# Create router
router = APIRouter(prefix="/api/nlp", tags=["agents"])

# ============================================================================
# EXTENDED INTENT ENUM FOR SEMANTIC ROUTING
# ============================================================================


class ExtendedIntentEnum(str, Enum):
    """Extended intent types for semantic routing (standalone enum)"""

    # Original intents from IntentEnum
    GREETING = "greeting"
    RISK_ASSESSMENT = "risk_assessment"
    NUTRITION_ADVICE = "nutrition_advice"
    EXERCISE_COACHING = "exercise_coaching"
    MEDICATION_REMINDER = "medication_reminder"
    SYMPTOM_CHECK = "symptom_check"
    HEALTH_GOAL = "health_goal"
    HEALTH_EDUCATION = "health_education"
    APPOINTMENT_BOOKING = "appointment_booking"
    EMERGENCY = "emergency"
    UNKNOWN = "unknown"
    # Extended intents for semantic routing
    SIMPLE_QUERY = "simple_query"
    COMPLEX_DIAGNOSIS = "complex_diagnosis"
    MULTI_DOMAIN = "multi_domain"
    HEALTH_CHECK = "health_check"
    APPOINTMENT = "appointment"
    MEDICATION = "medication"


# ============================================================================
# SEMANTIC ROUTER IMPLEMENTATION
# ============================================================================


class SemanticRouter:
    """Routes queries based on complexity and intent analysis."""

    def __init__(self, intent_recognizer, langgraph_orchestrator=None):
        self.intent_recognizer = intent_recognizer
        self.langgraph_orchestrator = langgraph_orchestrator
        self.complexity_threshold = float(os.getenv("COMPLEXITY_THRESHOLD", "0.8"))

    def calculate_complexity_score(self, query: str) -> float:
        """
        Calculate query complexity based on multiple factors:
        - Length of query
        - Number of medical terms
        - Presence of multiple symptoms/conditions
        - Question depth indicators
        """
        score = 0.0

        # Length factor (longer queries tend to be more complex)
        if len(query) > 200:
            score += 0.3
        elif len(query) > 100:
            score += 0.15

        # Medical complexity indicators
        complex_keywords = [
            "diagnosis",
            "differential",
            "interaction",
            "contraindication",
            "prognosis",
            "etiology",
            "comorbidity",
            "treatment plan",
            "multiple symptoms",
            "history of",
            "risk factors",
        ]
        for keyword in complex_keywords:
            if keyword.lower() in query.lower():
                score += 0.15

        # Multi-domain indicators (cardiac + nutrition + medication)
        domain_indicators = {
            "cardiac": [
                "heart",
                "cardiac",
                "cardiovascular",
                "arrhythmia",
                "ecg",
                "blood pressure",
            ],
            "nutrition": ["diet", "nutrition", "food", "eating", "weight"],
            "medication": ["drug", "medication", "prescription", "dosage", "medicine"],
        }
        domains_present = sum(
            1
            for domain, keywords in domain_indicators.items()
            if any(kw in query.lower() for kw in keywords)
        )
        if domains_present >= 2:
            score += 0.3

        return min(score, 1.0)  # Cap at 1.0


# ============================================================================
# PYDANTIC MODELS FOR REQUEST/RESPONSE
# ============================================================================


class QueryRequest(BaseModel):
    """Base query request to agents."""

    query: str = Field(..., alias="message", description="User query or input")
    session_id: str = Field(..., description="Session ID for tracking")
    user_id: str = Field(..., description="User ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "query": "I have a headache and my heart rate is 72",
                "session_id": "sess_abc123",
                "user_id": "user_123",
                "context": {"last_visit": "2025-11-20"},
            }
        }


class AgentResponse(BaseModel):
    """Response from agent processing."""

    agent: str = Field(..., description="Agent name that handled request")
    response: str = Field(..., description="Agent's response")
    action: Optional[str] = Field(
        None, description="Action taken (e.g., 'health_data_collection')"
    )
    data: Optional[Dict[str, Any]] = Field(
        None, description="Structured data extracted"
    )
    status: str = Field("success", description="Status: success, warning, error")

    class Config:
        json_schema_extra = {
            "example": {
                "agent": "HealthAgent",
                "response": "Thank you for sharing that information. Your heart rate is normal.",
                "action": "health_data_collection",
                "data": {"heart_rate": 72, "symptom": "headache", "severity": 5},
                "status": "success",
            }
        }


class HealthDataRequest(BaseModel):
    """Health-specific query request."""

    query: str = Field(..., description="Health-related query")
    session_id: str
    user_id: str
    patient_id: Optional[str] = Field(None, description="Patient ID if available")
    context: Optional[Dict[str, Any]] = None


class AppointmentRequest(BaseModel):
    """Appointment-specific query request."""

    query: str = Field(..., description="Appointment-related query")
    session_id: str
    user_id: str
    patient_id: Optional[str] = None
    provider_id: Optional[str] = None
    preferred_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    preferred_time: Optional[str] = Field(None, description="HH:MM")
    context: Optional[Dict[str, Any]] = None


class AuditLogResponse(BaseModel):
    """Audit log information."""

    timestamp: str
    agent: str
    action: str
    user_id: str
    patient_id: Optional[str] = None
    phi_fields: List[str] = []
    status: str


# ============================================================================
# GLOBAL AGENT INSTANCES
# ============================================================================

# Initialize agents at module load
health_agent = HealthAgent(name="health_agent")
appointment_agent = AppointmentAgent(name="appointment_agent")
orchestrator = HealthAppointmentOrchestrator()

logger.info("ADK agents initialized successfully")


# ============================================================================
# DEPENDENCY: VERIFY TOKEN (PLACEHOLDER)
# ============================================================================


async def verify_token(authorization: Optional[str] = None) -> str:
    """
    Verify API token/JWT.
    Placeholder - integrate with actual auth system.
    """
    if not authorization:
        # For now, allow requests without token in development
        return "dev_user"

    # TODO: Implement actual JWT verification
    # Extract token from "Bearer {token}" format
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return "verified_user"
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


# ============================================================================
# LEGACY INTENT HANDLER
# ============================================================================


async def legacy_intent_handler(
    query: str, intent: IntentEnum, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Legacy intent handler for simple queries.
    Maintains backward compatibility with existing implementation.
    """
    # Since we don't have direct access to NLPState here, we'll use the global instances
    response = {
        "query": query,
        "intent": intent.value if isinstance(intent, IntentEnum) else str(intent),
        "response": None,
        "confidence": 0.0,
    }

    try:
        # Process based on intent type
        if intent in [
            IntentEnum.SYMPTOM_CHECK,
            IntentEnum.HEALTH_CHECK,
            IntentEnum.HEALTH_EDUCATION,
        ]:
            # For simplicity, we'll simulate a response
            response["response"] = f"Processing health query: {query}"
            response["confidence"] = 0.9
        elif intent == IntentEnum.APPOINTMENT_BOOKING:
            response["response"] = "I'll help you schedule an appointment."
            response["confidence"] = 0.95
        elif intent == IntentEnum.MEDICATION_REMINDER:
            response["response"] = f"Providing medication guidance for: {query}"
            response["confidence"] = 0.85
        else:
            response["response"] = f"Processing general query: {query}"
            response["confidence"] = 0.7

    except Exception as e:
        response["error"] = str(e)
        response["confidence"] = 0.0

    return response


# ============================================================================
# ROUTES
# ============================================================================


@router.post("/health", response_model=AgentResponse)
async def health_query(
    request: HealthDataRequest, token: str = Depends(verify_token)
) -> AgentResponse:
    """
    Route query to Health Agent for health data collection and analysis.

    Health Agent handles:
    - Symptom reporting and tracking
    - Vital signs collection
    - Medication information
    - Medical history
    - Health recommendations (non-diagnostic)

    Example: "I have a persistent cough and temperature of 101"
    """
    try:
        logger.info(f"Health query from {token}: {request.query[:50]}...")

        # Process health data
        result = await health_agent.process_health_data(
            data={"query": request.query, "context": request.context or {}},
            user_id=request.user_id,
            patient_id=request.patient_id,
        )

        return AgentResponse(
            agent="HealthAgent",
            response=f"Health data processed: {result.get('status')}",
            action="health_data_collection",
            data=result.get("data", {}),
            status=result.get("status", "success"),
        )

    except Exception as e:
        logger.error(f"Error in health query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health agent error: {str(e)}",
        )


@router.post("/appointment", response_model=AgentResponse)
async def appointment_query(
    request: AppointmentRequest, token: str = Depends(verify_token)
) -> AgentResponse:
    """
    Route query to Appointment Agent for appointment booking and management.

    Appointment Agent handles:
    - Checking provider availability
    - Booking appointments
    - Rescheduling appointments
    - Cancelling appointments
    - Sending confirmations

    Example: "Can I book an appointment for Tuesday at 2 PM?"
    """
    try:
        logger.info(f"Appointment query from {token}: {request.query[:50]}...")

        # Process appointment request
        result = await appointment_agent.manage_appointment(
            appointment_data={
                "query": request.query,
                "patient_id": request.patient_id,
                "provider_id": request.provider_id,
                "preferred_date": request.preferred_date,
                "preferred_time": request.preferred_time,
                "context": request.context or {},
            },
            action="book",
        )

        return AgentResponse(
            agent="AppointmentAgent",
            response=f"Appointment request processed: {result.get('status')}",
            action="appointment_booking",
            data=result.get("data", {}),
            status=result.get("status", "success"),
        )

    except Exception as e:
        logger.error(f"Error in appointment query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Appointment agent error: {str(e)}",
        )


@router.post("/chat", response_model=AgentResponse)
async def agent_chat(
    request: QueryRequest,
    token: str = Depends(verify_token),
    nlp_service: NLPService = Depends(get_nlp_service),
) -> AgentResponse:
    """
    Smart routing endpoint - classifies query and routes to appropriate agent.

    This endpoint:
    1. Analyzes the user query using semantic router (intent + complexity)
    2. Routes to the appropriate agent (Doctor or Receptionist)
    3. Optionally adds web search tool for Receptionist when appropriate
    4. Returns structured response with intent confidence

    Query types:
    - Clinical query: "Drug interaction between aspirin and lisinopril" → Doctor (MedGemma)
    - General query: "What's the latest FDA approval for heart medication?" → Receptionist with web search
    - Appointment query: "Book an appointment" → Receptionist
    """
    try:
        logger.info(f"Chat request from {token}: {request.query[:50]}...")

        # Use semantic router to determine agent type and intent
        semantic_router = get_semantic_router()
        route_decision = semantic_router.route(request.query)

        logger.info(
            f"Routing decision: {route_decision.agent_type.value} for intent {route_decision.intent.value} "
            f"(complexity: {route_decision.complexity_score:.2f}, confidence: {route_decision.confidence:.2f})"
        )

        # Determine if web search tool should be available
        use_web_search = route_decision.intent == IntentCategory.WEB_SEARCH_TRIGGER
        
        # Process based on agent type
        if route_decision.agent_type == AgentType.DOCTOR:
            # Doctor (MedGemma) - for clinical analysis, drug interactions, etc.
            # DO NOT use web search for clinical decisions
            result = await health_agent.process_health_data(
                data={"query": request.query, "context": request.context or {}},
                user_id=request.user_id,
            )
            agent_name = "DoctorAgent (MedGemma)"
            action = "clinical_analysis"
            
        elif route_decision.agent_type == AgentType.RECEPTIONIST:
            # Receptionist - for general chat, appointments, non-clinical queries
            # MAY use web search if appropriate
            if use_web_search:
                # Execute web search tool for recent/fresh information
                web_search_result = search_verified_sources(request.query)
                
                # Include web search result in context for response generation
                context_with_web = (request.context or {}).copy()
                context_with_web["web_search_results"] = web_search_result
                
                # Process with web search context
                result = await orchestrator.run(
                    {
                        "query": request.query,
                        "session_id": request.session_id,
                        "user_id": request.user_id,
                        "context": context_with_web,
                    }
                )
                agent_name = "ReceptionistAgent (Web-Enhanced)"
                action = "web_search_response"
            else:
                # Regular receptionist processing
                if route_decision.intent == IntentCategory.APPOINTMENT:
                    # Route to Appointment Agent
                    result = await appointment_agent.manage_appointment(
                        appointment_data={
                            "query": request.query,
                            "context": request.context or {},
                        },
                        action="book",
                    )
                    agent_name = "ReceptionistAgent (Appointment)"
                    action = "appointment_booking"
                else:
                    # General receptionist processing
                    result = await orchestrator.run(
                        {
                            "query": request.query,
                            "session_id": request.session_id,
                            "user_id": request.user_id,
                            "context": request.context or {},
                        }
                    )
                    agent_name = "ReceptionistAgent (General)"
                    action = "general_response"
        
        # Include comprehensive analysis info in response data
        response_data = result.get("data", {})
        response_data["routing_analysis"] = {
            "agent_type": route_decision.agent_type.value,
            "intent": route_decision.intent.value,
            "complexity_score": route_decision.complexity_score,
            "confidence": route_decision.confidence,
            "is_emergency": route_decision.is_emergency,
            "routing_reason": route_decision.routing_reason,
            "matched_keywords": route_decision.matched_keywords,
        }

        # Include web search information if used
        if use_web_search:
            response_data["web_search_used"] = True
            response_data["web_search_tool"] = WEB_SEARCH_TOOL_DEFINITION["name"]

        # Use LLM Gateway if available
        if langchain_gateway:
            try:
                # Generate response using unified LLM Gateway
                response_text = await langchain_gateway.generate(
                    prompt=request.query,
                    content_type="medical" if route_decision.agent_type == AgentType.DOCTOR else "general",
                )
                response_data["langchain_response"] = response_text
            except Exception as e:
                logger.warning(f"LangChain generation failed: {e}")

        return AgentResponse(
            agent=agent_name,
            response=f"Query processed by {agent_name}: {result.get('status', 'success')}",
            action=action,
            data=response_data,
            status=result.get("status", "success"),
        )

    except Exception as e:
        logger.error(f"Error in agent chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(e)}",
        )


@router.post("/process", response_model=AgentResponse)
async def process_nlp(
    request: QueryRequest,
    token: str = Depends(verify_token),
    nlp_service: NLPService = Depends(get_nlp_service),
) -> AgentResponse:
    """
    Main NLP processing function with semantic routing.
    Uses NLPService for parallel processing of intent, sentiment, entities, and risk.

    This endpoint:
    - Performs comprehensive NLP analysis in parallel (~300ms vs 1200ms sequential)
    - Routes to LangGraph for complex queries, legacy handler for simple ones
    - Provides rich analysis including sentiment, entities, and risk assessment
    """
    try:
        logger.info(f"Processing NLP request from {token}: {request.query[:50]}...")

        # Try to access NLPState to get the LangGraph orchestrator
        # We'll simulate this since we don't have direct access in this context
        langgraph_orchestrator = None
        try:
            from ..main import NLPState

            langgraph_orchestrator = getattr(NLPState, "orchestrator", None)
        except ImportError:
            logger.debug("NLPState not available, using legacy processing")

        # Create semantic router with intent recognizer and LangGraph orchestrator
        router = SemanticRouter(
            intent_recognizer=nlp_service.intent_recognizer,
            langgraph_orchestrator=langgraph_orchestrator,
        )

        # Use NLPService for parallel analysis
        analysis: NLPAnalysisResult = await nlp_service.analyze(
            text=request.query, user_id=request.user_id, session_id=request.session_id
        )

        intent_result = analysis.intent
        complexity_score = router.calculate_complexity_score(request.query)

        logger.info(
            f"Intent: {intent_result.intent.value}, Complexity: {complexity_score:.2f}"
        )

        # Semantic routing decision
        if (
            intent_result.intent == IntentEnum.RISK_ASSESSMENT
            or intent_result.intent == IntentEnum.SYMPTOM_CHECK
            or complexity_score > router.complexity_threshold
        ):
            # Route to LangGraph for complex multi-step processing
            if router.langgraph_orchestrator:
                logger.info("Routing to LangGraph orchestrator for complex processing")
                result = await router.langgraph_orchestrator.process(
                    query=request.query, context=request.context
                )
                agent_name = "LangGraphOrchestrator"
                action = "complex_processing"
            else:
                # Fallback if LangGraph not available
                logger.info("LangGraph not available, falling back to legacy handler")
                result = await legacy_intent_handler(
                    request.query, intent_result.intent, request.context
                )
                agent_name = "LegacyHandler"
                action = "fallback_processing"
        else:
            # Use legacy handler for simple queries
            logger.info("Routing to legacy handler for simple processing")
            result = await legacy_intent_handler(
                request.query, intent_result.intent, request.context
            )
            agent_name = "LegacyHandler"
            action = "simple_processing"

        # Format response with comprehensive analysis
        response_data = (
            result.copy() if isinstance(result, dict) else {"result": str(result)}
        )
        response_data["nlp_analysis"] = {
            "intent_classification": {
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "keywords_matched": intent_result.keywords_matched or [],
            },
            "sentiment": {
                "sentiment": analysis.sentiment.sentiment,
                "score": analysis.sentiment.score,
            },
            "entities": [entity.to_dict() for entity in analysis.entities],
            "risk_assessment": analysis.risk.to_dict() if analysis.risk else None,
            "processing_time_ms": analysis.processing_time_ms,
        }

        if "response" in response_data:
            response_text = response_data["response"]
        else:
            response_text = str(response_data)

        return AgentResponse(
            agent=agent_name,
            response=response_text,
            action=action,
            data=response_data,
            status="success",
        )

    except Exception as e:
        logger.error(f"Error in NLP processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"NLP processing error: {str(e)}",
        )


# ============================================================================
# MONITORING & AUDIT ENDPOINTS
# ============================================================================


@router.get("/health/audit-log", response_model=List[AuditLogResponse])
async def get_health_audit_log(
    limit: int = 10, token: str = Depends(verify_token)
) -> List[AuditLogResponse]:
    """Get recent health agent audit log entries."""
    try:
        audit_trail = health_agent.get_phi_access_log()
        return [
            AuditLogResponse(
                timestamp=entry.get("timestamp", ""),
                agent=entry.get("agent", "HealthAgent"),
                action=entry.get("action", ""),
                user_id=entry.get("user_id", ""),
                patient_id=entry.get("patient_id"),
                phi_fields=entry.get("phi_fields", []),
                status="logged",
            )
            for entry in audit_trail[-limit:]
        ]
    except Exception as e:
        logger.error(f"Error retrieving audit log: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/appointment/log", response_model=List[Dict[str, Any]])
async def get_appointment_log(
    limit: int = 10, token: str = Depends(verify_token)
) -> List[Dict[str, Any]]:
    """Get recent appointment management log entries."""
    try:
        log = appointment_agent.get_appointments_log()
        return log[-limit:]
    except Exception as e:
        logger.error(f"Error retrieving appointment log: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/health/status")
async def agent_status(token: str = Depends(verify_token)) -> Dict[str, Any]:
    """Get status of all agents."""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "agents": {
                "health_agent": {
                    "name": health_agent.name,
                    "model": health_agent.model,
                    "audit_entries": len(health_agent.get_audit_trail()),
                },
                "appointment_agent": {
                    "name": appointment_agent.name,
                    "model": appointment_agent.model,
                    "appointments_managed": len(
                        appointment_agent.get_appointments_log()
                    ),
                },
                "orchestrator": {
                    "name": orchestrator.name,
                    "agents": len(orchestrator.agents),
                    "executions": len(orchestrator.get_execution_log()),
                },
            },
        }
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
