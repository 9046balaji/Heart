"""
StatPearls Downloader & Processor (Tier 1)

This module handles the complex StatPearls dataset acquisition:

1. Download raw XML from NCBI FTP (1.5GB)
2. Extract and validate XML structure
3. Process with MedRAG scripts to normalize
4. Convert to MedicalDocument schema

StatPearls is the "Gold Standard" for clinical decision support (like UpToDate)
and is critical for HeartGuard's clinical accuracy.

Source: NCBI Bookshelf FTP
Size: ~1.5GB (compressed), ~500k snippets (processed)
Difficulty: Hard (requires FTP download + XML processing)
Time: 30-60 minutes (mostly download)

Setup Steps:
1. Clone https://github.com/Teddy-XiongGZ/MedRAG.git
2. Run this downloader
3. Run processor
4. Validate output
"""

import os
import json
import logging
import shutil
import subprocess
import tarfile
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import time
from dataclasses import dataclass
import hashlib

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


@dataclass
class DownloadProgress:
    """Track download progress"""
    total_bytes: int = 0
    downloaded_bytes: int = 0
    start_time: float = 0.0
    
    @property
    def percentage(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return (self.downloaded_bytes / self.total_bytes) * 100
    
    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time
    
    @property
    def speed_mbps(self) -> float:
        if self.elapsed_seconds < 1:
            return 0.0
        return (self.downloaded_bytes / 1024 / 1024) / self.elapsed_seconds
    
    @property
    def eta_seconds(self) -> float:
        if self.speed_mbps < 0.1:
            return 0.0
        remaining_bytes = self.total_bytes - self.downloaded_bytes
        return (remaining_bytes / 1024 / 1024) / self.speed_mbps


class StatPearlsDownloader(DocumentLoader):
    """
    Download and process StatPearls dataset from NCBI.
    
    Important: This requires manual interaction with NCBI FTP.
    Consider the network requirements (~1.5GB download).
    
    Usage:
        downloader = StatPearlsDownloader(
            corpus_dir="corpus/statpearls",
        )
        
        # Download raw XML (1.5GB)
        downloader.download_raw_xml()
        
        # Process XML with native Python (no MedRAG subprocess needed)
        downloader.process_xml_native()
        
        # Or use MedRAG scripts if available
        downloader.process_xml()
        
        # Load processed documents
        docs = downloader.load()
    """
    
    # NCBI FTP constants
    NCBI_FTP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/litarch/3d/12/"
    STATPEARLS_ARCHIVE = "statpearls_NBK430685.tar.gz"
    
    # Default MedRAG path relative to this file's location
    _DEFAULT_MEDRAG_PATH = Path(__file__).parent / "MedRAG"
    
    def __init__(
        self,
        corpus_dir: str = "corpus/statpearls",
        medrag_repo_path: str = None,
        skip_download: bool = False,
    ):
        """
        Initialize StatPearls downloader.
        
        Args:
            corpus_dir: Where to store raw XML and processed data
            medrag_repo_path: Path to cloned MedRAG repository (auto-detected if None)
            skip_download: Set True if already downloaded
        """
        self.corpus_dir = Path(corpus_dir)
        
        # Auto-detect MedRAG path if not provided
        if medrag_repo_path is None:
            self.medrag_repo_path = self._DEFAULT_MEDRAG_PATH
        else:
            self.medrag_repo_path = Path(medrag_repo_path)
        
        self.skip_download = skip_download
        
        # Subdirectories
        self.raw_dir = self.corpus_dir / "raw_xml"
        self.processed_dir = self.corpus_dir / "processed"
        
        # Create directories
        for d in [self.corpus_dir, self.raw_dir, self.processed_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # File paths
        self.archive_path = self.corpus_dir / self.STATPEARLS_ARCHIVE
        self.checkpoint_file = self.corpus_dir / "download_checkpoint.json"
        
        self.documents = []
        self.stats = None
        
        logger.info(
            f"StatPearlsDownloader initialized:\n"
            f"  Corpus: {self.corpus_dir}\n"
            f"  MedRAG: {self.medrag_repo_path}\n"
            f"  Raw XML: {self.raw_dir}\n"
            f"  Processed: {self.processed_dir}"
        )
    
    def validate(self) -> bool:
        """Validate dependencies and configuration"""
        checks = [
            ("MedRAG repo exists", self.medrag_repo_path.exists()),
            ("requests library", self._check_import("requests")),
            ("wget available", shutil.which("wget") is not None),
        ]
        
        all_valid = True
        for check_name, result in checks:
            status = "✓" if result else "✗"
            logger.info(f"{status} {check_name}")
            if not result:
                all_valid = False
        
        return all_valid
    
    def download_raw_xml(self) -> bool:
        """
        Download StatPearls raw XML from NCBI FTP.
        
        ⚠️  This downloads ~1.5GB. Ensure you have:
        - Stable internet connection
        - 2GB free disk space
        - 30-60 minutes
        
        Returns:
            True if successful, False otherwise
        """
        if self.skip_download:
            logger.info("Skipping download (skip_download=True)")
            return self.archive_path.exists()
        
        if self.archive_path.exists():
            logger.info(f"Archive already exists at {self.archive_path}")
            return True
        
        logger.warning(
            f"Downloading {self.STATPEARLS_ARCHIVE} (~1.5GB) from NCBI FTP...\n"
            f"URL: {self.NCBI_FTP_URL}\n"
            f"⏱️  This may take 30-60 minutes depending on connection"
        )
        
        return self._download_with_resume()
    
    def _download_with_resume(self) -> bool:
        """Download with resume capability using wget"""
        url = self.NCBI_FTP_URL + self.STATPEARLS_ARCHIVE
        
        cmd = [
            "wget",
            "--continue",  # Resume if interrupted
            "--show-progress",
            "--progress=bar:force:noscroll",
            "-O", str(self.archive_path),
            url
        ]
        
        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=False)
            logger.info("✓ Download completed successfully")
            return True
        
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Download failed: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}")
            return False
    
    def extract_xml(self) -> bool:
        """Extract tarball to raw XML directory"""
        if not self.archive_path.exists():
            logger.error(f"Archive not found: {self.archive_path}")
            return False
        
        logger.info(f"Extracting {self.archive_path} to {self.raw_dir}...")
        
        try:
            with tarfile.open(self.archive_path, 'r:gz') as tar:
                # Extract with progress
                members = tar.getmembers()
                logger.info(f"Extracting {len(members)} files...")
                
                for i, member in enumerate(members):
                    tar.extract(member, path=self.raw_dir)
                    if (i + 1) % 100 == 0:
                        logger.debug(f"Extracted {i + 1}/{len(members)} files")
            
            logger.info("✓ Extraction completed")
            return True
        
        except Exception as e:
            logger.error(f"✗ Extraction failed: {e}")
            return False
    
    def process_xml(self) -> bool:
        """
        Run MedRAG processing script to convert XML to JSON.
        
        This requires the MedRAG repository to be cloned.
        Script: MedRAG/src/data/statpearls.py
        
        Returns:
            True if processing succeeded
        """
        script_path = self.medrag_repo_path / "src" / "data" / "statpearls.py"
        
        if not script_path.exists():
            logger.error(
                f"MedRAG processing script not found: {script_path}\n"
                f"Make sure you've cloned: https://github.com/Teddy-XiongGZ/MedRAG.git"
            )
            return False
        
        logger.info(f"Running MedRAG processor: {script_path}")
        
        try:
            env = os.environ.copy()
            env['CORPUS_DIR'] = str(self.corpus_dir)
            
            result = subprocess.run(
                ["python", str(script_path)],
                env=env,
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info("✓ Processing completed")
            if result.stdout:
                logger.debug(f"Stdout: {result.stdout[:500]}")
            return True
        
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Processing failed: {e}")
            logger.error(f"Stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}")
            return False
    
    def load(self) -> List[MedicalDocument]:
        """
        Load processed StatPearls documents.
        
        Expects processed/statpearls_*.jsonl files to exist.
        
        Returns:
            List of MedicalDocument objects
        """
        logger.info("Loading processed StatPearls documents...")
        start_time = time.time()
        
        documents = []
        errors = []
        
        # Find all processed JSONL files
        jsonl_files = list(self.processed_dir.glob("statpearls_*.jsonl"))
        
        if not jsonl_files:
            logger.warning(
                f"No processed files found in {self.processed_dir}\n"
                f"Run process_xml() first, or check MedRAG processing output"
            )
            return []
        
        logger.info(f"Found {len(jsonl_files)} processed files")
        
        for jsonl_file in jsonl_files:
            logger.debug(f"Loading {jsonl_file.name}...")
            
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line.strip())
                        doc = self._convert_to_medical_document(data)
                        documents.append(doc)
                    except Exception as e:
                        errors.append(str(e))
                        if len(errors) <= 5:  # Log first 5 errors only
                            logger.debug(f"Error at line {line_num}: {e}")
        
        elapsed = time.time() - start_time
        self._compute_stats(documents, elapsed, len(errors))
        self.documents = documents
        
        logger.info(f"✓ Loaded {len(documents)} documents in {elapsed:.1f}s")
        if errors:
            logger.warning(f"⚠️  {len(errors)} errors during loading")
        
        return documents
    
    def _convert_to_medical_document(self, data: Dict[str, Any]) -> MedicalDocument:
        """
        Convert processed StatPearls JSON to MedicalDocument.
        
        Args:
            data: Processed data from MedRAG script
        
        Returns:
            MedicalDocument
        """
        title = data.get('title', data.get('chapter_title', 'Unknown'))
        content = data.get('text', data.get('content', ''))
        doc_id = data.get('id', data.get('uid', ''))
        
        # StatPearls uses NBK (NCBI Bookshelf) identifiers
        if not doc_id.startswith('sp_'):
            doc_id = f"sp_{doc_id}"
        
        doc = MedicalDocument(
            document_id=doc_id,
            title=title,
            content=content,
            source=DocumentSource.STATPEARLS,
            tier=SourceTier.TIER_1_STATPEARLS,
            confidence_score=TIER_1_CONFIDENCE,  # StatPearls is authoritative
            review_status=ReviewStatus.VERIFIED,  # Peer-reviewed, curated
            
            # Extract metadata
            clinical_context=self._infer_clinical_context(title),
            keywords=data.get('keywords', []),
            mesh_terms=data.get('mesh_terms', []),
            source_url=f"https://www.ncbi.nlm.nih.gov/books/{doc_id}",
        )
        
        return doc
    
    @staticmethod
    def _infer_clinical_context(title: str) -> Optional[str]:
        """Infer clinical context from chapter title"""
        title_lower = title.lower()
        
        contexts = {
            "diagnosis": ["diagnosis", "diagnostic", "screening", "evaluation"],
            "treatment": ["treatment", "management", "therapy", "intervention"],
            "pathophysiology": ["pathophysiology", "mechanism", "etiology"],
            "epidemiology": ["epidemiology", "prevalence", "incidence"],
        }
        
        for context, keywords in contexts.items():
            if any(kw in title_lower for kw in keywords):
                return context
        
        return None
    
    def _compute_stats(self, documents: List[MedicalDocument], elapsed: float, errors: int):
        """Compute loading statistics"""
        total_tokens = sum(len(doc.content.split()) for doc in documents)
        
        self.stats = LoaderStats(
            source=DocumentSource.STATPEARLS,
            total_documents=len(documents),
            total_tokens=total_tokens,
            average_tokens_per_doc=total_tokens / len(documents) if documents else 0,
            load_time_seconds=elapsed,
            success_count=len(documents),
            error_count=errors,
        )
        
        logger.info(self.stats.summary())
    
    def get_stats(self) -> Optional[LoaderStats]:
        """Get loading statistics"""
        return self.stats
    
    @staticmethod
    def _check_import(module_name: str) -> bool:
        """Check if module is available"""
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False
    
    # =========================================================================
    # NATIVE PYTHON XML PROCESSOR (No MedRAG subprocess dependency)
    # =========================================================================
    
    @staticmethod
    def _ends_with_ending_punctuation(s: str) -> bool:
        """Check if string ends with ending punctuation."""
        ending_punctuation = ('.', '?', '!')
        return any(s.endswith(char) for char in ending_punctuation)
    
    @staticmethod
    def _concat_title_content(title: str, content: str) -> str:
        """Concatenate title and content with proper punctuation."""
        title = title.strip()
        content = content.strip()
        if StatPearlsDownloader._ends_with_ending_punctuation(title):
            return f"{title} {content}"
        return f"{title}. {content}"
    
    @staticmethod
    def _extract_text_from_element(element) -> str:
        """Recursively extract text from XML element."""
        text = (element.text or "").strip()
        
        for child in element:
            child_text = StatPearlsDownloader._extract_text_from_element(child)
            if child_text:
                text += (" " if text else "") + child_text
            if child.tail and child.tail.strip():
                text += (" " if text else "") + child.tail.strip()
        
        return text.strip()
    
    @staticmethod
    def _is_subtitle(element) -> bool:
        """Check if element is a subtitle (bold paragraph)."""
        if element.tag != 'p':
            return False
        children = list(element)
        if len(children) != 1:
            return False
        if children[0].tag != 'bold':
            return False
        if children[0].tail and children[0].tail.strip():
            return False
        return True
    
    def _process_single_nxml(self, fpath: Path) -> List[Dict[str, Any]]:
        """
        Process a single .nxml file and extract text chunks.
        
        This is a native Python implementation of the MedRAG statpearls.py logic.
        
        Args:
            fpath: Path to the .nxml file
            
        Returns:
            List of dictionaries with id, title, content, contents
        """
        fname = fpath.stem  # filename without extension
        
        try:
            tree = ET.parse(fpath)
            root = tree.getroot()
            
            # Get document title
            title_elem = root.find(".//title")
            if title_elem is None or title_elem.text is None:
                logger.warning(f"No title found in {fpath}")
                return []
            
            doc_title = title_elem.text.strip()
            sections = root.findall(".//sec")
            
            saved_chunks = []
            chunk_idx = 0
            
            for sec in sections:
                sec_title_elem = sec.find('./title')
                if sec_title_elem is None or sec_title_elem.text is None:
                    continue
                
                sec_title = sec_title_elem.text.strip()
                prefix = f"{doc_title} -- {sec_title}"
                
                last_text = None
                last_chunk = None
                last_node = None
                
                for ch in sec:
                    if self._is_subtitle(ch):
                        last_text = None
                        last_chunk = None
                        sub_title = self._extract_text_from_element(ch)
                        prefix = f"{doc_title} -- {sec_title} -- {sub_title}"
                    
                    elif ch.tag == 'p':
                        curr_text = self._extract_text_from_element(ch)
                        
                        # Merge short paragraphs with previous
                        if len(curr_text) < 200 and last_text and len(last_text + curr_text) < 1000:
                            last_text = f"{last_chunk['content']} {curr_text}"
                            last_chunk = {
                                "id": last_chunk['id'],
                                "title": last_chunk['title'],
                                "content": last_text,
                                "contents": self._concat_title_content(last_chunk['title'], last_text)
                            }
                            saved_chunks[-1] = last_chunk
                        else:
                            last_text = curr_text
                            last_chunk = {
                                "id": f"{fname}_{chunk_idx}",
                                "title": prefix,
                                "content": curr_text,
                                "contents": self._concat_title_content(prefix, curr_text)
                            }
                            saved_chunks.append(last_chunk)
                            chunk_idx += 1
                    
                    elif ch.tag == 'list':
                        list_texts = [self._extract_text_from_element(c) for c in ch]
                        joined_list = " ".join(list_texts)
                        
                        if last_text and len(joined_list + last_text) < 1000:
                            last_text = f"{last_chunk['content']} {joined_list}"
                            last_chunk = {
                                "id": last_chunk['id'],
                                "title": last_chunk['title'],
                                "content": last_text,
                                "contents": self._concat_title_content(last_chunk['title'], last_text)
                            }
                            saved_chunks[-1] = last_chunk
                        elif len(joined_list) < 1000:
                            last_text = joined_list
                            last_chunk = {
                                "id": f"{fname}_{chunk_idx}",
                                "title": prefix,
                                "content": last_text,
                                "contents": self._concat_title_content(prefix, last_text)
                            }
                            saved_chunks.append(last_chunk)
                            chunk_idx += 1
                        else:
                            # Split large lists into individual items
                            last_text = None
                            last_chunk = None
                            for item_text in list_texts:
                                saved_chunks.append({
                                    "id": f"{fname}_{chunk_idx}",
                                    "title": prefix,
                                    "content": item_text,
                                    "contents": self._concat_title_content(prefix, item_text)
                                })
                                chunk_idx += 1
                        
                        # Reset prefix if previous was subtitle
                        if last_node is not None and self._is_subtitle(last_node):
                            prefix = f"{doc_title} -- {sec_title}"
                    
                    last_node = ch
            
            return saved_chunks
        
        except ET.ParseError as e:
            logger.warning(f"XML parse error in {fpath}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error processing {fpath}: {e}")
            return []
    
    def process_xml_native(self) -> bool:
        """
        Process StatPearls XML files using native Python (no MedRAG subprocess).
        
        This is the recommended method as it doesn't require subprocess calls.
        Produces JSONL files compatible with the MedRAG format.
        
        Returns:
            True if processing succeeded
        """
        logger.info("Processing StatPearls XML files (native Python)...")
        
        # Find extracted XML directory
        extracted_dir = self.raw_dir / "statpearls_NBK430685"
        
        if not extracted_dir.exists():
            # Try alternate location
            xml_files = list(self.raw_dir.glob("*.nxml"))
            if not xml_files:
                logger.error(f"No extracted XML files found in {self.raw_dir}")
                return False
            extracted_dir = self.raw_dir
        
        # Find all .nxml files
        nxml_files = sorted(extracted_dir.glob("*.nxml"))
        
        if not nxml_files:
            logger.error(f"No .nxml files found in {extracted_dir}")
            return False
        
        logger.info(f"Found {len(nxml_files)} .nxml files to process")
        
        # Create chunk output directory
        chunk_dir = self.processed_dir
        chunk_dir.mkdir(parents=True, exist_ok=True)
        
        total_chunks = 0
        errors = 0
        
        for nxml_file in nxml_files:
            try:
                chunks = self._process_single_nxml(nxml_file)
                
                if chunks:
                    # Write JSONL file
                    output_file = chunk_dir / f"{nxml_file.stem}.jsonl"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        for chunk in chunks:
                            f.write(json.dumps(chunk) + '\n')
                    
                    total_chunks += len(chunks)
                    
                    if len(nxml_files) <= 100 or (nxml_files.index(nxml_file) + 1) % 100 == 0:
                        logger.debug(f"Processed {nxml_file.name}: {len(chunks)} chunks")
            
            except Exception as e:
                logger.warning(f"Error processing {nxml_file.name}: {e}")
                errors += 1
        
        logger.info(f"✓ Native processing complete: {total_chunks} chunks from {len(nxml_files)} files ({errors} errors)")
        return total_chunks > 0
    
    def full_pipeline(self) -> bool:
        """
        Run complete pipeline: download → extract → process → load
        
        Returns:
            True if all steps succeeded
        """
        logger.info("Starting full StatPearls pipeline...")
        
        steps = [
            ("Download", self.download_raw_xml),
            ("Extract", self.extract_xml),
            ("Process (Native)", self.process_xml_native),  # Use native by default
        ]
        
        for step_name, step_fn in steps:
            logger.info(f"\n{'='*50}")
            logger.info(f"Step: {step_name}")
            logger.info(f"{'='*50}")
            
            if not step_fn():
                logger.error(f"✗ {step_name} failed. Aborting pipeline.")
                return False
            
            logger.info(f"✓ {step_name} completed")
        
        # Load documents
        logger.info(f"\n{'='*50}")
        logger.info("Step: Load")
        logger.info(f"{'='*50}")
        self.load()
        
        logger.info(f"\n{'='*50}")
        logger.info("✓ PIPELINE COMPLETED SUCCESSFULLY")
        logger.info(f"{'='*50}")
        
        return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    downloader = StatPearlsDownloader(
        corpus_dir="corpus/statpearls",
        # medrag_repo_path auto-detected to rag/data_sources/MedRAG
        skip_download=False,  # Set to True if already downloaded
    )
    
    if not downloader.validate():
        print("Validation failed!")
        exit(1)
    
    # Run full pipeline
    success = downloader.full_pipeline()
    
    if success:
        print(f"\n✓ Loaded {len(downloader.documents)} documents")
        if downloader.documents:
            print(f"\nFirst document:")
            doc = downloader.documents[0]
            print(f"  ID: {doc.document_id}")
            print(f"  Title: {doc.title}")
            print(f"  Confidence: {doc.confidence_score}")
    else:
        print("\n✗ Pipeline failed")
        exit(1)

