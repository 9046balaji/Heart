"""
Access log model for health record audit trail.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class HealthRecordAccessLog(Base):
    """SQLAlchemy model for health record access audit trail."""
    
    __tablename__ = "health_record_access_log"
    
    id = Column(Integer, primary_key=True)
    patient_id = Column(String, ForeignKey("health_records.patient_id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    access_type = Column(String)  # "view", "edit", "export"
    accessed_at = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String)
    
    # ✅ Indexed for efficient queries
    __table_args__ = (
        Index('idx_access_log_patient', 'patient_id'),
        Index('idx_access_log_user', 'user_id'),
        Index('idx_access_log_time', 'accessed_at'),
    )
    
    def __repr__(self):
        return f"<HealthRecordAccessLog(id={self.id}, patient_id='{self.patient_id}', user_id='{self.user_id}', access_type='{self.access_type}')>"