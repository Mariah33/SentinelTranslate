"""Language detection wrapper for backward compatibility.

This module wraps the new langdetectcheck module to maintain backward compatibility
with existing code that imports from language_id.

The actual implementation now uses the lang-detect-service microservice with
multi-model weighted consensus for 5-8% higher accuracy.
"""

from langdetectcheck import detect_language as _detect_language, validate_language as _validate_language


def detect_language(text: str) -> str:
    """Detect language of text (backward compatible interface).

    Args:
        text: Input text

    Returns:
        ISO 639-1 language code (e.g., "en", "fr")
    """
    lang, _ = _detect_language(text)
    return lang


def validate_language(text: str, expected_lang: str) -> bool:
    """Validate text matches expected language (backward compatible interface).

    Args:
        text: Input text
        expected_lang: Expected language code

    Returns:
        True if language matches, False otherwise
    """
    return _validate_language(text, expected_lang)
