"""
Tool Registry for Function Calling

This module implements a tool registry system for function calling,
enabling LLMs to execute health-specific tools.

Features:
- Tool registration and discovery
- Schema generation for LLM function calling
- Parameter validation
- Execution with error handling
- Health-specific tools out of the box

Addresses GAPs from AI_ML_TOOLS_IMPLEMENTATION_GUIDE.md:
- ❌ No function calling -> ✅ Full tool registry
- ❌ Basic prompting -> ✅ Tool-augmented responses
"""

from .tool_registry import (
    Tool,
    ToolParameter,
    ToolRegistry,
    ToolResult,
    get_tool_registry,
    register_tool,
    execute_tool,
)

from .health_tools import (
    blood_pressure_analyzer,
    heart_rate_analyzer,
    medication_checker,
    drug_interaction_checker,
    symptom_triage,
    bmi_calculator,
    cardiovascular_risk_calculator,
    appointment_scheduler,
    health_reminder_setter,
)

__all__ = [
    # Core
    "Tool",
    "ToolParameter",
    "ToolRegistry",
    "ToolResult",
    "get_tool_registry",
    "register_tool",
    "execute_tool",
    # Health tools
    "blood_pressure_analyzer",
    "heart_rate_analyzer",
    "medication_checker",
    "drug_interaction_checker",
    "symptom_triage",
    "bmi_calculator",
    "cardiovascular_risk_calculator",
    "appointment_scheduler",
    "health_reminder_setter",
]
