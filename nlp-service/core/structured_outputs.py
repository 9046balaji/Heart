"""
Structured Output Module for LLM Generation

This module implements schema-guided generation for LLMs, ensuring
responses follow predefined JSON structures. Uses Pydantic for schema
definition and validation.

Key Concepts:
1. Schema Definition: Use Pydantic models to define output structure
2. Constrained Generation: Send JSON schema to LLM to guide output
3. Validation: Parse and validate LLM output against schema
4. Fallback: Handle malformed outputs gracefully
"""

import json
import logging
import re
from enum import Enum
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
)

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# ============================================================================
# PART 1: Structured Output Schemas (Pydantic Models)
# ============================================================================


class ResponseConfidence(str, Enum):
    """Confidence levels for LLM responses"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class HealthIntent(str, Enum):
    """Healthcare-specific intents"""

    SYMPTOM_REPORT = "symptom_report"
    MEDICATION_QUESTION = "medication_question"
    LIFESTYLE_ADVICE = "lifestyle_advice"
    EMERGENCY = "emergency"
    APPOINTMENT = "appointment"
    GENERAL_HEALTH = "general_health"
    VITAL_SIGNS = "vital_signs"
    DIET_NUTRITION = "diet_nutrition"
    EXERCISE = "exercise"
    MENTAL_HEALTH = "mental_health"
    UNKNOWN = "unknown"


class UrgencyLevel(str, Enum):
    """Urgency classification for health queries"""

    CRITICAL = "critical"  # Requires immediate attention (e.g., chest pain)
    HIGH = "high"  # Should see doctor soon
    MODERATE = "moderate"  # Can wait for regular appointment
    LOW = "low"  # General information/advice
    INFORMATIONAL = "informational"  # Just seeking knowledge


class ExtractedEntity(BaseModel):
    """Entity extracted from user input"""

    entity_type: str = Field(
        ..., description="Type of entity (symptom, medication, body_part, etc.)"
    )
    value: str = Field(..., description="The extracted value")
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Confidence score for this extraction"
    )
    context: Optional[str] = Field(
        default=None, description="Additional context about the entity"
    )


class FollowUpQuestion(BaseModel):
    """Suggested follow-up question to ask the user"""

    question: str = Field(..., description="The follow-up question text")
    priority: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Priority of asking this question (1=highest)",
    )
    reason: Optional[str] = Field(
        default=None, description="Why this question is relevant"
    )


class HealthRecommendation(BaseModel):
    """A specific health recommendation"""

    recommendation: str = Field(..., description="The recommendation text")
    category: str = Field(
        ..., description="Category (lifestyle, medical, emergency, etc.)"
    )
    urgency: UrgencyLevel = Field(default=UrgencyLevel.LOW)
    evidence_based: bool = Field(
        default=False, description="Whether this is evidence-based advice"
    )


# ============================================================================
# PART 2: Main Structured Output Schemas
# ============================================================================


class CardioHealthAnalysis(BaseModel):
    """
    Structured output for cardiovascular health analysis.
    This is the main schema for health-related queries.
    """

    # Core analysis
    intent: HealthIntent = Field(..., description="Identified user intent")
    intent_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in intent classification"
    )

    # Sentiment and urgency
    sentiment: str = Field(
        ...,
        description="User sentiment (positive, neutral, negative, anxious, distressed)",
    )
    urgency: UrgencyLevel = Field(..., description="Urgency level of the query")

    # Extracted information
    entities: List[ExtractedEntity] = Field(
        default_factory=list, description="Entities extracted from the message"
    )

    # Response content
    response: str = Field(..., description="The main response to the user")
    explanation: Optional[str] = Field(
        default=None, description="Medical explanation if relevant"
    )

    # Recommendations and follow-ups
    recommendations: List[HealthRecommendation] = Field(
        default_factory=list, description="Health recommendations"
    )
    follow_up_questions: List[FollowUpQuestion] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )

    # Metadata
    requires_professional: bool = Field(
        default=False,
        description="Whether user should consult a healthcare professional",
    )
    disclaimer: Optional[str] = Field(
        default="This is AI-generated health information. Please consult a healthcare professional for medical advice.",
        description="Medical disclaimer",
    )
    confidence: ResponseConfidence = Field(
        default=ResponseConfidence.MEDIUM, description="Overall response confidence"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "intent": "symptom_report",
                "intent_confidence": 0.92,
                "sentiment": "anxious",
                "urgency": "moderate",
                "entities": [
                    {
                        "entity_type": "symptom",
                        "value": "chest pain",
                        "confidence": 0.95,
                    },
                    {"entity_type": "duration", "value": "2 days", "confidence": 0.88},
                ],
                "response": "I understand you're experiencing chest pain. This is a symptom that should be evaluated by a healthcare professional.",
                "explanation": "Chest pain can have many causes, from muscle strain to cardiac issues.",
                "recommendations": [
                    {
                        "recommendation": "See a doctor within 24 hours",
                        "category": "medical",
                        "urgency": "high",
                    }
                ],
                "follow_up_questions": [
                    {
                        "question": "Is the pain constant or does it come and go?",
                        "priority": 1,
                    }
                ],
                "requires_professional": True,
                "confidence": "high",
            }
        }


class SimpleIntentAnalysis(BaseModel):
    """
    Lightweight structured output for quick intent analysis.
    Use when you just need basic classification.
    """

    intent: str = Field(..., description="Identified intent category")
    confidence: float = Field(..., ge=0.0, le=1.0)
    keywords: List[str] = Field(
        default_factory=list, description="Key terms identified"
    )
    summary: str = Field(..., description="Brief summary of the query")


class ConversationResponse(BaseModel):
    """
    Structured output for general conversation responses.
    """

    response: str = Field(..., description="The response text")
    tone: str = Field(
        default="friendly",
        description="Response tone (friendly, professional, empathetic, urgent)",
    )
    topics: List[str] = Field(
        default_factory=list, description="Topics discussed in the response"
    )
    action_items: List[str] = Field(
        default_factory=list, description="Action items mentioned"
    )
    needs_clarification: bool = Field(
        default=False, description="Whether clarification is needed from user"
    )


class VitalSignsAnalysis(BaseModel):
    """
    Structured output for vital signs interpretation.
    """

    metric_type: str = Field(
        ..., description="Type of vital sign (heart_rate, blood_pressure, etc.)"
    )
    value: float = Field(..., description="The numeric value")
    unit: str = Field(..., description="Unit of measurement")
    status: str = Field(
        ..., description="Status assessment (normal, elevated, low, critical)"
    )
    interpretation: str = Field(..., description="Plain language interpretation")
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations based on the reading"
    )
    reference_range: Optional[str] = Field(
        default=None, description="Normal reference range for this metric"
    )


class MedicationInfo(BaseModel):
    """
    Structured output for medication-related queries.
    """

    medication_name: str = Field(..., description="Name of the medication")
    purpose: str = Field(..., description="What the medication is used for")
    common_side_effects: List[str] = Field(default_factory=list)
    interactions_warning: Optional[str] = Field(default=None)
    dosage_reminder: Optional[str] = Field(default=None)
    important_notes: List[str] = Field(default_factory=list)
    consult_doctor: bool = Field(
        default=True, description="Whether to recommend consulting a doctor"
    )


# ============================================================================
# PART 3: Schema Generation Utilities
# ============================================================================


def pydantic_to_json_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """
    Convert a Pydantic model to JSON Schema for LLM guidance.

    This function generates a JSON schema that can be sent to LLMs
    to guide their output generation.

    Args:
        model: A Pydantic BaseModel class

    Returns:
        JSON Schema dictionary
    """
    schema = model.model_json_schema()

    # Add strict mode indicators for LLM guidance
    schema["additionalProperties"] = False

    return schema


def get_schema_prompt(model: Type[BaseModel], include_example: bool = True) -> str:
    """
    Generate a prompt section that instructs the LLM to output
    according to the given schema.

    Args:
        model: Pydantic model class
        include_example: Whether to include an example in the prompt

    Returns:
        Prompt string for schema guidance
    """
    schema = pydantic_to_json_schema(model)

    prompt = f"""
You MUST respond with valid JSON that matches this exact schema:

```json
{json.dumps(schema, indent=2)}
```

IMPORTANT RULES:
1. Output ONLY valid JSON - no additional text before or after
2. Include ALL required fields
3. Use the exact field names as specified
4. Follow the data types exactly (string, number, array, etc.)
5. For enum fields, use only the allowed values
"""

    # Check for example in model_config (Pydantic v2 style)
    if include_example:
        model_config = getattr(model, "model_config", None) or getattr(
            model, "Config", None
        )
        json_schema_extra = None
        if model_config:
            if isinstance(model_config, dict):
                json_schema_extra = model_config.get("json_schema_extra")
            elif hasattr(model_config, "json_schema_extra"):
                json_schema_extra = getattr(model_config, "json_schema_extra", None)

        if json_schema_extra and isinstance(json_schema_extra, dict):
            example = json_schema_extra.get("example")
            if example:
                prompt += f"""
Example of a valid response:
```json
{json.dumps(example, indent=2)}
```
"""

    return prompt


def get_simplified_schema_prompt(model: Type[BaseModel]) -> str:
    """
    Generate a simplified schema prompt that's more token-efficient.
    Good for smaller models or when token count matters.
    """
    schema = model.model_json_schema()
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Build a simplified representation
    fields_desc = []
    for field_name, field_info in properties.items():
        field_type = field_info.get("type", "any")
        description = field_info.get("description", "")
        is_required = "REQUIRED" if field_name in required else "optional"

        # Handle enums
        if "enum" in field_info:
            allowed = ", ".join(f'"{v}"' for v in field_info["enum"])
            field_type = f"enum({allowed})"

        fields_desc.append(
            f"  - {field_name} ({field_type}, {is_required}): {description}"
        )

    prompt = f"""Respond with JSON matching this structure:
{{
{chr(10).join(fields_desc)}
}}

Output ONLY valid JSON. No additional text."""

    return prompt


# ============================================================================
# PART 4: Response Parsing and Validation
# ============================================================================


class StructuredOutputParser:
    """
    Parser for LLM responses that should match a schema.
    Handles validation, error recovery, and fallbacks.
    """

    def __init__(self, model: Type[BaseModel]):
        """
        Initialize parser with target schema.

        Args:
            model: Pydantic model class to parse into
        """
        self.model = model
        self.schema = pydantic_to_json_schema(model)

    def parse(self, llm_output: str) -> BaseModel:
        """
        Parse LLM output into the target model.

        Args:
            llm_output: Raw string output from LLM

        Returns:
            Parsed Pydantic model instance

        Raises:
            ValueError: If parsing fails after all recovery attempts
        """
        # Step 1: Try direct JSON parsing
        try:
            cleaned = self._extract_json(llm_output)
            data = json.loads(cleaned)
            return self.model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Initial parse failed: {e}")

        # Step 2: Try to fix common JSON issues
        try:
            fixed = self._fix_json(llm_output)
            data = json.loads(fixed)
            return self.model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Fixed parse failed: {e}")

        # Step 3: Try lenient parsing with defaults
        try:
            return self._lenient_parse(llm_output)
        except Exception as e:
            logger.error(f"All parsing attempts failed: {e}")
            raise ValueError(
                f"Could not parse LLM output into {self.model.__name__}: {e}"
            )

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text that might have surrounding content.
        """
        # Look for JSON in code blocks
        code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if code_block_match:
            return code_block_match.group(1).strip()

        # Look for JSON object pattern
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json_match.group(0)

        # Return as-is
        return text.strip()

    def _fix_json(self, text: str) -> str:
        """
        Attempt to fix common JSON formatting issues.
        """
        extracted = self._extract_json(text)

        # Fix trailing commas
        extracted = re.sub(r",(\s*[}\]])", r"\1", extracted)

        # Fix single quotes to double quotes
        extracted = extracted.replace("'", '"')

        # Fix unquoted keys
        extracted = re.sub(
            r"(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', extracted
        )

        # Fix True/False/None to JSON equivalents
        extracted = extracted.replace("True", "true")
        extracted = extracted.replace("False", "false")
        extracted = extracted.replace("None", "null")

        return extracted

    def _lenient_parse(self, text: str) -> BaseModel:
        """
        Attempt lenient parsing by extracting field values individually.
        """
        extracted = self._extract_json(text)

        # Try to build a partial object from what we can extract
        partial_data = {}
        schema_props = self.schema.get("properties", {})

        for field_name, field_info in schema_props.items():
            # Try to find field in text
            pattern = r'"' + field_name + r'"\s*:\s*([^,}]+)'
            match = re.search(pattern, extracted)
            if match:
                value = match.group(1).strip()
                # Clean up the value
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value in ("true", "false"):
                    value = value == "true"
                elif value == "null":
                    value = None
                else:
                    try:
                        value = float(value) if "." in value else int(value)
                    except ValueError:
                        pass
                partial_data[field_name] = value

        # For CardioHealthAnalysis, ensure required fields have defaults
        if self.model.__name__ == "CardioHealthAnalysis":
            if "intent" not in partial_data:
                partial_data["intent"] = "general_health"
            if "sentiment" not in partial_data:
                partial_data["sentiment"] = "neutral"
            if "urgency" not in partial_data:
                partial_data["urgency"] = "low"
            if "response" not in partial_data:
                partial_data["response"] = "Thank you for sharing information about your health. Please consult a healthcare professional for personalized advice."
            if "intent_confidence" not in partial_data:
                partial_data["intent_confidence"] = 0.5

        return self.model.model_validate(partial_data)

    def safe_parse(
        self, llm_output: str, default: Optional[BaseModel] = None
    ) -> Optional[BaseModel]:
        """
        Parse with fallback to default on failure.

        Args:
            llm_output: Raw LLM output
            default: Default value if parsing fails

        Returns:
            Parsed model or default
        """
        try:
            return self.parse(llm_output)
        except ValueError as e:
            logger.warning(f"Parsing failed, using default: {e}")
            return default


# ============================================================================
# PART 5: Type Variable for Generic Structured Generation
# ============================================================================

T = TypeVar("T", bound=BaseModel)


class StructuredGenerator(Generic[T]):
    """
    Generic wrapper for generating structured outputs from LLMs.

    Usage:
        generator = StructuredGenerator(CardioHealthAnalysis)
        result = await generator.generate(ollama_gen, "What are my vital signs?")
    """

    def __init__(self, output_model: Type[T], use_simplified_schema: bool = False):
        """
        Initialize with target output model.

        Args:
            output_model: Pydantic model class for output
            use_simplified_schema: Use token-efficient schema format
        """
        self.output_model = output_model
        self.parser = StructuredOutputParser(output_model)
        self.use_simplified_schema = use_simplified_schema

    def get_schema_prompt(self) -> str:
        """Get the schema prompt to inject into system message."""
        if self.use_simplified_schema:
            return get_simplified_schema_prompt(self.output_model)
        return get_schema_prompt(self.output_model)

    async def generate(
        self,
        ollama_generator,  # OllamaGenerator instance
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        additional_context: Optional[str] = None,
    ) -> T:
        """
        Generate a structured response from the LLM.

        Args:
            ollama_generator: OllamaGenerator instance
            user_message: User's input message
            conversation_history: Previous conversation
            additional_context: Extra context to include

        Returns:
            Parsed response matching output_model schema
        """
        # Build system prompt with schema
        system_prompt = self._build_system_prompt(additional_context)

        # Generate response
        raw_response = await ollama_generator.generate_response(
            prompt=user_message,
            conversation_history=conversation_history,
            system_prompt=system_prompt,
            stream=False,
        )

        # Parse and validate
        return self.parser.parse(raw_response)

    def _build_system_prompt(self, additional_context: Optional[str] = None) -> str:
        """Build the complete system prompt with schema instructions."""
        schema_prompt = self.get_schema_prompt()

        base_prompt = """You are a helpful healthcare AI assistant.
Your responses must be accurate, empathetic, and safety-conscious.
Always recommend professional medical consultation for serious concerns.

CRITICAL: Your response must be valid JSON matching the specified schema."""

        if additional_context:
            base_prompt += f"\n\nAdditional Context:\n{additional_context}"

        return f"{base_prompt}\n\n{schema_prompt}"


# ============================================================================
# PART 6: Pre-configured Generators for Common Use Cases
# ============================================================================


class HealthAnalysisGenerator(StructuredGenerator[CardioHealthAnalysis]):
    """Pre-configured generator for health analysis responses."""

    def __init__(self):
        super().__init__(CardioHealthAnalysis)

    def _build_system_prompt(self, additional_context: Optional[str] = None) -> str:
        schema_prompt = self.get_schema_prompt()

        base_prompt = """You are CardioHealth AI, a specialized cardiovascular health assistant.

Your role is to:
1. Analyze user health queries and symptoms
2. Identify potential cardiovascular concerns
3. Provide helpful, accurate health information
4. Recommend professional consultation when appropriate

Safety Guidelines:
- NEVER diagnose conditions - only provide information
- For ANY chest pain, shortness of breath, or cardiac symptoms, recommend immediate medical attention
- Always include appropriate medical disclaimers
- Be empathetic and supportive in your responses

CRITICAL: Respond ONLY with valid JSON matching the specified schema."""

        if additional_context:
            base_prompt += f"\n\nPatient Context:\n{additional_context}"

        return f"{base_prompt}\n\n{schema_prompt}"


class IntentAnalysisGenerator(StructuredGenerator[SimpleIntentAnalysis]):
    """Pre-configured generator for quick intent analysis."""

    def __init__(self):
        super().__init__(SimpleIntentAnalysis, use_simplified_schema=True)


class ConversationGenerator(StructuredGenerator[ConversationResponse]):
    """Pre-configured generator for general conversation."""

    def __init__(self):
        super().__init__(ConversationResponse)


# ============================================================================
# PART 7: Export All Public Classes and Functions
# ============================================================================

__all__ = [
    # Enums
    "ResponseConfidence",
    "HealthIntent",
    "UrgencyLevel",
    # Schema Models
    "ExtractedEntity",
    "FollowUpQuestion",
    "HealthRecommendation",
    "CardioHealthAnalysis",
    "SimpleIntentAnalysis",
    "ConversationResponse",
    "VitalSignsAnalysis",
    "MedicationInfo",
    # Utilities
    "pydantic_to_json_schema",
    "get_schema_prompt",
    "get_simplified_schema_prompt",
    # Parser
    "StructuredOutputParser",
    # Generators
    "StructuredGenerator",
    "HealthAnalysisGenerator",
    "IntentAnalysisGenerator",
    "ConversationGenerator",
]
