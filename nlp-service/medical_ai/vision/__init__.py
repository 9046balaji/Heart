"""
Vision Package.

Provides multimodal vision capabilities for medical image analysis,
document processing, and visual content understanding.

Components:
- vision_service: Core vision analysis service
- ecg_analyzer: ECG image analysis
- food_recognition: Food/meal image analysis
- document_scanner: Medical document OCR
"""

from .vision_service import (
    VisionService,
    VisionAnalysis,
    ImageType,
    AnalysisResult,
)
from .ecg_analyzer import (
    ECGAnalyzer,
    ECGAnalysis,
    ECGRhythm,
)
from .food_recognition import (
    FoodRecognitionService,
    FoodAnalysis,
    NutritionInfo,
)

# Document scanning is available from the document_scanning package
# Import from parent package for convenience
from document_scanning import (
    DocumentIngestionService as DocumentScanner,
    DocumentType as ScannedDocumentType,
    MedicalDocumentCategory as DocumentType,
)

# Alias for compatibility
ScannedDocument = DocumentScanner  # Use the ingestion service

__all__ = [
    # Core
    "VisionService",
    "VisionAnalysis",
    "ImageType",
    "AnalysisResult",
    # ECG
    "ECGAnalyzer",
    "ECGAnalysis",
    "ECGRhythm",
    # Food
    "FoodRecognitionService",
    "FoodAnalysis",
    "NutritionInfo",
    # Document (from document_scanning package)
    "DocumentScanner",
    "ScannedDocument",
    "DocumentType",
    "ScannedDocumentType",
]
