"""
Token Budget Manager for RAG Pipeline.

Manage token allocation across prompt components to prevent exceeding
LLM context windows and optimize cost/performance.
"""

from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Try to import tiktoken for token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available. Using character-based approximation.")


class TokenBudgetManager:
    """Manage token allocation across prompt components."""
    
    def __init__(
        self,
        max_tokens: int = 4096,
        response_reserve: int = 1024,
        system_prompt_tokens: int = 500
    ):
        """
        Initialize token budget manager.
        
        Args:
            max_tokens: Maximum tokens for the entire prompt
            response_reserve: Tokens to reserve for the LLM response
            system_prompt_tokens: Tokens used by the system prompt
        """
        self.max_tokens = max_tokens
        self.response_reserve = response_reserve
        self.system_prompt_tokens = system_prompt_tokens
        
        # Initialize tokenizer if available
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoder = tiktoken.encoding_for_model("gpt-4")  # Compatible tokenizer
            except Exception as e:
                logger.warning(f"Failed to initialize tokenizer: {e}")
                self.encoder = None
        else:
            self.encoder = None
    
    def allocate(
        self,
        query: str,
        medical_context: str,
        memories: str,
        history: str
    ) -> Dict[str, str]:
        """
        Allocate token budget across components.
        
        Priority:
        1. Query (must include fully)
        2. Medical context (high priority for accuracy)
        3. Memories (medium priority)
        4. History (lowest priority, truncate first)
        
        Args:
            query: User query
            medical_context: Medical knowledge context
            memories: User memory context
            history: Conversation history
            
        Returns:
            Dict with truncated components according to budget
        """
        # Calculate available tokens
        available = (
            self.max_tokens - 
            self.response_reserve - 
            self.system_prompt_tokens
        )
        
        # Count tokens for query
        query_tokens = self._count_tokens(query)
        available -= query_tokens
        
        # Allocate remaining tokens: 50% medical, 30% memories, 20% history
        allocations = {
            "medical": int(available * 0.5),
            "memories": int(available * 0.3),
            "history": int(available * 0.2)
        }
        
        return {
            "query": query,
            "medical_context": self._truncate(medical_context, allocations["medical"]),
            "memories": self._truncate(memories, allocations["memories"]),
            "history": self._truncate(history, allocations["history"])
        }
    
    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count
            
        Returns:
            Number of tokens
        """
        if self.encoder and text:
            try:
                return len(self.encoder.encode(text))
            except Exception as e:
                logger.warning(f"Token counting failed: {e}")
        
        # Fallback to character approximation (4 chars per token)
        return len(text) // 4 if text else 0
    
    def _truncate(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
            
        Returns:
            Truncated text
        """
        if not text:
            return ""
            
        # If we have a tokenizer, use it for precise truncation
        if self.encoder:
            try:
                tokens = self.encoder.encode(text)
                if len(tokens) <= max_tokens:
                    return text
                return self.encoder.decode(tokens[:max_tokens]) + "..."
            except Exception as e:
                logger.warning(f"Token-based truncation failed: {e}")
        
        # Fallback to character-based truncation
        max_chars = max_tokens * 4  # Approximate
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."