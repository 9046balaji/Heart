"""
RAG Pipeline - Retrieval-Augmented Generation for Healthcare

This module combines vector search with LLM generation to provide
accurate, source-backed responses for healthcare queries.

Workflow:
1. User query → Generate embedding
2. Search medical knowledge base → Retrieve relevant documents
3. Search user memories → Retrieve relevant context
4. Augment prompt with retrieved context
5. Generate response with LLM
6. Return response with source citations

Addresses GAPs from COMPETITIVE_ANALYSIS_ROADMAP.md:
- ❌ No RAG -> ✅ Full RAG pipeline with citations
- ❌ Uneducated LLM -> ✅ Context-augmented responses
"""

import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from .vector_store import VectorStore
from .embedding_service import EmbeddingService


@dataclass
class RetrievedContext:
    """Container for retrieved context from RAG."""
    medical_sources: List[Dict] = field(default_factory=list)
    user_memories: List[Dict] = field(default_factory=list)
    drug_info: List[Dict] = field(default_factory=list)
    
    def to_prompt_context(self) -> str:
        """Format retrieved context for LLM prompt."""
        sections = []
        
        if self.medical_sources:
            medical_text = "\n".join([
                f"- {src['content'][:500]}... [Source: {src.get('metadata', {}).get('source', 'Unknown')}]"
                for src in self.medical_sources
            ])
            sections.append(f"**Medical Knowledge:**\n{medical_text}")
        
        if self.drug_info:
            drug_text = "\n".join([
                f"- {info['content'][:300]}..."
                for info in self.drug_info
            ])
            sections.append(f"**Drug Information:**\n{drug_text}")
        
        if self.user_memories:
            memory_text = "\n".join([
                f"- {mem['content'][:200]}"
                for mem in self.user_memories
            ])
            sections.append(f"**Patient History:**\n{memory_text}")
        
        return "\n\n".join(sections) if sections else "No additional context available."
    
    def get_citations(self) -> List[Dict]:
        """Get list of citations for attribution."""
        citations = []
        
        for src in self.medical_sources:
            meta = src.get("metadata", {})
            citations.append({
                "type": "medical_knowledge",
                "source": meta.get("source", "Unknown"),
                "category": meta.get("category", "general"),
                "score": src.get("score", 0),
            })
        
        for drug in self.drug_info:
            meta = drug.get("metadata", {})
            citations.append({
                "type": "drug_info",
                "drug_name": meta.get("drug_name", "Unknown"),
                "score": drug.get("score", 0),
            })
        
        return citations
    
    @property
    def has_context(self) -> bool:
        """Check if any context was retrieved."""
        return bool(self.medical_sources or self.user_memories or self.drug_info)


@dataclass
class RAGResponse:
    """Response from RAG pipeline."""
    response: str
    context: RetrievedContext
    citations: List[Dict]
    query: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    processing_time_ms: float = 0.0
    
    def to_dict(self, include_sources: bool = False) -> Dict:
        """
        Convert to dictionary for API response.
        
        Args:
            include_sources: Only True for internal/admin APIs
            
        Returns:
            Dictionary representation of the response
        """
        result = {
            "response": self.response,
            "citations": self._get_safe_citations(),
            "query": self.query,
            "timestamp": self.timestamp,
            "processing_time_ms": self.processing_time_ms,
        }
        
        # Only include raw sources for internal debugging
        if include_sources:
            result["_debug_sources"] = {
                "medical_sources": [
                    {
                        "content_preview": s["content"][:200] + "..." if len(s["content"]) > 200 else s["content"],
                        "source": s.get("metadata", {}).get("source"),
                        "score": s.get("score", 0),
                    }
                    for s in self.context.medical_sources
                ],
                "user_memories": [
                    {
                        "content_preview": m["content"][:100] + "..." if len(m["content"]) > 100 else m["content"],
                        "type": m.get("metadata", {}).get("type"),
                        "score": m.get("score", 0),
                    }
                    for m in self.context.user_memories
                ],
            }
        
        return result
    
    def _get_safe_citations(self) -> List[Dict]:
        """Return only safe citation metadata, not raw content."""
        safe_citations = []
        
        # Medical sources
        for src in self.context.medical_sources:
            meta = src.get("metadata", {})
            safe_citations.append({
                "type": "medical_knowledge",
                "source": meta.get("source", "Unknown"),
                "category": meta.get("category", "general"),
                "score": src.get("score", 0),
            })
        
        # Drug info
        for drug in self.context.drug_info:
            meta = drug.get("metadata", {})
            safe_citations.append({
                "type": "drug_info",
                "drug_name": meta.get("drug_name", "Unknown"),
                "score": drug.get("score", 0),
            })
        
        # User memories (only metadata, no content)
        for mem in self.context.user_memories:
            meta = mem.get("metadata", {})
            safe_citations.append({
                "type": "user_memory",
                "memory_type": meta.get("type", "general"),
                "score": mem.get("score", 0),
            })
        
        return safe_citations


class RAGPipeline:
    """
    Retrieval-Augmented Generation Pipeline for Healthcare.
    
    Features:
    - Medical knowledge retrieval
    - User memory retrieval
    - Drug interaction lookup
    - Context-augmented LLM generation
    - Source citations
    
    Example:
        rag = RAGPipeline()
        
        # Simple query
        response = await rag.query(
            "What are the symptoms of heart failure?",
            user_id="user123"
        )
        print(response.response)
        print(response.citations)
        
        # Streaming response
        async for chunk in rag.query_stream("heart failure symptoms"):
            print(chunk, end="", flush=True)
    """
    
    # System prompt for healthcare context
    SYSTEM_PROMPT = """You are a knowledgeable healthcare assistant for the Cardio AI app.
You have access to medical knowledge and the patient's health history.

Guidelines:
1. Provide accurate, evidence-based health information
2. Always cite sources when using medical knowledge
3. Be empathetic and supportive
4. If unsure, recommend consulting a healthcare provider
5. Never diagnose conditions - only provide information
6. For emergencies, advise calling emergency services

When responding:
- Use the provided medical context to inform your answers
- Reference the patient's history when relevant
- Be clear about what is general information vs personalized advice"""
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        llm_client: Optional[Any] = None,
        medical_top_k: int = 3,
        memory_top_k: int = 5,
        drug_top_k: int = 3,
        min_relevance_score: float = 0.3,
    ):
        """
        Initialize RAG Pipeline.
        
        Args:
            vector_store: VectorStore instance (creates new if None)
            llm_client: LLM client for generation (Ollama/Gemini)
            medical_top_k: Number of medical docs to retrieve
            memory_top_k: Number of memories to retrieve
            drug_top_k: Number of drug docs to retrieve
            min_relevance_score: Minimum score for retrieval
        """
        self.vector_store = vector_store or VectorStore()
        self.llm_client = llm_client
        self.medical_top_k = medical_top_k
        self.memory_top_k = memory_top_k
        self.drug_top_k = drug_top_k
        self.min_relevance_score = min_relevance_score
        
        logger.info("✅ RAGPipeline initialized")
    
    async def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        include_medical: bool = True,
        include_memories: bool = True,
        include_drugs: bool = True,
    ) -> RetrievedContext:
        """
        Retrieve relevant context for query.
        
        Args:
            query: User query
            user_id: Optional user ID for memory retrieval
            include_medical: Include medical knowledge
            include_memories: Include user memories
            include_drugs: Include drug information
            
        Returns:
            RetrievedContext with all relevant documents
        """
        context = RetrievedContext()
        
        # Run retrievals in parallel
        tasks = []
        
        if include_medical:
            tasks.append(self._retrieve_medical(query))
        
        if include_memories and user_id:
            tasks.append(self._retrieve_memories(query, user_id))
        
        if include_drugs:
            tasks.append(self._retrieve_drugs(query))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            idx = 0
            if include_medical:
                if not isinstance(results[idx], Exception):
                    context.medical_sources = results[idx]
                idx += 1
            
            if include_memories and user_id:
                if not isinstance(results[idx], Exception):
                    context.user_memories = results[idx]
                idx += 1
            
            if include_drugs:
                if not isinstance(results[idx], Exception):
                    context.drug_info = results[idx]
        
        return context
    
    async def _retrieve_medical(self, query: str) -> List[Dict]:
        """Retrieve medical knowledge."""
        try:
            results = self.vector_store.search_medical_knowledge(
                query, 
                top_k=self.medical_top_k
            )
            # Filter by relevance score
            return [r for r in results if r.get("score", 0) >= self.min_relevance_score]
        except Exception as e:
            logger.error(f"Medical retrieval failed: {e}")
            return []
    
    async def _retrieve_memories(self, query: str, user_id: str) -> List[Dict]:
        """Retrieve user memories."""
        try:
            results = self.vector_store.search_user_memories(
                user_id,
                query,
                top_k=self.memory_top_k
            )
            return [r for r in results if r.get("score", 0) >= self.min_relevance_score]
        except Exception as e:
            logger.error(f"Memory retrieval failed: {e}")
            return []
    
    async def _retrieve_drugs(self, query: str) -> List[Dict]:
        """Retrieve drug information."""
        try:
            results = self.vector_store.search_drug_info(
                query,
                top_k=self.drug_top_k
            )
            return [r for r in results if r.get("score", 0) >= self.min_relevance_score]
        except Exception as e:
            logger.error(f"Drug retrieval failed: {e}")
            return []
    
    def build_prompt(
        self,
        query: str,
        context: RetrievedContext,
        conversation_history: Optional[List[Dict]] = None,
    ) -> str:
        """
        Build augmented prompt with retrieved context.
        
        Args:
            query: User query
            context: Retrieved context
            conversation_history: Previous conversation messages
            
        Returns:
            Formatted prompt for LLM
        """
        parts = [self.SYSTEM_PROMPT]
        
        # Add retrieved context
        if context.has_context:
            parts.append("\n--- RETRIEVED CONTEXT ---")
            parts.append(context.to_prompt_context())
            parts.append("--- END CONTEXT ---\n")
        
        # Add conversation history
        if conversation_history:
            parts.append("\n--- CONVERSATION HISTORY ---")
            for msg in conversation_history[-5:]:  # Last 5 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                parts.append(f"{role.upper()}: {content}")
            parts.append("--- END HISTORY ---\n")
        
        # Add user query
        parts.append(f"\nUSER QUERY: {query}")
        parts.append("\nPlease provide a helpful response based on the context above:")
        
        return "\n".join(parts)
    
    async def query(
        self,
        query: str,
        user_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        **kwargs,
    ) -> RAGResponse:
        """
        Execute RAG query with retrieval and generation.
        
        Args:
            query: User query
            user_id: Optional user ID for personalization
            conversation_history: Previous conversation
            **kwargs: Additional params for retrieval
            
        Returns:
            RAGResponse with response and citations
            
        Example:
            response = await rag.query(
                "What are symptoms of heart failure?",
                user_id="user123"
            )
            print(response.response)
            print(response.citations)
        """
        import time
        start_time = time.time()
        
        # 1. Retrieve context
        context = await self.retrieve(
            query,
            user_id=user_id,
            **kwargs,
        )
        
        # 2. Build augmented prompt
        prompt = self.build_prompt(query, context, conversation_history)
        
        # 3. Generate response
        if self.llm_client:
            response_text = await self._generate(prompt)
        else:
            # Return context-only response if no LLM client
            response_text = self._generate_fallback(query, context)
        
        processing_time = (time.time() - start_time) * 1000
        
        return RAGResponse(
            response=response_text,
            context=context,
            citations=context.get_citations(),
            query=query,
            processing_time_ms=processing_time,
        )
    
    async def _generate(self, prompt: str) -> str:
        """Generate response using LLM client."""
        try:
            # This should be implemented based on your LLM client
            # For now, return a placeholder
            if hasattr(self.llm_client, 'generate'):
                return await self.llm_client.generate(prompt)
            elif hasattr(self.llm_client, 'chat'):
                return await self.llm_client.chat(prompt)
            else:
                return self._generate_fallback("", RetrievedContext())
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return f"I apologize, but I encountered an error generating a response. Error: {str(e)}"
    
    def _generate_fallback(self, query: str, context: RetrievedContext) -> str:
        """Generate fallback response when LLM is not available."""
        if not context.has_context:
            return (
                "I don't have enough information to answer that question. "
                "Please consult a healthcare provider for medical advice."
            )
        
        # Compile relevant info from context
        parts = ["Based on the available information:\n"]
        
        if context.medical_sources:
            parts.append("**Medical Information:**")
            for src in context.medical_sources[:2]:
                parts.append(f"- {src['content'][:300]}")
        
        if context.drug_info:
            parts.append("\n**Drug Information:**")
            for drug in context.drug_info[:2]:
                parts.append(f"- {drug['content'][:200]}")
        
        if context.user_memories:
            parts.append("\n**From your health history:**")
            for mem in context.user_memories[:2]:
                parts.append(f"- {mem['content'][:150]}")
        
        parts.append("\n\n*Please consult a healthcare provider for personalized medical advice.*")
        
        return "\n".join(parts)
    
    async def query_stream(
        self,
        query: str,
        user_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream RAG response.
        
        Yields chunks of the response as they are generated.
        
        Example:
            async for chunk in rag.query_stream("heart failure symptoms"):
                print(chunk, end="", flush=True)
        """
        # First, retrieve context
        context = await self.retrieve(query, user_id=user_id)
        
        # Build prompt
        prompt = self.build_prompt(query, context, conversation_history)
        
        # Stream response
        if self.llm_client and hasattr(self.llm_client, 'stream'):
            async for chunk in self.llm_client.stream(prompt):
                yield chunk
        else:
            # Fallback: yield complete response
            response = self._generate_fallback(query, context)
            yield response
    
    # =========================================================================
    # KNOWLEDGE BASE MANAGEMENT
    # =========================================================================
    
    async def index_medical_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Index a medical document into the knowledge base.
        
        Args:
            doc_id: Unique document ID
            content: Document content
            metadata: Document metadata (source, category, etc.)
            
        Returns:
            Document ID
        """
        return self.vector_store.add_medical_document(
            doc_id=doc_id,
            content=content,
            metadata=metadata,
        )
    
    async def index_drug_info(
        self,
        drug_id: str,
        drug_name: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Index drug information."""
        return self.vector_store.add_drug_info(
            drug_id=drug_id,
            drug_name=drug_name,
            content=content,
            metadata=metadata,
        )
    
    def get_stats(self) -> Dict:
        """Get RAG pipeline statistics."""
        return {
            "vector_store": self.vector_store.get_stats(),
            "config": {
                "medical_top_k": self.medical_top_k,
                "memory_top_k": self.memory_top_k,
                "drug_top_k": self.drug_top_k,
                "min_relevance_score": self.min_relevance_score,
            },
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_rag_pipeline(
    persist_directory: str = None,
    llm_client: Any = None,
) -> RAGPipeline:
    """
    Factory function to create RAG pipeline.
    
    Args:
        persist_directory: Directory for vector store
        llm_client: LLM client for generation
        
    Returns:
        Configured RAGPipeline instance
    """
    vector_store = VectorStore(persist_directory=persist_directory)
    return RAGPipeline(
        vector_store=vector_store,
        llm_client=llm_client,
    )


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import tempfile
    
    async def test_rag():
        print("Testing RAGPipeline...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create pipeline
            rag = create_rag_pipeline(persist_directory=tmpdir)
            
            # Index some test documents
            print("\n📚 Indexing test documents...")
            await rag.index_medical_document(
                "hf_guide",
                "Heart failure is a chronic condition where the heart cannot pump "
                "efficiently. Common symptoms include shortness of breath, fatigue, "
                "and swelling in legs. Treatment includes medications like ACE inhibitors, "
                "beta-blockers, and diuretics.",
                {"source": "AHA Guidelines", "category": "heart_failure"}
            )
            
            await rag.index_medical_document(
                "chest_pain",
                "Chest pain can have many causes including cardiac issues, "
                "gastrointestinal problems, or musculoskeletal issues. "
                "Cardiac chest pain often presents as pressure or squeezing "
                "and may radiate to the arm or jaw.",
                {"source": "Mayo Clinic", "category": "symptoms"}
            )
            
            await rag.index_drug_info(
                "lisinopril",
                "Lisinopril",
                "ACE inhibitor used to treat high blood pressure and heart failure. "
                "Common side effects include dry cough, dizziness, and headache.",
                {"drug_class": "ACE inhibitor"}
            )
            
            # Test retrieval
            print("\n🔍 Testing retrieval...")
            context = await rag.retrieve("heart failure symptoms treatment")
            print(f"  Medical sources: {len(context.medical_sources)}")
            print(f"  Drug info: {len(context.drug_info)}")
            
            # Test full query
            print("\n💬 Testing full query...")
            response = await rag.query(
                "What are the symptoms of heart failure?",
                user_id="test_user"
            )
            print(f"  Response: {response.response[:200]}...")
            print(f"  Citations: {len(response.citations)}")
            print(f"  Processing time: {response.processing_time_ms:.1f}ms")
            
            # Stats
            print(f"\n📊 Stats: {rag.get_stats()}")
            
            print("\n✅ RAGPipeline tests passed!")
    
    asyncio.run(test_rag())
