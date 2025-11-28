"""Multi-language Named Entity Recognition (NER) consistency checking via HTTP.

This module provides NER entity extraction and consistency validation for hallucination
detection by calling the NER microservice via HTTP.

Supports 20 languages with native spaCy models plus multilingual fallback for
unsupported languages (handled by the NER service).
"""

import logging
import os
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

# NER service URL
NER_SERVICE_URL = os.environ.get("NER_SERVICE_URL", "http://ner-service:8081")

# HTTP client for NER service
ner_client = httpx.Client(base_url=NER_SERVICE_URL, timeout=30.0)

# Supported language codes (same as NER service)
SUPPORTED_LANGS = {
    "zh",
    "hr",
    "da",
    "nl",
    "fi",
    "fr",
    "de",
    "el",
    "it",
    "ja",
    "ko",
    "lt",
    "pl",
    "pt",
    "ro",
    "ru",
    "sl",
    "es",
    "sv",
    "uk",
    "en",
}


class FallbackMode(Enum):
    """Fallback behavior when source language model is unavailable.

    MULTILINGUAL: Use multilingual fallback model (xx_ent_wiki_sm)
    SKIP_SOURCE: Skip source entity extraction, only check target
    STRICT: Fail the check if source language is unsupported
    """

    MULTILINGUAL = "multilingual"
    SKIP_SOURCE = "skip_source"
    STRICT = "strict"


def get_fallback_mode() -> FallbackMode:
    """Get NER fallback mode from environment variable.

    Returns:
        FallbackMode enum value

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
    """Extract named entities from text by calling NER microservice.

    Args:
        text: Input text to extract entities from
        lang_code: ISO 639-1 language code (e.g., "en", "fr", "zh")

    Returns:
        Set of entity text strings found in the input

    Notes:
        - Returns empty set if HTTP request fails
        - NER service handles fallback model for unsupported languages
        - HTTP timeout is 30 seconds
    """
    if not text or text.strip() == "":
        return set()

    try:
        response = ner_client.post("/extract-entities", json={"text": text, "lang_code": lang_code})
        response.raise_for_status()

        data = response.json()
        entities = set(data["entities"])

        if entities:
            logger.debug(f"Extracted {len(entities)} entities from {lang_code} text: {entities}")

        return entities

    except httpx.HTTPError as e:
        logger.error(f"Failed to extract entities from NER service: {e}")
        return set()
    except Exception as e:
        logger.error(f"Unexpected error calling NER service: {e}")
        return set()


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
        - Target is always checked with English (en)
        - Fallback behavior controlled by NER_FALLBACK_MODE environment variable
        - If source model unavailable, fallback mode determines behavior
    """
    fallback_mode = get_fallback_mode()

    # Extract source entities
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


def get_cache_stats() -> dict[str, list[str] | int]:
    """Get NER service cache statistics for monitoring/debugging.

    Returns:
        Dictionary with cache statistics from NER service
    """
    try:
        response = ner_client.get("/cache-stats")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get cache stats from NER service: {e}")
        return {"loaded_models": [], "cache_size": 0}
