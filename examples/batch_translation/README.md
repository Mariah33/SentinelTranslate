# Batch Translation Guide

This directory contains tutorials and examples for large-scale batch translation using SentinelTranslate's S3-based parquet processing API.

## Overview

The batch translation API allows you to:

1. **Upload** parquet files with multilingual text to S3
2. **Submit** batch translation jobs via REST API
3. **Monitor** job progress and status
4. **Download** translated results from S3
5. **Analyze** translation quality and throughput

Perfect for:
- Translating large datasets (thousands to millions of rows)
- Offline data processing pipelines
- ETL workflows with multilingual content
- Data analytics requiring English-only text

## Quick Start

```bash
# Run the batch translation notebook
jupyter notebook batch_s3_example.ipynb
```

The notebook will guide you through the complete batch translation workflow.

## Prerequisites

### Python Packages

```bash
pip install pandas pyarrow boto3 requests matplotlib
```

### AWS S3 Setup

You need an AWS account with S3 access:

1. **Create S3 bucket** for input/output files
2. **Configure AWS credentials**:
   ```bash
   export AWS_ACCESS_KEY_ID="your-access-key"
   export AWS_SECRET_ACCESS_KEY="your-secret-key"
   export AWS_DEFAULT_REGION="us-east-1"
   ```
3. **Grant permissions**: Ensure your IAM user/role has `s3:GetObject` and `s3:PutObject` permissions

### Services Running

```bash
# Start SentinelTranslate services
docker-compose up -d

# Verify batch API is healthy
curl http://localhost:8090/health
```

## Batch Translation Workflow

### 1. Prepare Data

Create a parquet file with your source text:

```python
import pandas as pd

df = pd.DataFrame({
    'id': [1, 2, 3],
    'content': [
        'Bonjour le monde',
        'Comment allez-vous?',
        'Merci beaucoup'
    ],
    'source_lang': ['fr', 'fr', 'fr']
})

df.to_parquet('input_data.parquet', index=False)
```

**Required columns**:
- **text_column**: Column containing text to translate (e.g., `content`)
- **source_lang** (optional): Can be in data or specified in API request

**Optional columns**:
- **id_column**: Preserved in output for tracking (e.g., `id`, `document_id`)
- Any other columns: Preserved in output

### 2. Upload to S3

```python
import boto3

s3 = boto3.client('s3')
s3.upload_file(
    'input_data.parquet',
    'my-translation-bucket',
    'input/data.parquet'
)
```

### 3. Submit Batch Job

```python
import requests

payload = {
    's3_bucket': 'my-translation-bucket',
    's3_key': 'input/data.parquet',
    'text_column': 'content',
    'source_lang': 'fr',
    'target_lang': 'en',
    'output_s3_bucket': 'my-translation-bucket',  # Optional
    'output_s3_key': 'output/data_en.parquet',    # Optional
    'id_column': 'id'  # Optional
}

response = requests.post('http://localhost:8090/batch/translate', json=payload)
job_id = response.json()['job_id']
print(f'Job submitted: {job_id}')
```

### 4. Monitor Progress

```python
import time

while True:
    status = requests.get(f'http://localhost:8090/batch/status/{job_id}').json()
    print(f"Status: {status['status']}")

    if status['status'] in ['SUCCESS', 'FAILURE']:
        break

    time.sleep(5)  # Poll every 5 seconds
```

### 5. Download Results

```python
if status['status'] == 'SUCCESS':
    output_location = status['result']['output_location']
    # Parse S3 location
    bucket, key = output_location.replace('s3://', '').split('/', 1)

    # Download
    s3.download_file(bucket, key, 'output_data.parquet')

    # Read results
    result_df = pd.read_parquet('output_data.parquet')
    print(result_df.head())
```

## API Reference

### Submit Batch Translation

**Endpoint**: `POST /batch/translate`

**Request**:
```json
{
  "s3_bucket": "string (required)",
  "s3_key": "string (required)",
  "text_column": "string (required)",
  "source_lang": "string (required)",
  "target_lang": "string (default: en)",
  "output_s3_bucket": "string (optional, defaults to input bucket)",
  "output_s3_key": "string (optional, auto-generated if not provided)",
  "id_column": "string (optional)"
}
```

**Response**:
```json
{
  "job_id": "uuid4-string",
  "message": "Batch translation job submitted successfully"
}
```

### Check Job Status

**Endpoint**: `GET /batch/status/{job_id}`

**Response (Pending/In Progress)**:
```json
{
  "job_id": "uuid4-string",
  "status": "PENDING"  // or "PROGRESS"
}
```

**Response (Success)**:
```json
{
  "job_id": "uuid4-string",
  "status": "SUCCESS",
  "result": {
    "output_location": "s3://bucket/key",
    "total_rows": 1000,
    "successful_translations": 995,
    "failed_rows": 5,
    "failed_indices": [42, 108, 567, 789, 923]
  }
}
```

**Response (Failure)**:
```json
{
  "job_id": "uuid4-string",
  "status": "FAILURE",
  "error": "Error message describing what went wrong"
}
```

## Data Format

### Input Parquet Schema

```
id: int64 (optional, preserved in output)
content: string (text to translate)
source_lang: string (optional if specified in API)
category: string (example: any columns are preserved)
timestamp: datetime64 (example: any columns are preserved)
```

### Output Parquet Schema

```
id: int64 (preserved from input)
content: string (original text)
translation: string (translated text)
source_lang: string
category: string (preserved from input)
timestamp: datetime64 (preserved from input)
```

All input columns are preserved. Translation is added as a new column.

## Performance and Costs

### Processing Time

| Rows | Average Time | Throughput |
|------|-------------|------------|
| 100 | 30s | ~3 rows/s |
| 1,000 | 5min | ~3 rows/s |
| 10,000 | 50min | ~3 rows/s |
| 100,000 | 8h | ~3 rows/s |

**Factors affecting speed**:
- Text length (longer texts take more time)
- Worker count (scale horizontally with more Celery workers)
- Hallucination detection (retries add latency)
- S3 I/O (download/upload time)

### Scaling for Higher Throughput

Increase worker count in `docker-compose.yml`:

```yaml
worker:
  deploy:
    replicas: 5  # Run 5 worker instances
```

With 5 workers, throughput increases to ~15 rows/s (5x improvement).

### Cost Estimation

**AWS S3**:
- Storage: $0.023/GB/month
- PUT requests: $0.005 per 1,000 requests
- GET requests: $0.0004 per 1,000 requests

**Example**: 100,000 rows (10MB parquet):
- Storage: $0.0002/month
- PUT (1 upload): $0.000005
- GET (1 download): $0.0000004
- **Total**: < $0.001

**Compute** (your infrastructure):
- GPU: ~$0.50-2.00/hour depending on instance type
- CPU: ~$0.05-0.20/hour

**Total cost for 100,000 rows**: $0.50-2.00 (dominated by compute time)

## Use Cases

### 1. Customer Support Tickets

Translate support tickets from multiple languages to English for analysis:

```python
# Input: tickets.parquet
# Columns: ticket_id, customer_message, language, created_at

df = pd.read_parquet('tickets.parquet')
df.to_parquet('input/tickets.parquet')

# Submit for each language
for lang in ['fr', 'es', 'de']:
    lang_tickets = df[df['language'] == lang]
    lang_tickets.to_parquet(f'input/tickets_{lang}.parquet')

    # Submit batch job
    submit_batch_job(
        s3_key=f'input/tickets_{lang}.parquet',
        source_lang=lang,
        text_column='customer_message',
        id_column='ticket_id'
    )
```

### 2. Social Media Monitoring

Translate social media posts for sentiment analysis:

```python
# Input: social_posts.parquet
# Columns: post_id, text, author, platform, timestamp, lang

submit_batch_job(
    s3_key='input/social_posts.parquet',
    text_column='text',
    source_lang='es',  # Or mixed languages
    id_column='post_id'
)
```

### 3. E-commerce Product Descriptions

Translate product descriptions for English-speaking markets:

```python
# Input: products.parquet
# Columns: sku, description, price, category

submit_batch_job(
    s3_key='input/products_fr.parquet',
    text_column='description',
    source_lang='fr',
    id_column='sku'
)
```

### 4. Research Paper Abstracts

Translate academic abstracts for literature review:

```python
# Input: papers.parquet
# Columns: doi, title, abstract, authors, year

submit_batch_job(
    s3_key='input/papers_de.parquet',
    text_column='abstract',
    source_lang='de',
    id_column='doi'
)
```

## Error Handling

### Failed Rows

Some rows may fail translation due to:
- Invalid characters or encoding issues
- Extremely long text (>512 tokens)
- Hallucination detection triggering multiple retries
- Network/service errors

The API returns failed row indices in the result:

```json
{
  "failed_rows": 5,
  "failed_indices": [42, 108, 567, 789, 923]
}
```

**To handle failures**:

```python
# Read output
df = pd.read_parquet('output.parquet')

# Failed rows will have empty/null translations
failed_rows = df[df['translation'].isna()]

# Retry failed rows individually via single API
for idx, row in failed_rows.iterrows():
    translate_single(row['content'], row['source_lang'])
```

### Job Failures

Entire job may fail due to:
- S3 bucket not accessible
- Invalid parquet format
- Missing required columns
- Service unavailability

**Best practices**:
1. Validate parquet schema before uploading
2. Test with small sample (100 rows) first
3. Implement exponential backoff for retries
4. Monitor Celery worker logs for errors

## Sample Data

See `sample_data.parquet` for an example dataset with:
- 200 rows
- Mixed languages (French, Spanish, German, Chinese)
- Various content types (reviews, tweets, articles)
- Realistic text lengths

Use this to test the batch API before processing your own data.

## Best Practices

### Data Preparation

1. **Clean text**: Remove HTML tags, special characters, control characters
2. **Split long documents**: Break into sentences/paragraphs (<512 tokens each)
3. **Deduplicate**: Remove exact duplicates to save processing time
4. **Filter empty rows**: Skip rows with empty text

### Job Submission

1. **Test first**: Process 100 rows before full dataset
2. **Batch size**: Keep under 100,000 rows per job for manageable runtime
3. **Language grouping**: Separate jobs by source language for better monitoring
4. **Naming convention**: Use descriptive S3 keys (e.g., `tickets_fr_2024_01.parquet`)

### Monitoring

1. **Poll frequency**: Check status every 5-10 seconds (don't spam API)
2. **Timeout**: Set reasonable timeout based on row count (e.g., 10min per 1000 rows)
3. **Alerts**: Set up notifications for job failures
4. **Logging**: Log all job IDs with metadata for audit trail

### Post-Processing

1. **Quality check**: Sample translations manually for quality
2. **BLEU score**: Calculate BLEU against reference translations if available
3. **Handle failures**: Retry failed rows individually
4. **Archive**: Keep original data alongside translations

## Troubleshooting

### Job Stuck in PENDING

```
Status remains "PENDING" for >5 minutes
```

**Causes**:
- Celery workers not running
- Redis queue backed up
- Worker crashed

**Solutions**:
```bash
# Check worker status
docker-compose logs worker

# Restart worker
docker-compose restart worker

# Check Redis queue length
docker-compose exec redis redis-cli LLEN celery
```

### S3 Access Denied

```
Error: "Access Denied" when reading/writing S3
```

**Solutions**:
1. Verify AWS credentials are set
2. Check IAM permissions (S3:GetObject, S3:PutObject)
3. Verify bucket name is correct
4. Check bucket policy allows access from your IP/VPC

### Parquet Read Error

```
Error: "Unable to read parquet file"
```

**Solutions**:
1. Verify file is valid parquet: `pd.read_parquet('file.parquet')`
2. Check column names match text_column parameter
3. Ensure UTF-8 encoding
4. Re-create parquet with `engine='pyarrow'`

### High Failure Rate

```
Many rows failing translation (>10%)
```

**Solutions**:
1. Check input data quality (encoding, special characters)
2. Review hallucination detection thresholds
3. Inspect failed row indices for patterns
4. Try shorter text chunks

## Advanced Topics

### Parallel Job Processing

Submit multiple jobs for different language pairs:

```python
jobs = {}
for lang in ['fr', 'es', 'de', 'zh']:
    response = submit_batch_job(
        s3_key=f'input/data_{lang}.parquet',
        source_lang=lang
    )
    jobs[lang] = response['job_id']

# Monitor all jobs
for lang, job_id in jobs.items():
    status = check_status(job_id)
    print(f'{lang}: {status["status"]}')
```

### Custom Output Transformations

Post-process translations before saving:

```python
df = pd.read_parquet('output.parquet')

# Add metadata
df['translated_at'] = pd.Timestamp.now()
df['model'] = 'opus-mt-fr-en'
df['service'] = 'SentinelTranslate'

# Quality score (custom logic)
df['quality_score'] = df.apply(lambda row: calculate_quality(row), axis=1)

df.to_parquet('output_enriched.parquet')
```

### Integration with Data Pipelines

Use in Apache Airflow, Prefect, or other orchestrators:

```python
# Airflow DAG example
from airflow import DAG
from airflow.operators.python import PythonOperator

def translate_batch(**context):
    job_id = submit_batch_job(...)
    context['ti'].xcom_push(key='job_id', value=job_id)

def check_completion(**context):
    job_id = context['ti'].xcom_pull(key='job_id')
    status = check_status(job_id)
    if status['status'] != 'SUCCESS':
        raise Exception('Translation failed')

with DAG('translate_pipeline') as dag:
    submit = PythonOperator(task_id='submit', python_callable=translate_batch)
    check = PythonOperator(task_id='check', python_callable=check_completion)
    submit >> check
```

## Resources

- **Sample Notebook**: [batch_s3_example.ipynb](batch_s3_example.ipynb)
- **Sample Data**: [sample_data.parquet](sample_data.parquet)
- **API Example**: [../api/example_usage.py](../../api/example_usage.py)
- **AWS S3 Docs**: https://docs.aws.amazon.com/s3/
- **Parquet Docs**: https://parquet.apache.org/

## Next Steps

1. **Run the tutorial**: Complete `batch_s3_example.ipynb`
2. **Process sample data**: Test with `sample_data.parquet`
3. **Prepare your data**: Convert your dataset to parquet format
4. **Submit your first job**: Start with 100 rows
5. **Scale up**: Process larger datasets with confidence

---

**Questions?** Check the main [SentinelTranslate README](../../README.md) or open an issue on GitHub.
