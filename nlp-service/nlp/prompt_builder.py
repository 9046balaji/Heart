"""
Healthcare Prompt Builder for AI Context Injection.

Implements structured prompt building based on chat.md architecture:
"Send it to the AI" with proper formatting and context injection.

This module provides:
- BuiltPrompt dataclass for complete prompts
- HealthcarePromptBuilder class for building AI-ready prompts
- Templates for healthcare-specific system prompts

Author: AI Memory System Implementation
Version: 1.0.0
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
from enum import Enum

from nlp.context_retrieval import RetrievedContext, ContextType

logger = logging.getLogger(__name__)


class CommunicationStyle(Enum):
    """Communication style preferences for responses."""

    FORMAL = "formal"
    CASUAL = "casual"
    DETAILED = "detailed"
    CONCISE = "concise"
    EMPATHETIC = "empathetic"


@dataclass
class BuiltPrompt:
    """
    Complete prompt ready for AI API call.

    Attributes:
        system_message: Full system prompt with context
        context_section: Just the context portion (for debugging)
        user_message: The user's actual query
        total_tokens_estimate: Estimated token count
        context_types_used: List of context types included
    """

    system_message: str
    context_section: str
    user_message: str
    total_tokens_estimate: int
    context_types_used: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthcarePromptBuilder:
    """
    Builds structured prompts for healthcare AI.

    Implements Section 8.C from chat.md:
    "Send it to the AI" with proper formatting

    Key Features:
    - Standardized system prompt template
    - Context organization by type
    - Token budget management
    - Healthcare compliance considerations
    - Customizable communication styles

    Usage:
        builder = HealthcarePromptBuilder()
        prompt = builder.build_prompt(
            user_query="What does my BP mean?",
            retrieved_contexts=contexts,
            user_name="John",
            patient_age=45
        )
    """

    # Base system prompt template
    SYSTEM_TEMPLATE = """You are a medical AI assistant for cardiac health.

IMPORTANT GUIDELINES:
- Never provide diagnosis. Only provide educational information.
- Always recommend consulting a healthcare provider for medical decisions.
- Be empathetic and clear in your responses.
- Reference the patient's context when relevant.
- If asked about emergencies, advise seeking immediate medical attention.
- Protect patient privacy - never share or repeat sensitive information unnecessarily.

{style_instructions}

{context_section}"""

    # Context section template
    CONTEXT_TEMPLATE = """
=== PATIENT CONTEXT ===
{patient_info}

=== RECENT VITALS ===
{vitals}

=== CURRENT MEDICATIONS ===
{medications}

=== MEDICAL HISTORY ===
{medical_history}

=== RISK ASSESSMENTS ===
{risk_assessments}

=== RECENT CONVERSATION ===
{conversation_summary}

=== USER PREFERENCES ===
{preferences}
"""

    # Minimal context template for shorter prompts
    MINIMAL_CONTEXT_TEMPLATE = """
=== CONTEXT ===
{patient_info}
{vitals}
{recent_conversation}
"""
    
    # Web search context template
    WEB_SEARCH_CONTEXT_TEMPLATE = """
## Web Search Results (External Sources)

The following information was retrieved from verified medical websites.
This is supplementary information and should be cited appropriately.

{web_results}

**IMPORTANT**: 
- Always cite the source URL when using this information
- Indicate this is from web search, not internal clinical data
- Include the standard medical disclaimer
- Do not present web information as clinical advice
"""

    # Style instruction templates
    STYLE_INSTRUCTIONS = {
        CommunicationStyle.FORMAL: "Use formal, professional language appropriate for medical communication.",
        CommunicationStyle.CASUAL: "Use friendly, approachable language while maintaining accuracy.",
        CommunicationStyle.DETAILED: "Provide comprehensive, detailed explanations with context.",
        CommunicationStyle.CONCISE: "Be brief and to the point. Use bullet points when helpful.",
        CommunicationStyle.EMPATHETIC: "Show empathy and understanding. Acknowledge patient concerns.",
    }

    def __init__(
        self,
        max_context_tokens: int = 2000,
        default_style: CommunicationStyle = CommunicationStyle.EMPATHETIC,
    ):
        """
        Initialize prompt builder.

        Args:
            max_context_tokens: Maximum tokens for context section
            default_style: Default communication style
        """
        self.max_context_tokens = max_context_tokens
        self.default_style = default_style

    def build_prompt(
        self,
        user_query: str,
        retrieved_contexts: List[RetrievedContext],
        user_name: Optional[str] = None,
        patient_age: Optional[int] = None,
        communication_style: Optional[CommunicationStyle] = None,
        minimal: bool = False,
        user_query_context: Optional[Dict[str, Any]] = None,
    ) -> BuiltPrompt:
        """
        Build complete prompt from retrieved context.

        Args:
            user_query: The user's current question
            retrieved_contexts: Context retrieved by ContextRetriever
            user_name: Patient's name (optional)
            patient_age: Patient's age (optional)
            communication_style: Preferred communication style
            minimal: Use minimal context template
            user_query_context: Additional context including web search results (optional)

        Returns:
            BuiltPrompt ready for AI API call
        """
        logger.debug(
            f"Building prompt for query: {user_query[:50]}... "
            f"with {len(retrieved_contexts)} context items"
        )

        # Organize context by type
        context_by_type = self._organize_contexts(retrieved_contexts)

        # Track which context types are used
        context_types_used = list(context_by_type.keys())

        # Build sections
        patient_info = self._build_patient_info(user_name, patient_age, context_by_type)

        vitals = self._build_vitals_section(context_by_type)
        medications = self._build_medications_section(context_by_type)
        medical_history = self._build_medical_history_section(context_by_type)
        risk_assessments = self._build_risk_section(context_by_type)
        conversation = self._build_conversation_section(context_by_type)
        preferences = self._build_preferences_section(context_by_type)
        
        # Check for web search results in context
        web_results = None
        if user_query_context and "web_search_results" in user_query_context:
            web_results = user_query_context.get("web_search_results")
        else:
            # Check if any context contains web search results
            for ctx_list in context_by_type.values():
                for ctx in ctx_list:
                    if ctx.context_type.value == "web_search" or "web_search" in str(ctx.data).lower():
                        web_results = ctx.data.get("web_search_results") or ctx.data
                        break
                if web_results:
                    break
        
        # Build context section
        if minimal:
            context_section = self.MINIMAL_CONTEXT_TEMPLATE.format(
                patient_info=patient_info or "No patient info available",
                vitals=vitals or "No recent vitals",
                recent_conversation=conversation or "New conversation",
            )
        else:
            # Add web search context if available
            web_context = ""
            if web_results:
                web_context = self.WEB_SEARCH_CONTEXT_TEMPLATE.format(web_results=web_results)
            
            context_section = self.CONTEXT_TEMPLATE.format(
                patient_info=patient_info or "Not available",
                vitals=vitals or "No recent vitals recorded",
                medications=medications or "No medications on file",
                medical_history=medical_history or "No history available",
                risk_assessments=risk_assessments or "No assessments available",
                conversation_summary=conversation or "New conversation",
                preferences=preferences or "Default settings",
            ) + web_context

        # Clean up empty sections
        context_section = self._clean_empty_sections(context_section)

        # Get style instructions
        style = communication_style or self.default_style
        style_instructions = self.STYLE_INSTRUCTIONS.get(
            style, self.STYLE_INSTRUCTIONS[CommunicationStyle.EMPATHETIC]
        )

        # Build system message
        system_message = self.SYSTEM_TEMPLATE.format(
            style_instructions=style_instructions, context_section=context_section
        )

        # Calculate token estimate
        total_tokens = self._estimate_tokens(system_message + user_query)

        logger.info(
            f"Built prompt: {total_tokens} tokens estimated, "
            f"context types: {[t.value for t in context_types_used]}"
        )

        return BuiltPrompt(
            system_message=system_message,
            context_section=context_section,
            user_message=user_query,
            total_tokens_estimate=total_tokens,
            context_types_used=[t.value for t in context_types_used],
            metadata={
                "user_name": user_name,
                "patient_age": patient_age,
                "style": style.value,
                "minimal": minimal,
                "built_at": datetime.utcnow().isoformat(),
            },
        )

    def build_emergency_prompt(
        self,
        user_query: str,
        retrieved_contexts: List[RetrievedContext],
        user_name: Optional[str] = None,
    ) -> BuiltPrompt:
        """
        Build prompt for emergency situations.

        Prioritizes medical history and emergency contact info.
        Uses urgent, clear communication style.
        """
        context_by_type = self._organize_contexts(retrieved_contexts)

        # Emergency-specific context
        emergency_context = """
=== EMERGENCY CONTEXT ===
{patient_info}

CRITICAL MEDICAL INFO:
{medical_history}

CURRENT MEDICATIONS (for emergency responders):
{medications}

EMERGENCY CONTACTS:
{emergency_info}
""".format(
            patient_info=self._build_patient_info(user_name, None, context_by_type)
            or "Unknown patient",
            medical_history=self._build_medical_history_section(context_by_type)
            or "No history available",
            medications=self._build_medications_section(context_by_type) or "Unknown",
            emergency_info=self._build_emergency_section(context_by_type)
            or "Not on file",
        )

        emergency_system = """You are a medical AI assistant responding to a potential emergency.

CRITICAL GUIDELINES:
- If this appears to be a life-threatening emergency, immediately advise calling emergency services (911).
- Provide clear, calm instructions.
- Do not delay with lengthy explanations.
- List any relevant medical information that emergency responders should know.

{context}""".format(
            context=emergency_context
        )

        return BuiltPrompt(
            system_message=emergency_system,
            context_section=emergency_context,
            user_message=user_query,
            total_tokens_estimate=self._estimate_tokens(emergency_system + user_query),
            context_types_used=[t.value for t in context_by_type.keys()],
            metadata={"emergency": True, "built_at": datetime.utcnow().isoformat()},
        )

    # ========================================================================
    # Context Organization Methods
    # ========================================================================

    def _organize_contexts(
        self, contexts: List[RetrievedContext]
    ) -> Dict[ContextType, List[RetrievedContext]]:
        """Group contexts by type."""
        organized: Dict[ContextType, List[RetrievedContext]] = {}
        for ctx in contexts:
            if ctx.context_type not in organized:
                organized[ctx.context_type] = []
            organized[ctx.context_type].append(ctx)
        return organized

    # ========================================================================
    # Section Building Methods
    # ========================================================================

    def _build_patient_info(
        self,
        name: Optional[str],
        age: Optional[int],
        contexts: Dict[ContextType, List[RetrievedContext]],
    ) -> Optional[str]:
        """Build patient information string."""
        parts = []

        if name:
            parts.append(f"- Name: {name}")
        if age:
            parts.append(f"- Age: {age} years")

        # Add preferences if available
        prefs_contexts = contexts.get(ContextType.USER_PREFERENCES, [])
        for pref_ctx in prefs_contexts:
            prefs = pref_ctx.data.get("preferences", {})
            if "language" in prefs:
                parts.append(f"- Preferred Language: {prefs['language']}")
            if "health_goals" in prefs:
                goals = prefs["health_goals"]
                if isinstance(goals, list):
                    goals = ", ".join(goals)
                parts.append(f"- Health Goals: {goals}")

        return "\n".join(parts) if parts else None

    def _build_vitals_section(
        self, contexts: Dict[ContextType, List[RetrievedContext]]
    ) -> Optional[str]:
        """Build vitals information string."""
        vitals_contexts = contexts.get(ContextType.RECENT_VITALS, [])
        if not vitals_contexts:
            return None

        parts = []
        for ctx in vitals_contexts:
            data = ctx.data

            # Handle vitals list
            vitals_list = data.get("vitals", [data])
            if not isinstance(vitals_list, list):
                vitals_list = [vitals_list]

            for vital in vitals_list:
                if "blood_pressure" in vital:
                    bp = vital["blood_pressure"]
                    if isinstance(bp, dict):
                        parts.append(
                            f"- Blood Pressure: {bp.get('systolic')}/{bp.get('diastolic')} mmHg"
                        )
                    else:
                        parts.append(f"- Blood Pressure: {bp}")

                if "blood_pressure_systolic" in vital:
                    parts.append(
                        f"- Blood Pressure: {vital['blood_pressure_systolic']}/"
                        f"{vital.get('blood_pressure_diastolic', '?')} mmHg"
                    )

                if "heart_rate" in vital:
                    parts.append(f"- Heart Rate: {vital['heart_rate']} bpm")

                if "spo2" in vital:
                    parts.append(f"- SpO2: {vital['spo2']}%")

                if "temperature" in vital:
                    parts.append(f"- Temperature: {vital['temperature']}°F")

                if "timestamp" in vital:
                    parts.append(f"  (Recorded: {vital['timestamp']})")

        return "\n".join(parts) if parts else None

    def _build_medications_section(
        self, contexts: Dict[ContextType, List[RetrievedContext]]
    ) -> Optional[str]:
        """Build medications information string."""
        med_contexts = contexts.get(ContextType.MEDICATIONS, [])
        if not med_contexts:
            return None

        parts = []
        for ctx in med_contexts:
            medications = ctx.data.get("medications", [])
            for med in medications:
                if isinstance(med, dict):
                    name = med.get("name", "Unknown")
                    dosage = med.get("dosage", "")
                    frequency = med.get("frequency", "")
                    parts.append(f"- {name} {dosage} {frequency}".strip())
                else:
                    parts.append(f"- {med}")

        return "\n".join(parts) if parts else None

    def _build_medical_history_section(
        self, contexts: Dict[ContextType, List[RetrievedContext]]
    ) -> Optional[str]:
        """Build medical history string."""
        history_contexts = contexts.get(ContextType.MEDICAL_HISTORY, [])
        if not history_contexts:
            return None

        parts = []
        for ctx in history_contexts:
            data = ctx.data

            if "conditions" in data:
                conditions = data["conditions"]
                if isinstance(conditions, list):
                    for cond in conditions:
                        parts.append(f"- Condition: {cond}")
                else:
                    parts.append(f"- Conditions: {conditions}")

            if "surgeries" in data:
                surgeries = data["surgeries"]
                if isinstance(surgeries, list):
                    for surg in surgeries:
                        parts.append(f"- Surgery: {surg}")

            if "allergies" in data:
                allergies = data["allergies"]
                if isinstance(allergies, list):
                    parts.append(f"- Allergies: {', '.join(allergies)}")
                else:
                    parts.append(f"- Allergies: {allergies}")

        return "\n".join(parts) if parts else None

    def _build_risk_section(
        self, contexts: Dict[ContextType, List[RetrievedContext]]
    ) -> Optional[str]:
        """Build risk assessments string."""
        risk_contexts = contexts.get(ContextType.RISK_ASSESSMENTS, [])
        if not risk_contexts:
            return None

        parts = []
        for ctx in risk_contexts:
            assessments = ctx.data.get("assessments", [ctx.data])
            if not isinstance(assessments, list):
                assessments = [assessments]

            for assessment in assessments:
                if "risk_level" in assessment:
                    parts.append(f"- Risk Level: {assessment['risk_level']}")
                if "risk_score" in assessment:
                    parts.append(f"- Risk Score: {assessment['risk_score']}")
                if "date" in assessment:
                    parts.append(f"  (Assessed: {assessment['date']})")
                if "recommendations" in assessment:
                    recs = assessment["recommendations"]
                    if isinstance(recs, list):
                        for rec in recs[:3]:  # Limit to 3 recommendations
                            parts.append(f"  - {rec}")

        return "\n".join(parts) if parts else None

    def _build_conversation_section(
        self, contexts: Dict[ContextType, List[RetrievedContext]]
    ) -> Optional[str]:
        """Build conversation summary string."""
        conv_contexts = contexts.get(ContextType.RECENT_CONVERSATIONS, [])
        if not conv_contexts:
            return None

        parts = []
        for ctx in conv_contexts:
            messages = ctx.data.get("messages", [])

            # Get last 5 messages for context
            for msg in messages[-5:]:
                role = msg.get("role", "unknown").capitalize()
                content = msg.get("content", "")

                # Truncate long messages
                if len(content) > 200:
                    content = content[:200] + "..."

                parts.append(f"{role}: {content}")

        return "\n".join(parts) if parts else None

    def _build_preferences_section(
        self, contexts: Dict[ContextType, List[RetrievedContext]]
    ) -> Optional[str]:
        """Build user preferences string."""
        pref_contexts = contexts.get(ContextType.USER_PREFERENCES, [])
        if not pref_contexts:
            return None

        parts = []
        for ctx in pref_contexts:
            prefs = ctx.data.get("preferences", {})

            if "communication_style" in prefs:
                parts.append(f"- Communication Style: {prefs['communication_style']}")
            if "preferred_units" in prefs:
                parts.append(f"- Preferred Units: {prefs['preferred_units']}")
            if "dietary_restrictions" in prefs:
                restrictions = prefs["dietary_restrictions"]
                if isinstance(restrictions, list):
                    restrictions = ", ".join(restrictions)
                parts.append(f"- Dietary Restrictions: {restrictions}")
            if "activity_level" in prefs:
                parts.append(f"- Activity Level: {prefs['activity_level']}")

        return "\n".join(parts) if parts else None

    def _build_emergency_section(
        self, contexts: Dict[ContextType, List[RetrievedContext]]
    ) -> Optional[str]:
        """Build emergency info string."""
        emergency_contexts = contexts.get(ContextType.EMERGENCY_INFO, [])
        if not emergency_contexts:
            return None

        parts = []
        for ctx in emergency_contexts:
            data = ctx.data

            if "emergency_contact" in data:
                contact = data["emergency_contact"]
                if isinstance(contact, dict):
                    parts.append(f"- Contact: {contact.get('name', 'Unknown')}")
                    parts.append(f"- Phone: {contact.get('phone', 'N/A')}")
                else:
                    parts.append(f"- Emergency Contact: {contact}")

            if "blood_type" in data:
                parts.append(f"- Blood Type: {data['blood_type']}")

            if "dnr_status" in data:
                parts.append(f"- DNR Status: {data['dnr_status']}")

        return "\n".join(parts) if parts else None

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _clean_empty_sections(self, text: str) -> str:
        """Remove empty sections from context."""
        lines = text.split("\n")
        cleaned_lines = []
        skip_next_empty = False

        for i, line in enumerate(lines):
            # Skip lines that are just section headers with empty content
            if line.startswith("===") and line.endswith("==="):
                # Check if next non-empty line is another header or end
                next_content = None
                for j in range(i + 1, len(lines)):
                    if lines[j].strip():
                        next_content = lines[j]
                        break

                if next_content and (
                    next_content.startswith("===")
                    or next_content
                    in [
                        "Not available",
                        "No recent vitals recorded",
                        "No medications on file",
                        "No history available",
                        "No assessments available",
                        "New conversation",
                        "Default settings",
                    ]
                ):
                    skip_next_empty = True
                    continue

            if skip_next_empty:
                if line.strip() in [
                    "Not available",
                    "No recent vitals recorded",
                    "No medications on file",
                    "No history available",
                    "No assessments available",
                    "New conversation",
                    "Default settings",
                    "",
                ]:
                    continue
                skip_next_empty = False

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough token estimate.

        Uses ~4 characters per token as approximation.
        More accurate estimation would use tiktoken.
        """
        return len(text) // 4


# ============================================================================
# Convenience Functions
# ============================================================================


def build_healthcare_prompt(
    user_query: str,
    retrieved_contexts: List[RetrievedContext],
    user_name: Optional[str] = None,
    patient_age: Optional[int] = None,
    user_query_context: Optional[Dict[str, Any]] = None,
) -> BuiltPrompt:
    """
    Convenience function to build a healthcare prompt.

    Args:
        user_query: User's question
        retrieved_contexts: List of context items
        user_name: Patient name
        patient_age: Patient age
        user_query_context: Additional context including web search results (optional)

    Returns:
        BuiltPrompt ready for AI call
    """
    builder = HealthcarePromptBuilder()
    return builder.build_prompt(
        user_query=user_query,
        retrieved_contexts=retrieved_contexts,
        user_name=user_name,
        patient_age=patient_age,
        user_query_context=user_query_context,
    )


# ============================================================================
# Singleton Instance
# ============================================================================

# Default prompt builder instance
prompt_builder = HealthcarePromptBuilder()
