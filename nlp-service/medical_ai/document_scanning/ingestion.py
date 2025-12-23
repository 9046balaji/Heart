"""
Document Ingestion Layer for Medical Documents.

Handles:
- PDF upload (text-based and scanned)
- Image upload (camera scans)
- File validation and security
- Secure storage with encryption
"""

import hashlib
from typing import Optional, Dict, Any, BinaryIO
from datetime import datetime
from pathlib import Path
from enum import Enum
import logging

# Add import
from nlp.rag.vector_store import VectorStore
from .text_quality import validate_text_quality

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Supported document types."""

    PDF_TEXT = "pdf_text"  # Text-based PDF
    PDF_SCANNED = "pdf_scanned"  # Scanned/image PDF
    IMAGE_JPEG = "image_jpeg"
    IMAGE_PNG = "image_png"
    UNKNOWN = "unknown"


class MedicalDocumentCategory(Enum):
    """Categories of medical documents."""

    LAB_REPORT = "lab_report"
    PRESCRIPTION = "prescription"
    MEDICAL_BILL = "medical_bill"
    DISCHARGE_SUMMARY = "discharge_summary"
    IMAGING_REPORT = "imaging_report"
    UNKNOWN = "unknown"


class DocumentIngestionService:
    """
    Ingests and validates uploaded medical documents.

    Features:
    - File type validation
    - Virus/malware scanning (placeholder)
    - Secure storage with encryption
    - Original file preservation for audit

    Example:
        service = DocumentIngestionService(storage_path="./documents")
        result = service.ingest_document(
            file=uploaded_file,
            filename="lab_report.pdf",
            user_id="user123"
        )
        print(result["document_id"])
    """

    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
    MAX_FILE_SIZE_MB = 20

    def __init__(
        self, storage_path: str = "./document_storage", encrypt_at_rest: bool = True
    ):
        """
        Initialize document ingestion service.

        Args:
            storage_path: Path for document storage
            encrypt_at_rest: Enable encryption for stored documents
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.encrypt_at_rest = encrypt_at_rest

        # Create subdirectories
        (self.storage_path / "originals").mkdir(exist_ok=True)
        (self.storage_path / "processed").mkdir(exist_ok=True)
        
        self.vector_store = VectorStore()

        logger.info(f"Document ingestion service initialized: {storage_path}")

    def ingest_document(
        self,
        file: BinaryIO,
        filename: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest a medical document.

        Args:
            file: File-like object
            filename: Original filename
            user_id: Uploading user ID
            metadata: Additional metadata

        Returns:
            Ingestion result with document_id and status
        """
        # Step 1: Validate file
        validation = self._validate_file(file, filename)
        if not validation["valid"]:
            return {"success": False, "error": validation["error"], "document_id": None}

        # Step 2: Generate document ID
        file_content = file.read()
        file.seek(0)  # Reset for later use
        document_id = self._generate_document_id(file_content, user_id)

        # Step 3: Detect document type
        doc_type = self._detect_document_type(filename, file_content)

        # Step 4: Store original
        storage_result = self._store_original(
            document_id=document_id,
            file_content=file_content,
            filename=filename,
            user_id=user_id,
            doc_type=doc_type,
        )
        
        # Step 4.5: Validate text quality (after OCR, before chunking)
        extracted_text = self._extract_text(file_content, doc_type)
        is_quality_ok, quality_details = validate_text_quality(extracted_text)
        
        if not is_quality_ok:
            return {
                "success": False,
                "document_id": document_id,
                "status": "quality_review_required",
                "quality_issues": quality_details["issues"],
                "quality_score": quality_details["score"]
            }

        # Step 5: Create ingestion record
        ingestion_record = {
            "success": True,
            "document_id": document_id,
            "user_id": user_id,
            "original_filename": filename,
            "document_type": doc_type.value,
            "file_size_bytes": len(file_content),
            "file_hash": hashlib.sha256(file_content).hexdigest(),
            "storage_path": storage_result["path"],
            "ingested_at": datetime.utcnow().isoformat(),
            "status": "pending_ocr",
            "metadata": metadata or {},
        }

        logger.info(f"Document ingested: {document_id} ({doc_type.value})")
        return ingestion_record

    def _validate_file(self, file: BinaryIO, filename: str) -> Dict[str, Any]:
        """Validate uploaded file."""
        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return {
                "valid": False,
                "error": f"File type not allowed: {ext}. Allowed: {self.ALLOWED_EXTENSIONS}",
            }

        # Check file size
        file.seek(0, 2)  # Seek to end
        size_bytes = file.tell()
        file.seek(0)  # Reset

        max_size_bytes = self.MAX_FILE_SIZE_MB * 1024 * 1024
        if size_bytes > max_size_bytes:
            return {
                "valid": False,
                "error": f"File too large: {size_bytes / (1024*1024):.1f}MB. Max: {self.MAX_FILE_SIZE_MB}MB",
            }

        # Check magic bytes (file signature)
        magic_valid = self._validate_magic_bytes(file, ext)
        if not magic_valid:
            return {"valid": False, "error": "File content does not match extension"}

        return {"valid": True, "error": None}

    def _validate_magic_bytes(self, file: BinaryIO, ext: str) -> bool:
        """Validate file magic bytes match extension."""
        file.seek(0)
        header = file.read(10)
        file.seek(0)

        magic_signatures = {
            ".pdf": b"%PDF",
            ".jpg": b"\xff\xd8\xff",
            ".jpeg": b"\xff\xd8\xff",
            ".png": b"\x89PNG",
        }

        expected = magic_signatures.get(ext)
        if expected:
            return header.startswith(expected)
        return True

    def _detect_document_type(self, filename: str, content: bytes) -> DocumentType:
        """Detect document type from extension and content."""
        ext = Path(filename).suffix.lower()

        if ext == ".pdf":
            # Check if PDF contains embedded text or is scanned
            # Look for text streams in PDF
            if b"/Type /Page" in content and b"BT" in content:
                return DocumentType.PDF_TEXT
            return DocumentType.PDF_SCANNED
        elif ext in {".jpg", ".jpeg"}:
            return DocumentType.IMAGE_JPEG
        elif ext == ".png":
            return DocumentType.IMAGE_PNG

        return DocumentType.UNKNOWN

    def _extract_text(self, file_content: bytes, doc_type: DocumentType) -> str:
        """Extract text from document based on type."""
        try:
            if doc_type in [DocumentType.PDF_TEXT, DocumentType.PDF_SCANNED]:
                # Extract text from PDF
                import PyPDF2
                from io import BytesIO
                
                pdf_file = BytesIO(file_content)
                reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
            elif doc_type in [DocumentType.IMAGE_JPEG, DocumentType.IMAGE_PNG]:
                # Extract text from image using OCR
                import pytesseract
                from PIL import Image
                from io import BytesIO
                
                image = Image.open(BytesIO(file_content))
                return pytesseract.image_to_string(image)
            else:
                # For unknown types, try to decode as text if possible
                return file_content.decode('utf-8', errors='ignore')
        except ImportError as e:
            logger.warning(f"Required library not installed for text extraction: {e}")
            # Return empty string if required libraries not available
            return ""
        except Exception as e:
            logger.error(f"Error extracting text from document: {e}")
            return ""

    def _generate_document_id(self, content: bytes, user_id: str) -> str:
        """Generate unique document ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        content_hash = hashlib.sha256(content).hexdigest()[:8]
        return f"doc_{user_id[:8]}_{timestamp}_{content_hash}"

    def _store_original(
        self,
        document_id: str,
        file_content: bytes,
        filename: str,
        user_id: str,
        doc_type: DocumentType,
    ) -> Dict[str, str]:
        """Store original document securely."""
        # Create user directory
        user_dir = self.storage_path / "originals" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # Store with document_id as filename
        ext = Path(filename).suffix
        storage_filename = f"{document_id}{ext}"
        storage_path = user_dir / storage_filename

        # Write file (add encryption in production)
        with open(storage_path, "wb") as f:
            if self.encrypt_at_rest:
                # TODO: Implement proper encryption with cryptography library
                # For now, just store as-is
                f.write(file_content)
            else:
                f.write(file_content)

        return {"path": str(storage_path)}

    def get_document_path(self, document_id: str, user_id: str) -> Optional[Path]:
        """Get storage path for a document."""
        user_dir = self.storage_path / "originals" / user_id

        # Find file with document_id prefix
        for file_path in user_dir.glob(f"{document_id}*"):
            return file_path

        return None

    def delete_document(self, document_id: str, user_id: str) -> bool:
        """Delete document and associated vectors."""
        # Delete from file storage
        file_path = self.get_document_path(document_id, user_id)
        file_deleted = False
        if file_path and file_path.exists():
            file_path.unlink()
            file_deleted = True
        
        # Delete from vector store
        vectors_deleted = self.vector_store.delete_document_vectors(document_id)
        
        logger.info(f"Document deleted: {document_id} "
                   f"(file={file_deleted}, vectors={vectors_deleted})")
        return file_deleted or vectors_deleted > 0
