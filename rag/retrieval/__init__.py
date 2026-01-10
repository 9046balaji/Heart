"""
Retrieval Module for HeartGuard Medical RAG System

Provides intelligent query routing and tiered document retrieval:

- Intent Detection: Classifies queries to determine best retrieval strategy
- Tiered Retrieval: Routes to Tier 1 (high-confidence) or Tier 2 (research) sources
- Result Merging: Combines and ranks results by confidence and relevance
- Explainability: Provides reasoning for retrieval decisions

Query Intent Classification:
- GUIDELINE: Medical standards, protocols, best practices
- DIAGNOSIS: Symptom interpretation, disease identification
- RESEARCH: Recent studies, clinical trials, evidence
- DEFINITION: Medical terminology, condition descriptions
- COMPARISON: Drug/treatment comparisons, alternatives
- VALIDATION: Fact-checking, safety verification
"""

from rag.retrieval.fusion_retriever import (
    FusionRetriever,
    clean_query,
    lemmatize_medical_terms,
    SearchResult
)

from rag.retrieval.unified_compressor import (
    UnifiedDocumentCompressor,
    CompressedDocument,
    CompressionStrategy
)

# MedRAG Tiered Retriever (new)
try:
    from rag.retrieval.tiered_retriever import (
        TieredRetriever,
        IntentDetector,
        QueryIntent,
        RetrievalConfig,
    )
except ImportError:
    pass

__all__ = [
    # Fusion Retriever
    "FusionRetriever",
    "clean_query",
    "lemmatize_medical_terms",
    "SearchResult",
    
    # Unified Compressor
    "UnifiedDocumentCompressor",
    "CompressedDocument",
    "CompressionStrategy",
]
