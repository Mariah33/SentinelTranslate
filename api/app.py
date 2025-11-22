from uuid import uuid4

from celery import Celery
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="SentinelTranslate Batch Frontend", version="0.1.0")

# Celery configuration - connects to same broker/backend as sidecar
celery_app = Celery("translator", broker="redis://redis:6379/0", backend="redis://redis:6379/1")


class BatchJobRequest(BaseModel):
    """Request to submit a batch translation job from S3 parquet file."""

    s3_bucket: str = Field(..., description="S3 bucket name containing the parquet file")
    s3_key: str = Field(..., description="S3 key (path) to the parquet file")
    text_column: str = Field(..., description="Name of the column containing text to translate")
    source_lang: str = Field(..., description="Source language code (e.g., 'fr', 'de', 'es')")
    target_lang: str = Field(default="en", description="Target language code (default: 'en')")
    output_s3_bucket: str | None = Field(default=None, description="Output S3 bucket (defaults to input bucket)")
    output_s3_key: str | None = Field(default=None, description="Output S3 key (defaults to input_key + '_translated')")
    id_column: str | None = Field(default=None, description="Optional ID column to preserve in output")


class BatchJobResponse(BaseModel):
    """Response after submitting a batch job."""

    job_id: str
    status: str = "submitted"
    message: str


class BatchJobStatus(BaseModel):
    """Status of a batch translation job."""

    job_id: str
    status: str  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
    result: dict | None = None
    error: str | None = None


@app.post("/batch/translate", response_model=BatchJobResponse)
def submit_batch_job(req: BatchJobRequest):
    """
    Submit a batch translation job for a parquet file stored in S3.

    The job will:
    1. Read the parquet file from S3
    2. Translate the specified text column
    3. Write results back to S3 with original data + translation column
    """
    job_id = str(uuid4())

    # Prepare task arguments
    output_bucket = req.output_s3_bucket or req.s3_bucket
    output_key = req.output_s3_key or f"{req.s3_key.rsplit('.', 1)[0]}_translated.parquet"

    # Send task to Celery worker
    celery_app.send_task(
        "tasks.translate_parquet_batch",
        args=[
            job_id,
            req.s3_bucket,
            req.s3_key,
            req.text_column,
            req.source_lang,
            req.target_lang,
            output_bucket,
            output_key,
            req.id_column,
        ],
    )

    return BatchJobResponse(
        job_id=job_id,
        status="submitted",
        message=f"Batch job submitted. Results will be written to s3://{output_bucket}/{output_key}",
    )


@app.get("/batch/status/{job_id}", response_model=BatchJobStatus)
def get_batch_status(job_id: str):
    """
    Get the status of a batch translation job.

    Returns:
    - PENDING: Job is queued but not started
    - STARTED: Job is currently processing
    - SUCCESS: Job completed successfully (result contains output S3 path and stats)
    - FAILURE: Job failed (error contains failure reason)
    - RETRY: Job is being retried
    """
    result = celery_app.AsyncResult(job_id)

    if result.state == "SUCCESS":
        return BatchJobStatus(job_id=job_id, status=result.state, result=result.result, error=None)
    elif result.state == "FAILURE":
        return BatchJobStatus(job_id=job_id, status=result.state, result=None, error=str(result.info))
    else:
        return BatchJobStatus(job_id=job_id, status=result.state, result=None, error=None)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "frontend"}
