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

from agents.base import (
    HealthAgent,
    AppointmentAgent,
    HealthAppointmentOrchestrator
)

# Import IntentRecognizer for smart query routing
from intent_recognizer import IntentRecognizer, IntentResult
from models import IntentEnum

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/agents", tags=["agents"])

# ============================================================================
# PYDANTIC MODELS FOR REQUEST/RESPONSE
# ============================================================================


class QueryRequest(BaseModel):
    """Base query request to agents."""
    query: str = Field(..., description="User query or input")
    session_id: str = Field(..., description="Session ID for tracking")
    user_id: str = Field(..., description="User ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "I have a headache and my heart rate is 72",
                "session_id": "sess_abc123",
                "user_id": "user_123",
                "context": {"last_visit": "2025-11-20"}
            }
        }


class AgentResponse(BaseModel):
    """Response from agent processing."""
    agent: str = Field(..., description="Agent name that handled request")
    response: str = Field(..., description="Agent's response")
    action: Optional[str] = Field(None, description="Action taken (e.g., 'health_data_collection')")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured data extracted")
    status: str = Field("success", description="Status: success, warning, error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent": "HealthAgent",
                "response": "Thank you for sharing that information. Your heart rate is normal.",
                "action": "health_data_collection",
                "data": {
                    "heart_rate": 72,
                    "symptom": "headache",
                    "severity": 5
                },
                "status": "success"
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

# Initialize IntentRecognizer for smart query routing
intent_recognizer = IntentRecognizer()

logger.info("ADK agents and IntentRecognizer initialized successfully")


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
# ROUTES
# ============================================================================


@router.post("/health", response_model=AgentResponse)
async def health_query(
    request: HealthDataRequest,
    token: str = Depends(verify_token)
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
            patient_id=request.patient_id
        )
        
        return AgentResponse(
            agent="HealthAgent",
            response=f"Health data processed: {result.get('status')}",
            action="health_data_collection",
            data=result.get("data", {}),
            status=result.get("status", "success")
        )
    
    except Exception as e:
        logger.error(f"Error in health query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health agent error: {str(e)}"
        )


@router.post("/appointment", response_model=AgentResponse)
async def appointment_query(
    request: AppointmentRequest,
    token: str = Depends(verify_token)
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
                "context": request.context or {}
            },
            action="book"
        )
        
        return AgentResponse(
            agent="AppointmentAgent",
            response=f"Appointment request processed: {result.get('status')}",
            action="appointment_booking",
            data=result.get("data", {}),
            status=result.get("status", "success")
        )
    
    except Exception as e:
        logger.error(f"Error in appointment query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Appointment agent error: {str(e)}"
        )


@router.post("/chat", response_model=AgentResponse)
async def agent_chat(
    request: QueryRequest,
    token: str = Depends(verify_token)
) -> AgentResponse:
    """
    Smart routing endpoint - classifies query and routes to appropriate agent.
    
    This endpoint:
    1. Analyzes the user query using IntentRecognizer (Trie + TF-IDF)
    2. Routes to the appropriate agent (Health, Appointment, or Sequential)
    3. Returns structured response with intent confidence
    
    Query types:
    - Health query: "I have a headache" → HealthAgent
    - Appointment query: "Book an appointment" → AppointmentAgent
    - Complex: "I have a fever and need an urgent appointment" → HealthAppointmentOrchestrator
    """
    try:
        logger.info(f"Chat request from {token}: {request.query[:50]}...")
        
        # Use IntentRecognizer for smart classification (Trie + TF-IDF)
        intent_result: IntentResult = await intent_recognizer.recognize_intent_async(request.query)
        
        logger.info(f"Intent classified: {intent_result.intent.value} (confidence: {intent_result.confidence:.2f})")
        
        # Define health-related intents
        health_intents = {
            IntentEnum.SYMPTOM_CHECK,
            IntentEnum.MEDICATION_REMINDER,
            IntentEnum.RISK_ASSESSMENT,
            IntentEnum.HEALTH_EDUCATION,
            IntentEnum.HEALTH_GOAL,
            IntentEnum.NUTRITION_ADVICE,
            IntentEnum.EXERCISE_COACHING,
            IntentEnum.EMERGENCY
        }
        
        # Route based on recognized intent
        if intent_result.intent == IntentEnum.APPOINTMENT_BOOKING:
            # Route to Appointment Agent
            result = await appointment_agent.manage_appointment(
                appointment_data={
                    "query": request.query,
                    "context": request.context or {}
                },
                action="book"
            )
            agent_name = "AppointmentAgent"
            action = "appointment_booking"
        
        elif intent_result.intent in health_intents and intent_result.confidence >= 0.3:
            # Route to Health Agent
            result = await health_agent.process_health_data(
                data={"query": request.query, "context": request.context or {}},
                user_id=request.user_id
            )
            agent_name = "HealthAgent"
            action = "health_data_collection"
        
        elif intent_result.intent == IntentEnum.GREETING:
            # Handle greetings directly
            result = {
                "status": "success",
                "data": {
                    "response": "Hello! How can I help you today with your health or appointments?",
                    "intent": intent_result.intent.value
                }
            }
            agent_name = "GreetingHandler"
            action = "greeting_response"
        
        elif intent_result.confidence < 0.3 or intent_result.intent == IntentEnum.UNKNOWN:
            # Low confidence or unknown intent: Use Sequential Orchestrator
            result = await orchestrator.run({
                "query": request.query,
                "session_id": request.session_id,
                "user_id": request.user_id,
                "context": request.context or {}
            })
            agent_name = "HealthAppointmentOrchestrator"
            action = "orchestration"
        
        else:
            # Default: Use Sequential Orchestrator for complex/ambiguous queries
            result = await orchestrator.run({
                "query": request.query,
                "session_id": request.session_id,
                "user_id": request.user_id,
                "context": request.context or {}
            })
            agent_name = "HealthAppointmentOrchestrator"
            action = "orchestration"
        
        # Include intent info in response data
        response_data = result.get("data", {})
        response_data["intent_classification"] = {
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "keywords_matched": intent_result.keywords_matched or []
        }
        
        return AgentResponse(
            agent=agent_name,
            response=f"Query processed by {agent_name}: {result.get('status', 'success')}",
            action=action,
            data=response_data,
            status=result.get("status", "success")
        )
    
    except Exception as e:
        logger.error(f"Error in agent chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(e)}"
        )


# ============================================================================
# MONITORING & AUDIT ENDPOINTS
# ============================================================================


@router.get("/health/audit-log", response_model=List[AuditLogResponse])
async def get_health_audit_log(
    limit: int = 10,
    token: str = Depends(verify_token)
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
                status="logged"
            )
            for entry in audit_trail[-limit:]
        ]
    except Exception as e:
        logger.error(f"Error retrieving audit log: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/appointment/log", response_model=List[Dict[str, Any]])
async def get_appointment_log(
    limit: int = 10,
    token: str = Depends(verify_token)
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
                    "audit_entries": len(health_agent.get_audit_trail())
                },
                "appointment_agent": {
                    "name": appointment_agent.name,
                    "model": appointment_agent.model,
                    "appointments_managed": len(appointment_agent.get_appointments_log())
                },
                "orchestrator": {
                    "name": orchestrator.name,
                    "agents": len(orchestrator.agents),
                    "executions": len(orchestrator.get_execution_log())
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
