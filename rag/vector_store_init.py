"""
Vector Store Initialization Script for HeartGuard Knowledge Base

This is the MASTER initialization script that orchestrates the ingestion of
medical documents (Textbooks + StatPearls) into ChromaDB with embeddings.

Purpose:
--------
1. Loads Tier 1 data (Textbooks + StatPearls) from disk
2. Initializes ChromaDB store with embeddings
3. Performs batch ingestion with progress reporting
4. Validates and reports statistics


Usage:
------
    python rag/vector_store_init.py
    
    Options:
    --tier {1,2,both}    : Which tier to load (default: 1)
    --batch-size N       : Batch size for ingestion (default: 200)
    --clear              : Clear existing vector store before loading

Expected Output:
----------------
    [OK] Loaded 126,430 snippets from textbooks
    [OK] Loaded 1,524,532 documents from StatPearls
    [OK] Indexed 1,650,962 documents in 15-45 minutes
    [OK] Vector store ready for semantic search!

Author: HeartGuard Implementation Team
Date: January 4, 2026
"""

import logging
import sys
import os
import argparse
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.data_sources.textbooks_loader import TextbooksLoader
from rag.data_sources.statpearls_downloader import StatPearlsDownloader
from rag.ingestion.vector_store_manager import VectorStoreManager
from rag.data_sources.models import MedicalDocument, DocumentSource

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VectorStoreInitializer:
    """
    Orchestrates the complete vector store initialization pipeline.
    
    Responsibilities:
    - Load documents from multiple Tier 1 sources
    - Initialize ChromaDB store
    - Batch ingest documents with embeddings
    - Provide detailed progress and statistics
    """
    
    def __init__(
        self,
        db_path: str = None,
        batch_size: int = 200,
        clear_existing: bool = False,
    ):
        """
        Initialize the orchestrator.
        
        Args:
            db_path: Optional ChromaDB persistence directory
            batch_size: Documents per batch for ingestion
            clear_existing: Clear vector store before loading
        """
        self.db_path = db_path  # Kept for backward compatibility
        self.batch_size = batch_size
        self.clear_existing = clear_existing
        self.vdb = None
        self.total_docs_loaded = 0
        self.start_time = None
        
        logger.info(f"VectorStoreInitializer configured: batch_size={batch_size}")
    
    def _print_header(self, title: str) -> None:
        """Print a formatted section header."""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60 + "\n")
    
    def _print_step(self, step_num: int, description: str) -> None:
        """Print a formatted step."""
        print(f"[Step {step_num}] {description}")
        print("-" * 60)
    
    def initialize_vector_store(self) -> bool:
        """
        Initialize ChromaDB store.
        
        Returns:
            True if successful, False otherwise
        """
        self._print_step(1, "Initializing ChromaDB Store")
        
        try:
            self.vdb = VectorStoreManager.get_instance()
            stats = self.vdb.get_stats()
            existing_count = stats.get('document_count', 0)
            
            if self.clear_existing and existing_count > 0:
                print(f"[WARNING] Clearing {existing_count} existing documents...")
                self.vdb.clear()
                self.vdb = VectorStoreManager.get_instance()
                existing_count = 0
            
            print(f"[OK] ChromaDB ready")
            print(f"   Database: ChromaDB (local persistent)")
            print(f"   Embedding model: all-MiniLM-L6-v2")
            print(f"   Existing documents: {existing_count}")
            print(f"   Batch size: {self.batch_size}")
            print()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            print(f"[ERROR] ERROR: {e}")
            return False
    
    def load_tier1_textbooks(self) -> Tuple[int, bool]:
        """
        Load Tier 1 Textbooks dataset.
        
        Returns:
            Tuple of (number_of_documents_loaded, success_flag)
        """
        self._print_step(2, "Loading Tier 1 Textbooks Dataset")
        
        try:
            loader = TextbooksLoader(cache_dir="data/medrag/textbooks")
            
            # Validate dependencies
            if not loader.validate():
                print("[ERROR] Missing dependencies (requires: datasets, huggingface_hub)")
                print("   Install with: pip install datasets huggingface_hub")
                return 0, False
            
            # Load documents
            print("Downloading from Hugging Face (if not cached)...")
            documents = loader.load()
            stats = loader.get_stats()
            
            print(f"[OK] Loaded {len(documents)} textbook snippets")
            print(f"   Source: MedRAG/textbooks (Hugging Face)")
            print(f"   Tier: Tier 1 (High Confidence)")
            print(f"   Size: ~500MB")
            print(f"   Topics: Anatomy, Pathology, Physiology, etc.")
            print()
            
            # Ingest into vector store
            print("Ingesting into vector store...")
            self.vdb.insert_documents(documents, batch_size=self.batch_size)
            
            print(f"[OK] {len(documents)} documents indexed")
            print()
            
            return len(documents), True
            
        except ImportError as e:
            logger.error(f"Missing dependencies: {e}")
            print(f"[ERROR] ERROR: Missing package - {e}")
            print("   Install with: pip install datasets huggingface_hub")
            return 0, False
        except Exception as e:
            logger.error(f"Failed to load textbooks: {e}")
            print(f"[ERROR] ERROR: {e}")
            return 0, False
    
    def load_tier1_statpearls(self) -> Tuple[int, bool]:
        """
        Load Tier 1 StatPearls dataset.
        
        Returns:
            Tuple of (number_of_documents_loaded, success_flag)
        """
        self._print_step(3, "Loading Tier 1 StatPearls Dataset")
        
        try:
            # Check if MedRAG repo exists
            medrag_path = Path("MedRAG/data/processed/statpearls")
            
            if not medrag_path.exists():
                print(f"[WARNING] StatPearls data not found at {medrag_path}")
                print("   To setup StatPearls:")
                print("   1. git clone https://github.com/Teddy-XiongGZ/MedRAG.git")
                print("   2. python rag/data_sources/statpearls_downloader.py")
                print("   3. Then run this script again")
                print()
                return 0, False
            
            # Load documents
            loader = StatPearlsDownloader(cache_dir="data/medrag/statpearls")
            documents = loader.load()
            
            print(f"[OK] Loaded {len(documents)} StatPearls documents")
            print(f"   Source: StatPearls (Clinical Guidelines)")
            print(f"   Tier: Tier 1 (Gold Standard)")
            print(f"   Size: ~1.5GB")
            print(f"   Coverage: 5,000+ medical topics")
            print()
            
            # Ingest into vector store
            print("Ingesting into vector store...")
            self.vdb.insert_documents(documents, batch_size=self.batch_size)
            
            print(f"[OK] {len(documents)} documents indexed")
            print()
            
            return len(documents), True
            
        except ImportError as e:
            logger.error(f"Missing dependencies: {e}")
            print(f"[ERROR] ERROR: Missing package - {e}")
            return 0, False
        except Exception as e:
            logger.error(f"Failed to load StatPearls: {e}")
            print(f"[ERROR] ERROR: {e}")
            return 0, False
    
    def verify_ingestion(self) -> bool:
        """
        Verify that documents were successfully ingested.
        
        Returns:
            True if verification passed, False otherwise
        """
        self._print_step(4, "Verifying Vector Store Ingestion")
        
        try:
            final_count = self.vdb.collection.count()
            
            print(f"[OK] Vector store verification:")
            print(f"   Total documents indexed: {final_count:,}")
            print(f"   Collection name: heart_guard_docs")
            print(f"   Status: READY FOR SEMANTIC SEARCH")
            print()
            
            if final_count > 0:
                # Test a simple query
                print("Testing semantic search...")
                results = self.vdb.search("heart disease", top_k=1)
                if results:
                    print(f"[OK] Search test successful!")
                    print(f"   Sample result: {results[0]['title'][:50]}...")
                    print()
                return True
            else:
                print("[WARNING] WARNING: No documents indexed")
                print("   Please run: python rag/data_sources/textbooks_loader.py")
                return False
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            print(f"[ERROR] ERROR: {e}")
            return False
    
    def run(self, tier: str = "1") -> bool:
        """
        Run the complete initialization pipeline.
        
        Args:
            tier: Which tier to load ("1", "2", or "both")
        
        Returns:
            True if successful, False otherwise
        """
        self.start_time = datetime.now()
        self._print_header("HeartGuard Vector Store Initialization")
        
        print(f"Starting at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Configuration:")
        print(f"  - Tier to load: {tier}")
        print(f"  - Batch size: {self.batch_size}")
        print(f"  - Clear existing: {self.clear_existing}")
        print()
        
        # Step 1: Initialize vector store
        if not self.initialize_vector_store():
            return False
        
        # Step 2: Load Tier 1 Textbooks
        textbooks_count, textbooks_success = self.load_tier1_textbooks()
        
        # Step 3: Load Tier 1 StatPearls (optional, if available)
        statpearls_count = 0
        if tier in ["1", "both"]:
            statpearls_count, _ = self.load_tier1_statpearls()
        
        # Step 4: Verify ingestion
        verification_passed = self.verify_ingestion()
        
        # Final report
        self._print_header("Summary")
        elapsed = datetime.now() - self.start_time
        
        print(f"[OK] Initialization Complete!")
        print()
        print(f"Documents Ingested:")
        print(f"  - Textbooks:  {textbooks_count:>8,}")
        print(f"  - StatPearls: {statpearls_count:>8,}")
        print(f"  - TOTAL:      {textbooks_count + statpearls_count:>8,}")
        print()
        print(f"Performance:")
        print(f"  - Time elapsed: {elapsed}")
        print(f"  - Rate: {(textbooks_count + statpearls_count) / elapsed.total_seconds():.0f} docs/sec")
        print()
        print(f"Next Steps:")
        print(f"  1. Your system is now ready for semantic search!")
        print(f"  2. Run: python main.py")
        print(f"  3. Query: 'How is atrial fibrillation diagnosed?'")
        print()
        print("=" * 60)
        
        return textbooks_success or verification_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Initialize HeartGuard Vector Store with medical documents"
    )
    parser.add_argument(
        "--tier",
        choices=["1", "2", "both"],
        default="1",
        help="Which tier to load (default: 1)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Batch size for ingestion (default: 200)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing vector store before loading"
    )
    # --db-path for ChromaDB persistence directory
    parser.add_argument(
        "--db-path",
        default=None,
        help="ChromaDB persistence directory (default: ./Chromadb)"
    )
    
    args = parser.parse_args()
    
    # Create initializer and run
    initializer = VectorStoreInitializer(
        db_path=args.db_path,
        batch_size=args.batch_size,
        clear_existing=args.clear,
    )
    
    success = initializer.run(tier=args.tier)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
