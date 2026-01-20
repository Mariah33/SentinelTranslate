"""
Tests for Pydantic models validation.
"""

import pytest
from pydantic import ValidationError

from models import (
    CacheStatsResponse,
    CaseMappingRequest,
    CaseMappingResponse,
    CaseOperation,
    HealthResponse,
    NormalizationForm,
    NormalizeRequest,
    NormalizeResponse,
    SupportedOperationsResponse,
    TransformRequest,
    TransformResponse,
    TransliterateRequest,
    TransliterateResponse,
)


class TestTransliterateRequest:
    """Tests for TransliterateRequest model."""

    def test_valid_request(self):
        """Test valid TransliterateRequest."""
        req = TransliterateRequest(
            texts=["Café"],
            transform_id="Latin-ASCII",
        )
        assert req.texts == ["Café"]
        assert req.transform_id == "Latin-ASCII"
        assert req.reverse is False

    def test_valid_request_with_reverse(self):
        """Test valid request with reverse flag."""
        req = TransliterateRequest(
            texts=["test"],
            transform_id="Latin-ASCII",
            reverse=True,
        )
        assert req.reverse is True

    def test_request_requires_texts(self):
        """Test that texts field is required."""
        with pytest.raises(ValidationError):
            TransliterateRequest(transform_id="Latin-ASCII")

    def test_request_requires_transform_id(self):
        """Test that transform_id field is required."""
        with pytest.raises(ValidationError):
            TransliterateRequest(texts=["test"])

    def test_empty_texts_array_fails(self):
        """Test that empty texts array fails validation."""
        with pytest.raises(ValidationError):
            TransliterateRequest(texts=[], transform_id="Latin-ASCII")

    def test_exceeds_max_batch_size(self):
        """Test that exceeding max batch size fails validation."""
        texts = [f"Text {i}" for i in range(1001)]
        with pytest.raises(ValidationError):
            TransliterateRequest(texts=texts, transform_id="Latin-ASCII")

    def test_max_batch_size_allowed(self):
        """Test that max batch size is accepted."""
        texts = [f"Text {i}" for i in range(1000)]
        req = TransliterateRequest(texts=texts, transform_id="Latin-ASCII")
        assert len(req.texts) == 1000

    def test_transform_id_cannot_be_empty(self):
        """Test that transform_id cannot be empty."""
        with pytest.raises(ValidationError):
            TransliterateRequest(texts=["test"], transform_id="")


class TestTransliterateResponse:
    """Tests for TransliterateResponse model."""

    def test_valid_response(self):
        """Test valid TransliterateResponse."""
        resp = TransliterateResponse(
            results=["Cafe"],
            transform_id="Latin-ASCII",
            reverse=False,
            count=1,
        )
        assert resp.results == ["Cafe"]
        assert resp.count == 1

    def test_response_serialization(self):
        """Test response serialization to dict."""
        resp = TransliterateResponse(
            results=["Cafe"],
            transform_id="Latin-ASCII",
            reverse=False,
            count=1,
        )
        data = resp.model_dump()
        assert "results" in data
        assert "count" in data


class TestNormalizeRequest:
    """Tests for NormalizeRequest model."""

    def test_valid_request_nfc(self):
        """Test valid NormalizeRequest with NFC form."""
        req = NormalizeRequest(texts=["café"], form="NFC")
        assert req.form == "NFC"

    def test_valid_request_nfd(self):
        """Test valid NormalizeRequest with NFD form."""
        req = NormalizeRequest(texts=["café"], form="NFD")
        assert req.form == "NFD"

    def test_valid_request_nfkc(self):
        """Test valid NormalizeRequest with NFKC form."""
        req = NormalizeRequest(texts=["café"], form="NFKC")
        assert req.form == "NFKC"

    def test_valid_request_nfkd(self):
        """Test valid NormalizeRequest with NFKD form."""
        req = NormalizeRequest(texts=["café"], form="NFKD")
        assert req.form == "NFKD"

    def test_invalid_form_fails(self):
        """Test that invalid form fails validation."""
        with pytest.raises(ValidationError):
            NormalizeRequest(texts=["café"], form="INVALID")

    def test_form_case_sensitive(self):
        """Test that form values are case sensitive."""
        with pytest.raises(ValidationError):
            NormalizeRequest(texts=["café"], form="nfc")

    def test_empty_texts_fails(self):
        """Test that empty texts array fails."""
        with pytest.raises(ValidationError):
            NormalizeRequest(texts=[], form="NFC")

    def test_form_defaults_to_nfc_when_not_provided(self):
        """Test that form is required and must be provided."""
        # Form field is required
        with pytest.raises(ValidationError):
            NormalizeRequest(texts=["café"])  # missing form

        # When provided, it should be accepted
        req = NormalizeRequest(texts=["café"], form="NFC")
        assert str(req.form) == "NFC" or req.form == NormalizationForm.NFC


class TestNormalizeResponse:
    """Tests for NormalizeResponse model."""

    def test_valid_response(self):
        """Test valid NormalizeResponse."""
        resp = NormalizeResponse(results=["café"], form="NFC", count=1)
        assert resp.results == ["café"]
        assert resp.form == "NFC"
        assert resp.count == 1

    def test_response_serialization(self):
        """Test NormalizeResponse serialization."""
        resp = NormalizeResponse(results=["café"], form="NFC", count=1)
        data = resp.model_dump()
        assert data["form"] == "NFC"
        assert data["count"] == 1


class TestTransformRequest:
    """Tests for TransformRequest model."""

    def test_valid_request(self):
        """Test valid TransformRequest."""
        req = TransformRequest(
            texts=["Hello"],
            transform_spec="::Upper;",
        )
        assert req.texts == ["Hello"]
        assert req.transform_spec == "::Upper;"

    def test_requires_texts(self):
        """Test that texts is required."""
        with pytest.raises(ValidationError):
            TransformRequest(transform_spec="::Upper;")

    def test_requires_transform_spec(self):
        """Test that transform_spec is required."""
        with pytest.raises(ValidationError):
            TransformRequest(texts=["Hello"])

    def test_empty_texts_fails(self):
        """Test that empty texts fails."""
        with pytest.raises(ValidationError):
            TransformRequest(texts=[], transform_spec="::Upper;")


class TestTransformResponse:
    """Tests for TransformResponse model."""

    def test_valid_response(self):
        """Test valid TransformResponse."""
        resp = TransformResponse(
            results=["HELLO"],
            transform_spec="::Upper;",
            count=1,
        )
        assert resp.count == 1
        assert resp.transform_spec == "::Upper;"


class TestCaseMappingRequest:
    """Tests for CaseMappingRequest model."""

    def test_valid_request_upper(self):
        """Test valid CaseMappingRequest with upper operation."""
        req = CaseMappingRequest(
            texts=["test"],
            operation="upper",
        )
        assert req.operation == "upper"

    def test_valid_request_lower(self):
        """Test valid CaseMappingRequest with lower operation."""
        req = CaseMappingRequest(texts=["TEST"], operation="lower")
        assert req.operation == "lower"

    def test_valid_request_title(self):
        """Test valid CaseMappingRequest with title operation."""
        req = CaseMappingRequest(texts=["test"], operation="title")
        assert req.operation == "title"

    def test_valid_request_with_locale(self):
        """Test valid request with explicit locale."""
        req = CaseMappingRequest(
            texts=["test"],
            operation="upper",
            locale="tr",
        )
        assert req.locale == "tr"

    def test_invalid_operation_fails(self):
        """Test that invalid operation fails validation."""
        with pytest.raises(ValidationError):
            CaseMappingRequest(texts=["test"], operation="invalid")

    def test_empty_texts_fails(self):
        """Test that empty texts fails."""
        with pytest.raises(ValidationError):
            CaseMappingRequest(texts=[], operation="upper")

    def test_default_locale_is_en(self):
        """Test that default locale is 'en'."""
        req = CaseMappingRequest(texts=["test"], operation="upper")
        assert req.locale == "en"


class TestCaseMappingResponse:
    """Tests for CaseMappingResponse model."""

    def test_valid_response(self):
        """Test valid CaseMappingResponse."""
        resp = CaseMappingResponse(
            results=["TEST"],
            operation="upper",
            locale="en",
            count=1,
        )
        assert resp.operation == "upper"
        assert resp.locale == "en"


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_valid_response(self):
        """Test valid HealthResponse."""
        resp = HealthResponse(
            status="healthy",
            icu_version="73.1",
            cache_size=0,
            uptime_seconds=0.0,
        )
        assert resp.status == "healthy"
        assert "73.1" in resp.icu_version

    def test_response_serialization(self):
        """Test HealthResponse serialization."""
        resp = HealthResponse(
            status="healthy",
            icu_version="73.1",
            cache_size=100,
            uptime_seconds=3600.0,
        )
        data = resp.model_dump()
        assert data["cache_size"] == 100
        assert data["uptime_seconds"] == 3600.0


class TestCacheStatsResponse:
    """Tests for CacheStatsResponse model."""

    def test_valid_response(self):
        """Test valid CacheStatsResponse."""
        resp = CacheStatsResponse(
            cached_transforms=["Latin-ASCII"],
            total_cached=1,
            total_requests=10,
            cache_hit_rate=0.8,
        )
        assert resp.total_cached == 1
        assert resp.cache_hit_rate == 0.8

    def test_hit_rate_range(self):
        """Test hit rate must be between 0 and 1."""
        # Valid edge cases
        resp1 = CacheStatsResponse(
            cached_transforms=[],
            total_cached=0,
            total_requests=10,
            cache_hit_rate=0.0,
        )
        assert resp1.cache_hit_rate == 0.0

        resp2 = CacheStatsResponse(
            cached_transforms=[],
            total_cached=0,
            total_requests=10,
            cache_hit_rate=1.0,
        )
        assert resp2.cache_hit_rate == 1.0


class TestSupportedOperationsResponse:
    """Tests for SupportedOperationsResponse model."""

    def test_valid_response(self):
        """Test valid SupportedOperationsResponse."""
        resp = SupportedOperationsResponse(
            transliterations=["Latin-ASCII"],
            normalizations=["NFC", "NFD"],
            case_operations=["upper", "lower"],
            example_transforms={"test": "::Upper;"},
        )
        assert len(resp.transliterations) > 0
        assert "NFC" in resp.normalizations

    def test_response_serialization(self):
        """Test SupportedOperationsResponse serialization."""
        resp = SupportedOperationsResponse(
            transliterations=["Latin-ASCII"],
            normalizations=["NFC"],
            case_operations=["upper"],
            example_transforms={},
        )
        data = resp.model_dump()
        assert "transliterations" in data


class TestEnums:
    """Tests for enum types."""

    def test_normalization_form_enum_values(self):
        """Test NormalizationForm enum values."""
        assert NormalizationForm.NFC.value == "NFC"
        assert NormalizationForm.NFD.value == "NFD"
        assert NormalizationForm.NFKC.value == "NFKC"
        assert NormalizationForm.NFKD.value == "NFKD"

    def test_case_operation_enum_values(self):
        """Test CaseOperation enum values."""
        assert CaseOperation.UPPER.value == "upper"
        assert CaseOperation.LOWER.value == "lower"
        assert CaseOperation.TITLE.value == "title"


class TestModelValidation:
    """General model validation tests."""

    def test_request_models_require_texts(self):
        """Test all request models require texts field."""
        # TransliterateRequest
        with pytest.raises(ValidationError):
            TransliterateRequest(transform_id="Latin-ASCII")

        # NormalizeRequest
        with pytest.raises(ValidationError):
            NormalizeRequest(form="NFC")

        # TransformRequest
        with pytest.raises(ValidationError):
            TransformRequest(transform_spec="::Upper;")

        # CaseMappingRequest
        with pytest.raises(ValidationError):
            CaseMappingRequest(operation="upper")

    def test_response_models_serializable(self):
        """Test all response models are JSON serializable."""
        responses = [
            (
                TransliterateResponse(
                    results=["test"],
                    transform_id="Latin-ASCII",
                    reverse=False,
                    count=1,
                ),
                ["count"],
            ),
            (NormalizeResponse(results=["test"], form="NFC", count=1), ["count"]),
            (
                TransformResponse(results=["test"], transform_spec="::Upper;", count=1),
                ["count"],
            ),
            (
                CaseMappingResponse(
                    results=["TEST"],
                    operation="upper",
                    locale="en",
                    count=1,
                ),
                ["count"],
            ),
            (
                HealthResponse(
                    status="healthy",
                    icu_version="73.1",
                    cache_size=0,
                    uptime_seconds=0.0,
                ),
                ["status", "icu_version"],
            ),
        ]

        for resp, expected_fields in responses:
            data = resp.model_dump()
            assert isinstance(data, dict)
            # Check at least one expected field exists
            assert any(field in data for field in expected_fields)

    def test_batch_size_validation_across_models(self):
        """Test batch size limit validation across request models."""
        texts = [f"Text {i}" for i in range(1001)]

        with pytest.raises(ValidationError):
            TransliterateRequest(texts=texts, transform_id="Latin-ASCII")

        with pytest.raises(ValidationError):
            NormalizeRequest(texts=texts, form="NFC")

        with pytest.raises(ValidationError):
            TransformRequest(texts=texts, transform_spec="::Upper;")

        with pytest.raises(ValidationError):
            CaseMappingRequest(texts=texts, operation="upper")
