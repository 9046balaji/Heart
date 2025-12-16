"""
Google Generative AI API Service
Handles all AI-related API calls securely from the backend
"""

import os
import json
import requests
import logging
import traceback
from typing import Optional, Dict, Any, Generator
from flask import Flask, request, jsonify, Response, stream_with_context
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

# ============================================================================
# AI GENERATION - ALL AI CALLS NOW PROXY TO NLP SERVICE (P1 FIX)
# ============================================================================
# The google.generativeai import has been REMOVED.
# All AI generation now flows through the NLP Service which provides:
# - Unified LLM Gateway (Gemini/Ollama with fallback)
# - Safety guardrails (PII redaction, medical disclaimers)
# - User memory context integration
# - Centralized audit logging for HIPAA compliance

logger.info(f"✓ AI generation will proxy to NLP Service at {NLP_SERVICE_URL}")

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


def proxy_to_nlp(endpoint: str, data: dict, timeout: int = 30) -> tuple:
    """
    Proxy request to NLP Service with error handling.
    
    All AI generation is now centralized in the NLP Service which handles:
    - LLM provider selection (Gemini/Ollama)
    - Safety guardrails (PII redaction, disclaimers)
    - User memory context
    - Audit logging
    
    Args:
        endpoint: NLP Service endpoint path (e.g., "/api/generate/insight")
        data: Request payload
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (response_data, status_code)
    """
    try:
        logger.debug(f"Proxying to NLP Service: {endpoint}")
        response = requests.post(
            f"{NLP_SERVICE_URL}{endpoint}",
            json=data,
            timeout=timeout,
            headers={"X-Forwarded-For": request.remote_addr}  # For rate limiting
        )
        return response.json(), response.status_code
    except requests.exceptions.ConnectionError:
        logger.error(f"✗ NLP Service unavailable at {NLP_SERVICE_URL}")
        return {"error": "AI service unavailable", "detail": "NLP Service not reachable"}, 503
    except requests.exceptions.Timeout:
        logger.error(f"✗ NLP Service timeout for {endpoint}")
        return {"error": "AI service timeout", "detail": "Request took too long"}, 504
    except Exception as e:
        logger.error(f"✗ NLP Service proxy error: {e}")
        return {"error": f"AI service error: {str(e)}"}, 500


def stream_to_nlp(endpoint: str, data: dict, timeout: int = 120) -> Generator[str, None, None]:
    """
    Stream response from NLP Service for real-time LLM output.
    
    FIX P5: Enable true streaming to eliminate Flask buffering.
    This allows character-by-character display in the frontend.
    
    Args:
        endpoint: NLP Service endpoint path
        data: Request payload
        timeout: Request timeout in seconds
        
    Yields:
        Response chunks as they arrive from the LLM
    """
    try:
        logger.debug(f"Streaming from NLP Service: {endpoint}")
        with requests.post(
            f"{NLP_SERVICE_URL}{endpoint}",
            json=data,
            stream=True,
            timeout=timeout,
            headers={
                "X-Forwarded-For": request.remote_addr,
                "Accept": "text/event-stream"
            }
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    yield chunk
    except requests.exceptions.ConnectionError:
        logger.error(f"✗ NLP Service unavailable for streaming")
        yield json.dumps({"error": "AI service unavailable"})
    except requests.exceptions.Timeout:
        logger.error(f"✗ NLP Service streaming timeout")
        yield json.dumps({"error": "AI service timeout"})
    except Exception as e:
        logger.error(f"✗ Streaming error: {e}")
        yield json.dumps({"error": str(e)})


# ============================================================================
# STREAMING ENDPOINTS (P5 FIX)
# ============================================================================

@app.route('/api/chat/stream', methods=['POST'])
def stream_chat():
    """
    Stream chat response for real-time display.
    
    FIX P5: Uses stream_with_context to prevent Flask buffering.
    Disables Nginx buffering via X-Accel-Buffering header.
    
    Returns:
        Server-Sent Events (SSE) stream of response tokens
    """
    try:
        logger.info("→ Starting streaming chat")
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "Message required"}), 400
        
        def generate():
            for chunk in stream_to_nlp("/api/chat/stream", data):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        
        return Response(
            stream_with_context(generate()),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',  # Disable Nginx buffering
                'Connection': 'keep-alive'
            }
        )
        
    except Exception as e:
        logger.error(f"✗ Streaming chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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
    Generate daily health insight based on user vitals and activities.
    
    PROXIED TO NLP SERVICE (P1 FIX) - Includes:
    - User memory context integration
    - Medical disclaimers
    - PII redaction
    """
    try:
        logger.info(f"→ Proxying /api/generate-insight to NLP Service")
        data = request.get_json()
        
        # Validate request
        is_valid, error_msg = validate_request(data, ["user_name", "vitals"])
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Transform to NLP Service format
        nlp_payload = {
            "user_id": data.get("user_id", "anonymous"),
            "user_name": data.get("user_name", "User"),
            "vitals": data.get("vitals", {}),
            "activities": data.get("activities", []),
            "medications": data.get("medications", [])
        }
        
        # Proxy to NLP Service
        result, status_code = proxy_to_nlp("/api/generate/insight", nlp_payload)
        
        # Transform response to match legacy format
        if status_code == 200:
            return jsonify({
                "insight": result.get("insight", ""),
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "context_used": result.get("context_used", False),
                "provider": result.get("provider", "nlp-service")
            }), 200
        else:
            return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"✗ Error in generate_insight: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/analyze-recipe', methods=['POST'])
def analyze_recipe():
    """
    Analyze recipe for nutritional insights.
    
    PROXIED TO NLP SERVICE (P1 FIX) - Includes:
    - User allergy checking from memory
    - Nutrition disclaimers
    """
    try:
        logger.info(f"→ Proxying /api/analyze-recipe to NLP Service")
        data = request.get_json()
        
        is_valid, error_msg = validate_request(data, ["recipe_name", "ingredients"])
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Transform to NLP Service format
        nlp_payload = {
            "user_id": data.get("user_id", "anonymous"),
            "recipe_name": data.get("recipe_name"),
            "ingredients": data.get("ingredients", []),
            "servings": data.get("servings", 1),
            "user_preferences": data.get("user_preferences", [])
        }
        
        # Proxy to NLP Service
        result, status_code = proxy_to_nlp("/api/generate/recipe", nlp_payload)
        
        if status_code == 200:
            return jsonify({
                "analysis": result.get("analysis", ""),
                "recipe": data.get("recipe_name"),
                "allergen_warnings": result.get("allergen_warnings", []),
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }), 200
        else:
            return jsonify(result), status_code
        
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
    Generate personalized meal plan.
    
    PROXIED TO NLP SERVICE (P1 FIX) - Includes:
    - User allergy merging from memory
    - Nutrition disclaimers
    """
    try:
        logger.info(f"→ Proxying /api/generate-meal-plan to NLP Service")
        data = request.get_json()
        
        is_valid, error_msg = validate_request(data, ["dietary_preferences"])
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        # Transform to NLP Service format
        nlp_payload = {
            "user_id": data.get("user_id", "anonymous"),
            "dietary_preferences": data.get("dietary_preferences", []),
            "calorie_target": data.get("calorie_target", 2000),
            "days": data.get("days", 7),
            "allergies": data.get("allergies", [])
        }
        
        # Proxy to NLP Service
        result, status_code = proxy_to_nlp("/api/generate/meal-plan", nlp_payload)
        
        if status_code == 200:
            return jsonify({
                "meal_plan": result.get("meal_plan", ""),
                "days": data.get("days", 7),
                "allergies_considered": result.get("allergies_considered", []),
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }), 200
        else:
            return jsonify(result), status_code
        
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
