"""
Generation Routes - Centralized AI generation endpoints.

All medical AI generation MUST flow through these endpoints.
This ensures:
1. User memory/preferences are consulted (via Memori)
2. Safety guardrails are applied (via LLMGateway)
3. Audit logging for HIPAA compliance

Endpoints:
- POST /api/generate/insight - Daily health insights
- POST /api/generate/recipe  - Recipe analysis with allergy checking
- POST /api/generate/meal-plan - Meal plan generation
- POST /api/chat/stream - Streaming chat responses (P5 FIX)
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from core.llm.llm_gateway import get_llm_gateway, LLMGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Generation"])

# Streaming chat router (separate prefix)
chat_router = APIRouter(prefix="/api/chat", tags=["Chat"])


# ============================================================================
# Request/Response Models
# ============================================================================

class InsightRequest(BaseModel):
    """Request for daily health insight generation."""
    user_id: str = Field(..., description="User identifier")
    user_name: str = Field(..., description="User's display name")
    vitals: Dict[str, Any] = Field(default_factory=dict, description="Vital signs data")
    activities: List[str] = Field(default_factory=list, description="Recent activities")
    medications: List[str] = Field(default_factory=list, description="Current medications")

class InsightResponse(BaseModel):
    """Response containing generated health insight."""
    insight: str = Field(..., description="Generated insight text with disclaimer")
    disclaimer: str = Field(..., description="Medical disclaimer")
    context_used: bool = Field(..., description="Whether user memory was used")
    provider: str = Field(..., description="LLM provider used")

class RecipeAnalysisRequest(BaseModel):
    """Request for recipe nutritional analysis."""
    user_id: str = Field(..., description="User identifier")
    recipe_name: str = Field(..., description="Name of the recipe")
    ingredients: List[str] = Field(..., description="List of ingredients")
    servings: int = Field(default=1, ge=1, description="Number of servings")
    user_preferences: List[str] = Field(default_factory=list, description="Dietary preferences")

class RecipeAnalysisResponse(BaseModel):
    """Response containing recipe analysis."""
    analysis: str = Field(..., description="Nutritional analysis")
    allergen_warnings: List[str] = Field(default_factory=list, description="Allergen warnings")
    provider: str = Field(..., description="LLM provider used")

class MealPlanRequest(BaseModel):
    """Request for meal plan generation."""
    user_id: str = Field(..., description="User identifier")
    dietary_preferences: List[str] = Field(default_factory=list, description="Dietary preferences")
    calorie_target: int = Field(default=2000, ge=1000, le=5000, description="Daily calorie target")
    days: int = Field(default=7, ge=1, le=14, description="Number of days")
    allergies: List[str] = Field(default_factory=list, description="Known allergies")

class MealPlanResponse(BaseModel):
    """Response containing generated meal plan."""
    meal_plan: str = Field(..., description="Generated meal plan")
    allergies_considered: List[str] = Field(..., description="Allergies factored in")
    provider: str = Field(..., description="LLM provider used")

class ChatRequest(BaseModel):
    """Request for streaming chat (P5 FIX)."""
    message: str = Field(..., description="User message")
    user_id: str = Field(default="anonymous", description="User identifier")
    content_type: str = Field(default="general", description="Content type for disclaimers")

class WorkoutAnalysisRequest(BaseModel):
    """Request for workout analysis."""
    workout_type: str = Field(..., description="Type of workout")
    duration_minutes: int = Field(..., description="Duration in minutes")
    intensity: str = Field(default="moderate", description="Intensity level")
    heart_rate_data: List[float] = Field(default_factory=list, description="Heart rate samples")
    user_goals: List[str] = Field(default_factory=list, description="User fitness goals")
    user_id: str = Field(default="anonymous", description="User identifier")

class WorkoutAnalysisResponse(BaseModel):
    """Response for workout analysis."""
    analysis: str = Field(..., description="Analysis text")
    workout_type: str = Field(..., description="Workout type")
    provider: str = Field(..., description="LLM provider used")

class HealthAssessmentRequest(BaseModel):
    """Request for comprehensive health assessment."""
    user_name: str = Field(..., description="User name")
    age: Optional[int] = Field(None, description="User age")
    vitals: Dict[str, Any] = Field(default_factory=dict, description="Vital signs")
    health_history: List[str] = Field(default_factory=list, description="Health history")
    lifestyle: Dict[str, Any] = Field(default_factory=dict, description="Lifestyle factors")
    user_id: str = Field(default="anonymous", description="User identifier")

class HealthAssessmentResponse(BaseModel):
    """Response for health assessment."""
    assessment: str = Field(..., description="Assessment text")
    user: str = Field(..., description="User name")
    provider: str = Field(..., description="LLM provider used")

class MedicationInsightsRequest(BaseModel):
    """Request for medication insights."""
    medications: List[Dict[str, str]] = Field(..., description="List of medications with name and dosage")
    supplements: List[str] = Field(default_factory=list, description="List of supplements")
    recent_vitals: Dict[str, Any] = Field(default_factory=dict, description="Recent vitals")
    user_id: str = Field(default="anonymous", description="User identifier")

class MedicationInsightsResponse(BaseModel):
    """Response for medication insights."""
    insights: str = Field(..., description="Insights text")
    medication_count: int = Field(..., description="Count of medications")
    provider: str = Field(..., description="LLM provider used")


# ============================================================================
# Helper Functions
# ============================================================================

async def get_user_context(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user context from Memori.
    
    This includes: health history, preferences, allergies, etc.
    """
    try:
        # Lazy import to avoid circular dependencies
        from nlp.memory_manager import MemoryManager
        
        mm = MemoryManager.get_instance()
        context = await mm.get_user_context(user_id)
        return context
    except Exception as e:
        logger.warning(f"Could not retrieve user context: {e}")
        return None

async def get_user_allergies(user_id: str) -> List[str]:
    """Get known allergies for a user from memory."""
    context = await get_user_context(user_id)
    if context:
        return context.get("allergies", [])
    return []

def check_allergens(ingredients: List[str], allergies: List[str]) -> List[str]:
    """Check ingredients against known allergies."""
    warnings = []
    ingredients_lower = [i.lower() for i in ingredients]
    
    allergen_keywords = {
        "peanut": ["peanut", "peanuts", "groundnut"],
        "tree_nut": ["almond", "walnut", "cashew", "pecan", "hazelnut", "macadamia"],
        "dairy": ["milk", "cheese", "butter", "cream", "yogurt", "lactose"],
        "gluten": ["wheat", "flour", "bread", "pasta", "barley", "rye"],
        "shellfish": ["shrimp", "crab", "lobster", "prawn", "crawfish"],
        "egg": ["egg", "eggs", "mayonnaise"],
        "soy": ["soy", "soya", "tofu", "edamame"],
    }
    
    for allergy in allergies:
        allergy_lower = allergy.lower()
        keywords = allergen_keywords.get(allergy_lower, [allergy_lower])
        
        for ingredient in ingredients_lower:
            for keyword in keywords:
                if keyword in ingredient:
                    warnings.append(f"⚠️ Contains {allergy}: {ingredient}")
                    break
    
    return warnings


# ============================================================================
# Prompt Templates
# ============================================================================

def build_insight_prompt(request: InsightRequest, context: Optional[Dict]) -> str:
    """Build prompt for health insight generation."""
    context_str = ""
    if context:
        context_str = f"""
User Health Context (from memory):
- Previous conditions: {context.get('conditions', 'None recorded')}
- Medication history: {context.get('medications', 'None recorded')}
- Health goals: {context.get('goals', 'General wellness')}
"""
    
    return f"""You are a helpful AI health assistant for {request.user_name}.

{context_str}

Current Vitals: {request.vitals}
Recent Activities: {', '.join(request.activities) if request.activities else 'None reported'}
Current Medications: {', '.join(request.medications) if request.medications else 'None reported'}

Please provide a brief, personalized daily health insight. Include:
1. A positive observation about their current status
2. One actionable suggestion for today
3. Any relevant reminder about medications or activities

Keep the response concise (2-3 short paragraphs)."""

def build_recipe_prompt(request: RecipeAnalysisRequest, allergen_warnings: List[str]) -> str:
    """Build prompt for recipe analysis."""
    warnings_str = ""
    if allergen_warnings:
        warnings_str = f"\n\n⚠️ ALLERGEN WARNINGS:\n" + "\n".join(allergen_warnings)
    
    return f"""Analyze the following recipe for nutritional value:

Recipe: {request.recipe_name}
Servings: {request.servings}
Ingredients:
{chr(10).join(f'- {i}' for i in request.ingredients)}

User Preferences: {', '.join(request.user_preferences) if request.user_preferences else 'None specified'}
{warnings_str}

Provide:
1. Estimated calories per serving
2. Macronutrient breakdown (protein, carbs, fat)
3. Key vitamins and minerals
4. Heart-healthy assessment
5. Suggestions for healthier modifications (if applicable)"""

def build_meal_plan_prompt(request: MealPlanRequest, all_allergies: List[str]) -> str:
    """Build prompt for meal plan generation."""
    allergy_str = ", ".join(all_allergies) if all_allergies else "None"
    
    return f"""Create a {request.days}-day meal plan with the following requirements:

Daily Calorie Target: {request.calorie_target} calories
Dietary Preferences: {', '.join(request.dietary_preferences) if request.dietary_preferences else 'Balanced diet'}
Allergies to Avoid: {allergy_str}

For each day, provide:
- Breakfast
- Lunch  
- Dinner
- 1-2 Snacks

Include estimated calories for each meal. Focus on heart-healthy options with:
- Lean proteins
- Whole grains
- Plenty of vegetables
- Limited sodium and saturated fat"""

def build_workout_prompt(request: WorkoutAnalysisRequest) -> str:
    """Build prompt for workout analysis."""
    avg_hr = sum(request.heart_rate_data) / len(request.heart_rate_data) if request.heart_rate_data else "N/A"
    return f"""Analyze this workout session and provide performance insights.
Workout Type: {request.workout_type}
Duration: {request.duration_minutes} minutes
Intensity: {request.intensity}
Average Heart Rate: {avg_hr} bpm
User Goals: {', '.join(request.user_goals) if request.user_goals else 'General fitness'}

Provide a brief workout analysis including calories burned estimate, performance notes, and one recommendation for improvement."""

def build_assessment_prompt(request: HealthAssessmentRequest) -> str:
    """Build prompt for health assessment."""
    return f"""Perform a health assessment for the following user.
Name: {request.user_name}
Age: {request.age if request.age else 'N/A'}
Vitals: {request.vitals}
Health History: {', '.join(request.health_history) if request.health_history else 'None reported'}
Lifestyle: {request.lifestyle}

Provide a brief health assessment (3-4 bullet points) highlighting key observations and one primary recommendation."""

def build_medication_prompt(request: MedicationInsightsRequest) -> str:
    """Build prompt for medication insights."""
    med_list = [f"{m.get('name')} ({m.get('dosage', 'N/A')})" for m in request.medications]
    return f"""Provide insights about medication management.
Current Medications: {', '.join(med_list)}
Supplements: {', '.join(request.supplements) if request.supplements else 'None'}
Recent Vitals: {request.recent_vitals}

Provide brief insights on medication management including adherence tips and any observations based on vitals. Keep it practical and encouraging."""


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/generate-insight", response_model=InsightResponse)
async def generate_insight(request: InsightRequest) -> InsightResponse:
    """
    Generate daily health insight with memory context and safety rails.
    
    This endpoint:
    1. Retrieves user context from Memori
    2. Generates personalized insight via LLM Gateway
    3. Applies medical disclaimer automatically
    """
    logger.info(f"Generating insight for user: {request.user_id}")
    
    try:
        gateway = get_llm_gateway()
        
        # Retrieve user context from memory
        user_context = await get_user_context(request.user_id)
        
        # Build prompt
        prompt = build_insight_prompt(request, user_context)
        
        # Generate with medical content type (adds disclaimer)
        insight = await gateway.generate(
            prompt=prompt,
            content_type="medical",
            user_id=request.user_id
        )
        
        status = gateway.get_status()
        
        return InsightResponse(
            insight=insight,
            disclaimer=gateway.guardrails.get_disclaimer("medical") if gateway.guardrails else "",
            context_used=user_context is not None,
            provider=status["primary_provider"]
        )
        
    except Exception as e:
        logger.error(f"Error generating insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-recipe", response_model=RecipeAnalysisResponse)
async def analyze_recipe(request: RecipeAnalysisRequest) -> RecipeAnalysisResponse:
    """
    Analyze recipe with allergy checking from user memory.
    
    This endpoint:
    1. Checks ingredients against user's stored allergies
    2. Generates nutritional analysis via LLM Gateway
    3. Applies nutrition disclaimer automatically
    """
    logger.info(f"Analyzing recipe for user: {request.user_id}")
    
    try:
        gateway = get_llm_gateway()
        
        # Get user allergies from memory
        user_allergies = await get_user_allergies(request.user_id)
        
        # Check for allergens
        allergen_warnings = check_allergens(request.ingredients, user_allergies)
        
        # Build prompt
        prompt = build_recipe_prompt(request, allergen_warnings)
        
        # Generate with nutrition content type
        analysis = await gateway.generate(
            prompt=prompt,
            content_type="nutrition",
            user_id=request.user_id
        )
        
        status = gateway.get_status()
        
        return RecipeAnalysisResponse(
            analysis=analysis,
            allergen_warnings=allergen_warnings,
            provider=status["primary_provider"]
        )
        
    except Exception as e:
        logger.error(f"Error analyzing recipe: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-meal-plan", response_model=MealPlanResponse)
async def generate_meal_plan(request: MealPlanRequest) -> MealPlanResponse:
    """
    Generate meal plan respecting user allergies from memory.
    
    This endpoint:
    1. Merges request allergies with stored allergies from memory
    2. Generates heart-healthy meal plan via LLM Gateway
    3. Applies nutrition disclaimer automatically
    """
    logger.info(f"Generating meal plan for user: {request.user_id}")
    
    try:
        gateway = get_llm_gateway()
        
        # Merge request allergies with stored allergies
        stored_allergies = await get_user_allergies(request.user_id)
        all_allergies = list(set(request.allergies + stored_allergies))
        
        # Build prompt
        prompt = build_meal_plan_prompt(request, all_allergies)
        
        # Generate with nutrition content type
        meal_plan = await gateway.generate(
            prompt=prompt,
            content_type="nutrition",
            user_id=request.user_id
        )
        
        status = gateway.get_status()
        
        return MealPlanResponse(
            meal_plan=meal_plan,
            allergies_considered=all_allergies,
            provider=status["primary_provider"]
        )
        
    except Exception as e:
        logger.error(f"Error generating meal plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-workout", response_model=WorkoutAnalysisResponse)
async def analyze_workout(request: WorkoutAnalysisRequest) -> WorkoutAnalysisResponse:
    """Analyze workout for performance insights."""
    logger.info(f"Analyzing workout for user: {request.user_id}")
    try:
        gateway = get_llm_gateway()
        prompt = build_workout_prompt(request)
        analysis = await gateway.generate(prompt=prompt, content_type="fitness", user_id=request.user_id)
        status = gateway.get_status()
        return WorkoutAnalysisResponse(
            analysis=analysis,
            workout_type=request.workout_type,
            provider=status["primary_provider"]
        )
    except Exception as e:
        logger.error(f"Error analyzing workout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/health-assessment", response_model=HealthAssessmentResponse)
async def health_assessment(request: HealthAssessmentRequest) -> HealthAssessmentResponse:
    """Perform comprehensive health assessment."""
    logger.info(f"Performing health assessment for user: {request.user_id}")
    try:
        gateway = get_llm_gateway()
        prompt = build_assessment_prompt(request)
        assessment = await gateway.generate(prompt=prompt, content_type="medical", user_id=request.user_id)
        status = gateway.get_status()
        return HealthAssessmentResponse(
            assessment=assessment,
            user=request.user_name,
            provider=status["primary_provider"]
        )
    except Exception as e:
        logger.error(f"Error performing health assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/medication-insights", response_model=MedicationInsightsResponse)
async def medication_insights(request: MedicationInsightsRequest) -> MedicationInsightsResponse:
    """Provide medication-related insights."""
    logger.info(f"Generating medication insights for user: {request.user_id}")
    try:
        gateway = get_llm_gateway()
        prompt = build_medication_prompt(request)
        insights = await gateway.generate(prompt=prompt, content_type="medical", user_id=request.user_id)
        status = gateway.get_status()
        return MedicationInsightsResponse(
            insights=insights,
            medication_count=len(request.medications),
            provider=status["primary_provider"]
        )
    except Exception as e:
        logger.error(f"Error generating medication insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_generation_status() -> Dict[str, Any]:
    """Get status of the generation service and LLM providers."""
    gateway = get_llm_gateway()
    return {
        "service": "generation",
        "llm_gateway": gateway.get_status()
    }


# ============================================================================
# Streaming Chat Endpoint (P5 FIX)
# ============================================================================

@chat_router.post("/stream")
async def stream_chat(request: ChatRequest):
    """
    Stream chat response for real-time display.
    
    FIX P5: Returns Server-Sent Events (SSE) stream of response tokens.
    Uses LLMGateway's generate_stream for non-buffered output.
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    logger.info(f"Streaming chat for user: {request.user_id}")
    
    try:
        gateway = get_llm_gateway()
        
        async def generate_sse():
            async for chunk in gateway.generate_stream(
                prompt=request.message,
                content_type=request.content_type
            ):
                # Format as Server-Sent Event
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable Nginx buffering
                "Connection": "keep-alive"
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
