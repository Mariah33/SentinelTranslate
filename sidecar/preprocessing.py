"""Text preprocessing with state-of-the-art sentence boundary detection.

Uses wtpsplit (Where's the Point?) for multilingual SBD:
- Trained on 85 languages
- Handles complex punctuation, URLs, abbreviations
- Neural model with 98%+ accuracy
"""

import logging
import re

from wtpsplit import SaT

logger = logging.getLogger(__name__)

# Singleton SaT model (loaded once at startup)
_sat_model = None


def get_sat_model() -> SaT:
    """Get or initialize the SaT sentence splitter model.

    Returns:
        SaT model instance (cached after first call)
    """
    global _sat_model
    if _sat_model is None:
        logger.info("Loading wtpsplit SaT-3l model...")
        _sat_model = SaT("sat-3l")
        logger.info("✓ wtpsplit model loaded successfully")
    return _sat_model


def normalize(text: str) -> str:
    """Normalize text by cleaning whitespace and standardizing quotes.

    Args:
        text: Input text to normalize

    Returns:
        Normalized text
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    # Normalize single quotes (curly quotes to straight)
    text = text.replace("'", "'").replace("'", "'")
    # Normalize double quotes (curly quotes to straight)
    text = text.replace(""", '"').replace(""", '"')
    return text


def sentence_split(text: str, lang_code: str = "en") -> list[str]:
    """Split text into sentences using wtpsplit neural model.

    Args:
        text: Text to split
        lang_code: ISO 639-1 language code (e.g., "fr", "de", "zh")
                   Helps the model optimize for language-specific patterns

    Returns:
        List of sentence strings

    Notes:
        - First call loads the model (~50MB, takes 2-3 seconds)
        - Subsequent calls are fast (~10ms per 1000 chars)
        - Supports 85+ languages out of the box
    """
    if not text or text.strip() == "":
        return []

    model = get_sat_model()

    # wtpsplit returns list of sentences
    sentences = model.split(text, lang_code=lang_code)

    return [s.strip() for s in sentences if s.strip()]


def preprocess(text: str, lang_code: str = "en") -> list[str]:
    """Preprocess text: normalize and split into sentences.

    Args:
        text: Input text
        lang_code: Source language code for optimal SBD

    Returns:
        List of normalized sentences
    """
    text = normalize(text)
    return sentence_split(text, lang_code=lang_code)
