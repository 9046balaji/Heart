"""
Knowledge Loader - Loads all medical knowledge into RAG

This module provides functionality to:
- Load all knowledge bases into RAG vector store
- Support PDF ingestion for additional medical literature
- Index everything for semantic search
- Provide unified knowledge access
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

from .contextual_chunker import ContextualMedicalChunker


class KnowledgeLoader:
    """
    Loads medical knowledge into RAG vector store.

    Features:
    - Load cardiovascular guidelines
    - Load drug database
    - Load symptom information
    - Optional PDF ingestion
    - Progress tracking

    Example:
        loader = KnowledgeLoader(vector_store=my_vector_store)
        stats = loader.load_all()
        print(f"Loaded {stats['total_documents']} documents")
    """

    def __init__(
        self,
        vector_store: Optional[Any] = None,
    ):
        """
        Initialize Knowledge Loader.

        Args:
            vector_store: VectorStore instance for indexing
        """
        self.vector_store = vector_store
        self._stats = {
            "cardiovascular": 0,
            "drugs": 0,
            "symptoms": 0,
            "pdfs": 0,
            "total_documents": 0,
            "last_load": None,
        }

    def set_vector_store(self, vector_store: Any) -> None:
        """Set or update the vector store."""
        self.vector_store = vector_store

    def load_cardiovascular_guidelines(self) -> int:
        """
        Load cardiovascular guidelines into vector store.

        Returns:
            Number of documents indexed
        """
        from .cardiovascular_guidelines import get_cardiovascular_guidelines

        guidelines = get_cardiovascular_guidelines()
        documents = guidelines.to_rag_documents()

        count = 0
        for doc in documents:
            try:
                if self.vector_store:
                    self.vector_store.add_medical_document(
                        doc_id=doc["id"],
                        content=doc["content"],
                        metadata={
                            **doc["metadata"],
                            "loaded_at": datetime.now().isoformat(),
                        },
                    )
                count += 1
            except Exception as e:
                logger.error(f"Failed to index cardiovascular doc {doc['id']}: {e}")

        self._stats["cardiovascular"] = count
        logger.info(f"✅ Loaded {count} cardiovascular guidelines")
        return count

    def load_drug_database(self) -> int:
        """
        Load drug database into vector store.

        Returns:
            Number of documents indexed
        """
        from .drug_database import get_drug_database

        db = get_drug_database()
        documents = db.to_rag_documents()

        count = 0
        for doc in documents:
            try:
                if self.vector_store:
                    self.vector_store.add_medical_document(
                        doc_id=doc["id"],
                        content=doc["content"],
                        metadata={
                            **doc["metadata"],
                            "loaded_at": datetime.now().isoformat(),
                        },
                    )
                count += 1
            except Exception as e:
                logger.error(f"Failed to index drug doc {doc['id']}: {e}")

        self._stats["drugs"] = count
        logger.info(f"✅ Loaded {count} drug documents")
        return count

    def load_symptom_data(self) -> int:
        """
        Load symptom checker data into vector store.

        Returns:
            Number of documents indexed
        """
        from .symptom_checker import get_symptom_checker

        checker = get_symptom_checker()
        documents = checker.to_rag_documents()

        count = 0
        for doc in documents:
            try:
                if self.vector_store:
                    self.vector_store.add_medical_document(
                        doc_id=doc["id"],
                        content=doc["content"],
                        metadata={
                            **doc["metadata"],
                            "loaded_at": datetime.now().isoformat(),
                        },
                    )
                count += 1
            except Exception as e:
                logger.error(f"Failed to index symptom doc {doc['id']}: {e}")

        self._stats["symptoms"] = count
        logger.info(f"✅ Loaded {count} symptom documents")
        return count

    def load_pdf(
        self,
        pdf_path: str,
        source_name: str = None,
        category: str = "medical_literature",
    ) -> int:
        """
        Load a PDF document into vector store.

        Uses PyPDF2 or pdfplumber for text extraction.
        Splits into chunks for embedding.

        Args:
            pdf_path: Path to PDF file
            source_name: Name for source attribution
            category: Document category

        Returns:
            Number of chunks indexed
        """
        try:
            # Try PyPDF2 first
            try:
                import PyPDF2

                with open(pdf_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
            except ImportError:
                # Try pdfplumber
                try:
                    import pdfplumber

                    with pdfplumber.open(pdf_path) as pdf:
                        text = ""
                        for page in pdf.pages:
                            text += page.extract_text() + "\n"
                except ImportError:
                    logger.warning(
                        "No PDF library available. Install PyPDF2 or pdfplumber."
                    )
                    return 0

            # Split into chunks
            chunks = self._chunk_text(text, chunk_size=1000, overlap=200)

            source = source_name or Path(pdf_path).stem

            count = 0
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                try:
                    if self.vector_store:
                        self.vector_store.add_medical_document(
                            doc_id=f"pdf_{source}_{i}",
                            content=chunk,
                            metadata={
                                "source": source,
                                "category": category,
                                "type": "pdf_content",
                                "chunk_index": i,
                                "pdf_path": pdf_path,
                                "loaded_at": datetime.now().isoformat(),
                            },
                        )
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to index PDF chunk {i}: {e}")

            self._stats["pdfs"] += count
            logger.info(f"✅ Loaded PDF '{source}': {count} chunks")
            return count

        except Exception as e:
            logger.error(f"Failed to load PDF {pdf_path}: {e}")
            return 0

    def load_pdfs_from_directory(
        self,
        directory: str,
        category: str = "medical_literature",
    ) -> int:
        """
        Load all PDFs from a directory.

        Args:
            directory: Directory containing PDFs
            category: Document category

        Returns:
            Total chunks indexed
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning(f"Directory not found: {directory}")
            return 0

        total = 0
        for pdf_file in dir_path.glob("*.pdf"):
            count = self.load_pdf(str(pdf_file), category=category)
            total += count

        return total

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> List[str]:
        """
        Split text into overlapping chunks using contextual chunker.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        if not text:
            return []

        # Use contextual chunker for better medical document handling
        chunker = ContextualMedicalChunker(
            max_chunk_size=chunk_size,
            min_chunk_size=200,
            overlap_sentences=overlap // 100,  # Approximate sentence overlap
        )

        # Chunk the document
        chunks = chunker.chunk_document(text, "medical_document", "unknown")

        # Return just the content of each chunk
        return [chunk.content for chunk in chunks]

    def load_all(self) -> Dict[str, Any]:
        """
        Load all knowledge bases.

        Returns:
            Statistics about loaded documents
        """
        logger.info("📚 Loading all medical knowledge...")

        # Load each knowledge base
        self.load_cardiovascular_guidelines()
        self.load_drug_database()
        self.load_symptom_data()

        # Calculate total
        self._stats["total_documents"] = (
            self._stats["cardiovascular"]
            + self._stats["drugs"]
            + self._stats["symptoms"]
            + self._stats["pdfs"]
        )
        self._stats["last_load"] = datetime.now().isoformat()

        logger.info(
            f"✅ Knowledge loading complete: {self._stats['total_documents']} documents"
        )
        return self._stats.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get loading statistics."""
        return self._stats.copy()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def load_all_knowledge(vector_store: Any) -> Dict[str, Any]:
    """
    Convenience function to load all knowledge.

    Args:
        vector_store: VectorStore instance

    Returns:
        Loading statistics
    """
    loader = KnowledgeLoader(vector_store=vector_store)
    return loader.load_all()


async def index_knowledge_to_rag(rag_pipeline: Any) -> Dict[str, Any]:
    """
    Index all knowledge into RAG pipeline.

    Args:
        rag_pipeline: RAGPipeline instance

    Returns:
        Loading statistics
    """
    if not hasattr(rag_pipeline, "vector_store"):
        raise ValueError("RAGPipeline must have a vector_store attribute")

    loader = KnowledgeLoader(vector_store=rag_pipeline.vector_store)
    return loader.load_all()


# =============================================================================
# DIRECT ACCESS TO KNOWLEDGE BASES
# =============================================================================


def get_quick_cardiovascular_info(topic: str) -> Dict[str, Any]:
    """
    Quick access to cardiovascular info without RAG.

    Args:
        topic: Topic to look up

    Returns:
        Information about the topic
    """
    from .cardiovascular_guidelines import get_cardiovascular_guidelines

    guidelines = get_cardiovascular_guidelines()
    return guidelines.get_condition_info(topic)


def get_quick_drug_info(drug_name: str) -> Optional[Dict[str, Any]]:
    """
    Quick access to drug info without RAG.

    Args:
        drug_name: Drug to look up

    Returns:
        Drug information or None
    """
    from .drug_database import get_drug_database

    db = get_drug_database()
    drug = db.get_drug(drug_name)
    return drug.to_dict() if drug else None


def check_drug_interactions_quick(drugs: List[str]) -> List[Dict[str, Any]]:
    """
    Quick drug interaction check without RAG.

    Args:
        drugs: List of drug names

    Returns:
        List of interactions
    """
    from .drug_database import get_drug_database

    db = get_drug_database()
    interactions = db.check_interactions(drugs)
    return [i.to_dict() for i in interactions]


def triage_symptoms_quick(symptoms: List[str]) -> Dict[str, Any]:
    """
    Quick symptom triage without RAG.

    Args:
        symptoms: List of symptoms

    Returns:
        Triage result
    """
    from .symptom_checker import get_symptom_checker

    checker = get_symptom_checker()
    return checker.triage_symptoms(symptoms)


def classify_blood_pressure_quick(systolic: int, diastolic: int) -> Dict[str, Any]:
    """
    Quick blood pressure classification.

    Args:
        systolic: Systolic pressure
        diastolic: Diastolic pressure

    Returns:
        Classification result
    """
    from .cardiovascular_guidelines import get_cardiovascular_guidelines

    guidelines = get_cardiovascular_guidelines()
    return guidelines.classify_blood_pressure(systolic, diastolic)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))

    print("Testing KnowledgeLoader...")

    # Test without vector store (dry run)
    print("\n📚 Testing knowledge access (no vector store):")

    # Quick cardiovascular info
    print("\n❤️ Heart failure info:")
    info = get_quick_cardiovascular_info("heart_failure")
    print(f"  Found {info['found']} guidelines")

    # Quick drug info
    print("\n💊 Lisinopril info:")
    drug = get_quick_drug_info("lisinopril")
    if drug:
        print(f"  Class: {drug['drug_class']}")
        print(f"  Uses: {', '.join(drug['indications'][:2])}...")

    # Quick interaction check
    print("\n⚠️ Drug interactions:")
    interactions = check_drug_interactions_quick(["warfarin", "ibuprofen"])
    for i in interactions:
        print(f"  [{i['severity']}] {i['drug1']} + {i['drug2']}")

    # Quick symptom triage
    print("\n🩺 Symptom triage:")
    triage = triage_symptoms_quick(["chest pain", "shortness of breath"])
    print(f"  Urgency: {triage['urgency']}")
    print(f"  Message: {triage['message']}")

    # Quick BP classification
    print("\n🩺 Blood pressure classification:")
    bp = classify_blood_pressure_quick(145, 92)
    print(f"  {bp['reading']}: {bp['category']}")

    # Test with mock vector store
    print("\n📦 Testing with mock vector store:")

    class MockVectorStore:
        def __init__(self):
            self.documents = []

        def add_medical_document(self, doc_id, content, metadata):
            self.documents.append({"id": doc_id, "content": content[:100]})
            return doc_id

    mock_store = MockVectorStore()
    loader = KnowledgeLoader(vector_store=mock_store)
    stats = loader.load_all()

    print(f"  Cardiovascular: {stats['cardiovascular']} docs")
    print(f"  Drugs: {stats['drugs']} docs")
    print(f"  Symptoms: {stats['symptoms']} docs")
    print(f"  Total: {stats['total_documents']} docs")
    print(f"  Mock store has: {len(mock_store.documents)} documents")

    print("\n✅ KnowledgeLoader tests passed!")
