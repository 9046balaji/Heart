"""
Appointments module exports.

Provides unified access to appointment models, services, and agents.
"""

from appointments.models import (
    AppointmentStatus,
    AppointmentType,
    ReminderType,
    AvailabilityStatus,
    Provider,
    TimeSlot,
    ProviderSchedule,
    Appointment,
    AppointmentReminder,
    AppointmentCreateRequest,
    AppointmentUpdateRequest,
    AppointmentCancelRequest,
    AppointmentResponse,
    AvailabilityQueryRequest,
    AvailabilityQueryResponse,
)

from appointments.service import (
    AppointmentService,
    get_appointment_service,
    reset_appointment_service,
    AppointmentDB,
    ProviderDB,
    TimeSlotDB,
    SessionLocal,
    engine,
)

from appointments.agents import (
    AppointmentParserAgent,
    AppointmentValidatorAgent,
    AppointmentBookingAgent,
)

__all__ = [
    # Models
    "AppointmentStatus",
    "AppointmentType",
    "ReminderType",
    "AvailabilityStatus",
    "Provider",
    "TimeSlot",
    "ProviderSchedule",
    "Appointment",
    "AppointmentReminder",
    "AppointmentCreateRequest",
    "AppointmentUpdateRequest",
    "AppointmentCancelRequest",
    "AppointmentResponse",
    "AvailabilityQueryRequest",
    "AvailabilityQueryResponse",
    # Service
    "AppointmentService",
    "get_appointment_service",
    "reset_appointment_service",
    "AppointmentDB",
    "ProviderDB",
    "TimeSlotDB",
    "SessionLocal",
    "engine",
    # Agents
    "AppointmentParserAgent",
    "AppointmentValidatorAgent",
    "AppointmentBookingAgent",
]
