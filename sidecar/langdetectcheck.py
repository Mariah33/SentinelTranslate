"""Multi-model language detection via HTTP.

This module provides language detection for hallucination detection by calling
the lang-detect-service microservice via HTTP.

Uses 4 models with weighted consensus for 5-8% higher accuracy than single-model langid.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Language detection service URL
LANG_DETECT_SERVICE_URL = os.environ.get("LANG_DETECT_SERVICE_URL", "http://lang-detect-service:8082")

# HTTP client for language detection service
lang_detect_client = httpx.Client(base_url=LANG_DETECT_SERVICE_URL, timeout=10.0)


def detect_language(text: str, strategy: str = "auto") -> tuple[str, float]:
    """Detect language of text using multi-model weighted consensus.

    Args:
        text: Input text to detect language
        strategy: Detection strategy (auto, short, medium, long, all_models)

    Returns:
        Tuple of (language_code, confidence_score)
        Returns ("unknown", 0.0) if detection fails

    Notes:
        - Calls lang-detect-service /detect endpoint
        - Uses 4 models: lingua-py, fasttext, langid, langdetect
        - Weighted consensus for higher accuracy
        - HTTP timeout is 10 seconds
    """
    if not text or text.strip() == "":
        logger.warning("Empty text provided for language detection")
        return ("unknown", 0.0)

    try:
        response = lang_detect_client.post("/detect", json={"text": text, "strategy": strategy})
        response.raise_for_status()

        data = response.json()
        detected_lang = data["detected_language"]
        confidence = data["confidence"]

        logger.debug(f"Detected language: {detected_lang} (confidence: {confidence:.2f}, strategy: {data['strategy_used']})")

        return (detected_lang, confidence)

    except httpx.HTTPError as e:
        logger.error(f"Failed to detect language from lang-detect-service: {e}")
        return ("unknown", 0.0)
    except Exception as e:
        logger.error(f"Unexpected error calling lang-detect-service: {e}")
        return ("unknown", 0.0)


def validate_language(text: str, expected_lang: str, min_confidence: float = 0.7) -> bool:
    """Validate that detected language matches expected language.

    Args:
        text: Input text to validate
        expected_lang: Expected ISO 639-1 language code (e.g., "en", "fr")
        min_confidence: Minimum confidence threshold (default: 0.7)

    Returns:
        True if detected language matches expected AND confidence >= min_confidence
        False otherwise

    Notes:
        - Uses multi-model weighted consensus for higher accuracy
        - Default confidence threshold of 0.7 filters out uncertain detections
        - Logs warnings when validation fails
    """
    detected_lang, confidence = detect_language(text)

    # Check if detected language matches expected
    if detected_lang != expected_lang:
        logger.warning(f"Language mismatch: expected '{expected_lang}', detected '{detected_lang}' (confidence: {confidence:.2f})")
        return False

    # Check if confidence meets minimum threshold
    if confidence < min_confidence:
        logger.warning(f"Low confidence for language '{detected_lang}': {confidence:.2f} < {min_confidence}")
        return False

    logger.debug(f"Language validation passed: '{expected_lang}' (confidence: {confidence:.2f})")
    return True


def get_service_info() -> dict[str, list[str] | str]:
    """Get language detection service information for monitoring/debugging.

    Returns:
        Dictionary with service information (loaded models, supported languages, etc.)
    """
    try:
        response = lang_detect_client.get("/models-info")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get service info from lang-detect-service: {e}")
        return {"error": str(e)}
