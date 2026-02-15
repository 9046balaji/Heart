from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime
import os

from database import get_db
from db_models.document import Document
from document_storage import DocumentStorage

router = APIRouter(prefix="/api/documents", tags=["documents"])
storage = DocumentStorage()

@router.get("/list")
async def list_documents(
    user_id: str,
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all documents for a user"""
    query = db.query(Document).filter(Document.user_id == user_id)
    if status:
        query = query.filter(Document.status == status)
    
    total = query.count()
    documents = query.offset(skip).limit(limit).all()
    
    return documents

@router.get("/{document_id}")
async def get_document(document_id: str, user_id: str, db: Session = Depends(get_db)):
    """Get a single document by ID"""
    doc = db.query(Document).filter(Document.document_id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.delete("/{document_id}")
async def delete_document(document_id: str, user_id: str, db: Session = Depends(get_db)):
    """Delete a document"""
    doc = db.query(Document).filter(Document.document_id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file from storage
    if doc.file_path:
        await storage.delete_file(doc.file_path)
    
    # Delete from DB
    db.delete(doc)
    db.commit()
    
    return {"message": "Document deleted"}

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Upload a document"""
    # Create document record
    doc_id = str(uuid.uuid4())
    
    # Save file
    file_content = await file.read()
    file_path = await storage.save_file(file_content, file.filename)
    
    new_doc = Document(
        user_id=user_id,
        document_id=doc_id,
        filename=file.filename,
        file_path=file_path,
        file_size=len(file_content),
        content_type=file.content_type,
        status="uploaded"
    )
    
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    return new_doc

@router.post("/process")
async def process_document(
    document_id: str = Form(...),
    user_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Process a document (Mock Implementation for now)"""
    doc = db.query(Document).filter(Document.document_id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    doc.status = "processed"
    doc.processed_at = datetime.utcnow()
    # Mock extracted data
    doc.text = "Sample extracted text from document."
    doc.entities = '[{"type": "medication", "value": "Aspirin", "confidence": 0.9}]'
    doc.classification = '{"document_type": "prescription", "confidence": 0.85}'
    doc.confidence = 0.85
    
    db.commit()
    db.refresh(doc)
    
    return doc
