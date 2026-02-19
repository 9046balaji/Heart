"""
Thinking Agent - Agent that thinks before acting.

Provides:
- ThinkingAgent: Uses <think> blocks before tool calls
- Structured reasoning traces
- Better decision making through explicit reasoning

Based on Test-Time Compute paper and DeepSeek-R1 patterns.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
import re
import json
import logging

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Get current UTC time (replacement for deprecated datetime.utcnow())."""
    return datetime.now(timezone.utc)


class ReasoningType(Enum):
    """Types of reasoning in thinking process."""
    ANALYSIS = "analysis"        # Understanding the problem
    PLANNING = "planning"        # Deciding what to do
    EVALUATION = "evaluation"    # Assessing options
    REFLECTION = "reflection"    # Reviewing decisions
    CONCLUSION = "conclusion"    # Final decision


@dataclass
class ThinkingBlock:
    """
    A block of reasoning/thinking.
    
    Attributes:
        content: The thinking content
        reasoning_type: Type of reasoning
        key_insights: Important conclusions from this block
        timestamp: When this thinking occurred
    """
    content: str
    reasoning_type: ReasoningType = ReasoningType.ANALYSIS
    key_insights: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=_utc_now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "reasoning_type": self.reasoning_type.value,
            "insights": self.key_insights,
            "timestamp": self.timestamp.isoformat()
        }
    
    def __str__(self) -> str:
        return f"<think>\n{self.content}\n</think>"


@dataclass
class ThinkingResult:
    """
    Complete result from thinking agent.
    
    Attributes:
        answer: Final answer
        thinking_blocks: All reasoning blocks
        tool_calls: Tools that were called
        total_thinking_time_ms: Time spent thinking
    """
    answer: str
    thinking_blocks: List[ThinkingBlock]
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    total_thinking_time_ms: float = 0.0
    
    def get_reasoning_trace(self) -> str:
        """Get formatted reasoning trace."""
        lines = ["## Reasoning Trace\n"]
        for i, block in enumerate(self.thinking_blocks, 1):
            lines.append(f"### Step {i} ({block.reasoning_type.value})")
            lines.append(f"```\n{block.content}\n```")
            if block.key_insights:
                lines.append("**Key Insights:**")
                for insight in block.key_insights:
                    lines.append(f"- {insight}")
            lines.append("")
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "thinking": [b.to_dict() for b in self.thinking_blocks],
            "tool_calls": self.tool_calls,
            "thinking_time_ms": self.total_thinking_time_ms
        }


class ThinkingAgent:
    """
    Agent that thinks before acting.
    
    Uses explicit <think>...</think> blocks to:
    1. Analyze the problem
    2. Plan the approach
    3. Evaluate options
    4. Reflect on decisions
    
    This leads to more reliable and interpretable responses.
    
    Usage:
        agent = ThinkingAgent(llm=my_llm, tools=[tool1, tool2])
        result = await agent.run("What drug interactions should I watch for?")
        
        print(result.answer)
        print(result.get_reasoning_trace())
    """
    
    THINKING_PROMPT = """You are a thoughtful assistant that reasons before acting.

IMPORTANT: Before taking any action, you MUST think through the problem.
Wrap your reasoning in <think>...</think> tags.

Your thinking should cover:
1. What is the user actually asking for?
2. What information do I need to answer this?
3. Which tool(s) would help me get this information?
4. What could go wrong and how should I handle it?

Available tools:
{tool_descriptions}

After thinking, either:
- Call a tool: <tool_call>tool_name({{"param": "value"}})</tool_call>
- Provide final answer: <answer>Your complete response</answer>

User query: {query}

Previous context:
{context}

Begin with your thinking:"""

    def __init__(
        self,
        llm,
        tools: Optional[List[Any]] = None,
        max_thinking_rounds: int = 3,  # P1.2: Reduced from 5 to 3
        verbose: bool = True,
        early_exit_confidence: float = 0.85  # P1.2: Exit early if confident
    ):
        """
        Initialize the thinking agent.
        
        Args:
            llm: Language model for reasoning
            tools: List of tools available
            max_thinking_rounds: Max rounds of think-act (default: 3)
            verbose: Log thinking process
            early_exit_confidence: Exit early if confidence > this (default: 0.85)
        """
        self.llm = llm
        self.tools = {}
        for t in (tools or []):
            name = getattr(t, 'name', None) or getattr(t, '__name__', str(t))
            self.tools[name] = t
            
        self.max_thinking_rounds = max_thinking_rounds
        self.verbose = verbose
        self.early_exit_confidence = early_exit_confidence
        
        self.thinking_history: List[ThinkingBlock] = []
        self.tool_call_history: List[Dict[str, Any]] = []
    
    async def run(self, query: str, context: str = "", file_ids: Optional[List[str]] = None) -> ThinkingResult:
        """
        Run the thinking agent.
        
        Args:
            query: User query
            context: Previous context
            file_ids: Optional list of file IDs to process
            
        Returns:
            ThinkingResult with answer and reasoning
        """
        start_time = datetime.utcnow()
        self.thinking_history = []
        self.tool_call_history = []
        
        current_context = context
        
        # Add file context if files are present
        if file_ids:
            file_context = f"\n\n[ATTACHED FILES]: The user has attached {len(file_ids)} file(s) with IDs: {', '.join(file_ids)}. Use the 'analyze_medical_image' or 'analyze_dicom_image' tools to examine them if they are images."
            current_context += file_context
        
        for round_num in range(self.max_thinking_rounds):
            if self.verbose:
                logger.info(f"Thinking round {round_num + 1}/{self.max_thinking_rounds}")
            
            # Generate response
            response = await self._generate_response(query, current_context)
            
            # Parse thinking and actions
            thinking, action = self._parse_response(response)
            
            if thinking:
                block = ThinkingBlock(
                    content=thinking,
                    reasoning_type=self._classify_thinking(thinking),
                    key_insights=self._extract_insights(thinking)
                )
                self.thinking_history.append(block)
                
                if self.verbose:
                    logger.info(f"💭 Thinking: {thinking[:100]}...")
                
                # P1.2: Early exit check - if we're confident, skip remaining rounds
                confidence = self._extract_confidence(thinking)
                if confidence > self.early_exit_confidence and round_num > 0:
                    logger.info(f"P1.2: Early exit at round {round_num + 1} (confidence={confidence:.2f})")
                    # Force a final answer generation
                    return await self._generate_final_answer(query, current_context, start_time)
            
            # Check for final answer
            if action.get("type") == "answer":
                return ThinkingResult(
                    answer=action["content"],
                    thinking_blocks=self.thinking_history,
                    tool_calls=self.tool_call_history,
                    total_thinking_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                )
            
            # Execute tool call
            if action.get("type") == "tool_call":
                tool_name = action["tool_name"]
                tool_args = action["args"]
                
                if self.verbose:
                    logger.info(f"🔧 Tool call: {tool_name}")
                
                result = await self._execute_tool(tool_name, tool_args)
                
                self.tool_call_history.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })
                
                # Add result to context
                # Fix: Append what the agent just thought/said AND the result
                current_context += f"\n\nAssistant Step {round_num+1}:\n{response}\n\nTool Result:\n{result}"
        
        # Max rounds reached - generate final answer
        return await self._generate_final_answer(query, current_context, start_time)
    
    async def _generate_response(self, query: str, context: str) -> str:
        """Generate next response from LLM."""
        prompt = self.THINKING_PROMPT.format(
            tool_descriptions=self._get_tool_descriptions(),
            query=query,
            context=context or "No previous context."
        )
        
        try:
            response = await self.llm.ainvoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"<think>Error calling LLM: {e}</think><answer>I encountered an error.</answer>"
    
    def _parse_response(self, response: str) -> tuple:
        """
        Parse thinking and action from response.
        
        Returns:
            Tuple of (thinking_content, action_dict)
        """
        thinking = None
        action = {}
        
        # Extract thinking
        think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL | re.IGNORECASE)
        if think_match:
            thinking = think_match.group(1).strip()
        
        # Check for answer
        answer_match = re.search(r'<answer>(.*?)</answer>', response, re.DOTALL | re.IGNORECASE)
        if answer_match:
            action = {
                "type": "answer",
                "content": answer_match.group(1).strip()
            }
            return thinking, action
        
        # Check for tool call
        tool_match = re.search(r'<tool_call>(\w+)\((.*?)\)</tool_call>', response, re.DOTALL | re.IGNORECASE)
        if tool_match:
            tool_name = tool_match.group(1).strip()
            args_str = tool_match.group(2).strip()
            
            try:
                tool_args = json.loads(args_str)
            except json.JSONDecodeError:
                tool_args = self._parse_simple_args(args_str)
            
            action = {
                "type": "tool_call",
                "tool_name": tool_name,
                "args": tool_args
            }
        
        return thinking, action
    
    def _parse_simple_args(self, args_str: str) -> Dict[str, Any]:
        """Parse simple key=value arguments."""
        args = {}
        for match in re.finditer(r'(\w+)\s*[=:]\s*["\']?([^"\',:}]+)["\']?', args_str):
            args[match.group(1)] = match.group(2).strip()
        return args
    
    def _classify_thinking(self, thinking: str) -> ReasoningType:
        """Classify the type of thinking."""
        thinking_lower = thinking.lower()
        
        if any(word in thinking_lower for word in ["plan", "steps", "first", "then", "next"]):
            return ReasoningType.PLANNING
        elif any(word in thinking_lower for word in ["evaluate", "compare", "option", "better"]):
            return ReasoningType.EVALUATION
        elif any(word in thinking_lower for word in ["reflect", "review", "consider", "mistake"]):
            return ReasoningType.REFLECTION
        elif any(word in thinking_lower for word in ["conclude", "therefore", "answer is", "final"]):
            return ReasoningType.CONCLUSION
        else:
            return ReasoningType.ANALYSIS
    
    def _extract_insights(self, thinking: str) -> List[str]:
        """Extract key insights from thinking."""
        insights = []
        
        # Look for bullet points or numbered items
        for match in re.finditer(r'[-•*]\s+(.+?)(?:\n|$)', thinking):
            insight = match.group(1).strip()
            if len(insight) > 10:
                insights.append(insight)
        
        # Look for "I should", "I need to", "Important:" patterns
        for pattern in [
            r'I (?:should|need to|must) (.+?)(?:\.|$)',
            r'Important:?\s*(.+?)(?:\.|$)',
            r'Key (?:point|insight):?\s*(.+?)(?:\.|$)'
        ]:
            for match in re.finditer(pattern, thinking, re.IGNORECASE):
                insight = match.group(1).strip()
                if len(insight) > 10:
                    insights.append(insight)
        
        return insights[:5]  # Max 5 insights
    
    def _extract_confidence(self, thinking: str) -> float:
        """Extract confidence level from thinking text.
        
        P1.2: Used to determine if we should exit early based on
        the agent's perceived confidence in its reasoning.
        
        Returns:
            Float between 0.0 and 1.0 indicating confidence level
        """
        thinking_lower = thinking.lower()
        
        # Confidence keywords mapped to scores
        confidence_keywords = {
            "certain": 0.95,
            "definitely": 0.95,
            "confident": 0.90,
            "sure": 0.85,
            "clear": 0.85,
            "likely": 0.75,
            "probably": 0.70,
            "think": 0.60,
            "possibly": 0.50,
            "maybe": 0.45,
            "unsure": 0.30,
            "uncertain": 0.25,
            "don't know": 0.20,
        }
        
        # Find highest matching confidence
        for keyword, conf in confidence_keywords.items():
            if keyword in thinking_lower:
                return conf
        
        # Default confidence
        return 0.60
    
    async def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a tool and return result."""
        if tool_name not in self.tools:
            return f"Error: Unknown tool '{tool_name}'"
        
        tool = self.tools[tool_name]
        
        try:
            if hasattr(tool, 'aforward'):
                result = await tool.aforward(**args)
            elif hasattr(tool, 'forward'):
                result = tool.forward(**args)
            elif hasattr(tool, 'execute'):
                result = await tool.execute(**args)
            elif callable(tool):
                import inspect
                if inspect.iscoroutinefunction(tool):
                    result = await tool(**args)
                else:
                    result = tool(**args)
                    if inspect.isawaitable(result):
                        result = await result
            else:
                return f"Error: Tool '{tool_name}' not callable"
            
            if hasattr(result, 'data'):
                return json.dumps(result.data, default=str)
            return str(result)
            
        except Exception as e:
            return f"Error executing {tool_name}: {e}"
    
    async def _generate_final_answer(
        self,
        query: str,
        context: str,
        start_time: datetime
    ) -> ThinkingResult:
        """Generate final answer after max rounds."""
        prompt = f"""Based on all the thinking and tool results, provide your final answer.

Query: {query}
Context: {context}

<answer>Your complete final answer here</answer>"""
        
        response = await self.llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        answer_match = re.search(r'<answer>(.*?)</answer>', response_text, re.DOTALL)
        answer = answer_match.group(1).strip() if answer_match else response_text
        
        return ThinkingResult(
            answer=answer,
            thinking_blocks=self.thinking_history,
            tool_calls=self.tool_call_history,
            total_thinking_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
        )
    
    def _get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions."""
        if not self.tools:
            return "No tools available."
        
        descriptions = []
        for tool in self.tools.values():
            name = getattr(tool, 'name', None) or getattr(tool, '__name__', str(tool))
            desc = getattr(tool, 'description', "") or getattr(tool, '__doc__', "")
            descriptions.append(f"- {name}: {desc}")
        
        return "\n".join(descriptions)
    
    def get_thinking_trace(self) -> str:
        """Get formatted thinking trace from last run."""
        if not self.thinking_history:
            return "No thinking recorded."
        
        lines = []
        for i, block in enumerate(self.thinking_history, 1):
            lines.append(f"## Step {i}: {block.reasoning_type.value.title()}")
            lines.append(f"```\n{block.content}\n```\n")
        
        return "\n".join(lines)


# Factory function
def create_thinking_agent(llm, tools: List[Any] = None) -> ThinkingAgent:
    """Create a configured thinking agent."""
    return ThinkingAgent(llm=llm, tools=tools or [], verbose=True)
