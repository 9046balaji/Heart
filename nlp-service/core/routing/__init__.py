"""
Routing module for Specialist vs. Generalist AI architecture.

Provides semantic routing capabilities to direct queries to the appropriate
AI agent (Doctor/MedGemma or Receptionist/General Chat).
"""

from .semantic_router import (
    SemanticRouterService,
    AgentType,
    IntentCategory,
    RouteDecision,
    get_semantic_router,
)

__all__ = [
    "SemanticRouterService",
    "AgentType",
    "IntentCategory",
    "RouteDecision",
    "get_semantic_router",
]
