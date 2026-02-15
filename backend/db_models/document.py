from sqlalchemy import Column, String, Integer, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)  # From useUserStore
    document_id = Column(String, unique=True, index=True)
    filename = Column(String)
    file_path = Column(String)
    file_size = Column(Integer)
    content_type = Column(String)
    status = Column(String, default="uploaded")  # uploaded, processing, processed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Processed data
    text = Column(Text, nullable=True)
    entities = Column(Text, nullable=True)  # JSON string
    classification = Column(Text, nullable=True)  # JSON string
    confidence = Column(Float, nullable=True)
