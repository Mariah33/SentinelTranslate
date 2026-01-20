"""HTTP client for ICU microservice with retry logic and connection pooling.

This module provides a robust HTTP client for calling the ICU microservice from PySpark jobs.
It includes connection pooling, retry logic with exponential backoff, and comprehensive error handling.

Example:
    client = ICUServiceClient("http://icu-service:8083", timeout=30)
    results = client.transliterate(["Café", "naïve"], "Latin-ASCII")
    print(results)  # ['Cafe', 'naive']
"""

import logging
import os
from typing import Any, Literal

import requests
from requests.adapters import HTTPAdapter
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Type aliases for better readability
NormalizationForm = Literal["NFC", "NFD", "NFKC", "NFKD"]
CaseMappingOperation = Literal["upper", "lower", "title", "fold"]


class ICUServiceError(Exception):
    """Base exception for ICU service errors."""

    pass


class ICUServiceClient:
    """HTTP client for ICU microservice with retry logic and connection pooling.

    This client provides methods for calling all ICU microservice endpoints with
    automatic retry on transient failures, connection pooling for performance,
    and comprehensive error handling.

    Attributes:
        base_url: Base URL of the ICU microservice (e.g., "http://icu-service:8083")
        timeout: Request timeout in seconds
        session: Requests session with connection pooling

    Example:
        # Initialize client
        client = ICUServiceClient("http://icu-service:8083", timeout=30)

        # Health check
        health = client.health_check()
        print(health)  # {'status': 'healthy', 'service': 'icu-service', ...}

        # Transliterate text
        results = client.transliterate(
            texts=["Café au lait", "naïve résumé"],
            transform_id="Latin-ASCII",
            reverse=False
        )
        print(results)  # ['Cafe au lait', 'naive resume']

        # Normalize text
        results = client.normalize(
            texts=["e\u0301"],  # e + combining acute accent
            form="NFC"
        )
        print(results)  # ['é']  # precomposed character

        # Case mapping with locale
        results = client.case_mapping(
            texts=["istanbul"],
            operation="upper",
            locale="tr"  # Turkish locale
        )
        print(results)  # ['İSTANBUL']  # Note: dotted I in Turkish
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """Initialize ICU service client.

        Args:
            base_url: Base URL of the ICU microservice. If None, reads from
                ICU_SERVICE_URL environment variable (default: http://icu-service:8083)
            timeout: Request timeout in seconds. If None, reads from
                ICU_REQUEST_TIMEOUT environment variable (default: 30)
        """
        self.base_url = (base_url or os.getenv("ICU_SERVICE_URL", "http://icu-service:8083")).rstrip("/")
        self.timeout = timeout or int(os.getenv("ICU_REQUEST_TIMEOUT", "30"))

        # Create session with connection pooling
        # pool_connections: Number of connection pools to cache
        # pool_maxsize: Maximum number of connections to save in the pool
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info(f"Initialized ICU client: base_url={self.base_url}, timeout={self.timeout}s")

    @retry(
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),  # 1s, 2s, 4s
        reraise=True,
    )
    def _post(self, endpoint: str, json_data: dict[str, Any]) -> dict[str, Any]:
        """Make POST request with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/transliterate")
            json_data: JSON payload

        Returns:
            JSON response as dictionary

        Raises:
            ICUServiceError: On HTTP errors or invalid response
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(url, json=json_data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Try to extract error message from response
            try:
                error_detail = e.response.json().get("detail", str(e))
            except Exception:
                error_detail = str(e)
            raise ICUServiceError(f"HTTP {e.response.status_code} error from {endpoint}: {error_detail}") from e
        except requests.exceptions.RequestException as e:
            raise ICUServiceError(f"Request failed for {endpoint}: {e}") from e
        except ValueError as e:
            raise ICUServiceError(f"Invalid JSON response from {endpoint}: {e}") from e

    @retry(
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    def _get(self, endpoint: str) -> dict[str, Any]:
        """Make GET request with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/health")

        Returns:
            JSON response as dictionary

        Raises:
            ICUServiceError: On HTTP errors or invalid response
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = e.response.json().get("detail", str(e))
            except Exception:
                error_detail = str(e)
            raise ICUServiceError(f"HTTP {e.response.status_code} error from {endpoint}: {error_detail}") from e
        except requests.exceptions.RequestException as e:
            raise ICUServiceError(f"Request failed for {endpoint}: {e}") from e
        except ValueError as e:
            raise ICUServiceError(f"Invalid JSON response from {endpoint}: {e}") from e

    def transliterate(
        self,
        texts: list[str],
        transform_id: str,
        reverse: bool = False,
    ) -> list[str]:
        """Transliterate text using ICU transform.

        Args:
            texts: List of texts to transliterate
            transform_id: ICU transform identifier (e.g., "Latin-ASCII", "Any-Latin", "Cyrillic-Latin")
            reverse: If True, reverse the transform direction

        Returns:
            List of transliterated texts

        Raises:
            ICUServiceError: On service errors or invalid transform_id

        Example:
            >>> client = ICUServiceClient()
            >>> client.transliterate(["Café", "naïve"], "Latin-ASCII")
            ['Cafe', 'naive']
            >>> client.transliterate(["Москва", "Киев"], "Cyrillic-Latin")
            ['Moskva', 'Kiev']
        """
        payload = {"texts": texts, "transform_id": transform_id, "reverse": reverse}
        response = self._post("/transliterate", payload)
        return response["results"]

    def normalize(
        self,
        texts: list[str],
        form: NormalizationForm,
    ) -> list[str]:
        """Normalize text using Unicode normalization.

        Args:
            texts: List of texts to normalize
            form: Normalization form (NFC, NFD, NFKC, NFKD)

        Returns:
            List of normalized texts

        Raises:
            ICUServiceError: On service errors or invalid normalization form

        Example:
            >>> client = ICUServiceClient()
            >>> # Combining characters to precomposed
            >>> client.normalize(["e\u0301"], "NFC")  # e + combining acute
            ['é']  # precomposed character
            >>> # Precomposed to combining characters
            >>> client.normalize(["é"], "NFD")
            ['e\u0301']  # e + combining acute
        """
        payload = {"texts": texts, "form": form}
        response = self._post("/normalize", payload)
        return response["results"]

    def transform(
        self,
        texts: list[str],
        transform_spec: str,
    ) -> list[str]:
        """Apply custom ICU transform specification.

        This allows complex multi-stage transforms like "NFD; Latin-ASCII; NFC".

        Args:
            texts: List of texts to transform
            transform_spec: ICU transform specification (e.g., "NFD; Latin-ASCII; NFC")

        Returns:
            List of transformed texts

        Raises:
            ICUServiceError: On service errors or invalid transform spec

        Example:
            >>> client = ICUServiceClient()
            >>> # Multi-stage transform: decompose, transliterate, recompose
            >>> client.transform(["Café"], "NFD; Latin-ASCII; NFC")
            ['Cafe']
        """
        payload = {"texts": texts, "transform_spec": transform_spec}
        response = self._post("/transform", payload)
        return response["results"]

    def case_mapping(
        self,
        texts: list[str],
        operation: CaseMappingOperation,
        locale: str | None = None,
    ) -> list[str]:
        """Apply locale-aware case mapping.

        Args:
            texts: List of texts to transform
            operation: Case operation (upper, lower, title, fold)
            locale: Locale code (e.g., "tr" for Turkish, "en" for English)
                If None, uses root locale

        Returns:
            List of case-mapped texts

        Raises:
            ICUServiceError: On service errors or invalid operation

        Example:
            >>> client = ICUServiceClient()
            >>> # Turkish uppercase (dotted I)
            >>> client.case_mapping(["istanbul"], "upper", "tr")
            ['İSTANBUL']
            >>> # English uppercase (dotless I)
            >>> client.case_mapping(["istanbul"], "upper", "en")
            ['ISTANBUL']
        """
        payload = {"texts": texts, "operation": operation, "locale": locale}
        response = self._post("/case-mapping", payload)
        return response["results"]

    def health_check(self) -> dict[str, Any]:
        """Check service health.

        Returns:
            Health status dictionary with service information

        Raises:
            ICUServiceError: On service errors

        Example:
            >>> client = ICUServiceClient()
            >>> health = client.health_check()
            >>> print(health)
            {'status': 'healthy', 'service': 'icu-service', 'version': '1.0.0'}
        """
        return self._get("/health")

    def get_supported_operations(self) -> dict[str, Any]:
        """Get list of supported ICU operations.

        Returns:
            Dictionary with supported transforms, normalizations, and case operations

        Raises:
            ICUServiceError: On service errors

        Example:
            >>> client = ICUServiceClient()
            >>> ops = client.get_supported_operations()
            >>> print(ops["transforms"])
            ['Latin-ASCII', 'Any-Latin', 'Cyrillic-Latin', ...]
        """
        return self._get("/supported-operations")

    def __enter__(self) -> "ICUServiceClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - close session."""
        self.session.close()

    def close(self) -> None:
        """Close the HTTP session and release connections."""
        self.session.close()
        logger.info("Closed ICU client session")
