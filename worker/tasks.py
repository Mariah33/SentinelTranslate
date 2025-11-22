import io
import logging

import boto3
import pandas as pd

from celery_app import celery_app
from worker.client_triton import TritonClient
from worker.hallucination import detect_hallucination
from worker.postprocess import postprocess
from worker.preprocess import preprocess

triton = TritonClient("triton:8000")
s3_client = boto3.client("s3")
logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.translate")
def translate(job_id, text, src, tgt):
    sentences = preprocess(text)
    outputs = []
    model = f"opus-mt-{src}-en"

    for s in sentences:
        fast = triton.forward(model, s)
        if detect_hallucination(s, fast, src_lang=src):
            cleaned = " ".join(s.split()[:30])
            retry = triton.forward(model, cleaned)
            outputs.append(retry)
        else:
            outputs.append(fast)

    return postprocess(outputs)


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
        model = f"opus-mt-{source_lang}-{target_lang}"

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

                # Preprocess and translate
                sentences = preprocess(text)
                outputs = []

                for s in sentences:
                    fast = triton.forward(model, s)
                    if detect_hallucination(s, fast, src_lang=source_lang):
                        # Fallback: truncate to 30 tokens and retry
                        cleaned = " ".join(s.split()[:30])
                        retry = triton.forward(model, cleaned)
                        outputs.append(retry)
                    else:
                        outputs.append(fast)

                translated_text = postprocess(outputs)
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
