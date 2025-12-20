"""
ADK Agent Configuration for nlp-service
Includes health data, appointment, and security settings.

Phase 1: Foundation - Configuration template
"""

import os
from typing import Final
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# GOOGLE ADK & AI MODEL SETTINGS
# ============================================================================

GOOGLE_API_KEY: Final[str] = os.getenv("GOOGLE_API_KEY", "")

# ADK Models
ADK_HEALTH_MODEL: Final[str] = os.getenv("ADK_HEALTH_MODEL", "gemini-2.5-pro")
ADK_APPOINTMENT_MODEL: Final[str] = os.getenv(
    "ADK_APPOINTMENT_MODEL", "gemini-2.0-flash"
)
ADK_TEMPERATURE: Final[float] = float(os.getenv("ADK_TEMPERATURE", "0.7"))
ADK_MAX_TOKENS: Final[int] = int(os.getenv("ADK_MAX_TOKENS", "2048"))

# ============================================================================
# HEALTH DATA SETTINGS
# ============================================================================

# Encryption & Security
HEALTH_DATA_ENCRYPTION_KEY: Final[str] = os.getenv(
    "HEALTH_DATA_ENCRYPTION_KEY", "default-dev-key-change-in-production"
)

# HIPAA Compliance
HIPAA_AUDIT_ENABLED: Final[bool] = (
    os.getenv("HIPAA_AUDIT_ENABLED", "true").lower() == "true"
)
PHI_RETENTION_DAYS: Final[int] = int(os.getenv("PHI_RETENTION_DAYS", "2555"))  # 7 years
PHI_ACCESS_LOG_ENABLED: Final[bool] = (
    os.getenv("PHI_ACCESS_LOG_ENABLED", "true").lower() == "true"
)
MINIMUM_NECESSARY_PRINCIPLE: Final[bool] = (
    os.getenv("MINIMUM_NECESSARY_PRINCIPLE", "true").lower() == "true"
)

# Health Data Validation
VITAL_SIGNS_STRICT_VALIDATION: Final[bool] = (
    os.getenv("VITAL_SIGNS_STRICT_VALIDATION", "true").lower() == "true"
)
MEDICATION_DATABASE_ENABLED: Final[bool] = (
    os.getenv("MEDICATION_DATABASE_ENABLED", "false").lower() == "true"
)
ALLERGY_CHECKING_ENABLED: Final[bool] = (
    os.getenv("ALLERGY_CHECKING_ENABLED", "true").lower() == "true"
)

# ============================================================================
# APPOINTMENT SETTINGS
# ============================================================================

# Calendar Integration
CALENDAR_API_KEY: Final[str] = os.getenv("CALENDAR_API_KEY", "")
CALENDAR_SYNC_INTERVAL: Final[int] = int(
    os.getenv("CALENDAR_SYNC_INTERVAL", "300")
)  # 5 minutes
APPOINTMENT_REMINDER_ENABLED: Final[bool] = (
    os.getenv("APPOINTMENT_REMINDER_ENABLED", "true").lower() == "true"
)
APPOINTMENT_REMINDER_MINUTES: Final[int] = int(
    os.getenv("APPOINTMENT_REMINDER_MINUTES", "30")
)

# Appointment Constraints
MAX_APPOINTMENT_DURATION_MINUTES: Final[int] = int(
    os.getenv("MAX_APPOINTMENT_DURATION_MINUTES", "120")
)
MIN_APPOINTMENT_ADVANCE_BOOKING_MINUTES: Final[int] = int(
    os.getenv("MIN_APPOINTMENT_ADVANCE_BOOKING_MINUTES", "15")
)
APPOINTMENT_CANCELLATION_ALLOWED_BEFORE_MINUTES: Final[int] = int(
    os.getenv("APPOINTMENT_CANCELLATION_ALLOWED_BEFORE_MINUTES", "30")
)

# ============================================================================
# DATABASE SETTINGS
# ============================================================================

# Health Data Database
HEALTH_DB_URL: Final[str] = os.getenv(
    "HEALTH_DB_URL", "sqlite:///./health_data.db"  # Default to SQLite for development
)

# Connection Pool
DB_POOL_SIZE: Final[int] = int(os.getenv("DB_POOL_SIZE", "10"))
DB_POOL_RECYCLE: Final[int] = int(os.getenv("DB_POOL_RECYCLE", "3600"))
DB_ECHO: Final[bool] = os.getenv("DB_ECHO", "false").lower() == "true"

# ============================================================================
# SECURITY & AUTHENTICATION
# ============================================================================

# OAuth2 & API Authentication
OAUTH_CLIENT_ID: Final[str] = os.getenv("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET: Final[str] = os.getenv("OAUTH_CLIENT_SECRET", "")
JWT_SECRET_KEY: Final[str] = os.getenv(
    "JWT_SECRET_KEY", "dev-secret-change-in-production"
)
JWT_ALGORITHM: Final[str] = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS: Final[int] = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# API Key
API_KEY: Final[str] = os.getenv("API_KEY", "")
API_KEY_HEADER_NAME: Final[str] = os.getenv("API_KEY_HEADER_NAME", "X-API-Key")

# Rate Limiting
RATE_LIMIT_ENABLED: Final[bool] = (
    os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
)
RATE_LIMIT_REQUESTS_PER_MINUTE: Final[int] = int(
    os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60")
)
RATE_LIMIT_PER_USER: Final[int] = int(os.getenv("RATE_LIMIT_PER_USER", "100"))

# ============================================================================
# NOTIFICATION SETTINGS
# ============================================================================

# Email Notifications
NOTIFICATION_EMAIL_ENABLED: Final[bool] = (
    os.getenv("NOTIFICATION_EMAIL_ENABLED", "false").lower() == "true"
)
NOTIFICATION_EMAIL_FROM: Final[str] = os.getenv(
    "NOTIFICATION_EMAIL_FROM", "noreply@nlp-service.local"
)
SMTP_SERVER: Final[str] = os.getenv("SMTP_SERVER", "localhost")
SMTP_PORT: Final[int] = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME: Final[str] = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD: Final[str] = os.getenv("SMTP_PASSWORD", "")

# SMS Notifications
NOTIFICATION_SMS_ENABLED: Final[bool] = (
    os.getenv("NOTIFICATION_SMS_ENABLED", "false").lower() == "true"
)
NOTIFICATION_SMS_GATEWAY: Final[str] = os.getenv("NOTIFICATION_SMS_GATEWAY", "")
TWILIO_ACCOUNT_SID: Final[str] = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: Final[str] = os.getenv("TWILIO_AUTH_TOKEN", "")

# ============================================================================
# LOGGING & MONITORING
# ============================================================================

LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", "INFO")
AUDIT_LOG_ENABLED: Final[bool] = (
    os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true"
)
AUDIT_LOG_PATH: Final[str] = os.getenv("AUDIT_LOG_PATH", "./logs/audit.log")

# Monitoring
METRICS_ENABLED: Final[bool] = os.getenv("METRICS_ENABLED", "true").lower() == "true"
TRACING_ENABLED: Final[bool] = os.getenv("TRACING_ENABLED", "false").lower() == "true"

# ============================================================================
# SERVICE SETTINGS
# ============================================================================

SERVICE_NAME: Final[str] = os.getenv("SERVICE_NAME", "nlp-service-health")
SERVICE_VERSION: Final[str] = os.getenv("SERVICE_VERSION", "1.0.0")
SERVICE_HOST: Final[str] = os.getenv("SERVICE_HOST", "127.0.0.1")
SERVICE_PORT: Final[int] = int(os.getenv("SERVICE_PORT", "8000"))

# Environment
ENVIRONMENT: Final[str] = os.getenv("ENVIRONMENT", "development")
DEBUG: Final[bool] = os.getenv("DEBUG", "false").lower() == "true"

# ============================================================================
# CORS & EXTERNAL SERVICES
# ============================================================================

CORS_ORIGINS: Final[list] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(
    ","
)
CORS_ALLOW_CREDENTIALS: Final[bool] = (
    os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
)

# External APIs
CALENDAR_API_URL: Final[str] = os.getenv(
    "CALENDAR_API_URL", "https://www.googleapis.com/calendar/v3"
)
NOTIFICATION_SERVICE_URL: Final[str] = os.getenv(
    "NOTIFICATION_SERVICE_URL", "http://localhost:8001"
)

# ============================================================================
# FEATURE FLAGS
# ============================================================================

FEATURE_HEALTH_DATA_COLLECTION: Final[bool] = (
    os.getenv("FEATURE_HEALTH_DATA_COLLECTION", "true").lower() == "true"
)
FEATURE_APPOINTMENT_BOOKING: Final[bool] = (
    os.getenv("FEATURE_APPOINTMENT_BOOKING", "true").lower() == "true"
)
FEATURE_HEALTH_VALIDATION: Final[bool] = (
    os.getenv("FEATURE_HEALTH_VALIDATION", "true").lower() == "true"
)
FEATURE_PHI_ENCRYPTION: Final[bool] = (
    os.getenv("FEATURE_PHI_ENCRYPTION", "true").lower() == "true"
)
FEATURE_SEQUENTIAL_ORCHESTRATION: Final[bool] = (
    os.getenv("FEATURE_SEQUENTIAL_ORCHESTRATION", "true").lower() == "true"
)
