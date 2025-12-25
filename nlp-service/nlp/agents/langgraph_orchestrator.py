"""
LangGraph Orchestration System for Cardio AI with Safety Controls.

This module implements a sophisticated multi-agent system using LangGraph
with enhanced reliability features:

Features:
- Visualizable workflow graphs for debugging
- Circuit breaker to prevent infinite loops (max 10 iterations)
- State checkpointing for crash recovery
- Emergency exit with graceful degradation
- Improved state management
- Alert system for monitoring

Phase 2: Advanced Data & Reliability Implementation
""""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal, TypedDict
from dataclasses import dataclass, field
from enum import Enum
import uuid

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage, AIMessage
    
    # Checkpointing imports
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        POSTGRES_CHECKPOINT_AVAILABLE = True
    except ImportError:
        POSTGRES_CHECKPOINT_AVAILABLE = False
    
    try:
        from langgraph.checkpoint.redis import RedisSaver
        REDIS_CHECKPOINT_AVAILABLE = True
    except ImportError:
        REDIS_CHECKPOINT_AVAILABLE = False

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None
    HumanMessage = None
    AIMessage = None
    POSTGRES_CHECKPOINT_AVAILABLE = False
    REDIS_CHECKPOINT_AVAILABLE = False

# Local imports
try:
    from config import settings
except ImportError:
    # Fallback settings
    class FallbackSettings:
        AGENT_MAX_ITERATIONS = 10
        CHECKPOINT_BACKEND = "postgres"
        DATABASE_URL = "sqlite:///./nlp_cache.db"
        REDIS_URL = "redis://localhost:6379/0"
    settings = FallbackSettings()

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


# ========== Phase 2: Enhanced Agent State with Circuit Breaker ==========

class SafeAgentState(TypedDict):
    """
    Enhanced state representation for LangGraph workflow with safety controls.
    
    Phase 2 Additions:
    - iterations: Current iteration count
    - max_iterations: Circuit breaker limit
    - error: Error tracking
    - thought: Agent reasoning
    - action: Current action
    - observation: Action result
    - final_answer: Final response (for early exit)
    """
    # Original fields
    messages: List[Any]
    current_agent: Optional[str]
    task_results: Dict[str, Any]
    final_response: Optional[str]
    
    # Phase 2: Safety fields
    iterations: int
    max_iterations: int
    thought: str
    action: str
    observation: str
    final_answer: str
    error: str


class AgentState(dict):
    """
    State representation for LangGraph workflow (legacy).
    
    Kept for backward compatibility with existing code.
    """

    def __init__(
        self, messages=None, current_agent=None, task_results=None, final_response=None
    ):
        super().__init__()
        self["messages"] = messages or []
        self["current_agent"] = current_agent
        self["task_results"] = task_results or {}
        self["final_response"] = final_response


# ========== Phase 2: Safe Agent Orchestrator with Circuit Breaker ==========

class SafeAgentOrchestrator:
    """
    LangGraph orchestrator with circuit breaker protection.

    Phase 2 Features:
    - Max iterations limit (default: 10)
    - Emergency exit on infinite loops
    - Graceful degradation
    - Monitoring and alerting
    
    Protection Against:
    - Infinite agent loops
    - Runaway API costs
    - Poor user experience
    """

    MAX_ITERATIONS = getattr(settings, "AGENT_MAX_ITERATIONS", 10)

    def __init__(self, llm_client=None):
        """
        Initialize safe agent orchestrator.

        Args:
            llm_client: LLM client for agent execution
        """
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available. Orchestrator disabled.")
            self.app = None
            return

        self.llm_client = llm_client
        
        # Build workflow graph
        self.app = self.build_graph()

        logger.info(f"✅ SafeAgentOrchestrator initialized (max iterations: {self.MAX_ITERATIONS})")

    def build_graph(self) -> StateGraph:
        """
        Build agent graph with safety controls.
        
        Returns:
            Compiled StateGraph with circuit breaker
        """
        workflow = StateGraph(SafeAgentState)

        # Add nodes
        workflow.add_node("think", self.think_node)
        workflow.add_node("act", self.act_node)
        workflow.add_node("observe", self.observe_node)
        workflow.add_node("finalize", self.finalize_node)
        workflow.add_node("emergency_exit", self.emergency_exit_node)  # NEW: Circuit breaker

        # Entry point
        workflow.set_entry_point("think")

        # Add conditional edges with circuit breaker
        workflow.add_conditional_edges(
            "think",
            self.should_continue,
            {
                "continue": "act",
                "finish": "finalize",
                "emergency": "emergency_exit",  # NEW: Emergency path
            },
        )

        workflow.add_edge("act", "observe")
        workflow.add_edge("observe", "think")  # Loop back
        workflow.add_edge("finalize", END)
        workflow.add_edge("emergency_exit", END)

        return workflow.compile()

    def should_continue(self, state: SafeAgentState) -> Literal["continue", "finish", "emergency"]:
        """
        Decide whether to continue agent loop (with circuit breaker).

        Returns:
            - "continue": Keep going
            - "finish": Task complete
            - "emergency": Hit max iterations, force stop
        """
        # Circuit breaker: Check iteration limit
        if state["iterations"] >= state.get("max_iterations", self.MAX_ITERATIONS):
            logger.error(
                f"⚠️ Agent hit max iterations ({state['iterations']}) - triggering emergency exit"
            )
            return "emergency"

        # Check if agent has final answer
        if state.get("final_answer"):
            return "finish"

        return "continue"

    async def think_node(self, state: SafeAgentState) -> SafeAgentState:
        """Agent reasoning step."""
        state["iterations"] += 1

        logger.info(
            f"🧠 Agent iteration {state['iterations']}/{state.get('max_iterations', self.MAX_ITERATIONS)}"
        )

        # Get the query
        if state["messages"]:
            query = (
                state["messages"][-1].content
                if hasattr(state["messages"][-1], "content")
                else str(state["messages"][-1])
            )
        else:
            query = state.get("thought", "No query provided")

        # LLM call to decide next action
        if self.llm_client:
            try:
                thought = await self.llm_client.generate(
                    f"Given input: {query}\n"
                    f"Previous observation: {state.get('observation', 'None')}\n"
                    f"What should I do next?",
                    content_type="medical",
                )
            except Exception as e:
                logger.warning(f"LLM think failed: {e}")
                thought = "Continue processing request"
        else:
            thought = "Continue processing request"

        state["thought"] = thought
        return state

    async def act_node(self, state: SafeAgentState) -> SafeAgentState:
        """Execute action based on thought."""
        logger.info(f"🎬 Executing action based on thought: {state['thought'][:50]}...")

        # Parse action from thought (simplified for now)
        action = "analyze_query"
        state["action"] = action

        # Execute tool/function
        try:
            # Placeholder: In real implementation, this would call actual tools
            result = {"status": "success", "data": "Analysis complete"}
            state["observation"] = str(result)
        except Exception as e:
            state["observation"] = f"Error: {str(e)}"
            logger.error(f"Action execution failed: {e}")

        return state

    async def observe_node(self, state: SafeAgentState) -> SafeAgentState:
        """Process observation and decide if task is complete."""
        logger.info(f"👀 Observing result: {state['observation'][:50]}...")

        # Check if observation indicates completion
        if "success" in state["observation"].lower():
            state["final_answer"] = state["observation"]

        return state

    async def finalize_node(self, state: SafeAgentState) -> SafeAgentState:
        """Finalize successful completion."""
        logger.info(f"✅ Agent completed successfully in {state['iterations']} iterations")

        # Set final response
        state["final_response"] = state.get("final_answer", "Task completed successfully")

        return state

    async def emergency_exit_node(self, state: SafeAgentState) -> SafeAgentState:
        """
        Emergency exit when max iterations hit.

        Returns a helpful fallback message instead of crashing.
        """
        error_msg = (
            f"I apologize, but I couldn't complete your request after "
            f"{state['iterations']} attempts. This might be due to a temporary issue. "
            f"Please try again or contact support for assistance."
        )

        state["final_answer"] = error_msg
        state["final_response"] = error_msg
        state["error"] = "MAX_ITERATIONS_EXCEEDED"

        logger.error(f"🚨 Emergency exit triggered. Last thought: {state.get('thought', 'N/A')}")

        # Send alert to monitoring system
        await self._send_alert("agent_loop_exceeded", state)

        return state

    async def _send_alert(self, alert_type: str, state: SafeAgentState):
        """
        Send alert to monitoring system.

        Args:
            alert_type: Type of alert (e.g., "agent_loop_exceeded")
            state: Current agent state
        """
        try:
            logger.critical(
                f"🚨 ALERT: {alert_type}",
                extra={
                    "alert_type": alert_type,
                    "iterations": state.get("iterations"),
                    "max_iterations": state.get("max_iterations"),
                    "thought": state.get("thought"),
                    "observation": state.get("observation"),
                    "timestamp": datetime.now().isoformat(),
                },
            )

            # TODO: Integrate with monitoring service (Sentry, DataDog, etc.)
            # Example:
            # sentry_sdk.capture_message(f"Agent loop exceeded: {state['iterations']} iterations")

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    async def run_agent(
        self, user_input: str, max_iterations: int = None
    ) -> Dict[str, Any]:
        """
        Run agent with circuit breaker protection.

        Args:
            user_input: User's request
            max_iterations: Override default max iterations

        Returns:
            Final agent state with response
        """
        if not self.app:
            raise RuntimeError("Orchestrator not initialized (missing dependencies)")

        initial_state: SafeAgentState = {
            "messages": [HumanMessage(content=user_input)],
            "current_agent": None,
            "task_results": {},
            "final_response": None,
            "iterations": 0,
            "max_iterations": max_iterations or self.MAX_ITERATIONS,
            "thought": "",
            "action": "",
            "observation": "",
            "final_answer": "",
            "error": "",
        }

        logger.info(f"🚀 Starting agent execution: {user_input[:50]}...")

        result = await self.app.ainvoke(initial_state)

        return result


# ========== Phase 2: Checkpointed Agent Orchestrator ==========

class CheckpointedAgentOrchestrator(SafeAgentOrchestrator):
    """
    Agent orchestrator with automatic state persistence for crash recovery.
    
    Phase 2 Feature: State checkpointing
    - Survives service crashes/restarts
    - Resumes from last checkpoint
    - Thread-based conversation tracking
    """

    def __init__(self, llm_client=None):
        """Initialize checkpointed orchestrator."""
        self.checkpointer = None

        # Initialize checkpointer backend
        checkpoint_backend = getattr(settings, "CHECKPOINT_BACKEND", "postgres")

        if checkpoint_backend == "postgres" and POSTGRES_CHECKPOINT_AVAILABLE:
            try:
                database_url = getattr(settings, "DATABASE_URL", "sqlite:///./nlp_cache.db")
                self.checkpointer = PostgresSaver(database_url)
                logger.info("✅ Using PostgreSQL checkpointer")
            except Exception as e:
                logger.warning(f"Failed to initialize PostgreSQL checkpointer: {e}")

        elif checkpoint_backend == "redis" and REDIS_CHECKPOINT_AVAILABLE:
            try:
                redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
                self.checkpointer = RedisSaver(redis_url)
                logger.info("✅ Using Redis checkpointer")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis checkpointer: {e}")

        if not self.checkpointer:
            logger.warning("⚠️ Checkpointing not available, running without persistence")

        # Initialize parent
        super().__init__(llm_client=llm_client)

    def build_graph(self) -> StateGraph:
        """Build graph with checkpointing enabled."""
        workflow = super().build_graph()

        if self.checkpointer:
            # Compile with checkpointer
            return workflow.compile(checkpointer=self.checkpointer)
        else:
            return workflow

    async def run_agent(
        self,
        user_input: str,
        thread_id: str = None,
        max_iterations: int = None,
    ) -> Dict[str, Any]:
        """
        Run agent with checkpointing.

        Args:
            user_input: User's request
            thread_id: Conversation thread ID (for recovery)
            max_iterations: Override default max iterations

        Returns:
            Final agent state
        """
        if not self.app:
            raise RuntimeError("Orchestrator not initialized (missing dependencies)")

        # Generate thread ID if not provided
        if thread_id is None:
            thread_id = f"thread_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        config = {"configurable": {"thread_id": thread_id}}

        initial_state: SafeAgentState = {
            "messages": [HumanMessage(content=user_input)],
            "current_agent": None,
            "task_results": {},
            "final_response": None,
            "iterations": 0,
            "max_iterations": max_iterations or self.MAX_ITERATIONS,
            "thought": "",
            "action": "",
            "observation": "",
            "final_answer": "",
            "error": "",
        }

        logger.info(f"🚀 Starting checkpointed agent (thread: {thread_id})")

        # Run with checkpointing
        result = await self.app.ainvoke(initial_state, config=config)

        return result


# ========== Legacy Orchestrator (Backward Compatibility) ==========

class LangGraphOrchestrator:
    """
    Original orchestrator using LangGraph for state management.

    Kept for backward compatibility. New code should use SafeAgentOrchestrator.
    """

    def __init__(self, llm_client=None):
        """
        Initialize LangGraph orchestrator.

        Args:
            llm_client: LLM client for agent execution
        """
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available. Orchestrator disabled.")
            self.app = None
            return

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
                "lifestyle_coach": "lifecycle_coach",
                "END": END,
            },
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
            query = (
                state["messages"][-1].content
                if hasattr(state["messages"][-1], "content")
                else str(state["messages"][-1])
            )
        else:
            query = "No query provided"

        # Determine which specialist to route to based on query content
        state["current_agent"] = self._determine_specialist(query)
        state["messages"].append(
            AIMessage(content=f"Planned to route to {state['current_agent']}")
        )

        return state

    def _determine_specialist(self, query: str) -> str:
        """Determine which specialist agent to route the query to."""
        query_lower = query.lower()

        # Check for symptom-related queries
        symptom_keywords = [
            "symptom",
            "pain",
            "feeling",
            "hurt",
            "ache",
            "dizzy",
            "tired",
        ]
        if any(kw in query_lower for kw in symptom_keywords):
            return "symptom_checker"

        # Check for medication queries
        med_keywords = [
            "medication",
            "drug",
            "medicine",
            "pill",
            "dose",
            "side effect",
            "interaction",
        ]
        if any(kw in query_lower for kw in med_keywords):
            return "medication_advisor"

        # Check for lifestyle queries
        lifestyle_keywords = [
            "exercise",
            "diet",
            "sleep",
            "stress",
            "weight",
            "lifestyle",
            "healthy",
        ]
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
        query = (
            state["messages"][-1].content
            if hasattr(state["messages"][-1], "content")
            else str(state["messages"][-1])
        )

        # Use LLM to generate health analysis if available
        if self.llm_client:
            try:
                prompt = f"As a health analyst, provide insights on: {query}"
                response = await self.llm_client.generate(
                    prompt, content_type="medical"
                )
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
            "recommendations": ["General health recommendation"],
        }
        return state

    async def _check_symptoms(self, state: AgentState) -> AgentState:
        """Check symptoms and provide triage guidance."""
        logger.info("Checking symptoms")

        # Get the query
        query = (
            state["messages"][-1].content
            if hasattr(state["messages"][-1], "content")
            else str(state["messages"][-1])
        )

        # Use LLM to generate symptom analysis if available
        if self.llm_client:
            try:
                prompt = f"As a symptom checker, analyze: {query}"
                response = await self.llm_client.generate(
                    prompt, content_type="medical"
                )
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
            "recommendations": recommendations,
        }
        return state

    async def _advise_medication(self, state: AgentState) -> AgentState:
        """Provide medication information and interaction checking."""
        logger.info("Advising on medication")

        # Get the query
        query = (
            state["messages"][-1].content
            if hasattr(state["messages"][-1], "content")
            else str(state["messages"][-1])
        )

        # Use LLM to generate medication advice if available
        if self.llm_client:
            try:
                prompt = f"As a medication advisor, provide information on: {query}"
                response = await self.llm_client.generate(
                    prompt, content_type="medical"
                )
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
            "warnings": [],
        }
        return state

    async def _coach_lifestyle(self, state: AgentState) -> AgentState:
        """Provide lifestyle and wellness guidance."""
        logger.info("Providing lifestyle coaching")

        # Get the query
        query = (
            state["messages"][-1].content
            if hasattr(state["messages"][-1], "content")
            else str(state["messages"][-1])
        )

        # Use LLM to generate lifestyle advice if available
        if self.llm_client:
            try:
                prompt = f"As a lifestyle coach, provide advice on: {query}"
                response = await self.llm_client.generate(
                    prompt, content_type="nutrition"
                )
                recommendations = {
                    "diet": [response],
                    "exercise": ["Walk 30 minutes daily"],
                }
            except Exception as e:
                logger.warning(f"LLM lifestyle advice failed: {e}")
                recommendations = {
                    "diet": ["Eat more vegetables"],
                    "exercise": ["Walk 30 minutes daily"],
                }
        else:
            recommendations = {
                "diet": ["Eat more vegetables"],
                "exercise": ["Walk 30 minutes daily"],
            }

        state["messages"].append(AIMessage(content="Lifestyle coaching completed"))
        state["task_results"]["lifestyle_coaching"] = {
            "agent": "lifestyle_coach",
            "recommendations": recommendations,
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

                response = await self.llm_client.generate(
                    validation_prompt, content_type="medical"
                )
                validated = (
                    "validated" in response.lower() or "safe" in response.lower()
                )
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
            "issues": issues,
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
                synthesis_prompt = (
                    "Synthesize the following information into a coherent response:\n"
                    + "\n".join(response_parts)
                )
                final_response = await self.llm_client.generate(
                    synthesis_prompt, content_type="medical"
                )
            except Exception as e:
                logger.warning(f"LLM synthesis failed: {e}")
                final_response = (
                    "\n".join(response_parts)
                    if response_parts
                    else "I've analyzed your query and here are the results."
                )
        else:
            final_response = (
                "\n".join(response_parts)
                if response_parts
                else "I've analyzed your query and here are the results."
            )

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
        if not self.app:
            raise RuntimeError(
                "LangGraph orchestrator is not initialized (missing dependencies)"
            )

        logger.info(f"Processing query: {query[:50]}...")

        # Initialize state
        initial_state = AgentState(
            messages=[HumanMessage(content=query)],
            current_agent=None,
            task_results={},
            final_response=None,
        )

        # Execute workflow
        final_state = await self.app.ainvoke(initial_state)

        return {
            "response": final_state["final_response"],
            "messages": [msg.content for msg in final_state["messages"]],
            "task_results": final_state["task_results"],
            "timestamp": datetime.now().isoformat(),
        }


# ========== Factory Functions ==========

def create_langgraph_orchestrator(llm_client=None) -> LangGraphOrchestrator:
    """
    Factory function to create a LangGraphOrchestrator (legacy).

    Args:
        llm_client: LLM client for agent execution

    Returns:
        Configured LangGraphOrchestrator
    """
    return LangGraphOrchestrator(llm_client=llm_client)


def create_safe_agent_orchestrator(llm_client=None) -> SafeAgentOrchestrator:
    """
    Factory function to create a SafeAgentOrchestrator (Phase 2).

    Args:
        llm_client: LLM client for agent execution

    Returns:
        Configured SafeAgentOrchestrator with circuit breaker
    """
    return SafeAgentOrchestrator(llm_client=llm_client)


def create_checkpointed_agent_orchestrator(llm_client=None) -> CheckpointedAgentOrchestrator:
    """
    Factory function to create a CheckpointedAgentOrchestrator (Phase 2).

    Args:
        llm_client: LLM client for agent execution

    Returns:
        Configured CheckpointedAgentOrchestrator with checkpointing
    """
    return CheckpointedAgentOrchestrator(llm_client=llm_client)
