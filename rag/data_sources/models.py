"""
Unified Schema for Medical Knowledge Sources

This module defines the common data structures used across all three medical data sources:
- Tier 1: StatPearls (Clinical Guidelines)
- Tier 1: Textbooks (Medical Theory)
- Tier 2: PubMed (Research Abstracts)

All sources are normalized to this schema before insertion into the vector database.
"""


from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, List, Any
from datetime import datetime
import json
from abc import ABC, abstractmethod


class SourceTier(str, Enum):
    """Priority tier for retrieval routing"""
    TIER_1_STATPEARLS = "tier_1_statpearls"
    TIER_1_TEXTBOOKS = "tier_1_textbooks"
    TIER_2_PUBMED = "tier_2_pubmed"


class DocumentSource(str, Enum):
    """Source identifier"""
    STATPEARLS = "statpearls"
    TEXTBOOKS = "textbooks"
    PUBMED = "pubmed"


class ReviewStatus(str, Enum):
    """Quality/verification status"""
    VERIFIED = "verified"  # Peer-reviewed, authoritative
    PREPRINT = "preprint"  # Under review or preliminary
    ARCHIVED = "archived"  # Older but still valid
    DEPRECATED = "deprecated"  # Outdated, use with caution


@dataclass
class MedicalDocument:
    """
    Unified schema for all medical knowledge sources
    
    Attributes:
        document_id: Unique identifier per source (e.g., "sp_12345" or "pm_PMID")
        title: Document/snippet title
        content: Main text content for retrieval
        source: Which dataset this came from
        tier: Retrieval priority tier
        
        source_url: Link to original (if available)
        publication_date: When published/updated
        authors: Creator(s)
        mesh_terms: Medical Subject Headings (PubMed)
        
        confidence_score: 0.0-1.0 (Tier 1: 1.0, PubMed: 0.6-0.9)
        review_status: Verification/quality status
        update_date: Last modification date
        
        keywords: Search keywords
        related_conditions: Medical conditions mentioned
        clinical_context: Diagnostic/treatment context
        
        embedding_token_count: Tokens used for embedding
        last_retrieved: For usage tracking
        retrieval_count: How many times used
    """
    
    # === CORE CONTENT ===
    document_id: str  # Unique per source
    title: str
    content: str  # Main retrievable text
    source: DocumentSource
    tier: SourceTier
    
    # === METADATA ===
    source_url: Optional[str] = None
    publication_date: Optional[datetime] = None
    authors: Optional[List[str]] = field(default_factory=list)
    mesh_terms: Optional[List[str]] = field(default_factory=list)  # PubMed only
    
    # === QUALITY METRICS ===
    confidence_score: float = 1.0  # Default to Tier 1 confidence
    review_status: ReviewStatus = ReviewStatus.VERIFIED
    update_date: datetime = field(default_factory=datetime.now)
    
    # === RETRIEVAL HINTS ===
    keywords: Optional[List[str]] = field(default_factory=list)
    related_conditions: Optional[List[str]] = field(default_factory=list)
    clinical_context: Optional[str] = None  # "diagnosis", "treatment", "prevention"
    
    # === PROCESSING TRACKING ===
    embedding_token_count: Optional[int] = None
    last_retrieved: Optional[datetime] = None
    retrieval_count: int = 0
    
    # === INTERNAL BOOKKEEPING ===
    created_at: datetime = field(default_factory=datetime.now)
    chunk_index: int = 0  # For documents split into multiple chunks
    chunk_total: Optional[int] = None
    
    def __post_init__(self):
        """Validate and normalize data after initialization"""
        if not isinstance(self.source, DocumentSource):
            self.source = DocumentSource(self.source)
        
        if not isinstance(self.tier, SourceTier):
            self.tier = SourceTier(self.tier)
        
        if not isinstance(self.review_status, ReviewStatus):
            self.review_status = ReviewStatus(self.review_status)
        
        # Validate confidence score
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(f"Confidence score must be 0.0-1.0, got {self.confidence_score}")
    
    def to_vector_store_doc(self) -> Dict[str, Any]:
        """
        Convert to format compatible with Chroma vector store
        
        Returns:
            Dictionary with 'id', 'document', and 'metadata' keys
        """
        return {
            "id": self.document_id,
            "document": self.content,
            "metadata": {
                "title": self.title,
                "source": self.source.value,
                "tier": self.tier.value,
                "confidence_score": self.confidence_score,
                "review_status": self.review_status.value,
                "publication_date": self.publication_date.isoformat() if self.publication_date else None,
                "mesh_terms": ",".join(self.mesh_terms) if self.mesh_terms else None,
                "clinical_context": self.clinical_context,
                "source_url": self.source_url,
                "chunk_index": self.chunk_index,
                "chunk_total": self.chunk_total,
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with serializable types"""
        data = asdict(self)
        # Convert enums to strings
        data['source'] = self.source.value
        data['tier'] = self.tier.value
        data['review_status'] = self.review_status.value
        # Convert datetimes to ISO strings
        data['publication_date'] = self.publication_date.isoformat() if self.publication_date else None
        data['update_date'] = self.update_date.isoformat() if self.update_date else None
        data['last_retrieved'] = self.last_retrieved.isoformat() if self.last_retrieved else None
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        return data
    
    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MedicalDocument':
        """Deserialize from dictionary"""
        # Convert string dates back to datetime
        if isinstance(data.get('publication_date'), str):
            data['publication_date'] = datetime.fromisoformat(data['publication_date'])
        if isinstance(data.get('update_date'), str):
            data['update_date'] = datetime.fromisoformat(data['update_date'])
        if isinstance(data.get('last_retrieved'), str):
            data['last_retrieved'] = datetime.fromisoformat(data['last_retrieved'])
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MedicalDocument':
        """Deserialize from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class DocumentLoader(ABC):
    """
    Abstract base class for all data source loaders.
    
    Concrete implementations:
    - TextbooksLoader
    - StatPearlsLoader
    - PubMedStreamer
    """
    
    @abstractmethod
    def load(self) -> List[MedicalDocument]:
        """Load documents from source"""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate loader configuration"""
        pass


@dataclass
class LoaderStats:
    """Statistics from a loader run"""
    source: DocumentSource
    total_documents: int
    total_tokens: int
    average_tokens_per_doc: float
    load_time_seconds: float
    success_count: int
    error_count: int
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def summary(self) -> str:
        """Human-readable summary"""
        return f"""
        {self.source.value.upper()} Loading Summary:
        ─────────────────────────────────
        ✓ Documents Loaded: {self.success_count:,}
        ✗ Errors: {self.error_count:,}
        ├─ Total Tokens: {self.total_tokens:,}
        ├─ Avg Tokens/Doc: {self.average_tokens_per_doc:.1f}
        └─ Time: {self.load_time_seconds:.1f}s
        """


# Constants for different source configurations

TIER_1_CONFIDENCE = 1.0  # StatPearls and Textbooks are authoritative
TIER_2_PUBMED_HIGH = 0.85  # Recent, high-impact journals
TIER_2_PUBMED_MEDIUM = 0.70  # Standard research
TIER_2_PUBMED_LOW = 0.55  # Preprints, specialized topics

# Default batch sizes for streaming
DEFAULT_BATCH_SIZE = 1000  # Documents per batch
PUBMED_BATCH_SIZE = 500  # Smaller batches for PubMed due to size
TEXTBOOKS_BATCH_SIZE = 5000  # All textbooks fit in one batch

# Memory limits
PUBMED_MAX_BATCH_MEMORY_MB = 500  # Max RAM per batch
EMBEDDING_CACHE_SIZE_GB = 3  # Keep embeddings in cache

