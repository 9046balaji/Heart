"""
Vision Service for image analysis using Gemini Vision API.

Provides image analysis capabilities for medical images including:
- ECG/EKG strips
- Medical reports
- Food photos
- Prescription labels

Phase 4: Security & Privacy - PII Detection & Blurring
"""

import os
import logging
import re
import io
from typing import Dict, Any, Optional, List
import base64

logger = logging.getLogger(__name__)


class VisionService:
    """
    Vision analysis service using Google Gemini Vision API.
    
    Features:
    - Image analysis with Gemini Vision
    - PII detection using OCR
    - Automatic PII blurring for HIPAA compliance
    
    Example:
        vision = VisionService()
        
        # Standard analysis
        result = await vision.analyze_image(
            image_base64="data:image/jpeg;base64,...",
            prompt="Describe this ECG strip"
        )
        
        # With PII protection
        result = await vision.process_and_analyze(
            image_data=image_bytes,
            prompt="Analyze this medical document",
            enable_pii_protection=True
        )
    """
    
    # PII Detection Patterns (HIPAA compliant)
    PII_PATTERNS = {
        "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        "mrn": r'\b(MRN|Medical Record|Patient ID|Record #)[\s:]*\d+\b',
        "phone": r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "date_of_birth": r'\b(DOB|Date of Birth)[\s:]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
    }
    
    def __init__(self):
        """Initialize vision service with Gemini API."""
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model = "gemini-1.5-flash"
        
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not set - vision analysis will fail")
        
        # Check if PII detection is enabled
        self.pii_detection_enabled = os.getenv("PII_DETECTION_ENABLED", "true").lower() == "true"
        
        # Tesseract path for Windows
        tesseract_path = os.getenv("TESSERACT_PATH")
        if tesseract_path and os.name == 'nt':
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                logger.info(f"Tesseract OCR configured: {tesseract_path}")
            except ImportError:
                logger.warning("pytesseract not installed - PII detection unavailable")
                self.pii_detection_enabled = False
    
    async def detect_pii(self, image) -> List[Dict]:
        """
        Use OCR to detect PII in image.
        
        Args:
            image: PIL Image object
        
        Returns:
            List of PII detections with bounding boxes
        """
        if not self.pii_detection_enabled:
            logger.warning("PII detection disabled")
            return []
        
        try:
            import pytesseract
        except ImportError:
            logger.error("pytesseract not installed - cannot detect PII")
            return []
        
        try:
            # Run OCR to get text and positions
            ocr_data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT
            )
            
            pii_detections = []
            
            # Check each detected text block for PII
            for i, text in enumerate(ocr_data['text']):
                if not text.strip():
                    continue
                
                # Check against PII patterns
                for pii_type, pattern in self.PII_PATTERNS.items():
                    if re.search(pattern, text, re.IGNORECASE):
                        pii_detections.append({
                            "type": pii_type,
                            "text": text,
                            "bbox": {
                                "x": ocr_data['left'][i],
                                "y": ocr_data['top'][i],
                                "width": ocr_data['width'][i],
                                "height": ocr_data['height'][i]
                            },
                            "confidence": ocr_data['conf'][i]
                        })
                        logger.warning(f"PII detected: {pii_type} at ({ocr_data['left'][i]}, {ocr_data['top'][i]})")
            
            return pii_detections
            
        except Exception as e:
            logger.error(f"PII detection failed: {e}")
            return []
    
    async def blur_pii(self, image, pii_detections: List[Dict]):
        """
        Blur detected PII regions in image.
        
        Args:
            image: PIL Image object
            pii_detections: List of PII detections from detect_pii()
        
        Returns:
            PIL Image with PII regions blurred
        """
        if not pii_detections:
            return image
        
        try:
            from PIL import ImageFilter
            
            img_copy = image.copy()
            
            for detection in pii_detections:
                bbox = detection['bbox']
                
                # Extract region
                region = img_copy.crop((
                    bbox['x'],
                    bbox['y'],
                    bbox['x'] + bbox['width'],
                    bbox['y'] + bbox['height']
                ))
                
                # Apply strong Gaussian blur
                blurred = region.filter(ImageFilter.GaussianBlur(radius=15))
                
                # Paste back
                img_copy.paste(blurred, (bbox['x'], bbox['y']))
                
                logger.info(f"Blurred {detection['type']} at ({bbox['x']}, {bbox['y']})")
            
            return img_copy
            
        except Exception as e:
            logger.error(f"PII blurring failed: {e}")
            return image
    
    async def process_and_analyze(
        self,
        image_data: bytes,
        prompt: str = "Analyze this medical image",
        enable_pii_protection: bool = True
    ) -> Dict:
        """
        Process image with optional PII protection before analysis.
        
        Workflow:
        1. Decode image
        2. Detect PII with OCR (if enabled)
        3. Blur PII if found
        4. Send to Gemini Vision
        5. Return analysis + PII report
        
        Args:
            image_data: Raw image bytes
            prompt: Analysis prompt for Gemini
            enable_pii_protection: Whether to detect and blur PII
        
        Returns:
            {
                "analysis": "...",
                "privacy": {
                    "pii_detected": bool,
                    "pii_count": int,
                    "pii_types": ["ssn", "mrn", ...],
                    "protection_enabled": bool
                }
            }
        """
        try:
            from PIL import Image
            
            # Decode image
            image = Image.open(io.BytesIO(image_data))
            
            pii_detections = []
            if enable_pii_protection and self.pii_detection_enabled:
                # Detect PII
                pii_detections = await self.detect_pii(image)
                
                if pii_detections:
                    logger.warning(f"Detected {len(pii_detections)} PII instances, blurring")
                    image = await self.blur_pii(image, pii_detections)
            
            # Convert back to base64 for Gemini
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            
            # Send to Gemini Vision
            analysis = await self.analyze_image(image_base64, prompt)
            
            return {
                "analysis": analysis,
                "privacy": {
                    "pii_detected": len(pii_detections) > 0,
                    "pii_count": len(pii_detections),
                    "pii_types": list(set(d['type'] for d in pii_detections)),
                    "protection_enabled": enable_pii_protection
                }
            }
            
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise
    
    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        content_type: str = "medical"
    ) -> str:
        """
        Analyze image with Gemini Vision API.
        
        Args:
            image_base64: Base64-encoded image (with or without data URI prefix)
            prompt: Analysis prompt
            content_type: Type of content ("medical", "nutrition", "general")
        
        Returns:
            Analysis text from Gemini
        
        Raises:
            ValueError: If API key is missing
            Exception: If API call fails
        """
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not configured")
        
        try:
            # Use langchain_google_genai for vision
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage
            
            # Initialize model
            model = ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=self.api_key,
                convert_system_message_to_human=True
            )
            
            # Prepare image data
            # Remove data URI prefix if present
            if ',' in image_base64 and image_base64.startswith('data:'):
                image_data = image_base64.split(',', 1)[1]
            else:
                image_data = image_base64
            
            # Create message with image
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{image_data}"
                    }
                ]
            )
            
            # Call API
            response = await model.ainvoke([message])
            
            # Extract text from response
            result_text = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"Vision analysis completed ({len(result_text)} chars)")
            
            return result_text
        
        except ImportError:
            logger.error("langchain_google_genai not available")
            raise ValueError("Vision service dependencies not installed")
        
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            raise


# Convenience function
async def analyze_image(image_base64: str, prompt: str) -> str:
    """
    Quick image analysis function.
    
    Args:
        image_base64: Base64-encoded image
        prompt: Analysis prompt
    
    Returns:
        Analysis text
    """
    service = VisionService()
    return await service.analyze_image(image_base64, prompt)
