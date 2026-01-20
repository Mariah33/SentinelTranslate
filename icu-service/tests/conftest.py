"""
Pytest fixtures for ICU microservice tests.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from icu_operations import ICUCache


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def clear_cache():
    """Clear ICU cache before and after each test."""
    cache = ICUCache()
    cache.clear()
    yield cache
    cache.clear()


@pytest.fixture
def sample_texts():
    """Sample texts for testing."""
    return {
        "latin": ["Café", "naïve", "résumé"],
        "cyrillic": ["Москва", "Санкт-Петербург", "Казань"],
        "greek": ["Αθήνα", "Θεσσαλονίκη", "Πάτρα"],
        "mixed": ["Hello", "Привет", "Γεια"],
        "special": ["", "123", "---"],
        "long": [
            "The quick brown fox jumps over the lazy dog",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
        ],
    }


@pytest.fixture
def sample_request_params():
    """Common request parameters for testing."""
    return {
        "transliterate": {
            "texts": ["Café", "naïve"],
            "transform_id": "Latin-ASCII",
        },
        "normalize": {
            "texts": ["café", "naïve"],
            "form": "NFC",
        },
        "transform": {
            "texts": ["Hello World"],
            "transform_spec": "::Latin-ASCII;",
        },
        "case_mapping": {
            "texts": ["istanbul"],
            "operation": "upper",
            "locale": "tr",
        },
    }
