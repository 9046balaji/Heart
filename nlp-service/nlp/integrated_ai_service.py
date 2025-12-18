"""
Integrated Healthcare AI Service.

This module ties together all memory management components from chat.md:
- Context retrieval
- Prompt building  
- AI call execution
- Response storage

Key principle: "AI models do not store or recall history. 
Applications store history, retrieve what matters, and pass it to the AI as context."

Author: AI Memory System Implementation
Version: 1.0.0
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
import logging
import asyncio

from context_retrieval import (
    ContextRetriever, 
    ContextType, 
    RetrievedContext,
    context_retriever as default_context_retriever
)
from prompt_builder import (
    HealthcarePromptBuilder, 
    BuiltPrompt, 
    CommunicationStyle,
    prompt_builder as default_prompt_builder
)
from user_preferences import (
    UserPreferencesManager,
    PreferenceKeys,
    get_preferences_manager
)
from chat_history import chat_history_manager

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """
    Complete AI response with metadata and audit info.
    
    Attributes:
        response: The AI's text response
        session_id: Conversation session ID
        context_used: List of context types that were included
        metadata: Processing metadata
        audit: HIPAA-compliant audit trail
    """
    response: str
    session_id: str
    context_used: List[Dict[str, str]]
    metadata: Dict[str, Any]
    audit: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None


@dataclass
class ProcessingMetrics:
    """Metrics for AI processing performance."""
    context_retrieval_ms: float = 0.0
    prompt_building_ms: float = 0.0
    ai_call_ms: float = 0.0
    total_ms: float = 0.0
    tokens_estimated: int = 0
    context_items_count: int = 0


class IntegratedHealthAIService:
    """
    Complete AI service integrating all memory concepts from chat.md.
    
    Key Implementation:
    1. Context is explicitly stored (chat_history)
    2. Context is selectively retrieved (context_retriever)
    3. Context is formatted for AI (prompt_builder)
    4. AI never "remembers" - we remind it every time
    
    This class implements the full flow:
    User Query → Store → Retrieve Context → Build Prompt → AI Call → Store Response → Return
    
    Usage:
        service = IntegratedHealthAIService(gemini_client)
        response = await service.process_query(
            user_id="user123",
            session_id="sess456",
            query="What does my blood pressure reading mean?"
        )
    """
    
    def __init__(
        self,
        gemini_client=None,
        ollama_client=None,
        patient_data_service=None,
        vitals_service=None,
        database_url: Optional[str] = None,
        context_retriever: Optional[ContextRetriever] = None,
        prompt_builder: Optional[HealthcarePromptBuilder] = None,
        preferences_manager: Optional[UserPreferencesManager] = None,
        default_ai_provider: str = "gemini"
    ):
        """
        Initialize integrated AI service.
        
        Args:
            gemini_client: Google Gemini API client
            ollama_client: Ollama local LLM client
            patient_data_service: Service for patient medical data
            vitals_service: Service for vital signs data
            database_url: Database URL for preferences (optional)
            context_retriever: Custom ContextRetriever (optional)
            prompt_builder: Custom HealthcarePromptBuilder (optional)
            preferences_manager: Custom UserPreferencesManager (optional)
            default_ai_provider: Default AI provider ("gemini" or "ollama")
        """
        # AI clients
        self.gemini = gemini_client
        self.ollama = ollama_client
        self.default_provider = default_ai_provider
        
        # External services
        self.patient_data = patient_data_service
        self.vitals = vitals_service
        
        # Core memory components
        self.chat_history = chat_history_manager
        self.preferences = preferences_manager or get_preferences_manager()
        
        # Initialize context retriever with services
        if context_retriever:
            self.context_retriever = context_retriever
        else:
            self.context_retriever = ContextRetriever(
                chat_history_manager=self.chat_history,
                patient_data_service=patient_data_service,
                vitals_service=vitals_service,
                preferences_manager=self.preferences
            )
        
        # Initialize prompt builder
        self.prompt_builder = prompt_builder or default_prompt_builder
        
        # Processing stats
        self._total_queries = 0
        self._successful_queries = 0
        self._failed_queries = 0
        self._total_processing_time = 0.0
        
        logger.info("IntegratedHealthAIService initialized")
    
    async def process_query(
        self,
        user_id: str,
        session_id: str,
        query: str,
        patient_name: Optional[str] = None,
        patient_age: Optional[int] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        ai_provider: Optional[str] = None,
        is_emergency: bool = False
    ) -> AIResponse:
        """
        Process user query with full context management.
        
        This is the main entry point implementing chat.md architecture:
        
        1. Store the user's message
        2. Retrieve relevant context
        3. Build structured prompt
        4. Call AI with context
        5. Store AI response
        6. Return response
        
        Args:
            user_id: Unique user identifier
            session_id: Conversation session ID
            query: User's question
            patient_name: Patient name for personalization
            patient_age: Patient age for context
            additional_context: Any extra context to include
            ai_provider: AI provider to use ("gemini" or "ollama")
            is_emergency: Whether this is an emergency query
        
        Returns:
            AIResponse with response, metadata, and audit info
        """
        start_time = datetime.utcnow()
        self._total_queries += 1
        metrics = ProcessingMetrics()
        
        try:
            # Step 1: Store user message
            await self._store_user_message(
                session_id=session_id,
                user_id=user_id,
                query=query,
                start_time=start_time
            )
            
            # Step 2: Retrieve relevant context
            retrieval_start = datetime.utcnow()
            retrieved_contexts = await self._retrieve_context(
                user_id=user_id,
                session_id=session_id,
                query=query,
                is_emergency=is_emergency
            )
            metrics.context_retrieval_ms = (
                datetime.utcnow() - retrieval_start
            ).total_seconds() * 1000
            metrics.context_items_count = len(retrieved_contexts)
            
            # Step 3: Get user communication style preference
            communication_style = await self._get_communication_style(user_id)
            
            # Step 4: Build structured prompt
            build_start = datetime.utcnow()
            if is_emergency:
                built_prompt = self.prompt_builder.build_emergency_prompt(
                    user_query=query,
                    retrieved_contexts=retrieved_contexts,
                    user_name=patient_name
                )
            else:
                built_prompt = self.prompt_builder.build_prompt(
                    user_query=query,
                    retrieved_contexts=retrieved_contexts,
                    user_name=patient_name,
                    patient_age=patient_age,
                    communication_style=communication_style
                )
            metrics.prompt_building_ms = (
                datetime.utcnow() - build_start
            ).total_seconds() * 1000
            metrics.tokens_estimated = built_prompt.total_tokens_estimate
            
            # Step 5: Call AI with context
            ai_start = datetime.utcnow()
            provider = ai_provider or self.default_provider
            ai_response = await self._call_ai(
                system_message=built_prompt.system_message,
                user_message=built_prompt.user_message,
                provider=provider
            )
            metrics.ai_call_ms = (
                datetime.utcnow() - ai_start
            ).total_seconds() * 1000
            
            # Step 6: Store AI response
            await self._store_ai_response(
                session_id=session_id,
                user_id=user_id,
                response=ai_response,
                contexts_used=len(retrieved_contexts),
                tokens_estimated=built_prompt.total_tokens_estimate
            )
            
            # Calculate total time
            metrics.total_ms = (
                datetime.utcnow() - start_time
            ).total_seconds() * 1000
            self._total_processing_time += metrics.total_ms
            self._successful_queries += 1
            
            # Build response
            return AIResponse(
                response=ai_response,
                session_id=session_id,
                context_used=[
                    {
                        "type": ctx.context_type.value,
                        "source": ctx.source,
                        "relevance": f"{ctx.relevance_score:.2f}"
                    }
                    for ctx in retrieved_contexts
                ],
                metadata={
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "processing_time_ms": metrics.total_ms,
                    "context_retrieval_ms": metrics.context_retrieval_ms,
                    "prompt_building_ms": metrics.prompt_building_ms,
                    "ai_call_ms": metrics.ai_call_ms,
                    "tokens_estimated": metrics.tokens_estimated,
                    "context_items_count": metrics.context_items_count,
                    "ai_provider": provider,
                    "is_emergency": is_emergency
                },
                audit=self._build_audit_trail(
                    user_id=user_id,
                    session_id=session_id,
                    retrieved_contexts=retrieved_contexts,
                    is_emergency=is_emergency
                ),
                success=True
            )
            
        except Exception as e:
            self._failed_queries += 1
            logger.error(f"Error processing query: {e}", exc_info=True)
            
            # Return error response
            return AIResponse(
                response="I apologize, but I'm having trouble processing your request. Please try again.",
                session_id=session_id,
                context_used=[],
                metadata={
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                },
                audit={
                    "action": "ai_query_failed",
                    "user_id": user_id,
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                },
                success=False,
                error=str(e)
            )
    
    # ========================================================================
    # Internal Processing Methods
    # ========================================================================
    
    async def _store_user_message(
        self,
        session_id: str,
        user_id: str,
        query: str,
        start_time: datetime
    ) -> None:
        """Store user message in chat history."""
        try:
            self.chat_history.add_message(
                session_id=session_id,
                role="user",
                content=query,
                user_id=user_id,
                metadata={"timestamp": start_time.isoformat()}
            )
            logger.debug(f"Stored user message for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to store user message: {e}")
            # Continue processing even if storage fails
    
    async def _retrieve_context(
        self,
        user_id: str,
        session_id: str,
        query: str,
        is_emergency: bool
    ) -> List[RetrievedContext]:
        """Retrieve relevant context for the query."""
        try:
            # For emergencies, prioritize certain context types
            context_types = None
            if is_emergency:
                context_types = [
                    ContextType.EMERGENCY_INFO,
                    ContextType.MEDICAL_HISTORY,
                    ContextType.MEDICATIONS,
                    ContextType.RECENT_VITALS
                ]
            
            contexts = await self.context_retriever.retrieve_for_query(
                user_id=user_id,
                session_id=session_id,
                query=query,
                context_types=context_types
            )
            logger.info(f"Retrieved {len(contexts)} context items")
            return contexts
        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            return []
    
    async def _get_communication_style(
        self,
        user_id: str
    ) -> Optional[CommunicationStyle]:
        """Get user's preferred communication style."""
        try:
            style_str = self.preferences.get_preference(
                user_id=user_id,
                key=PreferenceKeys.COMMUNICATION_STYLE,
                default=None
            )
            if style_str:
                return CommunicationStyle(style_str)
        except Exception:
            pass
        return None
    
    async def _call_ai(
        self,
        system_message: str,
        user_message: str,
        provider: str
    ) -> str:
        """Call AI provider with the built prompt."""
        if provider == "gemini" and self.gemini:
            return await self._call_gemini(system_message, user_message)
        elif provider == "ollama" and self.ollama:
            return await self._call_ollama(system_message, user_message)
        else:
            # Fallback response if no AI available
            logger.warning(f"No AI provider available for {provider}")
            return self._generate_fallback_response(user_message)
    
    async def _call_gemini(
        self,
        system_message: str,
        user_message: str
    ) -> str:
        """Call Google Gemini API."""
        try:
            # Build messages for Gemini
            messages = [
                {"role": "user", "parts": [{"text": system_message + "\n\nUser: " + user_message}]}
            ]
            
            # Call Gemini API
            response = await asyncio.to_thread(
                self.gemini.generate_content,
                messages,
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise
    
    async def _call_ollama(
        self,
        system_message: str,
        user_message: str
    ) -> str:
        """Call Ollama local LLM."""
        try:
            # Build messages for Ollama
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
            
            # Call Ollama API
            response = await self.ollama.chat(
                model="llama2",  # Or configured model
                messages=messages
            )
            
            return response['message']['content']
            
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            raise
    
    def _generate_fallback_response(self, user_message: str) -> str:
        """Generate a fallback response when AI is unavailable."""
        return (
            "I apologize, but I'm currently unable to process your request. "
            "Our AI service is temporarily unavailable. "
            "Please try again in a few moments, or contact support if the issue persists. "
            "For medical emergencies, please call 911 or your local emergency services immediately."
        )
    
    async def _store_ai_response(
        self,
        session_id: str,
        user_id: str,
        response: str,
        contexts_used: int,
        tokens_estimated: int
    ) -> None:
        """Store AI response in chat history."""
        try:
            self.chat_history.add_message(
                session_id=session_id,
                role="assistant",
                content=response,
                user_id=user_id,
                metadata={
                    "timestamp": datetime.utcnow().isoformat(),
                    "context_items_used": contexts_used,
                    "tokens_estimated": tokens_estimated
                }
            )
            logger.debug(f"Stored AI response for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to store AI response: {e}")
    
    def _build_audit_trail(
        self,
        user_id: str,
        session_id: str,
        retrieved_contexts: List[RetrievedContext],
        is_emergency: bool
    ) -> Dict[str, Any]:
        """Build HIPAA-compliant audit trail."""
        # Determine if PHI was accessed
        phi_context_types = {
            ContextType.RECENT_VITALS,
            ContextType.MEDICATIONS,
            ContextType.MEDICAL_HISTORY,
            ContextType.EMERGENCY_INFO,
            ContextType.RISK_ASSESSMENTS
        }
        
        phi_accessed = any(
            ctx.context_type in phi_context_types
            for ctx in retrieved_contexts
        )
        
        return {
            "action": "ai_query_processed",
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "context_types_accessed": [
                ctx.context_type.value for ctx in retrieved_contexts
            ],
            "phi_accessed": phi_accessed,
            "is_emergency": is_emergency,
            "context_sources": list(set(
                ctx.source for ctx in retrieved_contexts
            ))
        }
    
    # ========================================================================
    # Convenience Methods
    # ========================================================================
    
    async def quick_query(
        self,
        user_id: str,
        query: str
    ) -> str:
        """
        Quick query with auto-generated session ID.
        
        Convenience method for one-off queries.
        """
        import uuid
        session_id = f"quick_{uuid.uuid4().hex[:8]}"
        response = await self.process_query(
            user_id=user_id,
            session_id=session_id,
            query=query
        )
        return response.response
    
    async def continue_conversation(
        self,
        session_id: str,
        query: str
    ) -> AIResponse:
        """
        Continue an existing conversation.
        
        Extracts user_id from session history.
        """
        # Try to get user_id from session
        session_info = self.chat_history.get_session_info(session_id)
        user_id = session_info.get("user_id", "unknown") if session_info else "unknown"
        
        return await self.process_query(
            user_id=user_id,
            session_id=session_id,
            query=query
        )
    
    # ========================================================================
    # Stats and Health
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "total_queries": self._total_queries,
            "successful_queries": self._successful_queries,
            "failed_queries": self._failed_queries,
            "success_rate": (
                self._successful_queries / max(1, self._total_queries) * 100
            ),
            "avg_processing_time_ms": (
                self._total_processing_time / max(1, self._successful_queries)
            ),
            "context_retriever_stats": self.context_retriever.get_stats(),
            "preferences_health": self.preferences.health_check()
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        health = {
            "status": "healthy",
            "components": {}
        }
        
        # Check chat history
        try:
            self.chat_history.get_history("health_check_session", limit=1)
            health["components"]["chat_history"] = "ok"
        except Exception as e:
            health["components"]["chat_history"] = f"error: {e}"
            health["status"] = "degraded"
        
        # Check preferences
        try:
            pref_health = self.preferences.health_check()
            health["components"]["preferences"] = pref_health["status"]
            if pref_health["status"] != "healthy":
                health["status"] = "degraded"
        except Exception as e:
            health["components"]["preferences"] = f"error: {e}"
            health["status"] = "degraded"
        
        # Check AI providers
        health["components"]["gemini"] = "configured" if self.gemini else "not configured"
        health["components"]["ollama"] = "configured" if self.ollama else "not configured"
        
        if not self.gemini and not self.ollama:
            health["status"] = "degraded"
            health["warning"] = "No AI provider configured"
        
        health["timestamp"] = datetime.utcnow().isoformat()
        return health


# ============================================================================
# Singleton Instance
# ============================================================================

_integrated_service: Optional[IntegratedHealthAIService] = None


def get_integrated_ai_service() -> IntegratedHealthAIService:
    """Get or create the singleton integrated AI service."""
    global _integrated_service
    if _integrated_service is None:
        _integrated_service = IntegratedHealthAIService()
    return _integrated_service


def init_integrated_ai_service(
    gemini_client=None,
    ollama_client=None,
    database_url: Optional[str] = None,
    **kwargs
) -> IntegratedHealthAIService:
    """Initialize integrated AI service with configuration."""
    global _integrated_service
    _integrated_service = IntegratedHealthAIService(
        gemini_client=gemini_client,
        ollama_client=ollama_client,
        database_url=database_url,
        **kwargs
    )
    return _integrated_service
