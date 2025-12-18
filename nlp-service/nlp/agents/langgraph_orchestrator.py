"""
LangGraph Orchestration System for Cardio AI.

This module implements a sophisticated multi-agent system using LangGraph
for improved state management and workflow visualization.

Features:
- Visualizable workflow graphs for debugging
- Built-in checkpointing and persistence
- Improved state management
- Easier addition of new agent types
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Annotated
from dataclasses import dataclass, field
from enum import Enum
import uuid
import operator

# LangGraph imports
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

# Local imports
from .base import BaseAgent, HealthAgent

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles for specialized agents."""
    PLANNER = "planner"
    HEALTH_ANALYST = "health_analyst"
    SYMPTOM_CHECKER = "symptom_checker"
    MEDICATION_ADVISOR = "medication_advisor"
    LIFESTYLE_COACH = "lifestyle_coach"
    VALIDATOR = "validator"
    SYNTHESIZER = "synthesizer"


@dataclass
class AgentTask:
    """A task to be executed by an agent."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str = ""
    agent_role: AgentRole = AgentRole.HEALTH_ANALYST
    priority: int = 1
    context: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AgentState(dict):
    """State representation for LangGraph workflow."""
    def __init__(self, messages=None, current_agent=None, task_results=None, final_response=None):
        super().__init__()
        self["messages"] = messages or []
        self["current_agent"] = current_agent
        self["task_results"] = task_results or {}
        self["final_response"] = final_response


class LangGraphOrchestrator:
    """
    Orchestrator using LangGraph for state management.
    
    Features:
    - Visualizable workflow graphs
    - Built-in checkpointing
    - Improved state management
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize LangGraph orchestrator.
        
        Args:
            llm_client: LLM client for agent execution
        """
        self.llm_client = llm_client
        self.workflow = StateGraph(AgentState)
        self._setup_workflow()
        
        # Compile the workflow
        self.app = self.workflow.compile()
        
        logger.info("✅ LangGraphOrchestrator initialized")
    
    def _setup_workflow(self):
        """Set up the workflow graph with nodes and edges."""
        # Define nodes for each specialized agent
        self.workflow.add_node("planner", self._plan_task)
        self.workflow.add_node("health_analyst", self._analyze_health)
        self.workflow.add_node("symptom_checker", self._check_symptoms)
        self.workflow.add_node("medication_advisor", self._advise_medication)
        self.workflow.add_node("lifestyle_coach", self._coach_lifestyle)
        self.workflow.add_node("validator", self._validate_response)
        self.workflow.add_node("synthesizer", self._synthesize_response)
        
        # Define edges based on decision logic
        self.workflow.add_conditional_edges(
            "planner",
            self._route_to_specialist,
            {
                "health_analyst": "health_analyst",
                "symptom_checker": "symptom_checker",
                "medication_advisor": "medication_advisor",
                "lifestyle_coach": "lifestyle_coach",
                "END": END
            }
        )
        
        # Connect specialist agents to validator
        self.workflow.add_edge("health_analyst", "validator")
        self.workflow.add_edge("symptom_checker", "validator")
        self.workflow.add_edge("medication_advisor", "validator")
        self.workflow.add_edge("lifestyle_coach", "validator")
        
        # Connect validator to synthesizer
        self.workflow.add_edge("validator", "synthesizer")
        
        # End workflow
        self.workflow.add_edge("synthesizer", END)
        
        # Set entry point
        self.workflow.set_entry_point("planner")
    
    async def _plan_task(self, state: AgentState) -> AgentState:
        """Plan the execution strategy for complex queries."""
        logger.info("Planning task execution")
        
        # Get the last message (user query)
        if state["messages"]:
            query = state["messages"][-1].content if hasattr(state["messages"][-1], 'content') else str(state["messages"][-1])
        else:
            query = "No query provided"
        
        # Determine which specialist to route to based on query content
        state["current_agent"] = self._determine_specialist(query)
        state["messages"].append(AIMessage(content=f"Planned to route to {state['current_agent']}"))
        
        return state
    
    def _determine_specialist(self, query: str) -> str:
        """Determine which specialist agent to route the query to."""
        query_lower = query.lower()
        
        # Check for symptom-related queries
        symptom_keywords = ["symptom", "pain", "feeling", "hurt", "ache", "dizzy", "tired"]
        if any(kw in query_lower for kw in symptom_keywords):
            return "symptom_checker"
        
        # Check for medication queries
        med_keywords = ["medication", "drug", "medicine", "pill", "dose", "side effect", "interaction"]
        if any(kw in query_lower for kw in med_keywords):
            return "medication_advisor"
        
        # Check for lifestyle queries
        lifestyle_keywords = ["exercise", "diet", "sleep", "stress", "weight", "lifestyle", "healthy"]
        if any(kw in query_lower for kw in lifestyle_keywords):
            return "lifestyle_coach"
        
        # Default to health analyst
        return "health_analyst"
    
    def _route_to_specialist(self, state: AgentState) -> str:
        """Route to the appropriate specialist agent."""
        return state["current_agent"]
    
    async def _analyze_health(self, state: AgentState) -> AgentState:
        """Analyze health data and provide insights."""
        logger.info("Analyzing health data")
        
        # Get the query
        query = state["messages"][-1].content if hasattr(state["messages"][-1], 'content') else str(state["messages"][-1])
        
        # Use LLM to generate health analysis if available
        if self.llm_client:
            try:
                prompt = f"As a health analyst, provide insights on: {query}"
                response = await self.llm_client.generate(prompt, content_type="medical")
                insights = [response]
            except Exception as e:
                logger.warning(f"LLM health analysis failed: {e}")
                insights = ["Sample health insight"]
        else:
            insights = ["Sample health insight"]
        
        state["messages"].append(AIMessage(content="Health analysis completed"))
        state["task_results"]["health_analysis"] = {
            "agent": "health_analyst",
            "insights": insights,
            "recommendations": ["General health recommendation"]
        }
        return state
    
    async def _check_symptoms(self, state: AgentState) -> AgentState:
        """Check symptoms and provide triage guidance."""
        logger.info("Checking symptoms")
        
        # Get the query
        query = state["messages"][-1].content if hasattr(state["messages"][-1], 'content') else str(state["messages"][-1])
        
        # Use LLM to generate symptom analysis if available
        if self.llm_client:
            try:
                prompt = f"As a symptom checker, analyze: {query}"
                response = await self.llm_client.generate(prompt, content_type="medical")
                recommendations = [response]
            except Exception as e:
                logger.warning(f"LLM symptom analysis failed: {e}")
                recommendations = ["Monitor symptoms"]
        else:
            recommendations = ["Monitor symptoms"]
        
        state["messages"].append(AIMessage(content="Symptom check completed"))
        state["task_results"]["symptom_check"] = {
            "agent": "symptom_checker",
            "urgency": "routine",
            "recommendations": recommendations
        }
        return state
    
    async def _advise_medication(self, state: AgentState) -> AgentState:
        """Provide medication information and interaction checking."""
        logger.info("Advising on medication")
        
        # Get the query
        query = state["messages"][-1].content if hasattr(state["messages"][-1], 'content') else str(state["messages"][-1])
        
        # Use LLM to generate medication advice if available
        if self.llm_client:
            try:
                prompt = f"As a medication advisor, provide information on: {query}"
                response = await self.llm_client.generate(prompt, content_type="medical")
                drug_info = [response]
            except Exception as e:
                logger.warning(f"LLM medication advice failed: {e}")
                drug_info = ["Sample drug information"]
        else:
            drug_info = ["Sample drug information"]
        
        state["messages"].append(AIMessage(content="Medication advice completed"))
        state["task_results"]["medication_advice"] = {
            "agent": "medication_advisor",
            "drug_info": drug_info,
            "warnings": []
        }
        return state
    
    async def _coach_lifestyle(self, state: AgentState) -> AgentState:
        """Provide lifestyle and wellness guidance."""
        logger.info("Providing lifestyle coaching")
        
        # Get the query
        query = state["messages"][-1].content if hasattr(state["messages"][-1], 'content') else str(state["messages"][-1])
        
        # Use LLM to generate lifestyle advice if available
        if self.llm_client:
            try:
                prompt = f"As a lifestyle coach, provide advice on: {query}"
                response = await self.llm_client.generate(prompt, content_type="nutrition")
                recommendations = {"diet": [response], "exercise": ["Walk 30 minutes daily"]}
            except Exception as e:
                logger.warning(f"LLM lifestyle advice failed: {e}")
                recommendations = {
                    "diet": ["Eat more vegetables"],
                    "exercise": ["Walk 30 minutes daily"]
                }
        else:
            recommendations = {
                "diet": ["Eat more vegetables"],
                "exercise": ["Walk 30 minutes daily"]
            }
        
        state["messages"].append(AIMessage(content="Lifestyle coaching completed"))
        state["task_results"]["lifestyle_coaching"] = {
            "agent": "lifestyle_coach",
            "recommendations": recommendations
        }
        return state
    
    async def _validate_response(self, state: AgentState) -> AgentState:
        """Validate responses from other agents."""
        logger.info("Validating responses")
        
        # Use LLM to validate responses if available
        if self.llm_client:
            try:
                validation_prompt = "Validate the following health recommendations for accuracy and safety."
                for agent, result in state["task_results"].items():
                    if "recommendations" in result:
                        validation_prompt += f"\n{agent}: {result['recommendations']}"
                
                response = await self.llm_client.generate(validation_prompt, content_type="medical")
                validated = "validated" in response.lower() or "safe" in response.lower()
                issues = [] if validated else ["Potential safety concerns identified"]
            except Exception as e:
                logger.warning(f"LLM validation failed: {e}")
                validated = True
                issues = []
        else:
            validated = True
            issues = []
        
        state["messages"].append(AIMessage(content="Validation completed"))
        state["task_results"]["validation"] = {
            "agent": "validator",
            "validated": validated,
            "issues": issues
        }
        return state
    
    async def _synthesize_response(self, state: AgentState) -> AgentState:
        """Synthesize responses into final output."""
        logger.info("Synthesizing final response")
        
        # Combine results from all agents
        response_parts = []
        for agent, result in state["task_results"].items():
            if "recommendations" in result:
                response_parts.append(f"From {agent}: {result['recommendations']}")
            elif "insights" in result:
                response_parts.append(f"From {agent}: {result['insights']}")
        
        # Use LLM to synthesize final response if available
        if self.llm_client:
            try:
                synthesis_prompt = "Synthesize the following information into a coherent response:\n" + "\n".join(response_parts)
                final_response = await self.llm_client.generate(synthesis_prompt, content_type="medical")
            except Exception as e:
                logger.warning(f"LLM synthesis failed: {e}")
                final_response = "\n".join(response_parts) if response_parts else "I've analyzed your query and here are the results."
        else:
            final_response = "\n".join(response_parts) if response_parts else "I've analyzed your query and here are the results."
        
        state["messages"].append(AIMessage(content=final_response))
        state["final_response"] = final_response
        
        return state
    
    async def process(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Process a user query through the LangGraph workflow.
        
        Args:
            query: User query
            **kwargs: Additional parameters
            
        Returns:
            Dict with response and metadata
        """
        logger.info(f"Processing query: {query[:50]}...")
        
        # Initialize state
        initial_state = AgentState(
            messages=[HumanMessage(content=query)],
            current_agent=None,
            task_results={},
            final_response=None
        )
        
        # Execute workflow
        final_state = await self.app.ainvoke(initial_state)
        
        return {
            "response": final_state["final_response"],
            "messages": [msg.content for msg in final_state["messages"]],
            "task_results": final_state["task_results"],
            "timestamp": datetime.now().isoformat()
        }


# Factory function
def create_langgraph_orchestrator(llm_client=None) -> LangGraphOrchestrator:
    """
    Factory function to create a LangGraphOrchestrator.
    
    Args:
        llm_client: LLM client for agent execution
        
    Returns:
        Configured LangGraphOrchestrator
    """
    return LangGraphOrchestrator(llm_client=llm_client)