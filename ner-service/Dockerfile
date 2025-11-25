# Multi-stage build: UV builder + UBI runtime
# Stage 1: UV builder for fast dependency installation
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using UV (frozen lockfile for reproducibility)
RUN uv sync --frozen --no-dev

# Install spaCy models based on MODEL_SET build argument
# Options: full (all 21 models), dev (6 common models), minimal (2 models)
ARG MODEL_SET=dev

RUN if [ "$MODEL_SET" = "full" ]; then \
      uv pip install \
        https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.8.0/zh_core_web_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/hr_core_news_sm-3.8.0/hr_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/da_core_news_sm-3.8.0/da_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/nl_core_news_sm-3.8.0/nl_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/fi_core_news_sm-3.8.0/fi_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/fr_core_news_sm-3.8.0/fr_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.8.0/de_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/el_core_news_sm-3.8.0/el_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/it_core_news_sm-3.8.0/it_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.8.0/ja_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/ko_core_news_sm-3.8.0/ko_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/lt_core_news_sm-3.8.0/lt_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/pl_core_news_sm-3.8.0/pl_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/pt_core_news_sm-3.8.0/pt_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/ro_core_news_sm-3.8.0/ro_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.8.0/ru_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/sl_core_news_sm-3.8.0/sl_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/es_core_news_sm-3.8.0/es_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/sv_core_news_sm-3.8.0/sv_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/uk_core_news_sm-3.8.0/uk_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.8.0/xx_ent_wiki_sm-3.8.0-py3-none-any.whl; \
    elif [ "$MODEL_SET" = "dev" ]; then \
      uv pip install \
        https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/fr_core_news_sm-3.8.0/fr_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.8.0/de_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/es_core_news_sm-3.8.0/es_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.8.0/zh_core_web_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.8.0/xx_ent_wiki_sm-3.8.0-py3-none-any.whl; \
    else \
      uv pip install \
        https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.8.0/xx_ent_wiki_sm-3.8.0-py3-none-any.whl; \
    fi

# Stage 2: UBI runtime (Red Hat Universal Base Image for production)
FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY app.py ./

# Set Python path to use the venv
ENV PYTHONPATH="/app/.venv/lib/python3.11/site-packages:$PYTHONPATH"
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8081

# Run as non-root user (UID 1001 is default in UBI Python images)
USER 1001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3.11 -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/health').read()"

# Use ENTRYPOINT for proper signal handling
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
