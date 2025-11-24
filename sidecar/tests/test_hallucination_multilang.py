"""Integration tests for multi-language hallucination detection pipeline.

Tests the full hallucination detection flow including:
- Multi-language NER consistency checks
- Base hallucination detection (repetition, length ratio)
- Number consistency across languages
- Language ID validation
- Fallback behavior for unsupported languages
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hallucination import (
    base_hallucination,
    detect_hallucination,
    length_ratio,
    repetition_score,
)


# Test fixtures
@pytest.fixture
def mock_spacy_model():
    """Create a mock spaCy model that extracts capitalized words as entities."""
    from spacy.language import Language

    mock_model = MagicMock(spec=Language)

    def mock_call(text: str):
        """Mock spaCy pipeline execution."""
        doc = MagicMock()
        entities = []
        for word in text.split():
            # Extract capitalized words as entities
            if word and word[0].isupper() and not word[0].isdigit():
                ent = MagicMock()
                ent.text = word.rstrip(".,!?")
                entities.append(ent)
        doc.ents = entities
        return doc

    mock_model.__call__ = mock_call
    return mock_model


@pytest.fixture
def clear_ner_cache():
    """Clear NER model cache between tests."""
    from nercheck import ModelCache

    cache = ModelCache()
    cache._models.clear()
    yield
    cache._models.clear()


# TestMultiLanguageHallucination: Full pipeline integration tests
class TestMultiLanguageHallucination:
    """Integration tests for multi-language hallucination detection."""

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_french_to_english_no_hallucination(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test French → English translation without hallucination."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "Google est à Paris en France"
        tgt = "Google is in Paris in France"
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False  # No hallucination detected

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_german_to_english_no_hallucination(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test German → English translation without hallucination."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "de"

        src = "Microsoft hat seinen Sitz in Redmond"
        tgt = "Microsoft is headquartered in Redmond"
        src_lang = "de"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_spanish_to_english_no_hallucination(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test Spanish → English translation without hallucination."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "es"

        src = "Tesla está en California"
        tgt = "Tesla is in California"
        src_lang = "es"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_repetition_based_hallucination(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test detection of repetition-based hallucination."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "Bonjour le monde"  # 3 words
        tgt = "hello world hello world hello world hello world"  # Exact repetition pattern
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is True  # Hallucination detected (repetition or length ratio)

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_length_ratio_hallucination(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test detection of length ratio-based hallucination."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "Bonjour"  # 1 word
        tgt = "Hello world this is a very long translation that exceeds ratio"  # 11 words
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is True  # Hallucination detected (length ratio > 2.5)

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_number_consistency_pass(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test number consistency validation passes with matching numbers."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "Il y a 42 étudiants et 3 professeurs"
        tgt = "There are 42 students and 3 professors"
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False  # No hallucination (numbers match)

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_number_consistency_fail(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test number consistency validation fails with mismatched numbers."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "Il y a 42 étudiants"
        tgt = "There are 99 students"  # Wrong number
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is True  # Hallucination detected (number mismatch)

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_entity_consistency_pass(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test entity consistency validation passes with consistent entities."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "Google est à Paris"
        tgt = "Google is in Paris"
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False  # No hallucination (entities consistent)

    @patch("nercheck.extract_ents")
    @patch("language_id.detect_language")
    def test_entity_consistency_fail_hallucinated_entity(self, mock_detect, mock_extract, clear_ner_cache):
        """Test entity consistency fails with hallucinated entity."""
        # Source has no entities, target has fabricated entity
        mock_extract.side_effect = [set(), {"Microsoft"}]
        mock_detect.return_value = "fr"

        src = "La société est grande"  # No specific entities
        tgt = "Microsoft is a big company"  # Hallucinated "Microsoft"
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is True  # Hallucination detected (fabricated entity per Rule 2)

    @patch("language_id.detect_language")
    def test_language_id_mismatch(self, mock_detect):
        """Test hallucination detection with language ID mismatch."""
        mock_detect.return_value = "en"  # Detected as English, not French

        src = "Hello world"  # Actually English
        tgt = "Hello world"
        src_lang = "fr"  # Claimed to be French

        result = detect_hallucination(src, tgt, src_lang)

        assert result is True  # Hallucination detected (wrong language)


# TestFallbackBehavior: Test fallback handling for unsupported languages
class TestFallbackBehavior:
    """Test hallucination detection with fallback modes for unsupported languages."""

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_unsupported_language_multilingual_mode(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model, monkeypatch):
        """Test unsupported language with MULTILINGUAL fallback mode."""
        monkeypatch.setenv("NER_FALLBACK_MODE", "multilingual")
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "ar"

        src = "مرحبا بالعالم"  # Arabic (unsupported)
        tgt = "Hello world"
        src_lang = "ar"

        result = detect_hallucination(src, tgt, src_lang)

        # Should use fallback model and language ID passes (mocked as 'ar')
        # Base checks, number checks, and NER checks should all pass
        assert result is False

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_unsupported_language_skip_source_mode(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model, monkeypatch):
        """Test unsupported language with SKIP_SOURCE fallback mode."""
        monkeypatch.setenv("NER_FALLBACK_MODE", "skip_source")
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "ar"

        src = "مرحبا بالعالم"  # Arabic (unsupported)
        tgt = "Hello world"
        src_lang = "ar"

        result = detect_hallucination(src, tgt, src_lang)

        # Language ID passes (mocked as 'ar'), NER check skipped for unsupported language
        assert result is False

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_hallucination_detection_with_fallback(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model, monkeypatch):
        """Test that hallucination detection still works with fallback models."""
        monkeypatch.setenv("NER_FALLBACK_MODE", "multilingual")
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "ar"

        # Test with repetition hallucination - need more repetition to trigger
        src = "مرحبا"  # Short text (1 word)
        tgt = "hello world hello world hello world hello world"  # 8 words, repetition
        src_lang = "ar"

        result = detect_hallucination(src, tgt, src_lang)

        # Should detect either length ratio (8/1 > 2.5) or repetition
        assert result is True

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_unsupported_language_strict_mode_fails(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model, monkeypatch):
        """Test STRICT mode behavior with unsupported language."""
        monkeypatch.setenv("NER_FALLBACK_MODE", "strict")
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "ar"

        src = "مرحبا بالعالم"
        tgt = "Hello world"
        src_lang = "ar"

        result = detect_hallucination(src, tgt, src_lang)

        # STRICT mode should fail the NER check for unsupported language
        assert result is True


# TestBaseHallucination: Unit tests for base hallucination checks
class TestBaseHallucination:
    """Test suite for base hallucination detection functions."""

    def test_length_ratio_calculation(self):
        """Test length ratio calculation."""
        src_tokens = ["hello", "world"]
        tgt_tokens = ["hello", "world", "test", "long", "translation", "here"]

        ratio = length_ratio(src_tokens, tgt_tokens)

        assert ratio == 3.0  # 6 / 2

    def test_length_ratio_empty_source(self):
        """Test length ratio with empty source (edge case)."""
        src_tokens = []
        tgt_tokens = ["hello", "world"]

        ratio = length_ratio(src_tokens, tgt_tokens)

        assert ratio == 2.0  # 2 / max(1, 0) = 2 / 1

    def test_repetition_score_no_repetition(self):
        """Test repetition score with no repetition."""
        tokens = ["hello", "world", "this", "is", "unique"]

        score = repetition_score(tokens, 3)

        assert score == 1  # Each trigram appears once

    def test_repetition_score_with_repetition(self):
        """Test repetition score with excessive repetition."""
        tokens = ["hello", "world", "hello", "world", "hello", "world"]

        score = repetition_score(tokens, 3)

        assert score >= 2  # Some trigrams repeat

    def test_repetition_score_empty_tokens(self):
        """Test repetition score with empty token list."""
        tokens = []

        score = repetition_score(tokens, 3)

        assert score == 0

    def test_base_hallucination_length_ratio_trigger(self):
        """Test base hallucination detection via length ratio."""
        src = "Hello"
        tgt = "This is a very very very long translation that exceeds the ratio"

        result = base_hallucination(src, tgt)

        assert result is True

    def test_base_hallucination_repetition_trigger(self):
        """Test base hallucination detection via repetition."""
        src = "Hello world"
        tgt = "Hello world hello world hello world"  # Repeated pattern

        result = base_hallucination(src, tgt)

        assert result is True

    def test_base_hallucination_no_trigger(self):
        """Test base hallucination with normal translation."""
        src = "Bonjour le monde"
        tgt = "Hello the world"

        result = base_hallucination(src, tgt)

        assert result is False


# TestRealWorldScenarios: Real-world translation scenarios
class TestRealWorldScenarios:
    """Test realistic translation scenarios."""

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_technical_translation_with_entities(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test technical translation with company names and locations."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "Microsoft et Google ont des bureaux à Paris"
        tgt = "Microsoft and Google have offices in Paris"
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False

    @patch("nercheck.extract_ents")
    @patch("language_id.detect_language")
    def test_translation_with_numbers_and_dates(self, mock_detect, mock_extract):
        """Test translation with numbers and dates."""
        mock_detect.return_value = "fr"
        # Mock NER to return empty sets (no entities, only numbers which are checked separately)
        mock_extract.side_effect = [set(), set()]

        src = "Le projet a commencé en 2020 avec 150 employés"
        tgt = "The project started in 2020 with 150 employees"
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False  # Numbers match

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_empty_translation(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test detection with empty translation output."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "Bonjour le monde"
        tgt = ""  # Empty translation

        # Empty target will trigger entity loss if source has entities
        # But with no entities in source, it should pass base checks
        result = base_hallucination(src, tgt)

        assert result is False  # Base checks don't flag empty target

    @patch("nercheck.extract_ents")
    @patch("language_id.detect_language")
    def test_partial_translation_entity_loss(self, mock_detect, mock_extract, clear_ner_cache):
        """Test detection when entities are lost in translation."""
        # Source has entities, target doesn't
        mock_extract.side_effect = [{"Google", "Microsoft", "Paris"}, set()]
        mock_detect.return_value = "fr"

        src = "Google et Microsoft sont à Paris"
        tgt = "Companies are in the city"  # Lost entity information
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is True  # Entities were lost (Rule 1: source has entities, target doesn't)


# TestEdgeCases: Edge case handling
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_identical_source_and_target(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test when source and target are identical."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "en"

        src = "Hello world"
        tgt = "Hello world"
        src_lang = "en"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False  # No hallucination (perfect match)

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_very_short_text(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test with very short text (single word)."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "Bonjour"
        tgt = "Hello"
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False

    @patch("nercheck.spacy.load")
    @patch("language_id.detect_language")
    def test_text_with_special_characters(self, mock_detect, mock_load, clear_ner_cache, mock_spacy_model):
        """Test translation with special characters and punctuation."""
        mock_load.return_value = mock_spacy_model
        mock_detect.return_value = "fr"

        src = "C'est incroyable! N'est-ce pas?"
        tgt = "It's incredible! Isn't it?"
        src_lang = "fr"

        result = detect_hallucination(src, tgt, src_lang)

        assert result is False
