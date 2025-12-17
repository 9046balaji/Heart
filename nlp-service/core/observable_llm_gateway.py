"""
Observable LLM Gateway with Langfuse Integration.

This module enhances the LLM gateway with Langfuse observability
for detailed tracing and monitoring of LLM calls.

Features:
- Detailed tracing of LLM calls
- Performance monitoring
- Cost tracking
- Debugging capabilities
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Langfuse imports
from langfuse import Langfuse
from langfuse.decorators import observe

logger = logging.getLogger(__name__)


class ObservableLLMGateway:
    """
    LLM Gateway with Langfuse observability integration.
    
    Features:
    - Trace LLM calls with inputs/outputs
    - Monitor performance and costs
    - Debug generation issues
    """
    
    def __init__(self):
        """Initialize Observable LLM Gateway with Langfuse."""
        # Initialize Langfuse client
        self.langfuse = None
        try:
            self.langfuse = Langfuse(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                host=os.getenv("LANGFUSE_HOST", "http://localhost:3000")
            )
            logger.info("✅ Langfuse client initialized")
        except Exception as e:
            logger.warning(f"Langfuse initialization failed: {e}")
        
        logger.info("✅ ObservableLLMGateway initialized")
    
    @observe()
    async def generate(self, prompt: str, content_type: str = "general", user_id: Optional[str] = None) -> str:
        """
        Generate response with Langfuse tracing.
        
        Args:
            prompt: The prompt to send to the LLM
            content_type: "medical", "nutrition", or "general"
            user_id: Optional user ID for tracing
            
        Returns:
            Generated response
        """
        logger.info(f"Generating response with tracing: type={content_type}")
        
        # Create trace if Langfuse is available
        trace = None
        if self.langfuse:
            try:
                trace = self.langfuse.trace(
                    name="llm-generation",
                    user_id=user_id or "anonymous",
                    metadata={"content_type": content_type, "timestamp": datetime.now().isoformat()}
                )
                
                # Log input
                trace.generation(
                    name="prompt",
                    input=prompt,
                    model=content_type
                )
            except Exception as e:
                logger.warning(f"Failed to create Langfuse trace: {e}")
        
        try:
            # Import and use existing LLM gateway for generation
            # This is a simplified implementation - in practice, you would integrate with your existing LLM logic
            import asyncio
            import time
            
            # Simulate LLM generation delay
            await asyncio.sleep(0.1)
            
            # Simple response generation based on content type
            responses = {
                "medical": f"Based on your medical query about '{prompt[:20]}...', here is professional medical information. Please consult with a healthcare provider for personalized advice.",
                "nutrition": f"Regarding your nutrition question about '{prompt[:20]}...', a balanced diet with fruits and vegetables is recommended for heart health.",
                "general": f"Thank you for your question about '{prompt[:20]}...'. Here's helpful information."
            }
            
            response = responses.get(content_type, responses["general"])
            
            # Log output if trace exists
            if trace:
                try:
                    trace.generation(
                        name="response",
                        output=response,
                        model=content_type,
                        usage={
                            "input_tokens": len(prompt.split()),
                            "output_tokens": len(response.split())
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to log output to Langfuse: {e}")
            
            return response
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            
            # Log error if trace exists
            if trace:
                try:
                    trace.generation(
                        name="error",
                        status_message=str(e),
                        level="ERROR"
                    )
                except Exception as trace_error:
                    logger.warning(f"Failed to log error to Langfuse: {trace_error}")
            
            raise RuntimeError(f"LLM generation failed: {e}")
    
    def get_trace_url(self, trace_id: str) -> Optional[str]:
        """
        Get URL for a specific trace.
        
        Args:
            trace_id: Trace ID
            
        Returns:
            URL to view trace in Langfuse UI
        """
        if self.langfuse:
            try:
                return f"{self.langfuse.client.config.base_url}/trace/{trace_id}"
            except Exception as e:
                logger.warning(f"Failed to generate trace URL: {e}")
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get gateway status."""
        return {
            "langfuse_enabled": self.langfuse is not None,
            "timestamp": datetime.now().isoformat()
        }


# Factory function
def create_observable_llm_gateway() -> ObservableLLMGateway:
    """
    Factory function to create an ObservableLLMGateway.
    
    Returns:
        Configured ObservableLLMGateway
    """
    return ObservableLLMGateway()