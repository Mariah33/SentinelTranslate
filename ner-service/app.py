"""NER Microservice for multi-language named entity recognition.

Provides HTTP endpoints for extracting named entities from text in 20+ languages.
Uses spaCy models with lazy loading and thread-safe caching.
"""

import logging
import os
from enum import Enum

import spacy
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from spacy.language import Language

logger = logging.getLogger(__name__)

app = FastAPI(title="NER Service", version="1.0.0")


# Language code to spaCy model name mapping (20 supported languages)
LANG_TO_SPACY_MODEL = {
    "zh": "zh_core_web_sm",
    "hr": "hr_core_news_sm",
    "da": "da_core_news_sm",
    "nl": "nl_core_news_sm",
    "fi": "fi_core_news_sm",
    "fr": "fr_core_news_sm",
    "de": "de_core_news_sm",
    "el": "el_core_news_sm",
    "it": "it_core_news_sm",
    "ja": "ja_core_news_sm",
    "ko": "ko_core_news_sm",
    "lt": "lt_core_news_sm",
    "pl": "pl_core_news_sm",
    "pt": "pt_core_news_sm",
    "ro": "ro_core_news_sm",
    "ru": "ru_core_news_sm",
    "sl": "sl_core_news_sm",
    "es": "es_core_news_sm",
    "sv": "sv_core_news_sm",
    "uk": "uk_core_news_sm",
    "en": "en_core_web_sm",
}

SUPPORTED_LANGS = set(LANG_TO_SPACY_MODEL.keys())
FALLBACK_MODEL = "xx_ent_wiki_sm"


class FallbackMode(str, Enum):
    """Fallback behavior for unsupported languages."""

    MULTILINGUAL = "multilingual"
    STRICT = "strict"


class ModelCache:
    """Thread-safe singleton cache for spaCy NER models."""

    _instance = None
    _models: dict[str, Language] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_or_load(self, lang_code: str) -> Language | None:
        """Get cached model or load it lazily."""
        if lang_code in self._models:
            return self._models[lang_code]

        # Determine which model to load
        if lang_code in LANG_TO_SPACY_MODEL:
            model_name = LANG_TO_SPACY_MODEL[lang_code]
        else:
            # Use fallback for unsupported languages
            model_name = FALLBACK_MODEL
            logger.info(
                f"Using fallback model {FALLBACK_MODEL} for unsupported language: {lang_code}"
            )

        try:
            logger.info(f"Loading spaCy model: {model_name} for language: {lang_code}")
            model = spacy.load(model_name)
            self._models[lang_code] = model
            logger.info(f"Successfully loaded model {model_name}")
            return model
        except OSError as e:
            logger.error(f"Failed to load spaCy model {model_name}: {e}")
            return None

    def get_stats(self) -> dict[str, list[str] | int]:
        """Get cache statistics."""
        return {
            "loaded_models": list(self._models.keys()),
            "cache_size": len(self._models),
        }


# Global model cache
_cache = ModelCache()


# Request/Response models
class ExtractRequest(BaseModel):
    """Request model for entity extraction."""

    text: str
    lang_code: str


class ExtractResponse(BaseModel):
    """Response model for entity extraction."""

    entities: list[str]
    lang_code: str
    model_used: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    loaded_models: int
    supported_languages: int


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""

    loaded_models: list[str]
    cache_size: int


# API Endpoints
@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    stats = _cache.get_stats()
    return HealthResponse(
        status="healthy",
        loaded_models=stats["cache_size"],
        supported_languages=len(SUPPORTED_LANGS),
    )


@app.get("/cache-stats", response_model=CacheStatsResponse)
def cache_stats():
    """Get cache statistics."""
    stats = _cache.get_stats()
    return CacheStatsResponse(
        loaded_models=stats["loaded_models"],
        cache_size=stats["cache_size"],
    )


@app.get("/supported-languages")
def supported_languages():
    """Get list of supported language codes."""
    return {
        "supported": sorted(SUPPORTED_LANGS),
        "total": len(SUPPORTED_LANGS),
        "fallback_available": True,
    }


@app.post("/extract-entities", response_model=ExtractResponse)
def extract_entities(request: ExtractRequest):
    """Extract named entities from text.

    Args:
        request: ExtractRequest with text and lang_code

    Returns:
        ExtractResponse with list of entity strings

    Raises:
        HTTPException: If model loading fails or language is unsupported in strict mode
    """
    text = request.text
    lang_code = request.lang_code

    # Get fallback mode from environment
    fallback_mode_str = os.getenv("NER_FALLBACK_MODE", "multilingual").lower()
    try:
        fallback_mode = FallbackMode(fallback_mode_str)
    except ValueError:
        fallback_mode = FallbackMode.MULTILINGUAL

    # Check if language is supported
    if lang_code not in SUPPORTED_LANGS:
        if fallback_mode == FallbackMode.STRICT:
            raise HTTPException(
                status_code=400,
                detail=f"Language '{lang_code}' not supported in STRICT mode. Supported languages: {sorted(SUPPORTED_LANGS)}",
            )
        logger.info(f"Using fallback model for unsupported language: {lang_code}")

    # Load model
    model = _cache.get_or_load(lang_code)
    if model is None:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load model for language: {lang_code}",
        )

    # Determine model name used
    model_name = LANG_TO_SPACY_MODEL.get(lang_code, FALLBACK_MODEL)

    # Extract entities
    if not text or text.strip() == "":
        return ExtractResponse(entities=[], lang_code=lang_code, model_used=model_name)

    doc = model(text)
    entities = [ent.text for ent in doc.ents]

    logger.debug(f"Extracted {len(entities)} entities from {lang_code} text")

    return ExtractResponse(
        entities=entities,
        lang_code=lang_code,
        model_used=model_name,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
