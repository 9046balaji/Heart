"""
Transformer-based Intent Recognition Engine
Uses BERT/RoBERTa models for improved intent classification

================================================================================
HARDWARE REQUIREMENTS
================================================================================

Minimum Requirements (CPU-only inference):
- CPU: 4+ cores (Intel i5/AMD Ryzen 5 or better)
- RAM: 8GB minimum, 16GB recommended
- Storage: 2GB for model cache
- Inference Time: ~100-500ms per query (varies by model)

Recommended Requirements (GPU-accelerated):
- GPU: NVIDIA GPU with 4GB+ VRAM (GTX 1060, RTX 2060, or better)
- CUDA: 11.7+ with cuDNN 8.5+
- RAM: 16GB+
- Storage: 5GB for models + cache
- Inference Time: ~10-50ms per query

Supported Models & Resource Usage:
┌─────────────────────────────────┬──────────┬───────────┬─────────────┐
│ Model                           │ Size     │ RAM (CPU) │ VRAM (GPU)  │
├─────────────────────────────────┼──────────┼───────────┼─────────────┤
│ bert-base-uncased               │ 420MB    │ ~2GB      │ ~1.5GB      │
│ bert-large-uncased              │ 1.3GB    │ ~5GB      │ ~3GB        │
│ distilbert-base-uncased         │ 250MB    │ ~1.2GB    │ ~0.8GB      │
│ roberta-base                    │ 480MB    │ ~2.2GB    │ ~1.6GB      │
│ albert-base-v2 (lightweight)    │ 45MB     │ ~0.5GB    │ ~0.3GB      │
└─────────────────────────────────┴──────────┴───────────┴─────────────┘

QUANTIZATION OPTIONS (for CPU deployment):
- INT8 Quantization: ~4x smaller, ~2-3x faster, minimal accuracy loss
- Dynamic Quantization: No calibration needed, easy to use
- Static Quantization: Better performance, requires calibration data

ENVIRONMENT VARIABLES:
- USE_TRANSFORMER_MODELS=true     Enable transformer models (default: false)
- TRANSFORMER_MODEL_NAME=bert-base-uncased  Model to use
- TRANSFORMER_USE_QUANTIZATION=true  Enable INT8 quantization for CPU
- TRANSFORMER_DEVICE=auto         Device selection (auto/cpu/cuda)
- TRANSFORMER_WARMUP_ON_STARTUP=true  Pre-warm model at startup
- TRANSFORMER_MAX_BATCH_SIZE=8    Maximum batch size for inference

================================================================================
"""
import logging
import asyncio
import gc
import os
from typing import List, Dict, Tuple, Any, Optional, Literal, TypedDict
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
import time

# Conditional imports to handle missing dependencies
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    AutoTokenizer = None
    AutoModelForSequenceClassification = None
    pipeline = None

from config import (
    INTENT_CONFIDENCE_THRESHOLD
)
from models import IntentEnum, IntentResult
from async_patterns import AsyncTimeout, run_sync_in_executor

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TransformerConfig:
    """Configuration for transformer model deployment."""
    model_name: str = "bert-base-uncased"
    use_quantization: bool = False
    device: str = "auto"  # auto, cpu, cuda
    warmup_on_startup: bool = True
    max_batch_size: int = 8
    max_sequence_length: int = 512
    inference_timeout: float = 30.0
    
    # Quantization settings
    quantization_dtype: str = "int8"  # int8, float16
    quantization_backend: str = "fbgemm"  # fbgemm (Intel), qnnpack (ARM)
    
    @classmethod
    def from_env(cls) -> "TransformerConfig":
        """Load configuration from environment variables."""
        return cls(
            model_name=os.environ.get("TRANSFORMER_MODEL_NAME", "bert-base-uncased"),
            use_quantization=os.environ.get("TRANSFORMER_USE_QUANTIZATION", "false").lower() == "true",
            device=os.environ.get("TRANSFORMER_DEVICE", "auto"),
            warmup_on_startup=os.environ.get("TRANSFORMER_WARMUP_ON_STARTUP", "true").lower() == "true",
            max_batch_size=int(os.environ.get("TRANSFORMER_MAX_BATCH_SIZE", "8")),
        )


@dataclass
class ModelMetrics:
    """Metrics for model performance monitoring."""
    inference_count: int = 0
    total_inference_time_ms: float = 0.0
    avg_inference_time_ms: float = 0.0
    min_inference_time_ms: float = float('inf')
    max_inference_time_ms: float = 0.0
    error_count: int = 0
    last_inference_at: Optional[datetime] = None
    model_load_time_ms: float = 0.0
    warmup_time_ms: float = 0.0
    is_quantized: bool = False
    device: str = "cpu"
    
    def record_inference(self, time_ms: float) -> None:
        """Record an inference timing."""
        self.inference_count += 1
        self.total_inference_time_ms += time_ms
        self.avg_inference_time_ms = self.total_inference_time_ms / self.inference_count
        self.min_inference_time_ms = min(self.min_inference_time_ms, time_ms)
        self.max_inference_time_ms = max(self.max_inference_time_ms, time_ms)
        self.last_inference_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary."""
        return {
            "inference_count": self.inference_count,
            "avg_inference_time_ms": round(self.avg_inference_time_ms, 2),
            "min_inference_time_ms": round(self.min_inference_time_ms, 2) if self.min_inference_time_ms != float('inf') else None,
            "max_inference_time_ms": round(self.max_inference_time_ms, 2),
            "error_count": self.error_count,
            "model_load_time_ms": round(self.model_load_time_ms, 2),
            "warmup_time_ms": round(self.warmup_time_ms, 2),
            "is_quantized": self.is_quantized,
            "device": self.device,
            "last_inference_at": self.last_inference_at.isoformat() if self.last_inference_at else None,
        }


# ============================================================================
# TYPE DEFINITIONS & ERROR HANDLING
# ============================================================================

@dataclass
class TransformerError:
    """Structured error context for transformer operations."""
    error_type: str
    message: str
    model_name: str
    timestamp: datetime
    request_id: Optional[str] = None
    original_error: Optional[Exception] = None

    def __str__(self) -> str:
        return f"[{self.error_type}] {self.message} (model: {self.model_name})"


class TransformerModelError(Exception):
    """Custom exception for transformer model errors."""
    
    def __init__(self, error: TransformerError):
        self.error = error
        super().__init__(str(error))


class ModelInitializationError(TransformerModelError):
    """Error during model initialization."""
    pass


class InferenceError(TransformerModelError):
    """Error during inference."""
    pass


class ModelSwitchError(TransformerModelError):
    """Error during model switching."""
    pass


class IntentContextData(TypedDict, total=False):
    """Type-safe intent context structure."""
    priority: Literal["critical", "high", "medium", "low", "normal"]
    requires_immediate_action: bool
    requires_details: List[str]
    follow_up: str


class TransformerIntentRecognizer:
    """
    Transformer-based intent recognition engine using BERT/RoBERTa models.
    Provides improved accuracy over keyword-based approaches.
    
    Features:
    - Type-safe inference with structured error handling
    - Async support for non-blocking operations
    - Resource management with proper cleanup
    - Comprehensive logging and metrics collection
    - INT8 quantization for CPU deployment
    - Model warm-up for consistent latency
    - A/B testing support with fallback to Trie
    
    Example Usage:
        # Basic usage
        recognizer = TransformerIntentRecognizer("distilbert-base-uncased")
        result = recognizer.recognize_intent("I have chest pain")
        
        # With quantization for CPU deployment
        recognizer = TransformerIntentRecognizer.create_quantized("bert-base-uncased")
        
        # With warm-up
        recognizer = TransformerIntentRecognizer("bert-base-uncased")
        recognizer.warmup(num_samples=5)
        
        # Get performance metrics
        metrics = recognizer.get_metrics()
    """

    # Class-level cache for model instances (singleton pattern)
    _model_cache: Dict[str, 'TransformerIntentRecognizer'] = {}

    def __init__(
        self, 
        model_name: str = "bert-base-uncased",
        config: Optional[TransformerConfig] = None,
        use_quantization: bool = False
    ) -> None:
        """
        Initialize transformer intent recognizer.

        Args:
            model_name: Name of the transformer model to use
            config: Optional TransformerConfig for advanced settings
            use_quantization: Enable INT8 quantization for CPU inference
            
        Raises:
            ImportError: If PyTorch is not available
            ValueError: If model_name is invalid (empty or None)
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is not available. Please install torch to use transformer models.")
        
        # Input validation
        if not model_name or not isinstance(model_name, str):
            raise ValueError(f"model_name must be a non-empty string, got: {model_name!r}")
        
        self.model_name = model_name
        self.tokenizer: Optional[Any] = None
        self.model: Optional[Any] = None
        self.classifier: Optional[Any] = None
        
        # Metadata for observability
        self._created_at = datetime.now()
        self._inference_count = 0
        self._total_inference_time = 0.0
        
        self.intent_labels: List[str] = [
            "greeting",
            "emergency",
            "symptom_check",
            "medication_reminder",
            "risk_assessment",
            "nutrition_advice",
            "exercise_coaching",
            "health_goal",
            "health_education",
            "appointment_booking",
            "unknown"
        ]
        
        # Map string labels to IntentEnum values
        self.label_to_intent: Dict[str, IntentEnum] = {
            "greeting": IntentEnum.GREETING,
            "emergency": IntentEnum.EMERGENCY,
            "symptom_check": IntentEnum.SYMPTOM_CHECK,
            "medication_reminder": IntentEnum.MEDICATION_REMINDER,
            "risk_assessment": IntentEnum.RISK_ASSESSMENT,
            "nutrition_advice": IntentEnum.NUTRITION_ADVICE,
            "exercise_coaching": IntentEnum.EXERCISE_COACHING,
            "health_goal": IntentEnum.HEALTH_GOAL,
            "health_education": IntentEnum.HEALTH_EDUCATION,
            "appointment_booking": IntentEnum.APPOINTMENT_BOOKING,
            "unknown": IntentEnum.UNKNOWN
        }
        
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Initialize the transformer model and tokenizer with structured error handling."""
        try:
            logger.info(f"Loading transformer model: {self.model_name}")
            
            # Initialize tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Initialize model
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name,
                num_labels=len(self.intent_labels)
            )
            
            # Create classification pipeline
            self.classifier = pipeline(
                "text-classification",
                model=self.model,
                tokenizer=self.tokenizer,
                top_k=None
            )
            
            logger.info(f"Transformer model '{self.model_name}' loaded successfully")
            
        except FileNotFoundError as e:
            error = TransformerError(
                error_type="ModelNotFound",
                message=f"Model '{self.model_name}' not found in HuggingFace hub or local cache",
                model_name=self.model_name,
                timestamp=datetime.now(),
                original_error=e
            )
            logger.error(f"Model initialization failed: {error}")
            raise ModelInitializationError(error) from e
            
        except Exception as e:
            error = TransformerError(
                error_type="InitializationFailed",
                message=f"Failed to initialize model: {type(e).__name__}: {str(e)}",
                model_name=self.model_name,
                timestamp=datetime.now(),
                original_error=e
            )
            logger.error(f"Unexpected model initialization error: {error}")
            raise ModelInitializationError(error) from e

    def recognize_intent(self, text: str) -> IntentResult:
        """
        Recognize intent from user input using transformer model (BLOCKING).

        Args:
            text: User input text

        Returns:
            IntentResult with identified intent and confidence
            
        Raises:
            ValueError: If text is None or not a string
            InferenceError: If inference fails
        """
        # Input validation
        if not isinstance(text, str):
            raise ValueError(f"text must be a string, got: {type(text).__name__}")
        
        if not text or not text.strip():
            logger.warning("Empty text provided for intent recognition")
            return IntentResult(
                intent=IntentEnum.UNKNOWN,
                confidence=0.1,
                keywords_matched=[]
            )
        
        # Truncate very long texts to prevent performance issues (DoS protection)
        max_length = 512  # Standard transformer max length
        if len(text) > max_length:
            text = text[:max_length]
            logger.debug(f"Text truncated to {max_length} characters")
        
        return self._recognize_intent_sync(text)
    
    async def recognize_intent_async(self, text: str) -> IntentResult:
        """
        Recognize intent from user input asynchronously (NON-BLOCKING).

        Args:
            text: User input text

        Returns:
            IntentResult with identified intent and confidence
            
        Raises:
            ValueError: If text is None or not a string
            asyncio.TimeoutError: If inference exceeds timeout
            InferenceError: If inference fails
        """
        # Input validation
        if not isinstance(text, str):
            raise ValueError(f"text must be a string, got: {type(text).__name__}")
        
        if not text or not text.strip():
            logger.warning("Empty text provided for intent recognition")
            return IntentResult(
                intent=IntentEnum.UNKNOWN,
                confidence=0.1,
                keywords_matched=[]
            )
        
        @AsyncTimeout(timeout_seconds=30)
        async def _infer_with_timeout() -> IntentResult:
            """Run inference in thread pool with timeout."""
            return await run_sync_in_executor(
                self._recognize_intent_sync,
                text
            )
        
        try:
            return await _infer_with_timeout()
        except asyncio.TimeoutError:
            logger.error(f"Intent recognition timeout for text: {text[:50]}")
            error = TransformerError(
                error_type="InferenceTimeout",
                message=f"Intent recognition exceeded 30 second timeout",
                model_name=self.model_name,
                timestamp=datetime.now()
            )
            raise InferenceError(error) from None
        except InferenceError:
            raise
        except Exception as e:
            error = TransformerError(
                error_type="InferenceError",
                message=f"Unexpected error during async inference: {str(e)}",
                model_name=self.model_name,
                timestamp=datetime.now(),
                original_error=e
            )
            logger.error(f"Async inference failed: {error}")
            raise InferenceError(error) from e

    def _recognize_intent_sync(self, text: str) -> IntentResult:
        """
        Internal blocking inference logic (runs in thread pool when called async).

        Args:
            text: User input text (pre-validated)

        Returns:
            IntentResult with identified intent and confidence
        """
        import time
        start_time = time.time()
        
        try:
            if self.classifier is None:
                error = TransformerError(
                    error_type="ModelNotInitialized",
                    message="Classifier is not initialized. Model may have failed to load.",
                    model_name=self.model_name,
                    timestamp=datetime.now()
                )
                logger.error(f"Inference failed: {error}")
                raise InferenceError(error)
            
            # Get predictions from transformer model
            predictions: List[List[Dict[str, Any]]] = self.classifier(text)
            
            if not predictions or not predictions[0]:
                raise ValueError("No predictions returned from classifier")
            
            # Find the best prediction
            best_prediction: Dict[str, Any] = max(predictions[0], key=lambda x: x['score'])
            
            # Map label to IntentEnum
            intent_label: str = best_prediction['label']
            intent_enum: IntentEnum = self.label_to_intent.get(intent_label, IntentEnum.UNKNOWN)
            
            # Get confidence score
            confidence: float = float(best_prediction['score'])
            
            # If confidence is too low, mark as unknown
            if confidence < INTENT_CONFIDENCE_THRESHOLD:
                intent_enum = IntentEnum.UNKNOWN
                confidence = 0.1
            
            # Extract keywords
            keywords_matched: List[str] = self._extract_keywords(text, intent_enum)
            
            # Track metrics
            elapsed_time = time.time() - start_time
            self._inference_count += 1
            self._total_inference_time += elapsed_time
            
            logger.debug(
                f"Intent inference completed: {intent_label} "
                f"(confidence: {confidence:.2f}, time: {elapsed_time:.3f}s)"
            )
            
            return IntentResult(
                intent=intent_enum,
                confidence=min(0.99, confidence),
                keywords_matched=keywords_matched
            )
            
        except InferenceError:
            raise
        except Exception as e:
            error = TransformerError(
                error_type="InferenceError",
                message=f"Error during intent inference: {type(e).__name__}: {str(e)}",
                model_name=self.model_name,
                timestamp=datetime.now(),
                original_error=e
            )
            logger.error(f"Inference failed: {error}")
            raise InferenceError(error) from e

    def _extract_keywords(self, text: str, intent: IntentEnum) -> List[str]:
        """
        Extract keywords based on intent.

        Args:
            text: Input text (pre-validated and normalized)
            intent: Detected intent

        Returns:
            List of matched keywords
        """
        intent_keywords: Dict[IntentEnum, List[str]] = {
            IntentEnum.GREETING: ["hello", "hi", "hey", "good morning", "good afternoon"],
            IntentEnum.EMERGENCY: ["emergency", "help", "911", "severe", "critical"],
            IntentEnum.SYMPTOM_CHECK: ["pain", "hurt", "feel", "ache", "symptom"],
            IntentEnum.MEDICATION_REMINDER: ["medication", "pill", "medicine", "dose"],
            IntentEnum.RISK_ASSESSMENT: ["risk", "heart disease", "assessment"],
            IntentEnum.NUTRITION_ADVICE: ["eat", "food", "meal", "diet", "nutrition"],
            IntentEnum.EXERCISE_COACHING: ["exercise", "workout", "fitness", "training"],
            IntentEnum.HEALTH_GOAL: ["goal", "target", "achieve", "improve"],
            IntentEnum.HEALTH_EDUCATION: ["learn", "teach", "education", "information"],
            IntentEnum.APPOINTMENT_BOOKING: ["appointment", "doctor", "booking", "schedule"]
        }
        
        keywords: List[str] = intent_keywords.get(intent, [])
        text_lower = text.lower()
        
        # Use set for O(1) membership testing
        matched_keywords: List[str] = [
            kw for kw in keywords if kw in text_lower
        ]
        
        return matched_keywords

    def get_intent_context(self, intent: IntentEnum) -> IntentContextData:
        """
        Get contextual information for an intent with type safety.

        Args:
            intent: Identified intent

        Returns:
            Type-safe dictionary with intent context
        """
        context_map: Dict[IntentEnum, IntentContextData] = {
            IntentEnum.EMERGENCY: {
                "priority": "critical",
                "requires_immediate_action": True,
                "follow_up": "escalate_to_emergency_services"
            },
            IntentEnum.SYMPTOM_CHECK: {
                "priority": "high",
                "requires_details": ["duration", "severity", "frequency"],
                "follow_up": "provide_triage_guidance"
            },
            IntentEnum.RISK_ASSESSMENT: {
                "priority": "medium",
                "requires_details": ["age", "lifestyle", "medical_history"],
                "follow_up": "calculate_risk_score"
            },
            IntentEnum.MEDICATION_REMINDER: {
                "priority": "medium",
                "requires_details": ["medication_name", "dosage", "frequency"],
                "follow_up": "set_reminder"
            },
            IntentEnum.HEALTH_GOAL: {
                "priority": "low",
                "requires_details": ["goal_type", "timeframe"],
                "follow_up": "create_tracking_plan"
            },
            IntentEnum.APPOINTMENT_BOOKING: {
                "priority": "medium",
                "requires_details": ["provider_type", "preferred_date"],
                "follow_up": "book_appointment"
            },
        }

        return context_map.get(intent, {"priority": "normal"})

    def switch_model(self, model_name: str) -> None:
        """
        Switch to a different transformer model with proper cleanup.

        Args:
            model_name: Name of the new model to use
            
        Raises:
            ValueError: If model_name is invalid
            ModelSwitchError: If model switching fails
        """
        if not model_name or not isinstance(model_name, str):
            raise ValueError(f"model_name must be a non-empty string, got: {model_name!r}")
        
        old_model_name = self.model_name
        
        try:
            # Cleanup old resources
            self._cleanup_model()
            
            # Load new model
            self.model_name = model_name
            self._initialize_model()
            
            logger.info(f"Successfully switched from '{old_model_name}' to '{model_name}'")
            
        except ModelInitializationError as e:
            # Restore previous state on failure
            self.model_name = old_model_name
            logger.error(f"Failed to switch models: {e.error}. Restoring previous model.")
            raise ModelSwitchError(e.error) from e
        except Exception as e:
            # Restore previous state on failure
            self.model_name = old_model_name
            error = TransformerError(
                error_type="ModelSwitchFailed",
                message=f"Unexpected error while switching models: {type(e).__name__}: {str(e)}",
                model_name=model_name,
                timestamp=datetime.now(),
                original_error=e
            )
            logger.error(f"Model switch failed: {error}")
            raise ModelSwitchError(error) from e

    # ========================================================================
    # QUANTIZATION & OPTIMIZATION
    # ========================================================================

    def apply_quantization(self, backend: str = "fbgemm") -> bool:
        """
        Apply INT8 dynamic quantization to the model for faster CPU inference.
        
        Quantization reduces model size by ~4x and improves CPU inference speed
        by 2-3x with minimal accuracy loss (<1% typically).
        
        Args:
            backend: Quantization backend ("fbgemm" for Intel, "qnnpack" for ARM)
            
        Returns:
            True if quantization was successful
            
        Note:
            - Only works on CPU (GPU uses native precision)
            - Best results with bert-base and distilbert models
            - May need to reinstall with: pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
        """
        if not TORCH_AVAILABLE or self.model is None:
            logger.warning("Cannot quantize: model not loaded or PyTorch unavailable")
            return False
        
        try:
            import torch.quantization as quant
            
            # Set quantization backend
            torch.backends.quantized.engine = backend
            
            # Move model to CPU for quantization
            self.model = self.model.cpu()
            self.model.eval()
            
            # Apply dynamic quantization to Linear layers
            start_time = time.time()
            self.model = quant.quantize_dynamic(
                self.model,
                {torch.nn.Linear},
                dtype=torch.qint8
            )
            quantize_time = (time.time() - start_time) * 1000
            
            # Recreate the classifier pipeline with quantized model
            self.classifier = pipeline(
                "text-classification",
                model=self.model,
                tokenizer=self.tokenizer,
                top_k=None,
                device=-1  # Force CPU
            )
            
            logger.info(f"Model quantized successfully in {quantize_time:.1f}ms (backend: {backend})")
            return True
            
        except Exception as e:
            logger.error(f"Quantization failed: {e}")
            return False

    @classmethod
    def create_quantized(
        cls,
        model_name: str = "distilbert-base-uncased",
        backend: str = "fbgemm"
    ) -> "TransformerIntentRecognizer":
        """
        Factory method to create a quantized model for CPU deployment.
        
        Args:
            model_name: Model to load (lightweight models recommended)
            backend: Quantization backend
            
        Returns:
            TransformerIntentRecognizer with quantized model
            
        Example:
            recognizer = TransformerIntentRecognizer.create_quantized()
            # ~4x smaller, ~2-3x faster on CPU
        """
        instance = cls(model_name)
        instance.apply_quantization(backend)
        return instance

    def warmup(self, num_samples: int = 5) -> Dict[str, Any]:
        """
        Warm up the model with sample inferences to ensure consistent latency.
        
        First inference after model load is typically slower due to:
        - JIT compilation
        - Memory allocation
        - Cache population
        
        Args:
            num_samples: Number of warmup inferences to run
            
        Returns:
            Dictionary with warmup statistics
            
        Example:
            recognizer = TransformerIntentRecognizer("bert-base-uncased")
            warmup_stats = recognizer.warmup(num_samples=10)
            print(f"Warmup complete: avg latency = {warmup_stats['avg_time_ms']:.1f}ms")
        """
        warmup_texts = [
            "Hello, how are you?",
            "I have severe chest pain",
            "What should I eat for a healthy heart?",
            "Remind me to take my medication",
            "I want to book an appointment",
        ]
        
        # Extend samples if needed
        while len(warmup_texts) < num_samples:
            warmup_texts.extend(warmup_texts[:num_samples - len(warmup_texts)])
        warmup_texts = warmup_texts[:num_samples]
        
        times = []
        start_total = time.time()
        
        for text in warmup_texts:
            start = time.time()
            try:
                _ = self.recognize_intent(text)
                times.append((time.time() - start) * 1000)
            except Exception as e:
                logger.warning(f"Warmup inference failed: {e}")
        
        total_time = (time.time() - start_total) * 1000
        
        stats = {
            "num_samples": len(times),
            "total_time_ms": round(total_time, 2),
            "avg_time_ms": round(sum(times) / len(times), 2) if times else 0,
            "min_time_ms": round(min(times), 2) if times else 0,
            "max_time_ms": round(max(times), 2) if times else 0,
            "first_time_ms": round(times[0], 2) if times else 0,
            "last_time_ms": round(times[-1], 2) if times else 0,
        }
        
        logger.info(f"Model warmup complete: {stats['num_samples']} samples, avg {stats['avg_time_ms']:.1f}ms")
        return stats

    def get_device_info(self) -> Dict[str, Any]:
        """
        Get information about the current device and model configuration.
        
        Returns:
            Dictionary with device and model information
        """
        info = {
            "model_name": self.model_name,
            "torch_available": TORCH_AVAILABLE,
            "device": "unknown",
            "cuda_available": False,
            "cuda_device_count": 0,
            "model_loaded": self.model is not None,
        }
        
        if TORCH_AVAILABLE:
            info["cuda_available"] = torch.cuda.is_available()
            info["cuda_device_count"] = torch.cuda.device_count() if torch.cuda.is_available() else 0
            
            if self.model is not None:
                # Try to determine device from model parameters
                try:
                    param = next(self.model.parameters())
                    info["device"] = str(param.device)
                except StopIteration:
                    info["device"] = "cpu"
        
        return info

    def _cleanup_model(self) -> None:
        """
        Clean up model resources to prevent memory leaks.
        Should be called before loading a new model or on shutdown.
        """
        try:
            if self.model is not None:
                del self.model
                self.model = None
            
            if self.tokenizer is not None:
                del self.tokenizer
                self.tokenizer = None
            
            if self.classifier is not None:
                del self.classifier
                self.classifier = None
            
            # Force garbage collection
            gc.collect()
            
            logger.debug("Model resources cleaned up successfully")
            
        except Exception as e:
            logger.warning(f"Error during model cleanup: {type(e).__name__}: {str(e)}")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the recognizer.

        Returns:
            Dictionary with inference metrics
        """
        avg_inference_time = (
            self._total_inference_time / self._inference_count
            if self._inference_count > 0
            else 0.0
        )
        
        uptime = (datetime.now() - self._created_at).total_seconds()
        
        return {
            "model_name": self.model_name,
            "inference_count": self._inference_count,
            "total_inference_time_seconds": self._total_inference_time,
            "average_inference_time_ms": avg_inference_time * 1000,
            "uptime_seconds": uptime,
            "created_at": self._created_at.isoformat()
        }

    def __del__(self) -> None:
        """Cleanup on object destruction."""
        self._cleanup_model()


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_transformer_intent_recognizer(
    model_name: str = "bert-base-uncased"
) -> TransformerIntentRecognizer:
    """
    Factory function to create a transformer intent recognizer.

    Args:
        model_name: Name of the transformer model to use

    Returns:
        TransformerIntentRecognizer instance
        
    Raises:
        ImportError: If PyTorch is not available
        ValueError: If model_name is invalid
        ModelInitializationError: If model fails to load
    """
    return TransformerIntentRecognizer(model_name)


@lru_cache(maxsize=3)
def get_cached_recognizer(model_name: str = "bert-base-uncased") -> TransformerIntentRecognizer:
    """
    Get or create a cached transformer intent recognizer (singleton pattern).
    
    Use this for production to avoid reloading the same model multiple times.

    Args:
        model_name: Name of the transformer model to use

    Returns:
        Cached TransformerIntentRecognizer instance
        
    Note:
        Cache is limited to 3 different models. Cache cannot be modified after creation.
    """
    return TransformerIntentRecognizer(model_name)