"""
Document Scanning Package for Medical Documents.

This package provides intelligent medical document ingestion and structuring:
- Document upload and validation
- OCR text extraction (Tesseract, Google Vision, AWS Textract)
- Medical document classification (lab reports, prescriptions, bills, discharge summaries)
- Schema-driven data extraction
- Confidence scoring and uncertainty flagging

Usage:
    from document_scanning import DocumentIngestionService, OCREngineFactory, MedicalDocumentClassifier

    # Ingest a document
    ingestion = DocumentIngestionService()
    result = ingestion.ingest_document(file, filename, user_id)

    # Extract text via OCR
    ocr = OCREngineFactory().get_engine()
    text_result = ocr.extract_text(file_path)

    # Classify document type
    classifier = MedicalDocumentClassifier()
    classification = classifier.classify(text)
"""

from .ingestion import DocumentIngestionService, DocumentType, MedicalDocumentCategory

from .ocr_engine import (
    OCREngineFactory,
    OCRResult,
    OCRProvider,
    BaseOCREngine,
    TesseractOCREngine,
    GoogleVisionOCREngine,
    AWSTextractEngine,
)

from .classifier import (
    MedicalDocumentClassifier,
    DocumentCategory,
    ClassificationResult,
)

__all__ = [
    # Ingestion
    "DocumentIngestionService",
    "DocumentType",
    "MedicalDocumentCategory",
    # OCR
    "OCREngineFactory",
    "OCRResult",
    "OCRProvider",
    "BaseOCREngine",
    "TesseractOCREngine",
    "GoogleVisionOCREngine",
    "AWSTextractEngine",
    # Classification
    "MedicalDocumentClassifier",
    "DocumentCategory",
    "ClassificationResult",
]
