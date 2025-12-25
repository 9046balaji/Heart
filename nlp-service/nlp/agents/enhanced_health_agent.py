"""
Enhanced Health AI Agent with GraphRAG and Mode-Based Tool Loading

Integrates:
- Mode-based tool filtering (89% token reduction)
- GraphRAG for drug interactions
- RAG orchestrator for enhanced context
- Structured entity extraction

Phase 3: Intelligence Upgrade - Integration
"""

import logging
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class EnhancedHealthAgent:
    """
    Enhanced health AI agent with GraphRAG and intelligent tool loading.
    
    Features:
    - Automatic mode detection from user query
    - Context-aware tool filtering (reduces tokens by 89%)
    - GraphRAG-enhanced context retrieval
    - Drug interaction warning system
    - Structured entity extraction from conversations
    
    Example:
        agent = EnhancedHealthAgent()
        await agent.initialize()
        
        response = await agent.process_message(
            user_id="user_123",
            message="I'm taking Lisinopril and Aspirin. Can I take Warfarin?",
            user_medications=["Lisinopril", "Aspirin"]
        )
    """
    
    def __init__(self):
        """Initialize enhanced health agent."""
        self.mode_detector = None
        self.tool_registry = None
        self.rag_orchestrator = None
        self.entity_extractor = None
        self.llm_service = None
        
        logger.info("EnhancedHealthAgent initialized")
    
    async def initialize(self):
        """Initialize all services."""
        try:
            # Initialize mode detector
            from nlp.tools.mode_detector import get_mode_detector
            self.mode_detector = get_mode_detector()
            logger.info("✓ Mode detector initialized")
            
            # Initialize tool registry
            from nlp.tools.tool_registry import get_tool_registry
            self.tool_registry = get_tool_registry()
            logger.info("✓ Tool registry initialized")
            
            # Initialize RAG orchestrator
            from nlp.rag.rag_orchestrator import get_rag_orchestrator
            from nlp.knowledge_graph.graph_rag import GraphRAGService
            
            try:
                graph_service = GraphRAGService()
                await graph_service.initialize()
                self.rag_orchestrator = get_rag_orchestrator(
                    vector_service=None,  # Will use ChromaDB if available
                    graph_service=graph_service,
                    enable_graph=True
                )
                logger.info("✓ RAG orchestrator with GraphRAG initialized")
            except Exception as e:
                logger.warning(f"GraphRAG unavailable, using vector-only RAG: {e}")
                self.rag_orchestrator = get_rag_orchestrator(enable_graph=False)
            
            # Initialize entity extractor
            from nlp.extractors.medical_extractor import get_medical_extractor
            self.entity_extractor = get_medical_extractor()
            logger.info("✓ Medical entity extractor initialized")
            
            # Initialize LLM service
            from nlp.services.llm_service import LLMService
            self.llm_service = LLMService()
            logger.info("✓ LLM service initialized")
            
            logger.info("🚀 Enhanced Health Agent ready!")
            
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            raise
    
    async def process_message(
        self,
        user_id: str,
        message: str,
        user_medications: Optional[List[str]] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Process user message with full intelligence pipeline.
        
        Workflow:
        1. Detect conversation mode
        2. Filter tools based on mode (89% token reduction)
        3. Get enhanced context (vector + graph)
        4. Check drug interactions if medications mentioned
        5. Extract structured entities
        6. Generate response with filtered tools
        
        Args:
            user_id: User ID
            message: User message
            user_medications: User's current medications
            conversation_history: Previous conversation turns
        
        Returns:
            {
                "response": str,
                "mode": str,
                "tools_available": int,
                "tools_used": List[str],
                "drug_interactions": List[Dict] | None,
                "detected_entities": Dict | None,
                "context_used": Dict,
                "token_savings": float
            }
        """
        try:
            # Step 1: Detect mode
            detected_mode = self.mode_detector.detect(message)
            logger.info(f"Detected mode: {detected_mode}")
            
            # Step 2: Get mode-filtered tools
            mode_tools = self.tool_registry.get_tools_for_mode(detected_mode)
            tool_schemas = self.tool_registry.get_gemini_schemas_for_mode(detected_mode)
            
            all_tools_count = len(self.tool_registry.get_all_tools())
            token_savings = (1 - len(mode_tools) / all_tools_count) * 100 if all_tools_count > 0 else 0
            
            logger.info(f"Tools: {len(mode_tools)}/{all_tools_count} ({token_savings:.1f}% reduction)")
            
            # Step 3: Get enhanced context
            rag_context = await self.rag_orchestrator.get_enhanced_context(
                query=message,
                user_medications=user_medications or [],
                max_vector_results=3,
                max_graph_depth=2
            )
            
            # Step 4: Check drug interactions
            drug_interactions = rag_context.get("drug_interactions")
            if drug_interactions:
                logger.warning(f"⚠️ Found {len(drug_interactions)} drug interactions")
            
            # Step 5: Extract structured entities (if relevant)
            detected_entities = None
            if detected_mode in ["vitals", "medications", "symptoms"]:
                try:
                    if detected_mode == "vitals":
                        detected_entities = await self.entity_extractor.extract_vitals(message)
                    elif detected_mode == "medications":
                        detected_entities = await self.entity_extractor.extract_medications(message)
                    elif detected_mode == "symptoms":
                        detected_entities = await self.entity_extractor.extract_symptoms(message)
                except Exception as e:
                    logger.warning(f"Entity extraction failed: {e}")
            
            # Step 6: Build prompt with context
            system_prompt = self._build_system_prompt(
                mode=detected_mode,
                context=rag_context,
                drug_interactions=drug_interactions
            )
            
            # Step 7: Generate response
            response = await self.llm_service.generate(
                prompt=message,
                system_prompt=system_prompt,
                tools=tool_schemas,
                conversation_history=conversation_history
            )
            
            return {
                "response": response,
                "mode": detected_mode,
                "tools_available": len(mode_tools),
                "tools_used": [],  # Will be populated by LLM
                "drug_interactions": drug_interactions,
                "detected_entities": detected_entities,
                "context_used": {
                    "vector_docs": len(rag_context.get("vector_context", [])),
                    "graph_entities": len(rag_context.get("graph_context", {}).get("primary_entities", [])) if rag_context.get("graph_context") else 0,
                },
                "token_savings_percent": round(token_savings, 1),
                "timestamp": rag_context.get("timestamp")
            }
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            raise
    
    def _build_system_prompt(
        self,
        mode: str,
        context: Dict,
        drug_interactions: Optional[List[Dict]]
    ) -> str:
        """
        Build system prompt with context and warnings.
        
        Args:
            mode: Detected conversation mode
            context: RAG context
            drug_interactions: Drug interaction warnings
        
        Returns:
            System prompt string
        """
        parts = [
            "You are an AI medical assistant for cardiology health management.",
            f"\nCurrent conversation mode: {mode}",
        ]
        
        # Add context
        if context.get("combined_context"):
            parts.append("\n## Available Medical Knowledge:\n")
            parts.append(context["combined_context"])
        
        # Add drug interaction warnings
        if drug_interactions:
            parts.append("\n## ⚠️ CRITICAL: Drug Interaction Warnings\n")
            for interaction in drug_interactions:
                severity = interaction.get("severity", "unknown").upper()
                drug1 = interaction.get("drug1")
                drug2 = interaction.get("drug2")
                desc = interaction.get("description", "")
                
                parts.append(f"**{severity}**: {drug1} + {drug2}")
                parts.append(f"  - {desc}")
                
                if interaction.get("via"):
                    parts.append(f"  - Indirect interaction via {interaction['via']}")
            
            parts.append("\n**IMPORTANT**: Warn the user about these interactions!")
        
        # Add mode-specific instructions
        mode_instructions = {
            "medications": "Focus on medication guidance, interactions, and adherence.",
            "vitals": "Analyze vital signs and provide health insights.",
            "nutrition": "Provide nutritional advice and calorie calculations.",
            "symptoms": "Assess symptoms with appropriate triage recommendations.",
            "calculators": "Use health calculators to provide accurate metrics.",
        }
        
        if mode in mode_instructions:
            parts.append(f"\nMode Guidance: {mode_instructions[mode]}")
        
        return "\n".join(parts)
    
    async def close(self):
        """Cleanup resources."""
        if self.rag_orchestrator and hasattr(self.rag_orchestrator, "graph_service"):
            if self.rag_orchestrator.graph_service:
                await self.rag_orchestrator.graph_service.close()
        
        logger.info("EnhancedHealthAgent closed")


# Singleton instance
_agent_instance: Optional[EnhancedHealthAgent] = None


async def get_enhanced_health_agent() -> EnhancedHealthAgent:
    """Get or create enhanced health agent singleton."""
    global _agent_instance
    
    if _agent_instance is None:
        _agent_instance = EnhancedHealthAgent()
        await _agent_instance.initialize()
    
    return _agent_instance
