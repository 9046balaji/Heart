"""
Device registration model for smartwatch ownership validation.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class UserDevice(Base):
    """SQLAlchemy model for user device registration and ownership tracking."""

    __tablename__ = "user_devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String, unique=True, nullable=False, index=True)
    device_type = Column(String)  # "apple_watch", "fitbit", "garmin", etc.
    registered_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<UserDevice(id={self.id}, user_id='{self.user_id}', device_id='{self.device_id}')>"
