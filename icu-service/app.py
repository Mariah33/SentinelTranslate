"""ICU Microservice for text normalization, transliteration, and transformation.

Provides HTTP endpoints for ICU operations on text:
- Transliteration (e.g., Latin-Katakana, Any-Latin)
- Unicode normalization (NFC, NFD, NFKC, NFKD)
- Custom transforms (compound ICU specs)
- Locale-aware case mapping

Uses lazy loading and thread-safe caching for optimal performance.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

import config
import icu_operations
from models import (
    CaseMappingRequest,
    CaseMappingResponse,
    HealthResponse,
    NormalizeRequest,
    NormalizeResponse,
    SupportedOperationsResponse,
    TransformRequest,
    TransformResponse,
    TransliterateRequest,
    TransliterateResponse,
)

# Configure logging
log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Service startup time
_startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Lifespan event handler for startup and shutdown."""
    # Startup
    icu_version = icu_operations.get_icu_version()
    logger.info(f"ICU Service starting with ICU version {icu_version}")
    logger.info(f"Service running on {config.HOST}:{config.PORT}")
    logger.info(f"Log level: {config.LOG_LEVEL}")
    yield
    # Shutdown
    logger.info("ICU Service shutting down")


# FastAPI app
app = FastAPI(
    title="ICU Service",
    description="Text normalization, transliteration, and transformation service",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics instrumentation
Instrumentator().instrument(app).expose(app)


@app.post("/transliterate", response_model=TransliterateResponse)
async def transliterate(request: TransliterateRequest) -> TransliterateResponse:
    """Transliterate texts using ICU transform ID.

    Args:
        request: TransliterateRequest with texts, transform_id, and reverse flag

    Returns:
        TransliterateResponse with transliterated texts

    Raises:
        HTTPException: If transform_id is invalid or transliteration fails
    """
    # Validate batch size
    if len(request.texts) > config.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size {len(request.texts)} exceeds maximum of {config.MAX_BATCH_SIZE}",
        )

    try:
        results = icu_operations.transliterate_batch(request.texts, request.transform_id, request.reverse)

        return TransliterateResponse(
            results=results,
            transform_id=request.transform_id,
            reverse=request.reverse,
            count=len(results),
        )
    except ValueError as e:
        logger.error(f"Transliteration error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error during transliteration: {e}")
        raise HTTPException(status_code=500, detail=f"Transliteration failed: {e}") from e


@app.post("/normalize", response_model=NormalizeResponse)
async def normalize(request: NormalizeRequest) -> NormalizeResponse:
    """Normalize texts using Unicode normalization form.

    Args:
        request: NormalizeRequest with texts and normalization form

    Returns:
        NormalizeResponse with normalized texts

    Raises:
        HTTPException: If normalization fails
    """
    # Validate batch size
    if len(request.texts) > config.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size {len(request.texts)} exceeds maximum of {config.MAX_BATCH_SIZE}",
        )

    try:
        results = icu_operations.normalize_batch(request.texts, request.form)

        return NormalizeResponse(
            results=results,
            form=request.form.value,
            count=len(results),
        )
    except ValueError as e:
        logger.error(f"Normalization error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error during normalization: {e}")
        raise HTTPException(status_code=500, detail=f"Normalization failed: {e}") from e


@app.post("/transform", response_model=TransformResponse)
async def transform(request: TransformRequest) -> TransformResponse:
    """Apply custom ICU transform specification to texts.

    Args:
        request: TransformRequest with texts and transform specification

    Returns:
        TransformResponse with transformed texts

    Raises:
        HTTPException: If transform specification is invalid or transform fails
    """
    # Validate batch size
    if len(request.texts) > config.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size {len(request.texts)} exceeds maximum of {config.MAX_BATCH_SIZE}",
        )

    try:
        results = icu_operations.transform_batch(request.texts, request.transform_spec)

        return TransformResponse(
            results=results,
            transform_spec=request.transform_spec,
            count=len(results),
        )
    except ValueError as e:
        logger.error(f"Transform error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error during transform: {e}")
        raise HTTPException(status_code=500, detail=f"Transform failed: {e}") from e


@app.post("/case-mapping", response_model=CaseMappingResponse)
async def case_mapping(request: CaseMappingRequest) -> CaseMappingResponse:
    """Apply locale-aware case mapping to texts.

    Args:
        request: CaseMappingRequest with texts, operation, and locale

    Returns:
        CaseMappingResponse with case-mapped texts

    Raises:
        HTTPException: If case mapping fails
    """
    # Validate batch size
    if len(request.texts) > config.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size {len(request.texts)} exceeds maximum of {config.MAX_BATCH_SIZE}",
        )

    try:
        results = icu_operations.case_mapping_batch(request.texts, request.operation, request.locale)

        return CaseMappingResponse(
            results=results,
            operation=request.operation.value,
            locale=request.locale,
            count=len(results),
        )
    except ValueError as e:
        logger.error(f"Case mapping error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error during case mapping: {e}")
        raise HTTPException(status_code=500, detail=f"Case mapping failed: {e}") from e


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint with ICU version and cache statistics.

    Returns:
        HealthResponse with service status and metadata
    """
    cache_stats = icu_operations.get_cache_stats()
    uptime_seconds = time.time() - _startup_time

    return HealthResponse(
        status="healthy",
        icu_version=icu_operations.get_icu_version(),
        cache_size=cache_stats["total_cached"],
        uptime_seconds=uptime_seconds,
    )


@app.get("/supported-operations", response_model=SupportedOperationsResponse)
async def supported_operations() -> SupportedOperationsResponse:
    """Get list of supported operations and examples.

    Returns:
        SupportedOperationsResponse with available operations and examples
    """
    ops = icu_operations.get_supported_operations()

    return SupportedOperationsResponse(
        transliterations=ops["transliterations"],
        normalizations=ops["normalizations"],
        case_operations=ops["case_operations"],
        example_transforms=ops["example_transforms"],
    )


@app.get("/cache-stats")
async def cache_stats() -> dict[str, Any]:
    """Get cache statistics.

    Returns:
        Cache statistics including hits, misses, and cached transforms
    """
    return icu_operations.get_cache_stats()


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Any, exc: ValueError) -> dict[str, Any]:
    """Handle ValueError exceptions with 400 status code.

    Args:
        request: FastAPI request object
        exc: ValueError exception

    Returns:
        Error response with 400 status code
    """
    logger.error(f"ValueError: {exc}")
    return {
        "detail": str(exc),
        "error_code": "INVALID_INPUT",
    }


@app.exception_handler(Exception)
async def general_exception_handler(request: Any, exc: Exception) -> dict[str, Any]:
    """Handle general exceptions with 500 status code.

    Args:
        request: FastAPI request object
        exc: Exception

    Returns:
        Error response with 500 status code
    """
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return {
        "detail": f"Internal server error: {exc}",
        "error_code": "INTERNAL_ERROR",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
