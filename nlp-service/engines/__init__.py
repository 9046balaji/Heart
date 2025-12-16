"""
NLP Engines Package

This package provides a clean import interface for the core NLP processing engines.
The actual implementations are in the parent nlp-service directory for backwards
compatibility. This __init__.py re-exports them for cleaner imports.

Usage:
    from engines import IntentRecognizer, SentimentAnalyzer
    # or
    from engines.intent_recognizer import IntentRecognizer
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Re-export from parent directory
from intent_recognizer import IntentRecognizer
from sentiment_analyzer import SentimentAnalyzer
from entity_extractor import EntityExtractor
from risk_assessor import RiskAssessor

__all__ = [
    "IntentRecognizer",
    "SentimentAnalyzer", 
    "EntityExtractor",
    "RiskAssessor",
]
