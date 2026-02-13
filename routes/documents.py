"""
Document Routes - Multimodal Document Upload and Processing API

Provides endpoints for:
- Single document upload and ingestion
- Batch folder processing
- Document processing status
- Query documents with multimodal context

Uses rag/multimodal/ components for:
- PDF parsing (MineruParser)
- Table/image/equation processing
- VLM-enhanced retrieval
"""


import os
import tempfile
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any

from routes.file_security import validate_upload
from core.security import get_current_user

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["documents"])


# ============================================================
# Response Models
# ============================================================

class DocumentUploadResponse(BaseModel):
    """Response for document upload."""
    success: bool
    doc_id: str
    file_name: str
    chunks_created: int = 0
    tables_processed: int = 0
    images_processed: int = 0
    message: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchUploadResponse(BaseModel):
    """Response for batch document upload."""
    success: bool
    total_files: int
    successful: int
    failed: int
    results: List[Dict[str, Any]] = Field(default_factory=list)


class DocumentQueryRequest(BaseModel):
    """Request for querying documents."""
    query: str
    doc_ids: Optional[List[str]] = None
    top_k: int = 5
    include_images: bool = False
    include_tables: bool = True


class DocumentQueryResponse(BaseModel):
    """Response for document query."""
    query: str
    results: List[Dict[str, Any]]
    total_results: int
    multimodal_context: Optional[str] = None


# ============================================================
# Lazy Service Initialization
# ============================================================

_ingestion_service = None
_query_service = None


def _get_ingestion_service():
    """Lazy load the multimodal ingestion service."""
    global _ingestion_service
    if _ingestion_service is None:
        try:
            from rag.multimodal import MultimodalIngestionService, MultimodalConfig
            from rag.vector_store import get_vector_store
            from rag.embedding_service import get_embedding_service
            from core.llm import get_llm_gateway
            
            vector_store = get_vector_store()
            embedding_service = get_embedding_service()
            llm_gateway = get_llm_gateway()
            
            # Create embedding function wrapper
            async def embed_func(text: str) -> List[float]:
                return await embedding_service.embed_text(text)
            
            # Create LLM function wrapper
            async def llm_func(prompt: str) -> str:
                return await llm_gateway.generate(prompt)
            
            config = MultimodalConfig(
                enable_table_processing=True,
                enable_image_processing=True,
                enable_equation_processing=True,
            )
            
            _ingestion_service = MultimodalIngestionService(
                vector_store=vector_store,
                embedding_func=embed_func,
                llm_func=llm_func,
                config=config,
            )
            logger.info("MultimodalIngestionService initialized for document routes")
        except Exception as e:
            logger.error(f"Failed to initialize ingestion service: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Document processing service unavailable: {e}"
            )
    
    return _ingestion_service


def _get_query_service():
    """Lazy load the multimodal query service."""
    global _query_service
    if _query_service is None:
        try:
            from rag.multimodal import MultimodalQueryService
            from rag.vector_store import get_vector_store
            from core.llm import get_llm_gateway
            
            vector_store = get_vector_store()
            llm_gateway = get_llm_gateway()
            
            # MultimodalQueryService expects retriever (not vector_store) and llm_func (not llm_gateway)
            _query_service = MultimodalQueryService(
                retriever=vector_store,
                llm_func=llm_gateway,
            )
            logger.info("MultimodalQueryService initialized for document routes")
        except Exception as e:
            logger.warning(f"MultimodalQueryService not available: {e}")
            _query_service = None
    
    return _query_service


# ============================================================
# Endpoints
# ============================================================

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form("medical"),
    user_id: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Upload and process a single document.
    
    Supported formats:
    - PDF (with OCR support)
    - Word documents (.docx)
    - Text files (.txt)
    - Markdown (.md)
    
    Features:
    - Extracts tables, images, and equations
    - Generates embeddings for semantic search
    - Stores in vector database
    
    **Security:**
    ✅ Streams file in 1MB chunks (prevents OOM on large uploads)
    ✅ Validates MIME type from binary signature (prevents spoofing)
    ✅ Respects max file size limits
    
    Args:
        file: Document file to upload
        description: Optional description of the document
        category: Document category (default: medical)
        user_id: Optional user ID to associate with document
    
    Returns:
        DocumentUploadResponse with ingestion details
    """
    ingestion_service = _get_ingestion_service()
    
    # Validate file type
    allowed_extensions = {".pdf", ".docx", ".txt", ".md", ".doc"}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: {allowed_extensions}"
        )
    
    # Configuration for file uploads
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    
    # Save uploaded file temporarily with chunked reading
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=file_ext,
            prefix="upload_"
        ) as temp_file:
            temp_path = temp_file.name
            total_bytes = 0
            
            # ✅ SECURITY FIX: Stream file in chunks instead of reading all at once
            # This prevents OOM from large files (e.g., 500MB PDF)
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                total_bytes += len(chunk)
                
                # Enforce file size limit
                if total_bytes > MAX_FILE_SIZE_BYTES:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max size: {MAX_FILE_SIZE_MB}MB"
                    )
                
                temp_file.write(chunk)
                
                # Log progress for large files
                if total_bytes % (5 * CHUNK_SIZE) == 0:  # Every 5MB
                    logger.debug(f"Upload progress: {total_bytes / (1024*1024):.1f}MB")
        
        # ✅ SECURITY FIX: Validate MIME type from binary signature (not just extension)
        # This prevents upload spoofing (e.g., .exe renamed to .pdf)
        is_valid, error_msg = await validate_upload(
            file_path=temp_path,
            filename=file.filename,
            max_size_bytes=MAX_FILE_SIZE_BYTES
        )
        
        if not is_valid:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {error_msg}"
            )
        
        # Prepare metadata
        metadata = {
            "original_filename": file.filename,
            "description": description,
            "category": category,
            "user_id": user_id,
            "file_size": total_bytes,
        }
        
        logger.info(f"📁 File uploaded and validated: {file.filename} ({total_bytes / (1024*1024):.1f}MB)")
        
        # Ingest document
        result = await ingestion_service.ingest_document(
            file_path=temp_path,
            metadata=metadata
        )
        
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        
        if result.success:
            return DocumentUploadResponse(
                success=True,
                doc_id=result.doc_id,
                file_name=file.filename,
                chunks_created=result.chunks_created,
                tables_processed=result.tables_processed,
                images_processed=result.images_processed,
                message="Document processed successfully",
                metadata=result.metadata,
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Document processing failed: {result.error}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document upload failed: {str(e)}"
        )


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form("medical"),
    user_id: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Upload multiple documents in batch.
    
    Args:
        files: List of document files
        category: Document category for all files
        user_id: Optional user ID
        background_tasks: FastAPI background tasks
    
    Returns:
        BatchUploadResponse with results for each file
    """
    ingestion_service = _get_ingestion_service()
    
    results = []
    successful = 0
    failed = 0
    
    for file in files:
        try:
            # Process each file
            file_ext = Path(file.filename).suffix.lower()
            
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=file_ext,
                prefix="batch_"
            ) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_path = temp_file.name
            
            metadata = {
                "original_filename": file.filename,
                "category": category,
                "user_id": user_id,
                "file_size": len(content),
            }
            
            result = await ingestion_service.ingest_document(
                file_path=temp_path,
                metadata=metadata
            )
            
            # Cleanup
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            
            if result.success:
                successful += 1
                results.append({
                    "file_name": file.filename,
                    "success": True,
                    "doc_id": result.doc_id,
                    "chunks_created": result.chunks_created,
                })
            else:
                failed += 1
                results.append({
                    "file_name": file.filename,
                    "success": False,
                    "error": result.error,
                })
        
        except Exception as e:
            failed += 1
            results.append({
                "file_name": file.filename,
                "success": False,
                "error": str(e),
            })
    
    return BatchUploadResponse(
        success=failed == 0,
        total_files=len(files),
        successful=successful,
        failed=failed,
        results=results,
    )


@router.post("/query", response_model=DocumentQueryResponse)
async def query_documents(
    request: DocumentQueryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Query documents with multimodal context.
    
    Supports:
    - Semantic search across documents
    - Table-aware queries
    - Image context inclusion
    
    Args:
        request: Query parameters
    
    Returns:
        DocumentQueryResponse with matching results
    """
    try:
        from rag.vector_store import get_vector_store
        
        vector_store = get_vector_store()
        
        # Perform search
        results = vector_store.search_medical_knowledge(
            query=request.query,
            top_k=request.top_k
        )
        
        # Filter by doc_ids if specified
        if request.doc_ids:
            results = [
                r for r in results 
                if r.get("metadata", {}).get("doc_id") in request.doc_ids
            ]
        
        # Optionally enhance with multimodal context
        multimodal_context = None
        query_service = _get_query_service()
        
        if query_service and (request.include_images or request.include_tables):
            try:
                enhanced = await query_service.query_with_multimodal_context(
                    query=request.query,
                    documents=results,
                    include_images=request.include_images,
                    include_tables=request.include_tables,
                )
                multimodal_context = enhanced.get("context")
                results = enhanced.get("results", results)
            except Exception as e:
                logger.warning(f"Multimodal enhancement failed: {e}")
        
        return DocumentQueryResponse(
            query=request.query,
            results=results,
            total_results=len(results),
            multimodal_context=multimodal_context,
        )
    
    except Exception as e:
        logger.error(f"Document query failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)}"
        )


@router.get("/status")
async def get_document_service_status():
    """
    Get status of document processing services.
    
    Returns:
        Service status information
    """
    status = {
        "ingestion_service": False,
        "query_service": False,
        "parsers_available": [],
        "processors_enabled": [],
    }
    
    try:
        from rag.multimodal import (
            MineruParser, DoclingParser,
            TableProcessor, ImageProcessor, EquationProcessor
        )
        
        # Check parsers
        status["parsers_available"] = ["MineruParser", "DoclingParser"]
        status["processors_enabled"] = ["TableProcessor", "ImageProcessor", "EquationProcessor"]
        
        # Check services
        try:
            _get_ingestion_service()
            status["ingestion_service"] = True
        except Exception:
            pass
        
        try:
            _get_query_service()
            status["query_service"] = True
        except Exception:
            pass
        
    except ImportError as e:
        status["error"] = f"Multimodal module not fully available: {e}"
    
    return status


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete a document and all its chunks.
    
    Args:
        doc_id: Document ID to delete
    
    Returns:
        Deletion confirmation
    """
    try:
        from rag.vector_store import get_vector_store
        
        vector_store = get_vector_store()
        
        # Delete all chunks with this doc_id
        if hasattr(vector_store, "delete_by_metadata"):
            deleted_count = vector_store.delete_by_metadata({"doc_id": doc_id})
            return {
                "success": True,
                "doc_id": doc_id,
                "chunks_deleted": deleted_count,
            }
        else:
            # Fallback: mark as deleted but can't remove
            return {
                "success": False,
                "doc_id": doc_id,
                "message": "Deletion not supported by vector store",
            }
    
    except Exception as e:
        logger.error(f"Document deletion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Deletion failed: {str(e)}"
        )


# ============================================================
# Utility Functions
# ============================================================

def get_document_router() -> APIRouter:
    """Get the document router for inclusion in main app."""
    return router
