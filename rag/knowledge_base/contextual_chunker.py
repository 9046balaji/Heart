"""
Contextual Medical Chunker

Handles intelligent splitting of medical documents into chunks while preserving:
- Entity context (drugs, conditions)
- Sentence boundaries
- Semantic coherence
"""

import logging
import re
import uuid
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class MedicalChunk:
    """
    Represents a chunk of medical text with metadata and entity context.
    """
    chunk_id: str
    doc_id: str
    content: str
    chunk_type: str
    source: str
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    entities: List[Dict[str, str]] = field(default_factory=list)
    has_overlap: bool = False

class DrugDictionary:
    """
    Singleton dictionary of known drugs for entity recognition.
    """
    _instance = None
    
    def __init__(self):
        self.drugs: Set[str] = set()
        # Initialize with some common drugs for fallback
        self.drugs.update([
            "lisinopril", "metformin", "atorvastatin", "amlodipine", 
            "metoprolol", "omeprazole", "losartan", "albuterol", 
            "gabapentin", "hydrochlorothiazide"
        ])
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DrugDictionary()
        return cls._instance
        
    def add_drugs(self, drug_names: List[str]):
        """Add drugs to the dictionary."""
        self.drugs.update(d.lower() for d in drug_names)
        
    def is_drug(self, term: str) -> bool:
        """Check if a term is a known drug."""
        return term.lower() in self.drugs

class ContextualMedicalChunker:
    """
    Chunks medical documents while preserving context and entities.
    """
    
    def __init__(
        self,
        max_chunk_size: int = 1500,
        min_chunk_size: int = 200,
        overlap_sentences: int = 1,
        drug_dictionary: Optional[DrugDictionary] = None
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_sentences = overlap_sentences
        self.drug_dictionary = drug_dictionary
        
        # Use centralized SpaCyService
        self.nlp = None
        self.spacy_service = None
        try:
            from core.services.spacy_service import get_spacy_service
            self.spacy_service = get_spacy_service()
            self.nlp = self.spacy_service.nlp
            logger.info("ContextualMedicalChunker using centralized SpaCyService")
        except Exception as e:
            logger.warning(f"Failed to load SpaCyService: {e}. Using regex fallback.")
        
    def chunk_document(
        self,
        text: str,
        doc_type: str,
        source: str,
        doc_id: str
    ) -> List[MedicalChunk]:
        """
        Split document into contextual chunks.
        
        Args:
            text: Document content
            doc_type: Type of document (guideline, drug_info, etc.)
            source: Source filename or origin
            doc_id: Unique document identifier
            
        Returns:
            List of MedicalChunk objects
        """
        sentences = self._split_sentences(text)
        
        chunks = []
        current_chunk_sentences = []
        current_length = 0
        chunk_index = 0
        
        for i, sentence in enumerate(sentences):
            sentence_len = len(sentence)
            
            # Check if adding this sentence exceeds max size
            # But always keep at least one sentence if it's huge
            if current_chunk_sentences and (current_length + sentence_len > self.max_chunk_size):
                # Finalize current chunk
                chunk_content = " ".join(current_chunk_sentences)
                
                # Only add if it meets minimum size or is the only content we have
                if len(chunk_content) >= self.min_chunk_size or not chunks:
                    chunks.append(self._create_chunk(
                        content=chunk_content,
                        doc_id=doc_id,
                        doc_type=doc_type,
                        source=source,
                        index=chunk_index
                    ))
                    chunk_index += 1
                
                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk_sentences) - self.overlap_sentences)
                current_chunk_sentences = current_chunk_sentences[overlap_start:]
                current_length = sum(len(s) for s in current_chunk_sentences) + len(current_chunk_sentences)
            
            current_chunk_sentences.append(sentence)
            current_length += sentence_len + 1
            
        # Add last chunk
        if current_chunk_sentences:
            chunk_content = " ".join(current_chunk_sentences)
            if len(chunk_content) >= self.min_chunk_size or not chunks:
                chunks.append(self._create_chunk(
                    content=chunk_content,
                    doc_id=doc_id,
                    doc_type=doc_type,
                    source=source,
                    index=chunk_index
                ))
            
        return chunks
        
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences using spaCy or regex."""
        if self.nlp:
            doc = self.nlp(text)
            return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        
        # Fallback regex splitter
        # Look for periods, question marks, exclamation marks followed by space and capital letter
        # Also handles some common abbreviations like Dr. Mr. etc.
        text = text.replace("\n", " ")
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        return [s.strip() for s in sentences if s.strip()]
        
    def _create_chunk(self, content: str, doc_id: str, doc_type: str, source: str, index: int) -> MedicalChunk:
        """Create a MedicalChunk object with entity extraction."""
        entities = []
        
        # Entity extraction using SpaCyService if available
        if self.spacy_service:
            try:
                spacy_entities = self.spacy_service.get_entities(content, include_negated=False)
                for ent in spacy_entities:
                    entities.append({"name": ent["text"], "type": ent["label"]})
            except Exception as e:
                logger.warning(f"SpaCy entity extraction failed: {e}")
        
        # Fallback/Additional extraction using dictionary
        if self.drug_dictionary:
            # Simple tokenization for matching
            words = set(re.findall(r'\b[a-zA-Z]{3,}\b', content.lower()))
            found_drugs = words.intersection(self.drug_dictionary.drugs)
            for drug in found_drugs:
                # Avoid duplicates if already found by spaCy
                if not any(e["name"].lower() == drug for e in entities):
                    entities.append({"name": drug, "type": "DRUG"})
                
        return MedicalChunk(
            chunk_id=f"{doc_id}_{index}",
            doc_id=doc_id,
            content=content,
            chunk_type=doc_type,
            source=source,
            chunk_index=index,
            entities=entities,
            has_overlap=self.overlap_sentences > 0
        )
