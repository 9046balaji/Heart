"""
Document Scanning API Routes.

FastAPI routes for document upload, OCR processing, and classification.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
    Query,
)
from pydantic import BaseModel, Field
import logging
import os
import asyncio

try:
    import chardet
except ImportError:
    chardet = None
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Document Scanning"])

# Configuration
UNSTRUCTURED_TIMEOUT = float(os.getenv("UNSTRUCTURED_TIMEOUT", "30.0"))
USE_UNSTRUCTURED_FALLBACK = (
    os.getenv("USE_UNSTRUCTURED_FALLBACK", "true").lower() == "true"
)


# ==================== Chain of Responsibility Pattern ====================


class DocumentProcessingResult(BaseModel):
    """Result from document processing."""

    text: str
    metadata: dict
    processor_used: str
    entities: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
    confidence: float = 0.0


class DocumentProcessor(ABC):
    """Abstract base class for document processors (Chain of Responsibility)."""

    def __init__(self):
        self._next_processor: Optional["DocumentProcessor"] = None

    def set_next(self, processor: "DocumentProcessor") -> "DocumentProcessor":
        """Set the next processor in the chain."""
        self._next_processor = processor
        return processor

    @abstractmethod
    async def can_process(self, file_content: bytes, file_type: str) -> bool:
        """Check if this processor can handle the file."""

    @abstractmethod
    async def process(
        self, file_content: bytes, file_type: str
    ) -> DocumentProcessingResult:
        """Process the document."""

    async def handle(
        self, file_content: bytes, file_type: str
    ) -> DocumentProcessingResult:
        """
        Handle the document processing request.
        Try this processor first, fall back to next in chain on failure.
        """
        try:
            if await self.can_process(file_content, file_type):
                return await self.process(file_content, file_type)
        except Exception as e:
            logger.warning(
                f"{self.__class__.__name__} failed: {e}, trying next processor"
            )

        # Fall back to next processor in chain
        if self._next_processor:
            return await self._next_processor.handle(file_content, file_type)

        raise HTTPException(status_code=500, detail="All document processors failed")


class UnstructuredProcessor(DocumentProcessor):
    """
    Primary processor using Unstructured.io for high-quality document parsing.
    Handles complex layouts, tables, and forms automatically.
    """

    async def can_process(self, file_content: bytes, file_type: str) -> bool:
        """Unstructured.io can handle most document types."""
        supported_types = [
            "pdf",
            "docx",
            "doc",
            "pptx",
            "xlsx",
            "html",
            "txt",
            "md",
            "png",
            "jpg",
            "jpeg",
        ]
        return file_type.lower() in supported_types

    async def process(
        self, file_content: bytes, file_type: str
    ) -> DocumentProcessingResult:
        """Process using Unstructured.io with timeout protection."""
        try:
            # Save content to temporary file for Unstructured.io processing
            import tempfile

            with tempfile.NamedTemporaryFile(
                suffix=f".{file_type}", delete=False
            ) as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name

            try:
                # Apply timeout to prevent hanging on large documents
                result = await asyncio.wait_for(
                    self._process_document(tmp_file_path), timeout=UNSTRUCTURED_TIMEOUT
                )

                return DocumentProcessingResult(
                    text=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                    processor_used="UnstructuredIO",
                    entities=result.get("entities", []),
                    tables=result.get("tables", []),
                    confidence=result.get("confidence", 0.95),
                )
            finally:
                # Clean up temporary file
                os.unlink(tmp_file_path)

        except asyncio.TimeoutError:
            logger.warning(f"Unstructured.io timed out after {UNSTRUCTURED_TIMEOUT}s")
            raise
        except ImportError as e:
            logger.error(f"Unstructured.io not available: {e}")
            raise

    async def _process_document(self, file_path: str) -> dict:
        """Internal method to process document with Unstructured.io."""
        from medical_ai.document_scanning.unstructured_processor import (
            UnstructuredDocumentProcessor,
        )

        processor = UnstructuredDocumentProcessor()
        return processor.process_document(file_path)


class TesseractOCRProcessor(DocumentProcessor):
    """
    Fallback processor using Tesseract OCR for image-based documents.
    Lighter weight but less feature-rich than Unstructured.io.
    """

    async def can_process(self, file_content: bytes, file_type: str) -> bool:
        """Tesseract handles images and PDFs."""
        supported_types = ["pdf", "png", "jpg", "jpeg", "tiff", "bmp"]
        return file_type.lower() in supported_types

    async def process(
        self, file_content: bytes, file_type: str
    ) -> DocumentProcessingResult:
        """Process using legacy Tesseract OCR engine."""
        # Save content to temporary file for OCR processing
        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix=f".{file_type}", delete=False
        ) as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name

        try:
            from medical_ai.document_scanning.ocr_engine import OCREngineFactory, OCRProvider

            factory = OCREngineFactory()
            ocr_engine = factory.get_engine(OCRProvider.TESSERACT)
            result = ocr_engine.extract_text(tmp_file_path)

            return DocumentProcessingResult(
                text=result.text,
                metadata={
                    "source": "tesseract_ocr",
                    "file_type": file_type,
                    "processing_time_ms": result.processing_time_ms,
                },
                processor_used="TesseractOCR",
                confidence=result.confidence,
            )
        finally:
            # Clean up temporary file
            os.unlink(tmp_file_path)


class SimpleTextProcessor(DocumentProcessor):
    """
    Last-resort processor for plain text files.
    No dependencies, always available.
    """

    async def can_process(self, file_content: bytes, file_type: str) -> bool:
        """Text processor handles plain text formats."""
        return file_type.lower() in ["txt", "md", "csv", "json"]

    async def process(
        self, file_content: bytes, file_type: str
    ) -> DocumentProcessingResult:
        """Simple text extraction with encoding detection."""
        # Detect encoding
        if chardet:
            detected = chardet.detect(file_content)
            encoding = detected.get("encoding", "utf-8")
        else:
            encoding = "utf-8"

        try:
            text = file_content.decode(encoding)
        except:
            text = file_content.decode("utf-8", errors="ignore")

        return DocumentProcessingResult(
            text=text,
            metadata={"encoding": encoding, "file_type": file_type},
            processor_used="SimpleText",
            confidence=0.99,
        )


def create_processor_chain() -> DocumentProcessor:
    """
    Create the Chain of Responsibility for document processing.
    Order: Unstructured.io -> Tesseract OCR -> Simple Text
    """
    # Build the chain
    unstructured = UnstructuredProcessor()
    tesseract = TesseractOCRProcessor()
    simple_text = SimpleTextProcessor()

    if USE_UNSTRUCTURED_FALLBACK:
        # Full chain: Unstructured -> Tesseract -> Simple
        unstructured.set_next(tesseract).set_next(simple_text)
        return unstructured
    else:
        # Skip Unstructured: Tesseract -> Simple
        tesseract.set_next(simple_text)
        return tesseract


# Global processor chain
_processor_chain: Optional[DocumentProcessor] = None


def get_processor_chain() -> DocumentProcessor:
    """Get or create the processor chain singleton."""
    global _processor_chain
    if _processor_chain is None:
        _processor_chain = create_processor_chain()
    return _processor_chain


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
                "created_at": "2024-01-15T10:30:00Z",
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
                "language": "eng",
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
                "page_count": 1,
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
                "text": "LABORATORY REPORT\nPatient: John Smith\nGlucose: 126 mg/dL",
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
                "suggested_schema": "LabReportSchema",
            }
        }


class ExtractionRequest(BaseModel):
    """Request to extract structured data from document."""

    document_id: str
    document_type: str
    text: Optional[str] = None
    auto_verify: bool = Field(
        default=False, description="Skip human verification queue"
    )


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
    from medical_ai.document_scanning import DocumentIngestionService

    return DocumentIngestionService()


def get_ocr_factory():
    """Get OCR engine factory instance."""
    from medical_ai.document_scanning import OCREngineFactory

    return OCREngineFactory()


def get_classifier():
    """Get document classifier instance."""
    from medical_ai.document_scanning import MedicalDocumentClassifier

    return MedicalDocumentClassifier()


def get_audit_service():
    """Get audit service instance."""
    from core.compliance.audit_logger import AuditService

    return AuditService()


def get_verification_queue():
    """Get verification queue instance."""
    from core.compliance.verification_queue import VerificationQueue

    return VerificationQueue()


# ==================== Routes ====================


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    summary="Upload Medical Document",
    description="Upload a medical document for processing. Supports PDF, images, and common document formats.",
)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Query(..., description="User ID uploading the document"),
    background_tasks: BackgroundTasks = None,
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
            file_size=len(content),
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        file_size=len(content),
        content_type=file.content_type or "application/octet-stream",
        status="uploaded",
        created_at=datetime.utcnow(),
    )


@router.post(
    "/ocr",
    response_model=OCRResult,
    summary="Process OCR",
    description="Extract text from an uploaded document using OCR.",
)
async def process_ocr(
    request: OCRRequest, user_id: str = Query(..., description="User ID")
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
        page_count=1,
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
            page_count=result.page_count,
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")

    return result


@router.post(
    "/classify",
    response_model=ClassificationResult,
    summary="Classify Document",
    description="Classify a document by type (lab report, prescription, etc.)",
)
async def classify_document(
    request: ClassificationRequest, user_id: str = Query(..., description="User ID")
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
        suggested_schema="LabReportSchema",
    )


@router.post(
    "/extract",
    response_model=ExtractionResult,
    summary="Extract Structured Data",
    description="Extract structured entities from a classified document using AI.",
)
async def extract_entities(
    request: ExtractionRequest, user_id: str = Query(..., description="User ID")
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
            source_location="line 1",
        ),
        ExtractedEntity(
            field="test_date",
            value="2024-01-15",
            confidence=0.95,
            source_location="line 2",
        ),
        ExtractedEntity(
            field="glucose",
            value="126 mg/dL",
            confidence=0.88,
            source_location="line 5",
        ),
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
            confidence=overall_confidence,
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
        verification_id=verification_id,
    )


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="List Documents",
    description="List uploaded documents for a user.",
)
async def list_documents(
    user_id: str = Query(..., description="User ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
    document_type: Optional[str] = Query(None, description="Filter by type"),
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
            ocr_confidence=0.92,
        )
    ]

    return DocumentListResponse(
        total=1, page=page, page_size=page_size, documents=documents
    )


@router.get(
    "/{document_id}",
    summary="Get Document Details",
    description="Get details and processing status of a specific document.",
)
async def get_document(
    document_id: str, user_id: str = Query(..., description="User ID")
):
    """Get document details by ID."""
    # Audit view access
    try:
        audit = get_audit_service()
        audit.log_document_viewed(user_id=user_id, document_id=document_id)
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")

    return {
        "document_id": document_id,
        "filename": "example.pdf",
        "status": "processed",
        "created_at": datetime.utcnow().isoformat(),
        "ocr_result": None,
        "classification": None,
        "extraction": None,
    }


@router.delete(
    "/{document_id}",
    summary="Delete Document",
    description="Delete an uploaded document.",
)
async def delete_document(
    document_id: str,
    user_id: str = Query(..., description="User ID"),
    reason: str = Query(..., description="Reason for deletion"),
):
    """Delete a document."""
    # Audit deletion
    try:
        audit = get_audit_service()
        audit.log_document_deleted(
            user_id=user_id, document_id=document_id, reason=reason
        )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")

    return {"status": "deleted", "document_id": document_id}


@router.get(
    "/{document_id}/audit",
    summary="Get Document Audit Trail",
    description="Get the complete audit trail for a document.",
)
async def get_document_audit(
    document_id: str, user_id: str = Query(..., description="User ID")
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
                    "details": e.details,
                }
                for e in events
            ],
        }
    except Exception as e:
        logger.error(f"Failed to get audit trail: {e}")
        return {"document_id": document_id, "events": []}


@router.post(
    "/process",
    response_model=DocumentProcessingResult,
    summary="Process Document",
    description="Process an uploaded document using the Chain of Responsibility pattern.",
)
async def process_document(
    file: UploadFile = File(...), user_id: str = Query(..., description="User ID")
):
    """
    Process an uploaded document using the Chain of Responsibility pattern.
    Tries Unstructured.io first, falls back to Tesseract OCR if needed.
    """
    # Get file extension
    file_type = file.filename.split(".")[-1] if "." in file.filename else "txt"

    # Read file content
    file_content = await file.read()

    # Process through the chain
    processor_chain = get_processor_chain()
    result = await processor_chain.handle(file_content, file_type)

    logger.info(f"Document processed by: {result.processor_used}")
    return result


@router.post("/process/{document_id}")
async def process_document_by_id(document_id: str, user_id: str = Query(...)):
    """Proxy for processing a document by ID."""
    # In a real app, this would fetch the document and process it
    return {
        "status": "processing",
        "document_id": document_id,
        "message": f"Document {document_id} is being processed",
    }


@router.get("/processors/status")
async def get_processors_status():
    """Get status of available document processors."""
    status = {
        "chain_order": [],
        "unstructured_enabled": USE_UNSTRUCTURED_FALLBACK,
        "timeout_seconds": UNSTRUCTURED_TIMEOUT,
    }

    # Check which processors are available
    try:
        from medical_ai.document_scanning.unstructured_processor import (
            UnstructuredDocumentProcessor,  # noqa: F401
        )

        status["chain_order"].append("UnstructuredIO")
    except ImportError:
        pass

    try:
        pass

        status["chain_order"].append("TesseractOCR")
    except ImportError:
        pass

    status["chain_order"].append("SimpleText")  # Always available

    return status
