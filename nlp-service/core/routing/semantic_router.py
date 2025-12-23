"""
Semantic Router - Production-grade query routing for Specialist vs. Generalist pattern.

Routes user queries to either:
- MedGemma (Doctor) - For complex medical queries, drug interactions, clinical analysis
- General Chat (Receptionist) - For greetings, simple questions, appointment scheduling

Based on ARCHITECTURE.md specifications.
"""

import os
import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """Type of AI agent handling the query."""
    DOCTOR = "doctor"          # MedGemma - strict, data-driven, low temperature
    RECEPTIONIST = "receptionist"  # General Chat - friendly, conversational


class IntentCategory(str, Enum):
    """Categorized user intents for routing decisions."""
    GREETING = "greeting"
    MEDICAL_REPORT = "medical_report"
    DRUG_INTERACTION = "drug_interaction"
    SYMPTOM_CHECK = "symptom_check"
    RISK_ASSESSMENT = "risk_assessment"
    VITALS_ANALYSIS = "vitals_analysis"
    APPOINTMENT = "appointment"
    NUTRITION = "nutrition"
    EXERCISE = "exercise"
    GENERAL_HEALTH = "general_health"
    EMERGENCY = "emergency"
    UNKNOWN = "unknown"


@dataclass
class RouteDecision:
    """Result of routing decision with full context."""
    agent_type: AgentType
    intent: IntentCategory
    complexity_score: float
    is_emergency: bool
    confidence: float
    routing_reason: str
    matched_keywords: List[str] = field(default_factory=list)


class SemanticRouterService:
    """
    Production-grade semantic router implementing the Specialist vs. Generalist pattern.
    
    Routing Logic:
    1. Emergency detection takes priority
    2. If complexity_score > threshold OR intent is medical_report → Doctor (MedGemma)
    3. Otherwise → Receptionist (General Chat)
    
    Usage:
        router = SemanticRouterService()
        decision = router.route("What are the drug interactions between lisinopril and aspirin?")
        print(decision.agent_type)  # AgentType.DOCTOR
    """
    
    # Emergency keywords - HIGHEST PRIORITY, always route to Doctor
    EMERGENCY_KEYWORDS: Set[str] = {
        "chest pain", "heart attack", "stroke", "can't breathe", "cannot breathe",
        "severe pain", "passing out", "fainting", "unconscious", "numbness",
        "911", "emergency", "dying", "help me", "call ambulance",
        "difficulty breathing", "shortness of breath", "crushing chest",
        "arm pain radiating", "jaw pain", "sudden weakness"
    }
    
    # Medical report / analysis keywords - route to Doctor
    MEDICAL_REPORT_KEYWORDS: Set[str] = {
        "report", "analysis", "analyze", "interpret", "lab results", "test results",
        "ecg", "ekg", "blood work", "bloodwork", "medical records", "diagnosis",
        "differential", "prognosis", "treatment plan", "clinical", "assessment"
    }
    
    # Drug interaction keywords - route to Doctor
    DRUG_INTERACTION_KEYWORDS: Set[str] = {
        "drug interaction", "medication interaction", "contraindication",
        "can i take", "safe to take", "mix medications", "combine drugs",
        "side effects", "adverse reaction", "drug-drug", "lisinopril",
        "metformin", "aspirin", "warfarin", "ibuprofen", "prescription"
    }
    
    # Complex medical terms - add to complexity score
    COMPLEX_MEDICAL_TERMS: Set[str] = {
        "diagnosis", "differential", "etiology", "pathophysiology", "comorbidity",
        "contraindication", "pharmacokinetics", "bioavailability", "arrhythmia",
        "tachycardia", "bradycardia", "hypertension", "hypotension", "ischemia",
        "infarction", "fibrillation", "stenosis", "cardiomyopathy", "endocarditis",
        "hemoglobin", "cholesterol", "triglycerides", "creatinine", "bilirubin"
    }
    
    # Greeting patterns - route to Receptionist
    GREETING_PATTERNS: Set[str] = {
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "how are you", "what's up", "howdy", "greetings", "nice to meet"
    }
    
    # Appointment keywords - route to Receptionist
    APPOINTMENT_KEYWORDS: Set[str] = {
        "appointment", "schedule", "book", "booking", "reschedule", "cancel",
        "doctor visit", "availability", "slot", "meeting", "consultation time"
    }
    
    def __init__(self, complexity_threshold: float = 0.8):
        """
        Initialize the semantic router.
        
        Args:
            complexity_threshold: Score above which queries route to Doctor (default 0.8)
        """
        self.complexity_threshold = float(
            os.getenv("COMPLEXITY_THRESHOLD", str(complexity_threshold))
        )
        logger.info(f"SemanticRouterService initialized with threshold={self.complexity_threshold}")
    
    def route(self, query: str) -> RouteDecision:
        """
        Route a user query to the appropriate agent.
        
        Args:
            query: User's input text
            
        Returns:
            RouteDecision with agent type, intent, complexity score, and reasoning
        """
        query_lower = query.lower().strip()
        matched_keywords: List[str] = []
        
        # STEP 1: Emergency detection (highest priority)
        is_emergency, emergency_matches = self._detect_emergency(query_lower)
        if is_emergency:
            matched_keywords.extend(emergency_matches)
            return RouteDecision(
                agent_type=AgentType.DOCTOR,
                intent=IntentCategory.EMERGENCY,
                complexity_score=1.0,
                is_emergency=True,
                confidence=0.99,
                routing_reason="Emergency keywords detected - immediate medical attention required",
                matched_keywords=matched_keywords
            )
        
        # STEP 2: Calculate complexity score
        complexity_score, complexity_matches = self._calculate_complexity_score(query_lower)
        matched_keywords.extend(complexity_matches)
        
        # STEP 3: Detect intent category
        intent, intent_confidence, intent_matches = self._detect_intent(query_lower)
        matched_keywords.extend(intent_matches)
        
        # STEP 4: Routing decision
        # Route to Doctor if:
        # - Complexity > threshold
        # - Intent is medical report, drug interaction, or vitals analysis
        should_route_to_doctor = (
            complexity_score > self.complexity_threshold or
            intent in {
                IntentCategory.MEDICAL_REPORT,
                IntentCategory.DRUG_INTERACTION,
                IntentCategory.SYMPTOM_CHECK,
                IntentCategory.RISK_ASSESSMENT,
                IntentCategory.VITALS_ANALYSIS
            }
        )
        
        if should_route_to_doctor:
            reason = self._build_doctor_reason(complexity_score, intent)
            return RouteDecision(
                agent_type=AgentType.DOCTOR,
                intent=intent,
                complexity_score=complexity_score,
                is_emergency=False,
                confidence=max(0.7, intent_confidence),
                routing_reason=reason,
                matched_keywords=list(set(matched_keywords))
            )
        else:
            reason = self._build_receptionist_reason(complexity_score, intent)
            return RouteDecision(
                agent_type=AgentType.RECEPTIONIST,
                intent=intent,
                complexity_score=complexity_score,
                is_emergency=False,
                confidence=max(0.6, intent_confidence),
                routing_reason=reason,
                matched_keywords=list(set(matched_keywords))
            )
    
    def _detect_emergency(self, query_lower: str) -> tuple[bool, List[str]]:
        """Detect emergency situations requiring immediate response."""
        matches = []
        for keyword in self.EMERGENCY_KEYWORDS:
            if keyword in query_lower:
                matches.append(keyword)
        
        return len(matches) > 0, matches
    
    def _calculate_complexity_score(self, query_lower: str) -> tuple[float, List[str]]:
        """
        Calculate query complexity based on multiple factors.
        
        Returns:
            Tuple of (complexity_score 0.0-1.0, matched_keywords)
        """
        score = 0.0
        matches = []
        
        # Length factor (longer queries tend to be more complex)
        if len(query_lower) > 200:
            score += 0.25
        elif len(query_lower) > 100:
            score += 0.15
        elif len(query_lower) > 50:
            score += 0.05
        
        # Medical complexity indicators
        for term in self.COMPLEX_MEDICAL_TERMS:
            if term in query_lower:
                score += 0.12
                matches.append(term)
        
        # Drug interaction keywords (high complexity)
        for keyword in self.DRUG_INTERACTION_KEYWORDS:
            if keyword in query_lower:
                score += 0.20
                matches.append(keyword)
        
        # Medical report keywords
        for keyword in self.MEDICAL_REPORT_KEYWORDS:
            if keyword in query_lower:
                score += 0.15
                matches.append(keyword)
        
        # Multi-domain detection (cardiac + nutrition + medication = complex)
        domains = {
            "cardiac": ["heart", "cardiac", "cardiovascular", "ecg", "blood pressure", "pulse"],
            "nutrition": ["diet", "nutrition", "food", "eating", "sodium", "cholesterol"],
            "medication": ["drug", "medication", "prescription", "dosage", "medicine", "pill"],
            "exercise": ["exercise", "workout", "activity", "fitness", "walking", "running"]
        }
        
        domains_present = 0
        for domain, keywords in domains.items():
            if any(kw in query_lower for kw in keywords):
                domains_present += 1
        
        if domains_present >= 2:
            score += 0.25
        
        # Question depth indicators
        depth_indicators = ["why", "how does", "explain", "what causes", "relationship between"]
        for indicator in depth_indicators:
            if indicator in query_lower:
                score += 0.08
        
        return min(score, 1.0), matches
    
    def _detect_intent(self, query_lower: str) -> tuple[IntentCategory, float, List[str]]:
        """
        Detect the primary intent of the query.
        
        Returns:
            Tuple of (intent_category, confidence, matched_keywords)
        """
        matches = []
        
        # Check for greeting (highest priority for Receptionist)
        for pattern in self.GREETING_PATTERNS:
            if query_lower.startswith(pattern) or pattern in query_lower[:30]:
                matches.append(pattern)
                return IntentCategory.GREETING, 0.95, matches
        
        # Check for medical report request
        for keyword in self.MEDICAL_REPORT_KEYWORDS:
            if keyword in query_lower:
                matches.append(keyword)
                return IntentCategory.MEDICAL_REPORT, 0.85, matches
        
        # Check for drug interactions
        for keyword in self.DRUG_INTERACTION_KEYWORDS:
            if keyword in query_lower:
                matches.append(keyword)
                return IntentCategory.DRUG_INTERACTION, 0.90, matches
        
        # Check for appointment scheduling
        for keyword in self.APPOINTMENT_KEYWORDS:
            if keyword in query_lower:
                matches.append(keyword)
                return IntentCategory.APPOINTMENT, 0.85, matches
        
        # Check for symptom-related queries
        symptom_keywords = ["symptom", "feeling", "pain", "ache", "hurt", "discomfort", "swelling"]
        for keyword in symptom_keywords:
            if keyword in query_lower:
                matches.append(keyword)
                return IntentCategory.SYMPTOM_CHECK, 0.75, matches
        
        # Check for vitals analysis
        vitals_keywords = ["heart rate", "blood pressure", "bp", "pulse", "spo2", "oxygen", "vitals"]
        for keyword in vitals_keywords:
            if keyword in query_lower:
                matches.append(keyword)
                return IntentCategory.VITALS_ANALYSIS, 0.80, matches
        
        # Check for risk assessment
        risk_keywords = ["risk", "chance", "likelihood", "prevent", "reduce risk", "factors"]
        for keyword in risk_keywords:
            if keyword in query_lower:
                matches.append(keyword)
                return IntentCategory.RISK_ASSESSMENT, 0.75, matches
        
        # Check for nutrition
        nutrition_keywords = ["diet", "food", "eat", "nutrition", "meal", "calories", "sodium"]
        for keyword in nutrition_keywords:
            if keyword in query_lower:
                matches.append(keyword)
                return IntentCategory.NUTRITION, 0.70, matches
        
        # Check for exercise
        exercise_keywords = ["exercise", "workout", "walk", "run", "activity", "fitness"]
        for keyword in exercise_keywords:
            if keyword in query_lower:
                matches.append(keyword)
                return IntentCategory.EXERCISE, 0.70, matches
        
        # Default to general health or unknown
        health_keywords = ["health", "healthy", "wellness", "medical", "doctor", "hospital"]
        for keyword in health_keywords:
            if keyword in query_lower:
                matches.append(keyword)
                return IntentCategory.GENERAL_HEALTH, 0.50, matches
        
        return IntentCategory.UNKNOWN, 0.30, matches
    
    def _build_doctor_reason(self, complexity_score: float, intent: IntentCategory) -> str:
        """Build explanation for routing to Doctor."""
        reasons = []
        
        if complexity_score > self.complexity_threshold:
            reasons.append(f"Complexity score ({complexity_score:.2f}) exceeds threshold ({self.complexity_threshold})")
        
        if intent == IntentCategory.MEDICAL_REPORT:
            reasons.append("Medical report/analysis requested")
        elif intent == IntentCategory.DRUG_INTERACTION:
            reasons.append("Drug interaction query detected")
        elif intent == IntentCategory.SYMPTOM_CHECK:
            reasons.append("Symptom evaluation required")
        elif intent == IntentCategory.VITALS_ANALYSIS:
            reasons.append("Vitals data analysis requested")
        elif intent == IntentCategory.RISK_ASSESSMENT:
            reasons.append("Risk assessment query detected")
        
        return " | ".join(reasons) if reasons else "Medical expertise required"
    
    def _build_receptionist_reason(self, complexity_score: float, intent: IntentCategory) -> str:
        """Build explanation for routing to Receptionist."""
        if intent == IntentCategory.GREETING:
            return "Greeting detected - friendly response appropriate"
        elif intent == IntentCategory.APPOINTMENT:
            return "Appointment scheduling - administrative task"
        elif intent == IntentCategory.NUTRITION:
            return "General nutrition question - educational response"
        elif intent == IntentCategory.EXERCISE:
            return "Exercise question - lifestyle guidance"
        else:
            return f"Low complexity ({complexity_score:.2f}) - general assistance appropriate"


# Singleton instance
_router_instance: Optional[SemanticRouterService] = None


def get_semantic_router() -> SemanticRouterService:
    """Get or create the singleton SemanticRouterService instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticRouterService()
    return _router_instance
