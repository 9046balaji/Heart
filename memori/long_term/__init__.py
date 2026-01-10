"""
Long-term Memory Module for Memori

Provides persistent fact extraction and memory consolidation for AI agents.
Supports background processing and async memory operations.
"""

from .fact_extractor import (
    FactExtractor,
    MemoryExtractionWorker,
    get_fact_extractor,
    get_extraction_worker,
)

__all__ = [
    "FactExtractor",
    "MemoryExtractionWorker",
    "get_fact_extractor",
    "get_extraction_worker",
]
