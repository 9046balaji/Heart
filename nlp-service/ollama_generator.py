"""
Ollama Generator Module
Handles inference with Ollama models (specifically gemma3:4b)
Manages conversation history and generates contextual responses
"""

import logging
import asyncio
import logging
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime
import ollama
import requests
from fastapi.concurrency import run_in_threadpool
from starlette.concurrency import iterate_in_threadpool
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    AsyncRetrying,
)  # PHASE 2: Add retry logic with exponential backoff

from circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from error_handling import (
    ExternalServiceError,
    TimeoutError,
    ProcessingError,
)  # PHASE 2: Import exception hierarchy
# Fix the relative import issue
try:
    from chat_history import chat_history_manager
except ImportError:
    # Fallback if running as a module
    from .chat_history import chat_history_manager

# Import structured output support
try:
    from structured_outputs import (
        StructuredOutputParser,
        StructuredGenerator,
        HealthAnalysisGenerator,
        CardioHealthAnalysis,
        SimpleIntentAnalysis,
        ConversationResponse,
        pydantic_to_json_schema,
        get_schema_prompt,
    )
    STRUCTURED_OUTPUTS_AVAILABLE = True
except ImportError:
    STRUCTURED_OUTPUTS_AVAILABLE = False
    # logger will be defined after this block

# Configure logging
logger = logging.getLogger(__name__)

if not STRUCTURED_OUTPUTS_AVAILABLE:
    logger.warning("Structured outputs module not available")


class OllamaGenerator:
    """
    Wrapper around Ollama client for generating responses using gemma3:1b model
    Supports streaming and non-streaming responses with conversation context
    """

    def __init__(
        self,
        model_name: str = "gemma3:1b",
        ollama_host: str = "http://localhost:11434",
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        max_tokens: int = 512,
        context_window: int = 2048,
    ):
        """
        Initialize Ollama Generator

        Args:
            model_name: Model to use (default: gemma3:4b)
            ollama_host: Ollama server URL (use 127.0.0.1 for localhost loopback)
            temperature: Sampling temperature (0.0-2.0, higher = more creative)
            top_p: Nucleus sampling parameter
            top_k: Top K sampling parameter
            max_tokens: Maximum tokens to generate
            context_window: Maximum tokens the model can handle (default: 2048 for gemma3:4b)
        """
        self.model_name = model_name
        # Normalize localhost to 127.0.0.1 for consistency
        self.ollama_host = ollama_host.replace("localhost", "127.0.0.1")
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.context_window = context_window
        
        # Create Ollama client with longer timeout (30 seconds)
        self.client = ollama.Client(host=self.ollama_host, timeout=120.0)
        
        # Also create requests session for direct HTTP calls as fallback
        self.session = requests.Session()
        self.session.timeout = 60  # 60 second timeout for generation
        
        self.generation_count = 0
        self.total_tokens = 0
        
        # Initialize circuit breaker for Ollama resilience
        # 3 failures before opening, 30s recovery timeout
        self.circuit_breaker = CircuitBreaker(
            name="OllamaService",
            failure_threshold=3,
            recovery_timeout=30,
            expected_exception=Exception
        )

        logger.info(
            f"OllamaGenerator initialized with model: {model_name} at {self.ollama_host} (context_window={context_window}, timeout=30s)"
        )

    async def is_available(self) -> bool:
        """
        Check if Ollama server is available and model is loaded

        Returns:
            True if Ollama is reachable and model is available
        """
        try:
            # First, try direct HTTP GET to check if service is responding
            check_url = f"{self.ollama_host}/api/tags"
            logger.info(f"Checking Ollama availability at {check_url}...")
            
            # Use requests with timeout in threadpool to avoid blocking
            def _check_health():
                try:
                    response = requests.get(check_url, timeout=5)
                    return response.status_code == 200
                except Exception as e:
                    logger.debug(f"Health check request failed: {e}")
                    return False
            
            is_responding = await run_in_threadpool(_check_health)
            
            if not is_responding:
                logger.warning(f"Ollama server not responding at {check_url}")
                return False
            
            # Then check if model is available
            try:
                response = self.client.list()
                # Handle both old ('name') and new ('model') formats from Ollama API
                models = response.get("models", [])
                model_names = []
                for m in models:
                    # Check for 'name' or 'model' key
                    name = m.get("name") or m.get("model")
                    if name:
                        model_names.append(name.split(":")[0])
                
                is_available = self.model_name.split(":")[0] in model_names
                logger.info(
                    f"Ollama availability check: {is_available} (available models: {model_names})"
                )
                return is_available
            except Exception as e:
                logger.error(f"Error listing Ollama models: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Ollama server unavailable: {str(e)}")
            return False

    def _prune_history(
        self,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        buffer_tokens: int = 512,
    ) -> List[Dict[str, str]]:
        """
        Prune conversation history to fit within context window limits.
        
        Uses rough token estimation (4 characters ≈ 1 token) to prevent:
        - Silent context truncation at the model level
        - OOM errors from oversized prompts
        - Loss of conversation quality from incomplete context
        
        Strategy: Remove oldest messages first, keeping recent context for coherence
        
        Args:
            conversation_history: List of messages with 'role' and 'content'
            buffer_tokens: Reserve tokens for system prompt, user input, and response
                          (default: 512 for system prompt + user message space)
        
        Returns:
            Pruned conversation history that fits within context window
        """
        if not conversation_history:
            return []
        
        # Calculate available tokens for history
        available_tokens = self.context_window - self.max_tokens - buffer_tokens
        
        if available_tokens <= 0:
            logger.warning(
                f"Context window ({self.context_window}) too small for max_tokens ({self.max_tokens}) "
                f"+ buffer ({buffer_tokens}). Keeping only last 2 messages."
            )
            return conversation_history[-2:] if len(conversation_history) >= 2 else conversation_history
        
        # Rough token estimation: 4 chars = 1 token (common heuristic for English)
        def estimate_tokens(text: str) -> int:
            return max(1, len(text) // 4)
        
        # Build pruned history from newest to oldest (reverse iteration)
        pruned_history = []
        current_tokens = 0
        
        for msg in reversed(conversation_history):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Estimate tokens: role label + content + formatting
            msg_tokens = estimate_tokens(f"{role}: {content}\n")
            
            if current_tokens + msg_tokens <= available_tokens:
                pruned_history.insert(0, msg)  # Insert at beginning to maintain order
                current_tokens += msg_tokens
            else:
                # Stop adding messages once we exceed the limit
                logger.debug(
                    f"History pruning: Removed oldest {len(conversation_history) - len(pruned_history)} messages "
                    f"({current_tokens}/{available_tokens} tokens used)"
                )
                break
        
        return pruned_history

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, requests.RequestException)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retry attempt {retry_state.attempt_number} for generate_response. "
            f"Will retry in {retry_state.next_action.sleep} seconds."
        ),
    )  # PHASE 2: Add retry with exponential backoff (2-10s, max 3 attempts)
    async def generate_response(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        stream: bool = False,
    ) -> str:
        """
        Generate response using Ollama gemma3:4b model with Circuit Breaker protection

        Args:
            prompt: User input message
            conversation_history: List of previous messages with 'role' and 'content'
            system_prompt: Optional system prompt for context
            stream: Whether to stream response

        Returns:
            Generated response text (or async generator if stream=True)
            
        Raises:
            CircuitBreakerOpen: If Ollama service is unavailable
        """
        try:
            # Check circuit breaker status
            if self.circuit_breaker.is_open:
                logger.warning("Circuit breaker is OPEN. Ollama service is currently unavailable.")
                raise CircuitBreakerOpen(
                    "Ollama service is temporarily unavailable. Please try again later."
                )
            
            # Prune conversation history to fit within context window
            pruned_history = self._prune_history(conversation_history)
            
            # Build context from pruned conversation history
            context_text = ""
            if pruned_history:
                for msg in pruned_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    context_text += f"{role.capitalize()}: {content}\n"

            # Build full prompt with system message and context
            if system_prompt:
                full_prompt = f"{system_prompt}\n\nConversation:\n{context_text}User: {prompt}\nAssistant:"
            else:
                full_prompt = f"{context_text}User: {prompt}\nAssistant:" if context_text else f"User: {prompt}\nAssistant:"

            logger.info(
                f"Generating response with {self.model_name} (stream={stream}, history_msgs={len(pruned_history)})"
            )

            if stream:
                return self._stream_response(full_prompt)
            else:
                # Wrap in circuit breaker with timeout handling
                def _generate():
                    try:
                        logger.debug(f"Calling Ollama.generate() with timeout of 60s")
                        response = self.client.generate(
                            model=self.model_name,
                            prompt=full_prompt,
                            stream=False,
                            options={
                                'temperature': self.temperature,
                                'top_p': self.top_p,
                                'top_k': self.top_k,
                                'num_predict': self.max_tokens,
                            }
                        )
                        logger.debug(f"Ollama response received: {len(response.get('response', ''))} chars")
                        return response
                    except Exception as e:
                        logger.error(f"Error in Ollama generate call: {type(e).__name__}: {str(e)}")
                        # Add more detailed timeout error handling
                        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                            logger.warning("Ollama request timed out - model may still be loading")
                        raise
                
                # Execute circuit breaker call in threadpool with timeout of 65 seconds
                logger.info(f"Generating response with {self.model_name} - starting circuit breaker call")
                response = await asyncio.wait_for(
                    run_in_threadpool(self.circuit_breaker.call, _generate),
                    timeout=65.0  # 5 second buffer beyond client timeout
                )
                
                generated_text = response["response"].strip()
                self.generation_count += 1
                self.total_tokens += response.get("eval_count", 0)

                logger.info(
                    f"Generated response ({response.get('eval_count', 0)} tokens, total: {self.total_tokens})"
                )

                return generated_text

        except asyncio.TimeoutError as e:
            logger.error(f"Ollama generation timeout after 65 seconds")
            raise Exception("Ollama generation timeout - model may be overloaded")
        except CircuitBreakerOpen as e:
            logger.warning(f"Circuit breaker blocked Ollama call: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error generating response: {type(e).__name__}: {str(e)}")
            raise

    def _stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Stream response from Ollama

        Args:
            prompt: Full prompt with context

        Yields:
            Response chunks as they are generated
        """

        async def _stream_generator():
            try:
                # Initial call in threadpool
                response = await run_in_threadpool(
                    self.client.generate,
                    model=self.model_name,
                    prompt=prompt,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    top_k=self.top_k,
                    num_predict=self.max_tokens,
                    stream=True,
                )

                # Iterate in threadpool
                async for chunk in iterate_in_threadpool(response):
                    if "response" in chunk:
                        text = chunk["response"]
                        if text:
                            yield text

                        # Update stats on final chunk
                        if chunk.get("done", False):
                            self.generation_count += 1
                            self.total_tokens += chunk.get("eval_count", 0)
                            logger.info(
                                f"Stream complete ({chunk.get('eval_count', 0)} tokens)"
                            )

            except Exception as e:
                logger.error(f"Error in stream generation: {str(e)}")
                raise

        return _stream_generator()

    async def _stream_response_async(
        self,
        prompt: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async stream response from Ollama with conversation history support

        Args:
            prompt: User input message
            conversation_history: List of previous messages
            system_prompt: Optional system prompt

        Yields:
            Response chunks as they are generated
        """
        try:
            # Prune conversation history to fit within context window
            pruned_history = self._prune_history(conversation_history)
            
            # Build context from pruned conversation history
            context_text = ""
            if pruned_history:
                for msg in pruned_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    context_text += f"{role.capitalize()}: {content}\n"

            # Build full prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\nConversation:\n{context_text}User: {prompt}\nAssistant:"
            else:
                full_prompt = f"{context_text}User: {prompt}\nAssistant:" if context_text else f"User: {prompt}\nAssistant:"

            logger.info(f"Streaming response with {self.model_name} (history_msgs={len(pruned_history)})")

            # Stream response (initial call)
            response = await run_in_threadpool(
                self.client.generate,
                model=self.model_name,
                prompt=full_prompt,
                temperature=self.temperature,
                top_p=self.top_p,
                top_k=self.top_k,
                num_predict=self.max_tokens,
                stream=True,
            )

            token_count = 0
            # Iterate in threadpool
            async for chunk in iterate_in_threadpool(response):
                if "response" in chunk:
                    text = chunk["response"]
                    if text:
                        token_count += 1
                        yield text

                    # Update stats on final chunk
                    if chunk.get("done", False):
                        self.generation_count += 1
                        self.total_tokens += chunk.get("eval_count", 0)
                        logger.info(
                            f"Stream complete ({token_count} tokens, total: {self.total_tokens})"
                        )

        except Exception as e:
            logger.error(f"Error in async stream generation: {str(e)}")
            raise

    async def generate_healthcare_response(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        stream: bool = False,
    ) -> str:
        """
        Generate healthcare-specific response with medical context awareness.
        Uses per‑session chat history when a `session_id` is provided.

        Args:
            user_message: User's healthcare question/statement.
            session_id: Optional identifier for the conversation session.
            stream: Whether to stream response.

        Returns:
            Generated healthcare response.
        """
        healthcare_system_prompt = """You are a helpful healthcare chatbot assistant. 
        Provide accurate, supportive healthcare information.
        Always recommend consulting healthcare professionals for serious concerns.
        Be empathetic and clear in your responses."""

        # Load stored history if a session_id is provided
        stored_history: List[Dict[str, str]] = []
        if session_id:
            stored_history = chat_history_manager.get(session_id)
            # Record the incoming user message for future turns
            chat_history_manager.add(session_id, "user", user_message)

        response = await self.generate_response(
            prompt=user_message,
            conversation_history=stored_history,
            system_prompt=healthcare_system_prompt,
            stream=stream,
        )

        # Store the assistant reply for the session
        if session_id:
            chat_history_manager.add(session_id, "assistant", response)
        return response

    def get_stats(self) -> Dict[str, any]:
        """Get generation statistics"""
        return {
            "model": self.model_name,
            "generation_count": self.generation_count,
            "total_tokens": self.total_tokens,
            "average_tokens_per_generation": (
                self.total_tokens / self.generation_count
                if self.generation_count > 0
                else 0
            ),
        }

    async def health_check(self) -> Dict[str, any]:
        """
        Perform health check on Ollama connection

        Returns:
            Health check status
        """
        available = await self.is_available()
        return {
            "status": "healthy" if available else "unhealthy",
            "model": self.model_name,
            "ollama_host": self.ollama_host,
            "available": available,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ========================================================================
    # STRUCTURED OUTPUT GENERATION METHODS
    # ========================================================================

    async def generate_structured_response(
        self,
        prompt: str,
        output_schema: type,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """
        Generate a response that conforms to a specific Pydantic schema.
        
        This method uses schema-guided generation to ensure the LLM output
        matches the expected structure exactly.
        
        Args:
            prompt: User input message
            output_schema: Pydantic model class defining the output structure
            conversation_history: Previous messages for context
            system_prompt: Additional system instructions
            session_id: Optional session ID for history tracking
            
        Returns:
            Parsed instance of output_schema
            
        Raises:
            ValueError: If structured outputs module is not available
            ValueError: If LLM output cannot be parsed into schema
        """
        if not STRUCTURED_OUTPUTS_AVAILABLE:
            raise ValueError("Structured outputs module not available. Cannot generate structured response.")
        
        # Create a generator for the schema
        generator = StructuredGenerator(output_schema)
        
        # Combine any custom system prompt with schema instructions
        schema_prompt = generator.get_schema_prompt()
        combined_system = f"{system_prompt}\n\n{schema_prompt}" if system_prompt else schema_prompt
        
        # Load history if session provided
        history = conversation_history or []
        if session_id and not conversation_history:
            history = chat_history_manager.get(session_id)
        
        # Generate raw response
        raw_response = await self.generate_response(
            prompt=prompt,
            conversation_history=history,
            system_prompt=combined_system,
            stream=False,
        )
        
        # Store in history if session provided
        if session_id:
            chat_history_manager.add(session_id, "user", prompt)
            chat_history_manager.add(session_id, "assistant", raw_response)
        
        # Parse and validate
        parser = StructuredOutputParser(output_schema)
        return parser.parse(raw_response)

    async def generate_health_analysis(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        patient_context: Optional[Dict[str, any]] = None,
    ):
        """
        Generate a structured health analysis response.
        
        Returns a CardioHealthAnalysis object with:
        - Intent classification
        - Sentiment analysis
        - Extracted entities (symptoms, medications, etc.)
        - Recommendations
        - Follow-up questions
        - Urgency assessment
        
        Args:
            user_message: User's health-related query
            session_id: Optional session ID for context
            patient_context: Optional patient information for personalization
            
        Returns:
            CardioHealthAnalysis instance
        """
        if not STRUCTURED_OUTPUTS_AVAILABLE:
            raise ValueError("Structured outputs module not available")
        
        # Build context string from patient info
        context_str = ""
        if patient_context:
            context_str = "Patient Information:\n"
            for key, value in patient_context.items():
                context_str += f"- {key}: {value}\n"
        
        generator = HealthAnalysisGenerator()
        
        # Load history if session provided
        history = []
        if session_id:
            history = chat_history_manager.get(session_id)
            chat_history_manager.add(session_id, "user", user_message)
        
        try:
            result = await generator.generate(
                ollama_generator=self,
                user_message=user_message,
                conversation_history=history,
                additional_context=context_str if context_str else None,
            )
            
            # Store response in history
            if session_id:
                chat_history_manager.add(session_id, "assistant", result.response)
            
            return result
        except Exception as e:
            logger.error(f"Failed to generate health analysis: {e}")
            raise

    async def generate_intent_analysis(
        self,
        user_message: str,
    ):
        """
        Generate a quick intent analysis for a message.
        
        Returns a SimpleIntentAnalysis with:
        - Intent classification
        - Confidence score
        - Keywords identified
        - Brief summary
        
        Args:
            user_message: User's message to analyze
            
        Returns:
            SimpleIntentAnalysis instance
        """
        if not STRUCTURED_OUTPUTS_AVAILABLE:
            raise ValueError("Structured outputs module not available")
        
        system_prompt = """Analyze the user's message and identify their intent.
Classify the intent, extract key terms, and provide a brief summary.
Respond ONLY with valid JSON."""
        
        return await self.generate_structured_response(
            prompt=user_message,
            output_schema=SimpleIntentAnalysis,
            system_prompt=system_prompt,
        )

    def supports_structured_outputs(self) -> bool:
        """Check if structured output generation is available."""
        return STRUCTURED_OUTPUTS_AVAILABLE


# Singleton instance
_ollama_generator: Optional[OllamaGenerator] = None


def get_ollama_generator(
    model_name: str = "gemma3:4b", ollama_host: str = "http://localhost:11434"
) -> OllamaGenerator:
    """
    Get or create Ollama generator singleton

    Args:
        model_name: Model name (default: gemma3:4b)
        ollama_host: Ollama server URL

    Returns:
        OllamaGenerator instance
    """
    global _ollama_generator
    if _ollama_generator is None:
        _ollama_generator = OllamaGenerator(
            model_name=model_name, ollama_host=ollama_host
        )
    return _ollama_generator


def reset_ollama_generator():
    """Reset the singleton instance"""
    global _ollama_generator
    _ollama_generator = None
