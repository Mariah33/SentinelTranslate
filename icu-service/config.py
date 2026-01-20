"""Configuration for ICU service."""

import os
from typing import Literal, TypeAlias

# Service configuration
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8083"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
WORKERS: int = int(os.getenv("WORKERS", "4"))

# Batch processing limits
MAX_BATCH_SIZE: int = int(os.getenv("MAX_BATCH_SIZE", "1000"))
DEFAULT_BATCH_SIZE: int = int(os.getenv("DEFAULT_BATCH_SIZE", "500"))

# Logging
LogLevel: TypeAlias = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # "json" or "text"
