"""Language code mapping between ISO 639-1 and FLORES-200 codes.

FLORES-200 codes used by NLLB-200 model include script information (e.g., Latn, Cyrl, Arab).
ISO 639-1 codes are simpler 2-letter codes without script info.

This module provides bidirectional mapping for translation services.
"""

# ISO 639-1 to FLORES-200 mapping for NLLB-200 model
# Covers 41 languages supported by OPUS-MT plus additional common languages
ISO_TO_FLORES = {
    # European languages (Latin script)
    "en": "eng_Latn",  # English
    "fr": "fra_Latn",  # French
    "de": "deu_Latn",  # German
    "es": "spa_Latn",  # Spanish
    "pt": "por_Latn",  # Portuguese
    "it": "ita_Latn",  # Italian
    "nl": "nld_Latn",  # Dutch
    "pl": "pol_Latn",  # Polish
    "ro": "ron_Latn",  # Romanian
    "cs": "ces_Latn",  # Czech
    "da": "dan_Latn",  # Danish
    "fi": "fin_Latn",  # Finnish
    "sv": "swe_Latn",  # Swedish
    "no": "nob_Latn",  # Norwegian (Bokmål)
    "hu": "hun_Latn",  # Hungarian
    "et": "est_Latn",  # Estonian
    "lv": "lvs_Latn",  # Latvian (Standard)
    "lt": "lit_Latn",  # Lithuanian
    "hr": "hrv_Latn",  # Croatian
    "sl": "slv_Latn",  # Slovenian
    "sk": "slk_Latn",  # Slovak
    # European languages (non-Latin scripts)
    "el": "ell_Grek",  # Greek
    "ru": "rus_Cyrl",  # Russian
    "uk": "ukr_Cyrl",  # Ukrainian
    "bg": "bul_Cyrl",  # Bulgarian
    "sr": "srp_Cyrl",  # Serbian
    # Asian languages
    "zh": "zho_Hans",  # Chinese (Simplified) - default for "zh"
    "zh-CN": "zho_Hans",  # Chinese (Simplified) - explicit
    "zh-TW": "zho_Hant",  # Chinese (Traditional)
    "ja": "jpn_Jpan",  # Japanese
    "ko": "kor_Hang",  # Korean
    "vi": "vie_Latn",  # Vietnamese
    "th": "tha_Thai",  # Thai
    "id": "ind_Latn",  # Indonesian
    "ms": "zsm_Latn",  # Malay (Standard)
    "bn": "ben_Beng",  # Bengali
    "hi": "hin_Deva",  # Hindi
    "ta": "tam_Taml",  # Tamil
    "te": "tel_Telu",  # Telugu
    # Middle Eastern languages
    "ar": "arb_Arab",  # Arabic (Standard)
    "he": "heb_Hebr",  # Hebrew
    "fa": "pes_Arab",  # Persian (Farsi)
    "tr": "tur_Latn",  # Turkish
    "ur": "urd_Arab",  # Urdu
}

# Reverse mapping: FLORES-200 to ISO 639-1
# For cases where we need to convert back
FLORES_TO_ISO = {v: k for k, v in ISO_TO_FLORES.items() if "-" not in k}  # Exclude variant codes like zh-CN

# Supported OPUS-MT languages (for reference)
OPUS_MT_LANGUAGES = {
    "ar",
    "bg",
    "bn",
    "cs",
    "da",
    "de",
    "el",
    "es",
    "et",
    "fa",
    "fi",
    "fr",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "lt",
    "lv",
    "ms",
    "nl",
    "no",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "sr",
    "sv",
    "ta",
    "te",
    "th",
    "tr",
    "uk",
    "ur",
    "vi",
    "zh",
}


def iso_to_flores(iso_code: str) -> str:
    """Convert ISO 639-1 language code to FLORES-200 format.

    Args:
        iso_code: ISO 639-1 2-letter language code (e.g., "fr", "zh")

    Returns:
        FLORES-200 code with script (e.g., "fra_Latn", "zho_Hans")

    Raises:
        ValueError: If language code is not supported
    """
    if iso_code not in ISO_TO_FLORES:
        raise ValueError(
            f"Unsupported language code: {iso_code}. Supported codes: {sorted(set(ISO_TO_FLORES.keys()) - {'zh-CN', 'zh-TW'})}"
        )
    return ISO_TO_FLORES[iso_code]


def flores_to_iso(flores_code: str) -> str:
    """Convert FLORES-200 code back to ISO 639-1 format.

    Args:
        flores_code: FLORES-200 code (e.g., "fra_Latn", "zho_Hans")

    Returns:
        ISO 639-1 2-letter code (e.g., "fr", "zh")

    Raises:
        ValueError: If FLORES code is not in mapping
    """
    if flores_code not in FLORES_TO_ISO:
        raise ValueError(f"Unsupported FLORES-200 code: {flores_code}. Supported codes: {sorted(FLORES_TO_ISO.keys())}")
    return FLORES_TO_ISO[flores_code]


def is_opus_mt_supported(iso_code: str) -> bool:
    """Check if language is supported by OPUS-MT models.

    Args:
        iso_code: ISO 639-1 language code

    Returns:
        True if OPUS-MT model exists for this language
    """
    return iso_code in OPUS_MT_LANGUAGES


def is_nllb_supported(iso_code: str) -> bool:
    """Check if language is supported by NLLB-200 model.

    Args:
        iso_code: ISO 639-1 language code

    Returns:
        True if NLLB-200 supports this language
    """
    return iso_code in ISO_TO_FLORES
