"""
Database package for HeartGuard NLP Service.

Provides:
- Base SQLAlchemy models and configuration
- Database abstraction layer (FeedbackStorage interface)
- Backend-specific implementations (MySQL, PostgreSQL, DynamoDB, SQLite)
- XAMPP MySQL integration for existing deployments
"""

from .storage_interface import (
    FeedbackStorage,
    FeedbackStorageFactory,
    Feedback,
    FeedbackType,
    StorageException,
)
from .postgres_feedback_storage import PostgresFeedbackStorage

__all__ = [
    "FeedbackStorage",
    "FeedbackStorageFactory",
    "Feedback",
    "FeedbackType",
    "StorageException",
    "PostgresFeedbackStorage",
]
