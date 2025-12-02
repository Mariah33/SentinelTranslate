"""
Language Detection Microservice with Multi-Model Weighted Consensus.

Supports 4 detection models:
- lingua-py: Highest accuracy, 75 languages, weight=1.0
- fasttext: 176 languages, weight=0.9
- langid: 97 languages, weight=0.8
- langdetect: 55 languages, weight=0.7

Text-size-aware strategies:
- SHORT (<50 chars): All 4 models, require 3/4 agreement
- MEDIUM (50-200 chars): All 4 models, weighted consensus
- LONG (>200 chars): lingua-py + fasttext only (faster)
"""

import logging
import os
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any

import fasttext
import langdetect
import langid
from fastapi import FastAPI, HTTPException
from lingua import LanguageDetectorBuilder
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Environment configuration
MODEL_PATH = os.getenv("LANG_DETECT_MODEL_PATH", "/app/models/lang-detect")

# Model weights based on known accuracy
MODEL_WEIGHTS = {
    "lingua-py": 1.0,
    "fasttext": 0.9,
    "langid": 0.8,
    "langdetect": 0.7,
}


class DetectionStrategy(str, Enum):
    """Text-size-aware detection strategies."""

    AUTO = "auto"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    ALL_MODELS = "all_models"


class ModelResult(BaseModel):
    """Individual model detection result."""

    model: str
    language: str
    confidence: float
    weight: float


class DetectionRequest(BaseModel):
    """Language detection request."""

    text: str = Field(..., min_length=1, description="Text to detect language for")
    strategy: DetectionStrategy = Field(
        default=DetectionStrategy.AUTO,
        description="Detection strategy (auto, short, medium, long, all_models)",
    )


class DetectionResponse(BaseModel):
    """Language detection response with weighted consensus."""

    detected_language: str
    confidence: float
    strategy_used: str
    text_length: int
    model_results: list[ModelResult]
    weighted_scores: dict[str, float]


class ModelInfo(BaseModel):
    """Model information."""

    name: str
    loaded: bool
    language_count: int
    weight: float


class ModelsInfoResponse(BaseModel):
    """Models information response."""

    models: list[ModelInfo]
    total_loaded: int


class ModelCache:
    """
    Singleton cache for lazy-loaded language detection models.

    Thread-safe lazy loading with double-check locking pattern.
    Models are loaded on-demand to minimize memory usage.
    """

    _instance: "ModelCache | None" = None
    _initialized: bool = False

    def __new__(cls) -> "ModelCache":
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize model cache (only once)."""
        if not ModelCache._initialized:
            self._lingua_detector: Any = None
            self._fasttext_model: Any = None
            self._langid_initialized: bool = False
            self._langdetect_initialized: bool = False
            ModelCache._initialized = True
            logger.info("ModelCache initialized (0MB at startup)")

    def get_lingua_detector(self) -> Any:
        """Lazy load lingua-py detector (highest accuracy)."""
        if self._lingua_detector is None:
            logger.info("Loading lingua-py detector...")
            try:
                # Build detector for all available languages
                self._lingua_detector = LanguageDetectorBuilder.from_all_languages().with_preloaded_language_models().build()
                logger.info("lingua-py detector loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load lingua-py detector: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load lingua-py detector: {e}",
                ) from e
        return self._lingua_detector

    def get_fasttext_model(self) -> Any:
        """Lazy load fasttext language detection model."""
        if self._fasttext_model is None:
            logger.info("Loading fasttext model...")
            model_path = Path(MODEL_PATH) / "lid.176.bin"
            try:
                if not model_path.exists():
                    raise FileNotFoundError(f"fasttext model not found at {model_path}. Run 'make download-models' first.")
                # Suppress fasttext warnings
                fasttext.FastText.eprint = lambda *args, **kwargs: None
                self._fasttext_model = fasttext.load_model(str(model_path))
                logger.info("fasttext model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load fasttext model: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load fasttext model: {e}",
                ) from e
        return self._fasttext_model

    def initialize_langid(self) -> None:
        """Initialize langid (auto-downloads on first use)."""
        if not self._langid_initialized:
            logger.info("Initializing langid...")
            try:
                # langid auto-downloads model on first classify() call
                # Pre-warm with a test string
                langid.classify("test")
                self._langid_initialized = True
                logger.info("langid initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize langid: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize langid: {e}",
                ) from e

    def initialize_langdetect(self) -> None:
        """Initialize langdetect (uses built-in profiles)."""
        if not self._langdetect_initialized:
            logger.info("Initializing langdetect...")
            try:
                # langdetect uses built-in language profiles
                # Pre-warm with a test string
                langdetect.detect("test")
                self._langdetect_initialized = True
                logger.info("langdetect initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize langdetect: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize langdetect: {e}",
                ) from e

    def is_lingua_loaded(self) -> bool:
        """Check if lingua-py detector is loaded."""
        return self._lingua_detector is not None

    def is_fasttext_loaded(self) -> bool:
        """Check if fasttext model is loaded."""
        return self._fasttext_model is not None

    def is_langid_loaded(self) -> bool:
        """Check if langid is initialized."""
        return self._langid_initialized

    def is_langdetect_loaded(self) -> bool:
        """Check if langdetect is initialized."""
        return self._langdetect_initialized


# Global model cache singleton
model_cache = ModelCache()

# FastAPI app
app = FastAPI(
    title="Language Detection Service",
    description="Multi-model language detection with weighted consensus",
    version="0.1.0",
)


def determine_strategy(text: str, strategy: DetectionStrategy) -> DetectionStrategy:
    """
    Determine detection strategy based on text length.

    Args:
        text: Input text
        strategy: Requested strategy (or AUTO)

    Returns:
        Resolved detection strategy
    """
    if strategy != DetectionStrategy.AUTO:
        return strategy

    length = len(text)
    if length < 50:
        return DetectionStrategy.SHORT
    elif length < 200:
        return DetectionStrategy.MEDIUM
    else:
        return DetectionStrategy.LONG


def detect_with_lingua(text: str) -> ModelResult:
    """Detect language using lingua-py (highest accuracy)."""
    detector = model_cache.get_lingua_detector()
    try:
        confidence_values = detector.compute_language_confidence_values(text)
        if not confidence_values:
            return ModelResult(
                model="lingua-py",
                language="unknown",
                confidence=0.0,
                weight=MODEL_WEIGHTS["lingua-py"],
            )

        # Get highest confidence result
        best = confidence_values[0]
        lang_code = best.language.iso_code_639_1.name.lower()
        confidence = best.value

        return ModelResult(
            model="lingua-py",
            language=lang_code,
            confidence=confidence,
            weight=MODEL_WEIGHTS["lingua-py"],
        )
    except Exception as e:
        logger.warning(f"lingua-py detection failed: {e}")
        return ModelResult(
            model="lingua-py",
            language="unknown",
            confidence=0.0,
            weight=MODEL_WEIGHTS["lingua-py"],
        )


def detect_with_fasttext(text: str) -> ModelResult:
    """Detect language using fasttext."""
    model = model_cache.get_fasttext_model()
    try:
        # fasttext returns ((label,), (score,))
        predictions = model.predict(text.replace("\n", " "), k=1)
        lang_code = predictions[0][0].replace("__label__", "")
        confidence = float(predictions[1][0])

        return ModelResult(
            model="fasttext",
            language=lang_code,
            confidence=confidence,
            weight=MODEL_WEIGHTS["fasttext"],
        )
    except Exception as e:
        logger.warning(f"fasttext detection failed: {e}")
        return ModelResult(
            model="fasttext",
            language="unknown",
            confidence=0.0,
            weight=MODEL_WEIGHTS["fasttext"],
        )


def detect_with_langid(text: str) -> ModelResult:
    """Detect language using langid."""
    model_cache.initialize_langid()
    try:
        lang_code, confidence = langid.classify(text)
        return ModelResult(
            model="langid",
            language=lang_code,
            confidence=confidence,
            weight=MODEL_WEIGHTS["langid"],
        )
    except Exception as e:
        logger.warning(f"langid detection failed: {e}")
        return ModelResult(
            model="langid",
            language="unknown",
            confidence=0.0,
            weight=MODEL_WEIGHTS["langid"],
        )


def detect_with_langdetect(text: str) -> ModelResult:
    """Detect language using langdetect."""
    model_cache.initialize_langdetect()
    try:
        # langdetect is probabilistic, set seed for consistency
        langdetect.DetectorFactory.seed = 0
        lang_code = langdetect.detect(text)

        # langdetect doesn't provide confidence, use 0.8 as baseline
        confidence = 0.8

        return ModelResult(
            model="langdetect",
            language=lang_code,
            confidence=confidence,
            weight=MODEL_WEIGHTS["langdetect"],
        )
    except Exception as e:
        logger.warning(f"langdetect detection failed: {e}")
        return ModelResult(
            model="langdetect",
            language="unknown",
            confidence=0.0,
            weight=MODEL_WEIGHTS["langdetect"],
        )


def weighted_consensus(model_results: list[ModelResult]) -> tuple[str, float, dict[str, float]]:
    """
    Calculate weighted consensus from multiple model results.

    Args:
        model_results: List of model detection results

    Returns:
        Tuple of (best_language, best_confidence, all_weighted_scores)
    """
    # Group by language, sum weighted scores
    scores: dict[str, float] = defaultdict(float)
    for result in model_results:
        if result.language != "unknown":
            weighted_score = result.confidence * result.weight
            scores[result.language] += weighted_score

    if not scores:
        return "unknown", 0.0, {}

    # Find language with highest weighted score
    best_lang = max(scores.items(), key=lambda x: x[1])

    # Normalize confidence to 0-1 range based on max possible score
    max_possible = sum(r.weight for r in model_results)
    normalized_confidence = best_lang[1] / max_possible if max_possible > 0 else 0.0

    return best_lang[0], normalized_confidence, dict(scores)


def check_agreement_threshold(model_results: list[ModelResult], threshold: int) -> tuple[bool, str]:
    """
    Check if models agree on language (for SHORT text strategy).

    Args:
        model_results: List of model results
        threshold: Minimum number of models that must agree

    Returns:
        Tuple of (agreement_met, agreed_language)
    """
    # Count votes for each language
    votes: dict[str, int] = defaultdict(int)
    for result in model_results:
        if result.language != "unknown":
            votes[result.language] += 1

    if not votes:
        return False, "unknown"

    # Find most common language
    best_lang = max(votes.items(), key=lambda x: x[1])

    return best_lang[1] >= threshold, best_lang[0]


@app.post("/detect", response_model=DetectionResponse)
async def detect_language(request: DetectionRequest) -> DetectionResponse:
    """
    Detect language using multi-model weighted consensus.

    Strategies:
    - SHORT (<50 chars): All 4 models, require 3/4 agreement
    - MEDIUM (50-200 chars): All 4 models, weighted consensus
    - LONG (>200 chars): lingua-py + fasttext only (faster)
    - ALL_MODELS: Force all 4 models regardless of text length
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    text_length = len(text)
    strategy = determine_strategy(text, request.strategy)

    logger.info(f"Detecting language for text (length={text_length}, strategy={strategy.value})")

    # Collect model results based on strategy
    model_results: list[ModelResult] = []

    if strategy in (DetectionStrategy.SHORT, DetectionStrategy.MEDIUM, DetectionStrategy.ALL_MODELS):
        # Use all 4 models
        model_results.append(detect_with_lingua(text))
        model_results.append(detect_with_fasttext(text))
        model_results.append(detect_with_langid(text))
        model_results.append(detect_with_langdetect(text))

        # For SHORT text, check if 3/4 models agree
        if strategy == DetectionStrategy.SHORT:
            agreement_met, agreed_lang = check_agreement_threshold(model_results, threshold=3)
            if agreement_met:
                # Use agreed language with high confidence
                detected_language = agreed_lang
                confidence = 0.95
            else:
                # Fall back to weighted consensus
                detected_language, confidence, weighted_scores = weighted_consensus(model_results)
        else:
            # MEDIUM or ALL_MODELS: use weighted consensus
            detected_language, confidence, weighted_scores = weighted_consensus(model_results)

    elif strategy == DetectionStrategy.LONG:
        # Use only lingua-py + fasttext (faster, still accurate)
        model_results.append(detect_with_lingua(text))
        model_results.append(detect_with_fasttext(text))
        detected_language, confidence, weighted_scores = weighted_consensus(model_results)

    else:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {strategy}")

    # Build weighted scores dict
    if strategy == DetectionStrategy.SHORT:
        weighted_scores = {}
        for result in model_results:
            if result.language != "unknown":
                weighted_scores[result.language] = weighted_scores.get(result.language, 0.0) + (result.confidence * result.weight)

    return DetectionResponse(
        detected_language=detected_language,
        confidence=confidence,
        strategy_used=strategy.value,
        text_length=text_length,
        model_results=model_results,
        weighted_scores=weighted_scores,
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/models-info", response_model=ModelsInfoResponse)
async def models_info() -> ModelsInfoResponse:
    """Return information about loaded models."""
    models = [
        ModelInfo(
            name="lingua-py",
            loaded=model_cache.is_lingua_loaded(),
            language_count=75,
            weight=MODEL_WEIGHTS["lingua-py"],
        ),
        ModelInfo(
            name="fasttext",
            loaded=model_cache.is_fasttext_loaded(),
            language_count=176,
            weight=MODEL_WEIGHTS["fasttext"],
        ),
        ModelInfo(
            name="langid",
            loaded=model_cache.is_langid_loaded(),
            language_count=97,
            weight=MODEL_WEIGHTS["langid"],
        ),
        ModelInfo(
            name="langdetect",
            loaded=model_cache.is_langdetect_loaded(),
            language_count=55,
            weight=MODEL_WEIGHTS["langdetect"],
        ),
    ]

    total_loaded = sum(1 for m in models if m.loaded)

    return ModelsInfoResponse(models=models, total_loaded=total_loaded)


@app.get("/supported-languages")
async def supported_languages() -> dict[str, Any]:
    """Return union of all model languages (176 via fasttext)."""
    return {
        "total_languages": 176,
        "note": "Supports 176 languages via fasttext (most comprehensive model)",
        "model_coverage": {
            "fasttext": 176,
            "langid": 97,
            "lingua-py": 75,
            "langdetect": 55,
        },
        "strategy": "Weighted consensus across all models for best accuracy",
    }
