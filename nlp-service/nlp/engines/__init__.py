"""
NLP Engines Package

This package provides a clean import interface for the core NLP processing engines.
After the 4-module refactor, these are now in the nlp package (parent directory).

Usage:
    from nlp.engines import IntentRecognizer, SentimentAnalyzer
"""

# Re-export from parent nlp package (relative imports)
from nlp.intent_recognizer import IntentRecognizer
from nlp.sentiment_analyzer import SentimentAnalyzer
from nlp.entity_extractor import EntityExtractor
from medical_ai.risk_assessor import RiskAssessor

__all__ = [
    "IntentRecognizer",
    "SentimentAnalyzer",
    "EntityExtractor",
    "RiskAssessor",
]
