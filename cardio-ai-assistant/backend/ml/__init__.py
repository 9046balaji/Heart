"""
ML Package for Cardiac Anomaly Detection

This package provides real-time anomaly detection for smartwatch health data.

Components:
- FeatureExtractor: Converts raw sensor readings into ML-ready features
- RuleEngine: Fast, threshold-based anomaly detection
- CardiacAnomalyModel: ML-based pattern detection using Isolation Forest
- AnomalyDetector: Main detection engine combining rules + ML
- AlertPipeline: Routes alerts to appropriate channels
- ChatbotManager: LLM integration for natural language explanations
- HealthExplainer: Main orchestrator combining all components

Usage:
    from ml import HealthExplainer, AnomalyDetector
    
    # Quick ML-only analysis
    detector = AnomalyDetector()
    result = detector.analyze(device_id="watch_123", hr=145, spo2=94)
    
    # Full analysis with chatbot explanations
    explainer = HealthExplainer(user_profile={'name': 'John', 'age': 35})
    analysis = await explainer.analyze(device_id="watch_123", hr=145, spo2=94)
"""

from .feature_extractor import FeatureExtractor, HealthFeatures
from .rule_engine import RuleEngine, Anomaly, Severity, AnomalyType
from .ml_model import CardiacAnomalyModel, MLPrediction
from .anomaly_detector import AnomalyDetector, PredictionResult
from .prompt_templates import (
    PromptContext, 
    ResponseTone, 
    get_prompt_for_anomaly, 
    get_quick_response,
    SYSTEM_PROMPT_HEALTH_ASSISTANT
)
from .chatbot_connector import ChatbotManager, ChatResponse, GeminiChatbot, OllamaChatbot
from .alert_pipeline import AlertPipeline, Alert, AlertChannel, AlertThrottler
from .health_explainer import HealthExplainer, HealthAnalysis, create_health_explainer

__all__ = [
    # Feature Extraction
    'FeatureExtractor',
    'HealthFeatures',
    
    # Rule Engine
    'RuleEngine',
    'Anomaly',
    'Severity',
    'AnomalyType',
    
    # ML Model
    'CardiacAnomalyModel',
    'MLPrediction',
    
    # Anomaly Detection
    'AnomalyDetector',
    'PredictionResult',
    
    # Prompts
    'PromptContext',
    'ResponseTone',
    'get_prompt_for_anomaly',
    'get_quick_response',
    'SYSTEM_PROMPT_HEALTH_ASSISTANT',
    
    # Chatbot
    'ChatbotManager',
    'ChatResponse',
    'GeminiChatbot',
    'OllamaChatbot',
    
    # Alert Pipeline
    'AlertPipeline',
    'Alert',
    'AlertChannel',
    'AlertThrottler',
    
    # Health Explainer
    'HealthExplainer',
    'HealthAnalysis',
    'create_health_explainer',
]

__version__ = '1.0.0'
