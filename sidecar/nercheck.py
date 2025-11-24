"""Multi-language Named Entity Recognition (NER) consistency checking.

This module provides thread-safe multi-language NER entity extraction and consistency
validation for hallucination detection in the SentinelTranslate worker.

Supports 20 languages with native spaCy models plus multilingual fallback for
unsupported languages.
"""

import logging
import os
import threading
from enum import Enum

import spacy
from spacy.language import Language

logger = logging.getLogger(__name__)


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

# Set of supported language codes
SUPPORTED_LANGS = set(LANG_TO_SPACY_MODEL.keys())

# Multilingual fallback model for unsupported languages
FALLBACK_MODEL = "xx_ent_wiki_sm"


class FallbackMode(Enum):
    """Fallback behavior when source language model is unavailable.

    MULTILINGUAL: Use multilingual fallback model (xx_ent_wiki_sm)
    SKIP_SOURCE: Skip source entity extraction, only check target
    STRICT: Fail the check if source language is unsupported
    """

    MULTILINGUAL = "multilingual"
    SKIP_SOURCE = "skip_source"
    STRICT = "strict"


class ModelCache:
    """Thread-safe singleton cache for spaCy NER models.

    Uses lazy loading with double-check locking pattern to load models
    on-demand while ensuring thread safety and preventing redundant loads.
    """

    _instance: "ModelCache | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize instance attributes."""
        self._models: dict[str, Language] = {}
        self._model_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ModelCache":
        """Singleton pattern: ensure only one cache instance exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def get_or_load(self, lang_code: str) -> Language | None:
        """Get cached model or load it lazily.

        Args:
            lang_code: ISO 639-1 language code (e.g., "en", "fr", "zh")

        Returns:
            Loaded spaCy Language model, or None if unavailable

        Raises:
            OSError: If model files are missing (logged but not raised)
        """
        # Fast path: check if already loaded (no lock needed for read)
        if lang_code in self._models:
            return self._models[lang_code]

        # Slow path: acquire lock and load model
        with self._model_lock:
            # Double-check: another thread might have loaded it while we waited
            if lang_code in self._models:
                return self._models[lang_code]

            # Determine which model to load
            model_name = LANG_TO_SPACY_MODEL.get(lang_code, FALLBACK_MODEL)

            try:
                logger.info(f"Loading spaCy model '{model_name}' for language '{lang_code}'")
                model = spacy.load(model_name)
                self._models[lang_code] = model
                logger.info(f"Successfully loaded model '{model_name}'")
                return model
            except OSError as e:
                url = f"https://github.com/explosion/spacy-models/releases/download/{model_name}-3.8.0/{model_name}-3.8.0-py3-none-any.whl"
                logger.error(
                    f"Failed to load spaCy model '{model_name}' for language '{lang_code}': {e}. "
                    + f"Ensure the model is installed via: pip install {url}"
                )
                return None

    def get_stats(self) -> dict[str, list[str] | int]:
        """Get cache statistics for debugging.

        Returns:
            Dictionary with loaded model info
        """
        return {
            "loaded_models": list(self._models.keys()),
            "cache_size": len(self._models),
        }


# Global cache instance
_cache = ModelCache()


def get_fallback_mode() -> FallbackMode:
    """Get fallback mode from environment variable.

    Returns:
        FallbackMode enum value (default: MULTILINGUAL)

    Environment:
        NER_FALLBACK_MODE: "multilingual" | "skip_source" | "strict"
    """
    mode_str = os.getenv("NER_FALLBACK_MODE", "multilingual").lower()
    try:
        return FallbackMode(mode_str)
    except ValueError:
        logger.warning(
            f"Invalid NER_FALLBACK_MODE '{mode_str}', defaulting to MULTILINGUAL. " + "Valid values: multilingual, skip_source, strict"
        )
        return FallbackMode.MULTILINGUAL


def extract_ents(text: str, lang_code: str) -> set[str]:
    """Extract named entities from text using language-specific model.

    Args:
        text: Input text to extract entities from
        lang_code: ISO 639-1 language code (e.g., "en", "fr", "zh")

    Returns:
        Set of entity text strings found in the input

    Notes:
        - Returns empty set if model loading fails
        - Uses fallback model (xx_ent_wiki_sm) for unsupported languages
        - Caches models in global ModelCache for performance
    """
    model = _cache.get_or_load(lang_code)

    if model is None:
        logger.warning(f"No model available for language '{lang_code}', returning empty entity set")
        return set()

    doc = model(text)
    entities = {ent.text for ent in doc.ents}

    if entities:
        logger.debug(f"Extracted {len(entities)} entities from {lang_code} text: {entities}")

    return entities


def ner_consistency(src: str, tgt: str, src_lang: str) -> bool:
    """Check if target translation maintains NER consistency with source.

    Validation logic:
    1. If source has entities but target has none → FAIL
    2. If target has entities not present in source → FAIL
    3. Otherwise → PASS

    Args:
        src: Source text
        tgt: Target (translated) text
        src_lang: ISO 639-1 language code for source

    Returns:
        True if NER consistency check passes, False otherwise

    Notes:
        - Target is always checked with English model (en_core_web_sm)
        - Fallback behavior controlled by NER_FALLBACK_MODE environment variable
        - If source model unavailable, fallback mode determines behavior
    """
    fallback_mode = get_fallback_mode()

    # Extract source entities with fallback handling
    ents_src = extract_ents(src, src_lang)

    # Handle missing source model based on fallback mode
    if src_lang not in SUPPORTED_LANGS and fallback_mode == FallbackMode.STRICT:
        logger.error(f"STRICT mode: Source language '{src_lang}' not supported. " + f"Supported languages: {sorted(SUPPORTED_LANGS)}")
        return False

    if src_lang not in SUPPORTED_LANGS and fallback_mode == FallbackMode.SKIP_SOURCE:
        logger.warning(f"SKIP_SOURCE mode: Skipping NER check for unsupported source language '{src_lang}'")
        return True

    # Extract target entities (always English)
    ents_tgt = extract_ents(tgt, "en")

    # Rule 1: If source has entities but target doesn't, entities were lost
    if ents_src and not ents_tgt:
        logger.warning(
            f"NER consistency failure: Source has {len(ents_src)} entities " + f"but target has none. Source entities: {ents_src}"
        )
        return False

    # Rule 2: If target has entities not in source, entities were fabricated
    fabricated = ents_tgt - ents_src
    if fabricated:
        logger.warning(
            f"NER consistency failure: Target has {len(fabricated)} fabricated entities " + f"not present in source: {fabricated}"
        )
        return False

    # Passed all checks
    logger.debug("NER consistency check passed")
    return True


def preload_models(lang_codes: list[str]) -> None:
    """Preload spaCy models for specified languages (for startup optimization).

    Args:
        lang_codes: List of ISO 639-1 language codes to preload

    Notes:
        - Models are loaded in order specified
        - Failures are logged but do not raise exceptions
        - Useful for container startup to avoid first-request latency
    """
    logger.info(f"Preloading {len(lang_codes)} spaCy models: {lang_codes}")
    for lang_code in lang_codes:
        _cache.get_or_load(lang_code)
    logger.info("Model preloading complete")


def get_cache_stats() -> dict[str, list[str] | int]:
    """Get model cache statistics for monitoring/debugging.

    Returns:
        Dictionary with cache statistics:
        - loaded_models: List of language codes with loaded models
        - cache_size: Number of models in cache
    """
    return _cache.get_stats()
