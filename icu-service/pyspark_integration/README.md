# PySpark Integration for ICU Microservice

Production-ready PySpark integration for the ICU microservice, enabling distributed text processing with ICU transformations in Apache Spark pipelines.

## Overview

This module provides:

- **HTTP Client**: Robust client with connection pooling, retry logic, and comprehensive error handling
- **Pandas UDFs**: Pre-built UDFs for common ICU operations (transliteration, normalization, case mapping)
- **Iterator UDFs**: Memory-efficient UDFs for processing large datasets
- **Graceful Error Handling**: Automatic fallback to original text on errors with detailed logging
- **Configuration**: Environment-based configuration for all settings

## Installation

### Prerequisites

- Python 3.11+
- Apache Spark 3.4+ with Arrow support
- ICU microservice running and accessible

### Install Dependencies

```bash
cd icu-service
pip install -r requirements.txt
```

Required packages:
- `pyspark>=3.4.0` - Apache Spark with Pandas UDF support
- `requests>=2.31.0` - HTTP client library
- `tenacity>=8.2.3` - Retry logic with exponential backoff
- `pandas>=2.0.0` - Pandas for UDF data processing
- `pyarrow>=13.0.0` - Arrow for efficient Spark-Pandas conversion

## Configuration

Configure the ICU service connection using environment variables:

```bash
# ICU service endpoint
export ICU_SERVICE_URL="http://icu-service:8083"

# Request timeout (seconds)
export ICU_REQUEST_TIMEOUT="30"

# Batch size for iterator UDFs
export ICU_BATCH_SIZE="500"
```

### Kubernetes Configuration

When running in Kubernetes with Kubeflow, configure via ConfigMap:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: icu-config
data:
  ICU_SERVICE_URL: "http://icu-service.default.svc.cluster.local:8083"
  ICU_REQUEST_TIMEOUT: "30"
  ICU_BATCH_SIZE: "500"
```

Then reference in your Spark job:

```yaml
spec:
  driver:
    envFrom:
      - configMapRef:
          name: icu-config
  executor:
    envFrom:
      - configMapRef:
          name: icu-config
```

## Quick Start

### Basic Usage

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark_integration import transliterate_latin_ascii, normalize_nfc

# Create Spark session with Arrow enabled
spark = SparkSession.builder \
    .appName("ICU-Example") \
    .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
    .config("spark.sql.execution.arrow.maxRecordsPerBatch", "500") \
    .getOrCreate()

# Create sample data
df = spark.createDataFrame([
    ("Café au lait",),
    ("naïve résumé",),
    ("Zürich",),
], ["text"])

# Apply ICU transformations
df = df.withColumn("normalized", normalize_nfc(col("text"))) \
       .withColumn("ascii", transliterate_latin_ascii(col("normalized")))

df.show()
# +-------------+-------------+-------------+
# |         text|   normalized|        ascii|
# +-------------+-------------+-------------+
# | Café au lait| Café au lait| Cafe au lait|
# |naïve résumé|naïve résumé|naive resume|
# |      Zürich|      Zürich|      Zurich|
# +-------------+-------------+-------------+
```

### Health Check

Always verify the ICU service is healthy before processing:

```python
from pyspark_integration import ICUServiceClient

client = ICUServiceClient()
try:
    health = client.health_check()
    print(f"Service healthy: {health}")
except Exception as e:
    raise RuntimeError(f"ICU service unavailable: {e}")
```

## Available UDFs

### Standard Pandas UDFs

Best for small-to-medium datasets where the entire partition fits in memory.

| UDF | Description | Example Input | Example Output |
|-----|-------------|---------------|----------------|
| `transliterate_latin_ascii` | Remove diacritics from Latin text | `"Café"` | `"Cafe"` |
| `transliterate_any_latin` | Transliterate any script to Latin | `"Москва"` | `"Moskva"` |
| `transliterate_cyrillic_latin` | Cyrillic to Latin transliteration | `"Киев"` | `"Kiev"` |
| `normalize_nfc` | NFC normalization (canonical composition) | `"e\u0301"` | `"é"` |
| `normalize_nfkc` | NFKC normalization (compatibility) | `"ﬁle"` | `"file"` |
| `case_mapping_upper_turkish` | Turkish-aware uppercase | `"istanbul"` | `"İSTANBUL"` |

### Iterator UDFs (Memory-Efficient)

Recommended for large datasets or memory-constrained environments. Processes data in configurable batches.

| UDF | Description | Batch Size |
|-----|-------------|------------|
| `transliterate_latin_ascii_iter` | Latin-ASCII (batched) | `ICU_BATCH_SIZE` env var |
| `transliterate_any_latin_iter` | Any-Latin (batched) | `ICU_BATCH_SIZE` env var |
| `normalize_nfc_iter` | NFC normalization (batched) | `ICU_BATCH_SIZE` env var |

**Example:**

```python
from pyspark_integration.udfs import transliterate_latin_ascii_iter

# For large datasets (millions of rows), use iterator UDF
df_large = spark.read.parquet("s3://my-bucket/large-dataset/")
df_processed = df_large.withColumn(
    "ascii",
    transliterate_latin_ascii_iter(col("text"))
)
```

## Usage Examples

### Example 1: Multilingual Search Normalization

```python
from pyspark.sql.functions import col
from pyspark_integration import normalize_nfkc, transliterate_any_latin

# Read multilingual search queries
df = spark.read.parquet("s3://search-logs/queries/")

# Normalize for search matching
df_normalized = df \
    .withColumn("normalized", normalize_nfkc(col("query"))) \
    .withColumn("latin", transliterate_any_latin(col("normalized")))

# Save search index
df_normalized.write.parquet("s3://search-index/normalized/")
```

### Example 2: Translation Pipeline Preprocessing

```python
from pyspark_integration import (
    normalize_nfc,
    transliterate_latin_ascii_iter
)

# Read source texts for translation
df = spark.read.parquet("s3://translation-jobs/source-texts/")

# Preprocess: normalize + transliterate for models expecting ASCII
df_preprocessed = df \
    .withColumn("normalized", normalize_nfc(col("source_text"))) \
    .withColumn("ascii_text", transliterate_latin_ascii_iter(col("normalized")))

# Send to translation service
df_preprocessed.write.parquet("s3://translation-jobs/preprocessed/")
```

### Example 3: Data Cleaning Pipeline

```python
from pyspark.sql.functions import col, when, length
from pyspark_integration import normalize_nfc, transliterate_latin_ascii

# Read raw user data
df = spark.read.json("s3://user-data/raw/")

# Clean and normalize names
df_cleaned = df \
    .withColumn("name_normalized", normalize_nfc(col("name"))) \
    .withColumn("name_ascii", transliterate_latin_ascii(col("name_normalized"))) \
    .withColumn(
        "name_clean",
        when(length(col("name_ascii")) > 0, col("name_ascii"))
        .otherwise(col("name_normalized"))
    )

df_cleaned.write.parquet("s3://user-data/cleaned/")
```

## Performance Tuning

### Batch Size Optimization

The `ICU_BATCH_SIZE` controls how many texts are sent in a single HTTP request.

**Recommendations:**
- **Small texts (<100 chars)**: 500-1000 per batch
- **Medium texts (100-500 chars)**: 200-500 per batch
- **Large texts (>500 chars)**: 50-200 per batch

```bash
# For small texts
export ICU_BATCH_SIZE="1000"

# For large texts
export ICU_BATCH_SIZE="100"
```

### Arrow Configuration

Enable Arrow for 10-100x faster Pandas UDF execution:

```python
spark = SparkSession.builder \
    .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
    .config("spark.sql.execution.arrow.maxRecordsPerBatch", "500") \
    .getOrCreate()
```

**Tuning `maxRecordsPerBatch`:**
- Small records: increase to 1000-2000
- Large records: decrease to 100-300
- Monitor memory usage and adjust

### Executor Configuration

For production workloads, configure executors appropriately:

```bash
spark-submit \
    --master yarn \
    --num-executors 20 \
    --executor-cores 4 \
    --executor-memory 8g \
    --driver-memory 4g \
    --conf spark.sql.execution.arrow.pyspark.enabled=true \
    --conf spark.sql.execution.arrow.maxRecordsPerBatch=500 \
    --conf spark.dynamicAllocation.enabled=true \
    --conf spark.shuffle.service.enabled=true \
    your_pipeline.py
```

### Connection Pooling

The HTTP client uses connection pooling for efficiency:
- **Pool connections**: 10 (number of connection pools)
- **Pool max size**: 20 (max connections per pool)
- **Retry strategy**: 3 attempts with exponential backoff (1s, 2s, 4s)

## Error Handling

### Graceful Degradation

All UDFs implement graceful error handling:

1. On service error, UDF logs a warning
2. Original text is returned unchanged
3. Processing continues without failing the job

**Example:**

```python
# If ICU service fails, original text is preserved
df = df.withColumn("ascii", transliterate_latin_ascii(col("text")))
# text="Café" -> ascii="Café" (fallback on error)
# text="Café" -> ascii="Cafe" (success)
```

### Monitoring Errors

Check Spark executor logs for ICU service warnings:

```bash
# View executor logs
kubectl logs -f spark-executor-1 -n kubeflow

# Look for warnings like:
# "ICU service error in transliterate_latin_ascii: HTTP 503 error..."
```

### Handling Service Unavailability

Always perform health check before processing:

```python
from pyspark_integration import ICUServiceClient

def validate_icu_service():
    client = ICUServiceClient()
    try:
        health = client.health_check()
        if health.get("status") != "healthy":
            raise RuntimeError(f"ICU service unhealthy: {health}")
        print(f"✓ ICU service ready: {health}")
    except Exception as e:
        raise RuntimeError(f"ICU service unavailable: {e}")

# Call before starting pipeline
validate_icu_service()

# Then proceed with Spark job
df = spark.read.parquet("s3://data/")
# ...
```

## Troubleshooting

### Issue: "Connection refused" errors

**Cause:** ICU service is not reachable from Spark executors.

**Solution:**
1. Verify service is running: `kubectl get pods -l app=icu-service`
2. Check service DNS: `kubectl get svc icu-service`
3. Update `ICU_SERVICE_URL` to use Kubernetes service DNS:
   ```bash
   export ICU_SERVICE_URL="http://icu-service.default.svc.cluster.local:8083"
   ```

### Issue: "Timeout" errors

**Cause:** Service is slow or overloaded.

**Solution:**
1. Increase timeout: `export ICU_REQUEST_TIMEOUT="60"`
2. Reduce batch size: `export ICU_BATCH_SIZE="200"`
3. Scale ICU service: `kubectl scale deployment icu-service --replicas=5`

### Issue: "Out of memory" errors

**Cause:** Iterator UDFs loading too much data.

**Solution:**
1. Reduce batch size: `export ICU_BATCH_SIZE="100"`
2. Reduce Arrow batch size:
   ```python
   .config("spark.sql.execution.arrow.maxRecordsPerBatch", "200")
   ```
3. Increase executor memory: `--executor-memory 16g`

### Issue: UDF returns original text (no transformation)

**Cause:** Service error or network issue.

**Solution:**
1. Check executor logs for warnings
2. Verify service health manually:
   ```python
   from pyspark_integration import ICUServiceClient
   client = ICUServiceClient()
   print(client.health_check())
   ```
3. Test transformation manually:
   ```python
   print(client.transliterate(["Café"], "Latin-ASCII"))
   ```

### Issue: Import errors in Spark executors

**Cause:** Python module not available on executors.

**Solution:**
1. Package module with `--py-files`:
   ```bash
   cd icu-service
   zip -r pyspark_integration.zip pyspark_integration/

   spark-submit --py-files pyspark_integration.zip your_pipeline.py
   ```

2. Or use `spark.submit.pyFiles` config:
   ```python
   spark = SparkSession.builder \
       .config("spark.submit.pyFiles", "/path/to/pyspark_integration.zip") \
       .getOrCreate()
   ```

## Complete Example

See `example_pipeline.py` for a complete working example:

```bash
# Local execution
spark-submit --master local[4] example_pipeline.py

# Cluster execution
spark-submit \
    --master yarn \
    --deploy-mode cluster \
    --num-executors 10 \
    --executor-cores 4 \
    --executor-memory 8g \
    --conf spark.sql.execution.arrow.pyspark.enabled=true \
    --conf spark.sql.execution.arrow.maxRecordsPerBatch=500 \
    --py-files pyspark_integration.zip \
    example_pipeline.py
```

## API Reference

### ICUServiceClient

```python
class ICUServiceClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None
    ) -> None: ...

    def transliterate(
        self,
        texts: list[str],
        transform_id: str,
        reverse: bool = False
    ) -> list[str]: ...

    def normalize(
        self,
        texts: list[str],
        form: Literal["NFC", "NFD", "NFKC", "NFKD"]
    ) -> list[str]: ...

    def transform(
        self,
        texts: list[str],
        transform_spec: str
    ) -> list[str]: ...

    def case_mapping(
        self,
        texts: list[str],
        operation: Literal["upper", "lower", "title", "fold"],
        locale: str | None = None
    ) -> list[str]: ...

    def health_check(self) -> dict[str, Any]: ...

    def get_supported_operations(self) -> dict[str, Any]: ...
```

## Contributing

When adding new UDFs:

1. Add to `udfs.py` with comprehensive docstring
2. Include usage example in docstring
3. Implement graceful error handling (return original on error)
4. Add both standard and iterator versions for large datasets
5. Export in `__init__.py`
6. Update this README with examples

## License

See `LICENSE` file in the repository root.

## Support

For issues or questions:
- Check troubleshooting section above
- Review Spark executor logs for detailed error messages
- Verify ICU service health: `curl http://icu-service:8083/health`
- Check environment variables are set correctly
