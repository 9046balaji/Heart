"""
Configuration for Multimodal RAG Processing

Adapted from RAG-Anything for medical domain use cases.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


def get_env_value(key: str, default, value_type=str):
    """Get environment variable with type conversion."""
    value = os.getenv(key, default)
    if value_type == bool:
        return str(value).lower() in ("true", "1", "yes")
    return value_type(value)


@dataclass
class ContextConfig:
    """Configuration for context extraction around multimodal content."""
    
    context_window: int = 1
    """Number of pages/chunks to include before and after current item."""
    
    context_mode: str = "page"
    """Context extraction mode: 'page' for page-based, 'chunk' for chunk-based."""
    
    max_context_tokens: int = 2000
    """Maximum number of tokens in extracted context."""
    
    include_headers: bool = True
    """Whether to include document headers and titles in context."""
    
    include_captions: bool = True
    """Whether to include image/table captions in context."""
    
    filter_content_types: List[str] = field(default_factory=lambda: ["text"])
    """Content types to include in context extraction."""


@dataclass
class MultimodalConfig:
    """Configuration for multimodal document processing."""
    
    # General settings
    enabled: bool = field(default_factory=lambda: get_env_value("MULTIMODAL_ENABLED", True, bool))
    """Enable/disable multimodal processing."""
    
    working_dir: str = field(default_factory=lambda: get_env_value("MULTIMODAL_WORKING_DIR", "./rag_storage/multimodal"))
    """Directory for multimodal processing storage."""
    
    output_dir: str = field(default_factory=lambda: get_env_value("MULTIMODAL_OUTPUT_DIR", "./rag_storage/parsed"))
    """Output directory for parsed content."""
    
    # Parser settings
    parser: str = field(default_factory=lambda: get_env_value("MULTIMODAL_PARSER", "mineru"))
    """Parser selection: 'mineru' or 'docling'."""
    
    parse_method: str = field(default_factory=lambda: get_env_value("MULTIMODAL_PARSE_METHOD", "auto"))
    """Parsing method: 'auto', 'ocr', or 'txt'."""
    
    # Processing toggles
    enable_image_processing: bool = field(default_factory=lambda: get_env_value("ENABLE_IMAGE_PROCESSING", True, bool))
    """Enable image content processing (ECG, charts, etc.)."""
    
    enable_table_processing: bool = field(default_factory=lambda: get_env_value("ENABLE_TABLE_PROCESSING", True, bool))
    """Enable table content processing (lab results, vitals)."""
    
    enable_equation_processing: bool = field(default_factory=lambda: get_env_value("ENABLE_EQUATION_PROCESSING", False, bool))
    """Enable equation processing (usually not needed for medical)."""
    
    # Batch processing
    max_concurrent_files: int = field(default_factory=lambda: get_env_value("MULTIMODAL_MAX_CONCURRENT", 4, int))
    """Maximum number of files to process concurrently."""
    
    recursive_folder_processing: bool = True
    """Whether to recursively process subfolders."""
    
    # Supported file types
    supported_extensions: List[str] = field(default_factory=lambda: [
        ".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", 
        ".gif", ".webp", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"
    ])
    """List of supported file extensions."""
    
    # Aliases for RAG-Anything compatibility
    @property
    def parser_output_dir(self) -> str:
        """Alias for output_dir (RAG-Anything compatibility)."""
        return self.output_dir
    
    @property
    def supported_file_extensions(self) -> List[str]:
        """Alias for supported_extensions (RAG-Anything compatibility)."""
        return self.supported_extensions
    
    # Medical-specific settings
    ocr_for_scanned_docs: bool = field(default_factory=lambda: get_env_value("OCR_SCANNED_DOCS", True, bool))
    """Use OCR for scanned medical documents."""
    
    extract_lab_tables: bool = field(default_factory=lambda: get_env_value("EXTRACT_LAB_TABLES", True, bool))
    """Extract and structure lab result tables."""
    
    extract_vital_signs: bool = field(default_factory=lambda: get_env_value("EXTRACT_VITAL_SIGNS", True, bool))
    """Extract vital signs from tables."""
    
    parse_prescription_images: bool = field(default_factory=lambda: get_env_value("PARSE_PRESCRIPTIONS", True, bool))
    """Parse prescription/medication images."""
    
    analyze_ecg_images: bool = field(default_factory=lambda: get_env_value("ANALYZE_ECG", True, bool))
    """Analyze ECG/EKG images with vision model."""
    
    # Context extraction
    context_config: ContextConfig = field(default_factory=ContextConfig)
    """Configuration for context extraction."""
    
    # Vision model settings
    vision_model: Optional[str] = field(default_factory=lambda: get_env_value("VISION_MODEL", "gpt-4o"))
    """Vision model for image analysis."""
    
    vision_max_tokens: int = field(default_factory=lambda: get_env_value("VISION_MAX_TOKENS", 1000, int))
    """Max tokens for vision model response."""
    
    # Caching
    enable_parse_cache: bool = field(default_factory=lambda: get_env_value("MULTIMODAL_CACHE", True, bool))
    """Cache parsed document results."""
    
    cache_ttl_hours: int = field(default_factory=lambda: get_env_value("MULTIMODAL_CACHE_TTL", 24, int))
    """Cache time-to-live in hours."""
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        import os
        
        # Create working directory if it doesn't exist
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir, exist_ok=True)
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        
        # Validate parser choice
        if self.parser not in ["mineru", "docling"]:
            raise ValueError(f"Invalid parser: {self.parser}. Must be 'mineru' or 'docling'.")
        
        # Validate parse method
        if self.parse_method not in ["auto", "ocr", "txt"]:
            raise ValueError(f"Invalid parse_method: {self.parse_method}. Must be 'auto', 'ocr', or 'txt'.")


# Alias for RAG-Anything compatibility
# The BatchMixin references RAGAnythingConfig, so we provide this alias
RAGAnythingConfig = MultimodalConfig
