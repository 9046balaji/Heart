"""
Prompt Templates for Health Chatbot
Carefully crafted prompts for medical context.

This module provides structured prompts for the LLM to generate
appropriate health-related responses based on anomaly type and severity.
"""

from enum import Enum
from typing import Optional, Tuple
from dataclasses import dataclass, field


class ResponseTone(Enum):
    """Tone for chatbot responses based on severity."""

    CALM = "calm"  # Normal readings
    CONCERNED = "concerned"  # Minor anomalies
    URGENT = "urgent"  # Warning level
    EMERGENCY = "emergency"  # Critical - direct to help


@dataclass
class PromptContext:
    """
    Context for generating prompts.

    Contains all the information needed to generate appropriate
    prompts for the chatbot.
    """

    # Anomaly Data
    anomaly_type: str
    severity: str
    current_value: float
    threshold: float

    # User Context
    user_name: str = "there"
    user_age: Optional[int] = None
    is_resting: bool = True
    recent_activity: str = "unknown"

    # Medical History (if available)
    has_heart_condition: bool = False
    medications: list = field(default_factory=list)

    # Response Settings
    language: str = "en"
    tone: ResponseTone = ResponseTone.CALM


# ============== SYSTEM PROMPTS ==============

SYSTEM_PROMPT_HEALTH_ASSISTANT = """You are CardioAI, a friendly and knowledgeable cardiac health assistant.

IMPORTANT GUIDELINES:
1. You are NOT a doctor. Always recommend consulting healthcare professionals for medical advice.
2. Be calm and reassuring - avoid causing panic.
3. Explain medical terms in simple language.
4. Provide actionable, practical advice.
5. Ask follow-up questions to understand context.
6. If the situation is truly critical, clearly state "Seek immediate medical attention."

RESPONSE STYLE:
- Use empathetic, conversational language
- Keep responses concise (2-4 sentences for alerts)
- Include ONE practical recommendation
- End with a supportive note or follow-up question

MEDICAL KNOWLEDGE:
- Normal resting heart rate: 60-100 bpm
- Athletes may have lower resting HR (40-60 bpm)
- Normal SpO2: 95-100%
- HRV (SDNN) normal range: 20-70ms
- Exercise can temporarily increase HR to 150-180 bpm (age-dependent)
"""


# ============== ANOMALY-SPECIFIC PROMPTS ==============

PROMPT_TEMPLATES = {
    # Tachycardia (High Heart Rate)
    "tachycardia": {
        "warning": """
The user's smartwatch detected an elevated heart rate.

CURRENT READINGS:
- Heart Rate: {current_value:.0f} bpm (threshold: {threshold:.0f} bpm)
- Activity Status: {activity_status}
- Time: {timestamp}

USER CONTEXT:
- Name: {user_name}
- Age: {user_age}
- Resting: {is_resting}
- Recent Activity: {recent_activity}

TASK:
1. Acknowledge the elevated reading calmly
2. Provide possible explanations (stress, caffeine, exercise, dehydration)
3. Give ONE specific actionable recommendation
4. Ask if they're experiencing any symptoms (chest pain, dizziness, shortness of breath)

Respond in a {tone} tone. Keep it under 100 words.
""",
        "critical": """
⚠️ CRITICAL ALERT: Very high heart rate detected.

READINGS:
- Heart Rate: {current_value:.0f} bpm (threshold: {threshold:.0f} bpm)
- Activity Status: {activity_status}

USER INFO:
- Name: {user_name}
- Has heart condition: {has_heart_condition}

TASK:
1. Clearly state this needs attention
2. Tell them to STOP any activity and SIT DOWN
3. Ask about symptoms: chest pain, dizziness, difficulty breathing
4. If symptoms present, recommend calling emergency services or going to ER
5. If no symptoms, recommend resting and monitoring

Be direct but not panic-inducing. Prioritize their safety.
""",
    },
    # Bradycardia (Low Heart Rate)
    "bradycardia": {
        "warning": """
The user's smartwatch detected a low heart rate.

CURRENT READINGS:
- Heart Rate: {current_value:.0f} bpm (threshold: {threshold:.0f} bpm)
- Activity Status: {activity_status}

USER CONTEXT:
- Name: {user_name}
- Is athlete: {is_athlete}
- Time of day: {time_of_day}

TASK:
1. Acknowledge the low reading
2. Explain that low HR can be normal for athletes or during sleep
3. Ask about symptoms (fatigue, dizziness, fainting)
4. If this is unusual for them, suggest monitoring and noting when it occurs

Respond in a {tone}, reassuring tone.
""",
        "critical": """
⚠️ ALERT: Very low heart rate detected.

READINGS:
- Heart Rate: {current_value:.0f} bpm

This is below normal range and needs attention.

TASK:
1. Ask if they feel okay (dizziness, weakness, confusion)
2. If symptomatic, recommend seeking medical care immediately
3. If asymptomatic but not an athlete, recommend contacting their doctor
4. Do NOT dismiss this reading

Be calm but clear about the importance of follow-up.
""",
    },
    # Hypoxemia (Low Blood Oxygen)
    "hypoxemia": {
        "warning": """
The user's smartwatch detected lower than normal blood oxygen.

CURRENT READINGS:
- SpO2: {current_value:.0f}% (normal: 95-100%)

USER CONTEXT:
- Name: {user_name}
- Location/Activity: {recent_activity}

TASK:
1. Note that the reading is slightly below normal
2. Ask about breathing (shortness of breath, chest tightness)
3. Suggest taking deep breaths and checking in a few minutes
4. Mention that cold fingers or movement can affect readings

Reassure but don't dismiss. Suggest rechecking.
""",
        "critical": """
🚨 CRITICAL: Blood oxygen level is dangerously low.

READINGS:
- SpO2: {current_value:.0f}%

This is a medical emergency if accurate.

TASK:
1. Ask immediately: "Are you having trouble breathing?"
2. If yes: Tell them to call emergency services (911) NOW
3. If no: Ask them to reposition the sensor and take another reading
4. Suggest sitting upright and taking slow deep breaths
5. Do not minimize - SpO2 below 90% requires immediate attention

Be direct. This could be life-threatening.
""",
    },
    # Resting Tachycardia
    "resting_tachy": {
        "warning": """
The user has an elevated heart rate while resting.

READINGS:
- Heart Rate: {current_value:.0f} bpm
- Activity: Resting (minimal movement detected)
- Steps in last 5 min: {steps}

USER CONTEXT:
- Name: {user_name}
- Age: {user_age}

TASK:
1. Note that their resting HR is elevated
2. Ask about: caffeine, stress, illness, poor sleep, anxiety
3. Recommend: hydration, deep breathing, checking again in 10 min
4. If persistent, suggest tracking pattern and mentioning to doctor

Be supportive and curious about potential causes.
"""
    },
    # Low HRV
    "low_hrv": {
        "warning": """
Heart rate variability analysis shows reduced variability.

READINGS:
- HRV (SDNN): {current_value:.1f} ms (healthy range: 20-70ms)

USER CONTEXT:
- Name: {user_name}
- Recent stress level: {recent_activity}

TASK:
1. Explain HRV simply (variation in time between heartbeats)
2. Note that low HRV can indicate: stress, fatigue, overtraining
3. Suggest: rest, stress management, adequate sleep
4. Recommend tracking trends over days rather than single readings

Be educational and encouraging about lifestyle factors.
"""
    },
    # General Health Summary
    "daily_summary": """
Generate a friendly daily health summary for the user.

TODAY'S DATA:
- Average HR: {avg_hr:.0f} bpm
- Resting HR: {resting_hr:.0f} bpm
- Max HR: {max_hr:.0f} bpm
- Average SpO2: {avg_spo2:.0f}%
- Steps: {total_steps}
- Anomalies detected: {anomaly_count}

USER INFO:
- Name: {user_name}
- Goal: {health_goal}

TASK:
Create a brief, encouraging summary that:
1. Highlights positive metrics
2. Notes any areas for improvement
3. Compares to their typical baseline (if available)
4. Ends with an encouraging message

Keep it conversational and motivating.
""",
    # Symptom Check
    "symptom_check": """
The user reported symptoms along with their vitals.

VITALS:
- Heart Rate: {current_value:.0f} bpm
- SpO2: {spo2:.0f}%

REPORTED SYMPTOMS:
{symptoms}

USER INFO:
- Name: {user_name}
- Age: {user_age}

TASK:
1. Acknowledge their symptoms with empathy
2. Correlate symptoms with the vital signs if relevant
3. Ask clarifying questions (duration, severity, triggers)
4. Based on severity, recommend:
   - Mild: Monitor and rest
   - Moderate: Consult doctor within 24-48 hours
   - Severe: Seek immediate medical attention
5. NEVER diagnose - only provide guidance

Be caring and thorough but not alarming.
""",
}


def get_prompt_for_anomaly(
    anomaly_type: str, severity: str, context: PromptContext
) -> Tuple[str, str]:
    """
    Get system prompt and user prompt for a specific anomaly.

    Args:
        anomaly_type: Type of anomaly (e.g., "tachycardia", "hypoxemia")
        severity: Severity level (e.g., "WARNING", "CRITICAL")
        context: PromptContext with all relevant information

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = SYSTEM_PROMPT_HEALTH_ASSISTANT

    # Get template
    template_key = anomaly_type.lower().replace("_", "_")
    severity_key = "critical" if severity in ["CRITICAL", "EMERGENCY"] else "warning"

    if template_key in PROMPT_TEMPLATES:
        template = PROMPT_TEMPLATES[template_key]
        if isinstance(template, dict):
            user_template = template.get(severity_key, template.get("warning", ""))
        else:
            user_template = template
    else:
        # Fallback generic template
        user_template = """
The user's health monitor detected an anomaly.

TYPE: {anomaly_type}
VALUE: {current_value}
THRESHOLD: {threshold}
SEVERITY: {severity}

Provide a helpful, calm response explaining what this might mean
and what actions they should consider.
"""

    # Format the template
    user_prompt = user_template.format(
        current_value=context.current_value,
        threshold=context.threshold,
        anomaly_type=context.anomaly_type,
        severity=context.severity,
        user_name=context.user_name,
        user_age=context.user_age or "unknown",
        is_resting="Yes" if context.is_resting else "No",
        is_athlete="No",  # Could be from user profile
        recent_activity=context.recent_activity,
        activity_status="Resting" if context.is_resting else "Active",
        has_heart_condition=context.has_heart_condition,
        tone=context.tone.value,
        timestamp="now",
        time_of_day="current",
        steps=0,
        spo2=98,
        symptoms="",
        avg_hr=75,
        resting_hr=65,
        max_hr=120,
        avg_spo2=97,
        total_steps=5000,
        anomaly_count=0,
        health_goal="Stay healthy",
    )

    return system_prompt, user_prompt


def get_quick_response(anomaly_type: str, value: float) -> str:
    """
    Get a quick pre-written response for common scenarios.
    Use when LLM is unavailable or for instant feedback.

    Args:
        anomaly_type: Type of anomaly
        value: The anomalous value

    Returns:
        Pre-written response string
    """
    quick_responses = {
        ("tachycardia", "warning"): (
            f"Your heart rate is elevated at {value:.0f} bpm. Try taking slow, deep breaths "
            f"and resting for a few minutes. If you're not exercising, consider reducing caffeine or stress."
        ),
        ("tachycardia", "critical"): (
            f"⚠️ Your heart rate is very high at {value:.0f} bpm. Please stop any activity "
            f"and sit down. If you feel chest pain, dizziness, or shortness of breath, "
            f"seek medical attention immediately."
        ),
        ("bradycardia", "warning"): (
            f"Your heart rate is low at {value:.0f} bpm. This can be normal for athletes "
            f"or during sleep. If you feel dizzy or faint, please sit down and monitor how you feel."
        ),
        ("bradycardia", "critical"): (
            f"⚠️ Your heart rate is very low at {value:.0f} bpm. If you feel dizzy, weak, "
            f"or confused, please seek medical attention promptly."
        ),
        ("hypoxemia", "warning"): (
            f"Your blood oxygen is at {value:.0f}%, slightly below the normal 95-100% range. "
            f"Try taking some deep breaths and ensure the sensor is positioned correctly."
        ),
        ("hypoxemia", "critical"): (
            f"🚨 Your blood oxygen is at {value:.0f}%, which is below safe levels. "
            f"If you're having difficulty breathing, please call emergency services immediately."
        ),
        ("resting_tachy", "warning"): (
            f"Your resting heart rate is elevated at {value:.0f} bpm. "
            f"This could indicate stress, caffeine intake, or dehydration. Try to relax and hydrate."
        ),
        ("low_hrv", "warning"): (
            f"Your heart rate variability is low at {value:.1f}ms. "
            f"This may indicate stress or fatigue. Consider getting more rest and managing stress."
        ),
    }

    # Determine severity based on value
    severity = (
        "critical"
        if (
            (anomaly_type == "tachycardia" and value > 150)
            or (anomaly_type == "hypoxemia" and value < 90)
            or (anomaly_type == "bradycardia" and value < 45)
        )
        else "warning"
    )

    return quick_responses.get(
        (anomaly_type, severity),
        f"Your health reading shows {anomaly_type}. Please monitor and consult a healthcare provider if concerned.",
    )


def get_normal_response(user_name: str, hr: float, spo2: float) -> str:
    """
    Get a positive response for normal readings.

    Args:
        user_name: User's name for personalization
        hr: Current heart rate
        spo2: Current SpO2

    Returns:
        Encouraging message string
    """
    greeting = f"Hi {user_name}! " if user_name and user_name != "there" else ""
    return (
        f"{greeting}Your vitals look good! Heart rate: {hr:.0f} bpm, SpO2: {spo2:.0f}%. "
        f"Keep up the healthy lifestyle! 💚"
    )
