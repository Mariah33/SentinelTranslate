"""ICU operations module with thread-safe caching.

Provides text transformation operations using the PyICU library:
- Transliteration (e.g., Latin-Katakana, Any-Latin)
- Unicode normalization (NFC, NFD, NFKC, NFKD)
- Custom transforms (compound ICU transform specs)
- Locale-aware case mapping

Uses singleton cache with double-check locking for thread safety.
"""

import logging
import threading
from datetime import datetime
from typing import Any

import icu

from models import CaseOperation, NormalizationForm

logger = logging.getLogger(__name__)


class ICUCache:
    """Thread-safe singleton cache for ICU transliterators.

    Lazy-loads and caches transliterators to minimize memory and initialization overhead.
    Tracks cache hits, misses, and per-transform statistics.
    """

    _instance: "ICUCache | None" = None
    _initialized: bool = False
    _lock = threading.Lock()

    def __new__(cls) -> "ICUCache":
        """Ensure singleton instance with double-check locking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize cache (only once)."""
        if not ICUCache._initialized:
            self._transliterators: dict[str, icu.Transliterator] = {}
            self._transform_stats: dict[str, dict[str, Any]] = {}
            self._total_requests: int = 0
            self._cache_hits: int = 0
            self._cache_misses: int = 0
            ICUCache._initialized = True
            logger.info("ICUCache initialized (0MB at startup)")

    def get_transliterator(self, transform_id: str, reverse: bool = False) -> icu.Transliterator:
        """Get cached transliterator or create and cache it.

        Args:
            transform_id: ICU transform ID (e.g., 'Latin-Katakana', 'Any-Latin')
            reverse: Whether to get the reverse transform

        Returns:
            ICU Transliterator instance

        Raises:
            ValueError: If transform_id is invalid or not supported
        """
        cache_key = f"{transform_id}::{'reverse' if reverse else 'forward'}"

        with self._lock:
            self._total_requests += 1

            if cache_key in self._transliterators:
                self._cache_hits += 1
                self._update_transform_stats(cache_key, hit=True)
                return self._transliterators[cache_key]

            # Cache miss - create new transliterator
            self._cache_misses += 1
            try:
                logger.info(f"Creating transliterator: {cache_key}")
                if reverse:
                    transliterator = icu.Transliterator.createInstance(transform_id, icu.UTransDirection.REVERSE)
                else:
                    transliterator = icu.Transliterator.createInstance(transform_id, icu.UTransDirection.FORWARD)

                self._transliterators[cache_key] = transliterator
                self._update_transform_stats(cache_key, hit=False)
                logger.info(f"Successfully cached transliterator: {cache_key}")
                return transliterator

            except icu.ICUError as e:
                logger.error(f"Failed to create transliterator '{transform_id}': {e}")
                raise ValueError(f"Invalid or unsupported transform ID: {transform_id}") from e

    def _update_transform_stats(self, cache_key: str, hit: bool) -> None:
        """Update per-transform statistics.

        Args:
            cache_key: Transform cache key
            hit: Whether this was a cache hit
        """
        if cache_key not in self._transform_stats:
            self._transform_stats[cache_key] = {
                "created_at": datetime.utcnow().isoformat(),
                "hits": 0,
                "total_requests": 0,
            }

        stats = self._transform_stats[cache_key]
        stats["total_requests"] += 1
        if hit:
            stats["hits"] += 1
        stats["last_used"] = datetime.utcnow().isoformat()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics including hits, misses, and cached transforms
        """
        with self._lock:
            cache_hit_rate = self._cache_hits / self._total_requests if self._total_requests > 0 else 0.0

            return {
                "cached_transforms": list(self._transliterators.keys()),
                "total_cached": len(self._transliterators),
                "total_requests": self._total_requests,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "cache_hit_rate": cache_hit_rate,
                "transform_stats": self._transform_stats,
            }

    def clear(self) -> None:
        """Clear cache (for testing)."""
        with self._lock:
            self._transliterators.clear()
            self._transform_stats.clear()
            self._total_requests = 0
            self._cache_hits = 0
            self._cache_misses = 0
            logger.info("Cache cleared")


# Global cache singleton
_cache = ICUCache()


def transliterate_batch(texts: list[str], transform_id: str, reverse: bool = False) -> list[str]:
    """Batch transliterate texts using ICU.

    Args:
        texts: List of texts to transliterate
        transform_id: ICU transform ID (e.g., 'Latin-Katakana', 'Any-Latin')
        reverse: Whether to apply reverse transformation

    Returns:
        List of transliterated texts

    Raises:
        ValueError: If transform_id is invalid
    """
    transliterator = _cache.get_transliterator(transform_id, reverse)

    results = []
    for text in texts:
        try:
            result = transliterator.transliterate(text)
            results.append(result)
        except Exception as e:
            logger.error(f"Transliteration failed for text '{text[:50]}...': {e}")
            raise ValueError(f"Transliteration failed: {e}") from e

    logger.debug(f"Transliterated {len(texts)} texts using {transform_id} (reverse={reverse})")
    return results


def normalize_batch(texts: list[str], form: NormalizationForm) -> list[str]:
    """Batch normalize texts using Unicode normalization.

    Args:
        texts: List of texts to normalize
        form: Normalization form (NFC, NFD, NFKC, NFKD)

    Returns:
        List of normalized texts

    Raises:
        ValueError: If normalization fails
    """
    # Map NormalizationForm enum to ICU Normalizer2 modes
    normalizer_map = {
        NormalizationForm.NFC: icu.Normalizer2.getNFCInstance(),
        NormalizationForm.NFD: icu.Normalizer2.getNFDInstance(),
        NormalizationForm.NFKC: icu.Normalizer2.getNFKCInstance(),
        NormalizationForm.NFKD: icu.Normalizer2.getNFKDInstance(),
    }

    normalizer = normalizer_map[form]

    results = []
    for text in texts:
        try:
            result = normalizer.normalize(text)
            results.append(result)
        except Exception as e:
            logger.error(f"Normalization failed for text '{text[:50]}...': {e}")
            raise ValueError(f"Normalization failed: {e}") from e

    logger.debug(f"Normalized {len(texts)} texts using {form.value}")
    return results


def transform_batch(texts: list[str], transform_spec: str) -> list[str]:
    """Batch transform texts using custom ICU transform specification.

    Transform specs can be compound (e.g., '::NFD; ::[:Nonspacing Mark:] Remove; ::NFC;')

    Args:
        texts: List of texts to transform
        transform_spec: ICU transform specification string

    Returns:
        List of transformed texts

    Raises:
        ValueError: If transform_spec is invalid
    """
    try:
        # Create transliterator from transform specification
        transliterator = icu.Transliterator.createFromRules("custom", transform_spec, icu.UTransDirection.FORWARD)
    except icu.ICUError as e:
        logger.error(f"Failed to create transliterator from spec '{transform_spec}': {e}")
        raise ValueError(f"Invalid transform specification: {transform_spec}") from e

    results = []
    for text in texts:
        try:
            result = transliterator.transliterate(text)
            results.append(result)
        except Exception as e:
            logger.error(f"Transform failed for text '{text[:50]}...': {e}")
            raise ValueError(f"Transform failed: {e}") from e

    logger.debug(f"Transformed {len(texts)} texts using custom spec")
    return results


def case_mapping_batch(texts: list[str], operation: CaseOperation, locale: str = "en") -> list[str]:
    """Batch case mapping with locale awareness.

    Args:
        texts: List of texts to transform
        operation: Case operation (upper, lower, title)
        locale: Locale for case mapping (e.g., 'en', 'tr', 'de')

    Returns:
        List of case-mapped texts

    Raises:
        ValueError: If operation fails
    """
    # Create locale object
    try:
        icu_locale = icu.Locale(locale)
    except Exception as e:
        logger.warning(f"Invalid locale '{locale}', falling back to 'en': {e}")
        icu_locale = icu.Locale("en")

    results = []
    for text in texts:
        try:
            # Create UnicodeString for locale-aware operations
            utext = icu.UnicodeString(text)

            if operation == CaseOperation.UPPER:
                result = utext.toUpper(icu_locale)
            elif operation == CaseOperation.LOWER:
                result = utext.toLower(icu_locale)
            elif operation == CaseOperation.TITLE:
                result = utext.toTitle(icu_locale)
            else:
                raise ValueError(f"Unknown case operation: {operation}")

            results.append(str(result))
        except Exception as e:
            logger.error(f"Case mapping failed for text '{text[:50]}...': {e}")
            raise ValueError(f"Case mapping failed: {e}") from e

    logger.debug(f"Applied {operation.value} case mapping to {len(texts)} texts (locale={locale})")
    return results


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    return _cache.get_stats()


def get_supported_operations() -> dict[str, Any]:
    """Get list of supported operations and examples.

    Returns:
        Dictionary with supported operations and examples
    """
    return {
        "transliterations": [
            "Latin-Katakana",
            "Latin-Hiragana",
            "Latin-Cyrillic",
            "Latin-Greek",
            "Latin-Arabic",
            "Latin-Hebrew",
            "Any-Latin",
            "Cyrillic-Latin",
            "Greek-Latin",
            "Arabic-Latin",
            "Hebrew-Latin",
            "Han-Latin",
            "Hangul-Latin",
        ],
        "normalizations": ["NFC", "NFD", "NFKC", "NFKD"],
        "case_operations": ["upper", "lower", "title"],
        "example_transforms": {
            "ascii_folding": "::Latin-ASCII;",
            "remove_accents": "::NFD; ::[:Nonspacing Mark:] Remove; ::NFC;",
            "remove_diacritics": "::NFD; ::[:M:] Remove; ::NFC;",
            "lowercase_ascii": "::Latin-ASCII; ::Lower;",
            "halfwidth_to_fullwidth": "::Halfwidth-Fullwidth;",
            "fullwidth_to_halfwidth": "::Fullwidth-Halfwidth;",
        },
        "icu_version": icu.ICU_VERSION,
        "unicode_version": icu.UNICODE_VERSION,
    }


def get_icu_version() -> str:
    """Get ICU library version.

    Returns:
        ICU version string
    """
    return icu.ICU_VERSION
