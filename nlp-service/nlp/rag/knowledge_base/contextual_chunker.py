"""
Contextual Medical Chunker for Knowledge Base.

Medical-aware chunking that preserves semantic completeness and entity boundaries.
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MedicalChunk:
    """A semantically complete chunk of medical content."""
    content: str
    chunk_type: str  # "drug", "condition", "guideline", "interaction"
    entities: List[Dict[str, str]]  # [{"type": "drug", "name": "Lisinopril"}]
    section_context: str  # Parent section heading
    source_metadata: Dict
    char_start: int
    char_end: int


class DrugDictionary:
    """
    High-performance drug name lookup using O(1) set operations.
    
    ⚠️ IMPORTANT: Do NOT use hardcoded regex patterns for drug detection!
    A small regex like `(Lisinopril|Metoprolol|...)` will miss common drugs
    like "Acetaminophen", "Gabapentin", "Hydrocodone", etc.
    
    Instead, load a comprehensive drug list from file for O(1) lookups.
    """
    
    _instance = None
    _drug_set: set = None
    
    # Path to drug dictionary file (one drug name per line)
    DRUG_FILE_PATH = "data/dictionaries/common_drugs.txt"
    
    # Fallback: Top 100 most common generic drugs if file not found
    FALLBACK_DRUGS = {
        "acetaminophen", "ibuprofen", "aspirin", "lisinopril", "metoprolol",
        "atorvastatin", "amlodipine", "metformin", "omeprazole", "losartan",
        "gabapentin", "hydrocodone", "amoxicillin", "azithromycin", "prednisone",
        "albuterol", "levothyroxine", "pantoprazole", "furosemide", "tramadol",
        "sertraline", "fluoxetine", "escitalopram", "duloxetine", "trazodone",
        "alprazolam", "lorazepam", "clonazepam", "diazepam", "zolpidem",
        "warfarin", "clopidogrel", "rivaroxaban", "apixaban", "enoxaparin",
        "insulin", "glipizide", "sitagliptin", "empagliflozin", "liraglutide",
        "carvedilol", "propranolol", "atenolol", "diltiazem", "verapamil",
        "hydrochlorothiazide", "chlorthalidone", "spironolactone", "triamterene",
        "lisinopril", "enalapril", "ramipril", "benazepril", "captopril",
        "valsartan", "olmesartan", "irbesartan", "candesartan", "telmisartan",
        "simvastatin", "rosuvastatin", "pravastatin", "lovastatin", "pitavastatin",
        "montelukast", "fluticasone", "budesonide", "tiotropium", "formoterol",
        "cetirizine", "loratadine", "fexofenadine", "diphenhydramine",
        "ranitidine", "famotidine", "esomeprazole", "lansoprazole", "dexlansoprazole",
        "methotrexate", "hydroxychloroquine", "sulfasalazine", "leflunomide",
        "morphine", "oxycodone", "fentanyl", "hydromorphone", "buprenorphine",
        "cyclobenzaprine", "methocarbamol", "baclofen", "tizanidine",
        "ciprofloxacin", "levofloxacin", "doxycycline", "trimethoprim",
        "fluconazole", "nystatin", "clotrimazole", "terbinafine",
        "valacyclovir", "acyclovir", "oseltamivir",
        "digoxin", "amiodarone", "sotalol", "flecainide",
    }
    
    @classmethod
    def get_instance(cls) -> "DrugDictionary":
        """Singleton pattern for drug dictionary."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize drug dictionary from file or fallback."""
        self._load_drugs()
    
    def _load_drugs(self) -> None:
        """Load drug names from file into set for O(1) lookup."""
        try:
            drug_file = Path(__file__).parent / self.DRUG_FILE_PATH
            
            if drug_file.exists():
                with open(drug_file, 'r', encoding='utf-8') as f:
                    # Load all drugs, lowercase for case-insensitive matching
                    self._drug_set = {
                        line.strip().lower() 
                        for line in f 
                        if line.strip() and not line.startswith('#')
                    }
                logger.info(f"Loaded {len(self._drug_set)} drugs from {drug_file}")
            else:
                logger.warning(f"Drug file not found at {drug_file}, using fallback")
                self._drug_set = self.FALLBACK_DRUGS.copy()
                
        except Exception as e:
            logger.error(f"Failed to load drug dictionary: {e}")
            self._drug_set = self.FALLBACK_DRUGS.copy()
    
    def is_drug(self, word: str) -> bool:
        """O(1) check if word is a known drug name."""
        return word.lower() in self._drug_set
    
    def find_drugs_in_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Find all drug mentions in text using O(1) lookups.
        
        Args:
            text: Input text to scan
            
        Returns:
            List of drug matches with positions
        """
        matches = []
        # Split on word boundaries
        words = re.findall(r'\b[A-Za-z]{3,}\b', text)
        
        # Track positions for each word occurrence
        pos = 0
        for word in words:
            word_pos = text.find(word, pos)
            if self.is_drug(word):
                matches.append({
                    "type": "drug",
                    "name": word,
                    "position": word_pos,
                    "confidence": 1.0  # Dictionary match = high confidence
                })
            pos = word_pos + len(word) if word_pos != -1 else pos
        
        return matches
    
    def add_custom_drugs(self, drugs: List[str]) -> None:
        """Add custom drug names to dictionary."""
        for drug in drugs:
            self._drug_set.add(drug.lower())
    
    @property
    def drug_count(self) -> int:
        """Number of drugs in dictionary."""
        return len(self._drug_set)


class ContextualMedicalChunker:
    """
    Medical-aware chunking that preserves semantic completeness.
    
    Strategy:
    1. Parse document structure (sections, lists)
    2. Detect medical entities (drugs, conditions) using dictionary lookup
    3. Create chunks around entity boundaries
    4. Attach rich metadata for filtering
    
    ⚠️ NOTE: Uses DrugDictionary for O(1) drug lookups instead of regex.
    This ensures we don't miss drugs like "Acetaminophen" or "Gabapentin".
    """
    
    # Dosage pattern (keep as regex - finite patterns)
    DOSAGE_PATTERN = re.compile(
        r'\b(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|units?|IU|mEq)\b',
        re.IGNORECASE
    )
    
    # Medical condition patterns (common cardiovascular)
    CONDITION_PATTERN = re.compile(
        r'\b(hypertension|diabetes|heart failure|atrial fibrillation|'
        r'myocardial infarction|stroke|angina|arrhythmia|cardiomyopathy|'
        r'hyperlipidemia|coronary artery disease|CHF|AFib|MI|CAD)\b',
        re.IGNORECASE
    )
    
    SECTION_MARKERS = [
        "Indications", "Dosage", "Side Effects", "Contraindications",
        "Interactions", "Warnings", "Precautions", "Mechanism of Action",
        "Administration", "Pharmacokinetics", "Adverse Reactions"
    ]
    
    def __init__(
        self,
        max_chunk_size: int = 1500,
        min_chunk_size: int = 200,
        overlap_sentences: int = 1,
        drug_dictionary: DrugDictionary = None
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_sentences = overlap_sentences
        # Use singleton drug dictionary for O(1) lookups
        self.drug_dict = drug_dictionary or DrugDictionary.get_instance()
    
    def chunk_document(
        self,
        text: str,
        doc_type: str = "medical_guideline",
        source: str = "unknown"
    ) -> List[MedicalChunk]:
        """
        Chunk a medical document with entity awareness.
        
        Args:
            text: Full document text
            doc_type: Type of document (drug_info, guideline, etc.)
            source: Source attribution
            
        Returns:
            List of semantically complete chunks
        """
        # 1. Parse sections
        sections = self._parse_sections(text)
        
        # 2. Process each section
        chunks = []
        for section in sections:
            section_chunks = self._chunk_section(
                section["content"],
                section["heading"],
                doc_type,
                source
            )
            chunks.extend(section_chunks)
        
        return chunks
    
    def _parse_sections(self, text: str) -> List[Dict]:
        """Identify document sections by headings."""
        sections = []
        current_section = {"heading": "Introduction", "content": "", "start": 0}
        
        lines = text.split('\n')
        pos = 0
        
        for line in lines:
            # Check if line is a section heading
            stripped = line.strip()
            is_heading = (
                any(marker in stripped for marker in self.SECTION_MARKERS) or
                (stripped.endswith(':') and len(stripped) < 50) or
                (stripped.isupper() and len(stripped) < 50)
            )
            
            if is_heading and current_section["content"]:
                sections.append(current_section)
                current_section = {
                    "heading": stripped.rstrip(':'),
                    "content": "",
                    "start": pos
                }
            else:
                current_section["content"] += line + '\n'
            
            pos += len(line) + 1
        
        # Add final section
        if current_section["content"]:
            sections.append(current_section)
        
        return sections
    
    def _chunk_section(
        self,
        content: str,
        section_heading: str,
        doc_type: str,
        source: str
    ) -> List[MedicalChunk]:
        """Chunk a section with entity awareness."""
        chunks = []
        
        # Find all entities in section
        entities = self._extract_entities(content)
        
        # If section is small enough, keep it whole
        if len(content) <= self.max_chunk_size:
            chunks.append(MedicalChunk(
                content=content.strip(),
                chunk_type=self._infer_chunk_type(section_heading, entities),
                entities=entities,
                section_context=section_heading,
                source_metadata={"doc_type": doc_type, "source": source},
                char_start=0,
                char_end=len(content)
            ))
            return chunks
        
        # Split on entity boundaries with proper offset tracking
        return self._split_on_entities(
            content, entities, section_heading, doc_type, source
        )
    
    def _extract_entities(self, text: str) -> List[Dict]:
        """
        Extract medical entities from text.
        
        Uses O(1) dictionary lookup for drugs instead of regex.
        """
        entities = []
        
        # Find drugs using dictionary (O(1) lookup per word)
        drug_matches = self.drug_dict.find_drugs_in_text(text)
        entities.extend(drug_matches)
        
        # Find dosages (regex is fine here - finite patterns)
        for match in self.DOSAGE_PATTERN.finditer(text):
            entities.append({
                "type": "dosage",
                "value": match.group(1),
                "unit": match.group(2),
                "position": match.start()
            })
        
        # Find medical conditions
        for match in self.CONDITION_PATTERN.finditer(text):
            entities.append({
                "type": "condition",
                "name": match.group(0),
                "position": match.start()
            })
        
        return entities
    
    def _infer_chunk_type(
        self,
        section: str,
        entities: List[Dict]
    ) -> str:
        """Infer semantic type of chunk."""
        section_lower = section.lower()
        
        if "interaction" in section_lower:
            return "interaction"
        elif "side effect" in section_lower or "adverse" in section_lower:
            return "side_effects"
        elif "dosage" in section_lower or "dose" in section_lower:
            return "dosage"
        elif "contraindication" in section_lower:
            return "contraindication"
        elif any(e["type"] == "drug" for e in entities):
            return "drug_info"
        else:
            return "general"
    
    def _split_on_entities(
        self,
        content: str,
        entities: List[Dict],
        section: str,
        doc_type: str,
        source: str
    ) -> List[MedicalChunk]:
        """Split content at entity boundaries."""
        chunks = []
        sentences = self._split_sentences_with_offsets(content)
        
        current_sentences = []
        current_length = 0
        current_entities = []
        
        for sent in sentences:
            sent_len = sent['end'] - sent['start']
            
            # Check if adding sentence exceeds limit
            if current_length + sent_len > self.max_chunk_size and current_sentences:
                # Save current chunk
                if current_sentences:
                    chunk_start = current_sentences[0]['start']
                    chunk_end = current_sentences[-1]['end']
                    chunk_content = content[chunk_start:chunk_end]
                    
                    # Find entities in this chunk
                    chunk_entities = [
                        e for e in entities 
                        if e['position'] >= chunk_start and e['position'] < chunk_end
                    ]
                    
                    chunks.append(MedicalChunk(
                        content=chunk_content.strip(),
                        chunk_type=self._infer_chunk_type(section, chunk_entities),
                        entities=chunk_entities,
                        section_context=section,
                        source_metadata={"doc_type": doc_type, "source": source},
                        char_start=chunk_start,
                        char_end=chunk_end
                    ))
                
                # Start new chunk with overlap
                overlap_count = min(len(current_sentences), self.overlap_sentences)
                current_sentences = current_sentences[-overlap_count:] if overlap_count > 0 else []
                current_length = sum((s['end'] - s['start']) for s in current_sentences)
            
            current_sentences.append(sent)
            current_length += sent_len
        
        # Save final chunk
        if current_sentences:
            chunk_start = current_sentences[0]['start']
            chunk_end = current_sentences[-1]['end']
            chunk_content = content[chunk_start:chunk_end]
            
            # Find entities in this chunk
            chunk_entities = [
                e for e in entities 
                if e['position'] >= chunk_start and e['position'] < chunk_end
            ]
            
            chunks.append(MedicalChunk(
                content=chunk_content.strip(),
                chunk_type=self._infer_chunk_type(section, chunk_entities),
                entities=chunk_entities,
                section_context=section,
                source_metadata={"doc_type": doc_type, "source": source},
                char_start=chunk_start,
                char_end=chunk_end
            ))
        
        return chunks
    
    def _split_sentences_with_offsets(self, text: str) -> List[Dict]:
        """
        Split text into sentences while preserving start/end indices.
        
        Returns list of dicts: {'text': str, 'start': int, 'end': int}
        """
        # Find sentence boundaries (punctuation followed by whitespace)
        matches = list(re.finditer(r'(?<=[.!?])\s+', text))
        
        sentences = []
        start = 0
        
        for match in matches:
            # match.start() is the beginning of the WHITESPACE after the sentence
            end = match.start() 
            
            # Extract sentence
            raw_sent = text[start:end]
            if raw_sent.strip():
                sentences.append({
                    'text': raw_sent,
                    'start': start,
                    'end': end
                })
            
            # match.end() is the start of the NEXT sentence
            start = match.end()
        
        # Add the final sentence
        if start < len(text):
            raw_sent = text[start:]
            if raw_sent.strip():
                sentences.append({
                    'text': raw_sent,
                    'start': start,
                    'end': len(text)
                })
        
        return sentences
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Use the offset-aware version and extract just the text
        sentences_with_offsets = self._split_sentences_with_offsets(text)
        return [s['text'] for s in sentences_with_offsets]
