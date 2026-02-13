"""
HeartDiseaseRAG Engine - Simplified RAG for Cardiovascular Knowledge

This module connects the Router directly to the populated PostgreSQL/pgvector store
containing 125,000+ medical textbook documents.
"""

import logging
from rag.ingestion.vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)



class HeartDiseaseRAG:
    """
    Singleton engine that connects the Router to the Vector Database.
    Provides semantic search over medical textbooks.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HeartDiseaseRAG, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize connection to the Vector Store Manager."""
        logger.info("Initializing RAG Engine...")
        try:
            # Connect directly to the Vector Store Manager
            # This accesses the 125,000+ documents in PostgreSQL/pgvector
            self.vector_store = VectorStoreManager.get_instance()
            logger.info(f"[SUCCESS] RAG Engine Connected to PostgreSQL/pgvector.")
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to Vector Store: {e}")
            self.vector_store = None
        finally:
            self._initialized = True

    @classmethod
    def get_instance(cls):
        """Get singleton instance of RAG engine."""
        return cls()

    def is_ready(self) -> bool:
        return hasattr(self, '_initialized') and self._initialized

    def retrieve_context(self, query: str, top_k: int = 3):
        """
        Retrieves relevant text from the vector database using semantic search.
        
        Args:
            query: Medical question or symptom description
            top_k: Number of top results to retrieve (default: 3)
            
        Returns:
            Dictionary with summary, context, and sources
        """
        if not self.vector_store:
            return {
                "summary": "System Error",
                "context": "Vector store not connected.",
                "sources": []
            }

        try:
            # Perform the actual semantic search against textbooks
            results = self.vector_store.search(query, top_k=top_k)
            
            if not results:
                return {
                    "summary": "No results found in medical textbooks.",
                    "context": "The knowledge base did not return any matches.",
                    "sources": []
                }
            
            # Format the results for the chatbot
            context_str = ""
            sources = []
            
            for res in results:
                title = res.get('metadata', {}).get('title', 'Unknown Source')
                text = res.get('text', '')
                
                # Add citation and text
                context_str += f"[SOURCE]: {title}\n{text}\n{'-'*40}\n"
                sources.append(title)
            
            return {
                "summary": f"Found {len(results)} relevant textbook excerpts.",
                "context": context_str,
                "sources": sources
            }
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            return {
                "summary": "Error retrieving context",
                "context": f"An error occurred: {str(e)}",
                "sources": []
            }


def get_heart_disease_rag():
    """Factory function to get the HeartDiseaseRAG instance."""
    return HeartDiseaseRAG.get_instance()
