"""
Multimodal Medical Document Processor.

Combines OCR output with visual analysis for scanned documents.
Uses MedGemma multimodal capabilities when available.

Best for:
- Scanned prescriptions (handwritten portions)
- Lab reports with graphs/charts
- ECG printouts
- Medical imaging reports with images
"""

import os
import logging
import base64
import aiohttp
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MultimodalAnalysisResult:
    """Result from multimodal document analysis."""
    ocr_text: str
    visual_analysis: Dict[str, Any]
    combined_extraction: Dict[str, Any]
    confidence: float
    image_quality: str  # "good", "fair", "poor"
    recommendations: List[str]


class MultimodalMedicalProcessor:
    """
    Process medical documents using both text and vision analysis.
    
    Combines:
    - OCR text extraction
    - Visual layout analysis
    - MedGemma multimodal understanding
    
    This is particularly useful for:
    - Documents with handwritten portions
    - Lab reports with graphs or charts
    - Medical images with annotations
    - Forms with complex layouts
    
    Example:
        processor = MultimodalMedicalProcessor()
        result = await processor.process_document(
            image_path="scan.jpg",
            ocr_text="extracted text...",
            document_type="prescription"
        )
    """
    
    def __init__(
        self,
        medgemma_service=None,
        vision_model: Optional[str] = None
    ):
        """
        Initialize multimodal processor.
        
        Args:
            medgemma_service: MedGemmaService instance for AI processing
            vision_model: Vision model to use (defaults to gemini-pro-vision)
        """
        self.medgemma_service = medgemma_service
        self.vision_model = vision_model or os.getenv(
            'VISION_MODEL', 
            'gemini-pro-vision'
        )
        self.api_key = os.getenv('GOOGLE_AI_API_KEY')
        self.base_url = os.getenv(
            'GOOGLE_AI_BASE_URL',
            'https://generativelanguage.googleapis.com/v1beta'
        )
        
        # Mock mode when no API key
        self.mock_mode = not self.api_key
        
        if self.mock_mode:
            logger.info("Multimodal processor initialized in MOCK mode")
        else:
            logger.info(f"Multimodal processor initialized: {self.vision_model}")
    
    async def process_document(
        self,
        image_path: str,
        ocr_text: str,
        document_type: str = "unknown",
        extraction_schema: Optional[Dict[str, Any]] = None
    ) -> MultimodalAnalysisResult:
        """
        Process a medical document with both text and visual analysis.
        
        Args:
            image_path: Path to the document image
            ocr_text: Text extracted from OCR
            document_type: Type of document (lab_report, prescription, etc.)
            extraction_schema: Optional schema for data extraction
        
        Returns:
            MultimodalAnalysisResult with combined analysis
        """
        # Step 1: Analyze image visually
        visual_analysis = await self._analyze_image_visually(image_path, document_type)
        
        # Step 2: Combined extraction using both text and image
        combined_extraction = await self._combined_extraction(
            image_path=image_path,
            ocr_text=ocr_text,
            visual_analysis=visual_analysis,
            schema=extraction_schema
        )
        
        # Step 3: Assess quality and confidence
        image_quality = self._assess_image_quality(image_path, visual_analysis)
        
        # Calculate confidence based on OCR text length and visual analysis
        confidence = self._calculate_confidence(ocr_text, visual_analysis, image_quality)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(image_quality, confidence)
        
        return MultimodalAnalysisResult(
            ocr_text=ocr_text,
            visual_analysis=visual_analysis,
            combined_extraction=combined_extraction,
            confidence=confidence,
            image_quality=image_quality,
            recommendations=recommendations
        )
    
    async def _analyze_image_visually(
        self,
        image_path: str,
        document_type: str
    ) -> Dict[str, Any]:
        """
        Analyze document image for visual elements.
        
        Identifies:
        - Document layout
        - Handwritten vs printed text
        - Tables and charts
        - Stamps and signatures
        - Quality issues
        """
        if self.mock_mode:
            return {
                "layout_type": "report",
                "has_tables": False,
                "has_handwriting": False,
                "has_stamps_signatures": False,
                "has_charts": False,
                "sections_identified": ["header", "body"],
                "quality_issues": []
            }
        
        try:
            # Read and encode image
            image_data = self._encode_image(image_path)
            if not image_data:
                return {}
            
            prompt = f"""Analyze this medical document image ({document_type}).

Identify:
1. Document layout (sections, columns, tables)
2. Any handwritten portions
3. Stamps, signatures, or official marks
4. Letterhead/hospital logo
5. Any charts, graphs, or images within the document
6. Areas that might be hard to read

Return JSON:
{{
  "layout_type": "form|report|prescription|other",
  "has_tables": true/false,
  "has_handwriting": true/false,
  "has_stamps_signatures": true/false,
  "has_charts": true/false,
  "sections_identified": ["header", "patient_info", "results"],
  "quality_issues": ["blurry_area", "skewed", "low_contrast"]
}}
"""
            
            # Call vision model
            response = await self._call_vision_model(image_data, prompt)
            
            # Parse response
            import json
            try:
                if "```json" in response:
                    start = response.find("```json") + 7
                    end = response.find("```", start)
                    response = response[start:end].strip()
                return json.loads(response)
            except:
                return {"raw_analysis": response}
                
        except Exception as e:
            logger.error(f"Visual analysis failed: {e}")
            return {}
    
    async def _combined_extraction(
        self,
        image_path: str,
        ocr_text: str,
        visual_analysis: Dict[str, Any],
        schema: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Perform combined extraction using image and text.
        
        Uses both the original image and OCR text for better accuracy,
        especially for handwritten portions or complex layouts.
        """
        if self.mock_mode:
            return {
                "source": "mock",
                "extracted_fields": {},
                "handwritten_content": None,
                "tables": []
            }
        
        try:
            image_data = self._encode_image(image_path)
            if not image_data:
                return {"error": "Could not read image"}
            
            schema_instruction = ""
            if schema:
                import json
                schema_instruction = f"""
Extract data according to this schema:
```json
{json.dumps(schema, indent=2)}
```
"""
            
            prompt = f"""You are analyzing a medical document. I have both the image and OCR-extracted text.

OCR Text:
{ocr_text[:2000]}

Visual Analysis:
{visual_analysis}

{schema_instruction}

Tasks:
1. Verify and correct the OCR text using the image
2. Extract any handwritten portions that OCR might have missed
3. Extract data from any tables or structured sections
4. Identify any values that differ between OCR and visual inspection

Return JSON:
{{
  "verified_text": "corrected OCR text if needed",
  "extracted_fields": {{}},
  "handwritten_content": "any handwritten text found",
  "tables": [],
  "discrepancies": []
}}
"""
            
            response = await self._call_vision_model(image_data, prompt)
            
            import json
            try:
                if "```json" in response:
                    start = response.find("```json") + 7
                    end = response.find("```", start)
                    response = response[start:end].strip()
                return json.loads(response)
            except:
                return {"raw_extraction": response}
                
        except Exception as e:
            logger.error(f"Combined extraction failed: {e}")
            return {"error": str(e)}
    
    def _encode_image(self, image_path: str) -> Optional[str]:
        """Read and base64 encode an image file."""
        try:
            path = Path(image_path)
            if not path.exists():
                logger.error(f"Image file not found: {image_path}")
                return None
            
            with open(path, 'rb') as f:
                image_bytes = f.read()
            
            return base64.standard_b64encode(image_bytes).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return None
    
    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type from file extension."""
        ext = Path(file_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.webp': 'image/webp'
        }
        return mime_types.get(ext, 'image/jpeg')
    
    async def _call_vision_model(self, image_data: str, prompt: str) -> str:
        """Call the vision model API."""
        if not self.api_key:
            raise ValueError("API key not configured")
        
        url = f"{self.base_url}/models/{self.vision_model}:generateContent"
        
        headers = {
            "Content-Type": "application/json",
        }
        
        params = {
            "key": self.api_key
        }
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_data
                            }
                        },
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.8,
                "maxOutputTokens": 4096
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, params=params, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Vision API call failed: {response.status} - {error_text}")
                
                result = await response.json()
                
                candidates = result.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                
                raise RuntimeError("No content in vision API response")
    
    def _assess_image_quality(
        self,
        image_path: str,
        visual_analysis: Dict[str, Any]
    ) -> str:
        """Assess overall image quality."""
        quality_issues = visual_analysis.get("quality_issues", [])
        
        if not quality_issues:
            return "good"
        elif len(quality_issues) <= 2:
            return "fair"
        else:
            return "poor"
    
    def _calculate_confidence(
        self,
        ocr_text: str,
        visual_analysis: Dict[str, Any],
        image_quality: str
    ) -> float:
        """Calculate confidence score for the extraction."""
        base_confidence = 0.7
        
        # Adjust based on text length
        if len(ocr_text) > 500:
            base_confidence += 0.1
        elif len(ocr_text) < 100:
            base_confidence -= 0.1
        
        # Adjust based on image quality
        quality_adjustments = {"good": 0.1, "fair": 0, "poor": -0.15}
        base_confidence += quality_adjustments.get(image_quality, 0)
        
        # Adjust based on visual analysis
        if visual_analysis.get("has_handwriting"):
            base_confidence -= 0.1  # Handwriting is harder to extract
        if visual_analysis.get("has_tables"):
            base_confidence -= 0.05  # Tables need more careful parsing
        
        return max(0.3, min(0.95, base_confidence))
    
    def _generate_recommendations(
        self,
        image_quality: str,
        confidence: float
    ) -> List[str]:
        """Generate recommendations based on quality."""
        recommendations = []
        
        if image_quality == "poor":
            recommendations.append("Consider rescanning the document with better lighting")
            recommendations.append("Ensure document is flat and not skewed")
        
        if confidence < 0.6:
            recommendations.append("Manual verification strongly recommended")
            recommendations.append("Some extracted values may be inaccurate")
        elif confidence < 0.8:
            recommendations.append("Review extraction results before use")
        
        return recommendations


async def process_medical_image(
    image_path: str,
    ocr_text: str,
    document_type: str = "unknown"
) -> MultimodalAnalysisResult:
    """
    Convenience function for processing a medical document image.
    
    Args:
        image_path: Path to document image
        ocr_text: OCR-extracted text
        document_type: Type of document
        
    Returns:
        MultimodalAnalysisResult
    """
    processor = MultimodalMedicalProcessor()
    return await processor.process_document(image_path, ocr_text, document_type)
