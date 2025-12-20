"""
Health-Specific Tools for Function Calling

This module provides pre-built health-specific tools for the Cardio AI Assistant.
All tools are automatically registered with the ToolRegistry.

Tools included:
- Blood pressure analyzer
- Heart rate analyzer
- Medication checker
- Drug interaction checker
- Symptom triage
- BMI calculator
- Cardiovascular risk calculator
- Appointment scheduler
- Health reminder setter
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from .tool_registry import (
    register_tool,
    ToolParameter,
    ToolResult,
)

logger = logging.getLogger(__name__)


# =============================================================================
# VITAL SIGN ANALYZERS
# =============================================================================


@register_tool(
    name="blood_pressure_analyzer",
    description="Analyze blood pressure reading and provide classification and recommendations",
    parameters=[
        ToolParameter(
            "systolic",
            "integer",
            "Systolic pressure (top number) in mmHg",
            required=True,
        ),
        ToolParameter(
            "diastolic",
            "integer",
            "Diastolic pressure (bottom number) in mmHg",
            required=True,
        ),
        ToolParameter(
            "pulse", "integer", "Heart rate during measurement in bpm", required=False
        ),
        ToolParameter(
            "arm",
            "string",
            "Which arm was used",
            required=False,
            enum=["left", "right"],
        ),
        ToolParameter(
            "position",
            "string",
            "Position during measurement",
            required=False,
            enum=["sitting", "standing", "lying"],
        ),
    ],
    category="vitals",
    version="1.0.0",
)
def blood_pressure_analyzer(
    systolic: int,
    diastolic: int,
    pulse: Optional[int] = None,
    arm: str = "left",
    position: str = "sitting",
) -> ToolResult:
    """
    Analyze blood pressure reading.

    Classification based on AHA/ACC 2017 Guidelines:
    - Normal: <120 and <80
    - Elevated: 120-129 and <80
    - Hypertension Stage 1: 130-139 or 80-89
    - Hypertension Stage 2: ≥140 or ≥90
    - Hypertensive Crisis: >180 and/or >120
    """
    # Validate ranges
    if not (60 <= systolic <= 300):
        return ToolResult(
            success=False,
            error=f"Invalid systolic pressure: {systolic}. Expected 60-300 mmHg.",
        )

    if not (40 <= diastolic <= 200):
        return ToolResult(
            success=False,
            error=f"Invalid diastolic pressure: {diastolic}. Expected 40-200 mmHg.",
        )

    # Classify
    category = ""
    severity = ""
    recommendations = []
    warnings = []

    if systolic > 180 or diastolic > 120:
        category = "Hypertensive Crisis"
        severity = "critical"
        warnings.append("⚠️ SEEK IMMEDIATE MEDICAL ATTENTION")
        warnings.append(
            "If experiencing headache, chest pain, or vision changes, call 911"
        )
        recommendations.append(
            "Do not drive yourself - call emergency services or have someone drive you"
        )
    elif systolic >= 140 or diastolic >= 90:
        category = "Hypertension Stage 2"
        severity = "high"
        recommendations.append("Schedule appointment with healthcare provider soon")
        recommendations.append("Monitor blood pressure daily")
        recommendations.append("Review medications with doctor")
    elif systolic >= 130 or diastolic >= 80:
        category = "Hypertension Stage 1"
        severity = "moderate"
        recommendations.append("Lifestyle modifications recommended")
        recommendations.append("Reduce sodium intake")
        recommendations.append("Increase physical activity")
        recommendations.append("Schedule follow-up with healthcare provider")
    elif systolic >= 120:
        category = "Elevated"
        severity = "mild"
        recommendations.append("Monitor blood pressure regularly")
        recommendations.append("Focus on lifestyle improvements")
        recommendations.append("Maintain healthy weight")
    else:
        category = "Normal"
        severity = "normal"
        recommendations.append("Continue healthy habits")
        recommendations.append("Check blood pressure periodically")

    # Check pulse if provided
    pulse_analysis = None
    if pulse:
        if pulse > 100:
            pulse_analysis = {
                "rate": pulse,
                "category": "Tachycardia",
                "note": "Heart rate is elevated",
            }
        elif pulse < 60:
            pulse_analysis = {
                "rate": pulse,
                "category": "Bradycardia",
                "note": "Heart rate is low (may be normal for athletes)",
            }
        else:
            pulse_analysis = {
                "rate": pulse,
                "category": "Normal",
                "note": "Heart rate is within normal range",
            }

    # Calculate pulse pressure (indicator of arterial stiffness)
    pulse_pressure = systolic - diastolic
    pp_analysis = None
    if pulse_pressure > 60:
        pp_analysis = "Wide pulse pressure - may indicate arterial stiffness"
    elif pulse_pressure < 25:
        pp_analysis = "Narrow pulse pressure"

    return ToolResult(
        success=True,
        data={
            "reading": f"{systolic}/{diastolic} mmHg",
            "category": category,
            "severity": severity,
            "systolic": systolic,
            "diastolic": diastolic,
            "pulse_pressure": pulse_pressure,
            "pulse_pressure_analysis": pp_analysis,
            "pulse_analysis": pulse_analysis,
            "measurement_conditions": {
                "arm": arm,
                "position": position,
            },
            "recommendations": recommendations,
        },
        warnings=warnings,
    )


@register_tool(
    name="heart_rate_analyzer",
    description="Analyze heart rate and provide context-aware interpretation",
    parameters=[
        ToolParameter(
            "heart_rate",
            "integer",
            "Heart rate in beats per minute (bpm)",
            required=True,
        ),
        ToolParameter(
            "activity",
            "string",
            "Activity level during measurement",
            required=False,
            enum=[
                "resting",
                "light_activity",
                "moderate_activity",
                "vigorous_activity",
                "sleeping",
            ],
        ),
        ToolParameter("age", "integer", "Patient age in years", required=False),
        ToolParameter(
            "is_athlete",
            "boolean",
            "Whether patient is a trained athlete",
            required=False,
        ),
    ],
    category="vitals",
    version="1.0.0",
)
def heart_rate_analyzer(
    heart_rate: int,
    activity: str = "resting",
    age: Optional[int] = None,
    is_athlete: bool = False,
) -> ToolResult:
    """
    Analyze heart rate with context.

    Normal resting heart rate: 60-100 bpm
    Athletes: 40-60 bpm
    """
    # Validate
    if not (20 <= heart_rate <= 300):
        return ToolResult(
            success=False,
            error=f"Invalid heart rate: {heart_rate}. Expected 20-300 bpm.",
        )

    category = ""
    severity = ""
    recommendations = []
    warnings = []

    # Resting analysis
    if activity == "resting" or activity == "sleeping":
        if heart_rate > 120:
            category = "Significant Tachycardia"
            severity = "high"
            warnings.append("Resting heart rate is significantly elevated")
            recommendations.append("Seek medical evaluation if persistent")
            recommendations.append("Check for fever, dehydration, or anxiety")
        elif heart_rate > 100:
            category = "Tachycardia"
            severity = "moderate"
            recommendations.append("Monitor for associated symptoms")
            recommendations.append("Reduce caffeine intake")
            recommendations.append("Practice relaxation techniques")
        elif heart_rate < 40:
            category = "Significant Bradycardia"
            severity = "moderate" if is_athlete else "high"
            if not is_athlete:
                warnings.append("Heart rate is very low - consult healthcare provider")
                recommendations.append("Medical evaluation recommended if symptomatic")
        elif heart_rate < 60:
            category = "Bradycardia"
            severity = "normal" if is_athlete else "mild"
            if is_athlete:
                recommendations.append("Normal for trained athletes")
            else:
                recommendations.append(
                    "May be normal - monitor for symptoms like dizziness"
                )
        else:
            category = "Normal"
            severity = "normal"
            recommendations.append("Heart rate is within normal range")

    # Calculate max heart rate (220 - age) if age provided
    max_hr = None
    target_zones = None
    if age:
        max_hr = 220 - age
        target_zones = {
            "moderate_exercise": f"{int(max_hr * 0.5)}-{int(max_hr * 0.7)} bpm",
            "vigorous_exercise": f"{int(max_hr * 0.7)}-{int(max_hr * 0.85)} bpm",
            "maximum": f"{int(max_hr * 0.85)}-{max_hr} bpm",
        }

    return ToolResult(
        success=True,
        data={
            "heart_rate": heart_rate,
            "unit": "bpm",
            "activity": activity,
            "category": category,
            "severity": severity,
            "is_athlete": is_athlete,
            "max_heart_rate": max_hr,
            "target_zones": target_zones,
            "recommendations": recommendations,
        },
        warnings=warnings,
    )


# =============================================================================
# MEDICATION TOOLS
# =============================================================================


@register_tool(
    name="medication_checker",
    description="Look up medication information including uses, side effects, and warnings",
    parameters=[
        ToolParameter(
            "medication_name",
            "string",
            "Name of medication (generic or brand)",
            required=True,
        ),
    ],
    category="medications",
    version="1.0.0",
)
def medication_checker(medication_name: str) -> ToolResult:
    """Look up medication information from the drug database."""
    try:
        from ..rag.knowledge_base import get_quick_drug_info

        info = get_quick_drug_info(medication_name)

        if not info:
            return ToolResult(
                success=True,
                data={
                    "found": False,
                    "medication": medication_name,
                    "message": f"Medication '{medication_name}' not found in database. "
                    "Please verify spelling or consult a pharmacist.",
                },
            )

        return ToolResult(
            success=True,
            data={
                "found": True,
                "generic_name": info.get("generic_name"),
                "brand_names": info.get("brand_names", []),
                "drug_class": info.get("drug_class"),
                "indications": info.get("indications", []),
                "dosing": info.get("dosing"),
                "common_side_effects": info.get("common_side_effects", []),
                "serious_side_effects": info.get("serious_side_effects", []),
                "contraindications": info.get("contraindications", []),
                "monitoring": info.get("monitoring", []),
                "food_interactions": info.get("food_interactions", []),
                "warnings": info.get("warnings", []),
            },
            warnings=["Always consult your pharmacist or doctor about medications"],
        )
    except ImportError:
        return ToolResult(
            success=False,
            error="Drug database not available. Please consult a pharmacist.",
        )


@register_tool(
    name="drug_interaction_checker",
    description="Check for potential interactions between multiple medications",
    parameters=[
        ToolParameter(
            "medications",
            "array",
            "List of medication names to check for interactions",
            required=True,
            items_type="string",
        ),
    ],
    category="medications",
    version="1.0.0",
)
def drug_interaction_checker(medications: List[str]) -> ToolResult:
    """Check for drug-drug interactions."""
    if len(medications) < 2:
        return ToolResult(
            success=False,
            error="At least 2 medications are required to check for interactions.",
        )

    try:
        from ..rag.knowledge_base import check_drug_interactions_quick

        interactions = check_drug_interactions_quick(medications)

        warnings = []
        for interaction in interactions:
            severity = interaction.get("severity", "")
            if severity in ["contraindicated", "major"]:
                warnings.append(
                    f"⚠️ {interaction['drug1']} + {interaction['drug2']}: {interaction['effect']}"
                )

        return ToolResult(
            success=True,
            data={
                "medications_checked": medications,
                "interactions_found": len(interactions),
                "interactions": interactions,
                "summary": (
                    f"Found {len(interactions)} potential interaction(s) "
                    f"between {len(medications)} medications."
                ),
            },
            warnings=warnings + ["Always verify interactions with your pharmacist"],
        )
    except ImportError:
        return ToolResult(
            success=False,
            error="Drug interaction database not available. Please consult a pharmacist.",
        )


# =============================================================================
# SYMPTOM TOOLS
# =============================================================================


@register_tool(
    name="symptom_triage",
    description="Triage symptoms and determine urgency level",
    parameters=[
        ToolParameter(
            "symptoms",
            "array",
            "List of symptoms the patient is experiencing",
            required=True,
            items_type="string",
        ),
        ToolParameter(
            "duration",
            "string",
            "How long symptoms have been present",
            required=False,
            enum=["minutes", "hours", "days", "weeks"],
        ),
        ToolParameter(
            "severity", "integer", "Severity on scale of 1-10", required=False
        ),
    ],
    category="symptoms",
    version="1.0.0",
)
def symptom_triage(
    symptoms: List[str],
    duration: Optional[str] = None,
    severity: Optional[int] = None,
) -> ToolResult:
    """Triage symptoms and determine urgency."""
    try:
        from ..rag.knowledge_base import triage_symptoms_quick

        triage = triage_symptoms_quick(symptoms)

        # Add duration and severity to analysis
        urgency_level = triage.get("urgency", "routine")

        # Escalate if severe
        if severity and severity >= 8:
            if urgency_level == "routine":
                urgency_level = "soon"
            elif urgency_level == "soon":
                urgency_level = "urgent"

        warnings = []
        if urgency_level == "emergency":
            warnings.append("⚠️ CALL 911 OR GO TO EMERGENCY ROOM IMMEDIATELY")

        return ToolResult(
            success=True,
            data={
                "symptoms": symptoms,
                "urgency": urgency_level,
                "message": triage.get("message"),
                "duration": duration,
                "severity": severity,
                "possible_conditions": triage.get("matched_conditions", []),
                "recommendations": triage.get("recommendations", []),
                "action": {
                    "emergency": "Call 911 immediately",
                    "urgent": "Seek care within hours",
                    "soon": "See doctor within days",
                    "routine": "Schedule regular appointment",
                }.get(urgency_level, "Monitor symptoms"),
            },
            warnings=warnings + [triage.get("disclaimer", "This is not a diagnosis.")],
        )
    except ImportError:
        # Fallback basic triage
        warnings = []
        urgency = "routine"

        emergency_symptoms = [
            "chest pain",
            "difficulty breathing",
            "severe headache",
            "loss of consciousness",
            "stroke",
            "heart attack",
        ]

        for symptom in symptoms:
            symptom_lower = symptom.lower()
            if any(es in symptom_lower for es in emergency_symptoms):
                urgency = "emergency"
                warnings.append(
                    f"⚠️ '{symptom}' may require immediate medical attention"
                )
                break

        return ToolResult(
            success=True,
            data={
                "symptoms": symptoms,
                "urgency": urgency,
                "message": "Please consult a healthcare provider for proper evaluation.",
                "recommendations": [
                    "Document your symptoms",
                    "Note when they started",
                    "Schedule an appointment with your doctor",
                ],
            },
            warnings=warnings,
        )


# =============================================================================
# HEALTH CALCULATORS
# =============================================================================


@register_tool(
    name="bmi_calculator",
    description="Calculate Body Mass Index and provide interpretation",
    parameters=[
        ToolParameter("weight", "number", "Weight value", required=True),
        ToolParameter(
            "weight_unit", "string", "Weight unit", required=True, enum=["kg", "lbs"]
        ),
        ToolParameter("height", "number", "Height value", required=True),
        ToolParameter(
            "height_unit",
            "string",
            "Height unit",
            required=True,
            enum=["m", "cm", "ft", "in"],
        ),
        ToolParameter("age", "integer", "Age in years (for context)", required=False),
    ],
    category="calculators",
    version="1.0.0",
)
def bmi_calculator(
    weight: float,
    weight_unit: str,
    height: float,
    height_unit: str,
    age: Optional[int] = None,
) -> ToolResult:
    """Calculate BMI with unit conversion."""
    # Convert weight to kg
    weight_kg = weight
    if weight_unit == "lbs":
        weight_kg = weight * 0.453592

    # Convert height to meters
    height_m = height
    if height_unit == "cm":
        height_m = height / 100
    elif height_unit == "ft":
        height_m = height * 0.3048
    elif height_unit == "in":
        height_m = height * 0.0254

    # Validate
    if not (20 <= weight_kg <= 500):
        return ToolResult(
            success=False,
            error=f"Invalid weight: {weight_kg} kg. Please check your input.",
        )

    if not (0.5 <= height_m <= 2.5):
        return ToolResult(
            success=False,
            error=f"Invalid height: {height_m} m. Please check your input.",
        )

    # Calculate BMI
    bmi = weight_kg / (height_m**2)
    bmi = round(bmi, 1)

    # Classify
    if bmi < 18.5:
        category = "Underweight"
        risk = "Increased risk of malnutrition"
        recommendations = [
            "Consult healthcare provider about healthy weight gain",
            "Ensure adequate nutrition",
            "Consider nutritionist consultation",
        ]
    elif bmi < 25:
        category = "Normal"
        risk = "Low health risk"
        recommendations = [
            "Maintain healthy eating habits",
            "Stay physically active",
            "Continue regular health checkups",
        ]
    elif bmi < 30:
        category = "Overweight"
        risk = "Increased risk of heart disease, diabetes"
        recommendations = [
            "Focus on balanced diet",
            "Increase physical activity",
            "Consider consulting nutritionist",
            "Monitor blood pressure and blood sugar",
        ]
    elif bmi < 35:
        category = "Obese (Class I)"
        risk = "High risk of cardiovascular disease"
        recommendations = [
            "Consult healthcare provider about weight management",
            "Structured diet and exercise program recommended",
            "Regular monitoring of cardiovascular risk factors",
        ]
    elif bmi < 40:
        category = "Obese (Class II)"
        risk = "Very high risk of cardiovascular disease"
        recommendations = [
            "Medical supervision recommended for weight loss",
            "Consider comprehensive weight management program",
            "Regular health screenings essential",
        ]
    else:
        category = "Obese (Class III)"
        risk = "Extremely high risk - medical intervention needed"
        recommendations = [
            "Seek medical consultation promptly",
            "Medically supervised weight loss program",
            "Consider all treatment options with healthcare team",
        ]

    # Calculate ideal weight range
    ideal_bmi_low = 18.5
    ideal_bmi_high = 24.9
    ideal_weight_low = ideal_bmi_low * (height_m**2)
    ideal_weight_high = ideal_bmi_high * (height_m**2)

    return ToolResult(
        success=True,
        data={
            "bmi": bmi,
            "category": category,
            "risk_level": risk,
            "measurements": {
                "weight_kg": round(weight_kg, 1),
                "height_m": round(height_m, 2),
            },
            "ideal_weight_range": {
                "low_kg": round(ideal_weight_low, 1),
                "high_kg": round(ideal_weight_high, 1),
                "low_lbs": round(ideal_weight_low * 2.205, 1),
                "high_lbs": round(ideal_weight_high * 2.205, 1),
            },
            "recommendations": recommendations,
        },
        warnings=[
            "BMI is a screening tool, not a diagnostic measure. "
            "It doesn't account for muscle mass or fat distribution."
        ],
    )


@register_tool(
    name="cardiovascular_risk_calculator",
    description="Calculate 10-year cardiovascular disease risk (simplified ASCVD)",
    parameters=[
        ToolParameter("age", "integer", "Age in years", required=True),
        ToolParameter(
            "sex", "string", "Biological sex", required=True, enum=["male", "female"]
        ),
        ToolParameter(
            "total_cholesterol", "integer", "Total cholesterol in mg/dL", required=True
        ),
        ToolParameter(
            "hdl_cholesterol", "integer", "HDL cholesterol in mg/dL", required=True
        ),
        ToolParameter(
            "systolic_bp", "integer", "Systolic blood pressure in mmHg", required=True
        ),
        ToolParameter(
            "on_bp_meds",
            "boolean",
            "Currently on blood pressure medications",
            required=True,
        ),
        ToolParameter("diabetic", "boolean", "Has diabetes", required=True),
        ToolParameter("smoker", "boolean", "Current smoker", required=True),
    ],
    category="calculators",
    version="1.0.0",
)
def cardiovascular_risk_calculator(
    age: int,
    sex: str,
    total_cholesterol: int,
    hdl_cholesterol: int,
    systolic_bp: int,
    on_bp_meds: bool,
    diabetic: bool,
    smoker: bool,
) -> ToolResult:
    """
    Calculate 10-year cardiovascular risk.

    This is a simplified calculation. The full ASCVD risk calculator uses
    the Pooled Cohort Equations which are more complex.
    """
    # Validate inputs
    if not (40 <= age <= 79):
        return ToolResult(
            success=False,
            error="Age must be between 40 and 79 for this calculator.",
        )

    # Simplified risk calculation (not the actual ASCVD formula)
    # This is for demonstration - real implementation should use validated formulas

    base_risk = 0.5  # Base 0.5% risk

    # Age factor
    age_factor = (age - 40) * 0.3  # 0.3% increase per year over 40

    # Sex factor
    sex_factor = 0 if sex == "female" else 2  # Higher baseline for males

    # Cholesterol factor
    tc_hdl_ratio = total_cholesterol / hdl_cholesterol
    chol_factor = max(0, (tc_hdl_ratio - 3.5) * 2)

    # Blood pressure factor
    bp_factor = max(0, (systolic_bp - 120) * 0.1)
    if on_bp_meds:
        bp_factor += 1  # Being on meds indicates underlying hypertension

    # Diabetes factor
    diabetes_factor = 4 if diabetic else 0

    # Smoking factor
    smoking_factor = 3 if smoker else 0

    # Calculate total risk
    risk = (
        base_risk
        + age_factor
        + sex_factor
        + chol_factor
        + bp_factor
        + diabetes_factor
        + smoking_factor
    )
    risk = min(risk, 50)  # Cap at 50%
    risk = round(risk, 1)

    # Classify risk
    if risk < 5:
        category = "Low"
        color = "green"
    elif risk < 7.5:
        category = "Borderline"
        color = "yellow"
    elif risk < 20:
        category = "Intermediate"
        color = "orange"
    else:
        category = "High"
        color = "red"

    # Generate recommendations
    recommendations = []
    modifiable_factors = []

    if smoker:
        modifiable_factors.append("Smoking cessation could significantly reduce risk")

    if systolic_bp > 130:
        modifiable_factors.append("Blood pressure management")

    if tc_hdl_ratio > 4:
        modifiable_factors.append("Cholesterol management (diet, possibly statins)")

    if diabetic:
        modifiable_factors.append("Optimal diabetes control")

    recommendations = [
        "Discuss these results with your healthcare provider",
        "Focus on modifiable risk factors",
    ] + modifiable_factors

    return ToolResult(
        success=True,
        data={
            "risk_percentage": risk,
            "risk_category": category,
            "risk_color": color,
            "interpretation": f"Your estimated 10-year risk of cardiovascular disease is {risk}%",
            "risk_factors_present": {
                "age_over_50": age > 50,
                "male": sex == "male",
                "elevated_cholesterol_ratio": tc_hdl_ratio > 4,
                "elevated_bp": systolic_bp > 130,
                "on_bp_medication": on_bp_meds,
                "diabetes": diabetic,
                "current_smoker": smoker,
            },
            "modifiable_factors": modifiable_factors,
            "recommendations": recommendations,
        },
        warnings=[
            "This is a simplified risk estimate for educational purposes only.",
            "Please use validated ASCVD calculators for clinical decision-making.",
            "Discuss your cardiovascular risk with your healthcare provider.",
        ],
    )


# =============================================================================
# APPOINTMENT & REMINDER TOOLS
# =============================================================================


@register_tool(
    name="appointment_scheduler",
    description="Schedule or check availability for medical appointments",
    parameters=[
        ToolParameter(
            "action",
            "string",
            "Action to perform",
            required=True,
            enum=["check_availability", "schedule", "cancel", "reschedule"],
        ),
        ToolParameter(
            "appointment_type",
            "string",
            "Type of appointment",
            required=True,
            enum=[
                "routine_checkup",
                "follow_up",
                "specialist",
                "urgent_care",
                "lab_work",
            ],
        ),
        ToolParameter(
            "preferred_date", "string", "Preferred date (YYYY-MM-DD)", required=False
        ),
        ToolParameter(
            "preferred_time",
            "string",
            "Preferred time slot",
            required=False,
            enum=["morning", "afternoon", "evening"],
        ),
        ToolParameter(
            "provider_name", "string", "Specific provider name", required=False
        ),
        ToolParameter("reason", "string", "Reason for appointment", required=False),
    ],
    category="appointments",
    version="1.0.0",
)
def appointment_scheduler(
    action: str,
    appointment_type: str,
    preferred_date: Optional[str] = None,
    preferred_time: str = "morning",
    provider_name: Optional[str] = None,
    reason: Optional[str] = None,
) -> ToolResult:
    """
    Handle appointment scheduling.

    Note: This is a simulation. Real implementation would connect to
    a scheduling system or EHR.
    """
    # Parse date or use defaults
    if preferred_date:
        try:
            target_date = datetime.strptime(preferred_date, "%Y-%m-%d")
        except ValueError:
            return ToolResult(
                success=False,
                error="Invalid date format. Use YYYY-MM-DD.",
            )
    else:
        target_date = datetime.now() + timedelta(days=7)  # Default to 1 week out

    # Time slot mapping
    time_slots = {
        "morning": ["9:00 AM", "10:00 AM", "11:00 AM"],
        "afternoon": ["1:00 PM", "2:00 PM", "3:00 PM"],
        "evening": ["4:00 PM", "5:00 PM"],
    }

    if action == "check_availability":
        # Simulate availability check
        available_slots = []
        for day_offset in range(7):
            check_date = target_date + timedelta(days=day_offset)
            if check_date.weekday() < 5:  # Weekdays only
                for slot in time_slots.get(preferred_time, time_slots["morning"]):
                    available_slots.append(
                        {
                            "date": check_date.strftime("%Y-%m-%d"),
                            "day": check_date.strftime("%A"),
                            "time": slot,
                        }
                    )

        return ToolResult(
            success=True,
            data={
                "action": "check_availability",
                "appointment_type": appointment_type,
                "available_slots": available_slots[:10],  # Return first 10
                "message": f"Found {len(available_slots)} available slots in the next 7 days.",
            },
        )

    elif action == "schedule":
        # Simulate scheduling
        scheduled_slot = time_slots.get(preferred_time, ["10:00 AM"])[0]

        return ToolResult(
            success=True,
            data={
                "action": "schedule",
                "appointment_type": appointment_type,
                "scheduled": {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "day": target_date.strftime("%A"),
                    "time": scheduled_slot,
                    "provider": provider_name or "First Available",
                    "reason": reason,
                },
                "confirmation_number": f"APT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "reminders": [
                    "Reminder will be sent 24 hours before appointment",
                    "Please arrive 15 minutes early",
                ],
            },
        )

    elif action == "cancel":
        return ToolResult(
            success=True,
            data={
                "action": "cancel",
                "message": "To cancel, please provide your confirmation number or call the office.",
                "contact": "Please call (555) 123-4567",
            },
        )

    elif action == "reschedule":
        return ToolResult(
            success=True,
            data={
                "action": "reschedule",
                "message": "To reschedule, please provide your confirmation number.",
                "next_steps": [
                    "Cancel existing appointment",
                    "Check new availability",
                    "Schedule new appointment",
                ],
            },
        )

    return ToolResult(
        success=False,
        error=f"Unknown action: {action}",
    )


@register_tool(
    name="health_reminder_setter",
    description="Set health-related reminders (medications, appointments, measurements)",
    parameters=[
        ToolParameter(
            "reminder_type",
            "string",
            "Type of reminder",
            required=True,
            enum=["medication", "measurement", "appointment", "exercise", "custom"],
        ),
        ToolParameter("title", "string", "Reminder title", required=True),
        ToolParameter(
            "frequency",
            "string",
            "How often to remind",
            required=True,
            enum=["once", "daily", "weekly", "monthly"],
        ),
        ToolParameter("time", "string", "Time for reminder (HH:MM)", required=False),
        ToolParameter(
            "days",
            "array",
            "Days of week for weekly reminders",
            required=False,
            items_type="string",
        ),
        ToolParameter("notes", "string", "Additional notes", required=False),
    ],
    category="reminders",
    version="1.0.0",
)
def health_reminder_setter(
    reminder_type: str,
    title: str,
    frequency: str,
    time: str = "09:00",
    days: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> ToolResult:
    """
    Set health reminders.

    Note: This is a simulation. Real implementation would integrate
    with notification systems.
    """
    # Validate time format
    try:
        reminder_time = datetime.strptime(time, "%H:%M")
        time_display = reminder_time.strftime("%I:%M %p")
    except ValueError:
        time_display = "9:00 AM"  # Default

    # Generate reminder ID
    reminder_id = f"REM-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Build schedule description
    if frequency == "once":
        schedule_desc = "One-time reminder"
    elif frequency == "daily":
        schedule_desc = f"Daily at {time_display}"
    elif frequency == "weekly":
        days_str = ", ".join(days) if days else "Every day"
        schedule_desc = f"Weekly on {days_str} at {time_display}"
    elif frequency == "monthly":
        schedule_desc = f"Monthly at {time_display}"
    else:
        schedule_desc = frequency

    # Tips based on reminder type
    tips = []
    if reminder_type == "medication":
        tips = [
            "Set reminders around meals if medication should be taken with food",
            "Use a pill organizer to track daily doses",
            "Keep medications visible (but safe) as a visual reminder",
        ]
    elif reminder_type == "measurement":
        tips = [
            "Take measurements at the same time each day for consistency",
            "Rest 5 minutes before blood pressure measurements",
            "Keep a log of all measurements",
        ]
    elif reminder_type == "exercise":
        tips = [
            "Start with achievable goals and gradually increase",
            "Prepare workout clothes the night before",
            "Find an exercise buddy for accountability",
        ]

    return ToolResult(
        success=True,
        data={
            "reminder_id": reminder_id,
            "type": reminder_type,
            "title": title,
            "schedule": schedule_desc,
            "time": time_display,
            "frequency": frequency,
            "days": days,
            "notes": notes,
            "status": "active",
            "tips": tips,
            "message": f"Reminder '{title}' has been set: {schedule_desc}",
        },
    )


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import asyncio
    from .tool_registry import get_tool_registry, execute_tool

    async def test_health_tools():
        print("Testing Health Tools...")

        registry = get_tool_registry()

        # List all health tools
        print(f"\n📋 Registered health tools: {len(registry.list_tools())}")
        for tool in registry.list_tools():
            print(f"  - {tool.name}: {tool.description[:50]}...")

        # Test blood pressure analyzer
        print("\n🩺 Testing blood_pressure_analyzer:")
        result = await execute_tool(
            "blood_pressure_analyzer",
            {
                "systolic": 145,
                "diastolic": 92,
                "pulse": 78,
            },
        )
        print(f"  Result: {result.data['category']} - {result.data['reading']}")
        print(f"  Recommendations: {result.data['recommendations'][:2]}")

        # Test heart rate analyzer
        print("\n❤️ Testing heart_rate_analyzer:")
        result = await execute_tool(
            "heart_rate_analyzer",
            {
                "heart_rate": 72,
                "activity": "resting",
                "age": 45,
            },
        )
        print(f"  Result: {result.data['category']} - {result.data['heart_rate']} bpm")

        # Test BMI calculator
        print("\n📊 Testing bmi_calculator:")
        result = await execute_tool(
            "bmi_calculator",
            {
                "weight": 180,
                "weight_unit": "lbs",
                "height": 5.9,
                "height_unit": "ft",
            },
        )
        print(f"  BMI: {result.data['bmi']} - {result.data['category']}")

        # Test symptom triage
        print("\n🏥 Testing symptom_triage:")
        result = await execute_tool(
            "symptom_triage",
            {
                "symptoms": ["chest pain", "shortness of breath"],
                "severity": 7,
            },
        )
        print(f"  Urgency: {result.data['urgency']}")
        print(f"  Action: {result.data['action']}")

        # Test appointment scheduler
        print("\n📅 Testing appointment_scheduler:")
        result = await execute_tool(
            "appointment_scheduler",
            {
                "action": "check_availability",
                "appointment_type": "routine_checkup",
                "preferred_time": "morning",
            },
        )
        print(f"  Found {len(result.data['available_slots'])} slots")

        # Test reminder setter
        print("\n⏰ Testing health_reminder_setter:")
        result = await execute_tool(
            "health_reminder_setter",
            {
                "reminder_type": "medication",
                "title": "Take blood pressure medication",
                "frequency": "daily",
                "time": "08:00",
            },
        )
        print(f"  Created: {result.data['reminder_id']}")
        print(f"  Schedule: {result.data['schedule']}")

        # Stats
        print(f"\n📊 Registry stats: {registry.get_stats()}")

        print("\n✅ Health tools tests passed!")

    asyncio.run(test_health_tools())
