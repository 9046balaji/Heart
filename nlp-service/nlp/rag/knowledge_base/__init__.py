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

from .cardiovascular_guidelines import (
    CardiovascularGuidelines,
    get_cardiovascular_guidelines,
)
from .drug_database import (
    DrugDatabase,
    DrugInteraction,
    get_drug_database,
)
from .symptom_checker import (
    SymptomChecker,
    SymptomMapping,
    get_symptom_checker,
)
from .knowledge_loader import (
    KnowledgeLoader,
    load_all_knowledge,
    index_knowledge_to_rag,
)

__all__ = [
    # Cardiovascular
    "CardiovascularGuidelines",
    "get_cardiovascular_guidelines",
    # Drugs
    "DrugDatabase",
    "DrugInteraction",
    "get_drug_database",
    # Symptoms
    "SymptomChecker",
    "SymptomMapping",
    "get_symptom_checker",
    # Loading
    "KnowledgeLoader",
    "load_all_knowledge",
    "index_knowledge_to_rag",
]
