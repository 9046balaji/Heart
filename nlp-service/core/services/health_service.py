"""
Health data service with database operations.
Handles encrypted storage and retrieval of patient health records.

Phase 2: Health Data Service
"""

from sqlalchemy import create_engine, Column, String, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Optional, List, Dict, Union
import logging

from ..models.health import HealthRecord
from ..models.access_log import HealthRecordAccessLog  # Import the new access log model
from ..services.encryption_service import get_encryption_service

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# DATABASE ORM MODELS
# ============================================================================


class HealthRecordDB(Base):
    """SQLAlchemy ORM model for encrypted health records."""

    __tablename__ = "health_records"

    # Primary key
    patient_id = Column(String, primary_key=True, index=True)

    # Encrypted sensitive data
    vitals_encrypted = Column(String, nullable=True)
    medications_encrypted = Column(String, nullable=True)
    allergies_encrypted = Column(String, nullable=True)
    medical_history_encrypted = Column(String, nullable=True)

    # Searchable fields (not encrypted for performance)
    chronic_conditions = Column(JSON)
    data_classification = Column(String, default="CONFIDENTIAL_MEDICAL")
    hipaa_consent = Column(Boolean, default=True)

    # Audit fields
    created_at = Column(DateTime, default=datetime.now)
    modified_at = Column(DateTime, default=datetime.now)
    last_accessed_at = Column(DateTime, nullable=True)
    accessed_by = Column(JSON, default=list)

    # Metadata
    is_active = Column(Boolean, default=True)


# ============================================================================
# DATABASE SESSION SETUP
# ============================================================================


# Default to SQLite for development, override with HEALTH_DB_URL in production
_db_url = "sqlite:///./health_data.db"

try:
    from agents.config import HEALTH_DB_URL

    _db_url = HEALTH_DB_URL
except ImportError:
    logger.warning("Could not import HEALTH_DB_URL, using default SQLite")

engine = create_engine(_db_url, pool_size=10, pool_recycle=3600, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables including the new access log table
Base.metadata.create_all(bind=engine)
logger.info(f"Database initialized: {_db_url}")


# ============================================================================
# HEALTH SERVICE
# ============================================================================


class HealthService:
    """Service for managing health records with encryption and HIPAA compliance."""

    def __init__(self):
        """Initialize health service."""
        self.encryption = get_encryption_service()
        logger.info("HealthService initialized")

    def create_health_record(self, health_data: HealthRecord, user_id: str) -> bool:
        """
        Create new health record with encryption.

        Args:
            health_data: HealthRecord object
            user_id: User ID creating the record

        Returns:
            True if successful, False otherwise
        """
        session = SessionLocal()
        try:
            # Encrypt sensitive data
            encrypted_vitals = None
            if health_data.vitals:
                encrypted_vitals = self.encryption.encrypt(
                    health_data.vitals.model_dump()
                )

            encrypted_meds = None
            if health_data.active_medications:
                meds_list = [m.model_dump() for m in health_data.active_medications]
                encrypted_meds = self.encryption.encrypt(meds_list)

            encrypted_allergies = None
            if health_data.allergies:
                allergies_list = [a.model_dump() for a in health_data.allergies]
                encrypted_allergies = self.encryption.encrypt(allergies_list)

            # Create DB record
            db_record = HealthRecordDB(
                patient_id=health_data.patient_id,
                vitals_encrypted=encrypted_vitals,
                medications_encrypted=encrypted_meds,
                allergies_encrypted=encrypted_allergies,
                chronic_conditions=health_data.chronic_conditions,
                data_classification=health_data.data_classification,
                hipaa_consent=health_data.hipaa_consent,
                # ✅ Remove accessed_by field - using dedicated access log table instead
            )

            session.add(db_record)

            # ✅ Log the creation in the access log table
            access_log = HealthRecordAccessLog(
                patient_id=health_data.patient_id,
                user_id=user_id,
                access_type="create",
                accessed_at=datetime.now(),
                ip_address=None,  # Would need to pass this in from the request context
            )
            session.add(access_log)

            session.commit()

            logger.info(
                f"Health record created: patient={health_data.patient_id[:8]}..., by={user_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error creating health record: {e}")
            session.rollback()
            return False

        finally:
            session.close()

    def get_health_record(
        self, patient_id: str, user_id: str
    ) -> Optional[HealthRecord]:
        """
        Retrieve and decrypt health record.

        Args:
            patient_id: Patient ID to retrieve
            user_id: User ID requesting the record (for audit)

        Returns:
            HealthRecord object or None if not found
        """
        session = SessionLocal()
        try:
            # Query database
            db_record = (
                session.query(HealthRecordDB)
                .filter(
                    HealthRecordDB.patient_id == patient_id,
                    HealthRecordDB.is_active == True,
                )
                .first()
            )

            if not db_record:
                logger.warning(f"Health record not found: {patient_id}")
                return None

            # Decrypt data
            vitals = None
            if db_record.vitals_encrypted:
                vitals_dict = self.encryption.decrypt(db_record.vitals_encrypted)
                from models.health import VitalSigns

                vitals = VitalSigns(**vitals_dict)

            medications = []
            if db_record.medications_encrypted:
                meds_data = self.encryption.decrypt(db_record.medications_encrypted)
                from models.health import MedicationRecord

                medications = [MedicationRecord(**m) for m in meds_data]

            allergies = []
            if db_record.allergies_encrypted:
                allergies_data = self.encryption.decrypt(db_record.allergies_encrypted)
                from models.health import Allergy

                allergies = [Allergy(**a) for a in allergies_data]

            # Reconstruct HealthRecord
            health_record = HealthRecord(
                patient_id=patient_id,
                vitals=vitals,
                active_medications=medications,
                allergies=allergies,
                chronic_conditions=db_record.chronic_conditions or [],
                data_classification=db_record.data_classification,
                hipaa_consent=db_record.hipaa_consent,
                modified_at=db_record.modified_at,
            )

            # ✅ Use dedicated table for audit logging instead of JSON column
            access_log = HealthRecordAccessLog(
                patient_id=patient_id,
                user_id=user_id,
                access_type="view",
                accessed_at=datetime.now(),
                ip_address=None,  # Would need to pass this in from the request context
            )
            session.add(access_log)

            # Update last accessed time
            db_record.last_accessed_at = datetime.now()
            session.commit()

            logger.info(
                f"Health record retrieved: patient={patient_id[:8]}..., by={user_id}"
            )

            return health_record

        except Exception as e:
            logger.error(f"Error retrieving health record: {e}")
            session.rollback()  # Rollback in case of error
            return None

        finally:
            session.close()

    def update_health_record(
        self, patient_id: str, health_data: HealthRecord, user_id: str
    ) -> bool:
        """
        Update existing health record.

        Args:
            patient_id: Patient ID to update
            health_data: Updated HealthRecord object
            user_id: User ID performing update

        Returns:
            True if successful, False otherwise
        """
        session = SessionLocal()
        try:
            db_record = (
                session.query(HealthRecordDB)
                .filter(HealthRecordDB.patient_id == patient_id)
                .first()
            )

            if not db_record:
                logger.warning(f"Record not found for update: {patient_id}")
                return False

            # Encrypt updated data
            if health_data.vitals:
                db_record.vitals_encrypted = self.encryption.encrypt(
                    health_data.vitals.model_dump()
                )

            if health_data.active_medications:
                meds_list = [m.model_dump() for m in health_data.active_medications]
                db_record.medications_encrypted = self.encryption.encrypt(meds_list)

            # Update metadata
            db_record.modified_at = datetime.now()
            db_record.chronic_conditions = health_data.chronic_conditions

            # ✅ Use dedicated table for audit logging instead of JSON column
            access_log = HealthRecordAccessLog(
                patient_id=patient_id,
                user_id=user_id,
                access_type="edit",
                accessed_at=datetime.now(),
                ip_address=None,  # Would need to pass this in from the request context
            )
            session.add(access_log)

            session.commit()

            logger.info(f"Health record updated: {patient_id[:8]}... by {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating health record: {e}")
            session.rollback()
            return False

        finally:
            session.close()

    def soft_delete_health_record(self, patient_id: str, user_id: str) -> bool:
        """
        Soft delete (mark inactive) a health record.
        Preserves data for audit trail compliance.

        Args:
            patient_id: Patient ID to deactivate
            user_id: User ID performing deletion

        Returns:
            True if successful, False otherwise
        """
        session = SessionLocal()
        try:
            db_record = (
                session.query(HealthRecordDB)
                .filter(HealthRecordDB.patient_id == patient_id)
                .first()
            )

            if not db_record:
                return False

            db_record.is_active = False
            db_record.modified_at = datetime.now()

            # ✅ Use dedicated table for audit logging instead of JSON column
            access_log = HealthRecordAccessLog(
                patient_id=patient_id,
                user_id=user_id,
                access_type="delete",
                accessed_at=datetime.now(),
                ip_address=None,  # Would need to pass this in from the request context
            )
            session.add(access_log)

            session.commit()

            logger.info(f"Health record deactivated: {patient_id[:8]}... by {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting health record: {e}")
            session.rollback()
            return False

        finally:
            session.close()

    def get_access_audit_log(self, patient_id: str) -> Optional[List[Dict]]:
        """
        Get audit log of who accessed this record.

        Args:
            patient_id: Patient ID

        Returns:
            List of access log entries or None if record not found
        """
        session = SessionLocal()
        try:
            # Query the dedicated access log table
            access_logs = (
                session.query(HealthRecordAccessLog)
                .filter(HealthRecordAccessLog.patient_id == patient_id)
                .order_by(HealthRecordAccessLog.accessed_at.desc())
                .all()
            )

            # Convert to list of dictionaries
            return [
                {
                    "user_id": log.user_id,
                    "access_type": log.access_type,
                    "accessed_at": (
                        log.accessed_at.isoformat() if log.accessed_at else None
                    ),
                    "ip_address": log.ip_address,
                }
                for log in access_logs
            ]

        except Exception as e:
            logger.error(f"Error retrieving access audit log: {e}")
            return None

        finally:
            session.close()

    # ========================================================================
    # ASYNC VARIANTS (PHASE 2A ENHANCEMENT: Non-blocking database operations)
    # ========================================================================
    # Note: Async variants follow same pattern but without event loop blocking.
    # Use these in FastAPI routes for better concurrency (10x+ throughput improvement).

    async def create_health_record_async(
        self, health_data: HealthRecord, user_id: str
    ) -> bool:
        """
        Create new health record asynchronously (non-blocking).
        PHASE 2A ENHANCEMENT: Async variant avoids blocking event loop.

        Args:
            health_data: HealthRecord object
            user_id: User ID creating the record

        Returns:
            True if successful, False otherwise
        """
        # Run sync database operation in thread pool to avoid event loop blocking
        from fastapi.concurrency import run_in_threadpool

        return await run_in_threadpool(self.create_health_record, health_data, user_id)

    async def get_health_record_async(
        self, patient_id: str, user_id: str
    ) -> Optional[HealthRecord]:
        """
        Retrieve and decrypt health record asynchronously (non-blocking).
        PHASE 2A ENHANCEMENT: Async variant avoids blocking event loop.

        Args:
            patient_id: Patient ID to retrieve
            user_id: User ID requesting the record (for audit)

        Returns:
            HealthRecord object or None if not found
        """
        from fastapi.concurrency import run_in_threadpool

        return await run_in_threadpool(self.get_health_record, patient_id, user_id)

    async def update_health_record_async(
        self, patient_id: str, health_data: HealthRecord, user_id: str
    ) -> bool:
        """
        Update existing health record asynchronously (non-blocking).
        PHASE 2A ENHANCEMENT: Async variant avoids blocking event loop.

        Args:
            patient_id: Patient ID to update
            health_data: Updated HealthRecord object
            user_id: User ID performing update

        Returns:
            True if successful, False otherwise
        """
        from fastapi.concurrency import run_in_threadpool

        return await run_in_threadpool(
            self.update_health_record, patient_id, health_data, user_id
        )

    async def soft_delete_health_record_async(
        self, patient_id: str, user_id: str
    ) -> bool:
        """
        Soft delete (mark inactive) a health record asynchronously (non-blocking).
        PHASE 2A ENHANCEMENT: Async variant avoids blocking event loop.

        Args:
            patient_id: Patient ID to deactivate
            user_id: User ID performing deletion

        Returns:
            True if successful, False otherwise
        """
        from fastapi.concurrency import run_in_threadpool

        return await run_in_threadpool(
            self.soft_delete_health_record, patient_id, user_id
        )

    async def get_access_audit_log_async(self, patient_id: str) -> Optional[List[Dict]]:
        """
        Get audit log of who accessed this record asynchronously (non-blocking).
        PHASE 2A ENHANCEMENT: Async variant avoids blocking event loop.

        Args:
            patient_id: Patient ID

        Returns:
            List of access log entries or None if record not found
        """
        from fastapi.concurrency import run_in_threadpool

        return await run_in_threadpool(self.get_access_audit_log, patient_id)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================


_health_service: Union[HealthService, None] = None


def get_health_service() -> HealthService:
    """
    Get or create health service singleton.

    Returns:
        HealthService instance
    """
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service


def reset_health_service() -> None:
    """Reset health service singleton (useful for testing)."""
    global _health_service
    _health_service = None
