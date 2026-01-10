"""
Multimodal RAG Module for Cardio AI

Provides multimodal document processing capabilities:
- Table extraction from medical PDFs (lab results, vital signs)
- Image analysis for ECG/medical charts
- Context-aware content processing
- Integration with existing RAG pipeline

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    Multimodal RAG Module                        │
    ├─────────────────────────────────────────────────────────────────┤
    │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
    │  │ TableProcessor  │  │ ImageProcessor  │  │ ContextExtractor│  │
    │  │ (Lab results)   │  │ (ECG/Charts)    │  │ (Document ctx)  │  │
    │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
    │           │                    │                    │           │
    │           └────────────────────┼────────────────────┘           │
    │                                ▼                                │
    │              ┌─────────────────────────────────┐                │
    │              │   MultimodalIngestionService    │                │
    │              │   (Bridge to VectorStore)       │                │
    │              └─────────────────────────────────┘                │
    │                                │                                │
    │     ┌──────────────────────────┼──────────────────────────┐     │
    │     ▼                          ▼                          ▼     │
    │  ┌────────────┐  ┌──────────────────────┐  ┌────────────────┐   │
    │  │VLMEnhanced │  │MultimodalQueryService│  │ BatchParser    │   │
    │  │ Retriever  │  │(Query with content)  │  │ (Parallel)     │   │
    │  └────────────┘  └──────────────────────┘  └────────────────┘   │
    │                                │                                │
    │     ┌──────────────────────────┼──────────────────────────┐     │
    │     ▼                          ▼                          ▼     │
    │  ┌────────────┐  ┌──────────────────────┐  ┌────────────────┐   │
    │  │MineruParser│  │   DoclingParser      │  │  BatchMixin    │   │
    │  │ (PDF/OCR)  │  │   (Office docs)      │  │ (Folder proc)  │   │
    │  └────────────┘  └──────────────────────┘  └────────────────┘   │
    └─────────────────────────────────────────────────────────────────┘

Features (adapted from RAG-Anything):
- VLM-Enhanced Queries: Automatic image analysis with vision models
- Multimodal Queries: Query with user-provided tables/equations
- Direct Content Insertion: Insert pre-parsed content without parsing
- Folder Processing: Batch ingest entire directories
- Entity Extraction: Extract entities for knowledge graph
- MinerU Parser: High-fidelity PDF parsing with OCR support
- Docling Parser: Office document parsing (Word, PowerPoint, Excel)
- Batch Processing: Parallel document processing with progress tracking
"""

from .config import MultimodalConfig, ContextConfig
from .processors import (
    TableProcessor,
    ImageProcessor,
    EquationProcessor,
    ContextExtractor,
    DocumentParser,
    ParsedContent,
    ProcessedDocument,
    DocStatus,
    ContentType,
    get_processor_for_type,
)
from .ingestion import (
    MultimodalIngestionService,
    MultimodalRetriever,
    VLMEnhancedRetriever,
    MultimodalQueryService,
    DirectContentInserter,
    FolderProcessor,
    EntityExtractor,
    IngestionResult,
    ChunkData,
)
from .prompts import MEDICAL_PROMPTS

# Document Parsers (from RAG-Anything)
from .parser import (
    Parser,
    MineruParser,
    DoclingParser,
    MineruExecutionError,
)

# Batch Processing (from RAG-Anything)
from .batch_parser import (
    BatchParser,
    BatchProcessingResult,
)
from .batch import BatchMixin

# Query Functionality (from RAG-Anything)
from .query import (
    MultimodalQueryMixin,
    MultimodalQueryService as QueryService,
)

# Utilities (from RAG-Anything)
from .utils import (
    RobustJSONParser,
    validate_image_file,
    encode_image_to_base64,
    get_image_mime_type,
    generate_multimodal_cache_key,
    extract_image_paths_from_context,
    build_vlm_messages,
    get_processor_for_type as get_modal_processor,
    compute_content_hash,
)

__all__ = [
    # Configuration
    "MultimodalConfig",
    "ContextConfig",
    # Processors
    "TableProcessor",
    "ImageProcessor",
    "EquationProcessor",
    "ContextExtractor",
    "DocumentParser",
    "ParsedContent",
    "ProcessedDocument",
    "DocStatus",
    "ContentType",
    "get_processor_for_type",
    # Services
    "MultimodalIngestionService",
    "MultimodalRetriever",
    "VLMEnhancedRetriever",
    "MultimodalQueryService",
    "DirectContentInserter",
    "FolderProcessor",
    "EntityExtractor",
    # Data Classes
    "IngestionResult",
    "ChunkData",
    # Document Parsers
    "Parser",
    "MineruParser",
    "DoclingParser",
    "MineruExecutionError",
    # Batch Processing
    "BatchParser",
    "BatchProcessingResult",
    "BatchMixin",
    # Query Functionality
    "MultimodalQueryMixin",
    "QueryService",
    # Utilities
    "RobustJSONParser",
    "validate_image_file",
    "encode_image_to_base64",
    "get_image_mime_type",
    "generate_multimodal_cache_key",
    "extract_image_paths_from_context",
    "build_vlm_messages",
    "get_modal_processor",
    "compute_content_hash",
    # Prompts
    "MEDICAL_PROMPTS",
]
