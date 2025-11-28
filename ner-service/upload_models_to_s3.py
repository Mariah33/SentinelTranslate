#!/usr/bin/env python3
"""Upload spaCy and Stanza models to S3 for production distribution.

This script discovers installed spaCy models in the UV virtual environment
and Stanza models in the local models directory, creates compressed archives,
and uploads them to S3 with a manifest file for tracking.

Usage:
    export S3_BUCKET=my-ner-models
    python upload_models_to_s3.py

    python upload_models_to_s3.py --bucket my-bucket --prefix production/models/
    python upload_models_to_s3.py --dry-run --spacy-only
"""

import argparse
import json
import logging
import os
import site
import sys
import tarfile
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class SpacyModelInfo:
    """Metadata for a spaCy model."""

    name: str
    version: str
    size_mb: float
    s3_key: str
    local_path: Path


@dataclass
class StanzaModelInfo:
    """Metadata for a Stanza model."""

    lang: str
    size_mb: float
    s3_key: str
    local_path: Path


@dataclass
class UploadManifest:
    """Complete manifest of uploaded models."""

    generated_at: str
    total_size_mb: float
    spacy_models: list[dict[str, Any]]
    stanza_models: list[dict[str, Any]]


class ModelUploader:
    """Handles model discovery, archiving, and S3 upload."""

    def __init__(
        self,
        bucket: str,
        prefix: str,
        region: str,
        profile: str | None,
        force: bool,
        dry_run: bool,
    ) -> None:
        """Initialize the model uploader.

        Args:
            bucket: S3 bucket name
            prefix: S3 key prefix/folder
            region: AWS region
            profile: AWS profile name (optional)
            force: Force re-upload even if files exist
            dry_run: Show what would be uploaded without uploading
        """
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/"  # Ensure trailing slash
        self.region = region
        self.profile = profile
        self.force = force
        self.dry_run = dry_run

        # Initialize S3 client
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.s3_client = session.client("s3", region_name=region)

        # Track uploaded models
        self.spacy_models: list[SpacyModelInfo] = []
        self.stanza_models: list[StanzaModelInfo] = []
        self.total_bytes_uploaded = 0
        self.upload_failures = 0

    def validate_aws_access(self) -> bool:
        """Validate AWS credentials and S3 bucket access.

        Returns:
            True if validation succeeds, False otherwise
        """
        try:
            logger.info("Validating AWS credentials...")
            sts = boto3.client("sts")
            identity = sts.get_caller_identity()
            logger.info(f"Authenticated as: {identity['Arn']}")

            logger.info(f"Validating S3 bucket access: s3://{self.bucket}")
            self.s3_client.head_bucket(Bucket=self.bucket)
            logger.info("S3 bucket is accessible")
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                logger.error(f"S3 bucket does not exist: {self.bucket}")
            elif error_code == "403":
                logger.error(f"Access denied to S3 bucket: {self.bucket}")
            else:
                logger.error(f"S3 bucket validation failed: {e}")
            return False
        except BotoCoreError as e:
            logger.error(f"AWS credentials validation failed: {e}")
            return False

    def discover_spacy_models(self) -> list[SpacyModelInfo]:
        """Discover installed spaCy models in UV virtual environment.

        Returns:
            List of discovered spaCy model metadata
        """
        logger.info("Discovering spaCy models in virtual environment...")
        models: list[SpacyModelInfo] = []

        # Get site-packages directory from UV virtual environment
        site_packages = site.getsitepackages()
        if not site_packages:
            logger.warning("No site-packages directory found")
            return models

        site_packages_path = Path(site_packages[0])
        logger.info(f"Searching in: {site_packages_path}")

        # Patterns for large spaCy models
        # Format: {lang}_core_{web|news}_lg-{version}.dist-info
        patterns = [
            "*_core_web_lg-*.dist-info",
            "*_core_news_lg-*.dist-info",
            "*_ent_wiki_lg-*.dist-info",
        ]

        for pattern in patterns:
            for dist_info in site_packages_path.glob(pattern):
                # Extract model name and version from dist-info directory
                # Example: en_core_web_lg-3.8.0.dist-info -> en_core_web_lg, 3.8.0
                dist_name = dist_info.name.replace(".dist-info", "")
                parts = dist_name.rsplit("-", 1)
                if len(parts) != 2:
                    logger.warning(f"Unexpected dist-info format: {dist_name}")
                    continue

                model_name, version = parts

                # Find actual model directory (without version suffix)
                model_dir = site_packages_path / model_name
                if not model_dir.exists() or not model_dir.is_dir():
                    logger.warning(f"Model directory not found: {model_dir}")
                    continue

                # Calculate size
                size_bytes = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
                size_mb = size_bytes / (1024 * 1024)

                # S3 key
                s3_key = f"{self.prefix}spacy/{model_name}-{version}.tar.gz"

                model_info = SpacyModelInfo(
                    name=model_name,
                    version=version,
                    size_mb=round(size_mb, 2),
                    s3_key=s3_key,
                    local_path=model_dir,
                )
                models.append(model_info)
                logger.info(f"Found spaCy model: {model_name} v{version} ({size_mb:.1f} MB)")

        logger.info(f"Discovered {len(models)} spaCy models")
        return models

    def discover_stanza_models(self) -> list[StanzaModelInfo]:
        """Discover Stanza models in models/stanza/ directory.

        Returns:
            List of discovered Stanza model metadata
        """
        logger.info("Discovering Stanza models...")
        models: list[StanzaModelInfo] = []

        stanza_dir = Path("models/stanza")
        if not stanza_dir.exists():
            logger.warning(f"Stanza models directory not found: {stanza_dir}")
            return models

        # Each subdirectory is a language
        for lang_dir in stanza_dir.iterdir():
            if not lang_dir.is_dir():
                continue

            lang = lang_dir.name

            # Calculate size
            size_bytes = sum(f.stat().st_size for f in lang_dir.rglob("*") if f.is_file())
            size_mb = size_bytes / (1024 * 1024)

            # S3 key
            s3_key = f"{self.prefix}stanza/{lang}.tar.gz"

            model_info = StanzaModelInfo(
                lang=lang,
                size_mb=round(size_mb, 2),
                s3_key=s3_key,
                local_path=lang_dir,
            )
            models.append(model_info)
            logger.info(f"Found Stanza model: {lang} ({size_mb:.1f} MB)")

        logger.info(f"Discovered {len(models)} Stanza models")
        return models

    def create_archive(self, source_path: Path, archive_name: str) -> Path:
        """Create a compressed tar.gz archive of a directory.

        Args:
            source_path: Directory to archive
            archive_name: Name for the archive file

        Returns:
            Path to created archive
        """
        temp_dir = Path(tempfile.gettempdir())
        archive_path = temp_dir / archive_name

        logger.debug(f"Creating archive: {archive_path}")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(source_path, arcname=source_path.name)

        return archive_path

    def file_exists_in_s3(self, s3_key: str) -> bool:
        """Check if a file already exists in S3.

        Args:
            s3_key: S3 object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            raise

    def upload_file(self, local_path: Path, s3_key: str, description: str) -> bool:
        """Upload a file to S3 with progress tracking.

        Args:
            local_path: Local file path
            s3_key: S3 object key
            description: Human-readable description for logging

        Returns:
            True if upload succeeds, False otherwise
        """
        if not self.force and self.file_exists_in_s3(s3_key):
            logger.info(f"Skipping {description} (already exists in S3)")
            return True

        size_mb = local_path.stat().st_size / (1024 * 1024)

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would upload {description} ({size_mb:.1f} MB) to s3://{self.bucket}/{s3_key}"
            )
            return True

        try:
            logger.info(f"Uploading {description} ({size_mb:.1f} MB)...")
            with open(local_path, "rb") as f:
                self.s3_client.upload_fileobj(f, self.bucket, s3_key)
            logger.info(f"Uploaded {description} successfully")
            self.total_bytes_uploaded += local_path.stat().st_size
            return True

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to upload {description}: {e}")
            self.upload_failures += 1
            return False

    def upload_spacy_models(self, models: list[SpacyModelInfo]) -> None:
        """Upload spaCy models to S3.

        Args:
            models: List of spaCy models to upload
        """
        logger.info(f"Uploading {len(models)} spaCy models...")

        for model in models:
            # Create archive
            archive_name = f"{model.name}-{model.version}.tar.gz"
            archive_path = self.create_archive(model.local_path, archive_name)

            # Upload
            description = f"{model.name} v{model.version}"
            success = self.upload_file(archive_path, model.s3_key, description)

            # Clean up archive
            archive_path.unlink(missing_ok=True)

            if success:
                self.spacy_models.append(model)

    def upload_stanza_models(self, models: list[StanzaModelInfo]) -> None:
        """Upload Stanza models to S3.

        Args:
            models: List of Stanza models to upload
        """
        logger.info(f"Uploading {len(models)} Stanza models...")

        for model in models:
            # Create archive
            archive_name = f"{model.lang}.tar.gz"
            archive_path = self.create_archive(model.local_path, archive_name)

            # Upload
            description = f"Stanza {model.lang}"
            success = self.upload_file(archive_path, model.s3_key, description)

            # Clean up archive
            archive_path.unlink(missing_ok=True)

            if success:
                self.stanza_models.append(model)

    def generate_manifest(self) -> UploadManifest:
        """Generate manifest file with metadata for all uploaded models.

        Returns:
            Upload manifest with model metadata
        """
        total_size_mb = sum(m.size_mb for m in self.spacy_models) + sum(
            m.size_mb for m in self.stanza_models
        )

        manifest = UploadManifest(
            generated_at=datetime.now(UTC).isoformat(),
            total_size_mb=round(total_size_mb, 2),
            spacy_models=[
                {
                    "name": m.name,
                    "version": m.version,
                    "size_mb": m.size_mb,
                    "s3_key": m.s3_key,
                }
                for m in self.spacy_models
            ],
            stanza_models=[
                {
                    "lang": m.lang,
                    "size_mb": m.size_mb,
                    "s3_key": m.s3_key,
                }
                for m in self.stanza_models
            ],
        )

        return manifest

    def upload_manifest(self, manifest: UploadManifest) -> bool:
        """Upload manifest file to S3.

        Args:
            manifest: Upload manifest to serialize and upload

        Returns:
            True if upload succeeds, False otherwise
        """
        manifest_json = json.dumps(asdict(manifest), indent=2)
        manifest_key = f"{self.prefix}manifest.json"

        if self.dry_run:
            logger.info(f"[DRY RUN] Would upload manifest to s3://{self.bucket}/{manifest_key}")
            logger.info(f"Manifest content:\n{manifest_json}")
            return True

        try:
            logger.info("Uploading manifest.json...")
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=manifest_key,
                Body=manifest_json.encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"Uploaded manifest to s3://{self.bucket}/{manifest_key}")
            return True

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to upload manifest: {e}")
            return False

    def print_summary(self) -> None:
        """Print upload summary."""
        total_mb = self.total_bytes_uploaded / (1024 * 1024)
        spacy_count = len(self.spacy_models)
        stanza_count = len(self.stanza_models)

        logger.info("=" * 60)
        logger.info("Upload Summary")
        logger.info("=" * 60)
        logger.info(f"spaCy models uploaded: {spacy_count}")
        logger.info(f"Stanza models uploaded: {stanza_count}")
        logger.info(f"Total size uploaded: {total_mb:.1f} MB")
        logger.info(f"Upload failures: {self.upload_failures}")
        logger.info("=" * 60)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Upload spaCy and Stanza models to S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload all models
  export S3_BUCKET=my-ner-models
  python upload_models_to_s3.py

  # Upload only spaCy models to custom location
  python upload_models_to_s3.py --bucket my-bucket --prefix production/models/ --spacy-only

  # Dry run to see what would be uploaded
  python upload_models_to_s3.py --bucket test --dry-run
        """,
    )

    parser.add_argument(
        "--bucket",
        help="S3 bucket name (or set S3_BUCKET env var)",
        default=os.environ.get("S3_BUCKET"),
    )
    parser.add_argument(
        "--prefix",
        help="S3 key prefix/folder (default: ner-models/)",
        default=os.environ.get("S3_PREFIX", "ner-models/"),
    )
    parser.add_argument(
        "--region",
        help="AWS region (default: us-east-1)",
        default=os.environ.get("AWS_REGION", "us-east-1"),
    )
    parser.add_argument(
        "--profile",
        help="AWS profile name (optional, for local development)",
        default=os.environ.get("AWS_PROFILE"),
    )
    parser.add_argument(
        "--spacy-only",
        action="store_true",
        help="Upload only spaCy models",
    )
    parser.add_argument(
        "--stanza-only",
        action="store_true",
        help="Upload only Stanza models",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-upload even if files exist in S3",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point for the upload script.

    Returns:
        Exit code (0 on success, non-zero on failure)
    """
    args = parse_args()

    # Validate required arguments
    if not args.bucket:
        logger.error("S3 bucket name is required (--bucket or S3_BUCKET env var)")
        return 1

    if args.spacy_only and args.stanza_only:
        logger.error("Cannot specify both --spacy-only and --stanza-only")
        return 1

    # Initialize uploader
    uploader = ModelUploader(
        bucket=args.bucket,
        prefix=args.prefix,
        region=args.region,
        profile=args.profile,
        force=args.force,
        dry_run=args.dry_run,
    )

    # Validate AWS access
    if not uploader.validate_aws_access():
        return 1

    # Discover models
    spacy_models: list[SpacyModelInfo] = []
    stanza_models: list[StanzaModelInfo] = []

    if not args.stanza_only:
        spacy_models = uploader.discover_spacy_models()

    if not args.spacy_only:
        stanza_models = uploader.discover_stanza_models()

    if not spacy_models and not stanza_models:
        logger.error("No models found to upload")
        return 1

    # Upload models
    if spacy_models:
        uploader.upload_spacy_models(spacy_models)

    if stanza_models:
        uploader.upload_stanza_models(stanza_models)

    # Generate and upload manifest
    manifest = uploader.generate_manifest()
    uploader.upload_manifest(manifest)

    # Print summary
    uploader.print_summary()

    # Return exit code based on failures
    return 1 if uploader.upload_failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
