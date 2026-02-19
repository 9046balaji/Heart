"""
SQLAlchemy models for the Cardio AI application.

These models represent the database schema and are used by Alembic
for migration generation and management.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    email = Column(String(255))
    date_of_birth = Column(DateTime)
    gender = Column(String(20))
    blood_type = Column(String(5))
    weight_kg = Column(Float)
    height_cm = Column(Float)
    known_conditions = Column(JSON)
    medications = Column(JSON)
    allergies = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        Index('idx_user_id', 'user_id'),
    )


class Device(Base):
    __tablename__ = 'devices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(255), unique=True, nullable=False)
    user_id = Column(String(255), nullable=False)  # Not using FK to avoid compatibility issues
    device_type = Column(String(50))
    model = Column(String(100))
    last_sync = Column(TIMESTAMP)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index('idx_device_user', 'user_id'),
    )


class PatientRecord(Base):
    __tablename__ = 'patient_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)  # Not using FK to avoid compatibility issues
    record_type = Column(String(100))
    data = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        Index('idx_patient_user', 'user_id'),
        Index('idx_patient_created', 'user_id', 'created_at'),
    )


class Vital(Base):
    __tablename__ = 'vitals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)  # Not using FK to avoid compatibility issues
    device_id = Column(String(255))
    metric_type = Column(String(50))
    value = Column(Float)
    unit = Column(String(20))
    recorded_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        Index('idx_vitals_user', 'user_id'),
        Index('idx_vitals_recorded', 'user_id', 'recorded_at'),
        Index('idx_vitals_metric', 'metric_type'),
    )


class HealthAlert(Base):
    __tablename__ = 'health_alerts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)  # Not using FK to avoid compatibility issues
    alert_type = Column(String(50))
    severity = Column(String(20))
    message = Column(Text)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    resolved_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        Index('idx_alerts_user', 'user_id'),
    )


class MedicalKnowledgeBase(Base):
    __tablename__ = 'medical_knowledge_base'

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text)
    content_type = Column(String(100))
    embedding = Column(Text)  # Using TEXT instead of BLOB for compatibility
    metadata_json = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        Index('idx_knowledge_type', 'content_type'),
    )


class ChatSession(Base):
    __tablename__ = 'chat_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False)
    user_id = Column(String(255), nullable=False)  # Not using FK to avoid compatibility issues
    started_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    ended_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        Index('idx_session_user', 'user_id'),
    )


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False)  # Not using FK to avoid compatibility issues
    message_type = Column(String(20))  # 'user' or 'assistant'
    content = Column(Text)
    metadata_json = Column(JSON)
    timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        Index('idx_message_session', 'session_id'),
    )


class NotificationFailure(Base):
    __tablename__ = 'notification_failures'

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Notification details
    notification_type = Column(String(50), nullable=False)  # 'email', 'push', 'sms'
    recipient = Column(String(255), nullable=False)  # Email or phone number
    subject = Column(String(500))
    content = Column(Text)
    
    # Failure tracking
    original_attempt_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=5)
    next_retry_at = Column(TIMESTAMP)
    
    # Error details
    last_error = Column(Text)
    status = Column(String(20), default='pending')  # 'pending', 'retrying', 'failed', 'succeeded'
    
    # Metadata
    user_id = Column(String(255))
    metadata_json = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        Index('idx_status_next_retry', 'status', 'next_retry_at'),
        Index('idx_nf_user_id', 'user_id'),
        Index('idx_nf_created_at', 'created_at'),
    )


class RagFeedback(Base):
    __tablename__ = 'rag_feedback'

    feedback_id = Column(String(255), primary_key=True)
    query = Column(Text)
    response_preview = Column(Text)
    rating = Column(Integer)  # 1 = thumbs up, -1 = thumbs down, 0 = neutral
    user_id = Column(String(255))
    timestamp = Column(String(255))  # Stored as ISO format string
    citations_count = Column(Integer)
    context_sources = Column(JSON)
    user_comment = Column(Text)

    __table_args__ = (
        Index('idx_feedback_rating_ts', 'rating', 'timestamp'),
        Index('idx_feedback_user', 'user_id'),
    )


class Medication(Base):
    __tablename__ = 'medications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    drug_name = Column(String(255), nullable=False)
    dosage = Column(String(100))
    frequency = Column(String(100))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        Index('idx_medication_user', 'user_id'),
    )


class Feedback(Base):
    """
    New feedback model for the decoupled storage interface.
    """
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_id = Column(String(255), unique=True, nullable=False)
    user_id = Column(String(255), nullable=False)
    query = Column(Text, nullable=False)
    result_id = Column(String(255), nullable=False)
    response_preview = Column(String(500))
    feedback_type = Column(String(50), nullable=False)
    rating = Column(Integer)
    comment = Column(Text)
    metadata_json = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        Index('idx_fb_user_id', 'user_id'),
        Index('idx_fb_result_id', 'result_id'),
        Index('idx_fb_feedback_type', 'feedback_type'),
    )


class UserDevice(Base):
    __tablename__ = 'user_devices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    device_id = Column(String(255), unique=True, nullable=False)
    device_type = Column(String(100))
    registered_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index('idx_user_device_user', 'user_id'),
        Index('idx_user_device_id', 'device_id'),
    )


class DeviceTimeSeries(Base):
    __tablename__ = 'device_timeseries'

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(255), nullable=False)
    metric_type = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    ts = Column(DateTime, nullable=False)
    idempotency_key = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        Index('idx_dt_device', 'device_id'),
        Index('idx_dt_metric', 'metric_type'),
        Index('idx_dt_ts', 'ts'),
        Index('idx_dt_device_ts', 'device_id', 'ts'),
    )