# Stage 1: UV installer - install dependencies from lock file
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
RUN uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# Stage 2: UBI runtime - minimal production image
FROM registry.access.redhat.com/ubi9/python-311:latest
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Use the virtual environment packages with system python
ENV PYTHONPATH="/app/.venv/lib/python3.11/site-packages:$PYTHONPATH"

# Run as non-root
USER 1001

ENTRYPOINT ["python3.11", "-m", "celery", "-A", "celery_app", "worker", "--loglevel=INFO"]
