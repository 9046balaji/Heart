"""
PubMed Streaming Loader (Tier 2)

This module handles streaming the MedRAG PubMed dataset with memory-safe
batch processing. PubMed is massive (24M+ snippets, 70GB+) and must be
streamed in batches to avoid RAM crashes.

Source: https://huggingface.co/datasets/MedRAG/pubmed
Size: 24M+ snippets, 70GB+ (extremely large)
Strategy: Stream in batches, cache processed batches, never load entire dataset

Key Features:
- Memory-safe batch processing (configurable batch size)
- Disk-based caching for already-processed batches
- Checkpointing for resume capability
- RAM monitoring with circuit breaker
- Lazy embedding (embeddings generated on-demand)
"""

import os
import json
import logging
import psutil
from typing import List, Optional, Dict, Any, Iterator, Tuple
from pathlib import Path
from datetime import datetime
import time
from dataclasses import dataclass

from rag.data_sources.models import (
    MedicalDocument,
    DocumentSource,
    SourceTier,
    DocumentLoader,
    ReviewStatus,
    LoaderStats,
    PUBMED_BATCH_SIZE,
    PUBMED_MAX_BATCH_MEMORY_MB,
)

logger = logging.getLogger(__name__)


@dataclass
class StreamingCheckpoint:
    """Tracks progress through PubMed dataset for resumable downloads"""
    last_batch_processed: int = 0
    total_batches_estimated: Optional[int] = None
    documents_processed: int = 0
    last_update: str = ""
    
    def save(self, checkpoint_file: Path):
        """Save checkpoint to disk"""
        with open(checkpoint_file, 'w') as f:
            json.dump({
                'last_batch': self.last_batch_processed,
                'total_batches': self.total_batches_estimated,
                'documents': self.documents_processed,
                'last_update': self.last_update,
            }, f)
    
    @classmethod
    def load(cls, checkpoint_file: Path) -> 'StreamingCheckpoint':
        """Load checkpoint from disk"""
        if not checkpoint_file.exists():
            return cls()
        
        with open(checkpoint_file, 'r') as f:
            data = json.load(f)
        
        cp = cls(
            last_batch_processed=data.get('last_batch', 0),
            total_batches_estimated=data.get('total_batches'),
            documents_processed=data.get('documents', 0),
            last_update=data.get('last_update', ''),
        )
        return cp


class PubMedStreamer(DocumentLoader):
    """
    Streams the PubMed dataset in memory-safe batches.
    
    Design Philosophy:
    - Never load entire dataset into RAM
    - Process in configurable batches (default: 500 documents)
    - Cache processed batches to disk for reuse
    - Monitor RAM and stop if approaching limit
    - Support resume from checkpoint
    
    Usage:
        streamer = PubMedStreamer(cache_dir="data/medrag/pubmed_cache")
        
        # Option 1: Stream all with callback
        for batch_num, batch_docs in enumerate(streamer.stream()):
            print(f"Processing batch {batch_num}: {len(batch_docs)} docs")
            vector_db.insert(batch_docs)
        
        # Option 2: Load up to N documents
        docs = streamer.load_n_documents(10000)
        
        # Option 3: Get specific batch
        batch = streamer.get_batch(5)  # 6th batch
    """
    
    def __init__(
        self,
        cache_dir: str = "data/medrag/pubmed_cache",
        batch_size: int = PUBMED_BATCH_SIZE,
        max_memory_mb: int = PUBMED_MAX_BATCH_MEMORY_MB,
        enable_checkpointing: bool = True,
    ):
        """
        Initialize PubMed streamer.
        
        Args:
            cache_dir: Directory for batch cache
            batch_size: Documents per batch
            max_memory_mb: Max RAM before circuit breaker triggers
            enable_checkpointing: Support resumable downloads
        """
        self.cache_dir = Path(cache_dir)
        self.batch_size = batch_size
        self.max_memory_mb = max_memory_mb
        self.enable_checkpointing = enable_checkpointing
        
        # Create directories
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.batch_cache_dir = self.cache_dir / "batches"
        self.batch_cache_dir.mkdir(exist_ok=True)
        
        # Checkpoint tracking
        self.checkpoint_file = self.cache_dir / "checkpoint.json"
        self.checkpoint = StreamingCheckpoint.load(self.checkpoint_file)
        
        # Stats
        self.stats = None
        self.total_streamed = 0
        
        logger.info(
            f"PubMedStreamer initialized:\n"
            f"  Cache: {self.cache_dir}\n"
            f"  Batch size: {self.batch_size}\n"
            f"  Max memory: {self.max_memory_mb}MB\n"
            f"  Checkpoint: {'Enabled' if enable_checkpointing else 'Disabled'}"
        )
    
    def validate(self) -> bool:
        """Validate dependencies"""
        try:
            import datasets
            logger.info(f"✓ datasets library available")
            return True
        except ImportError:
            logger.error("✗ datasets library not found. Install with: pip install datasets")
            return False
    
    def load(self) -> List[MedicalDocument]:
        """
        Load first batch of PubMed documents (for compatibility with DocumentLoader interface).
        
        Note: For PubMed, use stream() instead for memory efficiency.
        
        Returns:
            First batch of documents
        """
        logger.warning(
            "PubMedStreamer.load() returns only first batch.\n"
            "For memory efficiency, use .stream() or .load_n_documents() instead"
        )
        
        for batch in self.stream():
            return batch
        
        return []
    
    def stream(self, from_checkpoint: bool = True) -> Iterator[List[MedicalDocument]]:
        """
        Stream PubMed in batches (recommended method).
        
        Args:
            from_checkpoint: Resume from last checkpoint if available
        
        Yields:
            Batch of MedicalDocument objects (batch_size each)
        """
        try:
            from datasets import load_dataset
        except ImportError:
            raise RuntimeError("datasets library required. Install with: pip install datasets")
        
        logger.info("Starting PubMed streaming...")
        logger.info("⚠️  WARNING: PubMed is 70GB+. Only stream what you need!")
        
        # Determine start point
        start_batch = 0
        if from_checkpoint and self.checkpoint.last_batch_processed > 0:
            start_batch = self.checkpoint.last_batch_processed
            logger.info(f"Resuming from batch {start_batch} ({self.checkpoint.documents_processed} docs processed)")
        
        # Check for existing batches (skip re-downloading)
        batch_num = 0
        existing_batches = sorted([
            int(f.stem.split('_')[1])
            for f in self.batch_cache_dir.glob("batch_*.jsonl")
        ])
        
        if existing_batches:
            logger.info(f"Found {len(existing_batches)} cached batches")
            # Yield cached batches first
            for cache_batch_num in existing_batches:
                if cache_batch_num < start_batch:
                    continue
                
                docs = self._load_batch_from_cache(cache_batch_num)
                logger.info(f"Yielding cached batch {cache_batch_num}: {len(docs)} docs")
                yield docs
                batch_num = cache_batch_num + 1
        
        # Stream remaining batches from HF
        logger.info(f"Loading PubMed dataset from Hugging Face (streaming=True)...")
        dataset = load_dataset(
            "MedRAG/pubmed",
            streaming=True,
            cache_dir=str(self.cache_dir / "huggingface_cache"),
        )
        
        train_split = dataset['train']
        
        # Process batches
        batch_docs = []
        doc_count = 0
        
        for doc_idx, hf_example in enumerate(train_split):
            # Skip to start batch if resuming
            if doc_idx < (start_batch * self.batch_size):
                continue
            
            try:
                doc = self._convert_to_medical_document(hf_example, doc_idx)
                batch_docs.append(doc)
                doc_count += 1
                self.total_streamed += 1
                
                # Check memory usage
                if self._check_memory_exceeded():
                    logger.error("RAM limit exceeded! Stopping stream to prevent crash.")
                    break
                
                # Yield when batch full
                if len(batch_docs) >= self.batch_size:
                    logger.info(f"Batch {batch_num}: {len(batch_docs)} docs, {self.total_streamed} total")
                    
                    # Cache batch
                    if self.enable_checkpointing:
                        self._save_batch_to_cache(batch_docs, batch_num)
                        self.checkpoint.last_batch_processed = batch_num
                        self.checkpoint.documents_processed = self.total_streamed
                        self.checkpoint.last_update = datetime.now().isoformat()
                        self.checkpoint.save(self.checkpoint_file)
                    
                    yield batch_docs
                    batch_docs = []
                    batch_num += 1
                
                # Progress logging
                if doc_count % 5000 == 0:
                    logger.debug(f"Processed {doc_count} documents...")
            
            except Exception as e:
                logger.warning(f"Error processing document {doc_idx}: {e}")
        
        # Yield final partial batch if any
        if batch_docs:
            logger.info(f"Final batch {batch_num}: {len(batch_docs)} docs")
            if self.enable_checkpointing:
                self._save_batch_to_cache(batch_docs, batch_num)
            yield batch_docs
    
    def load_n_documents(self, n: int) -> List[MedicalDocument]:
        """
        Load first N documents (useful for testing/small batches).
        
        Args:
            n: Number of documents to load
        
        Returns:
            List of MedicalDocument objects (up to n)
        """
        documents = []
        
        for batch in self.stream():
            documents.extend(batch)
            if len(documents) >= n:
                return documents[:n]
        
        return documents
    
    def get_batch(self, batch_num: int) -> Optional[List[MedicalDocument]]:
        """
        Get specific batch from cache (if available).
        
        Args:
            batch_num: Batch number (0-indexed)
        
        Returns:
            Batch of documents or None if not cached
        """
        return self._load_batch_from_cache(batch_num)
    
    def _save_batch_to_cache(self, documents: List[MedicalDocument], batch_num: int):
        """Save batch to disk cache"""
        cache_file = self.batch_cache_dir / f"batch_{batch_num:06d}.jsonl"
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            for doc in documents:
                f.write(doc.to_json() + '\n')
        
        logger.debug(f"Cached batch {batch_num} to {cache_file}")
    
    def _load_batch_from_cache(self, batch_num: int) -> List[MedicalDocument]:
        """Load batch from disk cache"""
        cache_file = self.batch_cache_dir / f"batch_{batch_num:06d}.jsonl"
        
        if not cache_file.exists():
            return []
        
        documents = []
        with open(cache_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    doc_dict = json.loads(line.strip())
                    doc = MedicalDocument.from_dict(doc_dict)
                    documents.append(doc)
                except Exception as e:
                    logger.warning(f"Error loading document from {cache_file}: {e}")
        
        return documents
    
    def _check_memory_exceeded(self) -> bool:
        """Check if RAM usage exceeds threshold"""
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        if memory_mb > self.max_memory_mb:
            logger.warning(f"Memory usage {memory_mb:.1f}MB exceeds limit {self.max_memory_mb}MB")
            return True
        
        return False
    
    def _convert_to_medical_document(self, hf_example: Dict[str, Any], idx: int) -> MedicalDocument:
        """
        Convert Hugging Face PubMed example to MedicalDocument.
        
        HF PubMed format:
        {
            'pmid': str,
            'title': str,
            'abstract': str,
            'mesh_headings': list,
            'publication_date': str,
        }
        
        Args:
            hf_example: Example from dataset
            idx: Index for tracking
        
        Returns:
            MedicalDocument
        """
        pmid = hf_example.get('pmid', f'unknown_{idx}')
        title = hf_example.get('title', 'Unknown')
        abstract = hf_example.get('abstract', '')
        mesh_terms = hf_example.get('mesh_headings', [])
        pub_date = hf_example.get('publication_date', '')
        
        # Parse publication date
        publication_date = None
        if pub_date:
            try:
                publication_date = datetime.fromisoformat(pub_date)
            except:
                pass
        
        # Infer confidence based on recency
        confidence = self._calculate_confidence(publication_date)
        
        # Infer clinical context from title/abstract
        clinical_context = self._infer_clinical_context(title, abstract)
        
        doc = MedicalDocument(
            document_id=f"pubmed_{pmid}",
            title=title,
            content=abstract,
            source=DocumentSource.PUBMED,
            tier=SourceTier.TIER_2_PUBMED,
            confidence_score=confidence,
            review_status=ReviewStatus.VERIFIED if confidence > 0.7 else ReviewStatus.PREPRINT,
            
            publication_date=publication_date,
            mesh_terms=mesh_terms[:10],  # Top 10 MeSH terms
            clinical_context=clinical_context,
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
        )
        
        return doc
    
    @staticmethod
    def _calculate_confidence(pub_date: Optional[datetime]) -> float:
        """
        Calculate confidence score based on publication date.
        
        Recent papers (< 2 years): 0.85
        Medium (2-5 years): 0.70
        Older (> 5 years): 0.55
        """
        if not pub_date:
            return 0.65  # Unknown date = medium confidence
        
        age_years = (datetime.now() - pub_date).days / 365
        
        if age_years < 2:
            return 0.85  # Recent and high-impact
        elif age_years < 5:
            return 0.70  # Standard research
        else:
            return 0.55  # Older studies
    
    @staticmethod
    def _infer_clinical_context(title: str, abstract: str) -> Optional[str]:
        """Infer clinical context from title/abstract"""
        text = f"{title} {abstract}".lower()
        
        contexts = {
            "diagnosis": ["diagnos", "screening", "detection"],
            "treatment": ["treatment", "therapy", "intervention"],
            "prognosis": ["prognosis", "outcome", "survival"],
            "epidemiology": ["epidemiology", "prevalence", "incidence"],
        }
        
        for context, keywords in contexts.items():
            if any(kw in text for kw in keywords):
                return context
        
        return None
    
    def get_stats(self) -> Optional[LoaderStats]:
        """Get streaming statistics"""
        return self.stats


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    streamer = PubMedStreamer(
        cache_dir="data/medrag/pubmed_cache",
        batch_size=100,  # Small for testing
    )
    
    if not streamer.validate():
        print("Missing dependencies!")
        exit(1)
    
    print("Demo: Loading first 2 batches of PubMed...")
    
    for batch_num, batch in enumerate(streamer.stream()):
        print(f"\nBatch {batch_num}: {len(batch)} documents")
        if batch:
            print(f"  First doc: {batch[0].document_id} - {batch[0].title[:60]}")
        
        if batch_num >= 1:  # Just first 2 batches for demo
            break
    
    print("\n✓ Demo complete")

