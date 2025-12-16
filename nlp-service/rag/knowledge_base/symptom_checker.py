"""
Symptom Checker Knowledge Base

This module provides symptom-to-condition mapping for cardiovascular symptoms.
It helps triage symptoms and provides appropriate recommendations.

IMPORTANT DISCLAIMER: This is NOT a diagnostic tool. It provides general
health information only. Always consult a healthcare provider for medical advice.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Urgency(Enum):
    """Urgency levels for symptom triage."""
    EMERGENCY = "emergency"  # Call 911 immediately
    URGENT = "urgent"  # Seek care within hours
    SOON = "soon"  # See doctor within days
    ROUTINE = "routine"  # Schedule regular appointment


class SymptomCategory(Enum):
    """Categories of symptoms."""
    CHEST = "chest"
    BREATHING = "breathing"
    HEART_RHYTHM = "heart_rhythm"
    CIRCULATION = "circulation"
    FATIGUE = "fatigue"
    NEUROLOGICAL = "neurological"
    GENERAL = "general"


@dataclass
class SymptomMapping:
    """Maps a symptom to possible conditions and recommendations."""
    id: str
    symptom: str
    description: str
    category: SymptomCategory
    possible_conditions: List[str]
    red_flags: List[str]  # Symptoms that increase urgency
    questions_to_ask: List[str]  # Follow-up questions
    urgency: Urgency
    recommendations: List[str]
    related_symptoms: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symptom": self.symptom,
            "description": self.description,
            "category": self.category.value,
            "possible_conditions": self.possible_conditions,
            "red_flags": self.red_flags,
            "questions_to_ask": self.questions_to_ask,
            "urgency": self.urgency.value,
            "recommendations": self.recommendations,
            "related_symptoms": self.related_symptoms,
        }
    
    def to_content(self) -> str:
        """Convert to text content for embedding."""
        parts = [
            f"Symptom: {self.symptom}",
            f"Description: {self.description}",
            f"Possible causes: {', '.join(self.possible_conditions)}",
            f"Warning signs: {', '.join(self.red_flags)}",
            f"Urgency: {self.urgency.value}",
        ]
        return "\n".join(parts)


class SymptomChecker:
    """
    Cardiovascular symptom checker with triage guidance.
    
    Features:
    - Symptom-to-condition mapping
    - Urgency triage
    - Follow-up questions
    - Red flag detection
    
    DISCLAIMER: This is for informational purposes only and should
    not replace professional medical advice.
    
    Example:
        checker = SymptomChecker()
        
        # Check a symptom
        result = checker.check_symptom("chest pain")
        print(f"Urgency: {result['urgency']}")
        print(f"Possible conditions: {result['possible_conditions']}")
        
        # Check for red flags
        if checker.has_red_flags(["chest pain", "arm pain", "sweating"]):
            print("EMERGENCY - Call 911")
    """
    
    # Emergency red flag combinations
    EMERGENCY_COMBINATIONS = [
        {"chest pain", "arm pain"},
        {"chest pain", "jaw pain"},
        {"chest pain", "shortness of breath", "sweating"},
        {"sudden severe headache", "confusion"},
        {"face drooping", "arm weakness"},
        {"sudden numbness", "face drooping"},
        {"chest pain", "nausea", "sweating"},
        {"loss of consciousness"},
        {"unable to breathe"},
        {"severe chest pressure"},
    ]
    
    def __init__(self):
        """Initialize the symptom checker."""
        self._symptoms: Dict[str, SymptomMapping] = {}
        self._keyword_index: Dict[str, List[str]] = {}
        self._load_symptoms()
    
    def _load_symptoms(self) -> None:
        """Load symptom mappings."""
        symptoms = [
            # CHEST SYMPTOMS
            SymptomMapping(
                id="chest_pain",
                symptom="Chest Pain",
                description="Pain, pressure, tightness, or discomfort in the chest area",
                category=SymptomCategory.CHEST,
                possible_conditions=[
                    "Angina (heart-related chest pain)",
                    "Heart attack (if severe/persistent)",
                    "Acid reflux/GERD",
                    "Musculoskeletal pain",
                    "Anxiety/panic attack",
                    "Pericarditis",
                    "Pulmonary embolism",
                ],
                red_flags=[
                    "Pain radiating to arm, jaw, neck, or back",
                    "Accompanied by shortness of breath",
                    "Accompanied by sweating, nausea, or dizziness",
                    "Sudden onset with severe intensity",
                    "Pain with exertion that doesn't improve with rest",
                    "History of heart disease",
                ],
                questions_to_ask=[
                    "Where exactly is the pain located?",
                    "How would you describe it - sharp, dull, pressure, burning?",
                    "Does it radiate anywhere (arm, jaw, back)?",
                    "What were you doing when it started?",
                    "Does anything make it better or worse?",
                    "How long has it lasted?",
                    "Have you had this before?",
                    "Do you have any other symptoms?",
                ],
                urgency=Urgency.URGENT,
                recommendations=[
                    "If severe or with red flag symptoms - CALL 911 immediately",
                    "Do not drive yourself if you suspect heart attack",
                    "Chew aspirin (if not allergic) while waiting for emergency services",
                    "Rest and try to stay calm",
                    "For mild, non-cardiac chest pain, see doctor soon",
                ],
                related_symptoms=["shortness of breath", "arm pain", "jaw pain", "sweating"],
                keywords=["chest pain", "chest pressure", "chest tightness", "angina", "heart pain"],
            ),
            
            SymptomMapping(
                id="chest_pressure",
                symptom="Chest Pressure or Tightness",
                description="Feeling of pressure, squeezing, or heaviness in the chest",
                category=SymptomCategory.CHEST,
                possible_conditions=[
                    "Angina",
                    "Heart attack",
                    "Anxiety",
                    "Asthma",
                    "GERD",
                ],
                red_flags=[
                    "Pressure lasting more than a few minutes",
                    "Radiating discomfort",
                    "Associated with exertion",
                    "Cold sweats",
                ],
                questions_to_ask=[
                    "Can you describe the pressure?",
                    "Is it constant or does it come and go?",
                    "Does it get worse with activity?",
                ],
                urgency=Urgency.URGENT,
                recommendations=[
                    "Treat as potential cardiac emergency if persistent",
                    "Rest immediately",
                    "Call 911 if not improving within 5 minutes",
                ],
                related_symptoms=["chest pain", "shortness of breath"],
                keywords=["chest pressure", "tight chest", "chest squeezing", "heavy chest"],
            ),
            
            # BREATHING SYMPTOMS
            SymptomMapping(
                id="shortness_of_breath",
                symptom="Shortness of Breath",
                description="Difficulty breathing, feeling like you can't get enough air",
                category=SymptomCategory.BREATHING,
                possible_conditions=[
                    "Heart failure",
                    "Coronary artery disease",
                    "Arrhythmia",
                    "Pulmonary embolism",
                    "Asthma/COPD",
                    "Anemia",
                    "Anxiety",
                ],
                red_flags=[
                    "Sudden onset at rest",
                    "Accompanied by chest pain",
                    "Blue lips or fingertips (cyanosis)",
                    "Unable to speak in full sentences",
                    "Worsening when lying flat",
                    "Waking up at night gasping for air",
                    "New onset with leg swelling",
                ],
                questions_to_ask=[
                    "Did it come on suddenly or gradually?",
                    "Does it happen at rest or only with activity?",
                    "How many pillows do you sleep with?",
                    "Do you wake up at night short of breath?",
                    "Have you noticed any leg swelling?",
                    "Do you have a cough?",
                ],
                urgency=Urgency.URGENT,
                recommendations=[
                    "Sudden severe shortness of breath - Call 911",
                    "Sit upright to help breathing",
                    "If chronic/worsening, see doctor soon",
                    "Track when it occurs (rest vs exertion)",
                    "Weigh yourself daily if heart failure suspected",
                ],
                related_symptoms=["chest pain", "fatigue", "leg swelling", "cough"],
                keywords=["shortness of breath", "dyspnea", "breathless", "can't breathe", "breathing difficulty"],
            ),
            
            SymptomMapping(
                id="orthopnea",
                symptom="Difficulty Breathing When Lying Down",
                description="Shortness of breath that occurs or worsens when lying flat",
                category=SymptomCategory.BREATHING,
                possible_conditions=[
                    "Heart failure",
                    "Pulmonary edema",
                    "COPD",
                    "Obesity",
                ],
                red_flags=[
                    "Needing multiple pillows to sleep",
                    "Waking up gasping (paroxysmal nocturnal dyspnea)",
                    "Associated leg swelling",
                    "Weight gain (fluid)",
                ],
                questions_to_ask=[
                    "How many pillows do you need to sleep?",
                    "Do you sleep in a recliner?",
                    "Have you gained weight recently?",
                ],
                urgency=Urgency.SOON,
                recommendations=[
                    "Classic sign of heart failure - see cardiologist",
                    "Sleep with head elevated",
                    "Monitor weight daily",
                    "Limit salt and fluid intake",
                ],
                related_symptoms=["shortness of breath", "leg swelling", "fatigue"],
                keywords=["orthopnea", "can't lie flat", "sleeping upright", "PND"],
            ),
            
            # HEART RHYTHM SYMPTOMS
            SymptomMapping(
                id="palpitations",
                symptom="Palpitations",
                description="Awareness of heartbeat - racing, pounding, fluttering, or skipping",
                category=SymptomCategory.HEART_RHYTHM,
                possible_conditions=[
                    "Premature beats (PVCs, PACs)",
                    "Atrial fibrillation",
                    "Supraventricular tachycardia (SVT)",
                    "Anxiety/panic attacks",
                    "Caffeine/stimulants",
                    "Thyroid disorder",
                    "Anemia",
                ],
                red_flags=[
                    "Associated with passing out or near-fainting",
                    "Accompanied by chest pain",
                    "Lasting more than a few minutes",
                    "Associated with shortness of breath",
                    "History of heart disease",
                ],
                questions_to_ask=[
                    "Can you describe what you feel?",
                    "How fast does your heart seem to be beating?",
                    "Is it regular or irregular?",
                    "How long do episodes last?",
                    "What triggers them?",
                    "Do you feel lightheaded with them?",
                    "How much caffeine do you consume?",
                ],
                urgency=Urgency.SOON,
                recommendations=[
                    "If with fainting or chest pain - seek immediate care",
                    "Try to record pulse during episodes",
                    "Reduce caffeine and stimulants",
                    "Consider wearing a heart monitor (Holter)",
                    "If persistent/frequent, see cardiologist",
                ],
                related_symptoms=["dizziness", "shortness of breath", "anxiety"],
                keywords=["palpitations", "racing heart", "heart fluttering", "skipped beats", "heart pounding"],
            ),
            
            SymptomMapping(
                id="fast_heart_rate",
                symptom="Fast Heart Rate (Tachycardia)",
                description="Heart rate above 100 beats per minute at rest",
                category=SymptomCategory.HEART_RHYTHM,
                possible_conditions=[
                    "Sinus tachycardia (normal response to exercise, stress, fever)",
                    "Atrial fibrillation",
                    "SVT",
                    "Ventricular tachycardia (serious)",
                    "Thyroid disorder",
                    "Anemia",
                    "Dehydration",
                ],
                red_flags=[
                    "Heart rate >150 at rest",
                    "Associated with chest pain or shortness of breath",
                    "Feeling faint or passing out",
                    "Heart rate doesn't slow with rest",
                ],
                questions_to_ask=[
                    "What is your heart rate?",
                    "Does it start and stop suddenly or gradually?",
                    "Are you taking any medications or supplements?",
                ],
                urgency=Urgency.SOON,
                recommendations=[
                    "If with warning symptoms - seek immediate care",
                    "Check pulse and record it",
                    "Try vagal maneuvers (bearing down, cold water on face)",
                    "Avoid caffeine and stimulants",
                ],
                related_symptoms=["palpitations", "dizziness", "shortness of breath"],
                keywords=["fast heart rate", "tachycardia", "racing pulse", "rapid heartbeat"],
            ),
            
            SymptomMapping(
                id="slow_heart_rate",
                symptom="Slow Heart Rate (Bradycardia)",
                description="Heart rate below 60 beats per minute",
                category=SymptomCategory.HEART_RHYTHM,
                possible_conditions=[
                    "Normal in athletes",
                    "Sick sinus syndrome",
                    "Heart block",
                    "Medication effect (beta-blockers)",
                    "Hypothyroidism",
                ],
                red_flags=[
                    "Heart rate below 40",
                    "Fainting or near-fainting",
                    "Extreme fatigue",
                    "Confusion",
                ],
                questions_to_ask=[
                    "Are you an athlete or very physically active?",
                    "What medications are you taking?",
                    "Have you fainted?",
                ],
                urgency=Urgency.SOON,
                recommendations=[
                    "If symptomatic (fainting, fatigue), see doctor promptly",
                    "Review all medications",
                    "May need pacemaker evaluation",
                ],
                related_symptoms=["fatigue", "dizziness", "fainting"],
                keywords=["slow heart rate", "bradycardia", "slow pulse", "low heart rate"],
            ),
            
            # CIRCULATION SYMPTOMS
            SymptomMapping(
                id="leg_swelling",
                symptom="Leg Swelling (Edema)",
                description="Swelling in legs, ankles, or feet",
                category=SymptomCategory.CIRCULATION,
                possible_conditions=[
                    "Heart failure",
                    "Venous insufficiency",
                    "Deep vein thrombosis (DVT)",
                    "Kidney disease",
                    "Liver disease",
                    "Medication side effect",
                    "Lymphedema",
                ],
                red_flags=[
                    "Sudden swelling in ONE leg (possible DVT)",
                    "Red, warm, painful swelling",
                    "Associated shortness of breath",
                    "Rapid weight gain",
                ],
                questions_to_ask=[
                    "Is the swelling in one leg or both?",
                    "Did it come on suddenly or gradually?",
                    "Is it painful, red, or warm?",
                    "Do you have shortness of breath?",
                    "Have you gained weight recently?",
                    "What medications are you taking?",
                ],
                urgency=Urgency.SOON,
                recommendations=[
                    "One leg swelling with pain - may be DVT, seek urgent care",
                    "Elevate legs above heart level",
                    "Limit salt intake",
                    "Weigh yourself daily",
                    "See doctor if persistent or with other symptoms",
                ],
                related_symptoms=["shortness of breath", "weight gain", "fatigue"],
                keywords=["leg swelling", "edema", "ankle swelling", "swollen feet", "fluid retention"],
            ),
            
            SymptomMapping(
                id="dizziness",
                symptom="Dizziness or Lightheadedness",
                description="Feeling faint, woozy, or unsteady",
                category=SymptomCategory.CIRCULATION,
                possible_conditions=[
                    "Orthostatic hypotension (blood pressure drop on standing)",
                    "Dehydration",
                    "Arrhythmia",
                    "Medication side effect",
                    "Low blood sugar",
                    "Anemia",
                    "Inner ear problem (vertigo)",
                ],
                red_flags=[
                    "Associated with chest pain or shortness of breath",
                    "Progressing to fainting",
                    "With palpitations",
                    "After starting new medication",
                ],
                questions_to_ask=[
                    "Does it happen when you stand up?",
                    "Is the room spinning (vertigo)?",
                    "Have you fainted?",
                    "Any new medications?",
                    "Are you drinking enough fluids?",
                ],
                urgency=Urgency.SOON,
                recommendations=[
                    "Sit or lie down immediately if dizzy",
                    "Rise slowly from sitting or lying",
                    "Stay well hydrated",
                    "Check blood pressure lying and standing",
                    "Review medications with doctor",
                ],
                related_symptoms=["palpitations", "fainting", "fatigue"],
                keywords=["dizziness", "lightheaded", "woozy", "vertigo", "faint feeling"],
            ),
            
            SymptomMapping(
                id="syncope",
                symptom="Fainting (Syncope)",
                description="Temporary loss of consciousness",
                category=SymptomCategory.CIRCULATION,
                possible_conditions=[
                    "Vasovagal syncope (nervous system)",
                    "Orthostatic hypotension",
                    "Cardiac arrhythmia",
                    "Aortic stenosis",
                    "Cardiomyopathy",
                    "Dehydration",
                    "Seizure (different from true syncope)",
                ],
                red_flags=[
                    "Fainting during exercise",
                    "Fainting with palpitations",
                    "No warning before fainting",
                    "Family history of sudden death",
                    "Fainting while sitting or lying",
                    "Injury from fall",
                ],
                questions_to_ask=[
                    "What were you doing when you fainted?",
                    "Did you have any warning (nausea, vision changes)?",
                    "How long were you unconscious?",
                    "Did anyone witness it? Were you shaking?",
                    "Have you fainted before?",
                    "Any family history of sudden death or fainting?",
                ],
                urgency=Urgency.URGENT,
                recommendations=[
                    "All fainting episodes warrant medical evaluation",
                    "Fainting during exercise - seek care immediately",
                    "Do not drive until evaluated",
                    "May need cardiac workup (ECG, echo, monitor)",
                    "Avoid triggers if vasovagal identified",
                ],
                related_symptoms=["dizziness", "palpitations", "chest pain"],
                keywords=["fainting", "syncope", "passed out", "blacked out", "loss of consciousness"],
            ),
            
            # FATIGUE
            SymptomMapping(
                id="fatigue",
                symptom="Fatigue or Weakness",
                description="Persistent tiredness not relieved by rest",
                category=SymptomCategory.FATIGUE,
                possible_conditions=[
                    "Heart failure",
                    "Anemia",
                    "Thyroid disorder",
                    "Depression",
                    "Sleep apnea",
                    "Medication side effect",
                    "Deconditioning",
                ],
                red_flags=[
                    "Sudden onset with other cardiac symptoms",
                    "Inability to perform usual activities",
                    "Associated with shortness of breath",
                    "Weight changes",
                ],
                questions_to_ask=[
                    "How long have you felt fatigued?",
                    "Is it getting worse?",
                    "Does rest help?",
                    "How is your sleep?",
                    "Any mood changes?",
                    "Any other symptoms?",
                ],
                urgency=Urgency.ROUTINE,
                recommendations=[
                    "Get blood work (CBC, thyroid, metabolic panel)",
                    "Evaluate sleep quality",
                    "Screen for depression",
                    "If with cardiac symptoms, see cardiologist",
                    "Gradual exercise may help if cleared",
                ],
                related_symptoms=["shortness of breath", "dizziness", "weight changes"],
                keywords=["fatigue", "tiredness", "weakness", "exhausted", "no energy"],
            ),
            
            # NEUROLOGICAL (Stroke-related)
            SymptomMapping(
                id="stroke_symptoms",
                symptom="Stroke Warning Signs (BE FAST)",
                description="Sudden neurological symptoms suggesting stroke",
                category=SymptomCategory.NEUROLOGICAL,
                possible_conditions=[
                    "Ischemic stroke",
                    "Hemorrhagic stroke",
                    "TIA (transient ischemic attack - mini-stroke)",
                ],
                red_flags=[
                    "Face drooping on one side",
                    "Arm weakness (cannot raise both arms equally)",
                    "Speech difficulty (slurred or strange)",
                    "Sudden severe headache",
                    "Sudden vision loss",
                    "Sudden confusion",
                    "Loss of balance/coordination",
                ],
                questions_to_ask=[
                    "When did symptoms start?",
                    "Can you smile? Is one side drooping?",
                    "Can you raise both arms?",
                    "Can you repeat a simple sentence?",
                ],
                urgency=Urgency.EMERGENCY,
                recommendations=[
                    "CALL 911 IMMEDIATELY",
                    "Note the TIME symptoms started",
                    "Do NOT drive - call ambulance",
                    "Stroke treatment is time-critical",
                    "Do NOT give aspirin (could be bleeding stroke)",
                ],
                related_symptoms=["face drooping", "arm weakness", "speech difficulty"],
                keywords=["stroke", "face drooping", "arm weakness", "speech slurred", "TIA", "mini stroke"],
            ),
        ]
        
        for symptom in symptoms:
            self._symptoms[symptom.id] = symptom
            # Build keyword index
            for keyword in symptom.keywords:
                kw_lower = keyword.lower()
                if kw_lower not in self._keyword_index:
                    self._keyword_index[kw_lower] = []
                self._keyword_index[kw_lower].append(symptom.id)
    
    def check_symptom(self, symptom_query: str) -> Optional[Dict[str, Any]]:
        """
        Check a symptom and get information.
        
        Args:
            symptom_query: Symptom description
            
        Returns:
            Symptom information dict or None
        """
        query_lower = symptom_query.lower()
        
        # Try keyword index first
        for keyword, ids in self._keyword_index.items():
            if keyword in query_lower:
                symptom = self._symptoms[ids[0]]
                return {
                    **symptom.to_dict(),
                    "matched_keyword": keyword,
                }
        
        # Fuzzy search in symptoms
        results = self.search_symptoms(symptom_query)
        if results:
            return results[0].to_dict()
        
        return None
    
    def search_symptoms(self, query: str, max_results: int = 5) -> List[SymptomMapping]:
        """
        Search symptoms by query.
        
        Args:
            query: Search query
            max_results: Maximum results
            
        Returns:
            List of matching symptoms
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored = []
        
        for symptom in self._symptoms.values():
            score = 0
            
            # Symptom name match
            if query_lower in symptom.symptom.lower():
                score += 10
            
            # Keyword match
            for keyword in symptom.keywords:
                if keyword.lower() in query_lower:
                    score += 5
                elif any(w in keyword.lower() for w in query_words):
                    score += 2
            
            # Description match
            if any(w in symptom.description.lower() for w in query_words):
                score += 1
            
            if score > 0:
                scored.append((score, symptom))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:max_results]]
    
    def has_red_flags(self, symptoms: List[str]) -> bool:
        """
        Check if symptom combination indicates emergency.
        
        Args:
            symptoms: List of symptoms to check
            
        Returns:
            True if emergency red flags detected
        """
        symptom_set = {s.lower() for s in symptoms}
        
        # Check for emergency combinations
        for combo in self.EMERGENCY_COMBINATIONS:
            if combo.issubset(symptom_set):
                return True
        
        # Check individual high-urgency symptoms
        emergency_keywords = [
            "severe chest pain", "can't breathe", "passing out",
            "heart attack", "stroke", "face drooping",
        ]
        
        for symptom in symptoms:
            symptom_lower = symptom.lower()
            for keyword in emergency_keywords:
                if keyword in symptom_lower:
                    return True
        
        return False
    
    def triage_symptoms(self, symptoms: List[str]) -> Dict[str, Any]:
        """
        Triage a list of symptoms and determine urgency.
        
        Args:
            symptoms: List of symptoms
            
        Returns:
            Triage result with urgency and recommendations
        """
        # Check for emergency
        if self.has_red_flags(symptoms):
            return {
                "urgency": Urgency.EMERGENCY.value,
                "message": "CALL 911 IMMEDIATELY",
                "action": "These symptoms may indicate a medical emergency. Call emergency services now.",
                "symptoms_analyzed": symptoms,
            }
        
        # Find matching symptoms
        matched_symptoms = []
        highest_urgency = Urgency.ROUTINE
        urgency_order = {
            Urgency.EMERGENCY: 0,
            Urgency.URGENT: 1,
            Urgency.SOON: 2,
            Urgency.ROUTINE: 3,
        }
        
        all_recommendations = []
        
        for symptom_query in symptoms:
            result = self.check_symptom(symptom_query)
            if result:
                matched_symptoms.append(result)
                symptom_urgency = Urgency(result["urgency"])
                if urgency_order[symptom_urgency] < urgency_order[highest_urgency]:
                    highest_urgency = symptom_urgency
                all_recommendations.extend(result["recommendations"])
        
        # Generate message based on urgency
        messages = {
            Urgency.EMERGENCY: "Seek immediate emergency care",
            Urgency.URGENT: "Seek medical care within a few hours",
            Urgency.SOON: "See your doctor within a few days",
            Urgency.ROUTINE: "Schedule a regular appointment",
        }
        
        return {
            "urgency": highest_urgency.value,
            "message": messages[highest_urgency],
            "symptoms_analyzed": symptoms,
            "matched_conditions": matched_symptoms,
            "recommendations": list(set(all_recommendations))[:5],
            "disclaimer": "This is not a diagnosis. Always consult a healthcare provider.",
        }
    
    def get_follow_up_questions(self, symptom: str) -> List[str]:
        """Get follow-up questions for a symptom."""
        result = self.check_symptom(symptom)
        if result:
            return result.get("questions_to_ask", [])
        return [
            "When did this symptom start?",
            "How severe is it on a scale of 1-10?",
            "What makes it better or worse?",
            "Do you have any other symptoms?",
        ]
    
    def to_rag_documents(self) -> List[Dict[str, Any]]:
        """
        Convert symptoms to format suitable for RAG indexing.
        
        Returns:
            List of documents ready for vector store
        """
        documents = []
        
        for symptom in self._symptoms.values():
            documents.append({
                "id": f"symptom_{symptom.id}",
                "content": symptom.to_content(),
                "metadata": {
                    "symptom": symptom.symptom,
                    "category": symptom.category.value,
                    "urgency": symptom.urgency.value,
                    "type": "symptom_info",
                },
            })
        
        return documents


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_checker_instance: Optional[SymptomChecker] = None


def get_symptom_checker() -> SymptomChecker:
    """Get singleton instance of SymptomChecker."""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = SymptomChecker()
    return _checker_instance


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Testing SymptomChecker...")
    
    checker = get_symptom_checker()
    
    # Test symptom lookup
    print("\n🩺 Checking 'chest pain':")
    result = checker.check_symptom("chest pain")
    if result:
        print(f"  Symptom: {result['symptom']}")
        print(f"  Urgency: {result['urgency']}")
        print(f"  Possible conditions: {', '.join(result['possible_conditions'][:3])}...")
    
    # Test red flag detection
    print("\n🚨 Red flag detection:")
    test_cases = [
        ["chest pain"],
        ["chest pain", "arm pain", "sweating"],
        ["mild fatigue"],
        ["face drooping", "arm weakness"],
    ]
    for symptoms in test_cases:
        is_emergency = checker.has_red_flags(symptoms)
        status = "🔴 EMERGENCY" if is_emergency else "🟢 Not emergency"
        print(f"  {symptoms} -> {status}")
    
    # Test triage
    print("\n📋 Triage test:")
    triage = checker.triage_symptoms(["shortness of breath", "leg swelling"])
    print(f"  Urgency: {triage['urgency']}")
    print(f"  Message: {triage['message']}")
    
    # Test follow-up questions
    print("\n❓ Follow-up questions for 'palpitations':")
    questions = checker.get_follow_up_questions("palpitations")
    for q in questions[:3]:
        print(f"  - {q}")
    
    # Test RAG documents
    rag_docs = checker.to_rag_documents()
    print(f"\n📄 RAG documents ready: {len(rag_docs)}")
    
    print("\n✅ SymptomChecker tests passed!")
