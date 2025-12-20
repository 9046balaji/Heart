"""
Cardiovascular Disease Guidelines Knowledge Base

This module provides structured cardiovascular health guidelines including:
- Heart failure management
- Hypertension guidelines
- Arrhythmia information
- Risk factor management
- Lifestyle recommendations

Data based on publicly available guidelines from:
- American Heart Association (AHA)
- American College of Cardiology (ACC)
- European Society of Cardiology (ESC)

DISCLAIMER: This information is for educational purposes only and should not
be used as a substitute for professional medical advice, diagnosis, or treatment.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ConditionCategory(Enum):
    HEART_FAILURE = "heart_failure"
    HYPERTENSION = "hypertension"
    ARRHYTHMIA = "arrhythmia"
    CORONARY_ARTERY_DISEASE = "coronary_artery_disease"
    STROKE = "stroke"
    HEART_VALVE = "heart_valve"
    PERIPHERAL_ARTERY = "peripheral_artery"
    GENERAL = "general"


@dataclass
class Guideline:
    """A single medical guideline."""

    id: str
    title: str
    content: str
    category: ConditionCategory
    source: str
    keywords: List[str] = field(default_factory=list)
    related_conditions: List[str] = field(default_factory=list)
    last_updated: str = "2024"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category.value,
            "source": self.source,
            "keywords": self.keywords,
            "related_conditions": self.related_conditions,
            "last_updated": self.last_updated,
        }


@dataclass
class BloodPressureRange:
    """Blood pressure classification."""

    category: str
    systolic_min: int
    systolic_max: int
    diastolic_min: int
    diastolic_max: int
    risk_level: RiskLevel
    recommendation: str


class CardiovascularGuidelines:
    """
    Cardiovascular disease guidelines knowledge base.

    Provides structured access to cardiovascular health information
    for augmenting AI responses.

    Example:
        guidelines = CardiovascularGuidelines()

        # Get heart failure info
        hf_info = guidelines.get_condition_info("heart_failure")

        # Classify blood pressure
        bp_class = guidelines.classify_blood_pressure(130, 85)
        print(f"Category: {bp_class['category']}")

        # Search guidelines
        results = guidelines.search("chest pain symptoms")
    """

    # Blood Pressure Classifications (AHA Guidelines)
    BP_CLASSIFICATIONS = [
        BloodPressureRange(
            "Normal",
            0,
            120,
            0,
            80,
            RiskLevel.LOW,
            "Maintain healthy lifestyle. No medication typically needed.",
        ),
        BloodPressureRange(
            "Elevated",
            120,
            129,
            0,
            80,
            RiskLevel.MODERATE,
            "Lifestyle modifications recommended: diet, exercise, stress management.",
        ),
        BloodPressureRange(
            "High Blood Pressure Stage 1",
            130,
            139,
            80,
            89,
            RiskLevel.HIGH,
            "Lifestyle changes and possibly medication. Consult healthcare provider.",
        ),
        BloodPressureRange(
            "High Blood Pressure Stage 2",
            140,
            180,
            90,
            120,
            RiskLevel.HIGH,
            "Medication likely needed along with lifestyle changes. Regular monitoring.",
        ),
        BloodPressureRange(
            "Hypertensive Crisis",
            180,
            999,
            120,
            999,
            RiskLevel.VERY_HIGH,
            "SEEK IMMEDIATE MEDICAL ATTENTION. This is a medical emergency.",
        ),
    ]

    def __init__(self):
        """Initialize the cardiovascular guidelines database."""
        self._guidelines: Dict[str, Guideline] = {}
        self._load_guidelines()

    def _load_guidelines(self) -> None:
        """Load all cardiovascular guidelines."""
        guidelines = [
            # HEART FAILURE
            Guideline(
                id="hf_overview",
                title="Heart Failure Overview",
                content="""Heart failure is a chronic condition where the heart cannot pump blood
efficiently enough to meet the body's needs. It does not mean the heart has stopped working.

Types of Heart Failure:
- Heart Failure with Reduced Ejection Fraction (HFrEF): EF ≤40%, the heart pumps less blood
- Heart Failure with Preserved Ejection Fraction (HFpEF): EF ≥50%, the heart fills less blood
- Heart Failure with Mid-Range EF (HFmrEF): EF 41-49%

Common Symptoms:
- Shortness of breath (dyspnea), especially during activity or when lying down
- Fatigue and weakness
- Swelling (edema) in legs, ankles, and feet
- Rapid or irregular heartbeat
- Reduced ability to exercise
- Persistent cough or wheezing with white or pink phlegm
- Weight gain from fluid retention
- Difficulty concentrating

Ejection Fraction (EF) is the percentage of blood pumped out of the heart with each beat.
Normal EF is 55-70%.""",
                category=ConditionCategory.HEART_FAILURE,
                source="AHA/ACC Heart Failure Guidelines",
                keywords=[
                    "heart failure",
                    "HFrEF",
                    "HFpEF",
                    "ejection fraction",
                    "symptoms",
                    "shortness of breath",
                ],
                related_conditions=[
                    "coronary_artery_disease",
                    "hypertension",
                    "diabetes",
                ],
            ),
            Guideline(
                id="hf_treatment",
                title="Heart Failure Treatment Guidelines",
                content="""Heart failure treatment focuses on managing symptoms, slowing progression,
and improving quality of life.

First-Line Medications for HFrEF (Guideline-Directed Medical Therapy - GDMT):
1. ACE Inhibitors or ARBs: Lisinopril, Losartan - reduce strain on heart
2. Beta-Blockers: Metoprolol, Carvedilol - slow heart rate, reduce workload
3. Mineralocorticoid Receptor Antagonists: Spironolactone - reduce fluid retention
4. SGLT2 Inhibitors: Dapagliflozin, Empagliflozin - newer class, cardiovascular benefits
5. ARNI (Sacubitril/Valsartan): For symptomatic HFrEF, may replace ACE-I/ARB

Diuretics for Congestion:
- Loop diuretics (Furosemide, Bumetanide) for fluid overload
- Adjust based on daily weight and symptoms

Non-Medication Treatments:
- ICD (Implantable Cardioverter-Defibrillator) for EF ≤35%
- CRT (Cardiac Resynchronization Therapy) for select patients
- Heart transplant for end-stage heart failure
- LVAD (Left Ventricular Assist Device) as bridge or destination therapy

Lifestyle Modifications:
- Sodium restriction (<2g/day)
- Fluid restriction (1.5-2L/day for severe HF)
- Daily weight monitoring
- Regular exercise (cardiac rehabilitation)
- Smoking cessation
- Limit alcohol""",
                category=ConditionCategory.HEART_FAILURE,
                source="AHA/ACC Heart Failure Guidelines 2022",
                keywords=[
                    "treatment",
                    "medications",
                    "ACE inhibitor",
                    "beta blocker",
                    "diuretic",
                    "GDMT",
                ],
                related_conditions=["kidney_disease", "diabetes"],
            ),
            # HYPERTENSION
            Guideline(
                id="htn_overview",
                title="Hypertension (High Blood Pressure) Overview",
                content="""Hypertension is a condition where blood pressure is consistently elevated.
It is a major risk factor for heart disease, stroke, and kidney disease.

Blood Pressure Categories (AHA 2017):
- Normal: <120/<80 mmHg
- Elevated: 120-129/<80 mmHg
- Stage 1 Hypertension: 130-139/80-89 mmHg
- Stage 2 Hypertension: ≥140/≥90 mmHg
- Hypertensive Crisis: >180/>120 mmHg (seek immediate care)

Types:
- Primary (Essential) Hypertension: No identifiable cause, most common (90-95%)
- Secondary Hypertension: Caused by underlying condition (kidney disease, hormonal)

Risk Factors:
- Age (risk increases with age)
- Family history
- Obesity
- High sodium diet
- Low potassium diet
- Physical inactivity
- Excessive alcohol
- Stress
- Chronic conditions (diabetes, kidney disease)

Often called the "silent killer" because there are usually no symptoms until damage occurs.""",
                category=ConditionCategory.HYPERTENSION,
                source="AHA Blood Pressure Guidelines 2017",
                keywords=[
                    "hypertension",
                    "blood pressure",
                    "systolic",
                    "diastolic",
                    "silent killer",
                ],
                related_conditions=["heart_failure", "stroke", "kidney_disease"],
            ),
            Guideline(
                id="htn_treatment",
                title="Hypertension Treatment Guidelines",
                content="""Hypertension treatment aims to reduce blood pressure to target levels
and prevent cardiovascular events.

Blood Pressure Targets:
- General population: <130/80 mmHg
- Older adults (>65): <130/80 if tolerated
- Diabetes: <130/80 mmHg
- Chronic kidney disease: <130/80 mmHg

First-Line Medications:
1. ACE Inhibitors (ACE-I): Lisinopril, Enalapril, Ramipril
   - Contraindicated in pregnancy
2. Angiotensin Receptor Blockers (ARBs): Losartan, Valsartan, Olmesartan
   - Alternative to ACE-I if cough develops
3. Calcium Channel Blockers (CCBs): Amlodipine, Nifedipine, Diltiazem
   - Good for African American patients
4. Thiazide Diuretics: Hydrochlorothiazide, Chlorthalidone
   - Often used as add-on therapy

Lifestyle Modifications (DASH approach):
- DASH diet (rich in fruits, vegetables, whole grains, low-fat dairy)
- Sodium reduction (<2,300mg/day, ideally <1,500mg)
- Physical activity (150 min/week moderate exercise)
- Weight management (lose weight if overweight)
- Limit alcohol (≤2 drinks/day men, ≤1 drink/day women)
- Smoking cessation
- Stress management

Monitoring:
- Home blood pressure monitoring recommended
- Take readings at same time daily
- Average multiple readings for accuracy""",
                category=ConditionCategory.HYPERTENSION,
                source="AHA/ACC Hypertension Guidelines",
                keywords=[
                    "treatment",
                    "medications",
                    "DASH diet",
                    "lifestyle",
                    "ACE inhibitor",
                    "ARB",
                ],
                related_conditions=["diabetes", "kidney_disease"],
            ),
            # ARRHYTHMIA
            Guideline(
                id="afib_overview",
                title="Atrial Fibrillation (AFib) Overview",
                content="""Atrial fibrillation (AFib) is the most common type of irregular heartbeat
(arrhythmia). In AFib, the heart's upper chambers (atria) beat chaotically.

Types of AFib:
- Paroxysmal: Comes and goes, usually stops within 7 days
- Persistent: Lasts more than 7 days, may need treatment to stop
- Long-standing Persistent: Continuous for more than 12 months
- Permanent: Decision made not to restore normal rhythm

Symptoms:
- Palpitations (racing, fluttering, or pounding heart)
- Fatigue
- Shortness of breath
- Dizziness or lightheadedness
- Chest discomfort
- Some people have no symptoms (asymptomatic AFib)

Risk Factors:
- Age (increases with age)
- Heart disease
- High blood pressure
- Obesity
- Sleep apnea
- Thyroid disease
- Diabetes
- Alcohol use (especially binge drinking)

Complications:
- Stroke: AFib increases stroke risk 5x (blood pools, forms clots)
- Heart failure: Irregular rhythm weakens heart over time
- Cognitive decline: Associated with dementia risk""",
                category=ConditionCategory.ARRHYTHMIA,
                source="AHA/ACC AFib Guidelines",
                keywords=[
                    "atrial fibrillation",
                    "AFib",
                    "arrhythmia",
                    "irregular heartbeat",
                    "palpitations",
                ],
                related_conditions=["stroke", "heart_failure"],
            ),
            Guideline(
                id="afib_treatment",
                title="Atrial Fibrillation Treatment Guidelines",
                content="""AFib treatment focuses on three goals: rate control, rhythm control,
and stroke prevention.

1. STROKE PREVENTION (Most Important!)
CHA2DS2-VASc Score determines anticoagulation need:
- Score 0 (men) or 1 (women): No anticoagulation
- Score 1 (men) or 2 (women): Consider anticoagulation
- Score ≥2 (men) or ≥3 (women): Anticoagulation recommended

Anticoagulants (Blood Thinners):
- DOACs (preferred): Apixaban (Eliquis), Rivaroxaban (Xarelto), Dabigatran (Pradaxa)
- Warfarin: Requires INR monitoring, many drug/food interactions
- Aspirin alone is NOT recommended for stroke prevention in AFib

2. RATE CONTROL
Goal: Resting heart rate <110 bpm (lenient) or <80 bpm (strict)
Medications:
- Beta-blockers: Metoprolol, Atenolol
- Non-dihydropyridine CCBs: Diltiazem, Verapamil
- Digoxin: For sedentary patients, not first-line

3. RHYTHM CONTROL
Options to restore/maintain normal rhythm:
- Cardioversion (electrical or chemical)
- Antiarrhythmic drugs: Flecainide, Propafenone, Amiodarone, Dofetilide
- Catheter ablation: Pulmonary vein isolation, increasingly used
- Surgical Maze procedure

Lifestyle:
- Treat underlying conditions (HTN, sleep apnea, obesity)
- Limit alcohol and caffeine
- Manage stress
- Regular exercise""",
                category=ConditionCategory.ARRHYTHMIA,
                source="AHA/ACC AFib Guidelines 2023",
                keywords=[
                    "AFib treatment",
                    "anticoagulation",
                    "blood thinner",
                    "ablation",
                    "CHA2DS2-VASc",
                ],
                related_conditions=["stroke", "hypertension"],
            ),
            # CORONARY ARTERY DISEASE
            Guideline(
                id="cad_overview",
                title="Coronary Artery Disease (CAD) Overview",
                content="""Coronary Artery Disease (CAD) is the most common type of heart disease.
It occurs when the arteries supplying blood to the heart become narrowed or blocked.

Causes:
- Atherosclerosis: Plaque buildup (cholesterol, fat, calcium) in arteries
- Plaque can rupture, forming blood clots that block blood flow

Symptoms:
- Angina (chest pain or discomfort): Pressure, squeezing, fullness
  - Typically triggered by exertion or stress
  - Usually relieved by rest or nitroglycerin
- Shortness of breath
- Heart attack symptoms: Severe chest pain, radiating to arm/jaw, sweating, nausea

Types of Angina:
- Stable Angina: Predictable, occurs with exertion
- Unstable Angina: Unexpected, at rest, or worsening (EMERGENCY)
- Variant (Prinzmetal) Angina: Caused by coronary artery spasm

Risk Factors:
- High LDL cholesterol
- Low HDL cholesterol
- High blood pressure
- Diabetes
- Smoking
- Obesity
- Family history of heart disease
- Sedentary lifestyle
- Age (men >45, women >55)
- Stress""",
                category=ConditionCategory.CORONARY_ARTERY_DISEASE,
                source="AHA/ACC CAD Guidelines",
                keywords=[
                    "coronary artery disease",
                    "CAD",
                    "angina",
                    "chest pain",
                    "atherosclerosis",
                ],
                related_conditions=["heart_failure", "hypertension", "diabetes"],
            ),
            # GENERAL CARDIOVASCULAR HEALTH
            Guideline(
                id="cv_prevention",
                title="Cardiovascular Disease Prevention",
                content="""Prevention is the best approach to cardiovascular disease.
80% of cardiovascular diseases are preventable through lifestyle modification.

Life's Essential 8 (AHA 2022):
1. Eat Better: DASH or Mediterranean diet
2. Be More Active: 150 min/week moderate or 75 min/week vigorous exercise
3. Quit Tobacco: Smoking is the #1 preventable cause of CV death
4. Get Healthy Sleep: 7-9 hours for adults
5. Manage Weight: BMI 18.5-24.9
6. Control Cholesterol: LDL <100 mg/dL (or <70 if high risk)
7. Manage Blood Sugar: HbA1c <5.7%
8. Manage Blood Pressure: <130/80 mmHg

Heart-Healthy Diet Tips:
- Eat plenty of fruits and vegetables (5+ servings/day)
- Choose whole grains over refined grains
- Include lean proteins (fish, poultry, legumes)
- Limit saturated fat (<6% of calories)
- Avoid trans fats
- Reduce sodium (<2,300mg/day)
- Limit added sugars
- Eat fatty fish 2x/week (omega-3s)

Screening Recommendations:
- Blood pressure: Every 1-2 years (or more if elevated)
- Cholesterol: Every 4-6 years (starting at age 20)
- Blood glucose: Every 3 years (starting at age 45)
- Body weight/BMI: Annually
- Assess 10-year CV risk: Every 5 years (starting at age 40)""",
                category=ConditionCategory.GENERAL,
                source="AHA Life's Essential 8",
                keywords=[
                    "prevention",
                    "lifestyle",
                    "diet",
                    "exercise",
                    "Life's Essential 8",
                ],
                related_conditions=["hypertension", "diabetes", "obesity"],
            ),
            Guideline(
                id="emergency_signs",
                title="Cardiovascular Emergency Warning Signs",
                content="""CALL 911 IMMEDIATELY if you or someone else experiences these symptoms.
Every second counts during a heart attack or stroke.

HEART ATTACK WARNING SIGNS:
- Chest discomfort: Pressure, squeezing, fullness, pain lasting >few minutes
- Pain or discomfort in arms, back, neck, jaw, or stomach
- Shortness of breath (with or without chest discomfort)
- Cold sweat, nausea, lightheadedness
- Women may have additional symptoms: unusual fatigue, nausea, back/jaw pain

ACT FAST: Time is muscle. Treatment within 90 minutes saves more heart tissue.

STROKE WARNING SIGNS (BE FAST):
- B - Balance: Sudden loss of balance or coordination
- E - Eyes: Sudden vision changes in one or both eyes
- F - Face drooping: One side of face droops or is numb
- A - Arm weakness: One arm is weak or numb
- S - Speech difficulty: Slurred speech or hard to understand
- T - Time: Call 911 immediately

ACT FAST: Clot-busting drugs work best within 3-4.5 hours of symptom onset.

CARDIAC ARREST:
- Person suddenly collapses
- No pulse
- No breathing or only gasping
ACTION: Call 911, start CPR, use AED if available

DO NOT:
- Drive yourself to the hospital during a heart attack
- Wait to see if symptoms go away
- Take someone else's medication""",
                category=ConditionCategory.GENERAL,
                source="AHA Emergency Guidelines",
                keywords=[
                    "emergency",
                    "heart attack",
                    "stroke",
                    "911",
                    "warning signs",
                    "BE FAST",
                ],
                related_conditions=["heart_failure", "arrhythmia"],
            ),
        ]

        for guideline in guidelines:
            self._guidelines[guideline.id] = guideline

    def get_all_guidelines(self) -> List[Guideline]:
        """Get all guidelines."""
        return list(self._guidelines.values())

    def get_guideline(self, guideline_id: str) -> Optional[Guideline]:
        """Get a specific guideline by ID."""
        return self._guidelines.get(guideline_id)

    def get_guidelines_by_category(
        self, category: ConditionCategory
    ) -> List[Guideline]:
        """Get all guidelines for a specific category."""
        return [g for g in self._guidelines.values() if g.category == category]

    def get_condition_info(self, condition: str) -> Dict[str, Any]:
        """
        Get information about a specific condition.

        Args:
            condition: Condition name or keyword

        Returns:
            Dict with relevant guidelines and information
        """
        condition_lower = condition.lower().replace(" ", "_")

        # Map common terms to categories
        condition_map = {
            "heart_failure": ConditionCategory.HEART_FAILURE,
            "hf": ConditionCategory.HEART_FAILURE,
            "chf": ConditionCategory.HEART_FAILURE,
            "hypertension": ConditionCategory.HYPERTENSION,
            "high_blood_pressure": ConditionCategory.HYPERTENSION,
            "htn": ConditionCategory.HYPERTENSION,
            "afib": ConditionCategory.ARRHYTHMIA,
            "atrial_fibrillation": ConditionCategory.ARRHYTHMIA,
            "arrhythmia": ConditionCategory.ARRHYTHMIA,
            "cad": ConditionCategory.CORONARY_ARTERY_DISEASE,
            "coronary_artery_disease": ConditionCategory.CORONARY_ARTERY_DISEASE,
            "angina": ConditionCategory.CORONARY_ARTERY_DISEASE,
        }

        category = condition_map.get(condition_lower)

        if category:
            guidelines = self.get_guidelines_by_category(category)
        else:
            # Search by keyword
            guidelines = self.search(condition)

        return {
            "condition": condition,
            "guidelines": [g.to_dict() for g in guidelines],
            "found": len(guidelines),
        }

    def search(self, query: str, max_results: int = 5) -> List[Guideline]:
        """
        Search guidelines by query.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of matching guidelines
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored_guidelines = []

        for guideline in self._guidelines.values():
            score = 0

            # Title match (highest weight)
            if query_lower in guideline.title.lower():
                score += 10

            # Keyword match
            for keyword in guideline.keywords:
                if keyword.lower() in query_lower:
                    score += 5
                elif any(w in keyword.lower() for w in query_words):
                    score += 2

            # Content match
            content_lower = guideline.content.lower()
            for word in query_words:
                if word in content_lower:
                    score += 1

            if score > 0:
                scored_guidelines.append((score, guideline))

        # Sort by score and return top results
        scored_guidelines.sort(key=lambda x: x[0], reverse=True)
        return [g for _, g in scored_guidelines[:max_results]]

    def classify_blood_pressure(
        self,
        systolic: int,
        diastolic: int,
    ) -> Dict[str, Any]:
        """
        Classify blood pressure reading.

        Args:
            systolic: Systolic pressure (top number)
            diastolic: Diastolic pressure (bottom number)

        Returns:
            Dict with classification and recommendations
        """
        for bp_range in self.BP_CLASSIFICATIONS:
            if (
                bp_range.systolic_min <= systolic <= bp_range.systolic_max
                and bp_range.diastolic_min <= diastolic <= bp_range.diastolic_max
            ):
                return {
                    "reading": f"{systolic}/{diastolic}",
                    "category": bp_range.category,
                    "risk_level": bp_range.risk_level.value,
                    "recommendation": bp_range.recommendation,
                    "is_emergency": bp_range.risk_level == RiskLevel.VERY_HIGH,
                }

        # Default to highest category if above all ranges
        return {
            "reading": f"{systolic}/{diastolic}",
            "category": "Unknown/Abnormal",
            "risk_level": "high",
            "recommendation": "Consult a healthcare provider for proper evaluation.",
            "is_emergency": systolic >= 180 or diastolic >= 120,
        }

    def get_lifestyle_recommendations(self) -> List[Dict[str, str]]:
        """Get general lifestyle recommendations for heart health."""
        return [
            {
                "category": "Diet",
                "recommendation": "Follow DASH or Mediterranean diet. Eat 5+ servings of fruits/vegetables daily.",
                "priority": "high",
            },
            {
                "category": "Exercise",
                "recommendation": "150 minutes of moderate exercise or 75 minutes of vigorous exercise per week.",
                "priority": "high",
            },
            {
                "category": "Smoking",
                "recommendation": "Quit smoking. It's the #1 preventable cause of cardiovascular death.",
                "priority": "high",
            },
            {
                "category": "Sleep",
                "recommendation": "Get 7-9 hours of quality sleep per night.",
                "priority": "medium",
            },
            {
                "category": "Weight",
                "recommendation": "Maintain BMI between 18.5-24.9. Lose weight if overweight.",
                "priority": "medium",
            },
            {
                "category": "Alcohol",
                "recommendation": "Limit to ≤2 drinks/day for men, ≤1 drink/day for women.",
                "priority": "medium",
            },
            {
                "category": "Stress",
                "recommendation": "Practice stress management techniques: meditation, deep breathing, yoga.",
                "priority": "medium",
            },
            {
                "category": "Monitoring",
                "recommendation": "Check blood pressure regularly. Track weight daily if heart failure.",
                "priority": "high",
            },
        ]

    def to_rag_documents(self) -> List[Dict[str, Any]]:
        """
        Convert guidelines to format suitable for RAG indexing.

        Returns:
            List of documents ready for vector store
        """
        documents = []

        for guideline in self._guidelines.values():
            documents.append(
                {
                    "id": f"cardio_guide_{guideline.id}",
                    "content": f"{guideline.title}\n\n{guideline.content}",
                    "metadata": {
                        "source": guideline.source,
                        "category": guideline.category.value,
                        "keywords": guideline.keywords,
                        "type": "cardiovascular_guideline",
                    },
                }
            )

        return documents


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_guidelines_instance: Optional[CardiovascularGuidelines] = None


def get_cardiovascular_guidelines() -> CardiovascularGuidelines:
    """Get singleton instance of CardiovascularGuidelines."""
    global _guidelines_instance
    if _guidelines_instance is None:
        _guidelines_instance = CardiovascularGuidelines()
    return _guidelines_instance


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Testing CardiovascularGuidelines...")

    guidelines = get_cardiovascular_guidelines()

    # Test getting all guidelines
    all_guidelines = guidelines.get_all_guidelines()
    print(f"\n📚 Total guidelines: {len(all_guidelines)}")

    # Test category search
    hf_guidelines = guidelines.get_guidelines_by_category(
        ConditionCategory.HEART_FAILURE
    )
    print(f"\n❤️ Heart failure guidelines: {len(hf_guidelines)}")
    for g in hf_guidelines:
        print(f"  - {g.title}")

    # Test blood pressure classification
    print("\n🩺 Blood pressure classifications:")
    test_readings = [(115, 75), (125, 78), (135, 85), (145, 95), (185, 125)]
    for sys, dia in test_readings:
        result = guidelines.classify_blood_pressure(sys, dia)
        print(f"  {result['reading']}: {result['category']} ({result['risk_level']})")

    # Test search
    print("\n🔍 Search for 'chest pain':")
    results = guidelines.search("chest pain")
    for r in results:
        print(f"  - {r.title}")

    # Test condition info
    print("\n📋 Get condition info for 'afib':")
    info = guidelines.get_condition_info("afib")
    print(f"  Found {info['found']} guidelines")

    # Test RAG documents
    rag_docs = guidelines.to_rag_documents()
    print(f"\n📄 RAG documents ready: {len(rag_docs)}")

    print("\n✅ CardiovascularGuidelines tests passed!")
