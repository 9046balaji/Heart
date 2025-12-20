"""
Concurrent Task Executor for Multi-Agent System.

Executes agent tasks with proper dependency management,
concurrency control, and timeout handling.

Features:
- Parallel execution of independent tasks
- Dependency resolution
- Timeout handling per task
- Error recovery and partial results
- Execution metrics
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .planner import AgentTask, ExecutionPlan, AgentType

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class TaskResult:
    """Result from task execution."""

    task_id: str
    agent_type: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class ExecutionResult:
    """Result from plan execution."""

    plan_id: str
    status: str  # "success", "partial", "failed"
    task_results: List[TaskResult]
    total_time_ms: float
    completed_count: int
    failed_count: int
    final_response: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "status": self.status,
            "task_results": [r.to_dict() for r in self.task_results],
            "total_time_ms": self.total_time_ms,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "final_response": self.final_response,
        }


# Type alias for agent executor functions
AgentExecutor = Callable[[AgentTask, Dict[str, TaskResult]], Awaitable[Any]]


class TaskExecutor:
    """
    Executes agent tasks with dependency management.

    Features:
    - Parallel execution of independent tasks
    - Dependency resolution
    - Timeout handling
    - Error recovery

    Example:
        executor = TaskExecutor()
        executor.register_agent(AgentType.SYMPTOM_CHECKER, symptom_agent.execute)

        result = await executor.execute_plan(plan)
    """

    def __init__(
        self,
        max_concurrency: int = 5,
        default_timeout_ms: int = 10000,
    ):
        """
        Initialize executor.

        Args:
            max_concurrency: Maximum concurrent tasks
            default_timeout_ms: Default timeout per task
        """
        self.max_concurrency = max_concurrency
        self.default_timeout_ms = default_timeout_ms
        self._agents: Dict[AgentType, AgentExecutor] = {}
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def register_agent(
        self,
        agent_type: AgentType,
        executor: AgentExecutor,
    ):
        """
        Register an agent executor.

        Args:
            agent_type: Type of agent
            executor: Async function to execute tasks
        """
        self._agents[agent_type] = executor
        logger.info(f"Registered agent: {agent_type.value}")

    def register_agents(self, agents: Dict[AgentType, AgentExecutor]):
        """Register multiple agents at once."""
        for agent_type, executor in agents.items():
            self.register_agent(agent_type, executor)

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute a complete plan.

        Args:
            plan: ExecutionPlan to execute
            context: Additional context for agents

        Returns:
            ExecutionResult with all task results
        """
        start_time = time.perf_counter()
        plan_id = f"plan_{int(time.time() * 1000)}"

        logger.info(
            f"Executing plan {plan_id}: {len(plan.tasks)} tasks, "
            f"complexity={plan.complexity.value}"
        )

        # Get parallel execution groups
        groups = plan.get_parallel_groups()

        # Track results
        results: Dict[str, TaskResult] = {}

        # Execute each group
        for group_idx, group in enumerate(groups):
            logger.debug(
                f"Executing group {group_idx + 1}/{len(groups)}: {len(group)} tasks"
            )

            # Execute tasks in parallel within group
            group_results = await asyncio.gather(
                *[self._execute_task(task, results, context or {}) for task in group],
                return_exceptions=True,
            )

            # Process results
            for task, result in zip(group, group_results):
                if isinstance(result, Exception):
                    results[task.task_id] = TaskResult(
                        task_id=task.task_id,
                        agent_type=task.agent_type.value,
                        status=TaskStatus.FAILED,
                        error=str(result),
                    )
                else:
                    results[task.task_id] = result

        # Calculate metrics
        total_time = (time.perf_counter() - start_time) * 1000
        task_results = list(results.values())
        completed = sum(1 for r in task_results if r.status == TaskStatus.COMPLETED)
        failed = sum(
            1
            for r in task_results
            if r.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT]
        )

        # Determine overall status
        if failed == 0:
            status = "success"
        elif completed > 0:
            status = "partial"
        else:
            status = "failed"

        # Get final response from synthesizer or last task
        final_response = None
        for task_id in reversed(list(results.keys())):
            result = results[task_id]
            if result.status == TaskStatus.COMPLETED and result.result:
                final_response = result.result
                break

        logger.info(
            f"Plan {plan_id} completed: status={status}, "
            f"completed={completed}/{len(plan.tasks)}, time={total_time:.0f}ms"
        )

        return ExecutionResult(
            plan_id=plan_id,
            status=status,
            task_results=task_results,
            total_time_ms=total_time,
            completed_count=completed,
            failed_count=failed,
            final_response=final_response,
        )

    async def _execute_task(
        self,
        task: AgentTask,
        previous_results: Dict[str, TaskResult],
        context: Dict[str, Any],
    ) -> TaskResult:
        """
        Execute a single task.

        Args:
            task: Task to execute
            previous_results: Results from dependency tasks
            context: Additional context

        Returns:
            TaskResult
        """
        start_time = time.perf_counter()

        # Check if agent is registered
        if task.agent_type not in self._agents:
            logger.warning(f"No agent registered for {task.agent_type.value}")
            return TaskResult(
                task_id=task.task_id,
                agent_type=task.agent_type.value,
                status=TaskStatus.SKIPPED,
                error=f"No agent registered for {task.agent_type.value}",
            )

        # Check dependencies
        for dep_id in task.dependencies:
            if dep_id in previous_results:
                dep_result = previous_results[dep_id]
                if dep_result.status != TaskStatus.COMPLETED and task.required:
                    return TaskResult(
                        task_id=task.task_id,
                        agent_type=task.agent_type.value,
                        status=TaskStatus.SKIPPED,
                        error=f"Dependency {dep_id} not completed",
                    )

        # Execute with semaphore and timeout
        async with self._semaphore:
            try:
                timeout = task.timeout_ms / 1000  # Convert to seconds
                executor = self._agents[task.agent_type]

                result = await asyncio.wait_for(
                    executor(task, previous_results),
                    timeout=timeout,
                )

                execution_time = (time.perf_counter() - start_time) * 1000

                return TaskResult(
                    task_id=task.task_id,
                    agent_type=task.agent_type.value,
                    status=TaskStatus.COMPLETED,
                    result=result,
                    execution_time_ms=execution_time,
                )

            except asyncio.TimeoutError:
                execution_time = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"Task {task.task_id} timed out after {execution_time:.0f}ms"
                )
                return TaskResult(
                    task_id=task.task_id,
                    agent_type=task.agent_type.value,
                    status=TaskStatus.TIMEOUT,
                    error=f"Timeout after {task.timeout_ms}ms",
                    execution_time_ms=execution_time,
                )

            except Exception as e:
                execution_time = (time.perf_counter() - start_time) * 1000
                logger.error(f"Task {task.task_id} failed: {e}")
                return TaskResult(
                    task_id=task.task_id,
                    agent_type=task.agent_type.value,
                    status=TaskStatus.FAILED,
                    error=str(e),
                    execution_time_ms=execution_time,
                )

    async def execute_single_task(
        self,
        agent_type: AgentType,
        description: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_ms: int = None,
    ) -> TaskResult:
        """
        Execute a single task without a full plan.

        Args:
            agent_type: Agent to use
            description: Task description
            context: Optional context
            timeout_ms: Optional timeout

        Returns:
            TaskResult
        """
        task = AgentTask(
            task_id="single_task",
            agent_type=agent_type,
            description=description,
            timeout_ms=timeout_ms or self.default_timeout_ms,
        )

        return await self._execute_task(task, {}, context or {})


class MockAgentExecutor:
    """
    Mock agent executor for testing.

    Provides placeholder implementations for all agent types.
    """

    def __init__(self, delay_ms: int = 100):
        """
        Initialize mock executor.

        Args:
            delay_ms: Simulated processing delay
        """
        self.delay_ms = delay_ms

    async def execute(
        self,
        task: AgentTask,
        previous_results: Dict[str, TaskResult],
    ) -> str:
        """Execute mock task."""
        await asyncio.sleep(self.delay_ms / 1000)

        responses = {
            AgentType.HEALTH_ANALYST: "Health metrics analyzed. All vitals appear normal.",
            AgentType.MEDICAL_RESEARCH: "Based on medical research, here is the information...",
            AgentType.MEDICATION_ADVISOR: "Medication information: Please consult your doctor.",
            AgentType.SYMPTOM_CHECKER: "Symptoms assessed. Recommend monitoring and rest.",
            AgentType.LIFESTYLE_COACH: "Lifestyle recommendations: Exercise regularly, sleep well.",
            AgentType.NUTRITION_EXPERT: "Nutritional advice: Balanced diet with whole foods.",
            AgentType.CARDIO_SPECIALIST: "Cardiology assessment: Consider follow-up if symptoms persist.",
            AgentType.EMERGENCY_DETECTOR: "No emergency detected. Standard medical advice applies.",
            AgentType.VALIDATOR: "Response validated for medical accuracy.",
            AgentType.SYNTHESIZER: "Here is your comprehensive health response.",
        }

        return responses.get(
            task.agent_type,
            f"Response from {task.agent_type.value}: {task.description}",
        )

    def get_executors(self) -> Dict[AgentType, AgentExecutor]:
        """Get executor functions for all agent types."""
        return {agent_type: self.execute for agent_type in AgentType}


def create_executor_with_mock_agents(
    max_concurrency: int = 5,
) -> TaskExecutor:
    """
    Create TaskExecutor with mock agents for testing.

    Args:
        max_concurrency: Maximum concurrent tasks

    Returns:
        Configured TaskExecutor
    """
    executor = TaskExecutor(max_concurrency=max_concurrency)
    mock = MockAgentExecutor()
    executor.register_agents(mock.get_executors())
    return executor
