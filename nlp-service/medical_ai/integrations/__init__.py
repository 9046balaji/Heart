"""
Integrations Package.

System integration services for connecting medical document data
with other application modules as specified in medical.md Section 5:

- Heart disease prediction model
- Longitudinal patient history
- Doctor consultation dashboard
- Chatbot (contextualized Q&A)
- Nutrition and exercise recommendations
"""

from typing import TYPE_CHECKING

# Lazy imports to avoid circular dependencies
if TYPE_CHECKING:
    from .prediction_integration import PredictionIntegrationService
    from .timeline_service import PatientTimelineService
    from .doctor_dashboard import DoctorDashboardService
    from .chatbot_document_context import ChatbotDocumentContextService
    from .weekly_aggregation import WeeklyAggregationService

__all__ = [
    "PredictionIntegrationService",
    "PatientTimelineService",
    "DoctorDashboardService",
    "ChatbotDocumentContextService",
    "WeeklyAggregationService",
]
