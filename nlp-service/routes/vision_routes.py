"""
Vision API Routes.

FastAPI routes for medical image analysis including:
- ECG image analysis
- Food/meal recognition
- General vision analysis
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Form
from pydantic import BaseModel, Field
import logging
import base64

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vision", tags=["Vision Analysis"])


# ==================== Request/Response Models ====================

class ECGAnalysisResponse(BaseModel):
    """ECG image analysis result."""
    rhythm: str = Field(..., description="Detected heart rhythm")
    heart_rate_bpm: Optional[int] = Field(None, description="Estimated heart rate")
    abnormalities: List[str] = Field(default_factory=list)
    confidence: float
    recommendations: List[str] = Field(default_factory=list)
    requires_review: bool = Field(False, description="Needs professional review")
    analysis_time_ms: float
    
    disclaimer: str = (
        "⚠️ This AI analysis is for informational purposes only. "
        "ECG interpretation should be performed by a qualified healthcare provider. "
        "Seek immediate medical attention if experiencing chest pain or other cardiac symptoms."
    )


class FoodAnalysisResponse(BaseModel):
    """Food recognition result."""
    food_items: List[Dict[str, Any]]
    total_calories: Optional[float] = None
    macros: Dict[str, float] = Field(default_factory=dict)
    health_score: Optional[float] = Field(None, description="0-100 heart health score")
    recommendations: List[str] = Field(default_factory=list)
    confidence: float
    analysis_time_ms: float


class VisionAnalysisRequest(BaseModel):
    """Generic vision analysis request."""
    image_base64: str = Field(..., description="Base64 encoded image")
    image_type: str = Field("auto", description="Image type: ecg, food, document, auto")
    context: Optional[str] = Field(None, description="Additional context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "image_base64": "base64_encoded_image_data...",
                "image_type": "ecg",
                "context": "Patient reports occasional palpitations"
            }
        }


class VisionAnalysisResponse(BaseModel):
    """Generic vision analysis result."""
    image_type: str
    analysis: Dict[str, Any]
    confidence: float
    processing_time_ms: float
    timestamp: str


# ==================== ECG Analysis Endpoints ====================

@router.post("/ecg/analyze", response_model=ECGAnalysisResponse)
async def analyze_ecg_image(
    file: UploadFile = File(..., description="ECG image file"),
    patient_context: Optional[str] = Form(None, description="Patient context")
):
    """
    Analyze an ECG image for heart rhythm and abnormalities.
    
    Supports common image formats (JPEG, PNG).
    Returns rhythm classification, detected abnormalities, and recommendations.
    """
    import time
    start_time = time.time()
    
    try:
        from vision import ECGAnalyzer
        
        # Read file content
        content = await file.read()
        
        analyzer = ECGAnalyzer()
        result = await analyzer.analyze(
            image_data=content,
            filename=file.filename,
            context=patient_context,
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return ECGAnalysisResponse(
            rhythm=result.rhythm.value if hasattr(result.rhythm, 'value') else str(result.rhythm),
            heart_rate_bpm=result.heart_rate_bpm,
            abnormalities=result.abnormalities,
            confidence=result.confidence,
            recommendations=result.recommendations,
            requires_review=result.requires_review,
            analysis_time_ms=elapsed_ms,
        )
        
    except ImportError as e:
        logger.warning(f"Vision service not available: {e}")
        raise HTTPException(
            status_code=503,
            detail="ECG analysis service not available"
        )
    except Exception as e:
        logger.error(f"ECG analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ecg/analyze-base64", response_model=ECGAnalysisResponse)
async def analyze_ecg_base64(
    image_base64: str = Form(..., description="Base64 encoded ECG image"),
    patient_context: Optional[str] = Form(None)
):
    """
    Analyze ECG from base64 encoded image data.
    """
    import time
    start_time = time.time()
    
    try:
        from vision import ECGAnalyzer
        
        # Decode base64
        image_data = base64.b64decode(image_base64)
        
        analyzer = ECGAnalyzer()
        result = await analyzer.analyze(
            image_data=image_data,
            filename="ecg_upload.png",
            context=patient_context,
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return ECGAnalysisResponse(
            rhythm=result.rhythm.value if hasattr(result.rhythm, 'value') else str(result.rhythm),
            heart_rate_bpm=result.heart_rate_bpm,
            abnormalities=result.abnormalities,
            confidence=result.confidence,
            recommendations=result.recommendations,
            requires_review=result.requires_review,
            analysis_time_ms=elapsed_ms,
        )
        
    except ImportError:
        raise HTTPException(status_code=503, detail="ECG analysis service not available")
    except Exception as e:
        logger.error(f"ECG analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Food Recognition Endpoints ====================

@router.post("/food/recognize", response_model=FoodAnalysisResponse)
async def recognize_food(
    file: UploadFile = File(..., description="Food/meal image"),
    estimate_portions: bool = Form(True, description="Estimate portion sizes"),
    dietary_goals: Optional[str] = Form(None, description="User dietary goals")
):
    """
    Recognize food items in an image and estimate nutritional content.
    
    Returns identified foods, calorie estimates, and heart-healthy recommendations.
    """
    import time
    start_time = time.time()
    
    try:
        from vision import FoodRecognitionService
        
        content = await file.read()
        
        service = FoodRecognitionService()
        result = await service.recognize(
            image_data=content,
            filename=file.filename,
            estimate_portions=estimate_portions,
            dietary_context=dietary_goals,
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return FoodAnalysisResponse(
            food_items=result.food_items,
            total_calories=result.total_calories,
            macros=result.macros,
            health_score=result.health_score,
            recommendations=result.recommendations,
            confidence=result.confidence,
            analysis_time_ms=elapsed_ms,
        )
        
    except ImportError:
        raise HTTPException(status_code=503, detail="Food recognition service not available")
    except Exception as e:
        logger.error(f"Food recognition error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/food/log")
async def log_meal(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    meal_type: str = Form("snack", description="breakfast, lunch, dinner, snack"),
    notes: Optional[str] = Form(None)
):
    """
    Log a meal by analyzing the food image and storing nutrition data.
    """
    import time
    start_time = time.time()
    
    try:
        from vision import FoodRecognitionService
        
        content = await file.read()
        
        service = FoodRecognitionService()
        result = await service.recognize(image_data=content, filename=file.filename)
        
        # Store the meal log (simplified - would integrate with health data storage)
        meal_log = {
            "user_id": user_id,
            "meal_type": meal_type,
            "logged_at": datetime.utcnow().isoformat(),
            "food_items": result.food_items,
            "total_calories": result.total_calories,
            "macros": result.macros,
            "notes": notes,
            "analysis_confidence": result.confidence,
        }
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return {
            "status": "logged",
            "meal_log": meal_log,
            "health_score": result.health_score,
            "recommendations": result.recommendations,
            "processing_time_ms": elapsed_ms,
        }
        
    except ImportError:
        raise HTTPException(status_code=503, detail="Food recognition service not available")
    except Exception as e:
        logger.error(f"Meal logging error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== General Vision Endpoints ====================

@router.post("/analyze", response_model=VisionAnalysisResponse)
async def analyze_image(request: VisionAnalysisRequest):
    """
    General vision analysis endpoint.
    
    Automatically detects image type if not specified and routes
    to appropriate analyzer.
    """
    import time
    start_time = time.time()
    
    try:
        from vision import VisionService, ImageType
        
        # Decode base64 image
        image_data = base64.b64decode(request.image_base64)
        
        service = VisionService()
        
        # Determine image type
        if request.image_type == "auto":
            detected_type = await service.detect_image_type(image_data)
        else:
            detected_type = ImageType(request.image_type)
        
        # Analyze based on type
        result = await service.analyze(
            image_data=image_data,
            image_type=detected_type,
            context=request.context,
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return VisionAnalysisResponse(
            image_type=detected_type.value if hasattr(detected_type, 'value') else str(detected_type),
            analysis=result.to_dict() if hasattr(result, 'to_dict') else result.__dict__,
            confidence=result.confidence,
            processing_time_ms=elapsed_ms,
            timestamp=datetime.utcnow().isoformat(),
        )
        
    except ImportError:
        raise HTTPException(status_code=503, detail="Vision service not available")
    except Exception as e:
        logger.error(f"Vision analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supported-types")
async def get_supported_types():
    """
    Get list of supported image analysis types.
    """
    return {
        "supported_types": [
            {
                "type": "ecg",
                "description": "ECG/EKG strip images for heart rhythm analysis",
                "formats": ["jpeg", "png", "bmp"],
            },
            {
                "type": "food",
                "description": "Food/meal images for nutrition analysis",
                "formats": ["jpeg", "png"],
            },
            {
                "type": "document",
                "description": "Medical documents for OCR and data extraction",
                "formats": ["jpeg", "png", "pdf", "tiff"],
            },
        ],
        "max_file_size_mb": 10,
        "recommendations": {
            "ecg": "Use high-resolution scans of ECG strips for best results",
            "food": "Include the entire plate/meal in frame with good lighting",
            "document": "Ensure text is clearly visible and not skewed",
        },
    }
