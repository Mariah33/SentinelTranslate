# ICU Microservice

Production-ready microservice for PyICU operations (transliteration, normalization, case mapping) designed for PySpark integration in Kubeflow pipelines.

## Overview

This microservice provides HTTP endpoints for ICU (International Components for Unicode) text processing operations. It's optimized for batch processing from PySpark jobs with features like:

- **Batch-first API**: Process 100-1000 texts per request
- **Thread-safe caching**: Lazy-loaded ICU Transliterator objects with singleton pattern
- **High performance**: Sub-100ms latency for 500-item batches
- **Kubernetes-ready**: HPA autoscaling, health probes, Prometheus metrics
- **PySpark integration**: Pandas UDFs with retry logic and connection pooling

## Architecture

```
PySpark Pipeline (Kubeflow)
         │
         ├──→ Pandas UDF (500 texts/batch)
         │         │
         │         ├──→ HTTP POST /transliterate
         │         │         │
         │         │         └──→ ICU Service (K8s)
         │         │                   │
         │         │                   ├──→ ICUCache (singleton)
         │         │                   │     └──→ Transliterator objects
         │         │                   │
         │         │                   └──→ Result (500 texts)
         │         │
         │         └──→ Return to Spark DataFrame
```

## Features

### Supported Operations

| Operation | Endpoint | Example |
|-----------|----------|---------|
| **Transliteration** | `POST /transliterate` | Café → Cafe (Latin-ASCII) |
| **Unicode Normalization** | `POST /normalize` | café → café (NFC) |
| **Custom Transforms** | `POST /transform` | Any-Latin; Latin-ASCII |
| **Case Mapping** | `POST /case-mapping` | istanbul → İSTANBUL (Turkish) |

### Available Transforms

**Common Transliterations:**
- `Latin-ASCII` - Remove diacritics (Café → Cafe)
- `Any-Latin` - Any script to Latin (Москва → Moskva)
- `Cyrillic-Latin` - Cyrillic to Latin
- `Greek-Latin` - Greek to Latin
- `Han-Latin` - Chinese to Pinyin

**Unicode Normalization Forms:**
- `NFC` - Canonical Composition (most common)
- `NFD` - Canonical Decomposition
- `NFKC` - Compatibility Composition
- `NFKD` - Compatibility Decomposition

**Locale-Aware Case Mapping:**
- Turkish (`tr`): i → İ, I → ı
- Lithuanian (`lt`): i → İ
- Greek (`el`): σ → Σ (final sigma handling)
- Azerbaijani (`az`): i → İ

## Quick Start

### Local Development

```bash
# 1. Install dependencies
cd icu-service
make install

# 2. Start service
make run
# Service available at http://localhost:8083

# 3. Test endpoint
curl -X POST http://localhost:8083/transliterate \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Café", "naïve"], "transform_id": "Latin-ASCII"}'

# Response:
# {"results": ["Cafe", "naive"], "transform_id": "Latin-ASCII", "count": 2}
```

### Docker

```bash
# Build image
make build

# Run container
docker run -p 8083:8083 icu-service:latest

# Health check
curl http://localhost:8083/health
```

### Kubernetes

```bash
# Deploy to K8s
make k8s-deploy

# Check status
make k8s-status

# View logs
make k8s-logs
```

## API Reference

### POST /transliterate

Batch transliteration using ICU transforms.

**Request:**
```json
{
  "texts": ["Café", "Москва", "東京"],
  "transform_id": "Latin-ASCII",
  "reverse": false
}
```

**Response:**
```json
{
  "results": ["Cafe", "Moskva", "Tokyo"],
  "transform_id": "Latin-ASCII",
  "count": 3
}
```

### POST /normalize

Unicode normalization (NFC, NFD, NFKC, NFKD).

**Request:**
```json
{
  "texts": ["café", "naïve"],
  "form": "NFC"
}
```

**Response:**
```json
{
  "results": ["café", "naïve"],
  "form": "NFC",
  "count": 2
}
```

### POST /transform

Custom ICU transform specifications.

**Request:**
```json
{
  "texts": ["Hello World", "Привет мир"],
  "transform_spec": "Any-Latin; Latin-ASCII; Lower"
}
```

**Response:**
```json
{
  "results": ["hello world", "privet mir"],
  "transform_spec": "Any-Latin; Latin-ASCII; Lower",
  "count": 2
}
```

### POST /case-mapping

Locale-aware case conversion.

**Request:**
```json
{
  "texts": ["istanbul"],
  "operation": "upper",
  "locale": "tr"
}
```

**Response:**
```json
{
  "results": ["İSTANBUL"],
  "operation": "upper",
  "locale": "tr",
  "count": 1
}
```

### GET /health

Health check with ICU version and cache stats.

**Response:**
```json
{
  "status": "healthy",
  "icu_version": "72.1",
  "cache_size": 12,
  "uptime_seconds": 3600.5
}
```

### GET /supported-operations

List available ICU operations.

**Response:**
```json
{
  "transliterators": [
    {
      "id": "Latin-ASCII",
      "description": "Transliterate Latin to ASCII",
      "example": {"input": "Café", "output": "Cafe"}
    }
  ],
  "normalization_forms": ["NFC", "NFD", "NFKC", "NFKD"],
  "common_locales": ["en", "tr", "lt", "az"],
  "total_transliterators": 45
}
```

### GET /cache-stats

Cache performance statistics.

**Response:**
```json
{
  "cached_transforms": {
    "Latin-ASCII:forward": {
      "hits": 15234,
      "created_at": "2026-01-20T10:30:00Z"
    }
  },
  "total_cached": 12,
  "total_requests": 24155,
  "cache_hit_rate": 0.95
}
```

## PySpark Integration

See [pyspark_integration/README.md](pyspark_integration/README.md) for detailed PySpark usage.

### Quick Example

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark_integration import transliterate_latin_ascii, normalize_nfc

spark = SparkSession.builder.appName("ICU-Example").getOrCreate()

df = spark.read.parquet("s3://bucket/data/*.parquet")

# Apply ICU transformations
df_processed = df \
    .withColumn("normalized", normalize_nfc(col("text"))) \
    .withColumn("ascii", transliterate_latin_ascii(col("normalized")))

df_processed.write.parquet("s3://bucket/output/")
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8083` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `WORKERS` | `4` | Uvicorn workers |
| `MAX_BATCH_SIZE` | `1000` | Maximum texts per request |
| `LOG_FORMAT` | `json` | Log format (json/text) |

## Development

### Commands

```bash
make help           # Show all commands
make install        # Install dependencies with UV
make format         # Format code with ruff
make lint           # Run linting
make typecheck      # Run type checking
make test           # Run tests (141 tests)
make run            # Start dev server
make build          # Build Docker image
make clean          # Clean build artifacts
```

### Testing

```bash
# Run all tests
make test

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/test_app.py -v
```

### Code Quality

- **Formatter**: Ruff (line length: 140)
- **Linter**: Ruff (strict rules)
- **Type Checker**: basedpyright (strict mode)
- **Test Framework**: pytest
- **Coverage Target**: >90%

## Performance

### Benchmarks

| Operation | Batch Size | Latency (P50) | Throughput |
|-----------|------------|---------------|------------|
| Transliterate | 100 | 10-20ms | ~5000 texts/sec |
| Transliterate | 500 | 40-60ms | ~8000 texts/sec |
| Transliterate | 1000 | 80-100ms | ~10000 texts/sec |
| Normalize | 500 | 30-50ms | ~10000 texts/sec |

### Scaling

- **HPA Targets**: 70% CPU, 80% memory
- **Min Replicas**: 2 (high availability)
- **Max Replicas**: 10 (cost control)
- **Resource Requests**: 250m CPU, 256Mi memory
- **Resource Limits**: 1000m CPU, 512Mi memory

### Memory Usage

- Base Python + FastAPI: ~50MB
- ICU library: ~30MB
- Cached Transliterators: ~5-10MB each
- **Total per pod**: ~200-300MB (10-15 cached transforms)

## Monitoring

### Prometheus Metrics

Available at `/metrics`:

- `http_requests_total` - Total requests per endpoint
- `http_request_duration_seconds` - Request latency histogram
- `http_requests_in_progress` - Concurrent requests
- Custom: `icu_cache_size`, `icu_cache_hit_rate`

### Health Checks

- **Liveness**: `/health` every 30s (restart if failing)
- **Readiness**: `/health` every 10s (remove from service if failing)
- **Startup**: `/health` every 5s, 60s max startup time

## Troubleshooting

### Common Issues

**PyICU not installed:**
```bash
# Install ICU libraries (macOS)
brew install icu4c pkg-config

# Install ICU libraries (Ubuntu)
sudo apt-get install libicu-dev pkg-config

# Reinstall dependencies
make install
```

**Service not responding:**
```bash
# Check health
curl http://localhost:8083/health

# Check logs
make k8s-logs

# Check cache stats
curl http://localhost:8083/cache-stats
```

**High latency:**
- Check batch size (optimal: 500 texts)
- Verify cache hit rate (should be >90%)
- Check HPA scaling status
- Review Prometheus metrics

## Architecture Details

### Multi-Stage Docker Build

**Stage 1: Builder**
- Base: `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`
- Installs ICU development libraries
- Compiles PyICU with UV

**Stage 2: Runtime**
- Base: `registry.access.redhat.com/ubi9/python-311`
- Installs only ICU runtime libraries
- Copies `.venv` from builder
- Non-root user (UID 1001)
- ~400MB final image

### Caching Strategy

**ICUCache Singleton:**
- Thread-safe with double-check locking
- Lazy loading (0MB at startup)
- Cache key: `{transform_id}:{direction}`
- No eviction (ICU objects are immutable)
- Tracks hits/misses per transform

**Benefits:**
- 95%+ cache hit rate in production
- 10-100x faster than creating new Transliterators
- Minimal memory footprint (~5-10MB per cached object)

## Production Checklist

- [ ] Install dependencies: `make install`
- [ ] Run tests: `make test` (all 141 tests passing)
- [ ] Type check: `make typecheck` (strict mode)
- [ ] Build Docker: `make build`
- [ ] Test locally: `make run` + manual testing
- [ ] Deploy to K8s: `make k8s-deploy`
- [ ] Verify health: `kubectl get pods -n sentinel-translate`
- [ ] Load test: Run PySpark job with production data
- [ ] Monitor metrics: Check Prometheus dashboards
- [ ] Set up alerts: CPU/memory/error rate thresholds

## License

Part of SentinelTranslate project.

## Contributing

Follow the existing patterns from `ner-service` and `lang-detect-service`:
- Use UV for dependency management
- Ruff for formatting/linting (140 char lines)
- basedpyright for strict type checking
- pytest for comprehensive testing
- Multi-stage Docker builds (UV + UBI)
