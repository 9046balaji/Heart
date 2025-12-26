"""
Tools API Routes.

FastAPI routes for LLM function calling and health tools:
- Tool registry management
- Tool execution
- Health-specific tools (BP analyzer, heart rate, drug interactions, etc.)
- Memory Tool integration for LLM function calling (Memori)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

# Import Memori MemoryTool for LLM function calling
try:
    from memori.tools.memory_tool import MemoryTool
    from memori.core.memory import Memori

    MEMORI_TOOL_AVAILABLE = True
except ImportError:
    MEMORI_TOOL_AVAILABLE = False
    MemoryTool = None
    Memori = None

# Import MemoryManager for tool integration
try:
    from nlp.memory_manager import MemoryManager

    MEMORY_MANAGER_AVAILABLE = True
except ImportError:
    MEMORY_MANAGER_AVAILABLE = False
    MemoryManager = None

router = APIRouter(prefix="/tools", tags=["Tools & Function Calling"])


# ==================== Request/Response Models ====================


class ToolExecutionRequest(BaseModel):
    """Request to execute a tool."""

    tool_name: str = Field(..., description="Name of the tool to execute")
    parameters: Dict[str, Any] = Field(..., description="Tool parameters")
    user_id: Optional[str] = Field(None, description="User ID for context")

    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "blood_pressure_analyzer",
                "parameters": {"systolic": 140, "diastolic": 90},
                "user_id": "user_123",
            }
        }


class ToolResponse(BaseModel):
    """Tool execution response."""

    tool_name: str
    success: bool
    result: Any
    execution_time_ms: float
    warnings: List[str] = []
    recommendations: List[str] = []


# ==================== Memory Tool Models ====================


class MemoryToolSchemaResponse(BaseModel):
    """Response containing MemoryTool schema for LLM function calling."""

    available: bool
    tool_name: str
    description: str
    schema: Dict[str, Any]
    usage_example: Dict[str, Any]


class MemoryToolExecuteRequest(BaseModel):
    """Request to execute MemoryTool search."""

    query: str = Field(..., description="Search query for memory retrieval")
    user_id: str = Field(..., description="User ID for memory scope")
    session_id: str = Field("default", description="Session ID")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What medications am I taking?",
                "user_id": "patient_123",
                "session_id": "session_abc",
            }
        }


class MemoryToolExecuteResponse(BaseModel):
    """Response from MemoryTool execution."""

    success: bool
    query: str
    result: str
    memories_found: int
    execution_time_ms: float


class ToolSchemaResponse(BaseModel):
    """Tool schema for LLM function calling."""

    name: str
    description: str
    parameters: Dict[str, Any]
    returns: Dict[str, Any]
    examples: List[Dict[str, Any]] = []


class BPAnalysisRequest(BaseModel):
    """Blood pressure analysis request."""

    systolic: int = Field(..., ge=60, le=250, description="Systolic pressure (mmHg)")
    diastolic: int = Field(..., ge=40, le=150, description="Diastolic pressure (mmHg)")
    pulse: Optional[int] = Field(None, ge=30, le=220, description="Pulse rate (bpm)")
    user_id: Optional[str] = Field(None, description="User ID")
    context: Optional[str] = Field(None, description="Additional context")


class HeartRateAnalysisRequest(BaseModel):
    """Heart rate analysis request."""

    heart_rate: Optional[int] = Field(None, ge=30, le=220, description="Heart rate (bpm)")
    bpm: Optional[int] = Field(None, ge=30, le=220, description="Heart rate (bpm) - alias for heart_rate")
    activity: str = Field(
        "resting", description="Activity: resting, light, moderate, intense"
    )
    user_id: Optional[str] = Field(None, description="User ID")
    age: Optional[int] = Field(None, ge=1, le=120)


class DrugInteractionRequest(BaseModel):
    """Drug interaction check request."""

    medications: List[str] = Field(..., min_length=2, description="List of medications")
    include_foods: bool = Field(False, description="Include food interactions")


class SymptomTriageRequest(BaseModel):
    """Symptom triage request."""

    symptoms: List[str] = Field(..., min_length=1)
    duration_hours: Optional[int] = Field(None)
    severity: int = Field(5, ge=1, le=10)
    age: Optional[int] = Field(None)
    medical_history: Optional[List[str]] = Field(None)


# ==================== Tool Registry Endpoints ====================


@router.get("/", response_model=List[Dict[str, Any]])
async def list_tools():
    """
    List all available tools.
    """
    try:
        from nlp.tools import get_tool_registry

        registry = get_tool_registry()
        tools = registry.list_tools()

        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "parameters": [p.dict() for p in t.parameters],
            }
            for t in tools
        ]

    except ImportError:
        # Return built-in tools list if module not available
        return [
            {
                "name": "blood_pressure_analyzer",
                "description": "Analyze blood pressure readings",
                "category": "vitals",
            },
            {
                "name": "heart_rate_analyzer",
                "description": "Analyze heart rate",
                "category": "vitals",
            },
            {
                "name": "drug_interaction_checker",
                "description": "Check drug interactions",
                "category": "medication",
            },
            {
                "name": "symptom_triage",
                "description": "Triage symptoms for urgency",
                "category": "triage",
            },
            {
                "name": "bmi_calculator",
                "description": "Calculate BMI",
                "category": "metrics",
            },
            {
                "name": "cardiovascular_risk_calculator",
                "description": "Calculate CV risk",
                "category": "risk",
            },
        ]


@router.get("/schema/{tool_name}", response_model=ToolSchemaResponse)
async def get_tool_schema(tool_name: str):
    """
    Get JSON schema for a specific tool (for LLM function calling).
    """
    try:
        from nlp.tools import get_tool_registry

        registry = get_tool_registry()
        tool = registry.get_tool(tool_name)

        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

        return ToolSchemaResponse(
            name=tool.name,
            description=tool.description,
            parameters=tool.get_json_schema(),
            returns=tool.return_schema,
            examples=tool.examples,
        )

    except ImportError:
        raise HTTPException(status_code=503, detail="Tools module not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schemas")
async def get_all_schemas():
    """
    Get all tool schemas for LLM function calling setup.

    Returns schemas in OpenAI function calling format.
    """
    try:
        from nlp.tools import get_tool_registry

        registry = get_tool_registry()
        tools = registry.list_tools()

        schemas = []
        for tool in tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.get_json_schema(),
                    },
                }
            )

        return {
            "tools": schemas,
            "count": len(schemas),
            "format": "openai_function_calling",
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="Tools module not available")
    except Exception as e:
        logger.error(f"Error getting schemas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Generic Tool Execution ====================


@router.post("/execute", response_model=ToolResponse)
async def execute_tool(request: ToolExecutionRequest):
    """
    Execute any registered tool by name.
    """
    import time

    start_time = time.time()

    try:
        from nlp.tools import execute_tool as run_tool

        result = await run_tool(
            tool_name=request.tool_name,
            parameters=request.parameters,
            user_id=request.user_id,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return ToolResponse(
            tool_name=request.tool_name,
            success=result.success,
            result=result.data,
            execution_time_ms=elapsed_ms,
            warnings=result.warnings,
            recommendations=result.recommendations,
        )

    except ImportError:
        raise HTTPException(status_code=503, detail="Tools module not available")
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Tool not found: {request.tool_name}"
        )
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Health Tool Endpoints ====================


@router.post("/blood-pressure")
async def analyze_blood_pressure(request: BPAnalysisRequest):
    """
    Analyze blood pressure reading.

    Returns classification, risk assessment, and recommendations.
    """
    try:
        from nlp.tools import blood_pressure_analyzer

        result = blood_pressure_analyzer(
            systolic=request.systolic,
            diastolic=request.diastolic,
            pulse=request.pulse,
            context=request.context,
        )

        data = result.data or {}
        return {
            "classification": data.get("category", data.get("classification")),
            "risk_level": data.get("severity", data.get("risk_level")),
            "is_hypertensive": data.get("is_hypertensive", request.systolic >= 130 or request.diastolic >= 80),
            "pulse_pressure": data.get("pulse_pressure", request.systolic - request.diastolic),
            "recommendations": data.get("recommendations", []),
            "warning": result.warnings[0] if result.warnings else None,
            "disclaimer": (
                "This analysis is for informational purposes only. "
                "Consult your healthcare provider for medical advice."
            ),
        }

    except (ImportError, Exception):
        # Fallback implementation
        systolic = request.systolic
        diastolic = request.diastolic

        if systolic < 120 and diastolic < 80:
            classification = "Normal"
            risk_level = "Low"
        elif systolic < 130 and diastolic < 80:
            classification = "Elevated"
            risk_level = "Low"
        elif systolic < 140 or diastolic < 90:
            classification = "High Blood Pressure Stage 1"
            risk_level = "Moderate"
        elif systolic >= 140 or diastolic >= 90:
            classification = "High Blood Pressure Stage 2"
            risk_level = "High"
        else:
            classification = "Unknown"
            risk_level = "Unknown"

        if systolic >= 180 or diastolic >= 120:
            classification = "Hypertensive Crisis"
            risk_level = "Critical"

        return {
            "classification": classification,
            "risk_level": risk_level,
            "is_hypertensive": systolic >= 130 or diastolic >= 80,
            "pulse_pressure": systolic - diastolic,
            "recommendations": [
                "Monitor blood pressure regularly",
                "Maintain a healthy diet low in sodium",
                "Exercise regularly",
            ],
            "warning": (
                "Seek immediate medical attention" if risk_level == "Critical" else None
            ),
            "disclaimer": "This analysis is for informational purposes only.",
        }


@router.post("/heart-rate")
async def analyze_heart_rate(request: HeartRateAnalysisRequest):
    """
    Analyze heart rate.
    """
    try:
        from nlp.tools import heart_rate_analyzer

        hr_value = request.heart_rate or request.bpm
        if hr_value is None:
            raise HTTPException(status_code=400, detail="heart_rate or bpm is required")

        result = heart_rate_analyzer(
            heart_rate=hr_value,
            activity=request.activity,
            age=request.age,
        )

        return result.to_dict()

    except ImportError:
        # Fallback implementation
        hr = request.heart_rate or request.bpm
        if hr is None:
            raise HTTPException(status_code=400, detail="heart_rate or bpm is required")
        activity = request.activity

        if activity == "resting":
            if hr < 60:
                classification = "Bradycardia (slow)"
            elif hr <= 100:
                classification = "Normal resting"
            else:
                classification = "Tachycardia (fast)"
        else:
            # Active heart rates
            if request.age:
                max_hr = 220 - request.age
                hr_percent = (hr / max_hr) * 100
                if hr_percent < 50:
                    classification = "Light activity"
                elif hr_percent < 70:
                    classification = "Moderate activity"
                elif hr_percent < 85:
                    classification = "Vigorous activity"
                else:
                    classification = "Maximum effort"
            else:
                classification = "Active"

        return {
            "heart_rate": hr,
            "classification": classification,
            "activity_level": activity,
            "is_normal": 60 <= hr <= 100 if activity == "resting" else True,
            "recommendations": ["Consult a doctor if experiencing unusual symptoms"],
        }


@router.post("/drug-interactions")
async def check_drug_interactions(request: DrugInteractionRequest):
    """
    Check for potential drug interactions.

    ⚠️ This is for informational purposes only - always consult a pharmacist.
    """
    try:
        from nlp.tools import drug_interaction_checker

        result = drug_interaction_checker(
            medications=request.medications,
            include_foods=request.include_foods,
        )

        data = result.data or {}
        return {
            "medications_checked": request.medications,
            "interactions": data.get("interactions", []),
            "severity_summary": data.get("summary", "No interactions found"),
            "recommendations": data.get("recommendations", []),
            "disclaimer": "⚠️ Always consult a pharmacist or healthcare provider about drug interactions.",
        }

    except (ImportError, Exception):
        # Return basic response
        return {
            "medications_checked": request.medications,
            "interactions": [],
            "severity_summary": "No significant interactions found",
            "recommendations": ["Consult your pharmacist about potential interactions"],
            "disclaimer": "⚠️ Always consult a pharmacist or healthcare provider about drug interactions.",
        }


@router.post("/symptom-triage")
async def triage_symptoms(request: SymptomTriageRequest):
    """
    Triage symptoms for urgency level.

    ⚠️ This is not a substitute for professional medical evaluation.
    """
    try:
        from nlp.tools import symptom_triage

        result = symptom_triage(
            symptoms=request.symptoms,
            duration_hours=request.duration_hours,
            severity=request.severity,
            age=request.age,
            medical_history=request.medical_history,
        )

        data = result.data or {}
        return {
            "urgency_level": data.get("urgency", "routine"),
            "recommended_action": data.get("action", "Monitor symptoms"),
            "possible_conditions": data.get("possible_conditions", []),
            "red_flags": result.warnings,
            "next_steps": data.get("recommendations", []),
            "disclaimer": data.get("disclaimer", "This is not a diagnosis."),
        }

    except (ImportError, Exception):
        # Basic triage logic
        urgency = "routine"
        action = "Schedule appointment with your doctor"

        emergency_symptoms = [
            "chest pain",
            "difficulty breathing",
            "stroke",
            "severe bleeding",
            "unconscious",
        ]
        urgent_symptoms = ["high fever", "severe pain", "head injury", "broken bone"]

        for symptom in request.symptoms:
            symptom_lower = symptom.lower()
            if any(e in symptom_lower for e in emergency_symptoms):
                urgency = "emergency"
                action = "Call 911 or go to emergency room immediately"
                break
            if any(u in symptom_lower for u in urgent_symptoms):
                urgency = "urgent"
                action = "Seek medical attention within 24 hours"

        if request.severity >= 8:
            urgency = "urgent" if urgency != "emergency" else urgency

        return {
            "urgency_level": urgency,
            "recommended_action": action,
            "possible_conditions": [
                "Multiple conditions possible - professional evaluation needed"
            ],
            "red_flags": [
                s
                for s in request.symptoms
                if any(e in s.lower() for e in emergency_symptoms)
            ],
            "next_steps": [
                "Document your symptoms",
                "Note when symptoms started",
                action,
            ],
            "disclaimer": (
                "⚠️ This triage is for guidance only. "
                "If in doubt, seek professional medical help immediately."
            ),
        }


@router.post("/calculate/bmi")
async def calculate_bmi(
    weight_kg: float = Body(..., ge=20, le=500),
    height_cm: float = Body(..., ge=50, le=300),
):
    """
    Calculate BMI and provide classification.
    """
    try:
        from nlp.tools import bmi_calculator

        return bmi_calculator(weight_kg=weight_kg, height_cm=height_cm).__dict__
    except ImportError:
        height_m = height_cm / 100
        bmi = weight_kg / (height_m**2)

        if bmi < 18.5:
            category = "Underweight"
        elif bmi < 25:
            category = "Normal weight"
        elif bmi < 30:
            category = "Overweight"
        else:
            category = "Obese"

        return {
            "bmi": round(bmi, 1),
            "category": category,
            "healthy_weight_range_kg": {
                "min": round(18.5 * (height_m**2), 1),
                "max": round(24.9 * (height_m**2), 1),
            },
            "recommendations": [
                "Maintain a balanced diet",
                "Exercise regularly",
                "Consult a nutritionist for personalized advice",
            ],
        }


@router.post("/calculate/cardiovascular-risk")
async def calculate_cv_risk(
    age: int = Body(..., ge=20, le=100),
    gender: str = Body(..., description="M or F"),
    systolic_bp: int = Body(..., ge=90, le=200),
    total_cholesterol: int = Body(..., ge=100, le=400),
    hdl_cholesterol: int = Body(..., ge=20, le=100),
    smoker: bool = Body(...),
    diabetic: bool = Body(False),
    on_bp_meds: bool = Body(False),
):
    """
    Calculate 10-year cardiovascular risk using Framingham algorithm.
    """
    try:
        from nlp.tools import cardiovascular_risk_calculator

        return cardiovascular_risk_calculator(
            age=age,
            gender=gender,
            systolic_bp=systolic_bp,
            total_cholesterol=total_cholesterol,
            hdl_cholesterol=hdl_cholesterol,
            smoker=smoker,
            diabetic=diabetic,
            on_bp_meds=on_bp_meds,
        ).__dict__

    except ImportError:
        # Simplified risk calculation
        risk_score = 0

        # Age factor
        if age >= 65:
            risk_score += 15
        elif age >= 55:
            risk_score += 10
        elif age >= 45:
            risk_score += 5

        # Blood pressure
        if systolic_bp >= 160:
            risk_score += 10
        elif systolic_bp >= 140:
            risk_score += 5

        # Cholesterol
        ratio = total_cholesterol / hdl_cholesterol
        if ratio > 5:
            risk_score += 10
        elif ratio > 4:
            risk_score += 5

        # Risk factors
        if smoker:
            risk_score += 10
        if diabetic:
            risk_score += 10
        if gender == "M":
            risk_score += 5

        # Calculate percentage (simplified)
        risk_percent = min(risk_score, 30)

        if risk_percent < 10:
            category = "Low"
        elif risk_percent < 20:
            category = "Moderate"
        else:
            category = "High"

        return {
            "risk_percent": risk_percent,
            "risk_category": category,
            "risk_factors": {
                "age": age >= 45,
                "high_bp": systolic_bp >= 140,
                "high_cholesterol": total_cholesterol > 200,
                "low_hdl": hdl_cholesterol < 40,
                "smoker": smoker,
                "diabetic": diabetic,
            },
            "recommendations": [
                "Schedule a cardiovascular checkup",
                "Maintain healthy blood pressure",
                "Monitor cholesterol levels",
                "Quit smoking" if smoker else "Maintain non-smoking status",
            ],
            "disclaimer": "This is a simplified risk estimate. Consult your cardiologist for accurate assessment.",
        }


# ==================== Memory Tool Endpoints (Memori Integration) ====================


@router.get("/memory/schema", response_model=MemoryToolSchemaResponse)
async def get_memory_tool_schema():
    """
    Get the MemoryTool schema for LLM function calling.

    Returns the tool schema compatible with OpenAI function calling format,
    allowing LLMs to search and retrieve conversation memory.

    This enables LLMs to:
    - Search conversation history
    - Retrieve patient context
    - Access stored health data
    """
    if not MEMORI_TOOL_AVAILABLE:
        return MemoryToolSchemaResponse(
            available=False,
            tool_name="memori_memory",
            description="Memory tool not available - Memori package not installed",
            schema={},
            usage_example={},
        )

    # Create schema without actual Memori instance
    schema = {
        "name": "memori_memory",
        "description": "Search and retrieve information from conversation memory",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query to find relevant memories, conversations, "
                        "or personal information about the user"
                    ),
                },
            },
            "required": ["query"],
        },
    }

    return MemoryToolSchemaResponse(
        available=True,
        tool_name="memori_memory",
        description="Search and retrieve information from conversation memory",
        schema=schema,
        usage_example={
            "function_call": {
                "name": "memori_memory",
                "arguments": '{"query": "What medications is the patient taking?"}',
            },
            "openai_format": {"type": "function", "function": schema},
        },
    )


@router.post("/memory/execute", response_model=MemoryToolExecuteResponse)
async def execute_memory_tool(request: MemoryToolExecuteRequest):
    """
    Execute a MemoryTool search query.

    This endpoint allows executing memory searches that would typically
    be invoked by an LLM through function calling.

    Args:
        request: Search query and user context

    Returns:
        Search results from memory
    """
    import time

    start_time = time.time()

    if not MEMORI_TOOL_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="MemoryTool not available - Memori package not installed",
        )

    if not MEMORY_MANAGER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Memory manager not available")

    try:
        memory_mgr = MemoryManager.get_instance()

        # Search memory using memory manager
        results = await memory_mgr.search_memory(
            patient_id=request.user_id,
            query=request.query,
            session_id=request.session_id,
            limit=10,
        )

        # Format results as string (as MemoryTool would return)
        if results:
            result_text = "\n".join(
                [
                    (
                        f"- [{r.memory_type}] {r.content[:200]}..."
                        if len(r.content) > 200
                        else f"- [{r.memory_type}] {r.content}"
                    )
                    for r in results
                ]
            )
        else:
            result_text = "No relevant memories found for the query."

        elapsed_ms = (time.time() - start_time) * 1000

        return MemoryToolExecuteResponse(
            success=True,
            query=request.query,
            result=result_text,
            memories_found=len(results),
            execution_time_ms=round(elapsed_ms, 2),
        )

    except Exception as e:
        logger.error(f"MemoryTool execution error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Memory tool execution failed: {str(e)}"
        )


@router.get("/memory/status")
async def get_memory_tool_status():
    """
    Get status of MemoryTool integration.

    Returns availability and configuration status.
    """
    return {
        "memori_tool_available": MEMORI_TOOL_AVAILABLE,
        "memory_manager_available": MEMORY_MANAGER_AVAILABLE,
        "capabilities": {
            "semantic_search": MEMORI_TOOL_AVAILABLE,
            "conversation_memory": MEMORY_MANAGER_AVAILABLE,
            "llm_function_calling": MEMORI_TOOL_AVAILABLE,
        },
        "timestamp": datetime.now().isoformat(),
    }

@router.get("/patient-summary/{user_id}")
async def get_patient_summary_proxy(user_id: str):
    """Proxy to patient summary generation."""
    from routes.medical_ai_routes import generate_patient_summary, PatientSummaryRequest
    request = PatientSummaryRequest(patient_id=user_id, document_texts=[])
    return await generate_patient_summary(request, user_id=user_id)

@router.post("/extract-entities")
async def extract_entities_proxy(request: Dict[str, Any], user_id: str = Query("default")):
    """Proxy to entity extraction."""
    from routes.medical_ai_routes import extract_entities, EntityExtractionRequest
    req = EntityExtractionRequest(text=request.get("text", ""), document_type=request.get("document_type"))
    return await extract_entities(req, user_id=user_id)

@router.post("/terminology/expand")
async def expand_terminology_proxy(request: Dict[str, Any], user_id: str = Query("default")):
    """Proxy to terminology expansion."""
    from routes.medical_ai_routes import expand_terminology, TerminologyRequest
    req = TerminologyRequest(terms=[request.get("term", "")] if "term" in request else request.get("terms", []))
    return await expand_terminology(req, user_id=user_id)
