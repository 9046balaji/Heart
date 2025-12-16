"""
PHASE 2 TASK 2.4: Unified Keyword Database

Consolidates all keywords from intent_recognizer, sentiment_analyzer,
entity_extractor, and risk_assessor into a single source of truth.

Uses Enum + Flag pattern for multi-category keywords.

Benefits:
- Single point of maintenance
- Consistent updates across all components
- Easy to add new keywords
- Reduced code duplication
- Type-safe keyword references
"""

from enum import Enum, Flag, auto
from typing import Dict, List, Set, FrozenSet


class KeywordCategory(Flag):
    """Multi-category keyword classification"""
    INTENT = auto()
    SENTIMENT = auto()
    ENTITY = auto()
    RISK = auto()
    SYMPTOM = auto()
    MEDICATION = auto()
    FOOD = auto()
    ACTIVITY = auto()


class IntentKeywords(str, Enum):
    """Intent-specific keywords grouped by intent type"""
    
    # GREETING
    HELLO = "hello"
    HI = "hi"
    HEY = "hey"
    GOOD_MORNING = "good morning"
    GOOD_AFTERNOON = "good afternoon"
    GOOD_EVENING = "good evening"
    HOWDY = "howdy"
    GREETINGS = "greetings"
    WELCOME = "welcome"
    
    # RISK_ASSESSMENT
    RISK = "risk"
    HEART_DISEASE = "heart disease"
    ASSESSMENT = "assessment"
    CHANCE = "chance"
    PROBABILITY = "probability"
    WHATS_MY_RISK = "what's my risk"
    AM_I_AT_RISK = "am i at risk"
    RISK_HEART_ATTACK = "risk of heart attack"
    LIKELIHOOD = "likelihood"
    CALCULATE_RISK = "calculate risk"
    EVALUATE_RISK = "evaluate risk"
    
    # NUTRITION_ADVICE
    EAT = "eat"
    FOOD = "food"
    MEAL = "meal"
    NUTRITION = "nutrition"
    DIET = "diet"
    CALORIES = "calories"
    HEALTHY_EATING = "healthy eating"
    RECIPES = "recipes"
    MEAL_PLAN = "meal plan"
    WHAT_SHOULD_I_EAT = "what should i eat"
    FOOD_RECOMMENDATIONS = "food recommendations"
    DIETARY = "dietary"
    NUTRITION_PLAN = "nutrition plan"
    
    # EXERCISE_COACHING
    EXERCISE = "exercise"
    WORKOUT = "workout"
    FITNESS = "fitness"
    TRAINING = "training"
    CARDIO = "cardio"
    PHYSICAL_ACTIVITY = "physical activity"
    WORKOUT_PLAN = "workout plan"
    EXERCISE_ROUTINE = "exercise routine"
    GYM = "gym"
    RUNNING = "running"
    CYCLING = "cycling"
    SPORTS = "sports"
    ACTIVITY = "activity"
    
    # MEDICATION_REMINDER
    MEDICATION = "medication"
    PILL = "pill"
    MEDICINE = "medicine"
    DOSE = "dose"
    PRESCRIPTION = "prescription"
    TAKE_MEDICATION = "take medication"
    MEDICINE_REMINDER = "medicine reminder"
    DOSAGE = "dosage"
    REFILL = "refill"
    PHARMACY = "pharmacy"
    DRUG = "drug"
    
    # SYMPTOM_CHECK
    PAIN = "pain"
    SYMPTOM = "symptom"
    FEEL = "feel"
    HURT = "hurt"
    DISCOMFORT = "discomfort"
    ACHE = "ache"
    FEELING = "feeling"
    EXPERIENCE = "experience"
    HAVING = "having"
    CHEST = "chest"
    
    # HEALTH_GOAL
    GOAL = "goal"
    TARGET = "target"
    ACHIEVE = "achieve"
    IMPROVE = "improve"
    WANT_TO = "want to"
    WEIGHT_LOSS = "weight loss"
    FITNESS_GOAL = "fitness goal"
    HEALTH_GOAL = "health goal"
    PROGRESS = "progress"
    TRACK = "track"
    MONITOR = "monitor"
    
    # HEALTH_EDUCATION
    LEARN = "learn"
    TEACH = "teach"
    EDUCATION = "education"
    INFORMATION = "information"
    KNOW = "know"
    UNDERSTAND = "understand"
    EXPLAIN = "explain"
    TELL_ME_ABOUT = "tell me about"
    WHAT_IS = "what is"
    HOW_DOES = "how does"
    EDUCATIONAL = "educational"
    FACTS = "facts"
    
    # APPOINTMENT_BOOKING
    APPOINTMENT = "appointment"
    DOCTOR = "doctor"
    BOOKING = "booking"
    SCHEDULE = "schedule"
    VISIT = "visit"
    MEETING = "meeting"
    CONSULTATION = "consultation"
    HEALTHCARE_PROVIDER = "healthcare provider"
    MAKE_APPOINTMENT = "make an appointment"
    BOOK_APPOINTMENT = "book appointment"


class SentimentKeywords(str, Enum):
    """Sentiment analysis keywords"""
    
    # POSITIVE
    GOOD = "good"
    GREAT = "great"
    EXCELLENT = "excellent"
    AMAZING = "amazing"
    WONDERFUL = "wonderful"
    FANTASTIC = "fantastic"
    AWESOME = "awesome"
    PERFECT = "perfect"
    BETTER = "better"
    BEST = "best"
    LOVE = "love"
    HAPPY = "happy"
    GLAD = "glad"
    GRATEFUL = "grateful"
    THANKS = "thanks"
    APPRECIATE = "appreciate"
    
    # NEGATIVE
    BAD = "bad"
    TERRIBLE = "terrible"
    AWFUL = "awful"
    HORRIBLE = "horrible"
    POOR = "poor"
    WORSE = "worse"
    WORST = "worst"
    HATE = "hate"
    ANGRY = "angry"
    SAD = "sad"
    DEPRESSED = "depressed"
    FRUSTRATED = "frustrated"
    DISAPPOINTED = "disappointed"
    ANXIOUS = "anxious"
    
    # NEUTRAL/DISTRESSED
    OKAY = "okay"
    FINE = "fine"
    CONCERNED = "concerned"
    URGENT = "urgent"
    EMERGENCY = "emergency"
    CRITICAL = "critical"
    SEVERE = "severe"
    SERIOUS = "serious"
    WORRIED = "worried"


class SymptomKeywords(str, Enum):
    """Cardiovascular symptom keywords"""
    
    # CHEST SYMPTOMS
    CHEST_PAIN = "chest pain"
    CHEST_PRESSURE = "chest pressure"
    CHEST_TIGHTNESS = "chest tightness"
    CHEST_DISCOMFORT = "chest discomfort"
    
    # BREATHING
    SHORTNESS_OF_BREATH = "shortness of breath"
    DIFFICULTY_BREATHING = "difficulty breathing"
    BREATHLESSNESS = "breathlessness"
    DYSPNEA = "dyspnea"
    
    # HEART RATE
    PALPITATIONS = "palpitations"
    IRREGULAR_HEARTBEAT = "irregular heartbeat"
    HEART_RACING = "heart racing"
    RAPID_HEART_RATE = "rapid heart rate"
    
    # GENERAL
    FATIGUE = "fatigue"
    WEAKNESS = "weakness"
    DIZZINESS = "dizziness"
    LIGHTHEADEDNESS = "lightheadedness"
    NAUSEA = "nausea"
    SWEATING = "sweating"
    COLD_SWEAT = "cold sweat"


class MedicationKeywords(str, Enum):
    """Medication and drug-related keywords"""
    
    STATIN = "statin"
    ASPIRIN = "aspirin"
    BETA_BLOCKER = "beta blocker"
    ACE_INHIBITOR = "ace inhibitor"
    BLOOD_PRESSURE = "blood pressure"
    ANTICOAGULANT = "anticoagulant"
    ANTIPLATELET = "antiplatelet"
    DIURETIC = "diuretic"
    NITROGLYCERIN = "nitroglycerin"


class FoodKeywords(str, Enum):
    """Heart-healthy and unhealthy foods"""
    
    # HEALTHY
    SALMON = "salmon"
    SARDINES = "sardines"
    MACKEREL = "mackerel"
    ALMONDS = "almonds"
    WALNUTS = "walnuts"
    BERRIES = "berries"
    APPLE = "apple"
    ORANGE = "orange"
    OLIVE_OIL = "olive oil"
    WHOLE_WHEAT = "whole wheat"
    BEANS = "beans"
    LENTILS = "lentils"
    
    # UNHEALTHY
    SATURATED_FAT = "saturated fat"
    TRANS_FAT = "trans fat"
    FRIED = "fried"
    FAST_FOOD = "fast food"
    SALT = "salt"
    SODIUM = "sodium"
    SUGAR = "sugar"
    SODA = "soda"
    CANDY = "candy"
    PROCESSED = "processed"


class ActivityKeywords(str, Enum):
    """Physical activity keywords"""
    
    WALKING = "walking"
    JOGGING = "jogging"
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    YOGA = "yoga"
    PILATES = "pilates"
    STRENGTH_TRAINING = "strength training"
    WEIGHT_LIFTING = "weight lifting"
    AEROBIC = "aerobic"
    INTERVAL_TRAINING = "interval training"
    STRETCHING = "stretching"


class UnifiedKeywordDatabase:
    """
    Unified keyword database for all NLP components.
    
    Provides centralized keyword management with:
    - Intent keywords (9 categories)
    - Sentiment keywords (positive, negative, distressed)
    - Symptom keywords (cardiovascular)
    - Medication keywords
    - Food keywords (healthy/unhealthy)
    - Activity keywords
    """

    # Intent keyword groups
    INTENT_GROUPS: Dict[str, List[str]] = {
        "GREETING": [kw.value for kw in IntentKeywords if kw.name.isupper() and any(c in kw.name for c in "HELLO HI HEY GOOD HOWDY GREETINGS WELCOME".split())],
        "RISK_ASSESSMENT": [kw.value for kw in IntentKeywords if "RISK" in kw.name or "ASSESSMENT" in kw.name or "CHANCE" in kw.name or "PROBABILITY" in kw.name],
        "NUTRITION_ADVICE": [kw.value for kw in IntentKeywords if any(x in kw.name for x in ["EAT", "FOOD", "MEAL", "NUTRITION", "DIET", "CALORIES", "EATING", "RECIPES"])],
        "EXERCISE_COACHING": [kw.value for kw in IntentKeywords if any(x in kw.name for x in ["EXERCISE", "WORKOUT", "FITNESS", "TRAINING", "CARDIO", "ACTIVITY", "GYM", "RUNNING", "CYCLING", "SPORTS"])],
        "MEDICATION_REMINDER": [kw.value for kw in IntentKeywords if any(x in kw.name for x in ["MEDICATION", "PILL", "MEDICINE", "DOSE", "PRESCRIPTION", "DOSAGE", "REFILL", "PHARMACY", "DRUG"])],
        "SYMPTOM_CHECK": [kw.value for kw in IntentKeywords if any(x in kw.name for x in ["PAIN", "SYMPTOM", "FEEL", "HURT", "DISCOMFORT", "ACHE", "FEELING", "EXPERIENCE", "HAVING", "CHEST"])],
        "HEALTH_GOAL": [kw.value for kw in IntentKeywords if any(x in kw.name for x in ["GOAL", "TARGET", "ACHIEVE", "IMPROVE", "WEIGHT_LOSS", "FITNESS_GOAL", "HEALTH_GOAL", "PROGRESS", "TRACK", "MONITOR"])],
        "HEALTH_EDUCATION": [kw.value for kw in IntentKeywords if any(x in kw.name for x in ["LEARN", "TEACH", "EDUCATION", "INFORMATION", "KNOW", "UNDERSTAND", "EXPLAIN", "TELL", "WHAT", "HOW", "EDUCATIONAL", "FACTS"])],
        "APPOINTMENT_BOOKING": [kw.value for kw in IntentKeywords if any(x in kw.name for x in ["APPOINTMENT", "DOCTOR", "BOOKING", "SCHEDULE", "VISIT", "MEETING", "CONSULTATION", "HEALTHCARE_PROVIDER", "BOOK"])],
    }

    # Sentiment keyword groups
    SENTIMENT_GROUPS: Dict[str, List[str]] = {
        "POSITIVE": [kw.value for kw in SentimentKeywords if kw.name in ["GOOD", "GREAT", "EXCELLENT", "AMAZING", "WONDERFUL", "FANTASTIC", "AWESOME", "PERFECT", "BETTER", "BEST", "LOVE", "HAPPY", "GLAD", "GRATEFUL", "THANKS", "APPRECIATE"]],
        "NEGATIVE": [kw.value for kw in SentimentKeywords if kw.name in ["BAD", "TERRIBLE", "AWFUL", "HORRIBLE", "POOR", "WORSE", "WORST", "HATE", "ANGRY", "SAD", "DEPRESSED", "FRUSTRATED", "DISAPPOINTED", "WORRIED", "ANXIOUS"]],
        "DISTRESSED": [kw.value for kw in SentimentKeywords if kw.name in ["URGENT", "EMERGENCY", "CRITICAL", "SEVERE", "SERIOUS"]],
    }

    @classmethod
    def get_intent_keywords(cls, intent_name: str) -> List[str]:
        """Get keywords for a specific intent"""
        return cls.INTENT_GROUPS.get(intent_name, [])

    @classmethod
    def get_sentiment_keywords(cls, sentiment_type: str) -> List[str]:
        """Get keywords for a specific sentiment type"""
        return cls.SENTIMENT_GROUPS.get(sentiment_type, [])

    @classmethod
    def get_all_symptoms(cls) -> List[str]:
        """Get all symptom keywords"""
        return [kw.value for kw in SymptomKeywords]

    @classmethod
    def get_all_medications(cls) -> List[str]:
        """Get all medication keywords"""
        return [kw.value for kw in MedicationKeywords]

    @classmethod
    def get_all_foods(cls) -> List[str]:
        """Get all food keywords"""
        return [kw.value for kw in FoodKeywords]

    @classmethod
    def get_all_activities(cls) -> List[str]:
        """Get all activity keywords"""
        return [kw.value for kw in ActivityKeywords]

    @classmethod
    def get_healthy_foods(cls) -> List[str]:
        """Get healthy food keywords"""
        healthy = [
            "salmon", "sardines", "mackerel", "almonds", "walnuts",
            "berries", "apple", "orange", "olive oil", "whole wheat",
            "beans", "lentils"
        ]
        return healthy

    @classmethod
    def get_unhealthy_foods(cls) -> List[str]:
        """Get unhealthy food keywords"""
        unhealthy = [
            "saturated fat", "trans fat", "fried", "fast food",
            "salt", "sodium", "sugar", "soda", "candy", "processed"
        ]
        return unhealthy

    @classmethod
    def is_symptom(cls, word: str) -> bool:
        """Check if word is a known symptom"""
        return word.lower() in [kw.value for kw in SymptomKeywords]

    @classmethod
    def is_medication(cls, word: str) -> bool:
        """Check if word is a known medication"""
        return word.lower() in [kw.value for kw in MedicationKeywords]

    @classmethod
    def is_healthy_food(cls, word: str) -> bool:
        """Check if word is a healthy food"""
        return word.lower() in cls.get_healthy_foods()

    @classmethod
    def is_unhealthy_food(cls, word: str) -> bool:
        """Check if word is an unhealthy food"""
        return word.lower() in cls.get_unhealthy_foods()


# USAGE EXAMPLES
if __name__ == "__main__":
    # Get intent keywords
    greeting_keywords = UnifiedKeywordDatabase.get_intent_keywords("GREETING")
    print(f"Greeting keywords: {greeting_keywords}")

    # Check if word is a symptom
    is_symptom = UnifiedKeywordDatabase.is_symptom("chest pain")
    print(f"'chest pain' is symptom: {is_symptom}")

    # Get all healthy foods
    healthy = UnifiedKeywordDatabase.get_healthy_foods()
    print(f"Healthy foods: {healthy}")

    # Get sentiment keywords
    positive = UnifiedKeywordDatabase.get_sentiment_keywords("POSITIVE")
    print(f"Positive sentiment keywords: {positive}")
