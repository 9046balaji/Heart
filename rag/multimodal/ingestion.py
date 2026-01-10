"""
Multimodal Ingestion Service for Cardio AI

Bridges multimodal document processing with existing VectorStore.
Handles:
- Document parsing and content extraction
- Multimodal content processing (tables, images, equations)
- Chunking and embedding generation
- Storage in VectorStore

Integrates with:
- rag.vector_store.VectorStore for storage
- rag.embedding_service.EmbeddingService for embeddings
- core.llm.gateway.LLMGateway for LLM/vision processing
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field

from .config import MultimodalConfig, ContextConfig
from .processors import (
    DocumentParser,
    ContextExtractor,
    TableProcessor,
    ImageProcessor,
    EquationProcessor,
    ParsedContent,
    ProcessedDocument,
    DocStatus,
    ContentType,
    get_processor_for_type,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of document ingestion"""
    doc_id: str
    file_path: str
    success: bool
    chunks_created: int = 0
    tables_processed: int = 0
    images_processed: int = 0
    equations_processed: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkData:
    """Data for a single chunk to be stored"""
    chunk_id: str
    text: str
    doc_id: str
    chunk_type: str  # text, table, image, equation
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


class MultimodalIngestionService:
    """
    Service for ingesting multimodal documents into the RAG system.
    
    Handles parsing, processing, chunking, and storage of documents
    containing text, tables, images, and equations.
    """
    
    def __init__(
        self,
        vector_store: Optional[Any] = None,
        embedding_func: Optional[Callable] = None,
        llm_func: Optional[Callable] = None,
        vision_func: Optional[Callable] = None,
        config: Optional[MultimodalConfig] = None
    ):
        """
        Initialize the ingestion service.
        
        Args:
            vector_store: VectorStore instance for storing chunks
            embedding_func: Function to generate embeddings
            llm_func: LLM function for text analysis
            vision_func: Vision function for image analysis
            config: Multimodal configuration
        """
        self.vector_store = vector_store
        self.embedding_func = embedding_func
        self.llm_func = llm_func
        self.vision_func = vision_func
        self.config = config or MultimodalConfig()
        
        # Initialize parser
        self.parser = DocumentParser(config)
        
        # Initialize context extractor
        context_config = ContextConfig(
            context_window=self.config.context_window,
            max_context_tokens=self.config.max_context_tokens
        )
        self.context_extractor = ContextExtractor(context_config)
        
        # Initialize processors
        self.processors = {}
        if self.config.enable_table_processing:
            self.processors["table"] = TableProcessor(
                llm_func=llm_func,
                context_extractor=self.context_extractor,
                config=config
            )
        if self.config.enable_image_processing:
            self.processors["image"] = ImageProcessor(
                llm_func=llm_func,
                vision_func=vision_func,
                context_extractor=self.context_extractor,
                config=config
            )
        if self.config.enable_equation_processing:
            self.processors["equation"] = EquationProcessor(
                llm_func=llm_func,
                context_extractor=self.context_extractor,
                config=config
            )
        
        logger.info(f"MultimodalIngestionService initialized with processors: {list(self.processors.keys())}")
    
    async def ingest_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> IngestionResult:
        """
        Ingest a single document.
        
        Args:
            file_path: Path to the document
            metadata: Additional metadata to attach to chunks
            
        Returns:
            IngestionResult with ingestion details
        """
        logger.info(f"Starting ingestion: {file_path}")
        metadata = metadata or {}
        
        try:
            # Check file exists
            if not os.path.exists(file_path):
                return IngestionResult(
                    doc_id="",
                    file_path=file_path,
                    success=False,
                    error=f"File not found: {file_path}"
                )
            
            # Parse document
            doc_id, content_list = await self.parser.parse(file_path)
            logger.info(f"Parsed document {doc_id}: {len(content_list)} content items")
            
            # Process content
            processed = await self._process_content(doc_id, file_path, content_list, metadata)
            
            # Create chunks and store
            chunks = await self._create_chunks(processed)
            
            # Store in vector store
            if self.vector_store and chunks:
                await self._store_chunks(chunks)
            
            result = IngestionResult(
                doc_id=doc_id,
                file_path=file_path,
                success=True,
                chunks_created=len(chunks),
                tables_processed=len(processed.tables),
                images_processed=len(processed.images),
                equations_processed=len(processed.equations),
                metadata={"content_items": len(content_list)}
            )
            
            logger.info(f"Ingestion complete: {result.chunks_created} chunks created")
            return result
            
        except Exception as e:
            logger.error(f"Ingestion failed for {file_path}: {str(e)}")
            return IngestionResult(
                doc_id="",
                file_path=file_path,
                success=False,
                error=str(e)
            )
    
    async def ingest_batch(
        self,
        file_paths: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 3
    ) -> List[IngestionResult]:
        """
        Ingest multiple documents with controlled concurrency.
        
        Args:
            file_paths: List of file paths to ingest
            metadata: Common metadata for all documents
            max_concurrent: Maximum concurrent ingestions
            
        Returns:
            List of IngestionResult for each document
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def ingest_with_limit(path: str) -> IngestionResult:
            async with semaphore:
                return await self.ingest_document(path, metadata)
        
        tasks = [ingest_with_limit(path) for path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(IngestionResult(
                    doc_id="",
                    file_path=file_paths[i],
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_content(
        self,
        doc_id: str,
        file_path: str,
        content_list: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> ProcessedDocument:
        """Process all content items in a document"""
        processed = ProcessedDocument(
            doc_id=doc_id,
            file_path=file_path,
            status=DocStatus.PROCESSING,
            metadata=metadata
        )
        
        for i, item in enumerate(content_list):
            if not isinstance(item, dict):
                continue
            
            content_type = item.get("type", "text")
            
            # Extract context for multimodal items
            context = ""
            if content_type in ("table", "image", "equation"):
                context = self.context_extractor.extract_context(
                    content_list, i, content_type
                )
            
            # Process based on type
            if content_type == "text":
                text = item.get("text", "")
                if text.strip():
                    processed.text_chunks.append(ParsedContent(
                        content_type=ContentType.TEXT,
                        raw_content=text,
                        processed_content=text,
                        position=i
                    ))
            
            elif content_type == "table" and "table" in self.processors:
                try:
                    result = await self.processors["table"].process(item, context, metadata)
                    result.position = i
                    processed.tables.append(result)
                except Exception as e:
                    logger.warning(f"Table processing failed at position {i}: {e}")
            
            elif content_type == "image" and "image" in self.processors:
                try:
                    result = await self.processors["image"].process(item, context, metadata)
                    result.position = i
                    processed.images.append(result)
                except Exception as e:
                    logger.warning(f"Image processing failed at position {i}: {e}")
            
            elif content_type == "equation" and "equation" in self.processors:
                try:
                    result = await self.processors["equation"].process(item, context, metadata)
                    result.position = i
                    processed.equations.append(result)
                except Exception as e:
                    logger.warning(f"Equation processing failed at position {i}: {e}")
        
        processed.status = DocStatus.COMPLETED
        return processed
    
    async def _create_chunks(
        self,
        processed: ProcessedDocument
    ) -> List[ChunkData]:
        """Create chunks from processed document"""
        chunks = []
        chunk_counter = 0
        
        # Text chunks
        for item in processed.text_chunks:
            text = item.processed_content or item.raw_content
            if not text.strip():
                continue
            
            # Split large text into smaller chunks
            text_chunks = self._split_text(text, self.config.chunk_size, self.config.chunk_overlap)
            
            for chunk_text in text_chunks:
                chunk_id = f"{processed.doc_id}_text_{chunk_counter}"
                chunks.append(ChunkData(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    doc_id=processed.doc_id,
                    chunk_type="text",
                    metadata={
                        "file_path": processed.file_path,
                        "position": item.position,
                        **processed.metadata
                    }
                ))
                chunk_counter += 1
        
        # Table chunks
        for item in processed.tables:
            text = item.processed_content or item.raw_content
            if not text.strip():
                continue
            
            chunk_id = f"{processed.doc_id}_table_{chunk_counter}"
            chunks.append(ChunkData(
                chunk_id=chunk_id,
                text=text,
                doc_id=processed.doc_id,
                chunk_type="table",
                metadata={
                    "file_path": processed.file_path,
                    "position": item.position,
                    "table_caption": item.metadata.get("caption", ""),
                    **processed.metadata
                }
            ))
            chunk_counter += 1
        
        # Image chunks (store description)
        for item in processed.images:
            text = item.processed_content or f"Image: {item.raw_content}"
            
            chunk_id = f"{processed.doc_id}_image_{chunk_counter}"
            chunks.append(ChunkData(
                chunk_id=chunk_id,
                text=text,
                doc_id=processed.doc_id,
                chunk_type="image",
                metadata={
                    "file_path": processed.file_path,
                    "position": item.position,
                    "image_path": item.raw_content,
                    "image_caption": item.metadata.get("caption", ""),
                    **processed.metadata
                }
            ))
            chunk_counter += 1
        
        # Equation chunks
        for item in processed.equations:
            text = item.processed_content or item.raw_content
            if not text.strip():
                continue
            
            chunk_id = f"{processed.doc_id}_equation_{chunk_counter}"
            chunks.append(ChunkData(
                chunk_id=chunk_id,
                text=text,
                doc_id=processed.doc_id,
                chunk_type="equation",
                metadata={
                    "file_path": processed.file_path,
                    "position": item.position,
                    **processed.metadata
                }
            ))
            chunk_counter += 1
        
        return chunks
    
    def _split_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """Split text into overlapping chunks"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for boundary in [". ", ".\n", "? ", "! ", "\n\n"]:
                    last_boundary = chunk.rfind(boundary)
                    if last_boundary > chunk_size // 2:  # At least half the chunk
                        chunk = chunk[:last_boundary + len(boundary)]
                        end = start + len(chunk)
                        break
            
            chunks.append(chunk.strip())
            start = end - overlap
        
        return [c for c in chunks if c]  # Filter empty chunks
    
    async def _store_chunks(self, chunks: List[ChunkData]) -> None:
        """Store chunks in vector store"""
        if not self.vector_store:
            logger.warning("No vector store configured, chunks not stored")
            return
        
        # Generate embeddings if function provided
        if self.embedding_func:
            texts = [chunk.text for chunk in chunks]
            try:
                embeddings = await self._generate_embeddings(texts)
                for chunk, embedding in zip(chunks, embeddings):
                    chunk.embedding = embedding
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
        
        # Store in vector store
        try:
            # Prepare documents for vector store
            documents = []
            embeddings_list = []
            metadatas = []
            ids = []
            
            for chunk in chunks:
                documents.append(chunk.text)
                embeddings_list.append(chunk.embedding)
                metadatas.append({
                    "doc_id": chunk.doc_id,
                    "chunk_type": chunk.chunk_type,
                    **chunk.metadata
                })
                ids.append(chunk.chunk_id)
            
            # Use vector store's add method
            # This assumes vector store has an add method compatible with ChromaDB
            if hasattr(self.vector_store, 'add_documents'):
                await self._add_to_store_async(documents, embeddings_list, metadatas, ids)
            elif hasattr(self.vector_store, 'add'):
                self.vector_store.add(
                    documents=documents,
                    embeddings=embeddings_list if embeddings_list[0] else None,
                    metadatas=metadatas,
                    ids=ids
                )
            else:
                logger.warning("Vector store does not have compatible add method")
            
            logger.info(f"Stored {len(chunks)} chunks in vector store")
            
        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            raise
    
    async def _add_to_store_async(
        self,
        documents: List[str],
        embeddings: List[Optional[List[float]]],
        metadatas: List[Dict],
        ids: List[str]
    ) -> None:
        """Async wrapper for vector store add"""
        if hasattr(self.vector_store, 'add_documents'):
            if asyncio.iscoroutinefunction(self.vector_store.add_documents):
                await self.vector_store.add_documents(documents, embeddings, metadatas, ids)
            else:
                self.vector_store.add_documents(documents, embeddings, metadatas, ids)
    
    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts"""
        if asyncio.iscoroutinefunction(self.embedding_func):
            return await self.embedding_func(texts)
        return self.embedding_func(texts)


class MultimodalRetriever:
    """
    Retriever that handles multimodal content in search results.
    Enriches retrieval with context about tables, images, and equations.
    """
    
    def __init__(
        self,
        vector_store: Optional[Any] = None,
        llm_func: Optional[Callable] = None
    ):
        self.vector_store = vector_store
        self.llm_func = llm_func
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_types: Filter by chunk types (text, table, image, equation)
            
        Returns:
            List of retrieved chunks with metadata
        """
        if not self.vector_store:
            return []
        
        try:
            # Build filter if specified
            where_filter = None
            if filter_types:
                where_filter = {"chunk_type": {"$in": filter_types}}
            
            # Query vector store
            results = await self._query_store(query, top_k, where_filter)
            
            # Enrich results with type-specific formatting
            enriched = []
            for result in results:
                chunk_type = result.get("metadata", {}).get("chunk_type", "text")
                
                enriched_result = {
                    "text": result.get("text", ""),
                    "chunk_type": chunk_type,
                    "score": result.get("score", 0.0),
                    "metadata": result.get("metadata", {}),
                }
                
                # Add type-specific context
                if chunk_type == "table":
                    enriched_result["display_hint"] = "table"
                    enriched_result["caption"] = result.get("metadata", {}).get("table_caption", "")
                elif chunk_type == "image":
                    enriched_result["display_hint"] = "image_description"
                    enriched_result["image_path"] = result.get("metadata", {}).get("image_path", "")
                elif chunk_type == "equation":
                    enriched_result["display_hint"] = "equation"
                
                enriched.append(enriched_result)
            
            return enriched
            
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []
    
    async def _query_store(
        self,
        query: str,
        top_k: int,
        where_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Query the vector store"""
        if hasattr(self.vector_store, 'query'):
            if asyncio.iscoroutinefunction(self.vector_store.query):
                return await self.vector_store.query(query, n_results=top_k, where=where_filter)
            return self.vector_store.query(query, n_results=top_k, where=where_filter)
        elif hasattr(self.vector_store, 'similarity_search'):
            if asyncio.iscoroutinefunction(self.vector_store.similarity_search):
                return await self.vector_store.similarity_search(query, k=top_k)
            return self.vector_store.similarity_search(query, k=top_k)
        return []


# =============================================================================
# ADDITIONAL FEATURES FROM RAG-ANYTHING
# =============================================================================

class VLMEnhancedRetriever(MultimodalRetriever):
    """
    VLM-Enhanced Retriever that automatically analyzes images in retrieved context.
    
    When documents contain images, the system:
    1. Retrieves relevant context containing image paths
    2. Loads and encodes images as base64
    3. Sends both text context and images to VLM for comprehensive analysis
    """
    
    def __init__(
        self,
        vector_store: Optional[Any] = None,
        llm_func: Optional[Callable] = None,
        vision_func: Optional[Callable] = None
    ):
        super().__init__(vector_store, llm_func)
        self.vision_func = vision_func
    
    async def query_with_vlm(
        self,
        query: str,
        top_k: int = 5,
        vlm_enhanced: bool = True,
        mode: str = "hybrid"
    ) -> Dict[str, Any]:
        """
        Query with optional VLM enhancement for image analysis.
        
        Args:
            query: Search query
            top_k: Number of results to retrieve
            vlm_enhanced: Whether to analyze images with VLM
            mode: Query mode (hybrid, local, global, naive)
            
        Returns:
            Dict with answer, sources, and any image analyses
        """
        import base64
        
        # First, retrieve relevant chunks
        results = await self.retrieve(query, top_k)
        
        if not results:
            return {"answer": "No relevant information found.", "sources": []}
        
        # Separate image chunks from text chunks
        text_context = []
        image_chunks = []
        
        for result in results:
            if result.get("chunk_type") == "image":
                image_chunks.append(result)
            else:
                text_context.append(result.get("text", ""))
        
        combined_context = "\n\n".join(text_context)
        
        # If VLM enhanced and we have images, analyze them
        image_analyses = []
        if vlm_enhanced and self.vision_func and image_chunks:
            for img_chunk in image_chunks[:3]:  # Limit to 3 images
                image_path = img_chunk.get("image_path", "")
                if image_path and os.path.exists(image_path):
                    try:
                        with open(image_path, "rb") as f:
                            image_data = base64.b64encode(f.read()).decode("utf-8")
                        
                        # Analyze image with VLM
                        analysis = await self._analyze_image_with_vlm(
                            image_data, query, img_chunk.get("text", "")
                        )
                        image_analyses.append({
                            "image_path": image_path,
                            "analysis": analysis
                        })
                    except Exception as e:
                        logger.warning(f"Failed to analyze image {image_path}: {e}")
        
        # Generate answer using LLM
        answer = await self._generate_answer(
            query, combined_context, image_analyses
        )
        
        return {
            "answer": answer,
            "sources": results,
            "image_analyses": image_analyses,
            "mode": mode
        }
    
    async def _analyze_image_with_vlm(
        self,
        image_data: str,
        query: str,
        context: str
    ) -> str:
        """Analyze image using vision model"""
        prompt = f"""Analyze this image in the context of the following query:

Query: {query}

Context: {context}

Provide a detailed analysis of the image and how it relates to the query."""
        
        if asyncio.iscoroutinefunction(self.vision_func):
            return await self.vision_func(prompt, image_data=image_data)
        return self.vision_func(prompt, image_data=image_data)
    
    async def _generate_answer(
        self,
        query: str,
        context: str,
        image_analyses: List[Dict[str, str]]
    ) -> str:
        """Generate answer using LLM with all context"""
        if not self.llm_func:
            return context
        
        image_context = ""
        if image_analyses:
            image_context = "\n\nImage Analyses:\n"
            for i, analysis in enumerate(image_analyses, 1):
                image_context += f"\n[Image {i}]: {analysis['analysis']}"
        
        prompt = f"""Based on the following context, answer the query.

Context:
{context}
{image_context}

Query: {query}

Provide a comprehensive answer integrating information from both text and images."""
        
        if asyncio.iscoroutinefunction(self.llm_func):
            return await self.llm_func(prompt)
        return self.llm_func(prompt)


class MultimodalQueryService:
    """
    Service for multimodal queries with user-provided content.
    
    Supports:
    - Pure text queries (standard RAG)
    - VLM-enhanced queries (automatic image analysis)
    - Multimodal queries with user-provided tables/equations
    """
    
    def __init__(
        self,
        retriever: MultimodalRetriever,
        llm_func: Optional[Callable] = None,
        vision_func: Optional[Callable] = None
    ):
        self.retriever = retriever
        self.llm_func = llm_func
        self.vision_func = vision_func
    
    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 5
    ) -> str:
        """Standard text query"""
        results = await self.retriever.retrieve(query, top_k)
        
        if not results:
            return "No relevant information found."
        
        context = "\n\n".join([r.get("text", "") for r in results])
        
        if self.llm_func:
            prompt = f"Based on the following context, answer the query.\n\nContext:\n{context}\n\nQuery: {query}"
            if asyncio.iscoroutinefunction(self.llm_func):
                return await self.llm_func(prompt)
            return self.llm_func(prompt)
        
        return context
    
    async def query_with_multimodal(
        self,
        query: str,
        multimodal_content: List[Dict[str, Any]],
        mode: str = "hybrid",
        top_k: int = 5
    ) -> str:
        """
        Query with user-provided multimodal content.
        
        Args:
            query: Search query
            multimodal_content: List of multimodal items, e.g.:
                [{"type": "table", "table_data": "...", "table_caption": "..."}]
                [{"type": "equation", "latex": "...", "equation_caption": "..."}]
            mode: Query mode
            top_k: Number of results
            
        Returns:
            Generated answer integrating both retrieved and provided content
        """
        # Retrieve relevant context
        results = await self.retriever.retrieve(query, top_k)
        context = "\n\n".join([r.get("text", "") for r in results])
        
        # Format multimodal content
        multimodal_context = self._format_multimodal_content(multimodal_content)
        
        # Generate answer
        prompt = f"""Based on the following context and multimodal content, answer the query.

Retrieved Context:
{context}

User-Provided Content:
{multimodal_context}

Query: {query}

Provide a comprehensive answer that integrates all available information."""
        
        if self.llm_func:
            if asyncio.iscoroutinefunction(self.llm_func):
                return await self.llm_func(prompt)
            return self.llm_func(prompt)
        
        return f"Context: {context}\n\nMultimodal: {multimodal_context}"
    
    def _format_multimodal_content(
        self,
        content: List[Dict[str, Any]]
    ) -> str:
        """Format multimodal content for prompt"""
        formatted = []
        
        for item in content:
            content_type = item.get("type", "unknown")
            
            if content_type == "table":
                table_data = item.get("table_data", item.get("table_body", ""))
                caption = item.get("table_caption", "")
                formatted.append(f"[Table: {caption}]\n{table_data}")
            
            elif content_type == "equation":
                latex = item.get("latex", "")
                caption = item.get("equation_caption", "")
                formatted.append(f"[Equation: {caption}]\nLaTeX: {latex}")
            
            elif content_type == "image":
                caption = item.get("image_caption", "")
                description = item.get("description", "")
                formatted.append(f"[Image: {caption}]\n{description}")
            
            else:
                formatted.append(f"[{content_type}]: {item.get('content', str(item))}")
        
        return "\n\n".join(formatted)

    async def query_with_multimodal_context(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        include_images: bool = False,
        include_tables: bool = False,
    ) -> Dict[str, Any]:
        """
        Query with multimodal context from documents.
        
        Args:
            query: Search query
            documents: Pre-retrieved documents
            include_images: Whether to include image context
            include_tables: Whether to include table context
            
        Returns:
            Dict with 'context' and 'results' keys
        """
        context_parts = []
        enhanced_results = documents.copy() if documents else []
        
        for doc in (documents or []):
            # Extract text content
            text = doc.get("text", doc.get("content", ""))
            if text:
                context_parts.append(text)
            
            # Extract multimodal content if requested
            metadata = doc.get("metadata", {})
            
            if include_tables and metadata.get("table_data"):
                table_data = metadata.get("table_data", "")
                table_caption = metadata.get("table_caption", "")
                context_parts.append(f"[Table: {table_caption}]\n{table_data}")
            
            if include_images and metadata.get("image_path"):
                image_caption = metadata.get("image_caption", "")
                context_parts.append(f"[Image: {image_caption}]")
        
        context = "\n\n".join(context_parts) if context_parts else None
        
        return {
            "context": context,
            "results": enhanced_results
        }


class DirectContentInserter:
    """
    Insert pre-parsed content directly without document parsing.
    
    Useful when:
    - Content comes from external parsers
    - Processing programmatically generated content
    - Inserting content from multiple sources
    - Reusing cached parsing results
    """
    
    def __init__(
        self,
        ingestion_service: MultimodalIngestionService
    ):
        self.ingestion_service = ingestion_service
    
    async def insert_content_list(
        self,
        content_list: List[Dict[str, Any]],
        file_path: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        display_stats: bool = True
    ) -> IngestionResult:
        """
        Insert a pre-parsed content list directly.
        
        Args:
            content_list: List of content items with format:
                - Text: {"type": "text", "text": "...", "page_idx": 0}
                - Image: {"type": "image", "img_path": "...", "image_caption": [...], "page_idx": 1}
                - Table: {"type": "table", "table_body": "...", "table_caption": [...], "page_idx": 2}
                - Equation: {"type": "equation", "latex": "...", "text": "...", "page_idx": 3}
            file_path: Reference file path for citations
            doc_id: Optional custom document ID
            metadata: Additional metadata
            display_stats: Whether to log statistics
            
        Returns:
            IngestionResult with details
        """
        import hashlib
        
        metadata = metadata or {}
        
        # Generate doc_id if not provided
        if not doc_id:
            content_hash = hashlib.md5(str(content_list).encode()).hexdigest()[:16]
            doc_id = f"doc-{content_hash}"
        
        # Count content types
        stats = {"text": 0, "table": 0, "image": 0, "equation": 0}
        for item in content_list:
            item_type = item.get("type", "text")
            if item_type in stats:
                stats[item_type] += 1
        
        if display_stats:
            logger.info(f"Inserting content list: {len(content_list)} items")
            logger.info(f"  - Text: {stats['text']}, Tables: {stats['table']}, "
                       f"Images: {stats['image']}, Equations: {stats['equation']}")
        
        try:
            # Process the content list
            processed = await self.ingestion_service._process_content(
                doc_id, file_path, content_list, metadata
            )
            
            # Create chunks
            chunks = await self.ingestion_service._create_chunks(processed)
            
            # Store in vector store
            if self.ingestion_service.vector_store and chunks:
                await self.ingestion_service._store_chunks(chunks)
            
            return IngestionResult(
                doc_id=doc_id,
                file_path=file_path,
                success=True,
                chunks_created=len(chunks),
                tables_processed=stats["table"],
                images_processed=stats["image"],
                equations_processed=stats["equation"],
                metadata={"content_items": len(content_list)}
            )
            
        except Exception as e:
            logger.error(f"Content list insertion failed: {e}")
            return IngestionResult(
                doc_id=doc_id,
                file_path=file_path,
                success=False,
                error=str(e)
            )


class FolderProcessor:
    """
    Batch process entire folders of documents.
    
    Features:
    - Recursive folder traversal
    - File extension filtering
    - Concurrent processing with worker limit
    - Progress tracking
    """
    
    def __init__(
        self,
        ingestion_service: MultimodalIngestionService,
        max_workers: int = 4
    ):
        self.ingestion_service = ingestion_service
        self.max_workers = max_workers
    
    async def process_folder(
        self,
        folder_path: str,
        output_dir: Optional[str] = None,
        file_extensions: Optional[List[str]] = None,
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[IngestionResult]:
        """
        Process all documents in a folder.
        
        Args:
            folder_path: Path to folder
            output_dir: Output directory for processed files
            file_extensions: Filter by extensions (e.g., [".pdf", ".docx"])
            recursive: Process subfolders
            metadata: Common metadata for all documents
            
        Returns:
            List of IngestionResult for each document
        """
        # Default extensions
        if file_extensions is None:
            file_extensions = [".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".html", ".md"]
        
        # Normalize extensions
        file_extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
                         for ext in file_extensions]
        
        # Find all matching files
        folder = Path(folder_path)
        if not folder.exists():
            logger.error(f"Folder not found: {folder_path}")
            return []
        
        files = []
        if recursive:
            for ext in file_extensions:
                files.extend(folder.rglob(f"*{ext}"))
        else:
            for ext in file_extensions:
                files.extend(folder.glob(f"*{ext}"))
        
        file_paths = [str(f) for f in files]
        
        logger.info(f"Found {len(file_paths)} files to process in {folder_path}")
        
        if not file_paths:
            return []
        
        # Process with concurrency control
        return await self.ingestion_service.ingest_batch(
            file_paths,
            metadata=metadata,
            max_concurrent=self.max_workers
        )


class EntityExtractor:
    """
    Extract entities and relationships for knowledge graph integration.
    
    Extracts:
    - Medications, conditions, procedures
    - Lab tests, vital signs, symptoms
    - Relationships between entities
    """
    
    def __init__(
        self,
        llm_func: Optional[Callable] = None
    ):
        self.llm_func = llm_func
    
    async def extract_entities(
        self,
        content: str,
        content_type: str = "text"
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from content.
        
        Args:
            content: Text content to analyze
            content_type: Type of content (text, table, etc.)
            
        Returns:
            Dict with entities and relationships
        """
        if not self.llm_func:
            return {"entities": [], "relationships": []}
        
        prompt = f"""Extract medical entities and relationships from the following {content_type} content.

Content:
{content}

Return a JSON response with:
{{
    "entities": [
        {{
            "name": "<entity name>",
            "type": "<medication|condition|procedure|lab_test|vital_sign|symptom|provider>",
            "attributes": {{"<key>": "<value>"}}
        }}
    ],
    "relationships": [
        {{
            "from": "<entity1 name>",
            "to": "<entity2 name>",
            "type": "<treats|causes|indicates|monitors|prescribes|contraindicated_with>"
        }}
    ]
}}

Only return the JSON, no additional text."""
        
        try:
            if asyncio.iscoroutinefunction(self.llm_func):
                response = await self.llm_func(prompt)
            else:
                response = self.llm_func(prompt)
            
            # Parse JSON from response
            import json
            # Try to extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(response[start:end])
            
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
        
        return {"entities": [], "relationships": []}
    
    async def extract_from_table(
        self,
        table_content: str,
        table_caption: str = ""
    ) -> Dict[str, Any]:
        """Extract entities specifically from table content"""
        context = f"Table Caption: {table_caption}\n\n{table_content}"
        return await self.extract_entities(context, "table")
    
    async def extract_from_chunk(
        self,
        chunk: ChunkData
    ) -> Dict[str, Any]:
        """Extract entities from a processed chunk"""
        return await self.extract_entities(chunk.text, chunk.chunk_type)

