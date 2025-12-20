"""
Enhanced Planner Agent with LLM-powered query decomposition.

Uses Gemini to intelligently break down complex healthcare queries
into subtasks for specialist agents.

Features:
- Emergency detection (fast-path)
- Query complexity analysis
- Task dependency management
- Parallel execution planning
"""

import asyncio
import logging
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

# Optional imports
try:
    import google.generativeai as genai

    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False
    logger.warning("google-generativeai not installed")


class QueryComplexity(Enum):
    """Query complexity levels."""

    SIMPLE = "simple"  # Single agent, direct answer
    MODERATE = "moderate"  # 2-3 agents, some coordination
    COMPLEX = "complex"  # 4+ agents, dependencies
    EMERGENCY = "emergency"  # Urgent, immediate response needed


class AgentType(Enum):
    """Available specialist agents."""

    HEALTH_ANALYST = "health_analyst"
    MEDICAL_RESEARCH = "medical_research"
    MEDICATION_ADVISOR = "medication_advisor"
    SYMPTOM_CHECKER = "symptom_checker"
    LIFESTYLE_COACH = "lifestyle_coach"
    NUTRITION_EXPERT = "nutrition_expert"
    CARDIO_SPECIALIST = "cardio_specialist"
    EMERGENCY_DETECTOR = "emergency_detector"
    VALIDATOR = "validator"
    SYNTHESIZER = "synthesizer"


@dataclass
class AgentTask:
    """A task to be executed by an agent."""

    task_id: str
    agent_type: AgentType
    description: str
    priority: int = 1  # 1 = highest
    dependencies: List[str] = field(default_factory=list)
    timeout_ms: int = 5000
    required: bool = True

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type.value,
            "description": self.description,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "timeout_ms": self.timeout_ms,
            "required": self.required,
        }


@dataclass
class ExecutionPlan:
    """Execution plan for multi-agent query processing."""

    query: str
    complexity: QueryComplexity
    tasks: List[AgentTask]
    estimated_time_ms: int
    requires_validation: bool = True
    emergency_detected: bool = False
    emergency_reason: Optional[str] = None
    reasoning: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "complexity": self.complexity.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "estimated_time_ms": self.estimated_time_ms,
            "requires_validation": self.requires_validation,
            "emergency_detected": self.emergency_detected,
            "emergency_reason": self.emergency_reason,
            "reasoning": self.reasoning,
            "created_at": self.created_at,
        }

    def get_parallel_groups(self) -> List[List[AgentTask]]:
        """
        Group tasks by dependency level for parallel execution.

        Returns:
            List of task groups that can run in parallel
        """
        executed: set = set()
        groups: List[List[AgentTask]] = []
        remaining = list(self.tasks)

        while remaining:
            # Find tasks with all dependencies met
            ready = [t for t in remaining if all(d in executed for d in t.dependencies)]

            if not ready:
                # Circular dependency or missing dependency
                logger.warning("Could not resolve all dependencies")
                groups.append(remaining)
                break

            # Sort by priority
            ready.sort(key=lambda t: t.priority)
            groups.append(ready)

            # Mark as executed
            for t in ready:
                executed.add(t.task_id)
                remaining.remove(t)

        return groups


class EnhancedPlannerAgent:
    """
    LLM-powered query planner for multi-agent orchestration.

    Responsibilities:
    1. Analyze query complexity and intent
    2. Detect emergency situations
    3. Decompose into subtasks
    4. Assign agents with dependencies
    5. Estimate execution time

    Example:
        planner = EnhancedPlannerAgent()
        plan = await planner.create_plan(
            "I have chest pain and took aspirin, is that okay?"
        )
        # Returns plan with SymptomChecker -> MedicationAdvisor -> Validator
    """

    PLANNING_PROMPT = """You are a healthcare query planner. Analyze the user query and create an execution plan.

Query: {query}
User Context: {context}

Determine:
1. Query complexity (simple/moderate/complex/emergency)
2. Required specialist agents
3. Task dependencies
4. Priority level

Available agents:
- health_analyst: Interprets vitals, identifies trends, analyzes health metrics
- medical_research: Explains conditions, treatments, medical information
- medication_advisor: Drug info, interactions, dosages, side effects
- symptom_checker: Symptom analysis, urgency assessment
- lifestyle_coach: Diet, exercise, wellness advice, habit changes
- nutrition_expert: Meal planning, dietary restrictions, nutritional analysis
- cardio_specialist: Heart-specific conditions, cardiac medications, ECG interpretation
- emergency_detector: Urgent situation identification (always include for health queries)

Respond in JSON format:
{{
    "complexity": "simple|moderate|complex|emergency",
    "is_emergency": boolean,
    "emergency_reason": "string if emergency, null otherwise",
    "tasks": [
        {{
            "task_id": "unique_id",
            "agent_type": "agent_name",
            "description": "what this agent should do",
            "priority": 1-5 (1 highest),
            "dependencies": ["task_ids this depends on"],
            "required": true/false
        }}
    ],
    "reasoning": "brief explanation of the plan"
}}

IMPORTANT:
- For any symptom-related query, include emergency_detector first
- For medication questions, always include medication_advisor
- For heart/cardio topics, include cardio_specialist
- Always end with validator for medical accuracy"""

    # Emergency keywords for fast-path detection
    EMERGENCY_KEYWORDS = [
        "can't breathe",
        "cannot breathe",
        "difficulty breathing",
        "chest pain severe",
        "crushing chest pain",
        "chest tightness",
        "passing out",
        "fainting",
        "unconscious",
        "heart attack",
        "stroke",
        "cardiac arrest",
        "severe bleeding",
        "heavy bleeding",
        "anaphylaxis",
        "allergic reaction severe",
        "seizure",
        "convulsion",
        "suicidal",
        "suicide",
        "self harm",
        "overdose",
        "poisoning",
        "choking",
        "can't swallow",
    ]

    # Simple query patterns (single agent)
    SIMPLE_PATTERNS = [
        (r"what is (?:a |an )?(\w+)", AgentType.MEDICAL_RESEARCH),
        (r"explain (\w+)", AgentType.MEDICAL_RESEARCH),
        (r"side effects of (\w+)", AgentType.MEDICATION_ADVISOR),
        (r"how many calories", AgentType.NUTRITION_EXPERT),
        (r"exercise for", AgentType.LIFESTYLE_COACH),
    ]

    def __init__(
        self,
        model_name: str = "gemini-2.0-flash",
        use_llm: bool = True,
    ):
        """
        Initialize planner.

        Args:
            model_name: Gemini model to use
            use_llm: Use LLM for planning (vs rule-based fallback)
        """
        self.use_llm = use_llm and GENAI_AVAILABLE

        if self.use_llm:
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Planner initialized with LLM: {model_name}")
        else:
            self.model = None
            logger.info("Planner initialized in rule-based mode")

    async def create_plan(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """
        Create execution plan for a query.

        Args:
            query: User's healthcare query
            context: Optional context (user profile, history, etc.)

        Returns:
            ExecutionPlan with tasks and dependencies
        """
        query = query.strip()
        context = context or {}

        # Fast-path: Check for emergency
        if self._is_emergency(query):
            return self._create_emergency_plan(query)

        # Try LLM planning
        if self.use_llm:
            try:
                return await self._create_llm_plan(query, context)
            except Exception as e:
                logger.warning(f"LLM planning failed, using fallback: {e}")

        # Fallback: Rule-based planning
        return self._create_rule_based_plan(query, context)

    def _is_emergency(self, query: str) -> bool:
        """Fast emergency detection using keywords."""
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.EMERGENCY_KEYWORDS)

    def _create_emergency_plan(self, query: str) -> ExecutionPlan:
        """Create immediate emergency response plan."""
        return ExecutionPlan(
            query=query,
            complexity=QueryComplexity.EMERGENCY,
            emergency_detected=True,
            emergency_reason="Emergency keywords detected",
            requires_validation=False,  # Don't delay emergency response
            estimated_time_ms=500,
            tasks=[
                AgentTask(
                    task_id="emergency_1",
                    agent_type=AgentType.EMERGENCY_DETECTOR,
                    description="Assess emergency severity and provide immediate guidance",
                    priority=1,
                    timeout_ms=2000,
                ),
                AgentTask(
                    task_id="symptom_1",
                    agent_type=AgentType.SYMPTOM_CHECKER,
                    description="Quick symptom assessment",
                    priority=1,
                    dependencies=["emergency_1"],
                    timeout_ms=2000,
                ),
            ],
            reasoning="Emergency detected - fast-path response",
        )

    async def _create_llm_plan(
        self,
        query: str,
        context: Dict[str, Any],
    ) -> ExecutionPlan:
        """Create plan using LLM."""
        prompt = self.PLANNING_PROMPT.format(
            query=query,
            context=json.dumps(context) if context else "None provided",
        )

        response = await asyncio.to_thread(lambda: self.model.generate_content(prompt))

        # Parse JSON response
        plan_data = self._parse_plan_response(response.text)

        # Build ExecutionPlan
        complexity = QueryComplexity(plan_data.get("complexity", "moderate"))

        tasks = []
        for task_data in plan_data.get("tasks", []):
            try:
                agent_type = AgentType(task_data["agent_type"])
                tasks.append(
                    AgentTask(
                        task_id=task_data["task_id"],
                        agent_type=agent_type,
                        description=task_data.get("description", ""),
                        priority=task_data.get("priority", 3),
                        dependencies=task_data.get("dependencies", []),
                        required=task_data.get("required", True),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping invalid task: {e}")

        # Estimate time based on task count
        estimated_time = sum(t.timeout_ms for t in tasks)

        return ExecutionPlan(
            query=query,
            complexity=complexity,
            tasks=tasks,
            estimated_time_ms=estimated_time,
            emergency_detected=plan_data.get("is_emergency", False),
            emergency_reason=plan_data.get("emergency_reason"),
            reasoning=plan_data.get("reasoning"),
            requires_validation=complexity != QueryComplexity.SIMPLE,
        )

    def _parse_plan_response(self, response: str) -> Dict:
        """Parse LLM JSON response."""
        # Extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse LLM response as JSON")
        return {}

    def _create_rule_based_plan(
        self,
        query: str,
        context: Dict[str, Any],
    ) -> ExecutionPlan:
        """Create plan using rule-based logic."""
        query_lower = query.lower()
        tasks = []
        task_id = 0

        def add_task(
            agent: AgentType, desc: str, deps: List[str] = None, priority: int = 3
        ):
            nonlocal task_id
            task_id += 1
            tasks.append(
                AgentTask(
                    task_id=f"task_{task_id}",
                    agent_type=agent,
                    description=desc,
                    priority=priority,
                    dependencies=deps or [],
                )
            )
            return f"task_{task_id}"

        # Check for simple patterns first
        for pattern, agent in self.SIMPLE_PATTERNS:
            if re.search(pattern, query_lower):
                add_task(agent, f"Answer: {query}", priority=1)
                return ExecutionPlan(
                    query=query,
                    complexity=QueryComplexity.SIMPLE,
                    tasks=tasks,
                    estimated_time_ms=3000,
                    requires_validation=False,
                    reasoning="Simple pattern match",
                )

        # Symptom-related queries
        symptom_keywords = [
            "pain",
            "ache",
            "hurt",
            "symptom",
            "feeling",
            "dizzy",
            "nausea",
        ]
        if any(kw in query_lower for kw in symptom_keywords):
            t1 = add_task(
                AgentType.EMERGENCY_DETECTOR,
                "Check for emergency indicators",
                priority=1,
            )
            t2 = add_task(
                AgentType.SYMPTOM_CHECKER,
                "Analyze reported symptoms",
                deps=[t1],
                priority=2,
            )

        # Medication queries
        med_keywords = [
            "medication",
            "medicine",
            "drug",
            "pill",
            "dose",
            "taking",
            "prescription",
        ]
        if any(kw in query_lower for kw in med_keywords):
            deps = [tasks[-1].task_id] if tasks else []
            add_task(
                AgentType.MEDICATION_ADVISOR,
                "Provide medication information",
                deps=deps,
                priority=2,
            )

        # Heart/cardio queries
        cardio_keywords = [
            "heart",
            "cardio",
            "blood pressure",
            "bp",
            "pulse",
            "ecg",
            "cholesterol",
        ]
        if any(kw in query_lower for kw in cardio_keywords):
            deps = [tasks[-1].task_id] if tasks else []
            add_task(
                AgentType.CARDIO_SPECIALIST,
                "Provide cardiology expertise",
                deps=deps,
                priority=2,
            )

        # Lifestyle/diet queries
        lifestyle_keywords = [
            "diet",
            "exercise",
            "sleep",
            "stress",
            "weight",
            "lifestyle",
        ]
        if any(kw in query_lower for kw in lifestyle_keywords):
            deps = [tasks[-1].task_id] if tasks else []
            add_task(
                AgentType.LIFESTYLE_COACH,
                "Provide lifestyle recommendations",
                deps=deps,
                priority=3,
            )

        # Nutrition queries
        nutrition_keywords = ["food", "eat", "calorie", "nutrition", "meal", "vitamin"]
        if any(kw in query_lower for kw in nutrition_keywords):
            deps = [tasks[-1].task_id] if tasks else []
            add_task(
                AgentType.NUTRITION_EXPERT,
                "Provide nutritional guidance",
                deps=deps,
                priority=3,
            )

        # Default: medical research if no specific match
        if not tasks:
            add_task(
                AgentType.MEDICAL_RESEARCH,
                f"Research and explain: {query}",
                priority=2,
            )

        # Always add validator for non-simple queries
        if len(tasks) > 1:
            add_task(
                AgentType.VALIDATOR,
                "Validate medical accuracy of response",
                deps=[tasks[-1].task_id],
                priority=5,
            )

        # Determine complexity
        if len(tasks) <= 1:
            complexity = QueryComplexity.SIMPLE
        elif len(tasks) <= 3:
            complexity = QueryComplexity.MODERATE
        else:
            complexity = QueryComplexity.COMPLEX

        return ExecutionPlan(
            query=query,
            complexity=complexity,
            tasks=tasks,
            estimated_time_ms=sum(t.timeout_ms for t in tasks),
            requires_validation=len(tasks) > 1,
            reasoning="Rule-based planning",
        )


# Convenience function
async def create_execution_plan(
    query: str,
    context: Optional[Dict[str, Any]] = None,
) -> ExecutionPlan:
    """
    Create execution plan for a healthcare query.

    Args:
        query: User's query
        context: Optional context

    Returns:
        ExecutionPlan
    """
    planner = EnhancedPlannerAgent()
    return await planner.create_plan(query, context)
