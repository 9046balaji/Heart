"""
Unified Knowledge Ingestion Pipeline - Consolidates loading, chunking, and embedding.

Provides:
- UnifiedKnowledgeIngestion: Single interface for end-to-end data processing
- Proper document chunking through ContextualMedicalChunker
- Entity boundary preservation
- Vector store integration (embed_and_store workflow)
- Integration with KnowledgeLoaderSingleton for caching
- Validation and error handling
"""

import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import time

from .knowledge_loader import KnowledgeLoaderSingleton
from .contextual_chunker import ContextualMedicalChunker, MedicalChunk, DrugDictionary
from ..deepdoc_table_parser import DeepDocTableParser

try:
    from rag.raptor_retrieval import RAPTORBuilder, RAPTORIndexManager
    RAPTOR_AVAILABLE = True
except ImportError:
    RAPTOR_AVAILABLE = False

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Supported document types for ingestion."""
    DRUG_INFO = "drug_info"
    GUIDELINE = "guideline"
    SYMPTOM_GUIDE = "symptom_guide"
    INTERACTION = "interaction"
    MEDICAL_TEXT = "medical_text"
    UNSPECIFIED = "unspecified"


@dataclass
class IngestionStats:
    """Statistics from ingestion process."""
    documents_processed: int = 0
    chunks_created: int = 0
    entities_detected: int = 0
    total_text_bytes: int = 0
    errors: int = 0
    processing_time_seconds: float = 0.0


class UnifiedKnowledgeIngestion:
    """
    Unified pipeline for document ingestion and chunking.

    Features:
    - Load raw documents from JSON files
    - Process through medical-aware chunker
    - Preserve entity boundaries
    - Validate chunk quality
    - Cache processed results
    - Track ingestion statistics

    Example:
        ingestion = UnifiedKnowledgeIngestion()

        # Ingest all drugs with proper chunking
        stats = ingestion.ingest_drugs()
        print(f"Created {stats.chunks_created} chunks from {stats.documents_processed} drugs")

        # Or process custom documents
        chunks = ingestion.process_documents(
            documents=raw_documents,
            doc_type=DocumentType.GUIDELINE
        )
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        chunk_size: int = 1500,
        min_chunk_size: int = 200,
        overlap_sentences: int = 1,
    ):
        """
        Initialize unified ingestion pipeline.

        Args:
            data_dir: Path to data directory (uses KnowledgeLoaderSingleton default if None)
            chunk_size: Maximum chunk size in characters
            min_chunk_size: Minimum chunk size to preserve
            overlap_sentences: Sentences to overlap between chunks
        """
        self.knowledge_loader = KnowledgeLoaderSingleton.get_instance()
        self.chunker = ContextualMedicalChunker(
            max_chunk_size=chunk_size,
            min_chunk_size=min_chunk_size,
            overlap_sentences=overlap_sentences,
            drug_dictionary=DrugDictionary.get_instance(),
        )

        if data_dir:
            self.knowledge_loader.set_data_dir(data_dir)

        self.table_parser = DeepDocTableParser()
        self._stats = IngestionStats()

    def process_documents(
        self,
        documents: List[Dict[str, Any]],
        doc_type: DocumentType = DocumentType.UNSPECIFIED,
        source: str = "unknown",
    ) -> List[MedicalChunk]:
        """
        Process a list of documents through chunking pipeline.

        Args:
            documents: List of document dicts with 'id' and 'content' keys
            doc_type: Type of document for metadata
            source: Source attribution for documents

        Returns:
            List of processed chunks with metadata

        Raises:
            ValueError: If documents format is invalid
        """
        if not documents:
            logger.warning("No documents provided for processing")
            return []

        chunks = []
        self._stats.documents_processed = 0
        self._stats.errors = 0

        for doc in documents:
            try:
                # Validate document structure
                if not isinstance(doc, dict):
                    logger.warning(f"Skipping non-dict document: {type(doc)}")
                    self._stats.errors += 1
                    continue

                content = doc.get("content") or doc.get("text") or doc.get("data", "")
                doc_id = doc.get("id") or doc.get("_id") or f"doc_{len(chunks)}"

                if not content:
                    logger.debug(f"Skipping empty document {doc_id}")
                    self._stats.errors += 1
                    continue

                # Process through chunker
                doc_chunks = self.chunker.chunk_document(
                    text=str(content),
                    doc_type=doc_type.value,
                    source=source,
                    doc_id=doc_id,
                )

                # Track statistics
                self._stats.documents_processed += 1
                self._stats.chunks_created += len(doc_chunks)
                self._stats.total_text_bytes += len(str(content))

                # Count entities
                for chunk in doc_chunks:
                    self._stats.entities_detected += len(chunk.entities)

                chunks.extend(doc_chunks)

                logger.debug(f"Processed document {doc_id}: {len(doc_chunks)} chunks")

            except Exception as e:
                logger.error(f"Failed to process document {doc.get('id', 'unknown')}: {e}")
                self._stats.errors += 1
                continue

        logger.info(
            f"✅ Processed {self._stats.documents_processed} documents → "
            f"{self._stats.chunks_created} chunks, "
            f"{self._stats.entities_detected} entities detected"
        )

        return chunks

    def ingest_drugs(
        self,
        filename: str = "drugs.json",
    ) -> IngestionStats:
        """
        Ingest drugs from JSON file with proper chunking.

        Args:
            filename: Name of drugs JSON file in data directory

        Returns:
            IngestionStats with processing results
        """
        logger.info(f"Starting drug ingestion from {filename}...")

        # Load drugs using knowledge loader (with caching)
        drugs = self.knowledge_loader.get_drugs()

        if not drugs:
            logger.warning(f"No drugs found in {filename}")
            return self._stats

        # Process through unified pipeline
        chunks = self.process_documents(
            documents=drugs,
            doc_type=DocumentType.DRUG_INFO,
            source="drugs.json",
        )

        logger.info(
            f"✅ Drug ingestion complete: "
            f"{self._stats.documents_processed} drugs → {len(chunks)} chunks"
        )

        return self._stats

    def ingest_guidelines(
        self,
        filename: str = "guidelines.json",
    ) -> IngestionStats:
        """
        Ingest medical guidelines from JSON file.

        Args:
            filename: Name of guidelines JSON file

        Returns:
            IngestionStats with processing results
        """
        logger.info(f"Starting guideline ingestion from {filename}...")

        guidelines = self.knowledge_loader.get_guidelines()

        if not guidelines:
            logger.warning(f"No guidelines found in {filename}")
            return self._stats

        chunks = self.process_documents(
            documents=guidelines,
            doc_type=DocumentType.GUIDELINE,
            source="guidelines.json",
        )

        logger.info(
            f"✅ Guideline ingestion complete: "
            f"{self._stats.documents_processed} guidelines → {len(chunks)} chunks"
        )

        return self._stats

    def ingest_symptoms(
        self,
        filename: str = "symptoms.json",
    ) -> IngestionStats:
        """
        Ingest symptom guides from JSON file.

        Args:
            filename: Name of symptoms JSON file

        Returns:
            IngestionStats with processing results
        """
        logger.info(f"Starting symptom ingestion from {filename}...")

        symptoms = self.knowledge_loader.get_symptoms()

        if not symptoms:
            logger.warning(f"No symptoms found in {filename}")
            return self._stats

        chunks = self.process_documents(
            documents=symptoms,
            doc_type=DocumentType.SYMPTOM_GUIDE,
            source="symptoms.json",
        )

        logger.info(
            f"✅ Symptom ingestion complete: "
            f"{self._stats.documents_processed} symptoms → {len(chunks)} chunks"
        )

        return self._stats

    def ingest_pdf(
        self,
        pdf_path: str,
        doc_type: DocumentType = DocumentType.MEDICAL_TEXT,
    ) -> List[MedicalChunk]:
        """
        Ingest a PDF file, extracting tables as atomic chunks.
        
        Args:
            pdf_path: Path to PDF file
            doc_type: Document type for metadata
            
        Returns:
            List of processed chunks
        """
        logger.info(f"📄 Ingesting PDF: {pdf_path}")
        
        if not Path(pdf_path).exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return []
            
        chunks = []
        
        # 1. Extract tables using DeepDoc parser
        tables = self.table_parser.extract_tables_from_pdf(pdf_path)
        
        if tables:
            logger.info(f"Found {len(tables)} tables in PDF")
            
            # Create atomic table chunks
            table_chunks_data = self.table_parser.create_atomic_chunks(tables)
            
            # Convert to MedicalChunk objects
            for i, chunk_data in enumerate(table_chunks_data):
                chunk = MedicalChunk(
                    chunk_id=f"table_{Path(pdf_path).stem}_{i}",
                    doc_id=Path(pdf_path).name,
                    content=chunk_data["content"],
                    chunk_type="table",
                    source=pdf_path,
                    chunk_index=i,
                    metadata=chunk_data["metadata"]
                )
                chunks.append(chunk)
                self._stats.chunks_created += 1
        
        # 2. Extract text (TODO: Use PyMuPDF to extract non-table text)
        # For now, we focus on tables as per the requirement.
        # Future enhancement: Interleave text and tables.
        
        self._stats.documents_processed += 1
        return chunks

    def ingest_all(
        self,
        include_drugs: bool = True,
        include_guidelines: bool = True,
        include_symptoms: bool = True,
    ) -> Dict[str, IngestionStats]:
        """
        Ingest all available knowledge sources.

        Args:
            include_drugs: Whether to ingest drugs
            include_guidelines: Whether to ingest guidelines
            include_symptoms: Whether to ingest symptoms

        Returns:
            Dictionary mapping source to IngestionStats
        """
        results = {}

        if include_drugs:
            logger.info("📦 Ingesting drugs...")
            results["drugs"] = self.ingest_drugs()

        if include_guidelines:
            logger.info("📦 Ingesting guidelines...")
            results["guidelines"] = self.ingest_guidelines()

        if include_symptoms:
            logger.info("📦 Ingesting symptoms...")
            results["symptoms"] = self.ingest_symptoms()

        # Summary
        total_docs = sum(s.documents_processed for s in results.values())
        total_chunks = sum(s.chunks_created for s in results.values())
        total_entities = sum(s.entities_detected for s in results.values())

        logger.info(
            f"\n{'='*60}\n"
            f"🎯 INGESTION SUMMARY\n"
            f"{'='*60}\n"
            f"Documents processed:  {total_docs}\n"
            f"Chunks created:       {total_chunks}\n"
            f"Entities detected:    {total_entities}\n"
            f"{'='*60}"
        )

        return results

    def validate_chunk_quality(self, chunk: MedicalChunk) -> Dict[str, Any]:
        """
        Validate a chunk for quality metrics.

        Args:
            chunk: MedicalChunk to validate

        Returns:
            Dictionary with validation results
        """
        validation = {
            "is_valid": True,
            "warnings": [],
            "metrics": {
                "char_count": len(chunk.content),
                "word_count": len(chunk.content.split()),
                "entity_count": len(chunk.entities),
                "type": chunk.chunk_type,
            },
        }

        # Check size
        if len(chunk.content) < self.chunker.min_chunk_size:
            validation["warnings"].append(
                f"Chunk too small ({len(chunk.content)} chars, min {self.chunker.min_chunk_size})"
            )
            validation["is_valid"] = False

        if len(chunk.content) > self.chunker.max_chunk_size:
            validation["warnings"].append(
                f"Chunk too large ({len(chunk.content)} chars, max {self.chunker.max_chunk_size})"
            )
            validation["is_valid"] = False

        # Check entities
        if len(chunk.entities) == 0:
            validation["warnings"].append("No entities detected in chunk")

        return validation

    def embed_and_store(
        self,
        chunks: List[MedicalChunk],
        vector_store: Any,
        embedding_service: Any,
        batch_size: int = 10,
    ) -> Tuple[int, int, float]:
        """
        Embed chunks and store them in vector store (full pipeline).

        Args:
            chunks: List of MedicalChunk objects to embed and store
            vector_store: Vector store instance (must have add_document method)
            embedding_service: Embedding service instance (must have embed_text method)
            batch_size: Number of chunks to process in parallel

        Returns:
            Tuple of (chunks_embedded, chunks_failed, duration_seconds)

        Raises:
            ValueError: If chunks, vector_store, or embedding_service is None
        """
        if not chunks:
            logger.warning("No chunks provided for embedding and storage")
            return (0, 0, 0.0)

        if vector_store is None:
            raise ValueError("Vector store not initialized")

        if embedding_service is None:
            raise ValueError("Embedding service not initialized")

        logger.info(f"🔄 Starting embed and store pipeline for {len(chunks)} chunks...")

        start_time = time.time()
        chunks_embedded = 0
        chunks_failed = 0

        try:
            # Process chunks in batches
            for batch_start in range(0, len(chunks), batch_size):
                batch_end = min(batch_start + batch_size, len(chunks))
                batch = chunks[batch_start:batch_end]

                logger.debug(f"Processing batch {batch_start//batch_size + 1}: {len(batch)} chunks")

                for chunk in batch:
                    try:
                        # Generate embedding for chunk
                        embedding = embedding_service.embed_text(chunk.content)

                        # Store in vector store with metadata
                        vector_store.add_document(
                            doc_id=chunk.doc_id,
                            content=chunk.content,
                            embedding=embedding,
                            metadata={
                                "type": chunk.chunk_type,
                                "source": chunk.source,
                                "entities": [
                                    {"name": e.get("name"), "type": e.get("type")}
                                    for e in chunk.entities
                                ],
                                "chunk_index": chunk.chunk_index,
                                "has_overlap": chunk.has_overlap,
                            },
                        )

                        chunks_embedded += 1

                    except Exception as e:
                        logger.error(f"Failed to embed/store chunk {chunk.doc_id}: {e}")
                        chunks_failed += 1
                        continue

        except Exception as e:
            logger.error(f"Batch processing error: {e}")

        duration_seconds = time.time() - start_time

        logger.info(
            f"✅ Embed and store complete: "
            f"{chunks_embedded} embedded, {chunks_failed} failed, "
            f"{duration_seconds:.2f}s elapsed"
        )

        return (chunks_embedded, chunks_failed, duration_seconds)

    async def build_raptor_index(
        self,
        chunks: List[MedicalChunk],
        llm_gateway: Any,
        embedding_service: Any,
        doc_id: str = "combined_knowledge"
    ) -> bool:
        """
        Build RAPTOR tree from chunks and store it.
        
        Args:
            chunks: List of chunks to index
            llm_gateway: LLM for summarization
            embedding_service: Embedding service
            doc_id: Identifier for the tree
            
        Returns:
            True if successful
        """
        if not RAPTOR_AVAILABLE:
            logger.warning("RAPTOR modules not available, skipping tree building")
            return False
            
        logger.info(f"🦖 Building RAPTOR tree for {len(chunks)} chunks...")
        
        try:
            # Convert MedicalChunks to dicts expected by RAPTOR
            raptor_chunks = [
                {
                    "content": c.content,
                    "metadata": {
                        "source": c.source,
                        "type": c.chunk_type,
                        "entities": [e.get("name") for e in c.entities]
                    }
                }
                for c in chunks
            ]
            
            builder = RAPTORBuilder(
                llm_gateway=llm_gateway,
                embedding_model=embedding_service
            )
            
            tree = await builder.build_tree(raptor_chunks, document_id=doc_id)
            
            # Store tree
            manager = RAPTORIndexManager()
            manager.store_tree(tree)
            
            logger.info(f"✅ RAPTOR tree built and stored for {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"RAPTOR tree building failed: {e}")
            return False

    def ingest_and_store_all(
        self,
        vector_store: Any,
        embedding_service: Any,
        include_drugs: bool = True,
        include_guidelines: bool = True,
        include_symptoms: bool = True,
    ) -> Dict[str, Any]:
        """
        End-to-end ingestion pipeline: load → chunk → embed → store.

        Args:
            vector_store: Vector store instance
            embedding_service: Embedding service instance
            include_drugs: Whether to ingest drugs
            include_guidelines: Whether to ingest guidelines
            include_symptoms: Whether to ingest symptoms

        Returns:
            Dictionary with detailed results for each source
        """
        logger.info("🚀 Starting end-to-end ingestion pipeline...")

        results = {}
        all_chunks = []

        # Phase 1: Load and chunk all data
        if include_drugs:
            logger.info("📦 Loading and chunking drugs...")
            drugs = self.knowledge_loader.get_drugs()
            drug_chunks = self.process_documents(
                documents=drugs,
                doc_type=DocumentType.DRUG_INFO,
                source="drugs.json",
            )
            all_chunks.extend(drug_chunks)
            results["drugs"] = {
                "documents": len(drugs),
                "chunks": len(drug_chunks),
                "status": "chunked",
            }

        if include_guidelines:
            logger.info("📦 Loading and chunking guidelines...")
            guidelines = self.knowledge_loader.get_guidelines()
            guideline_chunks = self.process_documents(
                documents=guidelines,
                doc_type=DocumentType.GUIDELINE,
                source="guidelines.json",
            )
            all_chunks.extend(guideline_chunks)
            results["guidelines"] = {
                "documents": len(guidelines),
                "chunks": len(guideline_chunks),
                "status": "chunked",
            }

        if include_symptoms:
            logger.info("📦 Loading and chunking symptoms...")
            symptoms = self.knowledge_loader.get_symptoms()
            symptom_chunks = self.process_documents(
                documents=symptoms,
                doc_type=DocumentType.SYMPTOM_GUIDE,
                source="symptoms.json",
            )
            all_chunks.extend(symptom_chunks)
            results["symptoms"] = {
                "documents": len(symptoms),
                "chunks": len(symptom_chunks),
                "status": "chunked",
            }

        # Phase 2: Embed and store all chunks
        logger.info(f"📤 Embedding and storing {len(all_chunks)} total chunks...")

        chunks_embedded, chunks_failed, embed_time = self.embed_and_store(
            chunks=all_chunks,
            vector_store=vector_store,
            embedding_service=embedding_service,
        )

        results["summary"] = {
            "total_documents": sum(r["documents"] for r in results.values() if isinstance(r, dict)),
            "total_chunks": len(all_chunks),
            "chunks_embedded": chunks_embedded,
            "chunks_failed": chunks_failed,
            "embed_time_seconds": embed_time,
            "status": "complete" if chunks_failed == 0 else "partial_failure",
        }

        logger.info(
            f"\n{'='*60}\n"
            f"🎯 END-TO-END INGESTION COMPLETE\n"
            f"{'='*60}\n"
            f"Documents:         {results['summary']['total_documents']}\n"
            f"Chunks created:    {results['summary']['total_chunks']}\n"
            f"Chunks embedded:   {chunks_embedded}\n"
            f"Chunks failed:     {chunks_failed}\n"
            f"Embed time:        {embed_time:.2f}s\n"
            f"{'='*60}"
        )

        return results

    def get_stats(self) -> IngestionStats:
        """Get current ingestion statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset ingestion statistics."""
        self._stats = IngestionStats()


# ============================================================================
# Backward Compatibility Facade
# ============================================================================

_ingestion_instance: Optional[UnifiedKnowledgeIngestion] = None


def get_unified_ingestion() -> UnifiedKnowledgeIngestion:
    """
    Get the default unified ingestion instance (singleton pattern).

    Returns:
        UnifiedKnowledgeIngestion instance
    """
    global _ingestion_instance
    if _ingestion_instance is None:
        _ingestion_instance = UnifiedKnowledgeIngestion()
    return _ingestion_instance


def ingest_drugs() -> IngestionStats:
    """Ingest drugs using default ingestion pipeline."""
    return get_unified_ingestion().ingest_drugs()


def ingest_guidelines() -> IngestionStats:
    """Ingest guidelines using default ingestion pipeline."""
    return get_unified_ingestion().ingest_guidelines()


def ingest_symptoms() -> IngestionStats:
    """Ingest symptoms using default ingestion pipeline."""
    return get_unified_ingestion().ingest_symptoms()


def ingest_all(
    include_drugs: bool = True,
    include_guidelines: bool = True,
    include_symptoms: bool = True,
) -> Dict[str, IngestionStats]:
    """Ingest all sources using default ingestion pipeline."""
    return get_unified_ingestion().ingest_all(
        include_drugs=include_drugs,
        include_guidelines=include_guidelines,
        include_symptoms=include_symptoms,
    )
