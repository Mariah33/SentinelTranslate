#!/usr/bin/env python3
"""
OPUS-MT to ONNX Converter

Converts PyTorch OPUS-MT models to ONNX format for secure Triton deployment.
Eliminates torch.load() vulnerabilities while maintaining translation quality.

Usage:
    # Convert single language
    python convert_opus_to_onnx.py --language fr

    # Convert specific languages
    python convert_opus_to_onnx.py --languages fr,de,es,it

    # Convert all 41 supported languages
    python convert_opus_to_onnx.py --all

    # Parallel conversion with validation
    python convert_opus_to_onnx.py --all --workers 4 --validate
"""

import argparse
import logging
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import onnx
from optimum.onnxruntime import ORTModelForSeq2SeqLM
from transformers import AutoTokenizer

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
class ConversionResult:
    """Result of a model conversion."""

    language: str
    success: bool
    duration_seconds: float
    error_message: Optional[str] = None
    model_path: Optional[Path] = None


def convert_opus_mt_to_onnx(
    src_lang: str,
    tgt_lang: str,
    output_dir: Path,
    validate: bool = False,
    skip_existing: bool = True,
) -> ConversionResult:
    """
    Convert OPUS-MT model from PyTorch to ONNX format.

    Args:
        src_lang: Source language code (e.g., 'fr')
        tgt_lang: Target language code (e.g., 'en')
        output_dir: Root output directory (e.g., 'model-repository/')
        validate: Run ONNX model validation after conversion
        skip_existing: Skip conversion if model already exists

    Returns:
        ConversionResult with status and metadata
    """
    start_time = time.time()
    model_name = f"opus-mt-{src_lang}-{tgt_lang}"
    hf_model_name = f"Helsinki-NLP/{model_name}"

    # Create Triton-compatible directory structure
    model_dir = output_dir / model_name
    version_dir = model_dir / "1"

    # Check if already converted
    if skip_existing and version_dir.exists():
        onnx_files = list(version_dir.glob("*.onnx"))
        if onnx_files:
            logger.info(f"✓ Skipping {model_name} (already exists)")
            return ConversionResult(
                language=src_lang,
                success=True,
                duration_seconds=time.time() - start_time,
                model_path=version_dir,
            )

    logger.info(f"Converting {model_name}...")

    try:
        # Create output directory
        version_dir.mkdir(parents=True, exist_ok=True)

        # Load tokenizer
        logger.debug(f"  Loading tokenizer for {hf_model_name}")
        tokenizer = AutoTokenizer.from_pretrained(hf_model_name)

        # Convert to ONNX using Optimum
        logger.debug(f"  Converting {hf_model_name} to ONNX (this may take 2-5 minutes)")
        ort_model = ORTModelForSeq2SeqLM.from_pretrained(
            hf_model_name,
            export=True,  # Triggers PyTorch → ONNX conversion
            provider="CPUExecutionProvider",
        )

        # Save ONNX model + tokenizer
        logger.debug(f"  Saving ONNX model to {version_dir}")
        ort_model.save_pretrained(version_dir)
        tokenizer.save_pretrained(version_dir)

        # Validate ONNX models
        if validate:
            logger.debug(f"  Validating ONNX models")
            onnx_files = list(version_dir.glob("*.onnx"))
            for onnx_path in onnx_files:
                onnx_model = onnx.load(str(onnx_path))
                onnx.checker.check_model(onnx_model)
                logger.debug(f"    ✓ {onnx_path.name} is valid")

        duration = time.time() - start_time
        logger.info(f"✓ Converted {model_name} in {duration:.1f}s")

        return ConversionResult(
            language=src_lang,
            success=True,
            duration_seconds=duration,
            model_path=version_dir,
        )

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Failed to convert {model_name}: {e}"
        logger.error(f"✗ {error_msg}")

        # Clean up partial conversion
        if version_dir.exists():
            shutil.rmtree(version_dir)
            logger.debug(f"  Cleaned up partial conversion at {version_dir}")

        return ConversionResult(
            language=src_lang,
            success=False,
            duration_seconds=duration,
            error_message=error_msg,
        )


def convert_language_wrapper(args: tuple[str, str, Path, bool, bool]) -> ConversionResult:
    """
    Wrapper for parallel conversion.

    Args:
        args: Tuple of (src_lang, tgt_lang, output_dir, validate, skip_existing)

    Returns:
        ConversionResult
    """
    return convert_opus_mt_to_onnx(*args)


def convert_multiple_languages(
    languages: list[str],
    tgt_lang: str,
    output_dir: Path,
    validate: bool = False,
    skip_existing: bool = True,
    workers: int = 1,
) -> list[ConversionResult]:
    """
    Convert multiple OPUS-MT models in parallel.

    Args:
        languages: List of source language codes
        tgt_lang: Target language code (default: 'en')
        output_dir: Root output directory
        validate: Run ONNX validation after conversion
        skip_existing: Skip already converted models
        workers: Number of parallel workers (1 = sequential)

    Returns:
        List of ConversionResult objects
    """
    results: list[ConversionResult] = []
    total = len(languages)

    logger.info(f"Converting {total} language pairs with {workers} workers")

    if workers == 1:
        # Sequential conversion
        for i, src_lang in enumerate(languages, 1):
            logger.info(f"[{i}/{total}] Processing {src_lang}-{tgt_lang}")
            result = convert_opus_mt_to_onnx(src_lang, tgt_lang, output_dir, validate, skip_existing)
            results.append(result)
    else:
        # Parallel conversion
        conversion_args = [(lang, tgt_lang, output_dir, validate, skip_existing) for lang in languages]

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(convert_language_wrapper, args): args[0] for args in conversion_args}

            for i, future in enumerate(as_completed(futures), 1):
                src_lang = futures[future]
                logger.info(f"[{i}/{total}] Completed {src_lang}-{tgt_lang}")
                result = future.result()
                results.append(result)

    return results


def print_summary(results: list[ConversionResult]) -> None:
    """Print conversion summary report."""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    total_time = sum(r.duration_seconds for r in results)
    avg_time = total_time / len(results) if results else 0

    print("\n" + "=" * 70)
    print("CONVERSION SUMMARY")
    print("=" * 70)
    print(f"Total models:     {len(results)}")
    print(f"Successful:       {len(successful)} ✓")
    print(f"Failed:           {len(failed)} ✗")
    print(f"Total time:       {total_time:.1f}s")
    print(f"Average time:     {avg_time:.1f}s per model")
    print("=" * 70)

    if successful:
        print(f"\n✓ Successfully converted {len(successful)} models:")
        for result in successful:
            print(f"  - {result.language} ({result.duration_seconds:.1f}s)")

    if failed:
        print(f"\n✗ Failed conversions ({len(failed)}):")
        for result in failed:
            print(f"  - {result.language}: {result.error_message}")

    print()


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert OPUS-MT models from PyTorch to ONNX format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert French model
  python convert_opus_to_onnx.py --language fr

  # Convert multiple languages
  python convert_opus_to_onnx.py --languages fr,de,es,it

  # Convert all 41 languages with 4 workers
  python convert_opus_to_onnx.py --all --workers 4 --validate

  # List supported languages
  python convert_opus_to_onnx.py --list-languages
        """,
    )

    parser.add_argument(
        "--language",
        type=str,
        help="Single language code to convert (e.g., 'fr')",
    )

    parser.add_argument(
        "--languages",
        type=str,
        help="Comma-separated language codes (e.g., 'fr,de,es')",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help=f"Convert all {len(SUPPORTED_LANGUAGES)} supported language pairs",
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
        help="Output directory for converted models (default: model-repository/)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel conversion workers (default: 1)",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate ONNX models after conversion",
    )

    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-convert models even if they already exist",
    )

    parser.add_argument(
        "--target-lang",
        type=str,
        default="en",
        help="Target language code (default: en)",
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

    # Determine which languages to convert
    languages_to_convert: list[str] = []

    if args.all:
        languages_to_convert = SUPPORTED_LANGUAGES
    elif args.languages:
        languages_to_convert = [lang.strip() for lang in args.languages.split(",")]
    elif args.language:
        languages_to_convert = [args.language]
    else:
        parser.error("Must specify --language, --languages, or --all")

    # Validate language codes
    invalid_languages = [lang for lang in languages_to_convert if lang not in SUPPORTED_LANGUAGES]
    if invalid_languages:
        logger.error(f"Invalid language codes: {', '.join(invalid_languages)}")
        logger.info(f"Supported languages: {', '.join(SUPPORTED_LANGUAGES)}")
        return

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {args.output_dir.absolute()}")

    # Run conversions
    start_time = time.time()
    results = convert_multiple_languages(
        languages=languages_to_convert,
        tgt_lang=args.target_lang,
        output_dir=args.output_dir,
        validate=args.validate,
        skip_existing=not args.no_skip_existing,
        workers=args.workers,
    )
    total_time = time.time() - start_time

    # Print summary
    print_summary(results)

    # Exit with error code if any conversions failed
    failed_count = sum(1 for r in results if not r.success)
    if failed_count > 0:
        exit(1)


if __name__ == "__main__":
    main()
