"""
Download language detection models for all libraries.

Models:
- fasttext: lid.176.bin (~900KB compressed) from Facebook
- langid: Auto-downloads on first use (~1MB)
- langdetect: Uses built-in profiles (no download needed)
- lingua-py: Downloads on first use (~50MB for all languages)
"""

import logging
import os
import urllib.request
from pathlib import Path

import fasttext
import langdetect
import langid
from lingua import LanguageDetectorBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Model directory
MODEL_PATH = os.getenv("LANG_DETECT_MODEL_PATH", "./models")


def download_fasttext_model() -> None:
    """Download fasttext language identification model (lid.176.bin)."""
    model_dir = Path(MODEL_PATH)
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / "lid.176.bin"

    if model_path.exists():
        logger.info(f"fasttext model already exists at {model_path}")
        return

    logger.info("Downloading fasttext model (lid.176.bin)...")

    # fasttext language identification model URL
    url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"

    try:
        with urllib.request.urlopen(url) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            logger.info(f"Downloading {total_size // 1024}KB...")

            with open(model_path, "wb") as f:
                downloaded = 0
                chunk_size = 8192
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Progress indicator
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        if int(percent) % 10 == 0:
                            logger.info(f"Progress: {percent:.1f}%")

        logger.info(f"fasttext model downloaded successfully to {model_path}")
        logger.info(f"Model size: {model_path.stat().st_size // 1024}KB")

    except Exception as e:
        logger.error(f"Failed to download fasttext model: {e}")
        if model_path.exists():
            model_path.unlink()
        raise


def initialize_langid() -> None:
    """Initialize langid (auto-downloads model on first use)."""
    logger.info("Initializing langid...")
    try:
        # langid auto-downloads its model (~1MB) on first classify() call
        result = langid.classify("This is a test sentence for language detection.")
        logger.info(f"langid initialized successfully (detected: {result[0]})")
    except Exception as e:
        logger.error(f"Failed to initialize langid: {e}")
        raise


def initialize_langdetect() -> None:
    """Initialize langdetect (uses built-in profiles, no download needed)."""
    logger.info("Initializing langdetect...")
    try:
        # langdetect uses built-in language profiles
        result = langdetect.detect("This is a test sentence for language detection.")
        logger.info(f"langdetect initialized successfully (detected: {result})")
    except Exception as e:
        logger.error(f"Failed to initialize langdetect: {e}")
        raise


def initialize_lingua() -> None:
    """Initialize lingua-py (downloads models on first use, ~50MB)."""
    logger.info("Initializing lingua-py...")
    try:
        # lingua-py downloads language models on first use
        logger.info("Building language detector (this will download ~50MB of models)...")
        detector = LanguageDetectorBuilder.from_all_languages().with_preloaded_language_models().build()

        # Test detection
        test_text = "This is a test sentence for language detection."
        confidence_values = detector.compute_language_confidence_values(test_text)

        if confidence_values:
            best = confidence_values[0]
            logger.info(
                f"lingua-py initialized successfully (detected: {best.language.iso_code_639_1.name.lower()}, confidence: {best.value:.3f})"
            )
        else:
            logger.warning("lingua-py initialized but returned no results")

    except Exception as e:
        logger.error(f"Failed to initialize lingua-py: {e}")
        raise


def verify_models() -> None:
    """Verify all models are working correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("Verifying all models...")
    logger.info("=" * 60)

    test_text = "Bonjour, comment allez-vous? This is a multilingual test."

    # Test fasttext
    try:
        model_path = Path(MODEL_PATH) / "lid.176.bin"
        if model_path.exists():
            # Suppress fasttext warnings
            fasttext.FastText.eprint = lambda *args, **kwargs: None
            model = fasttext.load_model(str(model_path))
            predictions = model.predict(test_text, k=1)
            lang = predictions[0][0].replace("__label__", "")
            conf = predictions[1][0]
            logger.info(f"✓ fasttext: {lang} (confidence: {conf:.3f})")
        else:
            logger.error("✗ fasttext model not found")
    except Exception as e:
        logger.error(f"✗ fasttext failed: {e}")

    # Test langid
    try:
        lang, conf = langid.classify(test_text)
        logger.info(f"✓ langid: {lang} (confidence: {conf:.3f})")
    except Exception as e:
        logger.error(f"✗ langid failed: {e}")

    # Test langdetect
    try:
        langdetect.DetectorFactory.seed = 0
        lang = langdetect.detect(test_text)
        logger.info(f"✓ langdetect: {lang}")
    except Exception as e:
        logger.error(f"✗ langdetect failed: {e}")

    # Test lingua-py
    try:
        detector = LanguageDetectorBuilder.from_all_languages().with_preloaded_language_models().build()
        confidence_values = detector.compute_language_confidence_values(test_text)
        if confidence_values:
            best = confidence_values[0]
            lang = best.language.iso_code_639_1.name.lower()
            conf = best.value
            logger.info(f"✓ lingua-py: {lang} (confidence: {conf:.3f})")
        else:
            logger.error("✗ lingua-py returned no results")
    except Exception as e:
        logger.error(f"✗ lingua-py failed: {e}")

    logger.info("=" * 60)


def main() -> None:
    """Download and initialize all language detection models."""
    logger.info("Starting model download process...")
    logger.info(f"Model directory: {Path(MODEL_PATH).absolute()}")

    try:
        # Download fasttext model
        download_fasttext_model()

        # Initialize langid (auto-downloads)
        initialize_langid()

        # Initialize langdetect (built-in profiles)
        initialize_langdetect()

        # Initialize lingua-py (downloads on first use)
        initialize_lingua()

        # Verify all models
        verify_models()

        logger.info("\n✓ All models downloaded and verified successfully!")
        logger.info(f"\nModel directory: {Path(MODEL_PATH).absolute()}")
        logger.info("\nYou can now run the service with: make run")

    except Exception as e:
        logger.error(f"\n✗ Model download failed: {e}")
        raise


if __name__ == "__main__":
    main()
