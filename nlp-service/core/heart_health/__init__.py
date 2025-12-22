"""
Heart Health AI Module
Core implementation for the Heart Health AI Assistant.
"""

from .response_generator import (
    HeartHealthResponseGenerator,
    get_response_generator,
    generate_response
)
from .emergency_detector import EmergencyDetector

__all__ = [
    "HeartHealthResponseGenerator",
    "get_response_generator", 
    "generate_response",
    "EmergencyDetector"
]
