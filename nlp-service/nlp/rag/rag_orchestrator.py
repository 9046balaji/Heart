"""
RAG Orchestrator - Combines Vector Search + Knowledge Graph

Integrates traditional vector-based RAG with GraphRAG for enhanced context.

Phase 3: Intelligence Upgrade - GraphRAG Integration
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """
    Orchestrates hybrid RAG: Vector search + Knowledge graph traversal.
    
    Workflow:
    1. Vector search for relevant documents
    2. Graph search for entity relationships
    3. Merge and rank results
    4. Return enriched context
    
    Example:
        orchestrator = RAGOrchestrator(chroma_service, graph_rag_service)
        
        context = await orchestrator.get_enhanced_context(
            query="What drugs interact with Lisinopril?",
            user_medications=["Lisinopril", "Aspirin"]
        )
    """
    
    def __init__(
        self,
        vector_service=None,
        graph_service=None,
        enable_graph: bool = True
    ):
        """
        Initialize RAG orchestrator.
        
        Args:
            vector_service: ChromaDB or similar vector store
            graph_service: GraphRAGService instance
            enable_graph: Whether to use graph enhancement
        """
        self.vector_service = vector_service
        self.graph_service = graph_service
        self.enable_graph = enable_graph
        
        logger.info(f"RAG Orchestrator initialized (graph_enabled={enable_graph})")
    
    async def get_enhanced_context(
        self,
        query: str,
        user_medications: Optional[List[str]] = None,
        max_vector_results: int = 5,
        max_graph_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get enhanced context combining vector + graph search.
        
        Args:
            query: User query
            user_medications: User's current medications for interaction check
            max_vector_results: Max results from vector search
            max_graph_depth: Max graph traversal depth
        
        Returns:
            {
                "vector_context": List[str],
                "graph_context": GraphContext or None,
                "drug_interactions": List[Dict] or None,
                "combined_context": str,
                "sources": List[str]
            }
        """
        results = {
            "vector_context": [],
            "graph_context": None,
            "drug_interactions": None,
            "combined_context": "",
            "sources": []
        }
        
        # 1. Vector search
        if self.vector_service:
            try:
                vector_results = await self._vector_search(query, max_vector_results)
                results["vector_context"] = vector_results
                results["sources"].extend([f"Document {i+1}" for i in range(len(vector_results))])
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
        
        # 2. Graph search (if enabled)
        if self.enable_graph and self.graph_service:
            try:
                graph_context = await self.graph_service.get_enriched_context(
                    query=query,
                    max_depth=max_graph_depth
                )
                results["graph_context"] = graph_context
                results["sources"].append("Knowledge Graph")
            except Exception as e:
                logger.error(f"Graph search failed: {e}")
        
        # 3. Check drug interactions (if user has medications)
        if user_medications and self.enable_graph and self.graph_service:
            try:
                interactions = await self.graph_service.get_drug_interactions(
                    drug_names=user_medications,
                    max_hops=2
                )
                results["drug_interactions"] = interactions
                
                if interactions:
                    logger.warning(f"Found {len(interactions)} drug interactions")
            except Exception as e:
                logger.error(f"Drug interaction check failed: {e}")
        
        # 4. Combine contexts
        results["combined_context"] = self._build_combined_context(results)
        
        return results
    
    async def _vector_search(self, query: str, max_results: int) -> List[str]:
        """
        Perform vector search.
        
        Args:
            query: Search query
            max_results: Max results to return
        
        Returns:
            List of relevant document snippets
        """
        if not self.vector_service:
            return []
        
        try:
            # Assuming ChromaDB-style interface
            if hasattr(self.vector_service, 'query'):
                results = self.vector_service.query(
                    query_texts=[query],
                    n_results=max_results
                )
                
                # Extract documents
                if results and 'documents' in results:
                    docs = results['documents'][0] if results['documents'] else []
                    return docs
            
            return []
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []
    
    def _build_combined_context(self, results: Dict) -> str:
        """
        Build combined context string for LLM.
        
        Args:
            results: Results dict with vector and graph contexts
        
        Returns:
            Formatted context string
        """
        parts = []
        
        # Add vector context
        if results["vector_context"]:
            parts.append("## Relevant Information from Medical Database:\n")
            for i, doc in enumerate(results["vector_context"], 1):
                parts.append(f"{i}. {doc}\n")
        
        # Add graph context
        if results["graph_context"]:
            parts.append("\n## Knowledge Graph Context:\n")
            parts.append(results["graph_context"].to_context_string())
        
        # Add drug interaction warnings
        if results["drug_interactions"]:
            parts.append("\n## ⚠️ Drug Interaction Warnings:\n")
            for interaction in results["drug_interactions"]:
                severity = interaction.get('severity', 'unknown').upper()
                drug1 = interaction.get('drug1')
                drug2 = interaction.get('drug2')
                desc = interaction.get('description', '')
                interaction_type = interaction.get('type', 'direct')
                
                warning = f"**{severity}**: {drug1} + {drug2} ({interaction_type})"
                if interaction.get('via'):
                    warning += f" via {interaction['via']}"
                warning += f"\n  - {desc}"
                
                parts.append(warning + "\n")
        
        return "\n".join(parts)


# Singleton instance
_orchestrator_instance: Optional[RAGOrchestrator] = None


def get_rag_orchestrator(
    vector_service=None,
    graph_service=None,
    enable_graph: bool = True
) -> RAGOrchestrator:
    """Get or create RAG orchestrator singleton."""
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        _orchestrator_instance = RAGOrchestrator(
            vector_service=vector_service,
            graph_service=graph_service,
            enable_graph=enable_graph
        )
    
    return _orchestrator_instance
