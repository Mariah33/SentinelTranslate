# Multi-stage build for lang-detect-service
# Stage 1: UV builder for fast dependency installation
# Stage 2: UBI runtime for production security/support

# ============================================================================
# Stage 1: UV Builder - Install dependencies with UV
# ============================================================================
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using UV (frozen lock for reproducibility)
RUN uv sync --frozen --no-dev

# Download language detection models
COPY download_models.py ./
RUN uv run python download_models.py

# ============================================================================
# Stage 2: UBI Runtime - Production image with Red Hat UBI
# ============================================================================
FROM registry.access.redhat.com/ubi9/python-311:latest

# Set environment variables
ENV LANG_DETECT_MODEL_PATH=/app/models/lang-detect \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=1001:0 /app/.venv /app/.venv

# Copy models from builder
COPY --from=builder --chown=1001:0 /app/models /app/models

# Copy application code
COPY --chown=1001:0 app.py ./

# Expose port 8082
EXPOSE 8082

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8082/health || exit 1

# Run as non-root user (UID 1001)
USER 1001

# Use ENTRYPOINT for proper signal handling
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8082"]
