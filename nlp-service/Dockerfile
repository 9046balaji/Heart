# ============================================================================
# Multi-Stage Dockerfile for NLP Service
#
# Features:
# - Multi-stage build for smaller final image
# - Non-root user for security
# - Layer caching optimization
# - Health check instruction
# - Security hardening
# ============================================================================

# ==================================
# Stage 1: Builder
# ==================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# ==================================
# Stage 2: Runtime
# ==================================
FROM python:3.11-slim AS runtime

# Labels
LABEL maintainer="Healthcare Chatbot Team"
LABEL description="NLP Service for Cardio AI Assistant"
LABEL version="1.0.0"

# Security: Create non-root user
RUN groupadd --gid 1000 nlpservice && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home nlpservice

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=nlpservice:nlpservice . .

# Create necessary directories
RUN mkdir -p /app/logs /app/cache /app/tokens && \
    chown -R nlpservice:nlpservice /app

# Security: Remove unnecessary files
RUN rm -rf tests/ *.md .git .gitignore __pycache__ .pytest_cache .env.example

# Switch to non-root user
USER nlpservice

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NLP_SERVICE_PORT=5001 \
    NLP_SERVICE_HOST=0.0.0.0

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Run application
CMD ["python", "main.py"]
