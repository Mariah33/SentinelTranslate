import io
import logging
import os

import boto3
import httpx
import pandas as pd

from celery_app import celery_app
from cache import get_cached_translation, set_cached_translation

# Sidecar HTTP client configuration
SIDECAR_URL = os.environ.get("SIDECAR_URL", "http://sidecar:8080")
http_client = httpx.Client(base_url=SIDECAR_URL, timeout=30.0)

s3_client = boto3.client("s3")
logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.translate_parquet_batch", bind=True)
def translate_parquet_batch(
    self,
    job_id: str,
    s3_bucket: str,
    s3_key: str,
    text_column: str,
    source_lang: str,
    target_lang: str,
    output_bucket: str,
    output_key: str,
    id_column: str | None = None,
):
    """
    Process a parquet file from S3, translate the text column, and write results back to S3.

    Args:
        job_id: Unique job identifier
        s3_bucket: Input S3 bucket name
        s3_key: Input S3 key (file path)
        text_column: Name of column containing text to translate
        source_lang: Source language code (e.g., 'fr')
        target_lang: Target language code (e.g., 'en')
        output_bucket: Output S3 bucket name
        output_key: Output S3 key (file path)
        id_column: Optional ID column to preserve

    Returns:
        dict with output location and statistics
    """
    try:
        logger.info(f"[{job_id}] Starting batch translation from s3://{s3_bucket}/{s3_key}")

        # Download parquet file from S3
        logger.info(f"[{job_id}] Downloading parquet file from S3...")
        obj = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        df = pd.read_parquet(io.BytesIO(obj["Body"].read()))

        logger.info(f"[{job_id}] Loaded {len(df)} rows from parquet file")

        # Validate that the text column exists
        if text_column not in df.columns:
            raise ValueError(
                f"Column '{text_column}' not found in parquet file. Available columns: {list(df.columns)}"
            )

        # Validate ID column if specified
        if id_column and id_column not in df.columns:
            raise ValueError(
                f"ID column '{id_column}' not found in parquet file. Available columns: {list(df.columns)}"
            )

        # Translate each row
        logger.info(f"[{job_id}] Translating {len(df)} rows...")
        translations = []
        failed_rows = []

        for idx, row in df.iterrows():
            try:
                # Update task state to show progress
                if idx % 100 == 0:
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": idx,
                            "total": len(df),
                            "status": f"Translating row {idx}/{len(df)}",
                        },
                    )

                text = str(row[text_column])

                # Skip empty texts
                if not text or text.strip() == "" or pd.isna(text):
                    translations.append("")
                    continue

                # Check cache first (cache key includes full text before preprocessing)
                cached = get_cached_translation(text, source_lang, target_lang)
                if cached:
                    translations.append(cached)
                    continue

                # Call sidecar API for translation (handles hallucination detection internally)
                response = http_client.post(
                    "/translate",
                    json={"text": text, "source_lang": source_lang, "target_lang": target_lang},
                )
                response.raise_for_status()
                translated_text = response.json()["translation"]

                # Store in cache for future reuse
                set_cached_translation(text, source_lang, target_lang, translated_text)
                translations.append(translated_text)

            except Exception as e:
                logger.error(f"[{job_id}] Error translating row {idx}: {e}")
                translations.append("")
                failed_rows.append(idx)

        # Add translation column to dataframe
        df["translation"] = translations

        # If ID column specified, reorder to have ID first
        if id_column:
            cols = [id_column, text_column, "translation"] + [
                c for c in df.columns if c not in [id_column, text_column, "translation"]
            ]
            df = df[cols]

        # Write result to S3
        logger.info(f"[{job_id}] Writing results to s3://{output_bucket}/{output_key}")
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)

        s3_client.put_object(Bucket=output_bucket, Key=output_key, Body=buffer.getvalue())

        result = {
            "job_id": job_id,
            "output_location": f"s3://{output_bucket}/{output_key}",
            "total_rows": len(df),
            "successful_translations": len(df) - len(failed_rows),
            "failed_rows": len(failed_rows),
            "failed_indices": failed_rows[:10]
            if failed_rows
            else [],  # Return first 10 failed indices
            "source_lang": source_lang,
            "target_lang": target_lang,
        }

        logger.info(f"[{job_id}] Batch translation completed successfully: {result}")
        return result

    except Exception as e:
        logger.error(f"[{job_id}] Batch translation failed: {e}")
        raise
