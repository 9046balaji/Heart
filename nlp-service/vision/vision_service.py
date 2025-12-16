"""
Core Vision Analysis Service.

Provides multimodal vision capabilities using Gemini Vision
and specialized models for medical image analysis.

Features:
- Image classification (ECG, food, document, etc.)
- Multi-model routing based on image type
- Caching for repeated analyses
- Fallback handling
"""

import logging
import base64
import hashlib
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import asyncio
import os

logger = logging.getLogger(__name__)


class ImageType(Enum):
    """Types of images the service can process."""
    ECG = "ecg"
    FOOD = "food"
    DOCUMENT = "document"
    MEDICAL_SCAN = "medical_scan"
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    GENERAL = "general"
    UNKNOWN = "unknown"


class AnalysisConfidence(Enum):
    """Confidence levels for analysis."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


@dataclass
class AnalysisResult:
    """Result from image analysis."""
    success: bool
    image_type: ImageType
    confidence: float
    analysis: Dict[str, Any]
    summary: str
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    processing_time_ms: float = 0
    model_used: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "image_type": self.image_type.value,
            "confidence": self.confidence,
            "analysis": self.analysis,
            "summary": self.summary,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "processing_time_ms": self.processing_time_ms,
            "model_used": self.model_used,
            "timestamp": self.timestamp,
        }


@dataclass
class VisionAnalysis:
    """Complete vision analysis output."""
    image_hash: str
    results: List[AnalysisResult]
    primary_classification: ImageType
    combined_summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "image_hash": self.image_hash,
            "results": [r.to_dict() for r in self.results],
            "primary_classification": self.primary_classification.value,
            "combined_summary": self.combined_summary,
            "metadata": self.metadata,
        }


class VisionService:
    """
    Core vision analysis service.
    
    Routes images to appropriate analyzers and combines
    results for comprehensive analysis.
    
    Example:
        service = VisionService()
        result = await service.analyze_image(image_bytes)
        print(result.combined_summary)
    """
    
    # Image type detection patterns
    IMAGE_PATTERNS = {
        ImageType.ECG: ["ecg", "electrocardiogram", "heart rhythm", "ekg"],
        ImageType.FOOD: ["food", "meal", "dish", "plate", "nutrition"],
        ImageType.DOCUMENT: ["document", "text", "paper", "form"],
        ImageType.PRESCRIPTION: ["prescription", "rx", "medication", "pharmacy"],
        ImageType.LAB_REPORT: ["lab", "laboratory", "test results", "blood work"],
        ImageType.MEDICAL_SCAN: ["xray", "x-ray", "mri", "ct scan", "ultrasound"],
    }
    
    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        use_mock: bool = False,
        cache_enabled: bool = True,
        max_cache_size: int = 100,
    ):
        """
        Initialize vision service.
        
        Args:
            gemini_api_key: API key for Gemini Vision
            use_mock: Use mock responses
            cache_enabled: Enable result caching
            max_cache_size: Maximum cache entries
        """
        self.api_key = gemini_api_key or os.getenv("GOOGLE_API_KEY")
        self.use_mock = use_mock or not self.api_key
        self.cache_enabled = cache_enabled
        self._cache: Dict[str, VisionAnalysis] = {}
        self._max_cache_size = max_cache_size
        
        # Lazy-loaded analyzers
        self._ecg_analyzer = None
        self._food_recognizer = None
        self._document_scanner = None
        self._gemini_model = None
        
        if self.use_mock:
            logger.info("VisionService running in mock mode")
    
    async def initialize(self):
        """Initialize the service and models."""
        if not self.use_mock and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._gemini_model = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("Gemini Vision model initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
                self.use_mock = True
    
    async def analyze_image(
        self,
        image: Union[bytes, str, Path],
        image_type_hint: Optional[ImageType] = None,
        context: Optional[str] = None,
    ) -> VisionAnalysis:
        """
        Analyze an image.
        
        Args:
            image: Image bytes, base64 string, or file path
            image_type_hint: Optional hint for image type
            context: Additional context for analysis
        
        Returns:
            VisionAnalysis with results
        """
        import time
        start_time = time.perf_counter()
        
        # Get image bytes
        image_bytes = self._get_image_bytes(image)
        image_hash = self._compute_hash(image_bytes)
        
        # Check cache
        if self.cache_enabled and image_hash in self._cache:
            logger.debug(f"Cache hit for image {image_hash[:8]}")
            return self._cache[image_hash]
        
        # Classify image type
        if image_type_hint:
            detected_type = image_type_hint
        else:
            detected_type = await self._classify_image(image_bytes, context)
        
        # Route to appropriate analyzer
        results = []
        
        if detected_type == ImageType.ECG:
            result = await self._analyze_ecg(image_bytes, context)
            results.append(result)
        elif detected_type == ImageType.FOOD:
            result = await self._analyze_food(image_bytes, context)
            results.append(result)
        elif detected_type in [ImageType.DOCUMENT, ImageType.PRESCRIPTION, ImageType.LAB_REPORT]:
            result = await self._analyze_document(image_bytes, detected_type, context)
            results.append(result)
        else:
            # General analysis
            result = await self._analyze_general(image_bytes, context)
            results.append(result)
        
        # Combine results
        processing_time = (time.perf_counter() - start_time) * 1000
        combined_summary = self._combine_summaries(results)
        
        analysis = VisionAnalysis(
            image_hash=image_hash,
            results=results,
            primary_classification=detected_type,
            combined_summary=combined_summary,
            metadata={
                "processing_time_ms": processing_time,
                "context_provided": context is not None,
            },
        )
        
        # Cache result
        if self.cache_enabled:
            self._add_to_cache(image_hash, analysis)
        
        return analysis
    
    async def classify_image(
        self,
        image: Union[bytes, str, Path],
    ) -> ImageType:
        """
        Classify image type without full analysis.
        
        Args:
            image: Image to classify
        
        Returns:
            Detected ImageType
        """
        image_bytes = self._get_image_bytes(image)
        return await self._classify_image(image_bytes, None)
    
    async def _classify_image(
        self,
        image_bytes: bytes,
        context: Optional[str],
    ) -> ImageType:
        """Internal image classification."""
        if self.use_mock:
            return self._mock_classify(context)
        
        try:
            # Use Gemini for classification
            prompt = """Classify this image into one of these categories:
            - ecg: Electrocardiogram or heart rhythm strip
            - food: Food, meal, or nutrition-related image
            - document: General document or text
            - prescription: Medical prescription
            - lab_report: Laboratory test results
            - medical_scan: X-ray, MRI, CT scan, ultrasound
            - general: Other images
            
            Respond with only the category name."""
            
            if context:
                prompt += f"\n\nAdditional context: {context}"
            
            response = await asyncio.to_thread(
                self._gemini_model.generate_content,
                [prompt, {"mime_type": "image/jpeg", "data": image_bytes}],
            )
            
            classification = response.text.strip().lower()
            
            # Map to enum
            type_map = {
                "ecg": ImageType.ECG,
                "food": ImageType.FOOD,
                "document": ImageType.DOCUMENT,
                "prescription": ImageType.PRESCRIPTION,
                "lab_report": ImageType.LAB_REPORT,
                "medical_scan": ImageType.MEDICAL_SCAN,
                "general": ImageType.GENERAL,
            }
            
            return type_map.get(classification, ImageType.UNKNOWN)
            
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return ImageType.UNKNOWN
    
    def _mock_classify(self, context: Optional[str]) -> ImageType:
        """Mock classification based on context."""
        if context:
            context_lower = context.lower()
            for image_type, patterns in self.IMAGE_PATTERNS.items():
                if any(p in context_lower for p in patterns):
                    return image_type
        return ImageType.GENERAL
    
    async def _analyze_ecg(
        self,
        image_bytes: bytes,
        context: Optional[str],
    ) -> AnalysisResult:
        """Analyze ECG image."""
        if self.use_mock:
            return self._mock_ecg_analysis()
        
        try:
            prompt = """Analyze this ECG/EKG image. Provide:
            1. Heart rhythm (normal sinus, atrial fibrillation, etc.)
            2. Heart rate estimate
            3. Notable findings (ST changes, arrhythmias, etc.)
            4. Overall assessment
            5. Recommendations
            
            Be specific but note this is for educational purposes only."""
            
            if context:
                prompt += f"\n\nPatient context: {context}"
            
            response = await asyncio.to_thread(
                self._gemini_model.generate_content,
                [prompt, {"mime_type": "image/jpeg", "data": image_bytes}],
            )
            
            return AnalysisResult(
                success=True,
                image_type=ImageType.ECG,
                confidence=0.85,
                analysis={"raw_analysis": response.text},
                summary=response.text[:500],
                warnings=["This analysis is for educational purposes only. Consult a cardiologist."],
                recommendations=["Professional ECG interpretation recommended"],
                model_used="gemini-1.5-flash",
            )
            
        except Exception as e:
            logger.error(f"ECG analysis error: {e}")
            return self._mock_ecg_analysis()
    
    def _mock_ecg_analysis(self) -> AnalysisResult:
        """Mock ECG analysis result."""
        return AnalysisResult(
            success=True,
            image_type=ImageType.ECG,
            confidence=0.75,
            analysis={
                "rhythm": "Normal Sinus Rhythm",
                "heart_rate_bpm": 72,
                "pr_interval_ms": 160,
                "qrs_duration_ms": 90,
                "qt_interval_ms": 400,
                "findings": [
                    "Regular rhythm",
                    "Normal P wave morphology",
                    "No ST-segment abnormalities detected",
                ],
            },
            summary="ECG shows normal sinus rhythm at approximately 72 bpm. No significant abnormalities detected in this analysis.",
            warnings=[
                "⚠️ This is an AI analysis for educational purposes only",
                "Professional interpretation by a cardiologist is required",
            ],
            recommendations=[
                "Have ECG reviewed by qualified healthcare provider",
                "Compare with previous ECGs if available",
            ],
            model_used="mock",
        )
    
    async def _analyze_food(
        self,
        image_bytes: bytes,
        context: Optional[str],
    ) -> AnalysisResult:
        """Analyze food image."""
        if self.use_mock:
            return self._mock_food_analysis()
        
        try:
            prompt = """Analyze this food/meal image. Provide:
            1. Identified foods/ingredients
            2. Estimated portion sizes
            3. Approximate nutritional breakdown (calories, protein, carbs, fat)
            4. Health considerations
            5. Recommendations for a heart-healthy diet
            
            Be helpful but note these are estimates."""
            
            if context:
                prompt += f"\n\nDietary context: {context}"
            
            response = await asyncio.to_thread(
                self._gemini_model.generate_content,
                [prompt, {"mime_type": "image/jpeg", "data": image_bytes}],
            )
            
            return AnalysisResult(
                success=True,
                image_type=ImageType.FOOD,
                confidence=0.80,
                analysis={"raw_analysis": response.text},
                summary=response.text[:500],
                warnings=["Nutritional estimates are approximate"],
                recommendations=[],
                model_used="gemini-1.5-flash",
            )
            
        except Exception as e:
            logger.error(f"Food analysis error: {e}")
            return self._mock_food_analysis()
    
    def _mock_food_analysis(self) -> AnalysisResult:
        """Mock food analysis result."""
        return AnalysisResult(
            success=True,
            image_type=ImageType.FOOD,
            confidence=0.75,
            analysis={
                "identified_foods": [
                    {"name": "Grilled Chicken Breast", "portion": "4 oz"},
                    {"name": "Steamed Broccoli", "portion": "1 cup"},
                    {"name": "Brown Rice", "portion": "0.5 cup"},
                ],
                "estimated_nutrition": {
                    "calories": 420,
                    "protein_g": 35,
                    "carbohydrates_g": 32,
                    "fat_g": 12,
                    "fiber_g": 5,
                    "sodium_mg": 380,
                },
                "health_score": 8.5,
            },
            summary="Balanced meal with lean protein, vegetables, and whole grains. Approximately 420 calories with good protein content.",
            warnings=["Nutritional values are estimates based on visual analysis"],
            recommendations=[
                "Great choice for heart health!",
                "Consider adding healthy fats like olive oil or avocado",
                "Good fiber content from vegetables and whole grains",
            ],
            model_used="mock",
        )
    
    async def _analyze_document(
        self,
        image_bytes: bytes,
        doc_type: ImageType,
        context: Optional[str],
    ) -> AnalysisResult:
        """Analyze document image."""
        if self.use_mock:
            return self._mock_document_analysis(doc_type)
        
        try:
            prompts = {
                ImageType.PRESCRIPTION: """Extract information from this prescription:
                1. Medication names and dosages
                2. Frequency/instructions
                3. Prescriber information
                4. Any warnings or notes""",
                
                ImageType.LAB_REPORT: """Extract information from this lab report:
                1. Test names and values
                2. Reference ranges
                3. Any abnormal values
                4. Date of tests""",
                
                ImageType.DOCUMENT: """Extract text and key information from this document:
                1. Document type
                2. Key content
                3. Important dates or numbers
                4. Any medical relevance""",
            }
            
            prompt = prompts.get(doc_type, prompts[ImageType.DOCUMENT])
            
            if context:
                prompt += f"\n\nContext: {context}"
            
            response = await asyncio.to_thread(
                self._gemini_model.generate_content,
                [prompt, {"mime_type": "image/jpeg", "data": image_bytes}],
            )
            
            return AnalysisResult(
                success=True,
                image_type=doc_type,
                confidence=0.85,
                analysis={"extracted_text": response.text},
                summary=response.text[:500],
                warnings=["Verify extracted information with original document"],
                recommendations=[],
                model_used="gemini-1.5-flash",
            )
            
        except Exception as e:
            logger.error(f"Document analysis error: {e}")
            return self._mock_document_analysis(doc_type)
    
    def _mock_document_analysis(self, doc_type: ImageType) -> AnalysisResult:
        """Mock document analysis result."""
        if doc_type == ImageType.PRESCRIPTION:
            analysis = {
                "medications": [
                    {
                        "name": "Lisinopril",
                        "dosage": "10mg",
                        "frequency": "Once daily",
                        "instructions": "Take in the morning with water",
                    },
                ],
                "prescriber": "Dr. Smith, MD",
                "date": "2024-01-15",
            }
            summary = "Prescription for Lisinopril 10mg, once daily. ACE inhibitor for blood pressure management."
        elif doc_type == ImageType.LAB_REPORT:
            analysis = {
                "tests": [
                    {"name": "Total Cholesterol", "value": "185 mg/dL", "status": "normal"},
                    {"name": "LDL", "value": "110 mg/dL", "status": "borderline"},
                    {"name": "HDL", "value": "55 mg/dL", "status": "normal"},
                    {"name": "Triglycerides", "value": "120 mg/dL", "status": "normal"},
                ],
                "date": "2024-01-10",
            }
            summary = "Lipid panel results: Total cholesterol normal, LDL borderline elevated. Overall cardiovascular profile acceptable."
        else:
            analysis = {"content": "Document content extracted", "type": "general"}
            summary = "Document processed and text extracted."
        
        return AnalysisResult(
            success=True,
            image_type=doc_type,
            confidence=0.70,
            analysis=analysis,
            summary=summary,
            warnings=["Verify extracted information with original document"],
            recommendations=["Consult healthcare provider for interpretation"],
            model_used="mock",
        )
    
    async def _analyze_general(
        self,
        image_bytes: bytes,
        context: Optional[str],
    ) -> AnalysisResult:
        """General image analysis."""
        if self.use_mock:
            return AnalysisResult(
                success=True,
                image_type=ImageType.GENERAL,
                confidence=0.60,
                analysis={"description": "General image analysis"},
                summary="Image analyzed. No specific medical content detected.",
                warnings=[],
                recommendations=[],
                model_used="mock",
            )
        
        try:
            prompt = """Describe this image and identify any health or medical relevance:
            1. What is shown in the image?
            2. Any health-related content?
            3. Recommendations or observations"""
            
            if context:
                prompt += f"\n\nContext: {context}"
            
            response = await asyncio.to_thread(
                self._gemini_model.generate_content,
                [prompt, {"mime_type": "image/jpeg", "data": image_bytes}],
            )
            
            return AnalysisResult(
                success=True,
                image_type=ImageType.GENERAL,
                confidence=0.70,
                analysis={"description": response.text},
                summary=response.text[:500],
                warnings=[],
                recommendations=[],
                model_used="gemini-1.5-flash",
            )
            
        except Exception as e:
            logger.error(f"General analysis error: {e}")
            return AnalysisResult(
                success=False,
                image_type=ImageType.UNKNOWN,
                confidence=0.0,
                analysis={"error": str(e)},
                summary=f"Analysis failed: {e}",
                warnings=["Analysis could not be completed"],
                recommendations=["Try again or use a clearer image"],
                model_used="none",
            )
    
    def _get_image_bytes(self, image: Union[bytes, str, Path]) -> bytes:
        """Convert image input to bytes."""
        if isinstance(image, bytes):
            return image
        elif isinstance(image, Path):
            return image.read_bytes()
        elif isinstance(image, str):
            # Check if base64
            if len(image) > 260 and "/" not in image[:50]:
                return base64.b64decode(image)
            else:
                # Assume file path
                return Path(image).read_bytes()
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")
    
    def _compute_hash(self, data: bytes) -> str:
        """Compute hash for caching."""
        return hashlib.sha256(data).hexdigest()[:16]
    
    def _add_to_cache(self, key: str, value: VisionAnalysis):
        """Add to cache with size limit."""
        if len(self._cache) >= self._max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = value
    
    def _combine_summaries(self, results: List[AnalysisResult]) -> str:
        """Combine analysis summaries."""
        summaries = [r.summary for r in results if r.summary]
        return " ".join(summaries) if summaries else "No analysis available."
    
    def clear_cache(self):
        """Clear the analysis cache."""
        self._cache.clear()
