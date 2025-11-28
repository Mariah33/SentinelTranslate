#!/usr/bin/env python3
"""Download pre-packaged NER models from S3 for air-gapped Docker builds.

This script downloads spaCy and Stanza models from an S3 bucket during Docker build
to enable air-gapped deployments where internet access is not available at runtime.

Example usage:
    # Download all models
    python download_models_from_s3.py --bucket my-bucket --prefix ner-models/

    # Download only spaCy models
    python download_models_from_s3.py --bucket my-bucket --spacy-only

    # Download to specific directory
    python download_models_from_s3.py --bucket my-bucket --output-dir /models
"""

import argparse
import json
import logging
import sys
from hashlib import sha256
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def setup_s3_client() -> boto3.client:
    """Create and return S3 client.

    Supports both explicit credentials and IAM role-based access.
    For public buckets, no credentials are required.
    """
    try:
        client = boto3.client("s3")
        # Test connection
        client.head_bucket(Bucket="test-bucket")
    except NoCredentialsError:
        logger.warning("No AWS credentials found. Assuming public bucket access.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logger.debug("Bucket test-bucket not found, but credentials may be valid.")
        elif e.response["Error"]["Code"] == "403":
            logger.warning("Access denied. Check IAM permissions.")
        else:
            logger.debug(f"ClientError during credential test: {e}")

    return client


def download_manifest(bucket: str, prefix: str, s3_client: boto3.client) -> dict:
    """Download and parse manifest.json from S3.

    Args:
        bucket: S3 bucket name
        prefix: S3 prefix path
        s3_client: Boto3 S3 client

    Returns:
        dict: Manifest JSON parsed as dictionary

    Raises:
        FileNotFoundError: If manifest.json not found in S3
        json.JSONDecodeError: If manifest.json is invalid
    """
    manifest_key = f"{prefix.rstrip('/')}/manifest.json"
    logger.info(f"Downloading manifest from s3://{bucket}/{manifest_key}")

    try:
        response = s3_client.get_object(Bucket=bucket, Key=manifest_key)
        manifest_content = response["Body"].read().decode("utf-8")
        manifest = json.loads(manifest_content)
        logger.info(f"Manifest loaded successfully: {manifest}")
        return manifest
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            raise FileNotFoundError(
                f"manifest.json not found at s3://{bucket}/{manifest_key}. "
                f"Ensure models are packaged with manifest.json at the prefix root."
            ) from e
        raise


def verify_checksum(file_path: Path, expected_checksum: str) -> bool:
    """Verify SHA256 checksum of downloaded file.

    Args:
        file_path: Path to file to verify
        expected_checksum: Expected SHA256 hash

    Returns:
        bool: True if checksum matches
    """
    sha256_hash = sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    actual_checksum = sha256_hash.hexdigest()
    if actual_checksum == expected_checksum:
        logger.debug(f"Checksum verified for {file_path.name}")
        return True
    else:
        logger.error(
            f"Checksum mismatch for {file_path.name}: "
            f"expected {expected_checksum}, got {actual_checksum}"
        )
        return False


def download_spacy_models(
    bucket: str,
    manifest: dict,
    s3_client: boto3.client,
    output_dir: Path,
) -> None:
    """Download spaCy model archives from S3 and extract to output directory.

    Args:
        bucket: S3 bucket name
        manifest: Manifest dictionary from manifest.json
        s3_client: Boto3 S3 client
        output_dir: Directory to extract models to

    Raises:
        FileNotFoundError: If manifest missing spacy_models section
        ClientError: If S3 download fails
    """
    if "spacy_models" not in manifest:
        logger.warning("No spacy_models section in manifest")
        return

    spacy_models = manifest["spacy_models"]
    logger.info(f"Downloading {len(spacy_models)} spaCy models")

    for model in spacy_models:
        model_name = model["name"]
        model_key = model["s3_key"]
        checksum = model.get("sha256")

        logger.info(f"Downloading spaCy model: {model_name}")
        target_path = output_dir / "spacy" / f"{model_name}.whl"
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            s3_client.download_file(bucket, model_key, str(target_path))
            logger.info(f"Downloaded {model_name} to {target_path}")

            if checksum:
                if verify_checksum(target_path, checksum):
                    logger.info(f"Checksum verified for {model_name}")
                else:
                    logger.error(f"Checksum verification failed for {model_name}")
                    target_path.unlink()
                    raise ValueError(f"Checksum mismatch for {model_name}")
        except ClientError as e:
            logger.error(f"Failed to download {model_name}: {e}")
            raise


def download_stanza_models(
    bucket: str,
    manifest: dict,
    s3_client: boto3.client,
    output_dir: Path,
) -> None:
    """Download Stanza model archives from S3 and extract to output directory.

    Args:
        bucket: S3 bucket name
        manifest: Manifest dictionary from manifest.json
        s3_client: Boto3 S3 client
        output_dir: Directory to extract models to

    Raises:
        FileNotFoundError: If manifest missing stanza_models section
        ClientError: If S3 download fails
    """
    if "stanza_models" not in manifest:
        logger.warning("No stanza_models section in manifest")
        return

    stanza_models = manifest["stanza_models"]
    logger.info(f"Downloading {len(stanza_models)} Stanza models")

    for model in stanza_models:
        model_name = model["name"]
        model_key = model["s3_key"]
        checksum = model.get("sha256")

        logger.info(f"Downloading Stanza model: {model_name}")
        target_path = output_dir / "stanza" / f"{model_name}.tar.gz"
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            s3_client.download_file(bucket, model_key, str(target_path))
            logger.info(f"Downloaded {model_name} to {target_path}")

            if checksum:
                if verify_checksum(target_path, checksum):
                    logger.info(f"Checksum verified for {model_name}")
                else:
                    logger.error(f"Checksum verification failed for {model_name}")
                    target_path.unlink()
                    raise ValueError(f"Checksum mismatch for {model_name}")
        except ClientError as e:
            logger.error(f"Failed to download {model_name}: {e}")
            raise


def main() -> None:
    """Main entry point for model download script."""
    parser = argparse.ArgumentParser(
        description="Download pre-packaged NER models from S3 for air-gapped Docker builds"
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="S3 bucket name containing packaged models",
    )
    parser.add_argument(
        "--prefix",
        default="ner-models/",
        help="S3 prefix path (default: ner-models/)",
    )
    parser.add_argument(
        "--spacy-only",
        action="store_true",
        help="Download only spaCy models",
    )
    parser.add_argument(
        "--stanza-only",
        action="store_true",
        help="Download only Stanza models",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Output directory for downloaded models (default: current directory)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.spacy_only and args.stanza_only:
        logger.error("Cannot specify both --spacy-only and --stanza-only")
        sys.exit(1)

    try:
        logger.info(f"Initializing S3 client for bucket: {args.bucket}")
        s3_client = setup_s3_client()

        logger.info(f"Using output directory: {args.output_dir}")
        args.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading manifest from S3")
        manifest = download_manifest(args.bucket, args.prefix, s3_client)

        if not args.stanza_only:
            logger.info("Starting spaCy model download")
            download_spacy_models(args.bucket, manifest, s3_client, args.output_dir)

        if not args.spacy_only:
            logger.info("Starting Stanza model download")
            download_stanza_models(args.bucket, manifest, s3_client, args.output_dir)

        logger.info("Model download completed successfully")
        logger.info(f"Models are ready at: {args.output_dir}")

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except (ClientError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Download failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Download interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
