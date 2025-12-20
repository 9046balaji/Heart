"""
Unstructured Document Processor for Cardio AI.

This module implements document processing using Unstructured.io
for handling complex document layouts and improved text extraction.

Features:
- Handles complex document layouts automatically
- Built-in table and form extraction
- Header/footer removal
- Better text cleaning and normalization
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

# Unstructured imports
from unstructured.partition.auto import partition
from unstructured.chunking.title import chunk_by_title
from unstructured.cleaners.core import clean_extra_whitespace

logger = logging.getLogger(__name__)


class UnstructuredDocumentProcessor:
    """
    Document processor using Unstructured.io.

    Features:
    - Automatic document type detection
    - Advanced layout processing
    - Text cleaning and normalization
    - Chunking for RAG pipelines
    """

    def __init__(self):
        """Initialize Unstructured document processor."""
        logger.info("✅ UnstructuredDocumentProcessor initialized")

    def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Process a document using Unstructured.io.

        Args:
            file_path: Path to document file

        Returns:
            Dict with processed content and metadata
        """
        logger.info(f"Processing document: {file_path}")

        try:
            # Partition document based on file type
            elements = partition(filename=file_path)

            # Clean and chunk content
            cleaned_elements = [clean_extra_whitespace(element) for element in elements]
            chunks = chunk_by_title(cleaned_elements)

            # Extract metadata
            metadata = {
                "page_count": len([e for e in elements if hasattr(e, "metadata")]),
                "content_type": "unknown",
                "entities": [],
                "processed_at": datetime.now().isoformat(),
            }

            # Extract structured data
            content = "\n".join([str(element) for element in chunks])

            # Try to determine content type
            if any("symptom" in str(element).lower() for element in elements):
                metadata["content_type"] = "medical_report"
            elif any("medication" in str(element).lower() for element in elements):
                metadata["content_type"] = "prescription"
            elif any("lab" in str(element).lower() for element in elements):
                metadata["content_type"] = "lab_results"

            return {
                "content": content,
                "metadata": metadata,
                "chunks": [str(chunk) for chunk in chunks],
                "elements_count": len(elements),
                "success": True,
            }
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return {
                "error": str(e),
                "file_path": file_path,
                "processed_at": datetime.now().isoformat(),
                "success": False,
            }

    def extract_entities(self, file_path: str) -> Dict[str, Any]:
        """
        Extract entities from a document.

        Args:
            file_path: Path to document file

        Returns:
            Dict with extracted entities and metadata
        """
        logger.info(f"Extracting entities from: {file_path}")

        try:
            # Partition document
            elements = partition(filename=file_path)

            # Extract different types of entities
            entities = {
                "medical_terms": [],
                "medications": [],
                "measurements": [],
                "dates": [],
                "names": [],
            }

            # Simple entity extraction based on keywords
            medical_keywords = [
                "blood pressure",
                "heart rate",
                "cholesterol",
                "glucose",
            ]
            medication_keywords = [
                "tablet",
                "capsule",
                "injection",
                "cream",
                "mg",
                "ml",
            ]

            for element in elements:
                text = str(element).lower()

                # Extract medical terms
                for keyword in medical_keywords:
                    if keyword in text:
                        entities["medical_terms"].append(keyword)

                # Extract medication terms
                for keyword in medication_keywords:
                    if keyword in text:
                        entities["medications"].append(keyword)

            return {
                "entities": entities,
                "elements_processed": len(elements),
                "file_path": file_path,
                "extracted_at": datetime.now().isoformat(),
                "success": True,
            }
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return {
                "error": str(e),
                "file_path": file_path,
                "extracted_at": datetime.now().isoformat(),
                "success": False,
            }

    def process_batch(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Process multiple documents in batch.

        Args:
            file_paths: List of paths to document files

        Returns:
            Dict with batch processing results
        """
        logger.info(f"Processing batch of {len(file_paths)} documents")

        results = []
        successful = 0
        failed = 0

        for file_path in file_paths:
            result = self.process_document(file_path)
            results.append(result)

            if result["success"]:
                successful += 1
            else:
                failed += 1

        return {
            "results": results,
            "successful": successful,
            "failed": failed,
            "total": len(file_paths),
            "batch_processed_at": datetime.now().isoformat(),
        }


# Factory function
def create_unstructured_processor() -> UnstructuredDocumentProcessor:
    """
    Factory function to create an UnstructuredDocumentProcessor.

    Returns:
        Configured UnstructuredDocumentProcessor
    """
    return UnstructuredDocumentProcessor()
