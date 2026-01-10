"""
Medical Knowledge Base Module for Cardio AI

This module provides structured medical knowledge including:
- Cardiovascular disease guidelines
- Drug interactions database
- Symptom-condition mappings
- Medical terminology definitions
- Treatment protocols

All data is sourced from publicly available medical guidelines
and should NOT be used as a substitute for professional medical advice.
"""

from .knowledge_loader import (
    KnowledgeLoaderSingleton,
)

# Optional imports - may not all be implemented
try:
    from .knowledge_loader import load_all_knowledge
except ImportError:
    load_all_knowledge = None

try:
    from .knowledge_loader import index_knowledge_to_rag
except ImportError:
    index_knowledge_to_rag = None

try:
    from .knowledge_loader import get_quick_cardiovascular_info, get_quick_drug_info, check_drug_interactions_quick, triage_symptoms_quick, classify_blood_pressure_quick
except ImportError:
    get_quick_cardiovascular_info = None
    get_quick_drug_info = None
    check_drug_interactions_quick = None
    triage_symptoms_quick = None
    classify_blood_pressure_quick = None

from .unified_ingestion import (
    UnifiedKnowledgeIngestion,
    DocumentType,
    IngestionStats,
    get_unified_ingestion,
    ingest_drugs,
    ingest_guidelines,
    ingest_symptoms,
    ingest_all,
)

from .contextual_chunker import (
    ContextualMedicalChunker,
    MedicalChunk,
    DrugDictionary,
)

__all__ = [
    # Loading (Refactored Singleton)
    "KnowledgeLoaderSingleton",
    "load_all_knowledge",
    "index_knowledge_to_rag",
    # Direct Access (Backward Compat)
    "get_quick_cardiovascular_info",
    "get_quick_drug_info",
    "check_drug_interactions_quick",
    "triage_symptoms_quick",
    "classify_blood_pressure_quick",
    # Unified Ingestion Pipeline (NEW)
    "UnifiedKnowledgeIngestion",
    "DocumentType",
    "IngestionStats",
    "get_unified_ingestion",
    "ingest_drugs",
    "ingest_guidelines",
    "ingest_symptoms",
    "ingest_all",
    # Chunking Components
    "ContextualMedicalChunker",
    "MedicalChunk",
    "DrugDictionary",
]
