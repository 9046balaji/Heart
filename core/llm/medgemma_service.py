import requests
import logging

logger = logging.getLogger(__name__)

class MedGemmaService:
    """
    Client for the local MedGemma-4B GGUF server.
    
    The 'Mouth' of the AI.
    Connects to a local llama.cpp server running MedGemma-4B-GGUF model
    to generate natural language answers based on medical context from RAG.
    
    This approach:
    - Eliminates GPU memory constraints
    - Allows model to run on any GPU efficiently
    - Separates LLM serving from main application
    
    Prerequisites:
    - Run: llama-server -m medgemma-4b.gguf --port 8080
    """
    _instance = None
    SERVER_URL = "http://127.0.0.1:8080/completion"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MedGemmaService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Check connection to MedGemma server"""
        try:
            requests.get("http://127.0.0.1:8090/health", timeout=2)
            logger.info("✅ Connected to MedGemma-4B (Local GPU Server)")
        except:
            logger.error("❌ MedGemma Server OFFLINE. Run llama-server.exe first!")

    @classmethod
    def get_instance(cls):
        return cls()

    def generate_response(self, query: str, context: str) -> str:
        """
        Generates a medical answer using the retrieved context.
        
        Connects to local MedGemma server to generate a response.
        
        Args:
            query: The user's medical question
            context: The retrieved medical context from RAG
            
        Returns:
            A natural language response from the LLM, or error message if server unavailable
        """
        # Prompt specifically formatted for Gemma
        prompt = f"""<start_of_turn>user
You are HeartGuard, a medical AI assistant.
Answer based ONLY on the context provided.

CONTEXT:
{context}

QUESTION:
{query}<end_of_turn>
<start_of_turn>model
"""
        
        payload = {
            "prompt": prompt,
            "temperature": 0.2,
            "n_predict": 512,
            "stop": ["<end_of_turn>"],
            "cache_prompt": True
        }

        try:
            resp = requests.post(self.SERVER_URL, json=payload)
            if resp.status_code == 200:
                return resp.json().get("content", "").strip()
        except Exception as e:
            return f"Error connecting to AI Brain: {e}"
        return "Error generating response."
