"""
CrewAI Healthcare Simulation for Cardio AI.

This module implements a multi-agent healthcare simulation using CrewAI
for dynamic agent collaboration and role-based specialization.

Features:
- Dynamic agent collaboration
- Role-based specialization
- Delegation and escalation capabilities
- Built-in task management
"""

import os
import logging
from typing import Dict, Any, List
from datetime import datetime

# CrewAI imports
try:
    from crewai import Agent, Task, Crew
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_ollama import ChatOllama
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    Agent = None
    Task = None
    Crew = None
    ChatGoogleGenerativeAI = None
    ChatOllama = None

logger = logging.getLogger(__name__)


class HealthcareCrew:
    """
    Healthcare Crew using CrewAI for multi-agent simulation.
    
    Features:
    - Dynamic agent collaboration
    - Role-based specialization
    - Delegation and escalation capabilities
    """
    
    def __init__(self, primary_provider: str = "gemini"):
        """
        Initialize Healthcare Crew.
        
        Args:
            primary_provider: "gemini" or "ollama" for LLM provider
        """
        self.primary_provider = primary_provider
        
        if not CREWAI_AVAILABLE:
            logger.warning("CrewAI not available. Simulation disabled.")
            self.llm = None
            self.cardiologist = None
            self.nutritionist = None
            self.pharmacist = None
            return
        
        # Initialize LLM
        if primary_provider == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key or api_key == "your-google-api-key-here":
                logger.warning("Google API key not configured, falling back to Ollama")
                self.llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "gemma3:1b"))
            else:
                self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key)
        else:
            self.llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "gemma3:1b"))
        
        # Define specialized agents
        self.cardiologist = Agent(
            role='Cardiologist',
            goal='Provide expert cardiovascular health advice',
            backstory='Expert cardiologist with 20+ years experience in diagnosing and treating heart conditions',
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
        
        self.nutritionist = Agent(
            role='Nutritionist',
            goal='Provide heart-healthy dietary recommendations',
            backstory='Registered dietitian specializing in cardiovascular health and nutrition therapy',
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
        
        self.pharmacist = Agent(
            role='Pharmacist',
            goal='Provide medication information and safety checks',
            backstory='Clinical pharmacist with expertise in drug interactions and cardiovascular medications',
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
        
        logger.info(f"✅ HealthcareCrew initialized with {primary_provider} provider")
    
    def coordinate_care(self, patient_query: str, patient_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Coordinate care among healthcare professionals.
        
        Args:
            patient_query: Patient's health query
            patient_context: Additional patient context (medical history, medications, etc.)
            
        Returns:
            Dict with coordinated care recommendations
        """
        if not CREWAI_AVAILABLE:
            return {
                "error": "CrewAI dependencies not installed",
                "timestamp": datetime.now().isoformat(),
                "success": False
            }

        logger.info(f"Coordinating care for: {patient_query[:50]}...")
        
        # Build context string
        context_str = ""
        if patient_context:
            context_str = "Patient Context:\n"
            for key, value in patient_context.items():
                context_str += f"- {key}: {value}\n"
        
        # Define tasks for each agent
        diagnosis_task = Task(
            description=f"""Analyze patient symptoms and provide medical assessment:
            Patient Query: {patient_query}
            {context_str}
            
            Provide:
            1. Medical assessment of symptoms
            2. Potential conditions to consider
            3. Recommendations for monitoring or treatment
            4. When to seek immediate medical attention""",
            agent=self.cardiologist,
            expected_output="Detailed medical assessment with recommendations"
        )
        
        nutrition_task = Task(
            description=f"""Develop dietary plan for cardiovascular health:
            Patient Query: {patient_query}
            {context_str}
            
            Provide:
            1. Heart-healthy dietary recommendations
            2. Foods to include and avoid
            3. Meal planning suggestions
            4. Nutritional considerations""",
            agent=self.nutritionist,
            expected_output="Personalized nutrition recommendations"
        )
        
        medication_task = Task(
            description=f"""Review medications and check for interactions:
            Patient Query: {patient_query}
            {context_str}
            
            Provide:
            1. Medication information and purpose
            2. Potential side effects to monitor
            3. Drug interaction warnings
            4. Adherence recommendations""",
            agent=self.pharmacist,
            expected_output="Medication review with safety information"
        )
        
        # Create and run crew
        crew = Crew(
            agents=[self.cardiologist, self.nutritionist, self.pharmacist],
            tasks=[diagnosis_task, nutrition_task, medication_task],
            verbose=2
        )
        
        # Execute crew
        try:
            result = crew.kickoff()
            
            return {
                "coordinated_care": str(result),
                "agents_involved": ["cardiologist", "nutritionist", "pharmacist"],
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
        except Exception as e:
            logger.error(f"Crew execution failed: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False
            }


# Factory function
def create_healthcare_crew(primary_provider: str = "gemini") -> HealthcareCrew:
    """
    Factory function to create a HealthcareCrew.
    
    Args:
        primary_provider: "gemini" or "ollama" for LLM provider
        
    Returns:
        Configured HealthcareCrew
    """
    return HealthcareCrew(primary_provider=primary_provider)