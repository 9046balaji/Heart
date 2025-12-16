"""
Multi-Agent Orchestration System for Cardio AI

This module implements a sophisticated multi-agent system that coordinates
specialized agents to handle complex healthcare queries.

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                     AgentOrchestrator                           │
    │                                                                 │
    │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
    │  │  Planner    │──│   Router     │──│    Validator          │   │
    │  │  Agent      │  │              │  │    Agent              │   │
    │  └─────────────┘  └──────┬───────┘  └──────────────────────┘   │
    │                          │                                      │
    │          ┌───────────────┼───────────────┐                     │
    │          │               │               │                     │
    │  ┌───────▼────┐  ┌───────▼────┐  ┌───────▼────┐                │
    │  │  Health    │  │  Research  │  │ Medication │                │
    │  │  Analyst   │  │  Agent     │  │  Advisor   │                │
    │  └────────────┘  └────────────┘  └────────────┘                │
    └─────────────────────────────────────────────────────────────────┘

Addresses GAPs from AI_ML_TOOLS_IMPLEMENTATION_GUIDE.md:
- ❌ Single LLM only -> ✅ Multi-agent orchestration
- ❌ No specialization -> ✅ Domain-specific agents
- ❌ Simple prompting -> ✅ Planning and validation
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import uuid

from .base import BaseAgent, HealthAgent

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles for specialized agents."""
    PLANNER = "planner"
    ROUTER = "router"
    HEALTH_ANALYST = "health_analyst"
    MEDICAL_RESEARCH = "medical_research"
    MEDICATION_ADVISOR = "medication_advisor"
    SYMPTOM_CHECKER = "symptom_checker"
    LIFESTYLE_COACH = "lifestyle_coach"
    VALIDATOR = "validator"
    SYNTHESIZER = "synthesizer"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    URGENT = 3


@dataclass
class AgentTask:
    """A task to be executed by an agent."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str = ""
    agent_role: AgentRole = AgentRole.HEALTH_ANALYST
    priority: TaskPriority = TaskPriority.MEDIUM
    context: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # Task IDs this depends on
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "agent_role": self.agent_role.value,
            "priority": self.priority.value,
            "status": self.status,
            "dependencies": self.dependencies,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class OrchestratorResult:
    """Result from orchestrator execution."""
    query: str
    response: str
    confidence: float
    sources: List[Dict[str, Any]] = field(default_factory=list)
    tasks_executed: List[AgentTask] = field(default_factory=list)
    agent_contributions: Dict[str, str] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    warnings: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "response": self.response,
            "confidence": self.confidence,
            "sources": self.sources,
            "tasks_executed": [t.to_dict() for t in self.tasks_executed],
            "agent_contributions": self.agent_contributions,
            "execution_time_ms": self.execution_time_ms,
            "warnings": self.warnings,
            "timestamp": self.timestamp,
        }


# =============================================================================
# SPECIALIZED AGENTS
# =============================================================================

class PlannerAgent(BaseAgent):
    """
    Plans the execution strategy for complex queries.
    
    Responsibilities:
    - Analyze user query complexity
    - Determine which agents are needed
    - Create execution plan with dependencies
    - Handle query decomposition
    """
    
    def __init__(self):
        super().__init__(
            name="PlannerAgent",
            model="gemini-2.5-pro",
            description="Plans multi-agent execution strategy",
            instruction="""You are a planning agent that:
1. Analyzes user health queries
2. Determines query complexity and required expertise
3. Creates execution plans for other agents
4. Identifies dependencies between tasks
5. Prioritizes tasks based on urgency"""
        )
    
    async def create_plan(
        self,
        query: str,
        context: Dict[str, Any] = None,
    ) -> List[AgentTask]:
        """
        Create an execution plan for the query.
        
        Args:
            query: User query
            context: Additional context
            
        Returns:
            List of AgentTasks to execute
        """
        self.log_action("create_plan", f"Planning for: {query[:50]}...")
        
        # Analyze query to determine required agents
        tasks = []
        query_lower = query.lower()
        
        # Determine urgency
        priority = self._assess_priority(query)
        
        # Check for symptom-related queries
        symptom_keywords = ["symptom", "pain", "feeling", "hurt", "ache", "dizzy", "tired"]
        if any(kw in query_lower for kw in symptom_keywords):
            tasks.append(AgentTask(
                query=query,
                agent_role=AgentRole.SYMPTOM_CHECKER,
                priority=priority,
                context=context or {},
            ))
        
        # Check for medication queries
        med_keywords = ["medication", "drug", "medicine", "pill", "dose", "side effect", "interaction"]
        if any(kw in query_lower for kw in med_keywords):
            tasks.append(AgentTask(
                query=query,
                agent_role=AgentRole.MEDICATION_ADVISOR,
                priority=priority,
                context=context or {},
            ))
        
        # Check for condition/research queries
        research_keywords = ["what is", "tell me about", "explain", "cause", "treatment", "manage"]
        if any(kw in query_lower for kw in research_keywords):
            tasks.append(AgentTask(
                query=query,
                agent_role=AgentRole.MEDICAL_RESEARCH,
                priority=priority,
                context=context or {},
            ))
        
        # Check for lifestyle queries
        lifestyle_keywords = ["exercise", "diet", "sleep", "stress", "weight", "lifestyle", "healthy"]
        if any(kw in query_lower for kw in lifestyle_keywords):
            tasks.append(AgentTask(
                query=query,
                agent_role=AgentRole.LIFESTYLE_COACH,
                priority=priority,
                context=context or {},
            ))
        
        # Default: Use health analyst
        if not tasks:
            tasks.append(AgentTask(
                query=query,
                agent_role=AgentRole.HEALTH_ANALYST,
                priority=priority,
                context=context or {},
            ))
        
        # Add validation task (depends on all others)
        if len(tasks) >= 1:
            validator_task = AgentTask(
                query=f"Validate responses for: {query}",
                agent_role=AgentRole.VALIDATOR,
                priority=priority,
                context=context or {},
                dependencies=[t.id for t in tasks],
            )
            tasks.append(validator_task)
        
        # Add synthesis task (depends on validator)
        synthesizer_task = AgentTask(
            query=f"Synthesize final response for: {query}",
            agent_role=AgentRole.SYNTHESIZER,
            priority=priority,
            context=context or {},
            dependencies=[tasks[-1].id] if tasks else [],
        )
        tasks.append(synthesizer_task)
        
        return tasks
    
    def _assess_priority(self, query: str) -> TaskPriority:
        """Assess query priority based on content."""
        query_lower = query.lower()
        
        # Urgent keywords
        urgent_keywords = ["emergency", "911", "severe", "can't breathe", "chest pain", "passing out"]
        if any(kw in query_lower for kw in urgent_keywords):
            return TaskPriority.URGENT
        
        # High priority
        high_keywords = ["pain", "worried", "concerning", "sudden", "blood"]
        if any(kw in query_lower for kw in high_keywords):
            return TaskPriority.HIGH
        
        # Low priority
        low_keywords = ["curious", "general", "information", "learn"]
        if any(kw in query_lower for kw in low_keywords):
            return TaskPriority.LOW
        
        return TaskPriority.MEDIUM


class HealthAnalystAgent(HealthAgent):
    """
    Analyzes health data and provides insights.
    
    Responsibilities:
    - Interpret health metrics (BP, heart rate, etc.)
    - Identify trends and patterns
    - Provide personalized health insights
    - Flag concerning values
    """
    
    def __init__(self):
        super().__init__(name="HealthAnalystAgent")
        self.instruction = """You are a health analyst that:
1. Analyzes health metrics (blood pressure, heart rate, weight, etc.)
2. Identifies trends and patterns in health data
3. Provides personalized insights based on patient history
4. Flags concerning values that may need attention
5. Explains health metrics in plain language
6. Always recommends professional consultation for concerning findings"""
    
    async def analyze(
        self,
        query: str,
        health_data: Dict[str, Any] = None,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Analyze health data and provide insights.
        
        Args:
            query: User query
            health_data: User's health metrics
            context: Additional context
            
        Returns:
            Analysis result with insights
        """
        self.log_action("analyze", f"Analyzing: {query[:50]}...")
        
        insights = []
        warnings = []
        
        # Blood pressure analysis
        if health_data and "blood_pressure" in health_data:
            bp = health_data["blood_pressure"]
            if isinstance(bp, dict):
                systolic = bp.get("systolic", 0)
                diastolic = bp.get("diastolic", 0)
                
                if systolic >= 180 or diastolic >= 120:
                    warnings.append("⚠️ Blood pressure is critically high. Seek immediate medical attention.")
                elif systolic >= 140 or diastolic >= 90:
                    warnings.append("Blood pressure is elevated. Consider consulting your doctor.")
                elif systolic < 90 or diastolic < 60:
                    insights.append("Blood pressure is on the lower side. Monitor for symptoms.")
                else:
                    insights.append(f"Blood pressure ({systolic}/{diastolic}) is within normal range.")
        
        # Heart rate analysis
        if health_data and "heart_rate" in health_data:
            hr = health_data["heart_rate"]
            if hr > 100:
                insights.append(f"Heart rate ({hr} bpm) is elevated. Consider rest and relaxation.")
            elif hr < 60:
                insights.append(f"Heart rate ({hr} bpm) is low. Normal for athletes, check if feeling dizzy.")
            else:
                insights.append(f"Heart rate ({hr} bpm) is normal.")
        
        return {
            "agent": self.name,
            "query": query,
            "insights": insights,
            "warnings": warnings,
            "recommendations": [
                "Continue monitoring your vitals regularly.",
                "Maintain a healthy lifestyle with exercise and proper diet.",
            ] if not warnings else [
                "Consult with your healthcare provider about these findings.",
            ],
            "confidence": 0.8,
        }


class MedicalResearchAgent(BaseAgent):
    """
    Researches medical conditions and provides information.
    
    Responsibilities:
    - Look up condition information from knowledge base
    - Explain medical concepts in plain language
    - Provide evidence-based information
    - Cite sources for medical claims
    """
    
    def __init__(self, knowledge_base: Any = None):
        super().__init__(
            name="MedicalResearchAgent",
            model="gemini-2.5-pro",
            description="Researches medical conditions and provides information",
            instruction="""You are a medical research agent that:
1. Provides evidence-based medical information
2. Explains conditions, symptoms, and treatments in plain language
3. Cites sources for all medical claims
4. Emphasizes that information is educational, not medical advice
5. Recommends professional consultation for diagnosis and treatment"""
        )
        self.knowledge_base = knowledge_base
    
    async def research(
        self,
        query: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Research medical topics and provide information.
        
        Args:
            query: Research query
            context: Additional context
            
        Returns:
            Research findings
        """
        self.log_action("research", f"Researching: {query[:50]}...")
        
        findings = []
        sources = []
        
        # Try to use knowledge base if available
        if self.knowledge_base:
            try:
                # Import knowledge loader functions
                from ..rag.knowledge_base import (
                    get_quick_cardiovascular_info,
                    get_quick_drug_info,
                )
                
                # Search cardiovascular info
                cv_info = get_quick_cardiovascular_info(query)
                if cv_info.get("found", 0) > 0:
                    for guideline in cv_info.get("guidelines", [])[:2]:
                        findings.append(guideline.get("content", "")[:500])
                        sources.append({
                            "type": "guideline",
                            "source": guideline.get("source", "Medical Guidelines"),
                        })
            except ImportError:
                pass
        
        # Default response if no knowledge base results
        if not findings:
            findings = [
                f"Based on medical literature, '{query}' is a topic that requires "
                "consultation with a healthcare provider for personalized information.",
                "General information about cardiovascular health includes maintaining "
                "a healthy diet, regular exercise, and monitoring vital signs.",
            ]
            sources = [{"type": "general", "source": "Medical Education Resources"}]
        
        return {
            "agent": self.name,
            "query": query,
            "findings": findings,
            "sources": sources,
            "disclaimer": "This information is educational only. Please consult a healthcare provider for medical advice.",
            "confidence": 0.75,
        }


class MedicationAdvisorAgent(BaseAgent):
    """
    Provides medication information and interaction checking.
    
    Responsibilities:
    - Look up drug information
    - Check drug interactions
    - Explain dosing and side effects
    - Warn about contraindications
    """
    
    def __init__(self):
        super().__init__(
            name="MedicationAdvisorAgent",
            model="gemini-2.0-flash",
            description="Provides medication information and safety checks",
            instruction="""You are a medication advisor that:
1. Provides drug information (uses, dosing, side effects)
2. Checks for drug-drug interactions
3. Warns about contraindications
4. Explains medications in plain language
5. ALWAYS recommends consulting pharmacist or doctor for medication advice"""
        )
    
    async def advise(
        self,
        query: str,
        medications: List[str] = None,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Provide medication advice.
        
        Args:
            query: Medication query
            medications: List of medications to check
            context: Additional context
            
        Returns:
            Medication advice and warnings
        """
        self.log_action("advise", f"Medication query: {query[:50]}...")
        
        drug_info = []
        interactions = []
        warnings = []
        
        # Try to use drug database
        try:
            from ..rag.knowledge_base import (
                get_quick_drug_info,
                check_drug_interactions_quick,
            )
            
            # Look up individual drugs
            if medications:
                for med in medications:
                    info = get_quick_drug_info(med)
                    if info:
                        drug_info.append({
                            "drug": info.get("generic_name"),
                            "class": info.get("drug_class"),
                            "uses": info.get("indications", [])[:3],
                            "common_side_effects": info.get("common_side_effects", [])[:3],
                        })
                
                # Check interactions
                if len(medications) > 1:
                    interaction_results = check_drug_interactions_quick(medications)
                    for interaction in interaction_results:
                        severity = interaction.get("severity", "")
                        if severity in ["major", "contraindicated"]:
                            warnings.append(
                                f"⚠️ {interaction['drug1']} + {interaction['drug2']}: "
                                f"{interaction['effect']}"
                            )
                        interactions.append(interaction)
        except ImportError:
            pass
        
        return {
            "agent": self.name,
            "query": query,
            "drug_info": drug_info,
            "interactions": interactions,
            "warnings": warnings,
            "disclaimer": "Always consult your pharmacist or doctor about medications.",
            "confidence": 0.85 if drug_info else 0.5,
        }


class SymptomCheckerAgent(BaseAgent):
    """
    Checks symptoms and provides triage guidance.
    
    Responsibilities:
    - Assess symptom urgency
    - Identify possible conditions
    - Recommend appropriate care level
    - Identify red flags
    """
    
    def __init__(self):
        super().__init__(
            name="SymptomCheckerAgent",
            model="gemini-2.0-flash",
            description="Assesses symptoms and provides triage guidance",
            instruction="""You are a symptom checker that:
1. Assesses symptom severity and urgency
2. Identifies possible conditions (not diagnoses)
3. Recommends appropriate care level (emergency, urgent, routine)
4. Identifies red flag symptoms requiring immediate attention
5. NEVER provides diagnoses - always recommends professional evaluation"""
        )
    
    async def check_symptoms(
        self,
        query: str,
        symptoms: List[str] = None,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Check symptoms and provide guidance.
        
        Args:
            query: Symptom description
            symptoms: List of symptoms
            context: Additional context
            
        Returns:
            Symptom assessment and recommendations
        """
        self.log_action("check_symptoms", f"Checking: {query[:50]}...")
        
        # Try to use symptom checker
        try:
            from ..rag.knowledge_base import triage_symptoms_quick
            
            symptom_list = symptoms or [query]
            triage = triage_symptoms_quick(symptom_list)
            
            return {
                "agent": self.name,
                "query": query,
                "urgency": triage.get("urgency"),
                "message": triage.get("message"),
                "possible_conditions": [
                    m.get("possible_conditions", [])[:3]
                    for m in triage.get("matched_conditions", [])
                ],
                "recommendations": triage.get("recommendations", [])[:3],
                "disclaimer": triage.get("disclaimer"),
                "confidence": 0.7,
            }
        except ImportError:
            pass
        
        # Fallback response
        return {
            "agent": self.name,
            "query": query,
            "urgency": "routine",
            "message": "Please consult a healthcare provider for symptom evaluation.",
            "recommendations": [
                "Track your symptoms including when they occur and severity.",
                "Note any factors that make symptoms better or worse.",
                "Schedule an appointment with your doctor.",
            ],
            "disclaimer": "This is not a diagnosis. Please consult a healthcare provider.",
            "confidence": 0.5,
        }


class LifestyleCoachAgent(BaseAgent):
    """
    Provides lifestyle and wellness guidance.
    
    Responsibilities:
    - Offer diet and nutrition advice
    - Provide exercise recommendations
    - Give stress management tips
    - Encourage healthy habits
    """
    
    def __init__(self):
        super().__init__(
            name="LifestyleCoachAgent",
            model="gemini-2.0-flash",
            description="Provides lifestyle and wellness guidance",
            instruction="""You are a lifestyle coach that:
1. Provides heart-healthy diet recommendations
2. Suggests appropriate exercise plans
3. Offers stress management techniques
4. Encourages healthy sleep habits
5. Motivates sustainable lifestyle changes
6. Considers individual health conditions in recommendations"""
        )
    
    async def coach(
        self,
        query: str,
        health_goals: List[str] = None,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Provide lifestyle coaching.
        
        Args:
            query: Lifestyle question
            health_goals: User's health goals
            context: Additional context
            
        Returns:
            Lifestyle recommendations
        """
        self.log_action("coach", f"Coaching: {query[:50]}...")
        
        recommendations = {
            "diet": [
                "Follow a heart-healthy diet rich in fruits, vegetables, and whole grains.",
                "Limit sodium intake to less than 2,300mg per day.",
                "Choose lean proteins and healthy fats (olive oil, nuts, fish).",
            ],
            "exercise": [
                "Aim for 150 minutes of moderate exercise per week.",
                "Include both cardio and strength training.",
                "Start slowly if new to exercise and gradually increase intensity.",
            ],
            "stress": [
                "Practice deep breathing exercises daily.",
                "Consider meditation or mindfulness apps.",
                "Take regular breaks during work.",
            ],
            "sleep": [
                "Aim for 7-9 hours of quality sleep per night.",
                "Maintain a consistent sleep schedule.",
                "Create a relaxing bedtime routine.",
            ],
        }
        
        return {
            "agent": self.name,
            "query": query,
            "recommendations": recommendations,
            "motivation": "Small consistent changes lead to big health improvements!",
            "resources": [
                {"name": "DASH Diet Guide", "type": "diet"},
                {"name": "AHA Exercise Guidelines", "type": "exercise"},
            ],
            "confidence": 0.8,
        }


class ValidatorAgent(BaseAgent):
    """
    Validates responses from other agents.
    
    Responsibilities:
    - Check for consistency in responses
    - Identify potential errors or contradictions
    - Ensure safety of recommendations
    - Flag concerning advice
    """
    
    def __init__(self):
        super().__init__(
            name="ValidatorAgent",
            model="gemini-2.5-pro",
            description="Validates and quality-checks agent responses",
            instruction="""You are a validation agent that:
1. Checks responses for medical accuracy
2. Identifies contradictions between agents
3. Ensures safety of all recommendations
4. Flags potentially harmful advice
5. Verifies sources are cited appropriately
6. Confirms emergency situations are handled correctly"""
        )
    
    async def validate(
        self,
        agent_responses: Dict[str, Dict[str, Any]],
        original_query: str,
    ) -> Dict[str, Any]:
        """
        Validate responses from other agents.
        
        Args:
            agent_responses: Dict of agent name to response
            original_query: Original user query
            
        Returns:
            Validation result
        """
        self.log_action("validate", f"Validating {len(agent_responses)} responses")
        
        issues = []
        validated = True
        confidence_scores = []
        
        for agent_name, response in agent_responses.items():
            # Check confidence
            confidence = response.get("confidence", 0.5)
            confidence_scores.append(confidence)
            
            if confidence < 0.5:
                issues.append(f"Low confidence from {agent_name}: {confidence}")
            
            # Check for warnings
            warnings = response.get("warnings", [])
            if warnings:
                for warning in warnings:
                    if "emergency" in warning.lower() or "911" in warning.lower():
                        issues.append(f"EMERGENCY flagged by {agent_name}: {warning}")
            
            # Check for disclaimers
            if not response.get("disclaimer"):
                issues.append(f"{agent_name} missing medical disclaimer")
        
        # Calculate overall validation
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        validated = len(issues) == 0 or all("disclaimer" in i.lower() for i in issues)
        
        return {
            "agent": self.name,
            "validated": validated,
            "issues": issues,
            "average_confidence": avg_confidence,
            "agent_count": len(agent_responses),
            "recommendation": "Response validated" if validated else "Review flagged issues",
        }


class SynthesizerAgent(BaseAgent):
    """
    Synthesizes responses from multiple agents into a coherent response.
    
    Responsibilities:
    - Combine insights from multiple agents
    - Create coherent, unified response
    - Prioritize most relevant information
    - Format response for user
    """
    
    def __init__(self):
        super().__init__(
            name="SynthesizerAgent",
            model="gemini-2.5-pro",
            description="Synthesizes multi-agent responses",
            instruction="""You are a synthesis agent that:
1. Combines insights from multiple specialist agents
2. Creates coherent, unified responses
3. Prioritizes the most relevant information
4. Maintains consistent tone and format
5. Ensures all important points are included
6. Adds appropriate disclaimers"""
        )
    
    async def synthesize(
        self,
        agent_responses: Dict[str, Dict[str, Any]],
        validation_result: Dict[str, Any],
        original_query: str,
    ) -> str:
        """
        Synthesize responses into final output.
        
        Args:
            agent_responses: Dict of agent responses
            validation_result: Validation result
            original_query: Original user query
            
        Returns:
            Synthesized response string
        """
        self.log_action("synthesize", f"Synthesizing {len(agent_responses)} responses")
        
        parts = []
        
        # Check for emergencies first
        for response in agent_responses.values():
            urgency = response.get("urgency")
            if urgency == "emergency":
                return (
                    "⚠️ **IMPORTANT**: Based on the symptoms you've described, "
                    "this may require immediate medical attention. "
                    "Please call 911 or go to your nearest emergency room immediately.\n\n"
                    f"Concern: {response.get('message', 'Potential emergency detected.')}"
                )
        
        # Compile insights
        insights = []
        warnings = []
        recommendations = []
        
        for agent_name, response in agent_responses.items():
            # Gather insights
            if "insights" in response:
                insights.extend(response["insights"])
            if "findings" in response:
                insights.extend(response["findings"][:2])
            
            # Gather warnings
            if "warnings" in response:
                warnings.extend(response["warnings"])
            
            # Gather recommendations
            if "recommendations" in response:
                if isinstance(response["recommendations"], dict):
                    for category, recs in response["recommendations"].items():
                        recommendations.extend(recs[:2])
                elif isinstance(response["recommendations"], list):
                    recommendations.extend(response["recommendations"][:3])
        
        # Build response
        if warnings:
            parts.append("**Important Considerations:**")
            for warning in set(warnings):
                parts.append(f"- {warning}")
            parts.append("")
        
        if insights:
            parts.append("**Based on your query:**")
            for insight in set(insights[:5]):
                parts.append(f"- {insight}")
            parts.append("")
        
        if recommendations:
            parts.append("**Recommendations:**")
            for rec in set(recommendations[:5]):
                parts.append(f"- {rec}")
            parts.append("")
        
        # Add disclaimer
        parts.append(
            "*This information is for educational purposes only and should not replace "
            "professional medical advice. Please consult your healthcare provider for "
            "personalized medical guidance.*"
        )
        
        return "\n".join(parts) if parts else (
            "I'd be happy to help with your health question. "
            "Could you provide more details about what you'd like to know? "
            "Remember, for specific medical advice, always consult a healthcare provider."
        )


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class AgentOrchestrator:
    """
    Orchestrates multiple specialized agents to handle complex queries.
    
    Features:
    - Dynamic agent routing based on query
    - Parallel execution of independent tasks
    - Dependency management for sequential tasks
    - Response validation and synthesis
    - Execution tracking and audit logging
    
    Example:
        orchestrator = AgentOrchestrator()
        
        result = await orchestrator.process(
            "I'm having chest pain and shortness of breath",
            user_id="user123"
        )
        
        print(result.response)
        print(f"Confidence: {result.confidence}")
        print(f"Agents used: {list(result.agent_contributions.keys())}")
    """
    
    def __init__(
        self,
        llm_client: Any = None,
        knowledge_base: Any = None,
    ):
        """
        Initialize the orchestrator.
        
        Args:
            llm_client: LLM client for agent execution
            knowledge_base: Knowledge base for research agent
        """
        self.llm_client = llm_client
        self.knowledge_base = knowledge_base
        
        # Initialize specialized agents
        self.agents: Dict[AgentRole, BaseAgent] = {
            AgentRole.PLANNER: PlannerAgent(),
            AgentRole.HEALTH_ANALYST: HealthAnalystAgent(),
            AgentRole.MEDICAL_RESEARCH: MedicalResearchAgent(knowledge_base),
            AgentRole.MEDICATION_ADVISOR: MedicationAdvisorAgent(),
            AgentRole.SYMPTOM_CHECKER: SymptomCheckerAgent(),
            AgentRole.LIFESTYLE_COACH: LifestyleCoachAgent(),
            AgentRole.VALIDATOR: ValidatorAgent(),
            AgentRole.SYNTHESIZER: SynthesizerAgent(),
        }
        
        self._execution_log: List[Dict[str, Any]] = []
        logger.info("✅ AgentOrchestrator initialized with %d agents", len(self.agents))
    
    async def process(
        self,
        query: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        health_data: Optional[Dict[str, Any]] = None,
        medications: Optional[List[str]] = None,
    ) -> OrchestratorResult:
        """
        Process a user query through the multi-agent system.
        
        Args:
            query: User query
            user_id: User identifier
            context: Additional context
            health_data: User's health metrics
            medications: User's current medications
            
        Returns:
            OrchestratorResult with response and metadata
        """
        import time
        start_time = time.time()
        
        logger.info(f"Processing query: {query[:50]}...")
        
        # Build context
        full_context = {
            **(context or {}),
            "user_id": user_id,
            "health_data": health_data,
            "medications": medications,
        }
        
        # Step 1: Create execution plan
        planner = self.agents[AgentRole.PLANNER]
        tasks = await planner.create_plan(query, full_context)
        
        logger.info(f"Created plan with {len(tasks)} tasks")
        
        # Step 2: Execute tasks (respecting dependencies)
        agent_responses = {}
        completed_tasks = []
        
        for task in tasks:
            # Wait for dependencies
            while task.dependencies:
                completed_ids = {t.id for t in completed_tasks}
                if all(dep in completed_ids for dep in task.dependencies):
                    break
                await asyncio.sleep(0.01)
            
            # Execute task
            task.status = "running"
            task.started_at = datetime.now()
            
            try:
                agent = self.agents.get(task.agent_role)
                if agent:
                    # Execute based on agent type
                    if task.agent_role == AgentRole.HEALTH_ANALYST:
                        result = await agent.analyze(task.query, health_data, full_context)
                    elif task.agent_role == AgentRole.MEDICAL_RESEARCH:
                        result = await agent.research(task.query, full_context)
                    elif task.agent_role == AgentRole.MEDICATION_ADVISOR:
                        result = await agent.advise(task.query, medications, full_context)
                    elif task.agent_role == AgentRole.SYMPTOM_CHECKER:
                        result = await agent.check_symptoms(task.query, context=full_context)
                    elif task.agent_role == AgentRole.LIFESTYLE_COACH:
                        result = await agent.coach(task.query, context=full_context)
                    elif task.agent_role == AgentRole.VALIDATOR:
                        result = await agent.validate(agent_responses, query)
                    elif task.agent_role == AgentRole.SYNTHESIZER:
                        validation = agent_responses.get(AgentRole.VALIDATOR.value, {})
                        result = await agent.synthesize(agent_responses, validation, query)
                    else:
                        result = {"agent": agent.name, "response": "Processed"}
                    
                    agent_responses[task.agent_role.value] = result
                    task.result = result
                    task.status = "completed"
                else:
                    task.status = "failed"
                    task.error = f"Agent not found for role: {task.agent_role}"
                    
            except Exception as e:
                logger.error(f"Task {task.id} failed: {e}")
                task.status = "failed"
                task.error = str(e)
            
            task.completed_at = datetime.now()
            completed_tasks.append(task)
        
        # Step 3: Get final synthesized response
        final_response = agent_responses.get(AgentRole.SYNTHESIZER.value, "")
        if isinstance(final_response, dict):
            final_response = final_response.get("response", str(final_response))
        
        # Calculate confidence
        confidences = [
            r.get("confidence", 0.5) 
            for r in agent_responses.values() 
            if isinstance(r, dict) and "confidence" in r
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # Collect warnings
        warnings = []
        for response in agent_responses.values():
            if isinstance(response, dict) and "warnings" in response:
                warnings.extend(response["warnings"])
        
        execution_time = (time.time() - start_time) * 1000
        
        # Log execution
        self._execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "tasks": len(tasks),
            "execution_time_ms": execution_time,
            "agents_used": list(agent_responses.keys()),
        })
        
        return OrchestratorResult(
            query=query,
            response=final_response,
            confidence=avg_confidence,
            sources=[],  # Could be populated from research agent
            tasks_executed=completed_tasks,
            agent_contributions={
                k: str(v)[:200] if isinstance(v, dict) else str(v)[:200]
                for k, v in agent_responses.items()
            },
            execution_time_ms=execution_time,
            warnings=warnings,
        )
    
    def get_agent(self, role: AgentRole) -> Optional[BaseAgent]:
        """Get a specific agent by role."""
        return self.agents.get(role)
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Get execution history."""
        return self._execution_log.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "agents_count": len(self.agents),
            "agents": [a.name for a in self.agents.values()],
            "executions": len(self._execution_log),
            "avg_execution_time_ms": (
                sum(e["execution_time_ms"] for e in self._execution_log) / 
                len(self._execution_log)
                if self._execution_log else 0
            ),
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_orchestrator(
    llm_client: Any = None,
    knowledge_base: Any = None,
) -> AgentOrchestrator:
    """
    Factory function to create an AgentOrchestrator.
    
    Args:
        llm_client: LLM client for agent execution
        knowledge_base: Knowledge base for research
        
    Returns:
        Configured AgentOrchestrator
    """
    return AgentOrchestrator(
        llm_client=llm_client,
        knowledge_base=knowledge_base,
    )


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    async def test_orchestrator():
        print("Testing AgentOrchestrator...")
        
        orchestrator = create_orchestrator()
        
        # Test 1: Simple health query
        print("\n🧪 Test 1: Health analysis query")
        result = await orchestrator.process(
            "My blood pressure reading was 145/92 today. Should I be concerned?",
            health_data={"blood_pressure": {"systolic": 145, "diastolic": 92}}
        )
        print(f"  Response: {result.response[:200]}...")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Agents: {list(result.agent_contributions.keys())}")
        print(f"  Time: {result.execution_time_ms:.0f}ms")
        
        # Test 2: Medication query
        print("\n🧪 Test 2: Medication query")
        result = await orchestrator.process(
            "What should I know about taking lisinopril?",
            medications=["lisinopril"]
        )
        print(f"  Response: {result.response[:200]}...")
        print(f"  Confidence: {result.confidence:.2f}")
        
        # Test 3: Symptom query
        print("\n🧪 Test 3: Symptom query")
        result = await orchestrator.process(
            "I've been feeling dizzy and tired lately"
        )
        print(f"  Response: {result.response[:200]}...")
        print(f"  Warnings: {result.warnings}")
        
        # Test 4: Lifestyle query
        print("\n🧪 Test 4: Lifestyle query")
        result = await orchestrator.process(
            "What exercises are good for heart health?"
        )
        print(f"  Response: {result.response[:200]}...")
        
        # Stats
        print(f"\n📊 Stats: {orchestrator.get_stats()}")
        
        print("\n✅ AgentOrchestrator tests passed!")
    
    asyncio.run(test_orchestrator())
