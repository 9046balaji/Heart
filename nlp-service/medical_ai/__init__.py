"""
Medical AI Package for Document Understanding.

This package provides medical document understanding using MedGemma:
- Medical entity extraction
- Patient-friendly summarization
- Terminology normalization
- Multimodal document processing

Usage:
    from medical_ai import MedGemmaService, MedicalTerminologyNormalizer

    # Use MedGemma for extraction
    service = MedGemmaService()
    result = await service.extract_medical_entities(text, "lab_report")

    # Normalize medical terminology
    normalizer = MedicalTerminologyNormalizer()
    normalized, mappings = normalizer.normalize_text(text)
"""

from .services.medgemma_service import (
    MedGemmaService,
    MedGemmaModel,
    ExtractionResult,
    SummaryResult,
)

from .services.terminology_normalizer import MedicalTerminologyNormalizer, TermMapping

from .services.multimodal_processor import (
    MultimodalMedicalProcessor,
    MultimodalAnalysisResult,
)

__all__ = [
    # MedGemma Service
    "MedGemmaService",
    "MedGemmaModel",
    "ExtractionResult",
    "SummaryResult",
    # Terminology
    "MedicalTerminologyNormalizer",
    "TermMapping",
    # Multimodal
    "MultimodalMedicalProcessor",
    "MultimodalAnalysisResult",
]
