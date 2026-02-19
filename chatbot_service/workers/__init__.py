"""
Workers Package

This package contains ARQ worker configurations and background task workers:

- arq_settings.py: ARQ Worker Configuration for async task processing
- session_archiver.py: Background worker for HIPAA-compliant session archiving
- retry_scheduler.py: Worker for scheduled job retries

Usage:
    # Start ARQ worker
    arq workers.arq_settings.WorkerSettings

    # Start session archiver
    python -m workers.session_archiver

    # Start retry scheduler
    python -m workers.retry_scheduler
"""
