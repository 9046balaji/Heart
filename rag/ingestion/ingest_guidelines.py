"""
ingest_guidelines.py - Advanced Medical Guideline Ingestion with DeepDoc-Style Layout Analysis

This script:
1. Reads medical PDF files with layout-aware parsing
2. Detects and preserves table structure (critical for dosage info)
3. Separates table data from text blocks to prevent corruption
4. Applies Semantic Chunking to preserve medical concepts
5. Builds RAPTOR trees for hierarchical retrieval
6. Stores everything in PostgreSQL/pgvector with citation anchoring

Key Features:
- Table Detection: Uses PyMuPDF's find_tables() to identify dosage/protocol tables
- Layout Analysis: Prevents table columns from being read as running text
- Chunk Size Control: Respects token limits (512 for reranker, 2000 for context)
- Medical Metadata: Preserves source location (page, table, text block)

Usage:
    python rag/ingestion/ingest_guidelines.py --path ./data/guidelines/ --rebuild
"""

import asyncio
import argparse
import logging
import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Add project root to path (3 levels up from rag/ingestion/ingest_guidelines.py)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

# Production imports
from rag.vector_store import get_vector_store
from rag.embedding_service import EmbeddingService
from rag.ingestion.unified_chunker import UnifiedMedicalChunker
from rag.knowledge_base.raptor_tree_builder import MedicalRAPTORBuilder
from core.llm.llm_gateway import get_llm_gateway

# PDF reading
import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Classification of extracted content."""
    TABLE = "table"
    TEXT = "text"
    FIGURE = "figure"
    HEADER = "header"
    LIST = "list"


@dataclass
class LayoutChunk:
    """
    A chunk extracted from a PDF with layout information.
    Similar to RAGFlow's layout-aware extraction.
    """
    content: str
    content_type: ContentType
    page_num: int
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    metadata: Dict
    chunk_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.chunk_id:
            # Generate a unique ID based on page and position
            self.chunk_id = f"chunk_{self.page_num}_{hash(self.content) % 10000}"


class LayoutAnalyzer:
    """
    DeepDoc-style layout analyzer for medical PDFs.
    
    Detects tables, headers, and text blocks separately.
    Prevents table data from being corrupted when merged with running text.
    """
    
    def __init__(self, max_text_block_chars: int = 2000):
        self.max_text_block_chars = max_text_block_chars
    
    def analyze_page(self, page: fitz.Page) -> List[LayoutChunk]:
        """
        Analyze a single PDF page for layout structure.
        
        Returns:
            List of LayoutChunks preserving structure
        """
        chunks = []
        page_num = page.number
        
        # Step 1: Detect and extract tables (highest priority)
        table_chunks = self._extract_tables(page, page_num)
        chunks.extend(table_chunks)
        
        # Step 2: Get table bounding boxes to exclude from text extraction
        table_bboxes = [chunk.bbox for chunk in table_chunks]
        
        # Step 3: Extract text blocks, excluding table areas
        text_chunks = self._extract_text_blocks(page, page_num, table_bboxes)
        chunks.extend(text_chunks)
        
        # Step 4: Detect and extract headers (structural elements)
        header_chunks = self._extract_headers(page, page_num, table_bboxes)
        chunks.extend(header_chunks)
        
        return chunks
    
    def _extract_tables(self, page: fitz.Page, page_num: int) -> List[LayoutChunk]:
        """Extract tables from page using PyMuPDF's table detection."""
        chunks = []
        
        try:
            # PyMuPDF's find_tables() returns table objects
            tables = page.find_tables()
            
            for table_idx, table in enumerate(tables):
                # Convert table to markdown for LLM compatibility
                table_md = self._table_to_markdown(table)
                
                # Get table's bounding box
                bbox = table.bbox
                
                chunk = LayoutChunk(
                    content=table_md,
                    content_type=ContentType.TABLE,
                    page_num=page_num,
                    bbox=bbox,
                    metadata={
                        "source": "pdf_table",
                        "table_index": table_idx,
                        "preserved_structure": True,
                        "extracted_method": "pymupdf_find_tables"
                    }
                )
                chunks.append(chunk)
                
                logger.debug(f"✓ Extracted table {table_idx} from page {page_num}")
                
        except Exception as e:
            logger.warning(f"Table extraction failed on page {page_num}: {e}")
        
        return chunks
    
    def _table_to_markdown(self, table: fitz.Table) -> str:
        """Convert PyMuPDF table to Markdown format."""
        try:
            # Get table data
            rows = table.extract()
            
            if not rows:
                return ""
            
            # Build markdown table
            lines = []
            for i, row in enumerate(rows):
                # Clean cells
                cells = [str(cell).strip() for cell in row]
                line = "| " + " | ".join(cells) + " |"
                lines.append(line)
                
                # Add separator after header row
                if i == 0:
                    separators = ["---" for _ in cells]
                    lines.append("| " + " | ".join(separators) + " |")
            
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to convert table to markdown: {e}")
            return ""
    
    def _extract_text_blocks(
        self, 
        page: fitz.Page, 
        page_num: int, 
        table_bboxes: List[Tuple[float, float, float, float]]
    ) -> List[LayoutChunk]:
        """
        Extract text blocks, excluding areas occupied by tables.
        Prevents table columns from being read as running text.
        """
        chunks = []
        
        try:
            text_blocks = page.get_text("blocks")  # Returns list of (x0, y0, x1, y1, text, block_num, block_type)
            
            for block in text_blocks:
                x0, y0, x1, y1, text, block_num, block_type = block
                bbox = (x0, y0, x1, y1)
                
                # Skip if this block overlaps with any table
                if self._overlaps_with_tables(bbox, table_bboxes):
                    logger.debug(f"Skipping text block {block_num} (overlaps with table)")
                    continue
                
                # Skip empty or very small blocks
                text = text.strip()
                if not text or len(text) < 10:
                    continue
                
                # Split large blocks to respect max_text_block_chars
                if len(text) > self.max_text_block_chars:
                    sub_chunks = self._split_text_block(text, bbox, page_num)
                    chunks.extend(sub_chunks)
                else:
                    chunk = LayoutChunk(
                        content=text,
                        content_type=ContentType.TEXT,
                        page_num=page_num,
                        bbox=bbox,
                        metadata={
                            "source": "pdf_text",
                            "block_num": block_num,
                            "block_type": block_type
                        }
                    )
                    chunks.append(chunk)
        
        except Exception as e:
            logger.warning(f"Text block extraction failed on page {page_num}: {e}")
        
        return chunks
    
    def _overlaps_with_tables(
        self, 
        bbox: Tuple[float, float, float, float],
        table_bboxes: List[Tuple[float, float, float, float]],
        overlap_threshold: float = 0.1
    ) -> bool:
        """
        Check if a text block bbox overlaps with any table bbox.
        
        Args:
            bbox: Text block bounding box
            table_bboxes: List of table bounding boxes
            overlap_threshold: Minimum overlap percentage to consider intersection
        
        Returns:
            True if overlap detected, False otherwise
        """
        x0, y0, x1, y1 = bbox
        block_area = (x1 - x0) * (y1 - y0)
        
        if block_area == 0:
            return False
        
        for table_bbox in table_bboxes:
            tx0, ty0, tx1, ty1 = table_bbox
            
            # Calculate intersection
            inter_x0 = max(x0, tx0)
            inter_y0 = max(y0, ty0)
            inter_x1 = min(x1, tx1)
            inter_y1 = min(y1, ty1)
            
            if inter_x0 < inter_x1 and inter_y0 < inter_y1:
                intersection_area = (inter_x1 - inter_x0) * (inter_y1 - inter_y0)
                overlap_ratio = intersection_area / block_area
                
                if overlap_ratio > overlap_threshold:
                    return True
        
        return False
    
    def _split_text_block(
        self, 
        text: str, 
        bbox: Tuple[float, float, float, float],
        page_num: int
    ) -> List[LayoutChunk]:
        """Split large text blocks into smaller chunks."""
        chunks = []
        
        # Split by sentences for better semantic boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > self.max_text_block_chars:
                if current_chunk.strip():
                    chunk = LayoutChunk(
                        content=current_chunk.strip(),
                        content_type=ContentType.TEXT,
                        page_num=page_num,
                        bbox=bbox,
                        metadata={"source": "pdf_text", "split": True}
                    )
                    chunks.append(chunk)
                current_chunk = sentence
            else:
                current_chunk += " " + sentence
        
        if current_chunk.strip():
            chunk = LayoutChunk(
                content=current_chunk.strip(),
                content_type=ContentType.TEXT,
                page_num=page_num,
                bbox=bbox,
                metadata={"source": "pdf_text", "split": True}
            )
            chunks.append(chunk)
        
        return chunks
    
    def _extract_headers(
        self, 
        page: fitz.Page, 
        page_num: int,
        table_bboxes: List[Tuple[float, float, float, float]]
    ) -> List[LayoutChunk]:
        """
        Extract headers and structural elements.
        Headers are typically larger font size or bold.
        """
        chunks = []
        
        try:
            # Get spans (text with formatting info)
            text_dict = page.get_text("dict")
            
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # 0 = text block
                    continue
                
                for line in block.get("lines", []):
                    line_text = ""
                    max_font_size = 0
                    is_bold = False
                    
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                        max_font_size = max(max_font_size, span.get("size", 0))
                        flags = span.get("flags", 0)
                        # Check if bold (bit 4 of flags)
                        is_bold = is_bold or (flags & 16 != 0)
                    
                    # Consider as header if large font (>14pt) or bold
                    if (max_font_size > 14 or is_bold) and line_text.strip():
                        bbox = line.get("bbox", (0, 0, 0, 0))
                        
                        # Skip if overlaps with table
                        if self._overlaps_with_tables(bbox, table_bboxes):
                            continue
                        
                        chunk = LayoutChunk(
                            content=line_text.strip(),
                            content_type=ContentType.HEADER,
                            page_num=page_num,
                            bbox=bbox,
                            metadata={
                                "source": "pdf_header",
                                "font_size": max_font_size,
                                "is_bold": is_bold
                            }
                        )
                        chunks.append(chunk)
        
        except Exception as e:
            logger.debug(f"Header extraction failed on page {page_num}: {e}")
        
        return chunks


class MedicalGuidelineIngester:
    """
    Unified ingestion pipeline for medical guidelines with DeepDoc-style layout analysis.
    
    Flow:
    1. Read PDF with layout-aware parsing (detect tables vs text)
    2. Extract layout chunks (LayoutChunk objects with metadata)
    3. Apply Semantic Chunking to preserve medical concepts
    4. Build RAPTOR Tree for hierarchical retrieval
    5. Store in PostgreSQL/pgvector with citation anchoring and content type tracking
    
    Key Improvement:
    - Tables are extracted separately using PyMuPDF's find_tables()
    - Text blocks are extracted while excluding table areas
    - Prevents dosage/protocol information from being corrupted
    """
    
    def __init__(self, vector_store: Any, llm_gateway=None):
        self.vector_store = vector_store
        self.embedding_service = EmbeddingService.get_instance()
        self.llm = llm_gateway or get_llm_gateway()
        
        # Initialize layout analyzer (DeepDoc-style)
        self.layout_analyzer = LayoutAnalyzer(max_text_block_chars=2000)
        
        # Initialize chunker and RAPTOR builder
        self.chunker = UnifiedMedicalChunker(
            embedding_service=self.embedding_service,
            strategy="semantic",
            target_size=500,
            max_chunk_size=1000
        )
        
        self.raptor_builder = MedicalRAPTORBuilder(
            llm_gateway=self.llm,
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
            max_levels=3
        )
    
    def read_pdf_with_layout(self, path: str) -> List[LayoutChunk]:
        """
        Read PDF with layout-aware parsing.
        
        Returns:
            List of LayoutChunk objects with preserved structure
        """
        try:
            doc = fitz.open(path)
            layout_chunks = []
            
            for page in doc:
                page_chunks = self.layout_analyzer.analyze_page(page)
                layout_chunks.extend(page_chunks)
            
            doc.close()
            logger.info(f"✓ Extracted {len(layout_chunks)} layout-aware chunks from {Path(path).name}")
            
            # Log breakdown
            content_types = {}
            for chunk in layout_chunks:
                ct = chunk.content_type.value
                content_types[ct] = content_types.get(ct, 0) + 1
            
            for ct, count in content_types.items():
                logger.info(f"  - {ct}: {count}")
            
            return layout_chunks
            
        except Exception as e:
            logger.error(f"Failed to read PDF with layout analysis: {e}")
            return []
    
    def read_pdf_fallback(self, path: str) -> str:
        """Fallback: Read PDF and return text content (basic method)."""
        try:
            doc = fitz.open(path)
            content = ""
            for page in doc:
                content += page.get_text()
            doc.close()
            return content
        except Exception as e:
            logger.error(f"Fallback PDF reading failed: {e}")
            return ""
    
    async def ingest_document(
        self,
        path: str,
        metadata: dict = None,
        use_layout_analysis: bool = True
    ) -> dict:
        """
        Ingest a single medical document.
        
        Args:
            path: Path to PDF file
            metadata: Additional metadata to attach
            use_layout_analysis: If True, use layout-aware parsing (recommended)
        
        Returns:
            Statistics about ingestion
        """
        doc_id = Path(path).stem
        logger.info(f"📄 Ingesting: {doc_id}")
        
        try:
            # Step 1: Read content with layout analysis
            if use_layout_analysis:
                layout_chunks = self.read_pdf_with_layout(path)
                
                if not layout_chunks:
                    logger.warning(f"Layout analysis yielded no chunks, falling back to basic reading")
                    content = self.read_pdf_fallback(path)
                    layout_chunks = []
                else:
                    # Convert layout chunks to semantic chunker format
                    content = "\n\n".join([chunk.content for chunk in layout_chunks])
            else:
                content = self.read_pdf_fallback(path)
                layout_chunks = []
            
            # Step 2: Semantic Chunking
            base_metadata = metadata or {"source": path}
            base_metadata.update({
                "ingestion_method": "layout_aware" if layout_chunks else "fallback",
                "doc_id": doc_id
            })
            
            chunks = self.chunker.chunk_medical_guideline(
                content=content,
                doc_id=doc_id,
                guideline_metadata=base_metadata
            )
            
            # Step 3: Enrich chunks with layout information if available
            if layout_chunks:
                chunks = self._enrich_chunks_with_layout_info(chunks, layout_chunks)
            
            # Step 4: Store base chunks in vector store
            base_docs = [{
                "id": c.chunk_id,
                "content": c.content,
                "metadata": c.metadata
            } for c in chunks]
            
            chunks_stored = self.vector_store.add_medical_documents_batch(base_docs)
            logger.info(f"✓ Stored {chunks_stored} base chunks")
            
            # Step 5: Build and store RAPTOR tree
            chunk_dicts = [
                {
                    "content": c.content,
                    "chunk_id": c.chunk_id,
                    "metadata": c.metadata
                }
                for c in chunks
            ]
            raptor_tree = await self.raptor_builder.build_tree(chunk_dicts, doc_id)
            raptor_nodes_stored = await self.raptor_builder.store_tree(raptor_tree)
            logger.info(f"✓ Built RAPTOR tree with {raptor_nodes_stored} nodes")
            
            return {
                "status": "success",
                "doc_id": doc_id,
                "chunks_created": len(chunks),
                "chunks_stored": chunks_stored,
                "tables_extracted": sum(
                    1 for lc in layout_chunks if lc.content_type == ContentType.TABLE
                ),
                "raptor_levels": len(raptor_tree.levels) if raptor_tree else 0,
                "raptor_nodes": raptor_nodes_stored
            }
        
        except Exception as e:
            logger.error(f"Failed to ingest {path}: {e}", exc_info=True)
            return {
                "status": "error",
                "doc_id": doc_id,
                "error": str(e)
            }
    
    def _enrich_chunks_with_layout_info(
        self,
        semantic_chunks: List,
        layout_chunks: List[LayoutChunk]
    ) -> List:
        """
        Enrich semantic chunks with layout information from layout_chunks.
        
        Attempts to match semantic chunks with layout chunks and add
        content_type metadata.
        """
        for chunk in semantic_chunks:
            # Find matching layout chunk by content overlap
            best_match = None
            best_overlap = 0
            
            for layout_chunk in layout_chunks:
                # Calculate word overlap
                chunk_words = set(chunk.content.lower().split())
                layout_words = set(layout_chunk.content.lower().split())
                overlap = len(chunk_words & layout_words) / max(len(chunk_words), 1)
                
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = layout_chunk
            
            # Add layout info if good match found
            if best_match and best_overlap > 0.3:
                if not hasattr(chunk, 'metadata'):
                    chunk.metadata = {}
                
                chunk.metadata.update({
                    "content_type": best_match.content_type.value,
                    "page_num": best_match.page_num,
                    "extraction_method": "layout_aware"
                })
        
        return semantic_chunks
    
    async def ingest_directory(
        self,
        directory: str,
        use_layout_analysis: bool = True
    ) -> List[dict]:
        """
        Ingest all PDFs in a directory.
        
        Args:
            directory: Path to directory containing PDFs
            use_layout_analysis: If True, use layout-aware parsing
        
        Returns:
            List of ingestion results
        """
        results = []
        pdf_files = sorted(list(Path(directory).glob("*.pdf")))
        
        logger.info(f"🔍 Found {len(pdf_files)} PDF files")
        
        for pdf_path in pdf_files:
            try:
                result = await self.ingest_document(
                    str(pdf_path),
                    use_layout_analysis=use_layout_analysis
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to ingest {pdf_path}: {e}")
                results.append({"doc_id": pdf_path.stem, "status": "error", "error": str(e)})
        
        return results


async def main():
    parser = argparse.ArgumentParser(description="Ingest medical guidelines with advanced chunking")
    parser.add_argument("--path", required=True, help="Path to PDF file or directory")
    parser.add_argument("--rebuild", action="store_true", help="Delete existing data first")
    args = parser.parse_args()
    
    # Initialize using factory function
    vector_store = get_vector_store()
    
    if args.rebuild:
        logger.warning("Rebuilding - deleting existing medical knowledge")
        # Ensure delete_collection exists in VectorStore
        if hasattr(vector_store, "delete_collection"):
            vector_store.delete_collection("medical_knowledge")
            vector_store.delete_collection("raptor_tree")
        else:
            logger.warning("VectorStore does not support delete_collection")
    
    ingester = MedicalGuidelineIngester(vector_store)
    
    
    path = Path(args.path)
    if path.is_file():
        result = await ingester.ingest_document(str(path))
        print(f"Ingested: {result}")
    elif path.is_dir():
        results = await ingester.ingest_directory(str(path))
        print(f"Ingested {len(results)} documents")
        for r in results:
            print(f"  - {r}")
    else:
        print(f"Path not found: {args.path}")


if __name__ == "__main__":
    asyncio.run(main())
