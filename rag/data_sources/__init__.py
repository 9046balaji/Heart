"""
Data Sources Module for HeartGuard Medical RAG System

Provides loaders and processors for multiple medical knowledge sources:
- StatPearls: NCBI's curated medical knowledge base (Tier 1 - Authoritative)
- MedRAG Textbooks: Foundational medical education texts (Tier 1 - Authoritative)
- PubMed: Research abstracts and citations (Tier 2 - Research validation)

All sources are normalized to the unified MedicalDocument schema.

Example:
    >>> from rag.data_sources import StatPearlsDownloader, TextbooksLoader, PubMedStreamer
    >>> 
    >>> # Download and process StatPearls (Tier 1)
    >>> statpearls = StatPearlsDownloader(corpus_dir="corpus/statpearls")
    >>> statpearls.full_pipeline()  # download → extract → process → load
    >>> docs = statpearls.documents
    >>>
    >>> # Load textbooks (cached)
    >>> textbooks = TextbooksLoader()
    >>> docs = await textbooks.load()
    >>> print(f"Loaded {len(docs)} textbook snippets")
    >>>
    >>> # Stream PubMed data (memory-safe)
    >>> pubmed = PubMedStreamer()
    >>> async for batch in pubmed.stream(batch_size=500):
    ...     print(f"Processing batch of {len(batch)} documents")
"""

__version__ = "0.1.0"

from .models import (
    MedicalDocument,
    DocumentSource,
    SourceTier,
    ReviewStatus,
    DocumentLoader,
    LoaderStats,
)

# Data source loaders
from .statpearls_downloader import StatPearlsDownloader
from .textbooks_loader import TextbooksLoader
from .pubmed_streaming import PubMedStreamer

__all__ = [
    # Models
    "MedicalDocument",
    "DocumentSource",
    "SourceTier",
    "ReviewStatus",
    "DocumentLoader",
    "LoaderStats",
    # Loaders
    "StatPearlsDownloader",
    "TextbooksLoader",
    "PubMedStreamer",
]
