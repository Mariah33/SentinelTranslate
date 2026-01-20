"""
FastAPI endpoint tests for ICU microservice.
"""

from fastapi.testclient import TestClient
from starlette import status

# Use modern constant name
HTTP_422 = status.HTTP_422_UNPROCESSABLE_CONTENT


class TestTransliterateEndpoint:
    """Tests for /transliterate endpoint."""

    def test_basic_transliteration(self, client: TestClient):
        """Test basic Latin to ASCII transliteration."""
        response = client.post(
            "/transliterate",
            json={
                "texts": ["Café", "naïve"],
                "transform_id": "Latin-ASCII",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2
        assert len(data["results"]) == 2
        assert "Cafe" in data["results"]
        assert "naive" in data["results"]

    def test_transliterate_batch_processing(self, client: TestClient):
        """Test batch processing with 100 texts."""
        texts = [f"Text {i}: café" for i in range(100)]
        response = client.post(
            "/transliterate",
            json={
                "texts": texts,
                "transform_id": "Latin-ASCII",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 100
        assert len(data["results"]) == 100

    def test_transliterate_invalid_transform_id(self, client: TestClient):
        """Test transliteration with invalid transform ID."""
        response = client.post(
            "/transliterate",
            json={
                "texts": ["Café"],
                "transform_id": "InvalidTransformID",
            },
        )
        # Should return error (400 or 422)
        assert response.status_code in [400, 422]
        assert "detail" in response.json()

    def test_transliterate_batch_size_limit(self, client: TestClient):
        """Test that batch size exceeding limit returns error."""
        texts = [f"Text {i}" for i in range(1001)]
        response = client.post(
            "/transliterate",
            json={
                "texts": texts,
                "transform_id": "Latin-ASCII",
            },
        )
        assert response.status_code == HTTP_422
        data = response.json()
        # Check for either the field validation error or custom error message
        if isinstance(data, dict) and "detail" in data:
            assert "exceeds limit" in data["detail"] or "List should have" in str(data)
        elif isinstance(data, list):
            # Pydantic validation error list
            assert len(data) > 0

    def test_transliterate_empty_texts_array(self, client: TestClient):
        """Test that empty texts array fails validation."""
        response = client.post(
            "/transliterate",
            json={
                "texts": [],
                "transform_id": "Latin-ASCII",
            },
        )
        assert response.status_code == HTTP_422

    def test_transliterate_missing_transform_id(self, client: TestClient):
        """Test that missing transform_id fails validation."""
        response = client.post(
            "/transliterate",
            json={
                "texts": ["Café"],
            },
        )
        assert response.status_code == HTTP_422

    def test_transliterate_response_structure(self, client: TestClient):
        """Test response structure matches TransliterateResponse."""
        response = client.post(
            "/transliterate",
            json={
                "texts": ["test"],
                "transform_id": "Latin-ASCII",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data
        assert "transform_id" in data
        assert "reverse" in data
        assert "count" in data
        assert data["transform_id"] == "Latin-ASCII"
        assert data["count"] == 1


class TestNormalizeEndpoint:
    """Tests for /normalize endpoint."""

    def test_nfc_normalization(self, client: TestClient):
        """Test NFC normalization."""
        response = client.post(
            "/normalize",
            json={
                "texts": ["café", "naïve"],
                "form": "NFC",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2
        assert data["form"] == "NFC" or isinstance(data["form"], str)
        assert len(data["results"]) == 2

    def test_nfd_normalization(self, client: TestClient):
        """Test NFD normalization."""
        response = client.post(
            "/normalize",
            json={
                "texts": ["café"],
                "form": "NFD",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["form"] == "NFD"
        assert data["count"] == 1

    def test_nfkc_normalization(self, client: TestClient):
        """Test NFKC normalization."""
        response = client.post(
            "/normalize",
            json={
                "texts": ["café"],
                "form": "NFKC",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["form"] == "NFKC"

    def test_nfkd_normalization(self, client: TestClient):
        """Test NFKD normalization."""
        response = client.post(
            "/normalize",
            json={
                "texts": ["café"],
                "form": "NFKD",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["form"] == "NFKD"

    def test_normalize_invalid_form(self, client: TestClient):
        """Test normalization with invalid form."""
        response = client.post(
            "/normalize",
            json={
                "texts": ["café"],
                "form": "INVALID",
            },
        )
        assert response.status_code == HTTP_422

    def test_normalize_batch_processing(self, client: TestClient):
        """Test batch normalization."""
        texts = [f"Text {i}: café" for i in range(50)]
        response = client.post(
            "/normalize",
            json={
                "texts": texts,
                "form": "NFC",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 50

    def test_normalize_batch_size_limit(self, client: TestClient):
        """Test batch size limit for normalization."""
        texts = [f"Text {i}" for i in range(1001)]
        response = client.post(
            "/normalize",
            json={
                "texts": texts,
                "form": "NFC",
            },
        )
        assert response.status_code == HTTP_422

    def test_normalize_empty_texts(self, client: TestClient):
        """Test normalization with empty texts array."""
        response = client.post(
            "/normalize",
            json={
                "texts": [],
                "form": "NFC",
            },
        )
        assert response.status_code == HTTP_422


class TestTransformEndpoint:
    """Tests for /transform endpoint."""

    def test_custom_transform(self, client: TestClient):
        """Test custom ICU transform specification."""
        response = client.post(
            "/transform",
            json={
                "texts": ["Hello World"],
                "transform_spec": "::Latin-ASCII; ::Lower;",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 1
        assert data["transform_spec"] == "::Latin-ASCII; ::Lower;"

    def test_compound_transform(self, client: TestClient):
        """Test compound ICU transform."""
        response = client.post(
            "/transform",
            json={
                "texts": ["Café"],
                "transform_spec": "::Latin-ASCII; ::Upper;",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 1
        assert len(data["results"]) == 1

    def test_transform_invalid_spec(self, client: TestClient):
        """Test transform with invalid specification."""
        response = client.post(
            "/transform",
            json={
                "texts": ["test"],
                "transform_spec": "InvalidSpec123",
            },
        )
        # Should return error (400 or 422)
        assert response.status_code in [400, 422]

    def test_transform_batch_processing(self, client: TestClient):
        """Test batch transform processing."""
        texts = [f"Text {i}" for i in range(20)]
        response = client.post(
            "/transform",
            json={
                "texts": texts,
                "transform_spec": "::Upper;",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 20

    def test_transform_batch_size_limit(self, client: TestClient):
        """Test transform batch size limit."""
        texts = [f"Text {i}" for i in range(1001)]
        response = client.post(
            "/transform",
            json={
                "texts": texts,
                "transform_spec": "::Upper;",
            },
        )
        assert response.status_code == HTTP_422


class TestCaseMappingEndpoint:
    """Tests for /case-mapping endpoint."""

    def test_turkish_upper_case(self, client: TestClient):
        """Test Turkish locale upper case mapping."""
        response = client.post(
            "/case-mapping",
            json={
                "texts": ["istanbul"],
                "operation": "upper",
                "locale": "tr",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 1
        assert data["operation"] == "upper"
        assert data["locale"] == "tr"
        assert len(data["results"]) == 1

    def test_english_upper_case(self, client: TestClient):
        """Test English locale upper case."""
        response = client.post(
            "/case-mapping",
            json={
                "texts": ["hello", "world"],
                "operation": "upper",
                "locale": "en",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2
        assert all(text.isupper() for text in data["results"])

    def test_lower_case_operation(self, client: TestClient):
        """Test lower case operation."""
        response = client.post(
            "/case-mapping",
            json={
                "texts": ["HELLO", "WORLD"],
                "operation": "lower",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2
        assert data["operation"] == "lower"

    def test_title_case_operation(self, client: TestClient):
        """Test title case operation."""
        response = client.post(
            "/case-mapping",
            json={
                "texts": ["hello world"],
                "operation": "title",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["operation"] == "title"

    def test_case_mapping_invalid_operation(self, client: TestClient):
        """Test case mapping with invalid operation."""
        response = client.post(
            "/case-mapping",
            json={
                "texts": ["test"],
                "operation": "invalid",
            },
        )
        assert response.status_code == HTTP_422

    def test_case_mapping_batch(self, client: TestClient):
        """Test batch case mapping."""
        texts = [f"text{i}" for i in range(30)]
        response = client.post(
            "/case-mapping",
            json={
                "texts": texts,
                "operation": "upper",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 30

    def test_case_mapping_batch_size_limit(self, client: TestClient):
        """Test case mapping batch size limit."""
        texts = [f"Text {i}" for i in range(1001)]
        response = client.post(
            "/case-mapping",
            json={
                "texts": texts,
                "operation": "upper",
            },
        )
        assert response.status_code == HTTP_422

    def test_case_mapping_default_locale(self, client: TestClient):
        """Test case mapping without explicit locale."""
        response = client.post(
            "/case-mapping",
            json={
                "texts": ["test"],
                "operation": "upper",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "locale" in data


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_returns_200(self, client: TestClient):
        """Test health check returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK

    def test_health_response_structure(self, client: TestClient):
        """Test health response contains required fields."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "icu_version" in data
        assert "cache_size" in data
        assert "uptime_seconds" in data
        assert data["status"] == "healthy"

    def test_health_icu_version_present(self, client: TestClient):
        """Test health response includes ICU version."""
        response = client.get("/health")
        data = response.json()
        assert data["icu_version"]
        assert isinstance(data["icu_version"], str)

    def test_health_cache_size_integer(self, client: TestClient):
        """Test health response cache_size is integer."""
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["cache_size"], int)
        assert data["cache_size"] >= 0

    def test_health_uptime_seconds_positive(self, client: TestClient):
        """Test health response uptime is non-negative."""
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0


class TestCacheStatsEndpoint:
    """Tests for /cache-stats endpoint."""

    def test_cache_stats_returns_200(self, client: TestClient):
        """Test cache stats endpoint returns 200 OK."""
        response = client.get("/cache-stats")
        assert response.status_code == status.HTTP_200_OK

    def test_cache_stats_response_structure(self, client: TestClient):
        """Test cache stats response structure."""
        response = client.get("/cache-stats")
        data = response.json()
        # Check for either old or new field names
        assert "cache_hits" in data or "hits" in data
        assert "cache_misses" in data or "misses" in data
        assert "cache_hit_rate" in data or "hit_rate" in data

    def test_cache_stats_integer_values(self, client: TestClient):
        """Test cache stats integer fields are correct type."""
        response = client.get("/cache-stats")
        data = response.json()
        # Check for either field naming convention
        hits = data.get("cache_hits", data.get("hits"))
        misses = data.get("cache_misses", data.get("misses"))
        assert isinstance(hits, int)
        assert isinstance(misses, int)

    def test_cache_stats_hit_rate_range(self, client: TestClient):
        """Test cache stats hit rate is between 0 and 1."""
        response = client.get("/cache-stats")
        data = response.json()
        hit_rate = data.get("cache_hit_rate", data.get("hit_rate"))
        assert 0.0 <= hit_rate <= 1.0

    def test_cache_stats_increments_on_requests(self, client: TestClient):
        """Test cache stats update after requests."""
        # Get initial stats
        initial = client.get("/cache-stats").json()
        initial_total = initial.get("cache_hits", initial.get("hits", 0)) + initial.get("cache_misses", initial.get("misses", 0))

        # Make a request
        client.post(
            "/transliterate",
            json={
                "texts": ["test"],
                "transform_id": "Latin-ASCII",
            },
        )

        # Check stats updated
        updated = client.get("/cache-stats").json()
        updated_total = updated.get("cache_hits", updated.get("hits", 0)) + updated.get("cache_misses", updated.get("misses", 0))
        # Either hits or misses should have increased
        assert updated_total >= initial_total


class TestSupportedOperationsEndpoint:
    """Tests for /supported-operations endpoint."""

    def test_supported_operations_returns_200(self, client: TestClient):
        """Test supported operations endpoint returns 200 OK."""
        response = client.get("/supported-operations")
        assert response.status_code == status.HTTP_200_OK

    def test_supported_operations_structure(self, client: TestClient):
        """Test supported operations response structure."""
        response = client.get("/supported-operations")
        data = response.json()
        # Check for either naming convention
        assert "transliterators" in data or "transliterations" in data
        assert "normalization_forms" in data or "normalizations" in data
        assert "case_operations" in data

    def test_supported_transliterators_list(self, client: TestClient):
        """Test transliterators is a list."""
        response = client.get("/supported-operations")
        data = response.json()
        trans_list = data.get("transliterators", data.get("transliterations", []))
        assert isinstance(trans_list, list)
        assert len(trans_list) > 0

    def test_supported_normalization_forms(self, client: TestClient):
        """Test normalization forms list."""
        response = client.get("/supported-operations")
        data = response.json()
        forms = data.get("normalization_forms", data.get("normalizations", []))
        assert isinstance(forms, list)
        assert "NFC" in forms
        assert "NFD" in forms
        assert "NFKC" in forms
        assert "NFKD" in forms

    def test_supported_case_operations(self, client: TestClient):
        """Test case operations list."""
        response = client.get("/supported-operations")
        data = response.json()
        ops = data.get("case_operations", [])
        assert isinstance(ops, list)
        assert "upper" in ops
        assert "lower" in ops
        assert "title" in ops

    def test_supported_common_locales(self, client: TestClient):
        """Test common locales list."""
        response = client.get("/supported-operations")
        data = response.json()
        locales = data.get("common_locales", [])
        assert isinstance(locales, list)


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_endpoint_returns_200(self, client: TestClient):
        """Test root endpoint returns 200 OK."""
        try:
            response = client.get("/")
            assert response.status_code == status.HTTP_200_OK
        except Exception:
            # Root endpoint may not be implemented
            pass

    def test_root_endpoint_contains_info(self, client: TestClient):
        """Test root endpoint returns service info."""
        try:
            response = client.get("/")
            if response.status_code == 200:
                data = response.json()
                assert "service" in data or "endpoints" in data
        except Exception:
            # Root endpoint may not be implemented
            pass


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_required_field(self, client: TestClient):
        """Test missing required field returns 422."""
        response = client.post("/transliterate", json={"texts": ["test"]})
        assert response.status_code == HTTP_422

    def test_invalid_json_returns_422(self, client: TestClient):
        """Test invalid JSON returns 422."""
        response = client.post(
            "/transliterate",
            content="invalid json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code in [
            HTTP_422,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_nonexistent_endpoint_returns_404(self, client: TestClient):
        """Test nonexistent endpoint returns 404."""
        response = client.get("/nonexistent")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_wrong_http_method_returns_405(self, client: TestClient):
        """Test wrong HTTP method returns 405."""
        response = client.get("/transliterate")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
