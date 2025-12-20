"""
Appointment service with database operations and scheduling.

Phase 3: Appointment Service
"""

from sqlalchemy import (
    create_engine,
    Column,
    String,
    DateTime,
    Boolean,
    Integer,
    JSON,
    Float,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from typing import Optional, List
import logging

from appointments.models import (
    Appointment,
    AppointmentStatus,
    AppointmentCreateRequest,
    AppointmentUpdateRequest,
    AppointmentCancelRequest,
)

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# DATABASE ORM MODELS
# ============================================================================


class AppointmentDB(Base):
    """SQLAlchemy ORM model for appointments."""

    __tablename__ = "appointments"

    # Primary keys
    appointment_id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, index=True)
    provider_id = Column(String, index=True)

    # Appointment details
    appointment_type = Column(String)
    status = Column(String, default="pending", index=True)
    scheduled_datetime = Column(DateTime, index=True)
    estimated_duration_minutes = Column(Integer, default=30)

    # Location
    location = Column(String, nullable=True)
    is_telehealth = Column(Boolean, default=False)
    meeting_url = Column(String, nullable=True)

    # Medical context
    reason_for_visit = Column(String)
    clinical_notes = Column(String, nullable=True)
    relevant_medications = Column(JSON, default=list)
    known_allergies = Column(JSON, default=list)

    # Reminders
    reminders = Column(JSON, default=list)

    # HIPAA compliance
    data_classification = Column(String, default="CONFIDENTIAL_MEDICAL")
    patient_confirmed = Column(Boolean, default=False)
    confirmation_datetime = Column(DateTime, nullable=True)

    # Audit trail
    created_at = Column(DateTime, default=datetime.now)
    modified_at = Column(DateTime, default=datetime.now)
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_by = Column(String, nullable=True)
    cancellation_reason = Column(String, nullable=True)


class ProviderDB(Base):
    """SQLAlchemy ORM model for providers."""

    __tablename__ = "providers"

    provider_id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    specialty = Column(String, index=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    office_location = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    is_accepting_patients = Column(Boolean, default=True)
    average_rating = Column(Float, nullable=True)
    total_reviews = Column(Integer, default=0)


class TimeSlotDB(Base):
    """SQLAlchemy ORM model for available time slots."""

    __tablename__ = "time_slots"

    slot_id = Column(String, primary_key=True, index=True)
    provider_id = Column(String, index=True)
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime)
    status = Column(String, default="available", index=True)
    appointment_duration_minutes = Column(Integer, default=30)


# ============================================================================
# DATABASE SESSION SETUP
# ============================================================================


import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_db_url = f"sqlite:///{os.path.join(BASE_DIR, 'appointments.db')}"

try:
    from agents.config import APPOINTMENTS_DB_URL

    _db_url = APPOINTMENTS_DB_URL
except ImportError:
    logger.warning("Could not import APPOINTMENTS_DB_URL, using default SQLite")

engine = create_engine(_db_url, pool_size=10, pool_recycle=3600, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)
logger.info(f"Appointment database initialized: {_db_url}")


# ============================================================================
# APPOINTMENT SERVICE
# ============================================================================


class AppointmentService:
    """Service for managing appointments with scheduling validation."""

    def __init__(self):
        """Initialize appointment service."""
        logger.info("AppointmentService initialized")

    def create_appointment(
        self, request: AppointmentCreateRequest, user_id: str
    ) -> Optional[str]:
        """
        Create new appointment.

        Args:
            request: Appointment creation request
            user_id: User creating the appointment

        Returns:
            Appointment ID if successful, None otherwise
        """
        session = SessionLocal()
        try:
            import uuid

            appointment_id = f"appt_{uuid.uuid4().hex[:12]}"

            # Validate time slot is available
            conflicting = (
                session.query(AppointmentDB)
                .filter(
                    AppointmentDB.provider_id == request.provider_id,
                    AppointmentDB.scheduled_datetime == request.scheduled_datetime,
                    AppointmentDB.status != "cancelled",
                )
                .first()
            )

            if conflicting:
                logger.warning(
                    f"Time slot already booked: {request.provider_id} at {request.scheduled_datetime}"
                )
                return None

            # Create appointment
            db_appointment = AppointmentDB(
                appointment_id=appointment_id,
                patient_id=request.patient_id,
                provider_id=request.provider_id,
                appointment_type=request.appointment_type.value,
                status="pending",
                scheduled_datetime=request.scheduled_datetime,
                location="",
                is_telehealth=request.is_telehealth,
                reason_for_visit=request.reason_for_visit,
                relevant_medications=request.relevant_medications,
                known_allergies=request.known_allergies,
                data_classification="CONFIDENTIAL_MEDICAL",
            )

            session.add(db_appointment)
            session.commit()

            logger.info(
                f"Appointment created: {appointment_id}, patient={request.patient_id[:8]}..., "
                f"provider={request.provider_id}, by={user_id}"
            )
            return appointment_id

        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            session.rollback()
            return None

        finally:
            session.close()

    def get_appointment(
        self, appointment_id: str, user_id: str
    ) -> Optional[Appointment]:
        """
        Retrieve appointment details.

        Args:
            appointment_id: Appointment ID to retrieve
            user_id: User requesting (for audit)

        Returns:
            Appointment object or None if not found
        """
        session = SessionLocal()
        try:
            db_record = (
                session.query(AppointmentDB)
                .filter(AppointmentDB.appointment_id == appointment_id)
                .first()
            )

            if not db_record:
                logger.warning(f"Appointment not found: {appointment_id}")
                return None

            # Reconstruct Appointment object
            appointment = Appointment(
                appointment_id=db_record.appointment_id,
                patient_id=db_record.patient_id,
                provider_id=db_record.provider_id,
                appointment_type=db_record.appointment_type,
                status=AppointmentStatus(db_record.status),
                scheduled_datetime=db_record.scheduled_datetime,
                estimated_duration_minutes=db_record.estimated_duration_minutes,
                location=db_record.location,
                is_telehealth=db_record.is_telehealth,
                meeting_url=db_record.meeting_url,
                reason_for_visit=db_record.reason_for_visit,
                clinical_notes=db_record.clinical_notes,
                relevant_medications=db_record.relevant_medications or [],
                known_allergies=db_record.known_allergies or [],
                patient_confirmed=db_record.patient_confirmed,
                confirmation_datetime=db_record.confirmation_datetime,
                created_at=db_record.created_at,
                modified_at=db_record.modified_at,
                cancelled_at=db_record.cancelled_at,
                cancelled_by=db_record.cancelled_by,
                cancellation_reason=db_record.cancellation_reason,
            )

            logger.info(f"Appointment retrieved: {appointment_id}, by={user_id}")
            return appointment

        except Exception as e:
            logger.error(f"Error retrieving appointment: {e}")
            return None

        finally:
            session.close()

    def update_appointment(
        self, appointment_id: str, request: AppointmentUpdateRequest, user_id: str
    ) -> bool:
        """
        Update appointment details.

        Args:
            appointment_id: Appointment to update
            request: Update request
            user_id: User performing update

        Returns:
            True if successful, False otherwise
        """
        session = SessionLocal()
        try:
            db_record = (
                session.query(AppointmentDB)
                .filter(AppointmentDB.appointment_id == appointment_id)
                .first()
            )

            if not db_record:
                logger.warning(f"Appointment not found for update: {appointment_id}")
                return False

            # Update fields if provided
            if request.status:
                db_record.status = request.status.value
            if request.scheduled_datetime:
                db_record.scheduled_datetime = request.scheduled_datetime
            if request.clinical_notes:
                db_record.clinical_notes = request.clinical_notes
            if request.patient_confirmed is not None:
                db_record.patient_confirmed = request.patient_confirmed
                if request.patient_confirmed:
                    db_record.confirmation_datetime = datetime.now()

            db_record.modified_at = datetime.now()
            session.commit()

            logger.info(f"Appointment updated: {appointment_id}, by={user_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating appointment: {e}")
            session.rollback()
            return False

        finally:
            session.close()

    def cancel_appointment(
        self, appointment_id: str, request: AppointmentCancelRequest
    ) -> bool:
        """
        Cancel appointment.

        Args:
            appointment_id: Appointment to cancel
            request: Cancellation request

        Returns:
            True if successful, False otherwise
        """
        session = SessionLocal()
        try:
            db_record = (
                session.query(AppointmentDB)
                .filter(AppointmentDB.appointment_id == appointment_id)
                .first()
            )

            if not db_record:
                return False

            if db_record.status == "cancelled":
                logger.warning(f"Appointment already cancelled: {appointment_id}")
                return False

            db_record.status = "cancelled"
            db_record.cancelled_at = datetime.now()
            db_record.cancelled_by = request.cancelled_by
            db_record.cancellation_reason = request.cancellation_reason
            db_record.modified_at = datetime.now()

            session.commit()

            logger.info(
                f"Appointment cancelled: {appointment_id}, by={request.cancelled_by}, "
                f"reason={request.cancellation_reason}"
            )
            return True

        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            session.rollback()
            return False

        finally:
            session.close()

    def get_patient_appointments(
        self, patient_id: str, include_cancelled: bool = False
    ) -> List[Appointment]:
        """
        Get all appointments for a patient.

        Args:
            patient_id: Patient ID
            include_cancelled: Whether to include cancelled appointments

        Returns:
            List of appointments
        """
        session = SessionLocal()
        try:
            query = session.query(AppointmentDB).filter(
                AppointmentDB.patient_id == patient_id
            )

            if not include_cancelled:
                query = query.filter(AppointmentDB.status != "cancelled")

            db_records = query.order_by(AppointmentDB.scheduled_datetime).all()

            appointments = []
            for db_record in db_records:
                appointment = Appointment(
                    appointment_id=db_record.appointment_id,
                    patient_id=db_record.patient_id,
                    provider_id=db_record.provider_id,
                    appointment_type=db_record.appointment_type,
                    status=AppointmentStatus(db_record.status),
                    scheduled_datetime=db_record.scheduled_datetime,
                    estimated_duration_minutes=db_record.estimated_duration_minutes,
                    location=db_record.location,
                    is_telehealth=db_record.is_telehealth,
                    meeting_url=db_record.meeting_url,
                    reason_for_visit=db_record.reason_for_visit,
                    clinical_notes=db_record.clinical_notes,
                    relevant_medications=db_record.relevant_medications or [],
                    known_allergies=db_record.known_allergies or [],
                    patient_confirmed=db_record.patient_confirmed,
                    confirmation_datetime=db_record.confirmation_datetime,
                    created_at=db_record.created_at,
                    modified_at=db_record.modified_at,
                    cancelled_at=db_record.cancelled_at,
                    cancelled_by=db_record.cancelled_by,
                    cancellation_reason=db_record.cancellation_reason,
                )
                appointments.append(appointment)

            logger.info(
                f"Retrieved {len(appointments)} appointments for patient {patient_id[:8]}..."
            )
            return appointments

        except Exception as e:
            logger.error(f"Error retrieving patient appointments: {e}")
            return []

        finally:
            session.close()

    def get_provider_appointments(
        self, provider_id: str, start_date: datetime, end_date: datetime
    ) -> List[Appointment]:
        """
        Get appointments for a provider in date range.

        Args:
            provider_id: Provider ID
            start_date: Range start
            end_date: Range end

        Returns:
            List of appointments
        """
        session = SessionLocal()
        try:
            db_records = (
                session.query(AppointmentDB)
                .filter(
                    AppointmentDB.provider_id == provider_id,
                    AppointmentDB.scheduled_datetime >= start_date,
                    AppointmentDB.scheduled_datetime <= end_date,
                    AppointmentDB.status != "cancelled",
                )
                .order_by(AppointmentDB.scheduled_datetime)
                .all()
            )

            appointments = [
                Appointment(
                    appointment_id=db.appointment_id,
                    patient_id=db.patient_id,
                    provider_id=db.provider_id,
                    appointment_type=db.appointment_type,
                    status=AppointmentStatus(db.status),
                    scheduled_datetime=db.scheduled_datetime,
                    estimated_duration_minutes=db.estimated_duration_minutes,
                    location=db.location,
                    is_telehealth=db.is_telehealth,
                    meeting_url=db.meeting_url,
                    reason_for_visit=db.reason_for_visit,
                    clinical_notes=db.clinical_notes,
                    relevant_medications=db.relevant_medications or [],
                    known_allergies=db.known_allergies or [],
                    patient_confirmed=db.patient_confirmed,
                    confirmation_datetime=db.confirmation_datetime,
                    created_at=db.created_at,
                    modified_at=db.modified_at,
                    cancelled_at=db.cancelled_at,
                    cancelled_by=db.cancelled_by,
                    cancellation_reason=db.cancellation_reason,
                )
                for db in db_records
            ]

            return appointments

        except Exception as e:
            logger.error(f"Error retrieving provider appointments: {e}")
            return []

        finally:
            session.close()


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================


_appointment_service: Optional[AppointmentService] = None


def get_appointment_service() -> AppointmentService:
    """
    Get or create appointment service singleton.

    Returns:
        AppointmentService instance
    """
    global _appointment_service
    if _appointment_service is None:
        _appointment_service = AppointmentService()
    return _appointment_service


def reset_appointment_service() -> None:
    """Reset appointment service singleton (useful for testing)."""
    global _appointment_service
    _appointment_service = None
