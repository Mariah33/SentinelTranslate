"""Comprehensive unit tests for multi-language NER system.

Tests cover:
- Entity extraction across 20+ supported languages
- NER consistency validation logic
- ModelCache singleton and lazy loading
- Fallback mode configuration and behavior
"""

import os
import threading
from unittest.mock import MagicMock, patch

import pytest
import spacy
from spacy.language import Language

from worker.nercheck import (
    FALLBACK_MODEL,
    LANG_TO_SPACY_MODEL,
    SUPPORTED_LANGS,
    FallbackMode,
    ModelCache,
    extract_ents,
    get_cache_stats,
    get_fallback_mode,
    ner_consistency,
    preload_models,
)


# Test fixtures
@pytest.fixture
def clear_cache():
    """Clear model cache before each test to ensure isolation."""
    cache = ModelCache()
    cache._models.clear()
    yield
    cache._models.clear()


@pytest.fixture
def mock_spacy_model():
    """Create a mock spaCy model for testing without requiring model downloads."""
    mock_model = MagicMock(spec=Language)

    def mock_call(text: str):
        """Mock spaCy pipeline execution."""
        doc = MagicMock()
        # Simple mock: extract capitalized words as entities
        entities = []
        for word in text.split():
            if word and word[0].isupper():
                ent = MagicMock()
                ent.text = word
                entities.append(ent)
        doc.ents = entities
        return doc

    mock_model.__call__ = mock_call
    return mock_model


@pytest.fixture
def monkeypatch_env(monkeypatch):
    """Provide monkeypatch fixture for environment variable modification."""
    return monkeypatch


# TestExtractEnts: Entity extraction tests
class TestExtractEnts:
    """Test suite for extract_ents() function."""

    def test_english_entity_extraction(self, clear_cache):
        """Test baseline entity extraction with English model."""
        # Skip if model not installed
        try:
            spacy.load("en_core_web_sm")
        except OSError:
            pytest.skip("en_core_web_sm model not installed")

        text = "Apple Inc. is located in Cupertino, California."
        entities = extract_ents(text, "en")

        # Should extract at least some entities
        assert isinstance(entities, set)
        assert len(entities) > 0

    @pytest.mark.parametrize(
        "text,lang_code,expected_model",
        [
            ("Google est à Paris", "fr", "fr_core_news_sm"),
            ("Microsoft hat seinen Sitz in Redmond", "de", "de_core_news_sm"),
            ("Tesla está en California", "es", "es_core_news_sm"),
            ("苹果公司在库比蒂诺", "zh", "zh_core_web_sm"),
        ],
    )
    def test_supported_languages(self, clear_cache, text, lang_code, expected_model):
        """Test entity extraction for supported languages (fr, de, es, zh)."""
        # Skip if model not installed
        try:
            spacy.load(expected_model)
        except OSError:
            pytest.skip(f"{expected_model} model not installed")

        entities = extract_ents(text, lang_code)

        # Should return a set (may be empty if model doesn't detect entities)
        assert isinstance(entities, set)

    @patch("worker.nercheck.spacy.load")
    def test_unsupported_language_multilingual_mode(self, mock_load, clear_cache, mock_spacy_model):
        """Test unsupported language uses fallback model in MULTILINGUAL mode."""
        mock_load.return_value = mock_spacy_model

        text = "مرحبا العالم"  # Arabic (unsupported)
        entities = extract_ents(text, "ar")

        # Should attempt to load fallback model
        mock_load.assert_called_once_with(FALLBACK_MODEL)
        assert isinstance(entities, set)

    @patch("worker.nercheck.spacy.load")
    def test_unsupported_language_skip_source_mode(
        self, mock_load, clear_cache, monkeypatch_env, mock_spacy_model
    ):
        """Test unsupported language with SKIP_SOURCE mode still loads fallback."""
        monkeypatch_env.setenv("NER_FALLBACK_MODE", "skip_source")
        mock_load.return_value = mock_spacy_model

        text = "مرحبا العالم"  # Arabic
        entities = extract_ents(text, "ar")

        # extract_ents always attempts to load model
        mock_load.assert_called_once_with(FALLBACK_MODEL)
        assert isinstance(entities, set)

    @patch("worker.nercheck.spacy.load")
    def test_unsupported_language_strict_mode(
        self, mock_load, clear_cache, monkeypatch_env, mock_spacy_model
    ):
        """Test unsupported language with STRICT mode still attempts load."""
        monkeypatch_env.setenv("NER_FALLBACK_MODE", "strict")
        mock_load.return_value = mock_spacy_model

        text = "مرحبا العالم"  # Arabic
        entities = extract_ents(text, "ar")

        # extract_ents loads model regardless of fallback mode
        mock_load.assert_called_once_with(FALLBACK_MODEL)
        assert isinstance(entities, set)

    @patch("worker.nercheck.spacy.load")
    def test_model_load_failure(self, mock_load, clear_cache):
        """Test handling when model loading fails."""
        mock_load.side_effect = OSError("Model not found")

        text = "Test text"
        entities = extract_ents(text, "en")

        # Should return empty set on failure
        assert entities == set()

    @patch("worker.nercheck.spacy.load")
    def test_empty_text(self, mock_load, clear_cache, mock_spacy_model):
        """Test entity extraction from empty text."""
        mock_load.return_value = mock_spacy_model

        entities = extract_ents("", "en")

        assert isinstance(entities, set)
        assert len(entities) == 0

    @patch("worker.nercheck.spacy.load")
    def test_text_with_no_entities(self, mock_load, clear_cache, mock_spacy_model):
        """Test text with no entities returns empty set."""
        mock_model = MagicMock(spec=Language)
        doc = MagicMock()
        doc.ents = []
        mock_model.return_value = doc
        mock_load.return_value = mock_model

        text = "this is lowercase text with no entities"
        entities = extract_ents(text, "en")

        assert entities == set()


# TestNERConsistency: NER consistency validation tests
class TestNERConsistency:
    """Test suite for ner_consistency() function."""

    @patch("worker.nercheck.extract_ents")
    def test_consistent_entities_pass(self, mock_extract):
        """Test that consistent entities pass validation."""
        # Source and target have same entities
        mock_extract.side_effect = [{"Google", "Paris"}, {"Google", "Paris"}]

        result = ner_consistency("Google est à Paris", "Google is in Paris", "fr")

        assert result is True

    @patch("worker.nercheck.extract_ents")
    def test_hallucinated_entities_fail(self, mock_extract):
        """Test that hallucinated entities fail validation."""
        # Target has NEW entity not in source
        mock_extract.side_effect = [{"Paris"}, {"Microsoft", "Paris"}]

        result = ner_consistency("La ville est grande", "Microsoft is in Paris", "fr")

        assert result is False

    @patch("worker.nercheck.extract_ents")
    def test_dropped_entities_fail(self, mock_extract):
        """Test that dropped entities fail validation."""
        # Source has entities but target doesn't
        mock_extract.side_effect = [{"Google", "Paris"}, set()]

        result = ner_consistency("Google est à Paris", "The company is there", "fr")

        assert result is False

    @patch("worker.nercheck.extract_ents")
    def test_empty_source_and_target(self, mock_extract):
        """Test empty source and target text."""
        mock_extract.side_effect = [set(), set()]

        result = ner_consistency("", "", "en")

        assert result is True

    @patch("worker.nercheck.extract_ents")
    def test_no_entities_in_either(self, mock_extract):
        """Test text with no entities in source or target."""
        mock_extract.side_effect = [set(), set()]

        result = ner_consistency("la ville est grande", "the city is big", "fr")

        assert result is True

    @patch("worker.nercheck.extract_ents")
    @pytest.mark.parametrize("src_lang", ["fr", "de", "es", "zh"])
    def test_different_source_languages(self, mock_extract, src_lang):
        """Test NER consistency with different source languages."""
        mock_extract.side_effect = [{"Entity"}, {"Entity"}]

        result = ner_consistency("source text", "target text", src_lang)

        assert result is True
        # Verify extract_ents called with correct language codes
        assert mock_extract.call_count == 2
        calls = mock_extract.call_args_list
        assert calls[0][0][1] == src_lang  # Source language
        assert calls[1][0][1] == "en"  # Target always English

    @patch("worker.nercheck.extract_ents")
    def test_unsupported_language_strict_mode_fails(self, mock_extract, monkeypatch_env):
        """Test STRICT mode fails for unsupported languages."""
        monkeypatch_env.setenv("NER_FALLBACK_MODE", "strict")
        mock_extract.return_value = set()

        result = ner_consistency("مرحبا", "hello", "ar")

        assert result is False

    @patch("worker.nercheck.extract_ents")
    def test_unsupported_language_skip_source_mode_passes(self, mock_extract, monkeypatch_env):
        """Test SKIP_SOURCE mode passes for unsupported languages."""
        monkeypatch_env.setenv("NER_FALLBACK_MODE", "skip_source")
        mock_extract.return_value = set()

        result = ner_consistency("مرحبا", "hello", "ar")

        assert result is True

    @patch("worker.nercheck.extract_ents")
    def test_unsupported_language_multilingual_mode(self, mock_extract, monkeypatch_env):
        """Test MULTILINGUAL mode uses fallback for unsupported languages."""
        monkeypatch_env.setenv("NER_FALLBACK_MODE", "multilingual")
        mock_extract.side_effect = [{"Entity"}, {"Entity"}]

        result = ner_consistency("source text", "target text", "ar")

        assert result is True


# TestModelCache: Cache singleton and lazy loading tests
class TestModelCache:
    """Test suite for ModelCache class."""

    def test_singleton_pattern(self, clear_cache):
        """Test that ModelCache returns same instance."""
        cache1 = ModelCache()
        cache2 = ModelCache()

        assert cache1 is cache2

    @patch("worker.nercheck.spacy.load")
    def test_lazy_loading(self, mock_load, clear_cache, mock_spacy_model):
        """Test model is loaded on first access."""
        mock_load.return_value = mock_spacy_model
        cache = ModelCache()

        # Model not loaded yet
        assert "en" not in cache._models

        # First access triggers load
        model = cache.get_or_load("en")

        assert model is not None
        mock_load.assert_called_once_with("en_core_web_sm")
        assert "en" in cache._models

    @patch("worker.nercheck.spacy.load")
    def test_caching(self, mock_load, clear_cache, mock_spacy_model):
        """Test second access returns cached model without reload."""
        mock_load.return_value = mock_spacy_model
        cache = ModelCache()

        # First access
        model1 = cache.get_or_load("en")

        # Second access
        model2 = cache.get_or_load("en")

        # Should only call spacy.load once
        assert mock_load.call_count == 1
        assert model1 is model2

    def test_get_stats(self, clear_cache):
        """Test get_stats() returns cache information."""
        cache = ModelCache()
        stats = cache.get_stats()

        assert "loaded_models" in stats
        assert "cache_size" in stats
        assert isinstance(stats["loaded_models"], list)
        assert isinstance(stats["cache_size"], int)
        assert stats["cache_size"] == 0

    @patch("worker.nercheck.spacy.load")
    def test_get_stats_with_loaded_models(self, mock_load, clear_cache, mock_spacy_model):
        """Test get_stats() shows loaded models."""
        mock_load.return_value = mock_spacy_model
        cache = ModelCache()

        cache.get_or_load("en")
        cache.get_or_load("fr")

        stats = cache.get_stats()

        assert stats["cache_size"] == 2
        assert "en" in stats["loaded_models"]
        assert "fr" in stats["loaded_models"]

    @patch("worker.nercheck.spacy.load")
    def test_thread_safety(self, mock_load, clear_cache, mock_spacy_model):
        """Test thread-safe model loading with concurrent access."""
        load_count = 0
        load_lock = threading.Lock()

        def counting_load(model_name):
            """Track number of times spacy.load is called."""
            nonlocal load_count
            with load_lock:
                load_count += 1
            return mock_spacy_model

        mock_load.side_effect = counting_load
        cache = ModelCache()

        def load_model():
            cache.get_or_load("en")

        # Spawn multiple threads trying to load same model
        threads = [threading.Thread(target=load_model) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should only load model once despite concurrent access
        assert load_count == 1

    @patch("worker.nercheck.spacy.load")
    def test_fallback_model_for_unsupported_lang(self, mock_load, clear_cache, mock_spacy_model):
        """Test that unsupported languages use fallback model."""
        mock_load.return_value = mock_spacy_model
        cache = ModelCache()

        model = cache.get_or_load("ar")  # Arabic (unsupported)

        mock_load.assert_called_once_with(FALLBACK_MODEL)
        assert model is not None


# TestFallbackMode: Fallback configuration tests
class TestFallbackMode:
    """Test suite for fallback mode configuration."""

    def test_default_mode_is_multilingual(self, monkeypatch_env):
        """Test default fallback mode is MULTILINGUAL."""
        monkeypatch_env.delenv("NER_FALLBACK_MODE", raising=False)

        mode = get_fallback_mode()

        assert mode == FallbackMode.MULTILINGUAL

    @pytest.mark.parametrize(
        "env_value,expected_mode",
        [
            ("multilingual", FallbackMode.MULTILINGUAL),
            ("skip_source", FallbackMode.SKIP_SOURCE),
            ("strict", FallbackMode.STRICT),
            ("MULTILINGUAL", FallbackMode.MULTILINGUAL),
            ("Skip_Source", FallbackMode.SKIP_SOURCE),
        ],
    )
    def test_read_from_environment(self, monkeypatch_env, env_value, expected_mode):
        """Test reading fallback mode from NER_FALLBACK_MODE environment variable."""
        monkeypatch_env.setenv("NER_FALLBACK_MODE", env_value)

        mode = get_fallback_mode()

        assert mode == expected_mode

    def test_invalid_mode_defaults_to_multilingual(self, monkeypatch_env):
        """Test invalid mode defaults to MULTILINGUAL with warning."""
        monkeypatch_env.setenv("NER_FALLBACK_MODE", "invalid_mode")

        mode = get_fallback_mode()

        assert mode == FallbackMode.MULTILINGUAL


# TestPreloadModels: Model preloading tests
class TestPreloadModels:
    """Test suite for preload_models() function."""

    @patch("worker.nercheck.ModelCache.get_or_load")
    def test_preload_calls_get_or_load(self, mock_get_or_load):
        """Test preload_models() calls get_or_load for each language."""
        lang_codes = ["en", "fr", "de"]

        preload_models(lang_codes)

        assert mock_get_or_load.call_count == 3
        for lang in lang_codes:
            mock_get_or_load.assert_any_call(lang)

    @patch("worker.nercheck.ModelCache.get_or_load")
    def test_preload_empty_list(self, mock_get_or_load):
        """Test preload_models() with empty list."""
        preload_models([])

        mock_get_or_load.assert_not_called()


# TestCacheStats: Global cache stats function
class TestCacheStats:
    """Test suite for get_cache_stats() global function."""

    def test_get_cache_stats_returns_dict(self, clear_cache):
        """Test get_cache_stats() returns dictionary."""
        stats = get_cache_stats()

        assert isinstance(stats, dict)
        assert "loaded_models" in stats
        assert "cache_size" in stats


# TestConstants: Validate module constants
class TestConstants:
    """Test suite for module constants."""

    def test_supported_langs_count(self):
        """Test that SUPPORTED_LANGS has 21 languages."""
        assert len(SUPPORTED_LANGS) == 21

    def test_lang_to_spacy_model_mapping(self):
        """Test language to model mapping is complete."""
        assert len(LANG_TO_SPACY_MODEL) == 21

        # Verify some key mappings
        assert LANG_TO_SPACY_MODEL["en"] == "en_core_web_sm"
        assert LANG_TO_SPACY_MODEL["fr"] == "fr_core_news_sm"
        assert LANG_TO_SPACY_MODEL["de"] == "de_core_news_sm"
        assert LANG_TO_SPACY_MODEL["zh"] == "zh_core_web_sm"

    def test_fallback_model_constant(self):
        """Test fallback model constant is set."""
        assert FALLBACK_MODEL == "xx_ent_wiki_sm"

    def test_supported_langs_matches_mapping(self):
        """Test SUPPORTED_LANGS matches keys in LANG_TO_SPACY_MODEL."""
        assert SUPPORTED_LANGS == set(LANG_TO_SPACY_MODEL.keys())

    def test_fallback_mode_enum_values(self):
        """Test FallbackMode enum has correct values."""
        assert FallbackMode.MULTILINGUAL.value == "multilingual"
        assert FallbackMode.SKIP_SOURCE.value == "skip_source"
        assert FallbackMode.STRICT.value == "strict"
