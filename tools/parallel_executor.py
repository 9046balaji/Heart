"""
Parallel Tool Executor - Execute multiple tools concurrently.

Provides:
- ParallelToolExecutor: Execute tools in parallel when safe
- ToolCall: Request for tool execution
- Dependency tracking for ordered execution

Enables safe parallel execution for independent tools
while maintaining sequential order for state-modifying tools.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """
    Represents a tool call request.
    
    Attributes:
        tool_name: Name of the tool to call
        arguments: Arguments for the tool
        call_id: Unique identifier for this call (auto-generated if not provided)
    """
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    def __hash__(self):
        return hash(self.call_id)


@dataclass
class ExecutionResult:
    """
    Result of parallel tool execution.
    
    Attributes:
        results: Dict mapping call_id to ToolResult
        execution_time_ms: Total execution time
        parallel_count: How many tools ran in parallel
        sequential_count: How many tools ran sequentially
    """
    results: Dict[str, Any]
    execution_time_ms: float
    parallel_count: int
    sequential_count: int
    
    def get_result(self, call_id: str) -> Optional[Any]:
        """Get result for a specific call."""
        return self.results.get(call_id)
    
    def all_successful(self) -> bool:
        """Check if all calls succeeded."""
        return all(
            getattr(r, 'success', True)
            for r in self.results.values()
        )


class ParallelToolExecutor:
    """
    Execute multiple tools in parallel when safe.
    
    Features:
    - Automatic detection of parallelizable vs sequential tools
    - Timeout protection per tool
    - Failure isolation (one failure doesn't stop others)
    - Metrics tracking
    
    Example:
        ```python
        executor = ParallelToolExecutor(registry)
        
        calls = [
            ToolCall("calculator", {"expression": "2+2"}),
            ToolCall("calculator", {"expression": "3*3"}),
            ToolCall("web_search", {"query": "aspirin side effects"})
        ]
        
        results = await executor.execute_calls(calls, parallel=True)
        # Returns results for all three, with calculator calls run in parallel
        ```
    """
    
    # Tools that can safely run in parallel (read-only, no side effects)
    # NOTE: LangGraph natively handles parallel execution. Use this class only
    # when running tools outside of the LangGraph orchestrator.
    PARALLELIZABLE: Set[str] = {
        "calculator",
        "search_vector_store",
        "search_medical_knowledge",
        "web_search",
        "fetch_user_profile",
        "get_drug_interactions",
        "check_drug_interactions",
        "analyze_medical_image",
        "analyze_image",
    }
    
    # Tools that must run sequentially (may have side effects)
    SEQUENTIAL: Set[str] = {
        "query_sql_db",         # May have transactions
        "query_database",
        "update_user_profile",
        "save_memory",
        "store_conversation",
    }
    
    # Default timeout per tool (seconds)
    DEFAULT_TIMEOUT = 30.0
    
    def __init__(
        self,
        tool_registry=None,
        default_timeout: float = 30.0,
        max_parallel: int = 10
    ):
        """
        Initialize the executor.
        
        Args:
            tool_registry: ToolRegistry instance for looking up tools
            default_timeout: Default timeout per tool in seconds
            max_parallel: Maximum concurrent tool executions
        """
        self.registry = tool_registry
        self.default_timeout = default_timeout
        self.max_parallel = max_parallel
        self._semaphore = asyncio.Semaphore(max_parallel)
        
        # Metrics
        self.total_executions = 0
        self.parallel_executions = 0
        self.sequential_executions = 0
        self.failures = 0
        self.timeouts = 0
    
    async def execute_calls(
        self,
        calls: List[ToolCall],
        parallel: bool = True,
        timeout: Optional[float] = None
    ) -> ExecutionResult:
        """
        Execute tool calls, optionally in parallel.
        
        Args:
            calls: List of ToolCall requests
            parallel: Whether to allow parallel execution
            timeout: Timeout per call (uses default if None)
            
        Returns:
            ExecutionResult with all results
        """
        start_time = datetime.utcnow()
        timeout = timeout or self.default_timeout
        
        if not parallel:
            results = await self._execute_sequential(calls, timeout)
            parallel_count = 0
            sequential_count = len(calls)
        else:
            # Separate parallelizable and sequential calls
            parallel_calls = []
            sequential_calls = []
            
            for call in calls:
                if self._is_parallelizable(call.tool_name):
                    parallel_calls.append(call)
                else:
                    sequential_calls.append(call)
            
            results = {}
            
            # Execute parallel calls concurrently
            if parallel_calls:
                parallel_results = await self._execute_parallel(parallel_calls, timeout)
                results.update(parallel_results)
            
            # Execute sequential calls in order
            if sequential_calls:
                sequential_results = await self._execute_sequential(sequential_calls, timeout)
                results.update(sequential_results)
            
            parallel_count = len(parallel_calls)
            sequential_count = len(sequential_calls)
        
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds() * 1000
        
        self.total_executions += len(calls)
        self.parallel_executions += parallel_count
        self.sequential_executions += sequential_count
        
        return ExecutionResult(
            results=results,
            execution_time_ms=execution_time,
            parallel_count=parallel_count,
            sequential_count=sequential_count
        )
    
    def _is_parallelizable(self, tool_name: str) -> bool:
        """Check if a tool can be parallelized."""
        if tool_name in self.SEQUENTIAL:
            return False
        if tool_name in self.PARALLELIZABLE:
            return True
        # Default to sequential for unknown tools
        return False
    
    async def _execute_parallel(
        self,
        calls: List[ToolCall],
        timeout: float
    ) -> Dict[str, Any]:
        """Execute calls in parallel with semaphore limiting."""
        
        async def execute_with_semaphore(call: ToolCall) -> tuple:
            async with self._semaphore:
                return call.call_id, await self._execute_single(call, timeout)
        
        # Run all in parallel
        tasks = [execute_with_semaphore(call) for call in calls]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert to dict
        results = {}
        for item in results_list:
            if isinstance(item, Exception):
                logger.error(f"Parallel execution error: {item}")
                self.failures += 1
            else:
                call_id, result = item
                results[call_id] = result
        
        return results
    
    async def _execute_sequential(
        self,
        calls: List[ToolCall],
        timeout: float
    ) -> Dict[str, Any]:
        """Execute calls sequentially."""
        results = {}
        for call in calls:
            results[call.call_id] = await self._execute_single(call, timeout)
        return results
    
    async def _execute_single(
        self,
        call: ToolCall,
        timeout: float
    ) -> Any:
        """Execute a single tool call with timeout."""
        from tools.tool_registry import ToolResult
        
        try:
            # Get tool from registry
            if self.registry:
                tool = self.registry.get(call.tool_name)
            else:
                tool = None
            
            if tool is None:
                return ToolResult(
                    success=False,
                    error=f"Unknown tool: {call.tool_name}",
                    tool_name=call.tool_name
                )
            
            # Execute with timeout
            try:
                result = await asyncio.wait_for(
                    tool.execute(call.arguments),
                    timeout=timeout
                )
                return result
            except asyncio.TimeoutError:
                self.timeouts += 1
                return ToolResult(
                    success=False,
                    error=f"Tool execution timed out after {timeout}s",
                    tool_name=call.tool_name
                )
        
        except Exception as e:
            self.failures += 1
            logger.error(f"Tool {call.tool_name} failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name=call.tool_name
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        total = self.total_executions or 1
        return {
            "total_executions": self.total_executions,
            "parallel_executions": self.parallel_executions,
            "sequential_executions": self.sequential_executions,
            "parallelization_rate": round(self.parallel_executions / total * 100, 2),
            "failures": self.failures,
            "timeouts": self.timeouts,
            "failure_rate": round(self.failures / total * 100, 2)
        }
    
    def add_parallelizable(self, tool_name: str):
        """Mark a tool as safe for parallel execution."""
        self.PARALLELIZABLE.add(tool_name)
        if tool_name in self.SEQUENTIAL:
            self.SEQUENTIAL.remove(tool_name)
    
    def add_sequential(self, tool_name: str):
        """Mark a tool as requiring sequential execution."""
        self.SEQUENTIAL.add(tool_name)
        if tool_name in self.PARALLELIZABLE:
            self.PARALLELIZABLE.remove(tool_name)


# Convenience function for simple parallel execution
async def execute_tools_parallel(
    calls: List[ToolCall],
    registry=None,
    timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Simple function to execute tools in parallel.
    
    Args:
        calls: List of ToolCall requests
        registry: Optional ToolRegistry
        timeout: Timeout per tool
        
    Returns:
        Dict mapping call_id to result
    """
    executor = ParallelToolExecutor(registry, timeout)
    result = await executor.execute_calls(calls)
    return result.results
