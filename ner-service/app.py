"""NER Microservice for multi-language named entity recognition.

Provides HTTP endpoints for extracting named entities from text in 20+ languages.
Supports both spaCy (20 languages) and Stanza (60+ languages) frameworks.
Uses lazy loading and thread-safe caching for optimal memory usage.
"""

import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any

import spacy
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from spacy.language import Language

# Try to import Stanza (optional dependency)
STANZA_AVAILABLE = False
stanza = None  # type: ignore[assignment]

try:
    import stanza

    STANZA_AVAILABLE = True  # noqa: F841
except ImportError:
    pass

logger = logging.getLogger(__name__)

app = FastAPI(title="NER Service", version="1.0.0")


# Language code to spaCy model name mapping (20 supported languages - LARGE models)
LANG_TO_SPACY_MODEL = {
    "zh": "zh_core_web_lg",
    "hr": "hr_core_news_lg",
    "da": "da_core_news_lg",
    "nl": "nl_core_news_lg",
    "fi": "fi_core_news_lg",
    "fr": "fr_core_news_lg",
    "de": "de_core_news_lg",
    "el": "el_core_news_lg",
    "it": "it_core_news_lg",
    "ja": "ja_core_news_lg",
    "ko": "ko_core_news_lg",
    "lt": "lt_core_news_lg",
    "pl": "pl_core_news_lg",
    "pt": "pt_core_news_lg",
    "ro": "ro_core_news_lg",
    "ru": "ru_core_news_lg",
    "sl": "sl_core_news_lg",
    "es": "es_core_news_lg",
    "sv": "sv_core_news_lg",
    "uk": "uk_core_news_lg",
    "en": "en_core_web_lg",
}

SUPPORTED_LANGS = set(LANG_TO_SPACY_MODEL.keys())
FALLBACK_MODEL = "xx_ent_wiki_sm"  # Note: multilingual model only available in sm size

# Stanza supported languages (60+ languages)
STANZA_SUPPORTED_LANGS = {
    "af",
    "ar",
    "be",
    "bg",
    "ca",
    "zh",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "et",
    "fi",
    "fr",
    "de",
    "el",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "la",
    "lv",
    "lt",
    "no",
    "fa",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "es",
    "sv",
    "ta",
    "te",
    "th",
    "tr",
    "uk",
    "ur",
    "vi",
    "eu",
    "hy",
    "ga",
    "is",
    "kk",
    "kmr",
    "ky",
    "mr",
    "my",
    "nn",
    "nb",
    "sa",
    "sr",
    "wo",
    "cy",
    "gd",
    "gl",
    "mt",
}


class FallbackMode(str, Enum):
    """Fallback behavior for unsupported languages."""

    MULTILINGUAL = "multilingual"
    STRICT = "strict"


class NERFramework(str, Enum):
    """NER framework selection."""

    SPACY = "spacy"
    STANZA = "stanza"
    BOTH = "both"  # Try spaCy first, fall back to Stanza


class ModelCache:
    """Thread-safe singleton cache for spaCy and Stanza NER models.

    Supports dual-framework operation with lazy loading for optimal memory usage.
    spaCy models: 0MB at startup → ~150-200MB per large model
    Stanza pipelines: 0MB at startup → ~20-50MB per language
    """

    _instance = None
    _models: dict[str, Language] = {}
    _stanza_pipelines: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_or_load(self, lang_code: str) -> Language | None:
        """Get cached spaCy model or load it lazily from volume path.

        Models are expected to be mounted at SPACY_MODEL_PATH.
        This supports the new volume-mounted architecture where models are not
        included in the container but mounted at runtime.

        Args:
            lang_code: ISO 639-1 language code (e.g., 'en', 'fr')

        Returns:
            spaCy Language model or None if loading fails
        """
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

            # Try to load from volume-mounted path first
            spacy_model_path = os.getenv("SPACY_MODEL_PATH", "/app/models/spacy")
            model_dir = Path(spacy_model_path) / model_name

            if model_dir.exists():
                logger.info(f"Loading model from volume path: {model_dir}")
                model = spacy.load(str(model_dir))
            else:
                logger.info(f"Volume path {model_dir} not found, attempting standard load")
                model = spacy.load(model_name)

            self._models[lang_code] = model
            logger.info(f"Successfully loaded model {model_name}")
            return model
        except OSError as e:
            logger.error(f"Failed to load spaCy model {model_name}: {e}")
            return None

    def get_or_load_stanza(self, lang_code: str) -> Any | None:
        """Get cached Stanza pipeline or load it lazily from volume path.

        Models are expected to be mounted at STANZA_MODEL_PATH.
        This supports the new volume-mounted architecture where models are not
        included in the container but mounted at runtime.

        IMPORTANT: Models MUST be downloaded and mounted at runtime.
        This method will NOT download models (for air-gapped environments).

        Args:
            lang_code: ISO 639-1 language code (e.g., 'en', 'fr')

        Returns:
            Stanza Pipeline object or None if loading fails or Stanza unavailable
        """
        if not STANZA_AVAILABLE:
            logger.warning("Stanza is not installed, cannot load pipeline")
            return None

        if lang_code in self._stanza_pipelines:
            return self._stanza_pipelines[lang_code]

        if lang_code not in STANZA_SUPPORTED_LANGS:
            logger.warning(f"Language '{lang_code}' not supported by Stanza")
            return None

        # Get Stanza models directory from environment or use default
        stanza_model_path = os.getenv("STANZA_MODEL_PATH", "/app/models/stanza")
        stanza_dir = Path(stanza_model_path)

        try:
            logger.info(f"Loading Stanza pipeline for language: {lang_code} from {stanza_dir}")

            # Load pipeline (expects models to be pre-downloaded and volume-mounted)
            # download_method=None explicitly disables auto-download behavior
            pipeline = stanza.Pipeline(  # type: ignore[union-attr]
                lang_code,
                dir=str(stanza_dir),
                processors="tokenize,ner",
                logging_level="WARNING",
                download_method=None,  # Disable auto-download for air-gapped environments
            )

            self._stanza_pipelines[lang_code] = pipeline
            logger.info(f"Successfully loaded Stanza pipeline for {lang_code}")
            return pipeline

        except Exception as e:
            # Model not found - log error but do NOT try to download
            logger.error(
                f"Failed to load Stanza model for '{lang_code}' from {stanza_model_path}. "
                f"Models must be downloaded and mounted via volume. "
                f"Use: python download_all_models.py --output-dir <volume-path>. "
                f"Error: {e}"
            )
            return None

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics for both frameworks.

        Returns:
            Dictionary with loaded models/pipelines and cache sizes
        """
        return {
            "spacy_loaded_models": list(self._models.keys()),
            "spacy_cache_size": len(self._models),
            "stanza_loaded_models": list(self._stanza_pipelines.keys()),
            "stanza_cache_size": len(self._stanza_pipelines),
            "total_cache_size": len(self._models) + len(self._stanza_pipelines),
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
    framework_used: str  # "spacy" or "stanza"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    spacy_loaded_models: int
    stanza_loaded_models: int
    total_loaded_models: int
    supported_languages: int
    stanza_available: bool


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""

    spacy_loaded_models: list[str]
    spacy_cache_size: int
    stanza_loaded_models: list[str]
    stanza_cache_size: int
    total_cache_size: int


class FrameworksResponse(BaseModel):
    """Framework availability response."""

    stanza_available: bool
    spacy_available: bool
    current_framework: str
    spacy_supported_languages: int
    stanza_supported_languages: int


# API Endpoints
@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint with framework statistics."""
    stats = _cache.get_stats()
    return HealthResponse(
        status="healthy",
        spacy_loaded_models=stats["spacy_cache_size"],
        stanza_loaded_models=stats["stanza_cache_size"],
        total_loaded_models=stats["total_cache_size"],
        supported_languages=len(SUPPORTED_LANGS),
        stanza_available=STANZA_AVAILABLE,
    )


@app.get("/cache-stats", response_model=CacheStatsResponse)
def cache_stats():
    """Get cache statistics for both frameworks."""
    stats = _cache.get_stats()
    return CacheStatsResponse(
        spacy_loaded_models=stats["spacy_loaded_models"],
        spacy_cache_size=stats["spacy_cache_size"],
        stanza_loaded_models=stats["stanza_loaded_models"],
        stanza_cache_size=stats["stanza_cache_size"],
        total_cache_size=stats["total_cache_size"],
    )


@app.get("/supported-languages")
def supported_languages():
    """Get list of supported language codes for both frameworks."""
    return {
        "spacy_supported": sorted(SUPPORTED_LANGS),
        "spacy_total": len(SUPPORTED_LANGS),
        "stanza_supported": sorted(STANZA_SUPPORTED_LANGS) if STANZA_AVAILABLE else [],
        "stanza_total": len(STANZA_SUPPORTED_LANGS) if STANZA_AVAILABLE else 0,
        "fallback_available": True,
    }


@app.get("/frameworks", response_model=FrameworksResponse)
def frameworks():
    """Get framework availability and configuration."""
    framework_str = os.getenv("NER_FRAMEWORK", "both").lower()
    try:
        current_framework = NERFramework(framework_str)
    except ValueError:
        current_framework = NERFramework.BOTH

    return FrameworksResponse(
        stanza_available=STANZA_AVAILABLE,
        spacy_available=True,  # spaCy is always available
        current_framework=current_framework.value,
        spacy_supported_languages=len(SUPPORTED_LANGS),
        stanza_supported_languages=len(STANZA_SUPPORTED_LANGS),
    )


@app.post("/extract-entities", response_model=ExtractResponse)
def extract_entities(request: ExtractRequest):
    """Extract named entities from text using spaCy or Stanza.

    Supports dual-framework operation:
    - NER_FRAMEWORK=spacy: Use spaCy only
    - NER_FRAMEWORK=stanza: Use Stanza only
    - NER_FRAMEWORK=both (default): Try spaCy first, fall back to Stanza

    Args:
        request: ExtractRequest with text and lang_code

    Returns:
        ExtractResponse with entities, model name, and framework used

    Raises:
        HTTPException: If model loading fails or language is unsupported in strict mode
    """
    text = request.text
    lang_code = request.lang_code

    # Get configuration from environment
    fallback_mode_str = os.getenv("NER_FALLBACK_MODE", "multilingual").lower()
    try:
        fallback_mode = FallbackMode(fallback_mode_str)
    except ValueError:
        fallback_mode = FallbackMode.MULTILINGUAL

    framework_str = os.getenv("NER_FRAMEWORK", "both").lower()
    try:
        framework = NERFramework(framework_str)
    except ValueError:
        framework = NERFramework.BOTH

    # Handle empty text early
    if not text or text.strip() == "":
        return ExtractResponse(
            entities=[], lang_code=lang_code, model_used="none", framework_used="none"
        )

    # Try spaCy first (if allowed by framework setting)
    if framework in (NERFramework.SPACY, NERFramework.BOTH):
        if lang_code in SUPPORTED_LANGS or fallback_mode == FallbackMode.MULTILINGUAL:
            model = _cache.get_or_load(lang_code)
            if model is not None:
                # Successfully loaded spaCy model
                model_name = LANG_TO_SPACY_MODEL.get(lang_code, FALLBACK_MODEL)
                doc = model(text)
                entities = [ent.text for ent in doc.ents]

                logger.debug(
                    f"Extracted {len(entities)} entities from {lang_code} text using spaCy"
                )

                return ExtractResponse(
                    entities=entities,
                    lang_code=lang_code,
                    model_used=model_name,
                    framework_used="spacy",
                )
            else:
                logger.warning(f"spaCy model failed to load for {lang_code}")

    # Try Stanza if spaCy failed or framework is stanza/both
    if framework in (NERFramework.STANZA, NERFramework.BOTH):
        if STANZA_AVAILABLE and lang_code in STANZA_SUPPORTED_LANGS:
            pipeline = _cache.get_or_load_stanza(lang_code)
            if pipeline is not None:
                # Successfully loaded Stanza pipeline
                doc = pipeline(text)  # type: ignore[misc]
                entities = [ent.text for ent in doc.entities]  # type: ignore[union-attr]

                logger.debug(
                    f"Extracted {len(entities)} entities from {lang_code} text using Stanza"
                )

                return ExtractResponse(
                    entities=entities,
                    lang_code=lang_code,
                    model_used=f"stanza-{lang_code}",
                    framework_used="stanza",
                )
            else:
                logger.warning(f"Stanza pipeline failed to load for {lang_code}")
        elif not STANZA_AVAILABLE:
            logger.warning("Stanza is not available but was requested")

    # If we get here, both frameworks failed or language is unsupported
    if fallback_mode == FallbackMode.STRICT:
        stanza_langs = sorted(STANZA_SUPPORTED_LANGS) if STANZA_AVAILABLE else "N/A"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Language '{lang_code}' not supported in STRICT mode. "
                f"spaCy languages: {sorted(SUPPORTED_LANGS)}, "
                f"Stanza languages: {stanza_langs}"
            ),
        )

    # Last resort: try spaCy fallback model
    model = _cache.get_or_load(lang_code)
    if model is None:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load any NER model for language: {lang_code}",
        )

    model_name = FALLBACK_MODEL
    doc = model(text)
    entities = [ent.text for ent in doc.ents]

    logger.info(f"Using fallback model {FALLBACK_MODEL} for {lang_code}")

    return ExtractResponse(
        entities=entities,
        lang_code=lang_code,
        model_used=model_name,
        framework_used="spacy-fallback",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
