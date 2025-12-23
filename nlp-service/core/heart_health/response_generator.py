"""
Heart Health AI Assistant - Core Response Generator

Implements the RAG + User Context workflow for generating personalized
AI responses about heart health and cardiovascular conditions.
"""

import logging
import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Local imports
from .emergency_detector import EmergencyDetector, UrgencyLevel

# Import existing medical AI components
from medical_ai.smart_watch.chatbot_connector import ChatbotManager
from medical_ai.smart_watch.feature_extractor import FeatureExtractor
from medical_ai.smart_watch.rule_engine import RuleEngine

# Import notification services
from ..notifications.push_service import HealthPushNotificationService, PushNotificationService


@dataclass
class GenerationConfig:
    """Configuration for response generation."""
    max_chat_history: int = 5
    max_vitals_readings: int = 100
    vitals_lookback_hours: int = 24
    max_rag_results: int = 5
    temperature_normal: float = 0.7
    temperature_emergency: float = 0.3
    max_tokens: int = 512


class HeartHealthResponseGenerator:
    """
    Generates contextual responses for heart health queries.
    
    Workflow:
    1. Fetch user profile and history from MySQL
    2. Fetch recent chat history for context continuity
    3. Fetch smart watch vitals (BPM, SPO2) from MySQL
    4. Query ChromaDB for relevant medical guidelines
    5. Detect emergency keywords and classify urgency
    6. Construct augmented prompt with all context
    7. Generate response using ChatbotManager (Gemini/Ollama)
    8. Store response in chat history
    9. Return response with metadata
    """
    
    def __init__(self, config: Optional[GenerationConfig] = None):
        self.config = config or GenerationConfig()
        self.db = None
        self.chroma_service = None
        self.chatbot_manager = None
        self.embedding_model = None
        self.emergency_detector = EmergencyDetector()
        self.rule_engine = RuleEngine()
        self.initialized = False
    
    async def initialize(self) -> bool:
        """Initialize all service dependencies."""
        try:
            # Initialize MySQL connection (XAMPP)
            try:
                from ..database.xampp_db import get_database
                self.db = await get_database()
                if self.db and self.db.initialized:
                    logger.info("MySQL database connected")
                else:
                    logger.warning("MySQL database not fully initialized")
            except Exception as e:
                logger.warning(f"MySQL connection failed: {e}")
                self.db = None
            
            # Initialize ChromaDB service
            try:
                from ..database.chroma_db import get_chroma_service
                self.chroma_service = await get_chroma_service()
                if self.chroma_service and self.chroma_service.initialized:
                    logger.info("ChromaDB service connected")
                else:
                    logger.warning("ChromaDB not fully initialized (optional)")
            except Exception as e:
                logger.warning(f"ChromaDB connection failed (optional): {e}")
                self.chroma_service = None
            
            # Initialize Chatbot Manager (Unified LLM Gateway)
            try:
                self.chatbot_manager = ChatbotManager()
                logger.info("Chatbot Manager initialized")
            except Exception as e:
                logger.error(f"Chatbot Manager failed: {e}")
                self.chatbot_manager = None
            
            # Initialize embedding model (for fallback RAG)
            try:
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Embedding model loaded")
            except Exception as e:
                logger.warning(f"Embedding model not loaded: {e}")
                self.embedding_model = None
            
            # Initialize Health Push Service
            try:
                push_service = PushNotificationService()
                self.health_push = HealthPushNotificationService(push_service)
                logger.info("Health Push Service initialized")
            except Exception as e:
                logger.warning(f"Health Push Service failed: {e}")
                self.health_push = None

            # Check if we have minimum requirements
            if self.chatbot_manager is None:
                logger.error("Chatbot Manager is required but not available")
                return False
            
            self.initialized = True
            logger.info("HeartHealthResponseGenerator initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize response generator: {e}", exc_info=True)
            return False
    
    async def generate_response(
        self,
        user_id: str,
        user_query: str,
        session_id: Optional[str] = None,
        include_vitals: bool = True
    ) -> Dict[str, Any]:
        """
        Main entry point for generating AI responses.
        
        Args:
            user_id: Unique user identifier
            user_query: The user's question
            session_id: Optional chat session ID for context continuity
            include_vitals: Whether to include smart watch vitals in context
            
        Returns:
            Dict containing response, success status, metadata, and context used
        """
        if not self.initialized:
            # Try to initialize on first call
            await self.initialize()
            if not self.initialized:
                return {
                    "response": "Service not initialized. Please try again later.",
                    "success": False,
                    "error": "Service initialization required"
                }
        
        try:
            start_time = datetime.now()
            
            # Generate session ID if not provided
            if not session_id:
                session_id = str(uuid.uuid4())
            
            # ================================================================
            # STEP 1: Detect Emergency
            # ================================================================
            emergency_assessment = self.emergency_detector.detect(user_query)
            is_emergency = emergency_assessment.is_emergency
            urgency_level = emergency_assessment.urgency_level
            
            # Trigger alert if emergency or urgent
            if (is_emergency or urgency_level == UrgencyLevel.URGENT) and self.health_push:
                try:
                    # Fetch device token (mock implementation - would come from user profile)
                    # For now, we log it, but in production we'd look up the token
                    # device_token = await self._get_user_device_token(user_id)
                    # if device_token:
                    #     severity = "critical" if is_emergency else "warning"
                    #     await self.health_push.send_health_alert(
                    #         device_token=device_token,
                    #         alert_title="Health Alert",
                    #         alert_message=emergency_assessment.recommended_action[:100],
                    #         severity=severity
                    #     )
                    pass # Placeholder until device token lookup is implemented
                except Exception as e:
                    logger.error(f"Failed to send emergency alert: {e}")
            
            # ================================================================
            # STEP 2: Fetch User Profile from MySQL
            # ================================================================
            user_profile = await self._fetch_user_profile(user_id)
            
            # ================================================================
            # STEP 3: Fetch Recent Chat History
            # ================================================================
            chat_history = await self._fetch_chat_history(
                session_id=session_id,
                limit=self.config.max_chat_history
            )
            
            # ================================================================
            # STEP 4: Fetch Vitals Data from MySQL
            # ================================================================
            vitals_context = None
            if include_vitals:
                vitals_context = await self._fetch_vitals_context(
                    user_id=user_id,
                    hours_back=self.config.vitals_lookback_hours
                )
            
            # ================================================================
            # STEP 5: Query ChromaDB for Medical Guidelines
            # ================================================================
            medical_context = await self._fetch_medical_context(
                query=user_query,
                limit=self.config.max_rag_results
            )
            
            # ================================================================
            # STEP 6: Construct Augmented Prompt
            # ================================================================
            system_prompt, user_prompt = self._construct_prompts(
                user_query=user_query,
                user_profile=user_profile,
                chat_history=chat_history,
                vitals_context=vitals_context,
                medical_context=medical_context,
                emergency_assessment=emergency_assessment
            )
            
            # ================================================================
            # STEP 7: Generate Response using Chatbot Manager
            # ================================================================
            temperature = (
                self.config.temperature_emergency if is_emergency
                else self.config.temperature_normal
            )
            
            chat_response = await self.chatbot_manager.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=self.config.max_tokens
            )
            
            response_text = chat_response.content
            if not chat_response.success:
                logger.warning(f"Chatbot generation failed: {chat_response.error}")
                response_text = "I apologize, but I'm having trouble generating a response right now. Please try again later."
            
            response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # ================================================================
            # STEP 8: Store in Chat History (MySQL)
            # ================================================================
            await self._store_chat_messages(
                session_id=session_id,
                user_message=user_query,
                assistant_response=response_text,
                metadata={
                    "response_time_ms": response_time_ms,
                    "is_emergency": is_emergency,
                    "urgency_level": urgency_level.value,
                    "rag_docs_used": len(medical_context),
                    "model_used": chat_response.model
                }
            )
            
            # ================================================================
            # STEP 9: Return Response with Metadata
            # ================================================================
            return {
                "response": response_text,
                "success": chat_response.success,
                "session_id": session_id,
                "metadata": {
                    "user_id": user_id,
                    "is_emergency": is_emergency,
                    "urgency_level": urgency_level.value,
                    "recommended_action": emergency_assessment.recommended_action,
                    "response_time_ms": response_time_ms,
                    "model_used": chat_response.model,
                    "context_summary": {
                        "user_profile_loaded": user_profile is not None,
                        "chat_history_messages": len(chat_history),
                        "vitals_data_available": vitals_context is not None,
                        "medical_docs_retrieved": len(medical_context)
                    }
                },
                "context_used": {
                    "medical_guidelines": [
                        {
                            "id": ctx.get("id"),
                            "collection": ctx.get("collection"),
                            "similarity": ctx.get("similarity")
                        }
                        for ctx in medical_context[:3]
                    ],
                    "vitals_summary": vitals_context.get("summary") if vitals_context else None
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            return {
                "response": "I apologize, but I'm having trouble processing your request. Please try again or consult a healthcare professional if you have urgent concerns.",
                "success": False,
                "error": str(e)
            }
    
    # ========================================================================
    # HELPER METHODS - Data Fetching
    # ========================================================================
    
    async def _fetch_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user profile from MySQL."""
        if not self.db or not self.db.initialized:
            return None
        
        try:
            async with self.db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT user_id, name, date_of_birth, gender, blood_type,
                               weight_kg, height_cm, known_conditions, medications, allergies
                        FROM users
                        WHERE user_id = %s AND is_active = TRUE
                    """, (user_id,))
                    
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "user_id": row[0],
                            "name": row[1],
                            "date_of_birth": row[2],
                            "gender": row[3],
                            "blood_type": row[4],
                            "weight_kg": float(row[5]) if row[5] else None,
                            "height_cm": float(row[6]) if row[6] else None,
                            "known_conditions": row[7],
                            "medications": row[8],
                            "allergies": row[9]
                        }
            return None
        except Exception as e:
            logger.warning(f"Error fetching user profile: {e}")
            return None
    
    async def _fetch_chat_history(
        self,
        session_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Fetch recent chat history for context continuity."""
        if not self.db or not self.db.initialized:
            return []
        
        try:
            return await self.db.get_chat_history(session_id=session_id, limit=limit)
        except Exception as e:
            logger.warning(f"Error fetching chat history: {e}")
            return []
    
    async def _fetch_vitals_context(
        self,
        user_id: str,
        hours_back: int = 24
    ) -> Optional[Dict[str, Any]]:
        """Fetch and analyze recent vitals data using FeatureExtractor and RuleEngine."""
        if not self.db or not self.db.initialized:
            return None
        
        try:
            async with self.db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    cutoff = datetime.now() - timedelta(hours=hours_back)
                    
                    await cursor.execute("""
                        SELECT metric_type, value, recorded_at
                        FROM vitals
                        WHERE user_id = %s
                          AND metric_type IN ('heart_rate', 'spo2', 'steps')
                          AND recorded_at >= %s
                        ORDER BY recorded_at ASC
                    """, (user_id, cutoff))
                    
                    rows = await cursor.fetchall()
                    
                    if not rows:
                        return None
                    
                    # Initialize FeatureExtractor
                    extractor = FeatureExtractor(window_size=len(rows) + 10)
                    
                    # Group by minute to feed complete samples
                    samples = {}
                    for row in rows:
                        metric = row[0]
                        value = float(row[1])
                        ts = row[2]
                        key = ts.strftime("%Y-%m-%d %H:%M") # Minute precision
                        
                        if key not in samples:
                            samples[key] = {"hr": 0, "spo2": 98, "steps": 0}
                        
                        if metric == 'heart_rate':
                            samples[key]["hr"] = value
                        elif metric == 'spo2':
                            samples[key]["spo2"] = value
                        elif metric == 'steps':
                            samples[key]["steps"] = int(value)
                    
                    # Feed sorted samples
                    for key in sorted(samples.keys()):
                        s = samples[key]
                        if s["hr"] > 0: # Only add if we have HR
                            extractor.add_sample(hr=s["hr"], spo2=s["spo2"], steps=s["steps"])
                    
                    # Extract features
                    features = extractor.extract_features()
                    
                    if not features:
                        return {"summary": "Insufficient data for analysis"}
                    
                    # Run Rule Engine
                    anomalies = self.rule_engine.analyze(features)
                    status = self.rule_engine.get_overall_status(anomalies)
                    
                    return {
                        "features": {
                            "hr_current": features.hr_current,
                            "hr_mean": features.hr_mean_5min,
                            "spo2_current": features.spo2_current,
                            "is_resting": features.is_resting
                        },
                        "anomalies": [
                            {
                                "type": a.anomaly_type.value,
                                "message": a.message,
                                "severity": a.severity.name
                            } for a in anomalies
                        ],
                        "status": status,
                        "summary": f"Status: {status['status']}. {status['message']}"
                    }
                    
        except Exception as e:
            logger.warning(f"Error fetching vitals: {e}")
            return None
    
    async def _fetch_medical_context(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for relevant medical knowledge."""
        results = []
        
        # Try ChromaDB first
        if self.chroma_service and self.chroma_service.initialized:
            try:
                results = await self.chroma_service.search_all_collections(
                    query=query,
                    limit=limit
                )
                if results:
                    return results
            except Exception as e:
                logger.warning(f"ChromaDB search failed: {e}")
        
        # Fallback to MySQL-based RAG
        if self.db and self.db.initialized and self.embedding_model:
            try:
                query_embedding = self.embedding_model.encode(query).tolist()
                results = await self.db.search_similar_knowledge(
                    query_embedding=query_embedding,
                    limit=limit
                )
            except Exception as e:
                logger.warning(f"MySQL RAG fallback failed: {e}")
        
        return results
    
    # ========================================================================
    # HELPER METHODS - Prompt Construction
    # ========================================================================
    
    def _construct_prompts(
        self,
        user_query: str,
        user_profile: Optional[Dict],
        chat_history: List[Dict],
        vitals_context: Optional[Dict],
        medical_context: List[Dict],
        emergency_assessment
    ) -> tuple[str, str]:
        """Construct system and user prompts with all context."""
        
        # System instruction
        system_prompt = """You are HeartGuard AI, a specialized Heart Health Assistant focused on cardiovascular health.

Your role is to:
- Provide helpful, accurate, and empathetic responses about heart health
- Use the provided user profile, vitals data, and medical guidelines to personalize responses
- Always remind users to consult healthcare professionals for medical decisions
- Never diagnose conditions - only provide educational information
- If an emergency is detected, prioritize safety guidance"""

        # Emergency warning if detected
        if emergency_assessment.is_emergency:
            system_prompt += f"""

⚠️ EMERGENCY MODE ACTIVATED ⚠️
{emergency_assessment.recommended_action}

Prioritize immediate safety guidance in your response."""
        elif emergency_assessment.urgency_level == UrgencyLevel.URGENT:
            system_prompt += f"""

🔴 URGENT CONCERN DETECTED
{emergency_assessment.recommended_action}

Address the urgency appropriately in your response."""
        
        # Build context sections
        context_parts = []
        
        # User Profile
        if user_profile:
            age = self._calculate_age(user_profile.get("date_of_birth"))
            profile_text = f"""
PATIENT PROFILE:
- Name: {user_profile.get('name', 'Unknown')}
- Age: {age if age else 'Unknown'}
- Gender: {user_profile.get('gender', 'Unknown')}
- Known Conditions: {self._format_json_field(user_profile.get('known_conditions'))}
- Current Medications: {self._format_json_field(user_profile.get('medications'))}
- Allergies: {self._format_json_field(user_profile.get('allergies'))}"""
            context_parts.append(profile_text)
        
        # Vitals Data
        if vitals_context:
            vitals_text = f"""
RECENT VITALS ANALYSIS:
- Status: {vitals_context.get('status', {}).get('message', 'Unknown')}
- Current HR: {vitals_context.get('features', {}).get('hr_current', 'N/A')} bpm
- Avg HR (5min): {vitals_context.get('features', {}).get('hr_mean', 'N/A')} bpm
- SpO2: {vitals_context.get('features', {}).get('spo2_current', 'N/A')}%
- Anomalies Detected: {len(vitals_context.get('anomalies', []))}
"""
            for anomaly in vitals_context.get('anomalies', []):
                vitals_text += f"  - ⚠️ {anomaly['message']} ({anomaly['severity']})\n"
            
            context_parts.append(vitals_text)
        
        # Medical Guidelines (RAG)
        if medical_context:
            guidelines_text = "\nRELEVANT MEDICAL INFORMATION:"
            for i, ctx in enumerate(medical_context[:3], 1):
                content = ctx.get("content", "")[:400]
                source = ctx.get("metadata", {}).get("source", "Medical Reference")
                guidelines_text += f"\n[{i}] ({source}) {content}..."
            context_parts.append(guidelines_text)
        
        # Chat History
        if chat_history:
            history_text = "\nRECENT CONVERSATION:"
            for msg in chat_history[-3:]:
                role = msg.get("message_type", msg.get("role", "unknown")).upper()
                content = msg.get("content", "")[:150]
                history_text += f"\n{role}: {content}"
            context_parts.append(history_text)
        
        # Combine everything for the user prompt wrapper
        full_context = "\n".join(context_parts) if context_parts else "No additional context available."
        
        user_prompt_wrapper = f"""
CONTEXT INFORMATION:
{full_context}

USER QUESTION: {user_query}

Please provide a helpful, personalized response:"""

        return system_prompt, user_prompt_wrapper
    
    def _calculate_age(self, dob) -> Optional[int]:
        """Calculate age from date of birth."""
        if not dob:
            return None
        try:
            today = datetime.now().date()
            if isinstance(dob, str):
                dob = datetime.strptime(dob, "%Y-%m-%d").date()
            elif hasattr(dob, 'date'):
                dob = dob.date()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except Exception:
            return None
    
    def _format_json_field(self, value) -> str:
        """Format a JSON field for display."""
        if not value:
            return "None reported"
        if isinstance(value, str):
            try:
                import json
                value = json.loads(value)
            except Exception:
                return value
        if isinstance(value, list):
            return ", ".join(str(v) for v in value) if value else "None reported"
        return str(value)
    
    async def _store_chat_messages(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        metadata: Dict = None
    ) -> bool:
        """Store user and assistant messages in chat history."""
        if not self.db or not self.db.initialized:
            return False
        
        try:
            # Store user message
            await self.db.store_chat_message(
                session_id=session_id,
                message_type="user",
                content=user_message,
                metadata=None
            )
            
            # Store assistant response
            await self.db.store_chat_message(
                session_id=session_id,
                message_type="assistant",
                content=assistant_response,
                metadata=metadata
            )
            
            return True
        except Exception as e:
            logger.warning(f"Failed to store chat messages: {e}")
            return False


# ============================================================================
# SINGLETON INSTANCE AND CONVENIENCE FUNCTIONS
# ============================================================================

_response_generator: Optional[HeartHealthResponseGenerator] = None


async def get_response_generator() -> HeartHealthResponseGenerator:
    """Get singleton response generator instance."""
    global _response_generator
    if _response_generator is None:
        _response_generator = HeartHealthResponseGenerator()
        await _response_generator.initialize()
    return _response_generator


async def generate_response(user_id: str, user_query: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function for generating responses.
    
    Usage:
        result = await generate_response("user123", "Is my heart rate of 120 dangerous?")
        print(result["response"])
    
    Args:
        user_id: Unique user identifier
        user_query: The user's question
        **kwargs: Additional arguments (session_id, include_vitals)
        
    Returns:
        Dict containing response, success status, and metadata
    """
    generator = await get_response_generator()
    return await generator.generate_response(user_id=user_id, user_query=user_query, **kwargs)
