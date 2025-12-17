from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import logging

from ollama_generator import generate_response
from config import OLLAMA_MODEL

router = APIRouter(prefix="/api", tags=["Legacy Flask Endpoints"])

logger = logging.getLogger(__name__)

class WorkoutRequest(BaseModel):
    workout_type: str
    duration_minutes: int
    intensity: str = "moderate"
    heart_rate_data: List[float] = []
    user_goals: List[str] = []

class MealPlanRequest(BaseModel):
    dietary_preferences: List[str]
    calorie_target: int = 2000
    days: int = 7
    allergies: List[str] = []
    user_id: str = "anonymous"

class RecipeAnalysisRequest(BaseModel):
    recipe_name: str
    ingredients: List[str]
    servings: int = 1
    user_preferences: List[str] = []
    user_id: str = "anonymous"

class HealthAssessmentRequest(BaseModel):
    user_name: str
    age: Optional[int] = None
    vitals: Dict[str, Any] = {}
    health_history: List[str] = []
    lifestyle: Dict[str, Any] = {}
    user_id: str = "anonymous"

class MedicationInsightRequest(BaseModel):
    medications: List[Dict[str, str]]
    supplements: List[str] = []
    recent_vitals: Dict[str, Any] = {}
    user_id: str = "anonymous"

class HealthInsightRequest(BaseModel):
    user_name: str
    vitals: Dict[str, Any] = {}
    activities: List[Dict[str, Any]] = []
    medications: List[Dict[str, Any]] = []
    user_id: str = "anonymous"

@router.post("/analyze-workout")
async def analyze_workout(data: WorkoutRequest):
    """Analyze workout for performance insights"""
    try:
        avg_hr = sum(data.heart_rate_data) / len(data.heart_rate_data) if data.heart_rate_data else "N/A"
        
        prompt = f"""Analyze this workout session and provide performance insights.
Workout Type: {data.workout_type}
Duration: {data.duration_minutes} minutes
Intensity: {data.intensity}
Average Heart Rate: {avg_hr} bpm
User Goals: {', '.join(data.user_goals) if data.user_goals else 'General fitness'}

Provide a brief workout analysis including calories burned estimate, performance notes, and one recommendation for improvement."""

        analysis = await generate_response(prompt)
        
        if not analysis:
            raise HTTPException(status_code=500, detail="Failed to analyze workout")
        
        return {
            "analysis": analysis,
            "workout_type": data.workout_type,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in analyze_workout: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/generate-meal-plan")
async def generate_meal_plan(data: MealPlanRequest):
    """Generate personalized meal plan"""
    try:
        prompt = f"""Create a {data.days}-day meal plan for someone with these preferences:
Dietary Preferences: {', '.join(data.dietary_preferences)}
Calorie Target: {data.calorie_target} calories
Allergies: {', '.join(data.allergies) if data.allergies else 'None'}

Include breakfast, lunch, dinner, and 2 snacks per day. Make it realistic and nutritious."""

        meal_plan = await generate_response(prompt)
        
        if not meal_plan:
            raise HTTPException(status_code=500, detail="Failed to generate meal plan")
        
        return {
            "meal_plan": meal_plan,
            "days": data.days,
            "allergies_considered": data.allergies,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in generate_meal_plan: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/analyze-recipe")
async def analyze_recipe(data: RecipeAnalysisRequest):
    """Analyze recipe for nutritional insights"""
    try:
        prompt = f"""Analyze this recipe for nutritional insights:
Recipe Name: {data.recipe_name}
Ingredients: {', '.join(data.ingredients)}
Servings: {data.servings}

Consider these user preferences: {', '.join(data.user_preferences) if data.user_preferences else 'None'}

Provide nutritional analysis and allergen warnings if applicable."""

        analysis = await generate_response(prompt)
        
        if not analysis:
            raise HTTPException(status_code=500, detail="Failed to analyze recipe")
        
        return {
            "analysis": analysis,
            "recipe": data.recipe_name,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in analyze_recipe: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/health-assessment")
async def health_assessment(data: HealthAssessmentRequest):
    """Perform comprehensive health assessment"""
    try:
        prompt = f"""Perform a health assessment for the following user.
Name: {data.user_name}
Age: {data.age or 'N/A'}
Vitals: {json.dumps(data.vitals)}
Health History: {', '.join(data.health_history) if data.health_history else 'None reported'}
Lifestyle: {json.dumps(data.lifestyle)}

Provide a brief health assessment (3-4 bullet points) highlighting key observations and one primary recommendation."""

        assessment = await generate_response(prompt)
        
        if not assessment:
            raise HTTPException(status_code=500, detail="Failed to perform health assessment")
        
        return {
            "assessment": assessment,
            "user": data.user_name,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in health_assessment: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/medication-insights")
async def medication_insights(data: MedicationInsightRequest):
    """Provide medication-related insights"""
    try:
        med_list = [f"{m.get('name')} ({m.get('dosage', 'N/A')})" for m in data.medications]
        
        prompt = f"""Provide insights about medication management.
Current Medications: {', '.join(med_list)}
Supplements: {', '.join(data.supplements) if data.supplements else 'None'}
Recent Vitals: {json.dumps(data.recent_vitals)}

Provide brief insights on medication management including adherence tips and any observations based on vitals. Keep it practical and encouraging."""

        insights = await generate_response(prompt)
        
        if not insights:
            raise HTTPException(status_code=500, detail="Failed to provide medication insights")
        
        return {
            "insights": insights,
            "medication_count": len(data.medications),
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in medication_insights: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/generate-insight")
async def generate_insight(data: HealthInsightRequest):
    """Generate daily health insight based on user vitals and activities"""
    try:
        prompt = f"""Generate a daily health insight for {data.user_name}.
Vitals: {json.dumps(data.vitals)}
Activities: {json.dumps(data.activities)}
Medications: {json.dumps(data.medications)}

Provide a personalized health insight focusing on trends, recommendations, or educational information."""

        insight = await generate_response(prompt)
        
        if not insight:
            raise HTTPException(status_code=500, detail="Failed to generate health insight")
        
        return {
            "insight": insight,
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "provider": f"ollama-{OLLAMA_MODEL}"
        }
        
    except Exception as e:
        logger.error(f"Error in generate_insight: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")