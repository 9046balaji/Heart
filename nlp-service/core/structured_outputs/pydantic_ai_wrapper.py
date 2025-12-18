"""
PydanticAI Wrapper for Cardio AI structured outputs.

This module uses PydanticAI for guaranteed schema-compliant outputs.
"""

import os
import logging
import json
import re
from typing import List, Optional, Dict, Any, Type, TypeVar, Generic
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

# Check if PydanticAI is available
try:
    from pydantic_ai import Agent, RunContext
    PYDANTIC_AI_AVAILABLE = True
except ImportError:
    PYDANTIC_AI_AVAILABLE = False
    logger.warning("PydanticAI not available - install with: pip install pydantic-ai")


# Output schemas
class HealthRecommendation(BaseModel):
    recommendation: str = Field(description="The health recommendation")
    category: str = Field(description="Category: diet, exercise, medication, lifestyle")
    urgency: str = Field(description="Urgency: low, medium, high, critical")
    confidence: float = Field(ge=0, le=1, description="Confidence score")


class SymptomAssessment(BaseModel):
    symptoms: List[str] = Field(description="Identified symptoms")
    severity: str = Field(description="Overall severity: mild, moderate, severe")
    possible_conditions: List[str] = Field(description="Possible conditions")
    seek_medical_attention: bool = Field(description="Whether to seek immediate care")
    disclaimer: str = Field(
        default="This is not medical advice. Consult a healthcare provider.",
        description="Medical disclaimer"
    )


class CardioHealthAnalysis(BaseModel):
    intent: str = Field(description="Identified user intent")
    sentiment: str = Field(description="User sentiment: positive, neutral, negative, anxious")
    urgency: str = Field(description="Urgency level")
    recommendations: List[HealthRecommendation] = Field(default_factory=list)
    symptom_assessment: Optional[SymptomAssessment] = None
    response: str = Field(description="Main response to user")


class SimpleIntentAnalysis(BaseModel):
    """Simple intent analysis result."""
    intent: str = Field(description="Identified intent")
    confidence: float = Field(description="Confidence score")
    entities: List[str] = Field(default_factory=list, description="Extracted entities")


class ConversationResponse(BaseModel):
    """Structured conversation response."""
    response: str = Field(description="The response content")
    intent: Optional[str] = Field(description="Detected intent")
    confidence: float = Field(description="Confidence score")
    entities: List[str] = Field(default_factory=list, description="Extracted entities")
    next_action: Optional[str] = Field(description="Suggested next action")


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
        
        fields_desc.append(f"  - {field_name} ({field_type}, {is_required}): {description}")
    
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
            raise ValueError(f"Could not parse LLM output into {self.model.__name__}: {e}")
    
    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text that might have surrounding content.
        """
        # Look for JSON in code blocks
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if code_block_match:
            return code_block_match.group(1).strip()
        
        # Look for JSON object pattern
        json_match = re.search(r'\{[\s\S]*\}', text)
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
        extracted = re.sub(r',(\s*[}\]])', r'\1', extracted)
        
        # Fix single quotes to double quotes
        extracted = extracted.replace("'", '"')
        
        # Fix unquoted keys
        extracted = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', extracted)
        
        # Fix True/False/None to JSON equivalents
        extracted = extracted.replace('True', 'true')
        extracted = extracted.replace('False', 'false')
        extracted = extracted.replace('None', 'null')
        
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
                elif value in ('true', 'false'):
                    value = value == 'true'
                elif value == 'null':
                    value = None
                else:
                    try:
                        value = float(value) if '.' in value else int(value)
                    except ValueError:
                        pass
                partial_data[field_name] = value
        
        return self.model.model_validate(partial_data)
    
    def safe_parse(self, llm_output: str, default: Optional[BaseModel] = None) -> Optional[BaseModel]:
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

T = TypeVar('T', bound=BaseModel)


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


class PydanticHealthAgent:
    """
    Health agent using PydanticAI for structured outputs.
    
    Features:
    - Guaranteed schema compliance
    - Reduced parsing errors
    - Type-safe outputs
    - Better integration with type systems
    """
    
    def __init__(self, model: str = "gemini-1.5-flash"):
        if not PYDANTIC_AI_AVAILABLE:
            raise ImportError("PydanticAI not installed. Run: pip install pydantic-ai")
        
        self.model = model
        self.agent = Agent(
            model=model,
            result_type=CardioHealthAnalysis,
            system_prompt="""You are a cardiovascular health assistant.
            Analyze user queries and provide structured health guidance.
            Always include appropriate medical disclaimers.
            Never diagnose conditions - only provide information."""
        )
        
        logger.info(f"✅ PydanticHealthAgent initialized with {model}")
    
    async def analyze(self, user_message: str) -> CardioHealthAnalysis:
        """Analyze a user message and return structured output."""
        result = await self.agent.run(user_message)
        return result.data
    
    async def assess_symptoms(self, symptoms_description: str) -> SymptomAssessment:
        """Assess symptoms and return structured assessment."""
        symptom_agent = Agent(
            model=self.model,
            result_type=SymptomAssessment,
            system_prompt="""You are a symptom assessment assistant.
            Analyze described symptoms and provide structured assessment.
            Always err on the side of caution for medical recommendations."""
        )
        result = await symptom_agent.run(symptoms_description)
        return result.data
    
    async def get_recommendations(self, health_query: str) -> List[HealthRecommendation]:
        """Get health recommendations for a query."""
        result = await self.analyze(health_query)
        return result.recommendations


def create_pydantic_health_agent(model: Optional[str] = None) -> PydanticHealthAgent:
    """Factory function to create a PydanticHealthAgent."""
    return PydanticHealthAgent(model=model or "gemini-1.5-flash")