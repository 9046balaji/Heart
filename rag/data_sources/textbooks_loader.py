import os
import json
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import time

from rag.data_sources.models import (
    MedicalDocument,
    DocumentSource,
    SourceTier,
    DocumentLoader,
    ReviewStatus,
    LoaderStats,
    TIER_1_CONFIDENCE,
)

logger = logging.getLogger(__name__)



class TextbooksLoader(DocumentLoader):
    """
    Robust Loader for MedRAG Textbooks.
    Ensures content is correctly extracted regardless of HF field naming.
    """
    
    def __init__(self, cache_dir: str = "data/medrag/textbooks", force_download: bool = False):
        self.cache_dir = Path(cache_dir)
        self.force_download = force_download
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.documents = []
        self.stats = None
        logger.info(f"TextbooksLoader initialized with cache: {cache_dir}")

    def validate(self) -> bool:
        """Verify datasets library is available."""
        try:
            import datasets
            return True
        except ImportError:
            logger.warning("datasets library not available")
            return False

    def load(self) -> List[MedicalDocument]:
        """
        Load textbooks dataset. Steps:
        1. Check if cached locally
        2. If not, download from Hugging Face
        3. Parse and normalize to MedicalDocument schema
        """
        cache_file = self.cache_dir / "textbooks_train.jsonl"
        
        # 1. Load from cache if it exists and we aren't forcing download
        if cache_file.exists() and not self.force_download:
            logger.info(f"Loading from cache: {cache_file}")
            return self._load_from_cache(cache_file)
            
        # 2. Download from Hugging Face
        logger.info("Downloading from Hugging Face...")
        return self._download_and_process(cache_file)

    def _download_and_process(self, cache_file: Path) -> List[MedicalDocument]:
        """Download Textbooks dataset from Hugging Face and convert to schema."""
        try:
            from datasets import load_dataset
        except ImportError:
            raise RuntimeError("datasets library required. Install with: pip install datasets")
        
        logger.info("Downloading from https://huggingface.co/datasets/MedRAG/textbooks...")
        
        # Download
        dataset = load_dataset("MedRAG/textbooks", split="train")
        documents = []
        
        logger.info(f"Processing {len(dataset)} items...")
        
        # Open cache file for writing
        with open(cache_file, 'w', encoding='utf-8') as f:
            for i, item in enumerate(dataset):
                # CRITICAL FIX: Check multiple keys for the actual text content
                content = item.get("content") or item.get("contents") or item.get("text") or ""
                title = item.get("title") or "Unknown Title"
                doc_id = str(item.get("id") or i)
                
                if not content.strip():
                    continue  # Skip empty documents
                
                doc = MedicalDocument(
                    document_id=doc_id,
                    title=title,
                    content=content,
                    source=DocumentSource.TEXTBOOKS,
                    tier=SourceTier.TIER_1_TEXTBOOKS,
                    confidence_score=1.0,
                    clinical_context="medical_textbook"
                )
                
                documents.append(doc)
                f.write(json.dumps(doc.to_dict()) + "\n")
                
                if (i + 1) % 10000 == 0:
                    logger.info(f"Processed {i + 1}/{len(dataset)} items...")
        
        logger.info(f"[OK] Successfully processed {len(documents)} non-empty documents")
        return documents

    def _load_from_cache(self, cache_file: Path) -> List[MedicalDocument]:
        """Load from local cache with corruption detection."""
        documents = []
        
        # Basic size check to detect corruption
        if cache_file.stat().st_size < 1024 * 1024 * 50:  # < 50MB
            logger.warning("Cache file suspiciously small. Re-downloading.")
            return self._download_and_process(cache_file)

        with open(cache_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line)
                    if not data.get("content"): 
                        continue
                    doc = MedicalDocument.from_dict(data)
                    documents.append(doc)
                except Exception as e:
                    if line_num <= 5:
                        logger.warning(f"Error at line {line_num}: {e}")
                    continue
        
        logger.info(f"Loaded {len(documents)} documents from cache")
        return documents

    def get_stats(self):
        """Return statistics about loaded documents."""
        return None