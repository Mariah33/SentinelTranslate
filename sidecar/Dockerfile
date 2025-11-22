# Stage 1: UV installer - install dependencies from lock file
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: UBI runtime - minimal production image
FROM registry.access.redhat.com/ubi9/python-311:latest
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Use the virtual environment packages with system python
ENV PYTHONPATH="/app/.venv/lib/python3.11/site-packages:$PYTHONPATH"

# Expose FastAPI port
EXPOSE 8080

# Run as non-root
USER 1001

ENTRYPOINT ["python3.11", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
