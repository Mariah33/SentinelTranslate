"""Pydantic models for ICU service API requests and responses."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class NormalizationForm(str, Enum):
    """Unicode normalization forms."""

    NFC = "NFC"  # Canonical Decomposition, followed by Canonical Composition
    NFD = "NFD"  # Canonical Decomposition
    NFKC = "NFKC"  # Compatibility Decomposition, followed by Canonical Composition
    NFKD = "NFKD"  # Compatibility Decomposition


class CaseOperation(str, Enum):
    """Case mapping operations."""

    UPPER = "upper"  # Convert to uppercase
    LOWER = "lower"  # Convert to lowercase
    TITLE = "title"  # Convert to titlecase


# Request Models
class TransliterateRequest(BaseModel):
    """Request model for transliteration."""

    texts: list[str] = Field(..., min_length=1, max_length=1000, description="List of texts to transliterate")
    transform_id: str = Field(..., min_length=1, description="ICU transform ID (e.g., 'Latin-Katakana', 'Any-Latin')")
    reverse: bool = Field(default=False, description="Apply reverse transformation")

    class Config:
        json_schema_extra = {
            "example": {
                "texts": ["Hello World", "こんにちは"],
                "transform_id": "Latin-Katakana",
                "reverse": False,
            }
        }


class NormalizeRequest(BaseModel):
    """Request model for Unicode normalization."""

    texts: list[str] = Field(..., min_length=1, max_length=1000, description="List of texts to normalize")
    form: NormalizationForm = Field(..., description="Normalization form (NFC, NFD, NFKC, NFKD)")

    class Config:
        json_schema_extra = {
            "example": {
                "texts": ["café", "naïve"],
                "form": "NFC",
            }
        }


class TransformRequest(BaseModel):
    """Request model for custom ICU transformations."""

    texts: list[str] = Field(..., min_length=1, max_length=1000, description="List of texts to transform")
    transform_spec: str = Field(..., min_length=1, description="ICU transform specification string")

    class Config:
        json_schema_extra = {
            "example": {
                "texts": ["Hello World"],
                "transform_spec": "::Latin-ASCII; ::Lower;",
            }
        }


class CaseMappingRequest(BaseModel):
    """Request model for locale-aware case mapping."""

    texts: list[str] = Field(..., min_length=1, max_length=1000, description="List of texts to transform")
    operation: CaseOperation = Field(..., description="Case operation (upper, lower, title)")
    locale: str = Field(default="en", description="Locale for case mapping (e.g., 'en', 'tr', 'de')")

    class Config:
        json_schema_extra = {
            "example": {
                "texts": ["istanbul"],
                "operation": "upper",
                "locale": "tr",
            }
        }


# Response Models
class TransliterateResponse(BaseModel):
    """Response model for transliteration."""

    results: list[str] = Field(..., description="Transliterated texts")
    transform_id: str = Field(..., description="Transform ID used")
    reverse: bool = Field(..., description="Whether reverse transformation was applied")
    count: int = Field(..., description="Number of texts processed")

    class Config:
        json_schema_extra = {
            "example": {
                "results": ["ヘッロ ウォールド", "コンニチハ"],
                "transform_id": "Latin-Katakana",
                "reverse": False,
                "count": 2,
            }
        }


class NormalizeResponse(BaseModel):
    """Response model for normalization."""

    results: list[str] = Field(..., description="Normalized texts")
    form: str = Field(..., description="Normalization form used")
    count: int = Field(..., description="Number of texts processed")

    class Config:
        json_schema_extra = {
            "example": {
                "results": ["café", "naïve"],
                "form": "NFC",
                "count": 2,
            }
        }


class TransformResponse(BaseModel):
    """Response model for custom transformations."""

    results: list[str] = Field(..., description="Transformed texts")
    transform_spec: str = Field(..., description="Transform specification used")
    count: int = Field(..., description="Number of texts processed")

    class Config:
        json_schema_extra = {
            "example": {
                "results": ["hello world"],
                "transform_spec": "::Latin-ASCII; ::Lower;",
                "count": 1,
            }
        }


class CaseMappingResponse(BaseModel):
    """Response model for case mapping."""

    results: list[str] = Field(..., description="Case-mapped texts")
    operation: str = Field(..., description="Case operation performed")
    locale: str = Field(..., description="Locale used for case mapping")
    count: int = Field(..., description="Number of texts processed")

    class Config:
        json_schema_extra = {
            "example": {
                "results": ["İSTANBUL"],
                "operation": "upper",
                "locale": "tr",
                "count": 1,
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    icu_version: str = Field(..., description="ICU library version")
    cache_size: int = Field(..., description="Number of cached transformers")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error description")
    error_code: str = Field(..., description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Invalid transform ID: InvalidTransform",
                "error_code": "INVALID_TRANSFORM",
                "timestamp": "2025-01-20T12:00:00",
            }
        }


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""

    cached_transforms: list[str] = Field(..., description="List of cached transform IDs")
    total_cached: int = Field(..., description="Total number of cached transformers")
    total_requests: int = Field(..., description="Total requests processed")
    cache_hit_rate: float = Field(..., description="Cache hit rate (0.0 to 1.0)")

    class Config:
        json_schema_extra = {
            "example": {
                "cached_transforms": ["Latin-Katakana", "Any-Latin", "::NFC"],
                "total_cached": 3,
                "total_requests": 150,
                "cache_hit_rate": 0.87,
            }
        }


class SupportedOperationsResponse(BaseModel):
    """Supported operations response."""

    transliterations: list[str] = Field(..., description="Common transliteration transform IDs")
    normalizations: list[str] = Field(..., description="Supported normalization forms")
    case_operations: list[str] = Field(..., description="Supported case operations")
    example_transforms: dict[str, str] = Field(..., description="Example transform specifications")

    class Config:
        json_schema_extra = {
            "example": {
                "transliterations": ["Latin-Katakana", "Any-Latin", "Latin-Cyrillic"],
                "normalizations": ["NFC", "NFD", "NFKC", "NFKD"],
                "case_operations": ["upper", "lower", "title"],
                "example_transforms": {
                    "ascii_folding": "::Latin-ASCII;",
                    "remove_accents": "::NFD; ::[:Nonspacing Mark:] Remove; ::NFC;",
                },
            }
        }
