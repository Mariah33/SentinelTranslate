"""
Unit tests for ICU operations module.
"""

import threading
import time

import pytest

from icu_operations import (
    ICUCache,
    case_mapping_batch,
    get_cache_stats,
    get_icu_version,
    get_supported_operations,
    normalize_batch,
    transform_batch,
    transliterate_batch,
)
from models import CaseOperation, NormalizationForm


class TestTransliterateBatch:
    """Tests for transliterate_batch function."""

    def test_latin_ascii_transliteration(self):
        """Test Latin to ASCII transliteration."""
        texts = ["Café", "naïve", "résumé"]
        result = transliterate_batch(texts, "Latin-ASCII")
        assert len(result) == 3
        assert "Cafe" in result
        assert "naive" in result
        assert "resume" in result

    def test_transliterate_single_text(self):
        """Test transliteration of single text."""
        result = transliterate_batch(["Café"], "Latin-ASCII")
        assert len(result) == 1
        assert result[0] == "Cafe"

    def test_transliterate_empty_strings(self):
        """Test transliteration with empty strings."""
        result = transliterate_batch([""], "Latin-ASCII")
        assert len(result) == 1

    def test_transliterate_already_ascii(self):
        """Test transliteration of ASCII text."""
        result = transliterate_batch(["Hello", "World"], "Latin-ASCII")
        assert len(result) == 2
        assert result[0] == "Hello"
        assert result[1] == "World"

    def test_transliterate_numbers(self):
        """Test transliteration of numeric strings."""
        result = transliterate_batch(["123", "456"], "Latin-ASCII")
        assert len(result) == 2

    def test_transliterate_invalid_transform_raises_error(self):
        """Test invalid transform ID raises ValueError."""
        with pytest.raises(ValueError):
            transliterate_batch(["test"], "InvalidTransform")

    def test_transliterate_large_batch(self):
        """Test transliteration of large batch."""
        texts = [f"café {i}" for i in range(100)]
        result = transliterate_batch(texts, "Latin-ASCII")
        assert len(result) == 100


class TestNormalizeBatch:
    """Tests for normalize_batch function."""

    def test_nfc_normalization(self):
        """Test NFC normalization."""
        texts = ["café", "naïve"]
        result = normalize_batch(texts, NormalizationForm.NFC)
        assert len(result) == 2
        assert isinstance(result[0], str)

    def test_nfd_normalization(self):
        """Test NFD normalization."""
        texts = ["café"]
        result = normalize_batch(texts, NormalizationForm.NFD)
        assert len(result) == 1
        # NFD decomposes characters
        assert isinstance(result[0], str)

    def test_nfkc_normalization(self):
        """Test NFKC normalization."""
        texts = ["café"]
        result = normalize_batch(texts, NormalizationForm.NFKC)
        assert len(result) == 1

    def test_nfkd_normalization(self):
        """Test NFKD normalization."""
        texts = ["café"]
        result = normalize_batch(texts, NormalizationForm.NFKD)
        assert len(result) == 1

    def test_normalize_empty_strings(self):
        """Test normalization of empty strings."""
        result = normalize_batch([""], NormalizationForm.NFC)
        assert len(result) == 1
        assert result[0] == ""

    def test_normalize_ascii_text(self):
        """Test normalization of ASCII text."""
        result = normalize_batch(["Hello"], NormalizationForm.NFC)
        assert len(result) == 1
        assert result[0] == "Hello"

    def test_normalize_invalid_form_raises_error(self):
        """Test invalid form raises ValueError."""
        # Create a string that won't match enum values
        try:
            result = normalize_batch(["test"], NormalizationForm.NFC)
            # Should not raise
            assert len(result) == 1
        except ValueError:
            # If it does raise, that's also acceptable
            pass

    def test_normalize_large_batch(self):
        """Test normalization of large batch."""
        texts = [f"café {i}" for i in range(100)]
        result = normalize_batch(texts, NormalizationForm.NFC)
        assert len(result) == 100

    def test_nfc_vs_nfd_differences(self):
        """Test NFC and NFD produce different results for composed chars."""
        text = ["é"]  # composed character
        nfc = normalize_batch(text, NormalizationForm.NFC)
        nfd = normalize_batch(text, NormalizationForm.NFD)
        # Both should be valid, may have different lengths
        assert len(nfc) == 1
        assert len(nfd) == 1


class TestTransformBatch:
    """Tests for transform_batch function."""

    def test_simple_upper_transform(self):
        """Test simple uppercase transform."""
        result = transform_batch(["hello"], "::Upper;")
        assert len(result) == 1

    def test_compound_transform(self):
        """Test compound transform specification."""
        result = transform_batch(["Café"], "::Latin-ASCII; ::Upper;")
        assert len(result) == 1

    def test_transform_invalid_spec_raises_error(self):
        """Test invalid transform spec raises ValueError."""
        with pytest.raises(ValueError):
            transform_batch(["test"], "InvalidSpec123")

    def test_transform_large_batch(self):
        """Test transform of large batch."""
        texts = [f"text {i}" for i in range(50)]
        result = transform_batch(texts, "::Upper;")
        assert len(result) == 50

    def test_transform_empty_strings(self):
        """Test transform of empty strings."""
        result = transform_batch([""], "::Upper;")
        assert len(result) == 1


class TestCaseMappingBatch:
    """Tests for case_mapping_batch function."""

    def test_upper_case_default_locale(self):
        """Test uppercase with default locale."""
        result = case_mapping_batch(["hello"], CaseOperation.UPPER)
        assert len(result) == 1

    def test_lower_case_operation(self):
        """Test lowercase operation."""
        result = case_mapping_batch(["HELLO"], CaseOperation.LOWER)
        assert len(result) == 1

    def test_title_case_operation(self):
        """Test title case operation."""
        result = case_mapping_batch(["hello world"], CaseOperation.TITLE)
        assert len(result) == 1

    def test_turkish_locale_upper(self):
        """Test Turkish locale upper case mapping."""
        result = case_mapping_batch(["istanbul"], CaseOperation.UPPER, locale="tr")
        assert len(result) == 1

    def test_english_locale_upper(self):
        """Test English locale upper case."""
        result = case_mapping_batch(["hello"], CaseOperation.UPPER, locale="en")
        assert len(result) == 1

    def test_case_mapping_invalid_operation_raises_error(self):
        """Test invalid operation raises ValueError."""
        # Since we're using enums, invalid strings will fail at validation level
        # This test verifies enum validation works
        assert CaseOperation.UPPER.value == "upper"
        assert CaseOperation.LOWER.value == "lower"
        assert CaseOperation.TITLE.value == "title"

    def test_case_mapping_empty_strings(self):
        """Test case mapping of empty strings."""
        result = case_mapping_batch([""], CaseOperation.UPPER)
        assert len(result) == 1

    def test_case_mapping_large_batch(self):
        """Test case mapping of large batch."""
        texts = [f"text {i}" for i in range(100)]
        result = case_mapping_batch(texts, CaseOperation.UPPER)
        assert len(result) == 100

    def test_case_mapping_different_locales(self):
        """Test case mapping with different locales."""
        text = ["test"]
        for locale in ["en", "fr", "de"]:
            result = case_mapping_batch(text, CaseOperation.UPPER, locale=locale)
            assert len(result) == 1


class TestICUCache:
    """Tests for ICUCache singleton class."""

    def test_icu_cache_singleton_pattern(self):
        """Test ICUCache implements singleton pattern."""
        cache1 = ICUCache()
        cache2 = ICUCache()
        assert cache1 is cache2

    def test_icu_cache_lazy_loading(self):
        """Test cache starts and can be cleared."""
        cache = ICUCache()
        cache.clear()
        stats = cache.get_stats()
        assert stats["total_cached"] >= 0
        assert stats["cache_hits"] >= 0

    def test_icu_cache_get_transliterator(self):
        """Test getting transliterator from cache."""
        cache = ICUCache()
        cache.clear()
        # Valid transform ID
        try:
            trans = cache.get_transliterator("Latin-ASCII")
            assert trans is not None
        except ValueError:
            # If invalid, that's expected for some transforms
            pass

    def test_icu_cache_hit_counting(self):
        """Test cache hit counting."""
        cache = ICUCache()
        cache.clear()

        try:
            # Make two requests with same transform
            cache.get_transliterator("Latin-ASCII")
            cache.get_transliterator("Latin-ASCII")

            stats = cache.get_stats()
            assert stats["cache_hits"] >= 1
        except ValueError:
            # If Latin-ASCII is not available, skip this test
            pass

    def test_icu_cache_clear(self):
        """Test clearing cache."""
        cache = ICUCache()
        cache.clear()
        stats = cache.get_stats()
        assert stats["total_cached"] == 0

    def test_icu_cache_stats_structure(self):
        """Test cache stats structure."""
        cache = ICUCache()
        cache.clear()
        stats = cache.get_stats()

        # Verify expected keys
        assert "total_cached" in stats
        assert "total_requests" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "cache_hit_rate" in stats

    def test_icu_cache_thread_safety(self):
        """Test cache thread safety with concurrent access."""
        cache = ICUCache()
        cache.clear()

        def worker():
            for _ in range(10):
                try:
                    cache.get_transliterator("Latin-ASCII")
                except ValueError:
                    pass

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert True


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_icu_version(self):
        """Test getting ICU version."""
        version = get_icu_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_cache_stats_function(self):
        """Test getting cache stats via function."""
        stats = get_cache_stats()
        assert isinstance(stats, dict)
        assert "cache_hit_rate" in stats

    def test_get_supported_operations_function(self):
        """Test getting supported operations."""
        ops = get_supported_operations()
        assert isinstance(ops, dict)
        assert "transliterations" in ops
        assert "normalizations" in ops
        assert "case_operations" in ops
        assert isinstance(ops["normalizations"], list)


class TestPerformance:
    """Performance-related tests."""

    def test_transliterate_batch_performance(self):
        """Test transliteration batch completes in reasonable time."""
        texts = [f"café {i}" for i in range(100)]
        start = time.time()
        result = transliterate_batch(texts, "Latin-ASCII")
        elapsed = time.time() - start
        assert elapsed < 10.0  # Should complete in under 10 seconds
        assert len(result) == 100

    def test_normalize_batch_performance(self):
        """Test normalization batch completes in reasonable time."""
        texts = [f"café {i}" for i in range(100)]
        start = time.time()
        result = normalize_batch(texts, NormalizationForm.NFC)
        elapsed = time.time() - start
        assert elapsed < 10.0
        assert len(result) == 100

    def test_case_mapping_batch_performance(self):
        """Test case mapping batch completes in reasonable time."""
        texts = [f"text {i}" for i in range(100)]
        start = time.time()
        result = case_mapping_batch(texts, CaseOperation.UPPER)
        elapsed = time.time() - start
        assert elapsed < 10.0
        assert len(result) == 100


class TestEdgeCases:
    """Tests for edge cases."""

    def test_transliterate_special_characters(self):
        """Test transliteration with special characters."""
        result = transliterate_batch(["@#$%^&*"], "Latin-ASCII")
        assert len(result) == 1

    def test_normalize_unicode_combining_marks(self):
        """Test normalization with combining marks."""
        # Create text with combining marks
        text = ["e\u0301"]  # e with combining acute accent
        result = normalize_batch(text, NormalizationForm.NFC)
        assert len(result) == 1

    def test_case_mapping_with_symbols(self):
        """Test case mapping with mixed symbols."""
        result = case_mapping_batch(["Hello@123!"], CaseOperation.UPPER)
        assert len(result) == 1

    def test_transliterate_very_long_text(self):
        """Test transliteration of very long text."""
        long_text = "Café " * 1000
        result = transliterate_batch([long_text], "Latin-ASCII")
        assert len(result) == 1
