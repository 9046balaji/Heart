"""
Cardiology Specialist Agent.

Domain-specific agent for cardiovascular health queries,
heart disease risk assessment, and cardio-related recommendations.

Features:
- Heart disease risk prediction integration
- Vital signs analysis (BP, HR, ECG patterns)
- Medication interactions for cardiac drugs
- Exercise recommendations for heart health
- Emergency detection for cardiac events
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .planner import AgentTask, AgentType

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Cardiovascular risk level."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class CardiacSymptom(Enum):
    """Common cardiac symptoms."""

    CHEST_PAIN = "chest_pain"
    SHORTNESS_OF_BREATH = "shortness_of_breath"
    PALPITATIONS = "palpitations"
    DIZZINESS = "dizziness"
    FATIGUE = "fatigue"
    SWELLING = "swelling"
    IRREGULAR_HEARTBEAT = "irregular_heartbeat"
    JAW_PAIN = "jaw_pain"
    ARM_PAIN = "arm_pain"
    NAUSEA = "nausea"


@dataclass
class VitalSigns:
    """Vital signs data."""

    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[float] = None
    temperature: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "blood_pressure": (
                {
                    "systolic": self.systolic_bp,
                    "diastolic": self.diastolic_bp,
                }
                if self.systolic_bp
                else None
            ),
            "heart_rate": self.heart_rate,
            "respiratory_rate": self.respiratory_rate,
            "oxygen_saturation": self.oxygen_saturation,
            "temperature": self.temperature,
            "timestamp": self.timestamp,
        }


@dataclass
class CardioAssessment:
    """Cardiology assessment result."""

    risk_level: RiskLevel
    risk_score: float  # 0-100
    risk_factors: List[str]
    recommendations: List[str]
    warning_signs: List[str]
    requires_immediate_attention: bool
    suggested_tests: List[str]
    lifestyle_modifications: List[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "risk_factors": self.risk_factors,
            "recommendations": self.recommendations,
            "warning_signs": self.warning_signs,
            "requires_immediate_attention": self.requires_immediate_attention,
            "suggested_tests": self.suggested_tests,
            "lifestyle_modifications": self.lifestyle_modifications,
            "timestamp": self.timestamp,
        }


class CardioSpecialistAgent:
    """
    Specialized agent for cardiovascular health.

    Provides:
    - Risk assessment based on vitals and history
    - Symptom analysis for cardiac conditions
    - Medication guidance for cardiac drugs
    - Exercise and lifestyle recommendations

    Example:
        agent = CardioSpecialistAgent()
        assessment = await agent.assess_cardiac_risk(vitals, history)
    """

    # Risk thresholds
    BP_THRESHOLDS = {
        "normal": {"systolic": 120, "diastolic": 80},
        "elevated": {"systolic": 129, "diastolic": 80},
        "high_stage1": {"systolic": 139, "diastolic": 89},
        "high_stage2": {"systolic": 180, "diastolic": 120},
        "crisis": {"systolic": 180, "diastolic": 120},
    }

    HR_THRESHOLDS = {
        "bradycardia": 60,
        "normal_low": 60,
        "normal_high": 100,
        "tachycardia": 100,
    }

    # Emergency symptoms
    EMERGENCY_SYMPTOMS = [
        CardiacSymptom.CHEST_PAIN,
        CardiacSymptom.JAW_PAIN,
        CardiacSymptom.ARM_PAIN,
    ]

    # Cardiac medications
    CARDIAC_MEDICATIONS = [
        "aspirin",
        "metoprolol",
        "lisinopril",
        "amlodipine",
        "atorvastatin",
        "warfarin",
        "clopidogrel",
        "digoxin",
        "furosemide",
        "carvedilol",
        "losartan",
        "nitroglycerin",
    ]

    def __init__(
        self,
        risk_predictor: Optional[Any] = None,
        use_ml_prediction: bool = True,
    ):
        """
        Initialize cardio specialist.

        Args:
            risk_predictor: ML model for risk prediction
            use_ml_prediction: Whether to use ML-based prediction
        """
        self.risk_predictor = risk_predictor
        self.use_ml_prediction = use_ml_prediction and risk_predictor is not None

    async def execute(
        self,
        task: AgentTask,
        previous_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute cardio specialist task.

        Args:
            task: Task to execute
            previous_results: Results from previous tasks

        Returns:
            Assessment results
        """
        logger.info(f"CardioSpecialist executing: {task.description}")

        # Extract context from task
        context = task.context or {}
        vitals = context.get("vitals")
        symptoms = context.get("symptoms", [])
        medical_history = context.get("medical_history", {})
        query = task.description

        # Perform assessment
        assessment = await self.assess_cardiac_risk(
            vitals=vitals,
            symptoms=symptoms,
            medical_history=medical_history,
            query=query,
        )

        # Format response
        response = self._format_response(assessment, query)

        return {
            "assessment": assessment.to_dict(),
            "response": response,
            "agent": AgentType.CARDIO_SPECIALIST.value,
        }

    async def assess_cardiac_risk(
        self,
        vitals: Optional[Dict] = None,
        symptoms: Optional[List[str]] = None,
        medical_history: Optional[Dict] = None,
        query: Optional[str] = None,
    ) -> CardioAssessment:
        """
        Assess cardiovascular risk.

        Args:
            vitals: Current vital signs
            symptoms: Reported symptoms
            medical_history: Patient history
            query: User's query

        Returns:
            CardioAssessment
        """
        risk_factors = []
        recommendations = []
        warning_signs = []
        suggested_tests = []
        lifestyle_mods = []
        risk_score = 0.0
        requires_attention = False

        # Parse vitals
        vital_signs = None
        if vitals:
            vital_signs = VitalSigns(
                systolic_bp=vitals.get("systolic_bp")
                or vitals.get("blood_pressure", {}).get("systolic"),
                diastolic_bp=vitals.get("diastolic_bp")
                or vitals.get("blood_pressure", {}).get("diastolic"),
                heart_rate=vitals.get("heart_rate") or vitals.get("pulse"),
                oxygen_saturation=vitals.get("oxygen_saturation") or vitals.get("spo2"),
            )

        # Analyze blood pressure
        if vital_signs and vital_signs.systolic_bp:
            bp_analysis = self._analyze_blood_pressure(
                vital_signs.systolic_bp,
                vital_signs.diastolic_bp,
            )
            risk_score += bp_analysis["risk_contribution"]
            if bp_analysis["is_concerning"]:
                risk_factors.append(bp_analysis["message"])
                warning_signs.extend(bp_analysis.get("warnings", []))
            recommendations.extend(bp_analysis.get("recommendations", []))

        # Analyze heart rate
        if vital_signs and vital_signs.heart_rate:
            hr_analysis = self._analyze_heart_rate(vital_signs.heart_rate)
            risk_score += hr_analysis["risk_contribution"]
            if hr_analysis["is_concerning"]:
                risk_factors.append(hr_analysis["message"])
                warning_signs.extend(hr_analysis.get("warnings", []))
            recommendations.extend(hr_analysis.get("recommendations", []))

        # Analyze symptoms
        if symptoms:
            symptom_analysis = self._analyze_symptoms(symptoms)
            risk_score += symptom_analysis["risk_contribution"]
            if symptom_analysis["is_emergency"]:
                requires_attention = True
                warning_signs.extend(symptom_analysis.get("emergency_warnings", []))
            risk_factors.extend(symptom_analysis.get("risk_factors", []))
            recommendations.extend(symptom_analysis.get("recommendations", []))
            suggested_tests.extend(symptom_analysis.get("suggested_tests", []))

        # Analyze medical history
        if medical_history:
            history_analysis = self._analyze_history(medical_history)
            risk_score += history_analysis["risk_contribution"]
            risk_factors.extend(history_analysis.get("risk_factors", []))
            recommendations.extend(history_analysis.get("recommendations", []))

        # Add lifestyle modifications
        lifestyle_mods = self._get_lifestyle_modifications(risk_score)

        # Add standard suggested tests if high risk
        if risk_score > 50:
            suggested_tests.extend(
                [
                    "Lipid panel (cholesterol, triglycerides)",
                    "Echocardiogram",
                    "Stress test",
                ]
            )
        elif risk_score > 30:
            suggested_tests.extend(
                [
                    "Lipid panel",
                    "Blood pressure monitoring",
                ]
            )

        # Deduplicate
        risk_factors = list(dict.fromkeys(risk_factors))
        recommendations = list(dict.fromkeys(recommendations))
        warning_signs = list(dict.fromkeys(warning_signs))
        suggested_tests = list(dict.fromkeys(suggested_tests))
        lifestyle_mods = list(dict.fromkeys(lifestyle_mods))

        # Determine risk level
        risk_level = self._determine_risk_level(risk_score, requires_attention)

        # Cap risk score at 100
        risk_score = min(risk_score, 100)

        return CardioAssessment(
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=risk_factors,
            recommendations=recommendations,
            warning_signs=warning_signs,
            requires_immediate_attention=requires_attention,
            suggested_tests=suggested_tests,
            lifestyle_modifications=lifestyle_mods,
        )

    def _analyze_blood_pressure(
        self,
        systolic: int,
        diastolic: Optional[int],
    ) -> Dict[str, Any]:
        """Analyze blood pressure readings."""
        result = {
            "is_concerning": False,
            "risk_contribution": 0,
            "message": "",
            "warnings": [],
            "recommendations": [],
        }

        diastolic = diastolic or 0

        # Hypertensive crisis
        if systolic >= 180 or diastolic >= 120:
            result["is_concerning"] = True
            result["risk_contribution"] = 40
            result["message"] = f"Hypertensive crisis: {systolic}/{diastolic} mmHg"
            result["warnings"] = [
                "Blood pressure is dangerously high",
                "Seek immediate medical attention",
            ]
            result["recommendations"] = [
                "Call emergency services or go to ER immediately",
                "Do not drive yourself",
            ]

        # Stage 2 hypertension
        elif systolic >= 140 or diastolic >= 90:
            result["is_concerning"] = True
            result["risk_contribution"] = 25
            result["message"] = f"Stage 2 hypertension: {systolic}/{diastolic} mmHg"
            result["recommendations"] = [
                "Schedule appointment with cardiologist",
                "Reduce sodium intake",
                "Consider DASH diet",
            ]

        # Stage 1 hypertension
        elif systolic >= 130 or diastolic >= 80:
            result["is_concerning"] = True
            result["risk_contribution"] = 15
            result["message"] = f"Stage 1 hypertension: {systolic}/{diastolic} mmHg"
            result["recommendations"] = [
                "Monitor blood pressure regularly",
                "Lifestyle modifications recommended",
            ]

        # Elevated
        elif systolic >= 120:
            result["risk_contribution"] = 5
            result["message"] = f"Elevated blood pressure: {systolic}/{diastolic} mmHg"
            result["recommendations"] = [
                "Continue healthy lifestyle habits",
            ]

        # Hypotension
        elif systolic < 90:
            result["is_concerning"] = True
            result["risk_contribution"] = 15
            result["message"] = f"Low blood pressure: {systolic}/{diastolic} mmHg"
            result["warnings"] = ["Low blood pressure may cause dizziness"]
            result["recommendations"] = [
                "Stay hydrated",
                "Rise slowly from sitting/lying",
            ]

        return result

    def _analyze_heart_rate(self, heart_rate: int) -> Dict[str, Any]:
        """Analyze heart rate."""
        result = {
            "is_concerning": False,
            "risk_contribution": 0,
            "message": "",
            "warnings": [],
            "recommendations": [],
        }

        # Severe tachycardia
        if heart_rate > 150:
            result["is_concerning"] = True
            result["risk_contribution"] = 30
            result["message"] = f"Severe tachycardia: {heart_rate} bpm"
            result["warnings"] = [
                "Extremely elevated heart rate",
                "May indicate cardiac arrhythmia",
            ]
            result["recommendations"] = [
                "Seek immediate medical evaluation",
                "Avoid caffeine and stimulants",
            ]

        # Tachycardia
        elif heart_rate > 100:
            result["is_concerning"] = True
            result["risk_contribution"] = 15
            result["message"] = f"Tachycardia: {heart_rate} bpm"
            result["recommendations"] = [
                "Monitor heart rate",
                "Reduce stress and caffeine",
            ]

        # Bradycardia
        elif heart_rate < 50:
            result["is_concerning"] = True
            result["risk_contribution"] = 20
            result["message"] = f"Bradycardia: {heart_rate} bpm"
            result["warnings"] = ["Low heart rate may indicate conduction issues"]
            result["recommendations"] = [
                "Consult cardiologist",
                "ECG recommended",
            ]

        return result

    def _analyze_symptoms(self, symptoms: List[str]) -> Dict[str, Any]:
        """Analyze reported symptoms."""
        result = {
            "is_emergency": False,
            "risk_contribution": 0,
            "risk_factors": [],
            "recommendations": [],
            "suggested_tests": [],
            "emergency_warnings": [],
        }

        # Normalize symptoms
        symptom_set = {s.lower().replace(" ", "_") for s in symptoms}

        # Check for emergency symptoms
        emergency_symptoms = {"chest_pain", "jaw_pain", "arm_pain"}
        if symptom_set & emergency_symptoms:
            result["is_emergency"] = True
            result["risk_contribution"] = 50
            result["emergency_warnings"] = [
                "⚠️ EMERGENCY: Symptoms may indicate heart attack",
                "Call 911 immediately",
                "Do not drive - wait for emergency services",
                "Chew aspirin if available and not allergic",
            ]
            result["risk_factors"].append("Acute cardiac symptoms")
            return result

        # Check for concerning symptoms
        concerning_symptoms = {
            "shortness_of_breath": {
                "risk": 15,
                "factor": "Dyspnea at rest or exertion",
                "tests": ["Chest X-ray", "BNP test"],
            },
            "palpitations": {
                "risk": 10,
                "factor": "Heart rhythm irregularities",
                "tests": ["Holter monitor", "ECG"],
            },
            "dizziness": {
                "risk": 10,
                "factor": "Possible orthostatic hypotension",
                "tests": ["Blood pressure monitoring"],
            },
            "swelling": {
                "risk": 15,
                "factor": "Peripheral edema - possible heart failure",
                "tests": ["Echocardiogram", "BNP test"],
            },
            "fatigue": {
                "risk": 5,
                "factor": "Chronic fatigue - cardiac evaluation needed",
                "tests": ["Complete metabolic panel"],
            },
            "irregular_heartbeat": {
                "risk": 20,
                "factor": "Arrhythmia symptoms",
                "tests": ["ECG", "Holter monitor"],
            },
        }

        for symptom, info in concerning_symptoms.items():
            if symptom in symptom_set:
                result["risk_contribution"] += info["risk"]
                result["risk_factors"].append(info["factor"])
                result["suggested_tests"].extend(info["tests"])

        if result["risk_contribution"] > 20:
            result["recommendations"].append("Schedule cardiology appointment")

        return result

    def _analyze_history(self, medical_history: Dict) -> Dict[str, Any]:
        """Analyze medical history."""
        result = {
            "risk_contribution": 0,
            "risk_factors": [],
            "recommendations": [],
        }

        # Check for cardiac conditions
        conditions = medical_history.get("conditions", [])
        cardiac_conditions = [
            "hypertension",
            "diabetes",
            "high_cholesterol",
            "coronary_artery_disease",
            "heart_failure",
            "atrial_fibrillation",
            "previous_heart_attack",
            "stroke",
            "peripheral_artery_disease",
        ]

        for condition in conditions:
            if condition.lower().replace(" ", "_") in cardiac_conditions:
                result["risk_contribution"] += 10
                result["risk_factors"].append(f"History of {condition}")

        # Family history
        family_history = medical_history.get("family_history", [])
        if any("heart" in h.lower() or "cardiac" in h.lower() for h in family_history):
            result["risk_contribution"] += 10
            result["risk_factors"].append("Family history of heart disease")

        # Smoking
        if medical_history.get("smoking"):
            result["risk_contribution"] += 15
            result["risk_factors"].append("Tobacco use")
            result["recommendations"].append("Smoking cessation strongly recommended")

        # Age factor
        age = medical_history.get("age", 0)
        if age >= 65:
            result["risk_contribution"] += 10
            result["risk_factors"].append(f"Age ({age} years)")
        elif age >= 45:
            result["risk_contribution"] += 5

        return result

    def _get_lifestyle_modifications(self, risk_score: float) -> List[str]:
        """Get lifestyle modification recommendations."""
        mods = []

        if risk_score >= 50:
            mods = [
                "Follow heart-healthy diet (Mediterranean or DASH)",
                "150+ minutes moderate aerobic exercise per week",
                "Maintain BMI under 25",
                "Limit alcohol to 1 drink/day for women, 2 for men",
                "Practice stress management techniques",
                "Ensure 7-9 hours quality sleep nightly",
                "Reduce sodium to <2300mg/day",
                "Increase fiber intake (25-30g/day)",
            ]
        elif risk_score >= 30:
            mods = [
                "Regular aerobic exercise (30 min, 5x/week)",
                "Heart-healthy diet with whole grains and vegetables",
                "Maintain healthy weight",
                "Limit saturated fats and processed foods",
                "Practice stress reduction",
            ]
        else:
            mods = [
                "Maintain active lifestyle",
                "Eat balanced diet rich in fruits and vegetables",
                "Get regular health check-ups",
            ]

        return mods

    def _determine_risk_level(
        self,
        risk_score: float,
        requires_attention: bool,
    ) -> RiskLevel:
        """Determine risk level from score."""
        if requires_attention or risk_score >= 70:
            return RiskLevel.CRITICAL
        elif risk_score >= 50:
            return RiskLevel.HIGH
        elif risk_score >= 25:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW

    def _format_response(
        self,
        assessment: CardioAssessment,
        query: str,
    ) -> str:
        """Format assessment as natural language response."""
        parts = []

        # Emergency notice
        if assessment.requires_immediate_attention:
            parts.append("⚠️ **IMMEDIATE ATTENTION REQUIRED**")
            parts.append("")
            for warning in assessment.warning_signs:
                parts.append(f"• {warning}")
            parts.append("")
            return "\n".join(parts)

        # Risk level intro
        risk_intros = {
            RiskLevel.CRITICAL: "Your cardiovascular risk assessment indicates **critical** concerns that require immediate medical attention.",
            RiskLevel.HIGH: "Your cardiovascular risk assessment indicates **elevated** risk factors that should be addressed with your healthcare provider.",
            RiskLevel.MODERATE: "Your cardiovascular risk assessment indicates some **moderate** risk factors to monitor.",
            RiskLevel.LOW: "Your cardiovascular risk assessment indicates **low** risk. Keep up your healthy habits!",
        }
        parts.append(risk_intros.get(assessment.risk_level, ""))
        parts.append("")

        # Risk factors
        if assessment.risk_factors:
            parts.append("**Risk Factors Identified:**")
            for factor in assessment.risk_factors[:5]:
                parts.append(f"• {factor}")
            parts.append("")

        # Recommendations
        if assessment.recommendations:
            parts.append("**Recommendations:**")
            for rec in assessment.recommendations[:5]:
                parts.append(f"• {rec}")
            parts.append("")

        # Lifestyle modifications
        if assessment.lifestyle_modifications:
            parts.append("**Lifestyle Modifications:**")
            for mod in assessment.lifestyle_modifications[:4]:
                parts.append(f"• {mod}")
            parts.append("")

        # Suggested tests
        if assessment.suggested_tests:
            parts.append("**Suggested Tests:**")
            for test in assessment.suggested_tests[:4]:
                parts.append(f"• {test}")

        return "\n".join(parts)
