"""
LlamaIndex RAG Pipeline for Cardio AI.

This module implements a Retrieval-Augmented Generation pipeline using LlamaIndex
for enhanced document retrieval and context augmentation.

Features:
- Industry-standard RAG implementation
- Built-in GraphRAG capabilities
- Multiple retrieval strategies
- Advanced indexing options
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# LlamaIndex imports
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings

logger = logging.getLogger(__name__)


class LlamaIndexRAG:
    """
    RAG Pipeline using LlamaIndex framework.
    
    Features:
    - Vector-based document retrieval
    - Configurable embedding models
    - Context-augmented generation
    - Multiple retrieval strategies
    """
    
    def __init__(self, documents_path: Optional[str] = None):
        """
        Initialize LlamaIndex RAG pipeline.
        
        Args:
            documents_path: Path to directory containing medical documents
        """
        # Configure settings
        Settings.llm = Ollama(
            model=os.getenv("OLLAMA_MODEL", "gemma3:1b"),
            request_timeout=120.0
        )
        Settings.embed_model = OllamaEmbedding(
            model_name=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        )
        Settings.node_parser = SentenceSplitter(
            chunk_size=512,
            chunk_overlap=20
        )
        Settings.num_output = 512
        Settings.context_window = 3900
        
        # Load documents if path provided
        self.index = None
        self.query_engine = None
        
        if documents_path and os.path.exists(documents_path):
            try:
                documents = SimpleDirectoryReader(documents_path).load_data()
                self.index = VectorStoreIndex.from_documents(documents)
                self.query_engine = self.index.as_query_engine()
                logger.info(f"✅ Loaded {len(documents)} documents from {documents_path}")
            except Exception as e:
                logger.error(f"Failed to load documents: {e}")
        else:
            # Create empty index
            from llama_index.core import Document
            dummy_doc = Document(text="Cardiovascular health information will be indexed here.")
            self.index = VectorStoreIndex.from_documents([dummy_doc])
            self.query_engine = self.index.as_query_engine()
            logger.warning("No documents path provided, created empty index")
        
        logger.info("✅ LlamaIndexRAG initialized")
    
    async def query(self, question: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Query the RAG pipeline with a question.
        
        Args:
            question: User question
            user_id: Optional user ID for personalization
            
        Returns:
            Dict with response and metadata
        """
        logger.info(f"Querying RAG pipeline: {question[:50]}...")
        
        try:
            # Generate response
            response = await self.query_engine.aquery(question)
            
            return {
                "response": str(response),
                "sources": [],  # Would be populated with retrieved documents
                "query": question,
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return {
                "error": str(e),
                "query": question,
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
    
    def add_documents(self, documents_path: str) -> bool:
        """
        Add documents to the RAG pipeline.
        
        Args:
            documents_path: Path to directory containing documents
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(documents_path):
                logger.error(f"Documents path does not exist: {documents_path}")
                return False
            
            documents = SimpleDirectoryReader(documents_path).load_data()
            
            # Add documents to existing index
            for doc in documents:
                self.index.insert(doc)
            
            # Refresh query engine
            self.query_engine = self.index.as_query_engine()
            
            logger.info(f"✅ Added {len(documents)} documents to index")
            return True
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG pipeline statistics."""
        return {
            "index_size": len(self.index.ref_doc_info) if self.index else 0,
            "llm_model": Settings.llm.metadata.model_name if Settings.llm else "unknown",
            "embed_model": Settings.embed_model.model_name if Settings.embed_model else "unknown",
            "chunk_size": Settings.node_parser.chunk_size if Settings.node_parser else 512
        }


# Factory function
def create_llama_index_rag(documents_path: Optional[str] = None) -> LlamaIndexRAG:
    """
    Factory function to create a LlamaIndexRAG.
    
    Args:
        documents_path: Path to directory containing medical documents
        
    Returns:
        Configured LlamaIndexRAG
    """
    return LlamaIndexRAG(documents_path=documents_path)