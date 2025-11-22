# Frontend - Batch S3 Parquet Translation API

FastAPI service for submitting batch translation jobs from S3 parquet files.

## Overview

The frontend service provides an API for batch translation of parquet files stored in S3. It submits jobs to Celery workers which:
1. Download the parquet file from S3
2. Translate the specified text column row-by-row
3. Apply hallucination detection and safety checks
4. Write results back to S3 with original data + translation column

## API Endpoints

### POST /batch/translate

Submit a batch translation job.

**Request:**
```json
{
  "s3_bucket": "my-bucket",
  "s3_key": "data/input.parquet",
  "text_column": "text",
  "source_lang": "fr",
  "target_lang": "en",
  "output_s3_bucket": "my-bucket",  // optional
  "output_s3_key": "data/output.parquet",  // optional
  "id_column": "id"  // optional
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "submitted",
  "message": "Batch job submitted. Results will be written to s3://my-bucket/data/output.parquet"
}
```

### GET /batch/status/{job_id}

Get the status of a batch translation job.

**Response (in progress):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROGRESS",
  "result": null,
  "error": null
}
```

**Response (success):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCESS",
  "result": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "output_location": "s3://my-bucket/data/output.parquet",
    "total_rows": 1000,
    "successful_translations": 998,
    "failed_rows": 2,
    "failed_indices": [45, 678],
    "source_lang": "fr",
    "target_lang": "en"
  },
  "error": null
}
```

## Parquet File Structure

### Input File

Your parquet file can have any structure, but you must specify which column contains the text to translate:

```
| id  | text                    | metadata   |
|-----|-------------------------|------------|
| 1   | Bonjour le monde        | {...}      |
| 2   | Comment allez-vous?     | {...}      |
```

### Output File

The output parquet will have all original columns plus a `translation` column:

```
| id  | text                    | translation         | metadata   |
|-----|-------------------------|---------------------|------------|
| 1   | Bonjour le monde        | Hello world         | {...}      |
| 2   | Comment allez-vous?     | How are you?        | {...}      |
```

If you specify an `id_column`, it will be placed first in the output.

## Configuration

The frontend requires AWS credentials to access S3. Configure via:

**Option 1: Environment variables**
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1
```

**Option 2: IAM role (recommended for production)**
When running in EC2/ECS/EKS, attach an IAM role with S3 read/write permissions.

**Option 3: AWS credentials file**
Place credentials in `~/.aws/credentials`

## Development

```bash
# Install dependencies
make install

# Run locally
make run

# Lint and format
make lint

# Build Docker image
make build
```

## Docker

```bash
# Build
docker build -t frontend:latest .

# Run (with AWS credentials)
docker run -p 8090:8090 \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e AWS_REGION=us-east-1 \
  frontend:latest
```

## Example Usage

```python
import requests

# Submit batch job
response = requests.post("http://localhost:8090/batch/translate", json={
    "s3_bucket": "my-translation-bucket",
    "s3_key": "input/french_documents.parquet",
    "text_column": "content",
    "source_lang": "fr",
    "target_lang": "en",
    "id_column": "document_id"
})

job_id = response.json()["job_id"]
print(f"Job submitted: {job_id}")

# Poll for status
import time
while True:
    status_response = requests.get(f"http://localhost:8090/batch/status/{job_id}")
    status = status_response.json()

    if status["status"] == "SUCCESS":
        print(f"Translation complete!")
        print(f"Output: {status['result']['output_location']}")
        print(f"Translated {status['result']['successful_translations']} rows")
        break
    elif status["status"] == "FAILURE":
        print(f"Job failed: {status['error']}")
        break
    else:
        print(f"Status: {status['status']}")
        time.sleep(5)
```

## Architecture

```
Client → Frontend API (FastAPI)
           ↓ (submit Celery task)
         Redis Queue
           ↓
       Celery Worker
         ├─ Download parquet from S3
         ├─ Translate row-by-row
         ├─ Hallucination detection
         └─ Upload result to S3
           ↓
         S3 output parquet
```

## Environment Variables

- `REDIS_BROKER` - Redis broker URL (default: `redis://redis:6379/0`)
- `REDIS_BACKEND` - Redis backend URL (default: `redis://redis:6379/1`)
- `AWS_REGION` - AWS region (default: `us-east-1`)
- `AWS_ACCESS_KEY_ID` - AWS access key (optional, use IAM role instead)
- `AWS_SECRET_ACCESS_KEY` - AWS secret key (optional, use IAM role instead)
