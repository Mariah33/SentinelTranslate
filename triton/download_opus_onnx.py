#!/usr/bin/env python3
"""
OPUS-MT ONNX Model Downloader

Downloads pre-converted ONNX models from Hugging Face Hub.
Supports both official ONNX releases and community conversions.

Usage:
    # Download single language
    python download_opus_onnx.py --language fr

    # Download specific languages
    python download_opus_onnx.py --languages fr,de,es,it

    # Download all available ONNX models
    python download_opus_onnx.py --all

    # Download with parallel workers
    python download_opus_onnx.py --all --workers 4
"""

import argparse
import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from huggingface_hub.utils import HfHubHTTPError, RepositoryNotFoundError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# All 41 OPUS-MT language pairs (source → English)
SUPPORTED_LANGUAGES = [
    "ar",
    "bg",
    "bn",
    "cs",
    "da",
    "de",
    "el",
    "es",
    "et",
    "fa",
    "fi",
    "fr",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "lt",
    "lv",
    "ms",
    "nl",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "sr",
    "sv",
    "ta",
    "te",
    "th",
    "tr",
    "uk",
    "ur",
    "vi",
    "zh",
]


@dataclass
class DownloadResult:
    """Result of a model download."""

    language: str
    success: bool
    duration_seconds: float
    source: str | None = None  # 'official-onnx', 'pytorch', 'community'
    error_message: str| None = None
    model_path: Path| None = None


def check_onnx_model_exists(model_name: str, api: HfApi) -> str | None:
    """
    Check if official ONNX version exists on Hugging Face Hub.

    Args:
        model_name: Model name without prefix (e.g., 'opus-mt-fr-en')
        api: HuggingFace API client

    Returns:
        Repository ID if ONNX model exists, None otherwise
    """
    # Try multiple ONNX naming patterns
    patterns = [
        f"Helsinki-NLP/{model_name}-onnx",
        f"optimum/{model_name}",
        f"onnx/{model_name}",
    ]

    for repo_id in patterns:
        try:
            api.repo_info(repo_id=repo_id, repo_type="model")
            logger.debug(f"  Found ONNX model at {repo_id}")
            return repo_id
        except (RepositoryNotFoundError, HfHubHTTPError):
            continue

    return None


def download_onnx_model(
    src_lang: str,
    tgt_lang: str,
    output_dir: Path,
    skip_existing: bool = True,
    hf_token: str| None = None,
) -> DownloadResult:
    """
    Download pre-converted ONNX model from Hugging Face Hub.

    Args:
        src_lang: Source language code (e.g., 'fr')
        tgt_lang: Target language code (e.g., 'en')
        output_dir: Root output directory (e.g., 'model-repository/')
        skip_existing: Skip download if model already exists
        hf_token: Hugging Face API token (optional)

    Returns:
        DownloadResult with status and metadata
    """
    start_time = time.time()
    model_name = f"opus-mt-{src_lang}-{tgt_lang}"
    hf_model_name = f"Helsinki-NLP/{model_name}"

    # Create Triton-compatible directory structure
    model_dir = output_dir / model_name
    version_dir = model_dir / "1"

    # Check if already downloaded
    if skip_existing and version_dir.exists():
        onnx_files = list(version_dir.glob("*.onnx"))
        if onnx_files:
            logger.info(f"✓ Skipping {model_name} (already exists)")
            return DownloadResult(
                language=src_lang,
                success=True,
                duration_seconds=time.time() - start_time,
                source="cached",
                model_path=version_dir,
            )

    logger.info(f"Downloading {model_name}...")

    try:
        api = HfApi(token=hf_token)

        # Try to find official ONNX version
        onnx_repo = check_onnx_model_exists(model_name, api)

        if onnx_repo:
            # Download official ONNX model
            logger.debug(f"  Downloading ONNX model from {onnx_repo}")
            version_dir.mkdir(parents=True, exist_ok=True)

            # Download entire repository
            snapshot_download(
                repo_id=onnx_repo,
                local_dir=version_dir,
                local_dir_use_symlinks=False,
                token=hf_token,
            )

            source = "official-onnx"
            logger.info(f"✓ Downloaded {model_name} from official ONNX repository")

        else:
            # No ONNX version available - download PyTorch and note conversion needed
            logger.warning(f"  No ONNX version found for {model_name}")
            logger.warning(f"  Please run: python convert_opus_to_onnx.py --language {src_lang}")

            return DownloadResult(
                language=src_lang,
                success=False,
                duration_seconds=time.time() - start_time,
                error_message=f"No ONNX model available - conversion required",
            )

        duration = time.time() - start_time

        return DownloadResult(
            language=src_lang,
            success=True,
            duration_seconds=duration,
            source=source,
            model_path=version_dir,
        )

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Failed to download {model_name}: {e}"
        logger.error(f"✗ {error_msg}")

        # Clean up partial download
        if version_dir.exists():
            shutil.rmtree(version_dir)
            logger.debug(f"  Cleaned up partial download at {version_dir}")

        return DownloadResult(
            language=src_lang,
            success=False,
            duration_seconds=duration,
            error_message=error_msg,
        )


def download_language_wrapper(args: tuple[str, str, Path, bool, str]) -> DownloadResult:
    """
    Wrapper for parallel download.

    Args:
        args: Tuple of (src_lang, tgt_lang, output_dir, skip_existing, hf_token)

    Returns:
        DownloadResult
    """
    return download_onnx_model(*args)


def download_multiple_languages(
    languages: list[str],
    tgt_lang: str,
    output_dir: Path,
    skip_existing: bool = True,
    workers: int = 1,
    hf_token: str | None = None,
) -> list[DownloadResult]:
    """
    Download multiple ONNX models in parallel.

    Args:
        languages: List of source language codes
        tgt_lang: Target language code (default: 'en')
        output_dir: Root output directory
        skip_existing: Skip already downloaded models
        workers: Number of parallel workers (1 = sequential)
        hf_token: Hugging Face API token

    Returns:
        List of DownloadResult objects
    """
    results: list[DownloadResult] = []
    total = len(languages)

    logger.info(f"Downloading {total} language pairs with {workers} workers")

    if workers == 1:
        # Sequential download
        for i, src_lang in enumerate(languages, 1):
            logger.info(f"[{i}/{total}] Processing {src_lang}-{tgt_lang}")
            result = download_onnx_model(src_lang, tgt_lang, output_dir, skip_existing, hf_token)
            results.append(result)
    else:
        # Parallel download (I/O bound, so ThreadPoolExecutor is efficient)
        download_args = [(lang, tgt_lang, output_dir, skip_existing, hf_token) for lang in languages]

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(download_language_wrapper, args): args[0] for args in download_args}

            for i, future in enumerate(as_completed(futures), 1):
                src_lang = futures[future]
                logger.info(f"[{i}/{total}] Completed {src_lang}-{tgt_lang}")
                result = future.result()
                results.append(result)

    return results


def print_summary(results: list[DownloadResult]) -> None:
    """Print download summary report."""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    need_conversion = [r for r in failed if "conversion required" in (r.error_message or "")]

    total_time = sum(r.duration_seconds for r in results)
    avg_time = total_time / len(results) if results else 0

    print("\n" + "=" * 70)
    print("DOWNLOAD SUMMARY")
    print("=" * 70)
    print(f"Total models:     {len(results)}")
    print(f"Downloaded:       {len(successful)} ✓")
    print(f"Need conversion:  {len(need_conversion)} ⚠")
    print(f"Failed:           {len(failed) - len(need_conversion)} ✗")
    print(f"Total time:       {total_time:.1f}s")
    print(f"Average time:     {avg_time:.1f}s per model")
    print("=" * 70)

    if successful:
        print(f"\n✓ Successfully downloaded {len(successful)} models:")
        for result in successful:
            source_label = f"[{result.source}]" if result.source else ""
            print(f"  - {result.language} ({result.duration_seconds:.1f}s) {source_label}")

    if need_conversion:
        print(f"\n⚠ Need conversion ({len(need_conversion)}):")
        print("  Run: python convert_opus_to_onnx.py --languages " + ",".join(r.language for r in need_conversion))
        for result in need_conversion:
            print(f"  - {result.language}")

    if failed and len(failed) > len(need_conversion):
        print(f"\n✗ Failed downloads ({len(failed) - len(need_conversion)}):")
        for result in failed:
            if "conversion required" not in (result.error_message or ""):
                print(f"  - {result.language}: {result.error_message}")

    print()


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Download pre-converted ONNX OPUS-MT models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download French model
  python download_opus_onnx.py --language fr

  # Download multiple languages with 4 workers
  python download_opus_onnx.py --languages fr,de,es,it --workers 4

  # Download all available ONNX models
  python download_opus_onnx.py --all --workers 8

  # List supported languages
  python download_opus_onnx.py --list-languages
        """,
    )

    parser.add_argument(
        "--language",
        type=str,
        help="Single language code to download (e.g., 'fr')",
    )

    parser.add_argument(
        "--languages",
        type=str,
        help="Comma-separated language codes (e.g., 'fr,de,es')",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help=f"Download all {len(SUPPORTED_LANGUAGES)} supported language pairs",
    )

    parser.add_argument(
        "--list-languages",
        action="store_true",
        help="List all supported language codes and exit",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("model-repository"),
        help="Output directory for models (default: model-repository/)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel download workers (default: 1)",
    )

    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-download models even if they already exist",
    )

    parser.add_argument(
        "--target-lang",
        type=str,
        default="en",
        help="Target language code (default: en)",
    )

    parser.add_argument(
        "--hf-token",
        type=str,
        help="Hugging Face API token (for private models)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Handle --list-languages
    if args.list_languages:
        print(f"Supported language codes ({len(SUPPORTED_LANGUAGES)}):")
        for i, lang in enumerate(SUPPORTED_LANGUAGES, 1):
            print(f"  {i:2d}. {lang}")
        return

    # Determine which languages to download
    languages_to_download: list[str] = []

    if args.all:
        languages_to_download = SUPPORTED_LANGUAGES
    elif args.languages:
        languages_to_download = [lang.strip() for lang in args.languages.split(",")]
    elif args.language:
        languages_to_download = [args.language]
    else:
        parser.error("Must specify --language, --languages, or --all")

    # Validate language codes
    invalid_languages = [lang for lang in languages_to_download if lang not in SUPPORTED_LANGUAGES]
    if invalid_languages:
        logger.error(f"Invalid language codes: {', '.join(invalid_languages)}")
        logger.info(f"Supported languages: {', '.join(SUPPORTED_LANGUAGES)}")
        return

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {args.output_dir.absolute()}")

    # Run downloads
    start_time = time.time()
    results = download_multiple_languages(
        languages=languages_to_download,
        tgt_lang=args.target_lang,
        output_dir=args.output_dir,
        skip_existing=not args.no_skip_existing,
        workers=args.workers,
        hf_token=args.hf_token,
    )
    total_time = time.time() - start_time

    # Print summary
    print_summary(results)

    # Exit with warning if any downloads failed (but don't error for conversion needed)
    failed_count = sum(1 for r in results if not r.success and "conversion required" not in (r.error_message or ""))
    if failed_count > 0:
        exit(1)


if __name__ == "__main__":
    main()
