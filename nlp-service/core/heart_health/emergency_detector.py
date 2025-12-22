"""
Emergency Detector Module for Heart Health AI Assistant.

Detects emergency keywords and urgent medical situations in user queries.
"""

import logging
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UrgencyLevel(Enum):
    """Urgency classification levels."""
    ROUTINE = "routine"
    MODERATE = "moderate"
    URGENT = "urgent"
    EMERGENCY = "emergency"


@dataclass
class EmergencyAssessment:
    """Result of emergency detection analysis."""
    is_emergency: bool
    urgency_level: UrgencyLevel
    matched_keywords: List[str]
    recommended_action: str
    confidence: float
    

class EmergencyDetector:
    """
    Detects emergency situations and urgent medical conditions.
    
    Uses keyword matching and pattern recognition to identify:
    - Life-threatening emergencies requiring 911
    - Urgent conditions needing prompt medical attention
    - Moderate concerns for next-day follow-up
    - Routine health questions
    """
    
    # Emergency keywords - call 911 immediately
    EMERGENCY_KEYWORDS = [
        # Cardiac emergencies
        "heart attack", "cardiac arrest", "can't breathe", "cannot breathe",
        "severe chest pain", "crushing chest pain", "chest pressure",
        "stroke", "face drooping", "arm weakness", "speech difficulty",
        
        # Critical symptoms
        "passing out", "unconscious", "unresponsive", "collapse", "collapsed",
        "can't move", "paralyzed", "paralysis",
        "severe bleeding", "won't stop bleeding",
        "choking", "can't swallow",
        
        # Explicit emergency calls
        "call 911", "dial 911", "emergency", "ambulance", "ER",
        "help me", "dying", "I'm dying", "going to die",
        "911", "life threatening"
    ]
    
    # Urgent keywords - seek medical care within hours
    URGENT_KEYWORDS = [
        # Cardiac concerns
        "chest pain", "chest tightness", "heart racing", "heart pounding",
        "irregular heartbeat", "skipping beats", "palpitations",
        "shortness of breath", "difficulty breathing", "breathless",
        
        # Other urgent symptoms
        "severe pain", "worst pain", "sudden pain",
        "fainting", "fainted", "dizzy", "dizziness", "lightheaded",
        "severe headache", "worst headache",
        "swelling in legs", "leg swelling", "ankle swelling",
        "cold sweats", "breaking out in sweat",
        "nausea and vomiting", "severe nausea",
        
        # Vital sign concerns
        "very high heart rate", "heart rate over 150", "heart rate above 150",
        "very low heart rate", "heart rate below 40",
        "oxygen below 90", "spo2 below 90", "low oxygen"
    ]
    
    # Moderate concern keywords - schedule appointment soon
    MODERATE_KEYWORDS = [
        "occasional chest discomfort", "mild chest pain",
        "getting tired easily", "more tired than usual", "fatigue",
        "heart fluttering", "heart flutter",
        "mildly dizzy", "slight dizziness",
        "high blood pressure", "elevated blood pressure",
        "high heart rate", "fast heart rate",
        "low heart rate", "slow heart rate",
        "swollen ankles", "feet swelling"
    ]
    
    # Patterns for detecting vital sign concerns
    VITAL_PATTERNS = [
        # Heart rate patterns
        (r"heart rate (?:of |is |at )?(\d+)", "heart_rate"),
        (r"(\d+)\s*(?:bpm|beats per minute)", "heart_rate"),
        (r"pulse (?:of |is |at )?(\d+)", "heart_rate"),
        
        # SpO2 patterns
        (r"(?:spo2|oxygen|o2) (?:of |is |at )?(\d+)", "spo2"),
        (r"(?:spo2|oxygen|o2).{0,20}(\d+)\s*%", "spo2"),
        
        # Blood pressure patterns
        (r"blood pressure (?:of |is |at )?(\d+)/(\d+)", "blood_pressure"),
        (r"(\d+)/(\d+)\s*(?:mmhg|bp)", "blood_pressure")
    ]
    
    def __init__(self):
        self.emergency_pattern = self._compile_pattern(self.EMERGENCY_KEYWORDS)
        self.urgent_pattern = self._compile_pattern(self.URGENT_KEYWORDS)
        self.moderate_pattern = self._compile_pattern(self.MODERATE_KEYWORDS)
        self.vital_patterns = [(re.compile(p, re.IGNORECASE), t) for p, t in self.VITAL_PATTERNS]
    
    def _compile_pattern(self, keywords: List[str]) -> re.Pattern:
        """Compile keywords into a regex pattern."""
        escaped = [re.escape(kw) for kw in keywords]
        pattern = r'\b(?:' + '|'.join(escaped) + r')\b'
        return re.compile(pattern, re.IGNORECASE)
    
    def detect(self, query: str) -> EmergencyAssessment:
        """
        Analyze a query for emergency indicators.
        
        Args:
            query: User's query text
            
        Returns:
            EmergencyAssessment with urgency classification
        """
        query_lower = query.lower()
        matched_keywords = []
        urgency_level = UrgencyLevel.ROUTINE
        
        # Check for emergency keywords
        emergency_matches = self.emergency_pattern.findall(query_lower)
        if emergency_matches:
            matched_keywords.extend(emergency_matches)
            urgency_level = UrgencyLevel.EMERGENCY
        
        # Check for urgent keywords
        urgent_matches = self.urgent_pattern.findall(query_lower)
        if urgent_matches and urgency_level != UrgencyLevel.EMERGENCY:
            matched_keywords.extend(urgent_matches)
            urgency_level = UrgencyLevel.URGENT
        
        # Check for moderate keywords
        moderate_matches = self.moderate_pattern.findall(query_lower)
        if moderate_matches and urgency_level == UrgencyLevel.ROUTINE:
            matched_keywords.extend(moderate_matches)
            urgency_level = UrgencyLevel.MODERATE
        
        # Check vital signs for concerning values
        vital_urgency = self._check_vital_signs(query)
        if vital_urgency:
            if vital_urgency == UrgencyLevel.EMERGENCY:
                urgency_level = UrgencyLevel.EMERGENCY
            elif vital_urgency == UrgencyLevel.URGENT and urgency_level != UrgencyLevel.EMERGENCY:
                urgency_level = UrgencyLevel.URGENT
        
        # Determine recommendation
        recommended_action = self._get_recommended_action(urgency_level)
        
        # Calculate confidence
        confidence = self._calculate_confidence(matched_keywords, urgency_level)
        
        return EmergencyAssessment(
            is_emergency=(urgency_level == UrgencyLevel.EMERGENCY),
            urgency_level=urgency_level,
            matched_keywords=matched_keywords,
            recommended_action=recommended_action,
            confidence=confidence
        )
    
    def _check_vital_signs(self, query: str) -> Optional[UrgencyLevel]:
        """Check for concerning vital sign values in the query."""
        for pattern, vital_type in self.vital_patterns:
            match = pattern.search(query)
            if match:
                if vital_type == "heart_rate":
                    hr = int(match.group(1))
                    if hr > 150 or hr < 40:
                        return UrgencyLevel.EMERGENCY
                    elif hr > 120 or hr < 50:
                        return UrgencyLevel.URGENT
                    elif hr > 100 or hr < 60:
                        return UrgencyLevel.MODERATE
                        
                elif vital_type == "spo2":
                    spo2 = int(match.group(1))
                    if spo2 < 88:
                        return UrgencyLevel.EMERGENCY
                    elif spo2 < 92:
                        return UrgencyLevel.URGENT
                    elif spo2 < 95:
                        return UrgencyLevel.MODERATE
                        
                elif vital_type == "blood_pressure":
                    systolic = int(match.group(1))
                    diastolic = int(match.group(2))
                    if systolic > 180 or diastolic > 120:
                        return UrgencyLevel.EMERGENCY
                    elif systolic > 160 or diastolic > 100:
                        return UrgencyLevel.URGENT
                    elif systolic > 140 or diastolic > 90:
                        return UrgencyLevel.MODERATE
        
        return None
    
    def _get_recommended_action(self, urgency: UrgencyLevel) -> str:
        """Get recommended action based on urgency level."""
        actions = {
            UrgencyLevel.EMERGENCY: (
                "⚠️ EMERGENCY: Call 911 immediately or go to the nearest emergency room. "
                "Do not drive yourself. Stay calm and remain seated until help arrives."
            ),
            UrgencyLevel.URGENT: (
                "🔴 URGENT: Please seek medical attention within the next few hours. "
                "Contact your doctor's office, visit an urgent care center, or go to the ER if symptoms worsen."
            ),
            UrgencyLevel.MODERATE: (
                "🟡 Schedule an appointment with your healthcare provider within the next 1-2 days. "
                "Monitor your symptoms and seek immediate care if they worsen."
            ),
            UrgencyLevel.ROUTINE: (
                "This appears to be a general health question. I'm happy to provide information, "
                "but always consult your healthcare provider for personalized medical advice."
            )
        }
        return actions.get(urgency, actions[UrgencyLevel.ROUTINE])
    
    def _calculate_confidence(self, keywords: List[str], urgency: UrgencyLevel) -> float:
        """Calculate confidence score for the assessment."""
        if not keywords and urgency == UrgencyLevel.ROUTINE:
            return 0.9  # High confidence for routine (no concerning keywords)
        elif len(keywords) >= 3:
            return 0.95  # High confidence with multiple matches
        elif len(keywords) >= 1:
            return 0.85  # Good confidence with some matches
        else:
            return 0.7   # Moderate confidence (vital sign detection only)


# Optional type annotation import
from typing import Optional
