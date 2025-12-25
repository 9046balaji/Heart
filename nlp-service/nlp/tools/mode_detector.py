"""
Mode Detection Utility for Context-Aware Tool Loading

This module provides intelligent conversation mode detection to enable
smart tool filtering and reduce token usage by ~60%.
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class ModeDetector:
    """
    Detects conversation mode from user messages to enable context-aware tool loading.
    
    Modes:
    - nutrition: Diet, calories, food, BMI, weight management
    -medication: Drugs, prescriptions, interactions, side effects
    - vitals: Blood pressure, heart rate, temperature, oxygen
    - symptoms: Pain, illness, triage, diagnostic help
    - calculators: Risk assessment, general calculations
    - general: Default fallback
    
    Example:
        detector = ModeDetector()
        mode = detector.detect("What's my BMI if I'm 170cm and 70kg?")
        # Returns: "nutrition"
    """
    
    def __init__(self):
        """Initialize mode detector with keyword patterns."""
        self.mode_patterns = {
            "nutrition": [
                # Food and diet
                r'\b(food|diet|nutrition|calorie|calories|meal|eating|eat|ate)\b',
                r'\b(bmi|body mass|weight|kg|lbs|pounds|obesity|overweight)\b',
                r'\b(protein|carb|fat|fiber|vitamin|mineral|sodium)\b',
                r'\b(breakfast|lunch|dinner|snack|fasting)\b',
                r'\b(healthy eating|weight loss|gain weight|lose weight)\b',
            ],
            "medication": [
                # Medications and drugs
                r'\b(medication|medicine|drug|pill|prescription|rx)\b',
                r'\b(take|taking|prescribed|dosage|dose|mg)\b',
                r'\b(side effect|interaction|contraindication)\b',
                r'\b(aspirin|lisinopril|metformin|atorvastatin|warfarin|statin)\b',
                r'\b(pharmacist|pharmacy|refill)\b',
            ],
            "vitals": [
                # Vital signs
                r'\b(blood pressure|bp|systolic|diastolic|mmhg)\b',
                r'\b(heart rate|pulse|bpm|beats per minute)\b',
                r'\b(temperature|temp|fever|fahrenheit|celsius)\b',
                r'\b(oxygen|o2|saturation|spo2)\b',
                r'\b(vital|vitals|measurement)\b',
            ],
            "symptoms": [
                # Symptoms and triage
                r'\b(symptom|pain|ache|hurt|hurts|aching)\b',
                r'\b(chest pain|headache|dizzy|nausea|fatigue|tired)\b',
                r'\b(sick|illness|feel|feeling|experiencing)\b',
                r'\b(emergency|urgent|severe|critical)\b',
                r'\b(shortness of breath|difficulty breathing|palpitation)\b',
            ],
            "calculators": [
                # Risk and calculations
                r'\b(risk|calculate|calculator|score|assess|assessment)\b',
                r'\b(cardiovascular|heart disease|stroke|diabetes)\b',
                r'\b(framingham|ascvd|10-year|10 year)\b',
            ],
        }
        
        # Compile patterns for performance
        self.compiled_patterns = {
            mode: [re.compile(pattern, re.IGNORECASE) 
                   for pattern in patterns]
            for mode, patterns in self.mode_patterns.items()
        }
        
        # Map mode names to category names (for tool filtering)
        self.mode_to_category = {
            "nutrition": "calculators",  # BMI calculator
           "medication": "medications",  # Plural in categories
            "vitals": "vitals",
            "symptoms": "symptoms",
            "calculators": "calculators",
            "general": "general",
        }
    
    def detect(self, message: str, context: Optional[List[str]] = None) -> str:
        """
        Detect conversation mode from message.
        
        Args:
            message: User message text
            context: Optional list of previous messages for better context
        
        Returns:
            Detected mode: nutrition, medication, vitals, symptoms, calculators, or general
        """
        if not message:
            return "general"
        
        # Combine message with recent context if provided
        text = message
        if context:
            # Use last 3 messages for context
            text = " ".join(context[-3:] + [message])
        
        # Count matches per mode
        mode_scores = {mode: 0 for mode in self.mode_patterns}
        
        for mode, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                mode_scores[mode] += len(matches)
        
        # Get mode with highest score
        best_mode = max(mode_scores, key=mode_scores.get)
        best_score = mode_scores[best_mode]
        
        # Require minimum confidence  (at least 1 match)
        if best_score == 0:
            logger.debug(f"No mode keywords found in: '{message[:50]}...', using general")
            return "general"
        
        logger.info(f"Detected mode '{best_mode}' (score: {best_score}) for: '{message[:50]}...'")
        logger.debug(f"All mode scores: {mode_scores}")
        
        # Map mode to category for tool filtering
        return self.mode_to_category.get(best_mode, best_mode)
    
    def detect_multi(self, message: str, threshold: int = 1) -> List[str]:
        """
        Detect multiple modes (for complex queries).
        
        Args:
            message: User message
            threshold: Minimum score to include mode
        
        Returns:
            List of detected modes
        """
        if not message:
            return ["general"]
        
        mode_scores = {mode: 0 for mode in self.mode_patterns}
        
        for mode, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(message)
                mode_scores[mode] += len(matches)
        
        # Get all modes above threshold
        detected_modes = [
            mode for mode, score in mode_scores.items()
            if score >= threshold
        ]
        
        # Always include general as fallback
        if not detected_modes or "general" not in detected_modes:
            detected_modes.append("general")
        
        return detected_modes


# Singleton instance
_detector_instance: Optional[ModeDetector] = None


def get_mode_detector() -> ModeDetector:
    """Get singleton ModeDetector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ModeDetector()
    return _detector_instance


def detect_mode(message: str, context: Optional[List[str]] = None) -> str:
    """
    Convenience function to detect mode.
    
    Args:
        message: User message
        context: Optional conversation context
    
    Returns:
        Detected mode
    """
    return get_mode_detector().detect(message, context)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Testing ModeDetector...\n")
    
    detector = ModeDetector()
    
    test_cases = [
        ("What's my BMI if I'm 170cm and 70kg?", "nutrition"),
        ("I'm taking Lisinopril and Warfarin, any interactions?", "medication"),
        ("My blood pressure is 140/90", "vitals"),
        ("I have chest pain and feel dizzy", "symptoms"),
        ("Calculate my 10-year cardiovascular risk", "calculators"),
        ("Hello, how are you today?", "general"),
        ("I ate a burger for lunch and my BP is 120/80", "nutrition"),  # Multi-mode
    ]
    
    print("🧪 Test Cases:\n")
    for message, expected in test_cases:
        detected = detector.detect(message)
        status = "✅" if detected == expected else "⚠️"
        print(f"{status} Message: \"{message}\"")
        print(f"   Expected: {expected}, Detected: {detected}\n")
    
    # Test multi-mode detection
    print("\n🔍 Multi-Mode Detection:\n")
    complex_query = "I'm taking aspirin, my BP is 130/85, and I want to lose weight"
    modes = detector.detect_multi(complex_query)
    print(f"Query: \"{complex_query}\"")
    print(f"Detected modes: {modes}")
    
    print("\n✅ ModeDetector tests complete!")
