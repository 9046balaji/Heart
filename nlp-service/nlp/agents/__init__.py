"""
ADK Agent module for nlp-service.
Provides health data and appointment management agents.

Includes:
- Base agents (BaseAgent, HealthAgent, AppointmentAgent)
- Sequential and Parallel agents
- Multi-agent orchestrator for complex queries
"""

from .base import (
    BaseAgent,
    HealthAgent,
    AppointmentAgent,
    SequentialAgent,
    ParallelAgent,
    HealthAppointmentOrchestrator
)

from .orchestrator import (
    AgentOrchestrator,
    AgentRole,
    AgentTask,
    OrchestratorResult,
    PlannerAgent,
    HealthAnalystAgent,
    MedicalResearchAgent,
    MedicationAdvisorAgent,
    SymptomCheckerAgent,
    LifestyleCoachAgent,
    ValidatorAgent,
    SynthesizerAgent,
    create_orchestrator,
)

__all__ = [
    # Base agents
    "BaseAgent",
    "HealthAgent",
    "AppointmentAgent",
    "SequentialAgent",
    "ParallelAgent",
    "HealthAppointmentOrchestrator",
    # Multi-agent orchestrator
    "AgentOrchestrator",
    "AgentRole",
    "AgentTask",
    "OrchestratorResult",
    "PlannerAgent",
    "HealthAnalystAgent",
    "MedicalResearchAgent",
    "MedicationAdvisorAgent",
    "SymptomCheckerAgent",
    "LifestyleCoachAgent",
    "ValidatorAgent",
    "SynthesizerAgent",
    "create_orchestrator",
]
