import os

from celery import Celery

# Use environment variables for configuration (with fallback for local dev)
# Worker uses CELERY_* variable names, sidecar uses REDIS_* names
REDIS_BROKER = os.environ.get("CELERY_BROKER_URL") or os.environ.get(
    "REDIS_BROKER", "redis://redis:6379/0"
)
REDIS_BACKEND = os.environ.get("CELERY_RESULT_BACKEND") or os.environ.get(
    "REDIS_BACKEND", "redis://redis:6379/1"
)

celery_app = Celery("translator", broker=REDIS_BROKER, backend=REDIS_BACKEND)
