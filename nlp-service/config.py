"""
Configuration for NLP Microservice
"""

import os
from typing import List, Union
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


# Helper for Ollama Host
def _get_ollama_host():
    """
    Determine appropriate Ollama host based on deployment context.
    """
    # If explicitly set in environment, use it (highest priority)
    if os.getenv("OLLAMA_HOST"):
        return os.getenv("OLLAMA_HOST")

    # Check if running in Docker (standard Docker env variable)
    if os.path.exists("/.dockerenv"):
        # Running inside a container - use host.docker.internal
        default_host = "http://host.docker.internal:11434"
        return os.getenv("OLLAMA_HOST_DOCKER", default_host)

    # Not in Docker - assume localhost
    return "http://localhost:11434"


class Settings(BaseSettings):
    """
    Application Settings using Pydantic
    """

    # Service Configuration
    SERVICE_NAME: str = "HeartGuard NLP Service"
    SERVICE_VERSION: str = "1.0.0"
    SERVICE_PORT: int = Field(default=5001, alias="NLP_SERVICE_PORT")
    SERVICE_HOST: str = Field(default="127.0.0.1", alias="NLP_SERVICE_HOST")

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./nlp_cache.db"

    # Security Configuration
    SECRET_KEY: str = Field(default="default-secret-key", env="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """
        Validate SECRET_KEY to prevent insecure defaults in production.

        Security Requirements:
        - Must not be the default value in production or staging
        - Must be at least 32 characters long
        - Should be cryptographically random

        Raises:
            ValueError: If SECRET_KEY is insecure or too short
        """
        # Check environment (default to development if not set)
        environment = os.getenv("ENVIRONMENT", "development").lower()

        # In production AND staging, reject the default secret key
        if environment in ["production", "staging"] and v == "default-secret-key":
            raise ValueError(
                "SECRET_KEY must be set to a secure value in production/staging. "
                "Generate a random secret with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Enforce minimum length for security (32 characters = 256 bits)
        # Skip this check if using default key in development (handled by warning below)
        if v != "default-secret-key" and len(v) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters long (current: {len(v)}). "
                "For production, use: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Entropy check for production
        if environment == "production":
            pass

            # Calculate entropy: unique_chars / total_chars
            entropy = len(set(v)) / len(v)
            if entropy < 0.5:
                raise ValueError("SECRET_KEY has insufficient entropy for production")

        # Warn if using default in development
        if v == "default-secret-key":
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "Using default SECRET_KEY in development. "
                "Set a unique SECRET_KEY in .env for better security."
            )

        return v

    # NLP Model Configuration
    SPACY_MODEL: str = "en_core_web_sm"
    USE_GPU: bool = False

    # Intent Recognition Config
    INTENT_CONFIDENCE_THRESHOLD: float = 0.5
    ENTITY_CONFIDENCE_THRESHOLD: float = 0.6

    # Sentiment Analysis Config
    SENTIMENT_THRESHOLD_POSITIVE: float = 0.6
    SENTIMENT_THRESHOLD_NEGATIVE: float = -0.4
    SENTIMENT_THRESHOLD_DISTRESSED: float = -0.7
    SENTIMENT_THRESHOLD_URGENT: float = 0.8

    # LLM Configuration
    OLLAMA_HOST: str = Field(default_factory=_get_ollama_host)
    OLLAMA_MODEL: str = "gemma3:1b"
    OLLAMA_TEMPERATURE: float = 0.7
    OLLAMA_TOP_P: float = 0.9
    OLLAMA_TOP_K: int = 40
    OLLAMA_MAX_TOKENS: int = 256
    OLLAMA_CONTEXT_WINDOW: int = 2048
    OLLAMA_TIMEOUT_SECONDS: int = 60

    # Disable Gemini integration by default
    USE_GEMINI: bool = Field(default=False, env="USE_GEMINI")

    # Feature Flags
    RAG_ENABLED: bool = Field(default=True, env="FEATURE_RAG")
    MEMORY_ENABLED: bool = Field(default=True, env="FEATURE_MEMORY")
    AGENTS_ENABLED: bool = Field(default=True, env="FEATURE_AGENTS")
    REALTIME_ENABLED: bool = Field(default=True, env="FEATURE_REALTIME")
    MEDICAL_ROUTES_ENABLED: bool = Field(default=True, env="FEATURE_MEDICAL_ROUTES")
    INTEGRATIONS_ENABLED: bool = Field(default=True, env="FEATURE_INTEGRATIONS")
    COMPLIANCE_ENABLED: bool = Field(default=True, env="FEATURE_COMPLIANCE")
    CALENDAR_ENABLED: bool = Field(default=True, env="FEATURE_CALENDAR")
    KNOWLEDGE_GRAPH_ENABLED: bool = Field(default=True, env="FEATURE_KNOWLEDGE_GRAPH")
    NOTIFICATIONS_ENABLED: bool = Field(default=True, env="FEATURE_NOTIFICATIONS")
    TOOLS_ENABLED: bool = Field(default=True, env="FEATURE_TOOLS")
    VISION_ENABLED: bool = Field(default=True, env="FEATURE_VISION")
    NEW_AI_FRAMEWORKS_ENABLED: bool = Field(
        default=True, env="FEATURE_NEW_AI_FRAMEWORKS"
    )
    EVALUATION_ENABLED: bool = Field(default=True, env="FEATURE_EVALUATION")
    STRUCTURED_OUTPUTS_ENABLED: bool = Field(
        default=True, env="FEATURE_STRUCTURED_OUTPUTS"
    )
    GENERATION_ENABLED: bool = Field(default=True, env="FEATURE_GENERATION")

    USE_OLLAMA_FOR_RESPONSES: bool = True
    OLLAMA_FALLBACK_TO_LLM: bool = True

    # Model Versioning
    DEFAULT_MODEL_VERSION: str = "v1.0"

    # Transformer Models
    USE_TRANSFORMER_MODELS: bool = False
    TRANSFORMER_MODEL_NAME: str = "bert-base-uncased"

    # ML Models
    USE_ML_RISK_MODELS: bool = False
    ML_RISK_MODEL_TYPE: str = "random_forest"

    # Framingham Risk Score Coefficients (PHASE 3: Externalized Configuration)
    FRAMINGHAM_AGE_COEFFICIENT: float = 0.05
    FRAMINGHAM_BP_COEFFICIENT: float = 0.01
    FRAMINGHAM_CHOLESTEROL_COEFFICIENT: float = 0.005
    FRAMINGHAM_SMOKING_COEFFICIENT: float = 0.3
    FRAMINGHAM_DIABETES_COEFFICIENT: float = 0.2
    FRAMINGHAM_FAMILY_HISTORY_COEFFICIENT: float = 0.15
    FRAMINGHAM_ACTIVITY_COEFFICIENT: float = -0.001

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "nlp_service.log"

    # CORS Configuration - includes ports 5173, 5174, 5175, 5176 for Vite dev server
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "https://heartguard.ai",
    ]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Web Search Rate Limits
    WEB_SEARCH_RATE_LIMITS: dict = {
        "per_user_per_hour": 20,
        "per_user_per_day": 100,
        "global_per_minute": 60
    }

    # =========================================================================
    # MEMORI INTEGRATION SETTINGS (Phase 2: Enhanced Memory Features)
    # =========================================================================

    # Memory Manager Settings
    MEMORI_ENABLED: bool = True
    MEMORI_DATABASE_URL: str = "sqlite:///./memori.db"
    MEMORI_CACHE_SIZE: int = 100  # Max patient instances in LRU cache
    MEMORI_POOL_SIZE: int = 10  # Database connection pool size
    MEMORI_REQUEST_TIMEOUT: int = 30  # Timeout for memory operations (seconds)

    # Embedding Search Settings (EmbeddingSearchEngine)
    MEMORI_EMBEDDING_USE_LOCAL: bool = True  # Use sentence-transformers locally
    MEMORI_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # Local embedding model
    MEMORI_EMBEDDING_SIMILARITY_THRESHOLD: float = 0.5  # Minimum similarity score
    MEMORI_EMBEDDING_CACHE_SIZE: int = 10000  # Embedding vector cache size

    # Conscious Agent Settings (ConsciouscAgent)
    MEMORI_CONSCIOUS_INGEST: bool = True  # Auto-inject relevant memory
    MEMORI_CONSCIOUS_MEMORY_LIMIT: int = 10  # Max conscious memories to load

    # Rate Limiting Settings (Memori RateLimiter)
    MEMORI_RATE_LIMIT_SEARCH: int = 60  # Searches per minute per user
    MEMORI_RATE_LIMIT_STORE: int = 100  # Stores per minute per user
    MEMORI_RATE_LIMIT_API_CALLS: int = 1000  # API calls per day per user
    MEMORI_STORAGE_QUOTA_MB: int = 100  # Storage quota per user in MB
    MEMORI_MEMORY_COUNT_LIMIT: int = 10000  # Max memories per user

    # Auth Provider Settings (Optional - default to NoAuth for dev)
    MEMORI_AUTH_PROVIDER: str = "none"  # Options: "none", "jwt", "oauth2", "apikey"
    MEMORI_JWT_SECRET: str = ""  # JWT secret for JWTAuthProvider
    MEMORI_JWT_ALGORITHM: str = "HS256"

    # Input Validation Settings
    MEMORI_INPUT_MAX_QUERY_LENGTH: int = 10000  # Max query length
    MEMORI_INPUT_VALIDATE_SQL_INJECTION: bool = True
    MEMORI_INPUT_SANITIZE_XSS: bool = True

    # Circuit Breaker Settings
    MEMORI_CIRCUIT_BREAKER_THRESHOLD: int = 5  # Failures before opening
    MEMORI_CIRCUIT_BREAKER_TIMEOUT: int = 60  # Seconds before half-open

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str) and not v.strip().startswith("["):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def validate_cors_origins(cls, v):
        # Check for wildcard which is forbidden in production
        if "*" in v:
            raise ValueError("Wildcard CORS origin '*' is forbidden in production!")

        # Ensure all origins are valid URLs
        for origin in v:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(
                    f"Invalid CORS origin: {origin}. Must start with http:// or https://"
                )

        return v

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",  # Allow extra env vars like GOOGLE_*, SMTP_*, TWILIO_*, etc.
    )


# Initialize Settings
settings = Settings()

# Export variables for backward compatibility
SERVICE_NAME = settings.SERVICE_NAME
SERVICE_VERSION = settings.SERVICE_VERSION
SERVICE_PORT = settings.SERVICE_PORT
SERVICE_HOST = settings.SERVICE_HOST

DATABASE_URL = settings.DATABASE_URL

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

SPACY_MODEL = settings.SPACY_MODEL
USE_GPU = settings.USE_GPU

INTENT_CONFIDENCE_THRESHOLD = settings.INTENT_CONFIDENCE_THRESHOLD
ENTITY_CONFIDENCE_THRESHOLD = settings.ENTITY_CONFIDENCE_THRESHOLD

SENTIMENT_THRESHOLD_POSITIVE = settings.SENTIMENT_THRESHOLD_POSITIVE
SENTIMENT_THRESHOLD_NEGATIVE = settings.SENTIMENT_THRESHOLD_NEGATIVE
SENTIMENT_THRESHOLD_DISTRESSED = settings.SENTIMENT_THRESHOLD_DISTRESSED
SENTIMENT_THRESHOLD_URGENT = settings.SENTIMENT_THRESHOLD_URGENT

OLLAMA_HOST = settings.OLLAMA_HOST
OLLAMA_MODEL = settings.OLLAMA_MODEL
OLLAMA_TEMPERATURE = settings.OLLAMA_TEMPERATURE
OLLAMA_TOP_P = settings.OLLAMA_TOP_P
OLLAMA_TOP_K = settings.OLLAMA_TOP_K
OLLAMA_MAX_TOKENS = settings.OLLAMA_MAX_TOKENS
OLLAMA_CONTEXT_WINDOW = settings.OLLAMA_CONTEXT_WINDOW
OLLAMA_TIMEOUT_SECONDS = settings.OLLAMA_TIMEOUT_SECONDS

USE_OLLAMA_FOR_RESPONSES = settings.USE_OLLAMA_FOR_RESPONSES
OLLAMA_FALLBACK_TO_LLM = settings.OLLAMA_FALLBACK_TO_LLM

DEFAULT_MODEL_VERSION = settings.DEFAULT_MODEL_VERSION

USE_TRANSFORMER_MODELS = settings.USE_TRANSFORMER_MODELS
TRANSFORMER_MODEL_NAME = settings.TRANSFORMER_MODEL_NAME

USE_ML_RISK_MODELS = settings.USE_ML_RISK_MODELS
ML_RISK_MODEL_TYPE = settings.ML_RISK_MODEL_TYPE

LOG_LEVEL = settings.LOG_LEVEL
LOG_FILE = settings.LOG_FILE

CORS_ORIGINS = settings.CORS_ORIGINS

RATE_LIMIT_PER_MINUTE = settings.RATE_LIMIT_PER_MINUTE

# Memori Integration Settings Exports
MEMORI_ENABLED = settings.MEMORI_ENABLED
MEMORI_DATABASE_URL = settings.MEMORI_DATABASE_URL
MEMORI_CACHE_SIZE = settings.MEMORI_CACHE_SIZE
MEMORI_POOL_SIZE = settings.MEMORI_POOL_SIZE
MEMORI_REQUEST_TIMEOUT = settings.MEMORI_REQUEST_TIMEOUT
MEMORI_EMBEDDING_USE_LOCAL = settings.MEMORI_EMBEDDING_USE_LOCAL
MEMORI_EMBEDDING_MODEL = settings.MEMORI_EMBEDDING_MODEL
MEMORI_EMBEDDING_SIMILARITY_THRESHOLD = settings.MEMORI_EMBEDDING_SIMILARITY_THRESHOLD
MEMORI_CONSCIOUS_INGEST = settings.MEMORI_CONSCIOUS_INGEST
MEMORI_RATE_LIMIT_SEARCH = settings.MEMORI_RATE_LIMIT_SEARCH
MEMORI_RATE_LIMIT_STORE = settings.MEMORI_RATE_LIMIT_STORE
MEMORI_AUTH_PROVIDER = settings.MEMORI_AUTH_PROVIDER
MEMORI_CIRCUIT_BREAKER_THRESHOLD = settings.MEMORI_CIRCUIT_BREAKER_THRESHOLD

# Feature Flags Exports
RAG_ENABLED = settings.RAG_ENABLED
MEMORY_ENABLED = settings.MEMORY_ENABLED
AGENTS_ENABLED = settings.AGENTS_ENABLED
REALTIME_ENABLED = settings.REALTIME_ENABLED
MEDICAL_ROUTES_ENABLED = settings.MEDICAL_ROUTES_ENABLED
INTEGRATIONS_ENABLED = settings.INTEGRATIONS_ENABLED
COMPLIANCE_ENABLED = settings.COMPLIANCE_ENABLED
CALENDAR_ENABLED = settings.CALENDAR_ENABLED
KNOWLEDGE_GRAPH_ENABLED = settings.KNOWLEDGE_GRAPH_ENABLED
NOTIFICATIONS_ENABLED = settings.NOTIFICATIONS_ENABLED
TOOLS_ENABLED = settings.TOOLS_ENABLED
VISION_ENABLED = settings.VISION_ENABLED
NEW_AI_FRAMEWORKS_ENABLED = settings.NEW_AI_FRAMEWORKS_ENABLED
EVALUATION_ENABLED = settings.EVALUATION_ENABLED
STRUCTURED_OUTPUTS_ENABLED = settings.STRUCTURED_OUTPUTS_ENABLED
GENERATION_ENABLED = settings.GENERATION_ENABLED

# Constants (Not Settings)
EMERGENCY_KEYWORDS = [
    "emergency",
    "severe",
    "critical",
    "can't breathe",
    "cannot breathe",
    "passing out",
    "faint",
    "collapse",
    "help me",
    "911",
    "ambulance",
    "dying",
    "heart attack",
    "stroke",
    "unresponsive",
    "unconscious",
    "life threatening",
    "dial 911",
    "call 911",
    "please help",
]

CARDIOVASCULAR_SYMPTOMS = [
    "chest pain",
    "chest tightness",
    "chest discomfort",
    "chest pressure",
    "shortness of breath",
    "difficulty breathing",
    "breathless",
    "dyspnea",
    "dizziness",
    "dizzy",
    "lightheaded",
    "vertigo",
    "fainting",
    "fatigue",
    "tired",
    "exhausted",
    "weakness",
    "extreme fatigue",
    "palpitations",
    "heart pounding",
    "irregular heartbeat",
    "arrhythmia",
    "nausea",
    "nauseous",
    "sick",
    "vomiting",
    "sweating",
    "perspiration",
    "sweat",
    "diaphoresis",
    "jaw pain",
    "arm pain",
    "shoulder pain",
    "back pain",
    "neck pain",
    "fluttering heart",
    "racing heart",
    "heart skipping beats",
]

MEDICATIONS_DATABASE = {
    "aspirin": {"class": "antiplatelet", "frequency": "daily"},
    "lisinopril": {"class": "ace_inhibitor", "frequency": "daily"},
    "metoprolol": {"class": "beta_blocker", "frequency": "daily"},
    "atorvastatin": {"class": "statin", "frequency": "daily"},
    "amlodipine": {"class": "calcium_channel_blocker", "frequency": "daily"},
    "losartan": {"class": "arb", "frequency": "daily"},
    "carvedilol": {"class": "beta_blocker", "frequency": "twice_daily"},
    "furosemide": {"class": "diuretic", "frequency": "daily"},
    "diltiazem": {"class": "calcium_channel_blocker", "frequency": "daily"},
    "verapamil": {"class": "calcium_channel_blocker", "frequency": "daily"},
    "nitroglycerin": {"class": "nitrate", "frequency": "as_needed"},
    "clopidogrel": {"class": "antiplatelet", "frequency": "daily"},
    "dabigatran": {"class": "anticoagulant", "frequency": "twice_daily"},
    "warfarin": {"class": "anticoagulant", "frequency": "daily"},
    "enoxaparin": {"class": "anticoagulant", "frequency": "twice_daily"},
}

HEART_HEALTHY_FOODS = {
    "olive oil": "fat",
    "fish": "protein",
    "salmon": "protein",
    "nuts": "fat",
    "almonds": "fat",
    "berries": "fruit",
    "blueberries": "fruit",
    "strawberries": "fruit",
    "vegetables": "vegetable",
    "broccoli": "vegetable",
    "spinach": "vegetable",
    "oats": "grain",
    "whole wheat": "grain",
    "fiber": "fiber",
    "avocado": "fat",
    "chicken": "protein",
    "turkey": "protein",
    "beans": "protein",
    "lentils": "protein",
    "legumes": "protein",
    "whole grains": "grain",
}

MODEL_VERSIONS = {
    "intent_recognizer": DEFAULT_MODEL_VERSION,
    "sentiment_analyzer": DEFAULT_MODEL_VERSION,
    "entity_extractor": DEFAULT_MODEL_VERSION,
    "risk_assessor": DEFAULT_MODEL_VERSION,
}

OLLAMA_AVAILABLE_MODELS = [
    "gemma3:4b",  # ✅ Default: balanced performance & capability
    "gemma2:2b",  # Alternative: lightweight, fast
    "gemma2:9b",  # Alternative: larger Gemma2 model
    "phi3",  # Alternative: Microsoft Phi 3 (small, capable)
    "neural-chat",  # Alternative: dialogue-optimized
    "mistral",  # Alternative: powerful general-purpose
    "llama2",  # Alternative: larger context window
]
