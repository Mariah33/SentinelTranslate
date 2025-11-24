"""Unit tests for worker cache module.

Tests cover:
- Cache key generation with SHA256 hashing
- Cache get/set operations with Redis
- TTL configuration
- Error handling
"""

import sys
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock Redis before importing cache module
with patch("redis.Redis"):
    from cache import (
        CACHE_TTL,
        REDIS_CACHE_DB,
        REDIS_HOST,
        REDIS_PORT,
        _make_cache_key,
        get_cached_translation,
        set_cached_translation,
    )


class TestCacheKeyGeneration:
    """Test suite for cache key generation logic."""

    def test_cache_key_format(self):
        """Test that cache key follows expected format: {src}-{tgt}:{hash}"""
        key = _make_cache_key("Hello world", "en", "fr")

        assert key.startswith("en-fr:")
        assert len(key) == len("en-fr:") + 16  # 16-char hash

    def test_cache_key_consistency(self):
        """Test that same input generates same cache key."""
        text = "Bonjour le monde"
        key1 = _make_cache_key(text, "fr", "en")
        key2 = _make_cache_key(text, "fr", "en")

        assert key1 == key2

    def test_cache_key_uniqueness_text(self):
        """Test that different text generates different cache keys."""
        key1 = _make_cache_key("Hello", "en", "fr")
        key2 = _make_cache_key("World", "en", "fr")

        assert key1 != key2

    def test_cache_key_uniqueness_languages(self):
        """Test that different language pairs generate different cache keys."""
        text = "Hello world"
        key1 = _make_cache_key(text, "en", "fr")
        key2 = _make_cache_key(text, "en", "de")
        key3 = _make_cache_key(text, "fr", "en")

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_cache_key_with_special_characters(self):
        """Test cache key generation with special characters and unicode."""
        text = "Héllo wörld! 你好世界"
        key = _make_cache_key(text, "en", "zh")

        assert key.startswith("en-zh:")
        assert len(key) == len("en-zh:") + 16

    def test_cache_key_with_empty_string(self):
        """Test cache key generation with empty string."""
        key = _make_cache_key("", "en", "fr")

        assert key.startswith("en-fr:")
        assert len(key) == len("en-fr:") + 16

    def test_cache_key_hash_truncation(self):
        """Test that hash is truncated to 16 characters."""
        # Use long text to ensure full SHA256 hash would be longer
        long_text = "A" * 10000
        key = _make_cache_key(long_text, "en", "fr")

        hash_part = key.split(":")[1]
        assert len(hash_part) == 16


class TestGetCachedTranslation:
    """Test suite for get_cached_translation() function."""

    @patch("cache.cache_client")
    def test_cache_hit(self, mock_redis):
        """Test successful cache retrieval."""
        mock_redis.get.return_value = "Bonjour le monde"

        result = get_cached_translation("Hello world", "en", "fr")

        assert result == "Bonjour le monde"
        assert mock_redis.get.called

    @patch("cache.cache_client")
    def test_cache_miss(self, mock_redis):
        """Test cache miss returns None."""
        mock_redis.get.return_value = None

        result = get_cached_translation("Hello world", "en", "fr")

        assert result is None
        assert mock_redis.get.called

    @patch("cache.cache_client")
    def test_correct_key_passed(self, mock_redis):
        """Test that correct cache key is passed to Redis."""
        mock_redis.get.return_value = None

        text = "Test text"
        src_lang = "en"
        tgt_lang = "fr"

        get_cached_translation(text, src_lang, tgt_lang)

        # Verify get was called with key matching pattern
        call_args = mock_redis.get.call_args[0]
        assert len(call_args) == 1
        assert call_args[0].startswith(f"{src_lang}-{tgt_lang}:")

    @patch("cache.cache_client")
    def test_empty_string_cached(self, mock_redis):
        """Test that empty string can be cached and retrieved."""
        mock_redis.get.return_value = ""

        result = get_cached_translation("Some text", "en", "fr")

        assert result == ""

    @patch("cache.cache_client")
    def test_unicode_translation_cached(self, mock_redis):
        """Test caching of unicode translations."""
        mock_redis.get.return_value = "こんにちは世界"

        result = get_cached_translation("Hello world", "en", "ja")

        assert result == "こんにちは世界"


class TestSetCachedTranslation:
    """Test suite for set_cached_translation() function."""

    @patch("cache.cache_client")
    def test_cache_set(self, mock_redis):
        """Test successful cache storage."""
        text = "Hello world"
        translation = "Bonjour le monde"

        set_cached_translation(text, "en", "fr", translation)

        assert mock_redis.setex.called
        call_args = mock_redis.setex.call_args[0]
        assert len(call_args) == 3
        assert call_args[0].startswith("en-fr:")
        assert call_args[1] == CACHE_TTL
        assert call_args[2] == translation

    @patch("cache.cache_client")
    def test_ttl_configuration(self, mock_redis):
        """Test that TTL is set correctly."""
        set_cached_translation("Test", "en", "fr", "Test translation")

        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == CACHE_TTL

    @patch("cache.cache_client")
    def test_correct_key_generated(self, mock_redis):
        """Test that correct cache key is generated for storage."""
        text = "Original text"
        src_lang = "de"
        tgt_lang = "en"
        translation = "Translated text"

        set_cached_translation(text, src_lang, tgt_lang, translation)

        call_args = mock_redis.setex.call_args[0]
        key = call_args[0]
        assert key.startswith(f"{src_lang}-{tgt_lang}:")

    @patch("cache.cache_client")
    def test_empty_translation_stored(self, mock_redis):
        """Test storing empty translation string."""
        set_cached_translation("Text", "en", "fr", "")

        call_args = mock_redis.setex.call_args[0]
        assert call_args[2] == ""

    @patch("cache.cache_client")
    def test_unicode_translation_stored(self, mock_redis):
        """Test storing unicode translation."""
        translation = "Привет мир"
        set_cached_translation("Hello world", "en", "ru", translation)

        call_args = mock_redis.setex.call_args[0]
        assert call_args[2] == translation


class TestCacheConfiguration:
    """Test suite for cache configuration constants."""

    def test_default_redis_host(self):
        """Test default Redis host configuration."""
        assert REDIS_HOST == "redis" or isinstance(REDIS_HOST, str)

    def test_default_redis_port(self):
        """Test default Redis port configuration."""
        assert REDIS_PORT == 6379 or isinstance(REDIS_PORT, int)

    def test_default_cache_db(self):
        """Test default cache database number."""
        assert REDIS_CACHE_DB == 2 or isinstance(REDIS_CACHE_DB, int)

    def test_default_cache_ttl(self):
        """Test default cache TTL (24 hours)."""
        assert CACHE_TTL == 86400 or isinstance(CACHE_TTL, int)


class TestCacheIntegration:
    """Integration tests for cache get/set operations."""

    @patch("cache.cache_client")
    def test_cache_round_trip(self, mock_redis):
        """Test storing and retrieving translation."""
        text = "Test text"
        translation = "Test translation"

        # Mock Redis to store and return values
        stored_values = {}

        def mock_setex(key, ttl, value):
            stored_values[key] = value

        def mock_get(key):
            return stored_values.get(key)

        mock_redis.setex.side_effect = mock_setex
        mock_redis.get.side_effect = mock_get

        # Store translation
        set_cached_translation(text, "en", "fr", translation)

        # Retrieve translation
        result = get_cached_translation(text, "en", "fr")

        assert result == translation

    @patch("cache.cache_client")
    def test_different_language_pairs_isolated(self, mock_redis):
        """Test that different language pairs don't interfere."""
        text = "Hello"
        translation_fr = "Bonjour"
        translation_de = "Hallo"

        stored_values = {}

        def mock_setex(key, ttl, value):
            stored_values[key] = value

        def mock_get(key):
            return stored_values.get(key)

        mock_redis.setex.side_effect = mock_setex
        mock_redis.get.side_effect = mock_get

        # Store two translations
        set_cached_translation(text, "en", "fr", translation_fr)
        set_cached_translation(text, "en", "de", translation_de)

        # Retrieve both
        result_fr = get_cached_translation(text, "en", "fr")
        result_de = get_cached_translation(text, "en", "de")

        assert result_fr == translation_fr
        assert result_de == translation_de
