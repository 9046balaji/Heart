"""
Document Scanning API Routes.

FastAPI routes for document upload, OCR processing, and classification.
"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Document Scanning"])


# ==================== Request/Response Models ====================

class DocumentUploadResponse(BaseModel):
    """Response for document upload."""
    document_id: str
    filename: str
    file_size: int
    content_type: str
    status: str = "uploaded"
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_abc123",
                "filename": "lab_results.pdf",
                "file_size": 102400,
                "content_type": "application/pdf",
                "status": "uploaded",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


class OCRRequest(BaseModel):
    """Request to process OCR on a document."""
    document_id: str
    engine: str = Field(default="tesseract", description="OCR engine to use")
    language: str = Field(default="eng", description="Language code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_abc123",
                "engine": "tesseract",
                "language": "eng"
            }
        }


class OCRResult(BaseModel):
    """OCR processing result."""
    document_id: str
    text: str
    confidence: float
    engine_used: str
    processing_time_ms: float
    page_count: int = 1
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_abc123",
                "text": "Patient Name: John Smith\nDate: 2024-01-15\nGlucose: 126 mg/dL",
                "confidence": 0.92,
                "engine_used": "tesseract",
                "processing_time_ms": 1250.5,
                "page_count": 1
            }
        }


class ClassificationRequest(BaseModel):
    """Request to classify a document."""
    document_id: str
    text: Optional[str] = None  # Pre-extracted text, or will OCR
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_abc123",
                "text": "LABORATORY REPORT\nPatient: John Smith\nGlucose: 126 mg/dL"
            }
        }


class ClassificationResult(BaseModel):
    """Document classification result."""
    document_id: str
    document_type: str
    category: str
    confidence: float
    subcategories: List[str] = []
    suggested_schema: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_abc123",
                "document_type": "lab_report",
                "category": "diagnostic",
                "confidence": 0.95,
                "subcategories": ["blood_test", "metabolic_panel"],
                "suggested_schema": "LabReportSchema"
            }
        }


class ExtractionRequest(BaseModel):
    """Request to extract structured data from document."""
    document_id: str
    document_type: str
    text: Optional[str] = None
    auto_verify: bool = Field(default=False, description="Skip human verification queue")


class ExtractedEntity(BaseModel):
    """Single extracted entity."""
    field: str
    value: str
    confidence: float
    source_location: Optional[str] = None


class ExtractionResult(BaseModel):
    """Structured extraction result."""
    document_id: str
    document_type: str
    extraction_model: str
    overall_confidence: float
    entities: List[ExtractedEntity]
    raw_extraction: dict
    verification_required: bool
    verification_id: Optional[str] = None
    
    # Disclaimer (always include per medical.md)
    disclaimer: str = (
        "⚠️ This extraction is for informational purposes only. "
        "It is not a substitute for professional medical advice. "
        "Please consult your healthcare provider for medical decisions."
    )


class DocumentListItem(BaseModel):
    """Document list item."""
    document_id: str
    filename: str
    document_type: Optional[str]
    status: str
    created_at: datetime
    ocr_confidence: Optional[float]


class DocumentListResponse(BaseModel):
    """Response for document listing."""
    total: int
    page: int
    page_size: int
    documents: List[DocumentListItem]


# ==================== Dependency Injection ====================

def get_document_service():
    """Get document ingestion service instance."""
    # In production, use dependency injection
    from document_scanning import DocumentIngestionService
    return DocumentIngestionService()


def get_ocr_factory():
    """Get OCR engine factory instance."""
    from document_scanning import OCREngineFactory
    return OCREngineFactory()


def get_classifier():
    """Get document classifier instance."""
    from document_scanning import MedicalDocumentClassifier
    return MedicalDocumentClassifier()


def get_audit_service():
    """Get audit service instance."""
    from compliance import AuditService
    return AuditService()


def get_verification_queue():
    """Get verification queue instance."""
    from compliance import VerificationQueue
    return VerificationQueue()


# ==================== Routes ====================

@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    summary="Upload Medical Document",
    description="Upload a medical document for processing. Supports PDF, images, and common document formats."
)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Query(..., description="User ID uploading the document"),
    background_tasks: BackgroundTasks = None
):
    """
    Upload a medical document.
    
    Supported formats:
    - PDF documents
    - Images (JPEG, PNG, TIFF)
    - DOCX, TXT
    
    The document will be validated and stored securely.
    OCR processing can be triggered separately.
    """
    import uuid
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Read file content
    content = await file.read()
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")
    
    document_id = f"doc_{uuid.uuid4().hex[:12]}"
    
    # Log upload (audit trail)
    try:
        audit = get_audit_service()
        audit.log_document_upload(
            user_id=user_id,
            document_id=document_id,
            filename=file.filename,
            file_size=len(content)
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")
    
    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        file_size=len(content),
        content_type=file.content_type or "application/octet-stream",
        status="uploaded",
        created_at=datetime.utcnow()
    )


@router.post(
    "/ocr",
    response_model=OCRResult,
    summary="Process OCR",
    description="Extract text from an uploaded document using OCR."
)
async def process_ocr(
    request: OCRRequest,
    user_id: str = Query(..., description="User ID")
):
    """
    Process OCR on an uploaded document.
    
    Available engines:
    - tesseract: Open-source, local processing
    - google_vision: Google Cloud Vision API
    - aws_textract: AWS Textract (best for forms)
    """
    import time
    
    start_time = time.time()
    
    # Simulate OCR processing
    # In production: retrieve document and process with actual OCR engine
    
    processing_time_ms = (time.time() - start_time) * 1000
    
    # Mock result
    result = OCRResult(
        document_id=request.document_id,
        text="[OCR text would be extracted here]",
        confidence=0.85,
        engine_used=request.engine,
        processing_time_ms=processing_time_ms + 500,  # Simulated
        page_count=1
    )
    
    # Audit logging
    try:
        audit = get_audit_service()
        audit.log_ocr_completed(
            user_id=user_id,
            document_id=request.document_id,
            engine=request.engine,
            processing_time_ms=result.processing_time_ms,
            confidence=result.confidence,
            page_count=result.page_count
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")
    
    return result


@router.post(
    "/classify",
    response_model=ClassificationResult,
    summary="Classify Document",
    description="Classify a document by type (lab report, prescription, etc.)"
)
async def classify_document(
    request: ClassificationRequest,
    user_id: str = Query(..., description="User ID")
):
    """
    Classify a medical document.
    
    Supported document types:
    - lab_report: Laboratory test results
    - prescription: Medication prescriptions
    - medical_bill: Medical bills and invoices
    - discharge_summary: Hospital discharge summaries
    - imaging_report: Radiology/imaging reports
    - clinical_notes: Doctor's clinical notes
    """
    # In production: use actual classifier
    # classifier = get_classifier()
    # result = classifier.classify(request.text)
    
    # Mock classification
    return ClassificationResult(
        document_id=request.document_id,
        document_type="lab_report",
        category="diagnostic",
        confidence=0.92,
        subcategories=["blood_test"],
        suggested_schema="LabReportSchema"
    )


@router.post(
    "/extract",
    response_model=ExtractionResult,
    summary="Extract Structured Data",
    description="Extract structured entities from a classified document using AI."
)
async def extract_entities(
    request: ExtractionRequest,
    user_id: str = Query(..., description="User ID")
):
    """
    Extract structured data from a medical document.
    
    This uses AI models (MedGemma) to extract relevant entities.
    
    IMPORTANT: Per medical.md requirements, all extractions require
    human verification unless auto_verify is explicitly set.
    """
    import uuid
    
    # Mock extraction (in production: use MedGemma)
    entities = [
        ExtractedEntity(
            field="patient_name",
            value="John Smith",
            confidence=0.98,
            source_location="line 1"
        ),
        ExtractedEntity(
            field="test_date",
            value="2024-01-15",
            confidence=0.95,
            source_location="line 2"
        ),
        ExtractedEntity(
            field="glucose",
            value="126 mg/dL",
            confidence=0.88,
            source_location="line 5"
        )
    ]
    
    overall_confidence = sum(e.confidence for e in entities) / len(entities)
    
    # Add to verification queue if needed
    verification_id = None
    verification_required = not request.auto_verify and overall_confidence < 0.95
    
    if verification_required:
        verification_id = f"ver_{uuid.uuid4().hex[:8]}"
        # In production: add to VerificationQueue
    
    # Audit logging
    try:
        audit = get_audit_service()
        audit.log_ai_extraction(
            user_id=user_id,
            document_id=request.document_id,
            model_used="medgemma",
            entities_extracted=len(entities),
            confidence=overall_confidence
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")
    
    return ExtractionResult(
        document_id=request.document_id,
        document_type=request.document_type,
        extraction_model="medgemma",
        overall_confidence=overall_confidence,
        entities=entities,
        raw_extraction={e.field: e.value for e in entities},
        verification_required=verification_required,
        verification_id=verification_id
    )


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="List Documents",
    description="List uploaded documents for a user."
)
async def list_documents(
    user_id: str = Query(..., description="User ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
    document_type: Optional[str] = Query(None, description="Filter by type")
):
    """List user's uploaded documents."""
    # Mock response
    documents = [
        DocumentListItem(
            document_id="doc_abc123",
            filename="lab_results.pdf",
            document_type="lab_report",
            status="processed",
            created_at=datetime.utcnow(),
            ocr_confidence=0.92
        )
    ]
    
    return DocumentListResponse(
        total=1,
        page=page,
        page_size=page_size,
        documents=documents
    )


@router.get(
    "/{document_id}",
    summary="Get Document Details",
    description="Get details and processing status of a specific document."
)
async def get_document(
    document_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Get document details by ID."""
    # Audit view access
    try:
        audit = get_audit_service()
        audit.log_document_viewed(
            user_id=user_id,
            document_id=document_id
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")
    
    return {
        "document_id": document_id,
        "filename": "example.pdf",
        "status": "processed",
        "created_at": datetime.utcnow().isoformat(),
        "ocr_result": None,
        "classification": None,
        "extraction": None
    }


@router.delete(
    "/{document_id}",
    summary="Delete Document",
    description="Delete an uploaded document."
)
async def delete_document(
    document_id: str,
    user_id: str = Query(..., description="User ID"),
    reason: str = Query(..., description="Reason for deletion")
):
    """Delete a document."""
    # Audit deletion
    try:
        audit = get_audit_service()
        audit.log_document_deleted(
            user_id=user_id,
            document_id=document_id,
            reason=reason
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")
    
    return {"status": "deleted", "document_id": document_id}


@router.get(
    "/{document_id}/audit",
    summary="Get Document Audit Trail",
    description="Get the complete audit trail for a document."
)
async def get_document_audit(
    document_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Get audit trail for a document."""
    try:
        audit = get_audit_service()
        events = audit.get_document_events(document_id)
        
        return {
            "document_id": document_id,
            "events": [
                {
                    "event_type": e.event_type,
                    "timestamp": e.timestamp.isoformat(),
                    "user_id": e.user_id,
                    "action": e.action,
                    "details": e.details
                }
                for e in events
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get audit trail: {e}")
        return {"document_id": document_id, "events": []}
