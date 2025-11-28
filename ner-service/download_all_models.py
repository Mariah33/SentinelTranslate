#!/usr/bin/env python3
"""Download ALL spaCy and Stanza models for volume mounting.

This script downloads all 21 spaCy large models and 60+ Stanza models to a
directory structure suitable for persistent volume mounting in containers.

Usage:
    python download_all_models.py --output-dir /mnt/models
    python download_all_models.py --output-dir /mnt/models --spacy-only
    python download_all_models.py --output-dir /mnt/models --stanza-only
    python download_all_models.py --output-dir /mnt/models --languages en,fr,de
"""

import argparse
import json
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# All 21 spaCy large models (20 languages + 1 multilingual fallback)
SPACY_MODELS = {
    "en_core_web_lg": "https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl",
    "zh_core_web_lg": "https://github.com/explosion/spacy-models/releases/download/zh_core_web_lg-3.8.0/zh_core_web_lg-3.8.0-py3-none-any.whl",
    "hr_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/hr_core_news_lg-3.8.0/hr_core_news_lg-3.8.0-py3-none-any.whl",
    "da_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/da_core_news_lg-3.8.0/da_core_news_lg-3.8.0-py3-none-any.whl",
    "nl_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/nl_core_news_lg-3.8.0/nl_core_news_lg-3.8.0-py3-none-any.whl",
    "fi_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/fi_core_news_lg-3.8.0/fi_core_news_lg-3.8.0-py3-none-any.whl",
    "fr_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/fr_core_news_lg-3.8.0/fr_core_news_lg-3.8.0-py3-none-any.whl",
    "de_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/de_core_news_lg-3.8.0/de_core_news_lg-3.8.0-py3-none-any.whl",
    "el_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/el_core_news_lg-3.8.0/el_core_news_lg-3.8.0-py3-none-any.whl",
    "it_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/it_core_news_lg-3.8.0/it_core_news_lg-3.8.0-py3-none-any.whl",
    "ja_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/ja_core_news_lg-3.8.0/ja_core_news_lg-3.8.0-py3-none-any.whl",
    "ko_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/ko_core_news_lg-3.8.0/ko_core_news_lg-3.8.0-py3-none-any.whl",
    "lt_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/lt_core_news_lg-3.8.0/lt_core_news_lg-3.8.0-py3-none-any.whl",
    "pl_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/pl_core_news_lg-3.8.0/pl_core_news_lg-3.8.0-py3-none-any.whl",
    "pt_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/pt_core_news_lg-3.8.0/pt_core_news_lg-3.8.0-py3-none-any.whl",
    "ro_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/ro_core_news_lg-3.8.0/ro_core_news_lg-3.8.0-py3-none-any.whl",
    "ru_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/ru_core_news_lg-3.8.0/ru_core_news_lg-3.8.0-py3-none-any.whl",
    "sl_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/sl_core_news_lg-3.8.0/sl_core_news_lg-3.8.0-py3-none-any.whl",
    "es_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/es_core_news_lg-3.8.0/es_core_news_lg-3.8.0-py3-none-any.whl",
    "sv_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/sv_core_news_lg-3.8.0/sv_core_news_lg-3.8.0-py3-none-any.whl",
    "uk_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/uk_core_news_lg-3.8.0/uk_core_news_lg-3.8.0-py3-none-any.whl",
    "xx_ent_wiki_sm": "https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.8.0/xx_ent_wiki_sm-3.8.0-py3-none-any.whl",
}

# All 60+ Stanza supported languages
STANZA_LANGUAGES = [
    "af",
    "ar",
    "be",
    "bg",
    "ca",
    "zh",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "et",
    "fi",
    "fr",
    "de",
    "el",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "la",
    "lv",
    "lt",
    "no",
    "fa",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "es",
    "sv",
    "ta",
    "te",
    "th",
    "tr",
    "uk",
    "ur",
    "vi",
    "eu",
    "hy",
    "ga",
    "is",
    "kk",
    "kmr",
    "ky",
    "mr",
    "my",
    "nn",
    "nb",
    "sa",
    "sr",
    "wo",
    "cy",
    "gd",
    "gl",
    "mt",
]


def get_url_size(url: str) -> int | None:
    """Get the size of a remote file without downloading it.

    Args:
        url: URL to check

    Returns:
        Size in bytes, or None if unable to determine
    """
    try:
        request = Request(url, method="HEAD")
        request.add_header(
            "User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        with urlopen(request, timeout=5) as response:
            return int(response.headers.get("Content-Length", 0))
    except Exception as e:
        logger.debug(f"Could not get size for {url}: {e}")
        return None


def format_bytes(bytes_size: int) -> str:
    """Format bytes to human-readable size.

    Args:
        bytes_size: Size in bytes

    Returns:
        Formatted string (e.g., "123.45 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f} TB"


def download_spacy_model(model_name: str, url: str, output_dir: Path) -> bool:
    """Download and extract a spaCy model wheel.

    Args:
        model_name: Model name (e.g., 'en_core_web_lg')
        url: Download URL
        output_dir: Output directory for models

    Returns:
        True if successful, False otherwise
    """
    spacy_dir = output_dir / "spacy"
    spacy_dir.mkdir(parents=True, exist_ok=True)

    model_dir = spacy_dir / model_name
    if model_dir.exists():
        logger.info(f"Skipping {model_name} - already exists at {model_dir}")
        return True

    try:
        logger.info(f"Downloading {model_name}...")
        size = get_url_size(url)
        if size:
            logger.info(f"  Size: {format_bytes(size)}")

        # Download wheel and install to the output directory
        subprocess.run(
            ["python", "-m", "pip", "install", "--target", str(spacy_dir), "--no-deps", url],
            check=True,
            capture_output=True,
            timeout=300,
        )
        logger.info(f"Successfully installed {model_name}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to download {model_name}: {e.stderr.decode()}")
        return False
    except Exception as e:
        logger.error(f"Error downloading {model_name}: {e}")
        return False


def download_stanza_models(languages: list[str], output_dir: Path) -> bool:
    """Download Stanza models for specified languages.

    Args:
        languages: List of language codes (e.g., ['en', 'fr', 'de'])
        output_dir: Output directory for models

    Returns:
        True if all downloads successful, False if any failed
    """
    stanza_dir = output_dir / "stanza"
    stanza_dir.mkdir(parents=True, exist_ok=True)

    # Check if stanza is installed
    try:
        import stanza  # noqa: F401
    except ImportError:
        logger.error("Stanza is not installed. Install with: pip install stanza")
        return False

    all_success = True
    for lang_code in languages:
        lang_dir = stanza_dir / lang_code
        if lang_dir.exists():
            logger.info(f"Skipping {lang_code} - already exists at {lang_dir}")
            continue

        try:
            logger.info(f"Downloading Stanza models for {lang_code}...")
            import stanza

            stanza.download(lang_code, dir=str(stanza_dir), logging_level="ERROR")
            logger.info(f"Successfully downloaded Stanza {lang_code}")
        except Exception as e:
            logger.error(f"Failed to download Stanza {lang_code}: {e}")
            all_success = False

    return all_success


def create_manifest(output_dir: Path, spacy_models: dict, stanza_languages: list) -> None:
    """Create a manifest file documenting downloaded models.

    Args:
        output_dir: Output directory
        spacy_models: Dictionary of spaCy models
        stanza_languages: List of Stanza language codes
    """
    manifest = {
        "spacy": {
            "models": list(spacy_models.keys()),
            "count": len(spacy_models),
            "version": "3.8.0",
        },
        "stanza": {
            "languages": stanza_languages,
            "count": len(stanza_languages),
        },
        "total_models": len(spacy_models) + len(stanza_languages),
        "structure": {
            "spacy": "output_dir/spacy/{model_name}/",
            "stanza": "output_dir/stanza/{lang_code}/",
        },
    }

    manifest_file = output_dir / "MANIFEST.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Created manifest at {manifest_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download ALL spaCy and Stanza models for volume mounting"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for models (e.g., /mnt/models)",
    )
    parser.add_argument("--spacy-only", action="store_true", help="Download only spaCy models")
    parser.add_argument("--stanza-only", action="store_true", help="Download only Stanza models")
    parser.add_argument(
        "--languages", type=str, help="Comma-separated list of languages (e.g., en,fr,de)"
    )
    parser.add_argument(
        "--max-workers", type=int, default=4, help="Maximum parallel downloads (default: 4)"
    )

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Using output directory: {args.output_dir}")

    # Determine what to download
    download_spacy = not args.stanza_only
    download_stanza = not args.spacy_only

    # Determine which languages to download
    if args.languages:
        requested_languages = [lang.strip() for lang in args.languages.split(",")]
        stanza_languages = [lang for lang in requested_languages if lang in STANZA_LANGUAGES]
        spacy_models = {
            k: v for k, v in SPACY_MODELS.items() if any(lang in k for lang in requested_languages)
        }
    else:
        stanza_languages = STANZA_LANGUAGES
        spacy_models = SPACY_MODELS

    # Download spaCy models
    if download_spacy and spacy_models:
        logger.info(f"\nDownloading {len(spacy_models)} spaCy models...")
        success_count = 0

        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(download_spacy_model, name, url, args.output_dir): name
                for name, url in spacy_models.items()
            }

            for future in as_completed(futures):
                model_name = futures[future]
                try:
                    if future.result():
                        success_count += 1
                except Exception as e:
                    logger.error(f"Exception downloading {model_name}: {e}")

        logger.info(f"spaCy: {success_count}/{len(spacy_models)} models downloaded")

    # Download Stanza models
    if download_stanza and stanza_languages:
        logger.info(f"\nDownloading {len(stanza_languages)} Stanza models...")
        if download_stanza_models(stanza_languages, args.output_dir):
            logger.info(f"Stanza: All {len(stanza_languages)} models downloaded")
        else:
            logger.warning("Some Stanza models failed to download")

    # Create manifest
    if (download_spacy and spacy_models) or (download_stanza and stanza_languages):
        create_manifest(args.output_dir, spacy_models, stanza_languages)

    logger.info("\nDownload complete!")
    logger.info(f"Models stored at: {args.output_dir}")
    logger.info("Ready to mount as volume in containers")


if __name__ == "__main__":
    main()
