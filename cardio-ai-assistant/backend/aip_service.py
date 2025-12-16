"""
Google Generative AI API Service
Handles all AI-related API calls securely from the backend
"""

import os
import json
import requests
import logging
import traceback
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file in the same directory
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Initialize Flask app
app = Flask(__name__)
# Enable CORS for all origins during development
# In production, specify allowed origins more strictly
CORS(app, 
     origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     supports_credentials=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('api_debug.log', encoding='utf-8')  # File output with UTF-8
    ]
)
logger = logging.getLogger(__name__)

# NLP Service configuration
NLP_SERVICE_URL = os.getenv('NLP_SERVICE_URL', 'http://localhost:5001')

# Configure Google Generative AI (optional - won't fail if not set)
API_KEY = os.getenv('GOOGLE_API_KEY')
model = None
if API_KEY and API_KEY != 'your-google-api-key-here':
    try:
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("✓ Gemini AI configured successfully")
    except Exception as e:
        logger.error(f"✗ Failed to configure Gemini AI: {e}")
else:
    logger.warning("⚠ GOOGLE_API_KEY not set - AI features will return mock responses")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_request(data: Dict[str, Any], required_fields: list) -> tuple[bool, Optional[str]]:
    """Validate request data has required fields"""
    if not data:
        return False, "Request body is empty"
    
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    return True, None


def generate_content(prompt: str, context: Optional[str] = None) -> Optional[str]:
    """Generate content using Google Generative AI"""
    try:
        if not model:
            logger.warning("⚠ Gemini model not available, returning mock response")
            return "Mock AI response: AI service not configured."
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        logger.debug(f"Generating content with prompt: {full_prompt[:100]}...")
        response = model.generate_content(full_prompt)
        result = response.text
        logger.debug(f"Content generated successfully: {result[:100]}...")
        return result
    except Exception as e:
        logger.error(f"✗ Error generating content: {type(e).__name__}: {str(e)}")
        logger.error(f"Traceback:", exc_info=True)
        return None


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "AI Backend Service"}), 200


@app.route('/api/generate-insight', methods=['POST'])
def generate_insight():
    """
    Generate daily health insight based on user vitals and activities
    
    Request body:
    {
        "user_name": "string",
        "vitals": {
            "heart_rate": number,
            "blood_pressure": string,
            "blood_glucose": number
        },
        "activities": ["string"],
        "medications": ["string"]
    }
    """
    try:
        logger.info(f"→ Processing /api/generate-insight request")
        data = request.get_json()
        logger.debug(f"Request payload: {data}")
        
        # Validate request
        is_valid, error_msg = validate_request(data, ["user_name", "vitals"])
        if not is_valid:
            logger.warning(f"Validation failed: {error_msg}")
            return jsonify({"error": error_msg}), 400
        
        user_name = data.get("user_name", "User")
        vitals = data.get("vitals", {})
        activities = data.get("activities", [])
        medications = data.get("medications", [])
        
        logger.debug(f"User: {user_name}, Vitals: {vitals}, Activities: {activities}, Medications: {medications}")
        
        # Build context
        context = f"""You are a health assistant providing personalized health insights.
User: {user_name}
Vitals: Heart Rate: {vitals.get('heart_rate', 'N/A')} bpm, Blood Pressure: {vitals.get('blood_pressure', 'N/A')}, Blood Glucose: {vitals.get('blood_glucose', 'N/A')} mg/dL
Recent Activities: {', '.join(activities) if activities else 'None reported'}
Current Medications: {', '.join(medications) if medications else 'None'}

Provide a brief, personalized health insight (2-3 sentences) based on these metrics."""
        
        prompt = "Generate a brief, actionable health insight based on the user's current vitals and activities."
        logger.debug(f"Calling generate_content with context length: {len(context)}")
        insight = generate_content(prompt, context)
        
        if not insight:
            logger.error("generate_content returned None")
            return jsonify({"error": "Failed to generate insight"}), 500
        
        logger.info(f"✓ Successfully generated insight for {user_name}")
        return jsonify({
            "insight": insight,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"✗ Error in generate_insight: {e}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/analyze-recipe', methods=['POST'])
def analyze_recipe():
    """
    Analyze recipe for nutritional insights
    
    Request body:
    {
        "recipe_name": "string",
        "ingredients": ["string"],
        "servings": number,
        "user_preferences": ["string"]
    }
    """
    try:
        data = request.get_json()
        
        is_valid, error_msg = validate_request(data, ["recipe_name", "ingredients"])
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        recipe_name = data.get("recipe_name")
        ingredients = data.get("ingredients", [])
        servings = data.get("servings", 1)
        preferences = data.get("user_preferences", [])
        
        context = f"""Analyze this recipe for nutritional value and health impact.
Recipe: {recipe_name}
Ingredients: {', '.join(ingredients)}
Servings: {servings}
User Preferences: {', '.join(preferences) if preferences else 'None'}"""
        
        prompt = "Provide a brief nutritional analysis including estimated calories, macros, and health benefits. Format as a simple assessment."
        analysis = generate_content(prompt, context)
        
        if not analysis:
            return jsonify({"error": "Failed to analyze recipe"}), 500
        
        return jsonify({
            "analysis": analysis,
            "recipe": recipe_name,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"✗ Error in analyze_recipe: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/analyze-workout', methods=['POST'])
def analyze_workout():
    """
    Analyze workout for performance insights
    
    Request body:
    {
        "workout_type": "string",
        "duration_minutes": number,
        "intensity": "string",
        "heart_rate_data": [number],
        "user_goals": ["string"]
    }
    """
    try:
        data = request.get_json()
        
        is_valid, error_msg = validate_request(data, ["workout_type", "duration_minutes"])
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        workout_type = data.get("workout_type")
        duration = data.get("duration_minutes")
        intensity = data.get("intensity", "moderate")
        hr_data = data.get("heart_rate_data", [])
        goals = data.get("user_goals", [])
        
        avg_hr = sum(hr_data) / len(hr_data) if hr_data else "N/A"
        
        context = f"""Analyze this workout session and provide performance insights.
Workout Type: {workout_type}
Duration: {duration} minutes
Intensity: {intensity}
Average Heart Rate: {avg_hr} bpm
User Goals: {', '.join(goals) if goals else 'General fitness'}"""
        
        prompt = "Provide a brief workout analysis including calories burned estimate, performance notes, and one recommendation for improvement."
        analysis = generate_content(prompt, context)
        
        if not analysis:
            return jsonify({"error": "Failed to analyze workout"}), 500
        
        return jsonify({
            "analysis": analysis,
            "workout_type": workout_type,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"✗ Error in analyze_workout: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/generate-meal-plan', methods=['POST'])
def generate_meal_plan():
    """
    Generate personalized meal plan
    
    Request body:
    {
        "dietary_preferences": ["string"],
        "calorie_target": number,
        "days": number,
        "allergies": ["string"]
    }
    """
    try:
        data = request.get_json()
        
        is_valid, error_msg = validate_request(data, ["dietary_preferences"])
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        preferences = data.get("dietary_preferences", [])
        calorie_target = data.get("calorie_target", 2000)
        days = data.get("days", 1)
        allergies = data.get("allergies", [])
        
        context = f"""Create a meal plan based on these requirements.
Dietary Preferences: {', '.join(preferences)}
Daily Calorie Target: {calorie_target}
Plan Duration: {days} day(s)
Allergies to Avoid: {', '.join(allergies) if allergies else 'None'}"""
        
        prompt = f"Generate a {days}-day meal plan with {days} breakfast, lunch, and dinner suggestions. Keep it brief and practical."
        meal_plan = generate_content(prompt, context)
        
        if not meal_plan:
            return jsonify({"error": "Failed to generate meal plan"}), 500
        
        return jsonify({
            "meal_plan": meal_plan,
            "days": days,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"✗ Error in generate_meal_plan: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/health-assessment', methods=['POST'])
def health_assessment():
    """
    Perform comprehensive health assessment
    
    Request body:
    {
        "user_name": "string",
        "age": number,
        "vitals": {...},
        "health_history": ["string"],
        "lifestyle": {...}
    }
    """
    try:
        data = request.get_json()
        
        is_valid, error_msg = validate_request(data, ["user_name", "vitals"])
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        user_name = data.get("user_name")
        age = data.get("age", "N/A")
        vitals = data.get("vitals", {})
        health_history = data.get("health_history", [])
        lifestyle = data.get("lifestyle", {})
        
        context = f"""Perform a health assessment for the following user.
Name: {user_name}
Age: {age}
Vitals: {json.dumps(vitals)}
Health History: {', '.join(health_history) if health_history else 'None reported'}
Lifestyle: {json.dumps(lifestyle)}"""
        
        prompt = "Provide a brief health assessment (3-4 bullet points) highlighting key observations and one primary recommendation."
        assessment = generate_content(prompt, context)
        
        if not assessment:
            return jsonify({"error": "Failed to perform assessment"}), 500
        
        return jsonify({
            "assessment": assessment,
            "user": user_name,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"✗ Error in health_assessment: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/medication-insights', methods=['POST'])
def medication_insights():
    """
    Provide medication-related insights
    
    Request body:
    {
        "medications": [{"name": "string", "dosage": "string"}],
        "supplements": ["string"],
        "recent_vitals": {...}
    }
    """
    try:
        data = request.get_json()
        
        is_valid, error_msg = validate_request(data, ["medications"])
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        medications = data.get("medications", [])
        supplements = data.get("supplements", [])
        vitals = data.get("recent_vitals", {})
        
        med_list = [f"{m.get('name')} ({m.get('dosage', 'N/A')})" for m in medications]
        
        context = f"""Provide insights about medication management.
Current Medications: {', '.join(med_list)}
Supplements: {', '.join(supplements) if supplements else 'None'}
Recent Vitals: {json.dumps(vitals)}"""
        
        prompt = "Provide brief insights on medication management including adherence tips and any observations based on vitals. Keep it practical and encouraging."
        insights = generate_content(prompt, context)
        
        if not insights:
            return jsonify({"error": "Failed to generate insights"}), 500
        
        return jsonify({
            "insights": insights,
            "medication_count": len(medications),
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"✗ Error in medication_insights: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# ============================================================================
# NLP SERVICE PROXY
# ============================================================================

@app.route('/api/nlp/process', methods=['POST'])
def process_nlp():
    """Proxy NLP requests to the NLP service"""
    try:
        data = request.get_json()
        response = requests.post(
            f"{NLP_SERVICE_URL}/api/nlp/process",
            json=data,
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "NLP service unavailable", "nlp_url": NLP_SERVICE_URL}), 503
    except Exception as e:
        logger.error(f"✗ Error in process_nlp: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/nlp/health', methods=['GET'])
def nlp_health():
    """Check NLP service health"""
    try:
        response = requests.get(f"{NLP_SERVICE_URL}/health", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.exceptions.ConnectionError:
        logger.warning(f"⚠ NLP service unavailable at {NLP_SERVICE_URL}")
        return jsonify({"status": "unavailable", "nlp_url": NLP_SERVICE_URL}), 503
    except Exception as e:
        logger.error(f"✗ Error in nlp_health: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    logger.info(f"Starting Flask backend on http://0.0.0.0:{port}")
    logger.info(f"NLP Service URL: {NLP_SERVICE_URL}")
    logger.info(f"Debug mode: {debug}")
    app.run(host='0.0.0.0', port=port, debug=debug)
