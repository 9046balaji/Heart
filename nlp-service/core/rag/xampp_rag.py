"""
RAG (Retrieval-Augmented Generation) service using XAMPP MySQL (MariaDB) with vector search.
"""

import logging
from typing import List, Dict, Any, Optional
import asyncio

from ..database.xampp_db import get_database
from ..llm.llm_gateway import get_llm_gateway

logger = logging.getLogger(__name__)


class XAMPPRAGService:
    """RAG service using XAMPP MySQL with vector search capabilities."""

    def __init__(self):
        self.db = None
        self.llm_gateway = None
        self.initialized = False

    async def initialize(self):
        """Initialize the RAG service."""
        try:
            # Get database instance
            self.db = await get_database()

            # Get LLM gateway
            self.llm_gateway = get_llm_gateway()

            self.initialized = True
            logger.info("XAMPP RAG service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize XAMPP RAG service: {e}")
            return False

    async def add_medical_document(
        self, content: str, content_type: str, metadata: Dict = None
    ) -> bool:
        """Add a medical document to the knowledge base.

        In a production system, you would:
        1. Generate embeddings using a model like MedGemma or sentence-transformers
        2. Store the content and embeddings in the database

        For this example, we'll use a dummy embedding.
        """
        if not self.initialized:
            logger.warning("RAG service not initialized")
            return False

        try:
            # In a real implementation, you would generate actual embeddings here
            # For example, using sentence-transformers:
            # from sentence_transformers import SentenceTransformer
            # model = SentenceTransformer('all-MiniLM-L6-v2')
            # embedding = model.encode(content).tolist()

            # For this example, we'll create a dummy embedding
            # In practice, use a proper embedding model
            dummy_embedding = [0.1] * 1536  # Dummy 1536-dimensional vector

            # Store in database
            success = await self.db.store_medical_knowledge(
                content=content,
                content_type=content_type,
                embedding=dummy_embedding,
                metadata=metadata,
            )

            if success:
                logger.info(
                    f"Added medical document of type '{content_type}' to knowledge base"
                )
            else:
                logger.error("Failed to store medical document")

            return success
        except Exception as e:
            logger.error(f"Error adding medical document: {e}")
            return False

    async def retrieve_context(
        self, query: str, content_types: List[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant context from the knowledge base using vector search."""
        if not self.initialized:
            logger.warning("RAG service not initialized")
            return []

        try:
            # In a real implementation, you would generate an embedding for the query
            # For this example, we'll use a dummy embedding
            dummy_query_embedding = [0.1] * 1536  # Dummy 1536-dimensional vector

            # Search for similar documents
            if content_types:
                # Search for each content type separately and combine results
                all_results = []
                for content_type in content_types:
                    results = await self.db.search_similar_knowledge(
                        query_embedding=dummy_query_embedding,
                        content_type=content_type,
                        limit=limit,
                    )
                    all_results.extend(results)

                # Sort by similarity and limit results
                all_results.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
                return all_results[:limit]
            else:
                # Search across all content types
                return await self.db.search_similar_knowledge(
                    query_embedding=dummy_query_embedding, limit=limit
                )
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []

    async def generate_augmented_response(
        self, query: str, user_id: str = None, content_types: List[str] = None
    ) -> Dict[str, Any]:
        """Generate an augmented response using retrieved context."""
        if not self.initialized:
            return {
                "response": "RAG service not initialized",
                "context_used": [],
                "success": False,
            }

        try:
            # Retrieve relevant context
            context_items = await self.retrieve_context(query, content_types)

            if not context_items:
                # If no context found, fall back to direct LLM generation
                logger.info("No relevant context found, generating direct response")
                response = await self.llm_gateway.generate(
                    prompt=query, content_type="medical"
                )
                return {"response": response, "context_used": [], "success": True}

            # Build context string for the LLM
            context_text = "\n\n".join(
                [
                    f"[{item['content_type']}] {item['content']}"
                    for item in context_items
                ]
            )

            # Create augmented prompt
            augmented_prompt = f"""
            Context information is below.
            ---------------------
            {context_text}
            ---------------------
            Given the context information and not prior knowledge, answer the query.
            Query: {query}
            Answer:
            """

            # Generate response using LLM
            response = await self.llm_gateway.generate(
                prompt=augmented_prompt, content_type="medical"
            )

            return {
                "response": response,
                "context_used": context_items,
                "success": True,
            }
        except Exception as e:
            logger.error(f"Error generating augmented response: {e}")
            # Fallback to direct LLM generation
            try:
                response = await self.llm_gateway.generate(
                    prompt=query, content_type="medical"
                )
                return {
                    "response": response,
                    "context_used": [],
                    "success": True,
                    "error": str(e),
                }
            except Exception as e2:
                logger.error(f"Fallback generation also failed: {e2}")
                return {
                    "response": "Sorry, I'm having trouble generating a response right now.",
                    "context_used": [],
                    "success": False,
                    "error": str(e2),
                }

    async def get_available_content_types(self) -> List[str]:
        """Get list of available content types in the knowledge base."""
        if not self.initialized or not self.db:
            return []

        try:
            # This would require a specific query to get distinct content types
            # For now, we'll return some common medical content types
            return [
                "medical_guideline",
                "drug_information",
                "symptom_reference",
                "treatment_protocol",
                "prevention_guide",
                "emergency_procedure",
            ]
        except Exception as e:
            logger.error(f"Error getting content types: {e}")
            return []


# Global RAG service instance
rag_service: Optional[XAMPPRAGService] = None


async def get_rag_service() -> XAMPPRAGService:
    """Get singleton RAG service instance."""
    global rag_service
    if rag_service is None:
        rag_service = XAMPPRAGService()
        await rag_service.initialize()
    return rag_service


# Example usage and initialization
async def initialize_xampp_rag_demo():
    """Demo function to show how to initialize and use the RAG service."""
    # Initialize the RAG service
    rag = await get_rag_service()

    # Add some sample medical documents
    await rag.add_medical_document(
        content="For chest pain, immediately assess severity and associated symptoms. "
        "Severe, crushing chest pain with shortness of breath requires emergency care.",
        content_type="emergency_procedure",
        metadata={"category": "cardiac", "severity": "high"},
    )

    await rag.add_medical_document(
        content="Regular exercise reduces cardiovascular risk by 20-30%. "
        "Aim for 150 minutes of moderate-intensity aerobic activity per week.",
        content_type="prevention_guide",
        metadata={"category": "cardiovascular", "target": "general"},
    )

    await rag.add_medical_document(
        content="Aspirin 81mg daily is commonly prescribed for cardiovascular disease prevention "
        "in high-risk patients. Monitor for bleeding side effects.",
        content_type="drug_information",
        metadata={"drug": "aspirin", "dosage": "81mg", "frequency": "daily"},
    )

    logger.info("Sample medical documents added to knowledge base")


if __name__ == "__main__":
    # Run demo if script is executed directly
    asyncio.run(initialize_xampp_rag_demo())
