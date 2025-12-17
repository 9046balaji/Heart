Repair Plan: Migration Fixes
This document outlines the exact code changes required to fix the syntax errors and code corruption identified during the verification of the LLM Guardrail migration.

1. Fix 
nlp-service/ollama_generator.py
Issue: The generate_response method has a try block that is missing its corresponding except blocks, causing a SyntaxError.

Action: Add the missing error handling blocks to the end of the generate_response method.

Code Change: Replace the end of generate_response (approx. lines 327-346) with the following complete implementation:

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
            
            # Use LLMGateway for generation (Enforces Guardrails)
            from core.llm_gateway import get_llm_gateway
            gateway = get_llm_gateway()
            
            # Determine content type for disclaimers
            content_type = "general"
            if "medical" in prompt.lower() or "health" in prompt.lower():
                content_type = "medical"
            
            return await gateway.generate(
                prompt=full_prompt,
                content_type=content_type,
                model=self.model_name
            )
        except asyncio.TimeoutError as e:
            logger.error(f"Ollama generation timeout")
            raise Exception("Ollama generation timeout")
        except CircuitBreakerOpen as e:
            logger.warning(f"Circuit breaker blocked Ollama call: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error generating response: {type(e).__name__}: {str(e)}")
            raise
2. Fix 
nlp-service/vision/ecg_analyzer.py
Issue: The 
ECGAnalyzer
 class is corrupted. The 
init
 method contains code belonging to 
analyze
, and the 
initialize
 and 
analyze
 methods are missing or malformed.

Action: Restore the 
init
, 
initialize
, and 
analyze
 methods with the correct 
LLMGateway
 integration.

Code Change: Replace the beginning of the class (from def __init__ down to the _build_analysis_prompt method) with:

def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        use_mock: bool = False,
    ):
        """
        Initialize ECG analyzer.
        
        Args:
            gemini_api_key: API key for Gemini Vision
            use_mock: Use mock responses
        """
        self.api_key = gemini_api_key or os.getenv("GOOGLE_API_KEY")
        self._llm_gateway = None
        self.use_mock = use_mock
        
        if self.use_mock:
            logger.info("ECGAnalyzer running in mock mode")
    async def initialize(self):
        """Initialize the Gemini model via Gateway."""
        if not self.use_mock:
            try:
                from core.llm_gateway import get_llm_gateway
                self._llm_gateway = get_llm_gateway()
                
                if self._llm_gateway.gemini_available:
                    logger.info("ECG Analyzer initialized with Gemini via Gateway")
                else:
                    logger.warning("Gemini not available via Gateway, falling back to mock")
                    self.use_mock = True
            except Exception as e:
                logger.warning(f"Failed to initialize Gateway for ECG: {e}")
                self.use_mock = True
    async def analyze(
        self,
        image: Union[bytes, str, Path],
        patient_context: Optional[Dict] = None,
    ) -> ECGAnalysis:
        """
        Analyze ECG image.
        
        Args:
            image: ECG image (bytes, path, or base64)
            patient_context: Optional patient details (age, symptoms, etc.)
            
        Returns:
            ECGAnalysis result
        """
        image_bytes = self._get_image_bytes(image)
        
        if self.use_mock:
            return self._mock_analysis(patient_context)
        
        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(patient_context)
            
            # Call Gemini Vision via Gateway
            # Note: Gateway handles the disclaimer via content_type="medical"
            response_text = await self._llm_gateway.generate(
                prompt=prompt,
                images=[{"mime_type": "image/jpeg", "data": image_bytes}],
                content_type="medical"
            )
            
            # Parse response
            return self._parse_gemini_response(response_text)
            
        except Exception as e:
            logger.error(f"ECG analysis error: {e}")
            return self._mock_analysis(patient_context)
