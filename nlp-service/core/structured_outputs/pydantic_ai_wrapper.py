"""
PydanticAI Wrapper for Cardio AI structured outputs.

This module uses PydanticAI for guaranteed schema-compliant outputs.
"""

import os
import logging
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

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