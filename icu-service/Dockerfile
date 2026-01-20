# Multi-stage build: UV builder + UBI runtime
# ICU Service: Text transliteration and normalization microservice
#
# Stage 1: UV builder for fast dependency installation
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /build

# Install ICU development libraries required for PyICU compilation
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libicu-dev \
        pkg-config \
        gcc \
        g++ \
        make \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using UV (frozen lockfile for reproducibility)
# This includes PyICU which will be compiled against libicu-dev
RUN uv sync --frozen --no-dev

# Verify PyICU installation and ICU version
RUN .venv/bin/python -c "import icu; print(f'PyICU installed successfully. ICU version: {icu.ICU_VERSION}')"

# ============================================================================
# Stage 2: UBI Runtime - Production image with Red Hat UBI
# ============================================================================
FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /app

# Install ICU runtime libraries (much smaller than development libraries)
USER root
RUN dnf install -y --nodocs libicu && \
    dnf clean all && \
    rm -rf /var/cache/dnf /var/lib/dnf/history*

# Copy virtual environment from builder
COPY --from=builder --chown=1001:0 /build/.venv /app/.venv

# Copy application code
COPY --chown=1001:0 app.py icu_operations.py models.py config.py ./

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    LOG_LEVEL="INFO"

# Expose port 8083
EXPOSE 8083

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8083/health || exit 1

# Run as non-root user (UID 1001)
USER 1001

# Use ENTRYPOINT for proper signal handling
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8083"]
