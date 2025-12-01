# SentinelTranslate

SentinelTranslate is a high-reliability machine translation pipeline built on NVIDIA Triton Inference Server, FastAPI, Celery, and UV-managed Python environments. It delivers GPU-accelerated translations (OPUS-MT + NLLB-200) while actively preventing hallucinations using multi-layer safety checks, microservices architecture, constrained fallback decoding, and sentence-level processing.

---

## 🚀 Features

### 🧠 Hallucination-Resistant Translation
SentinelTranslate includes advanced safeguards to ensure accurate, faithful translations:

- **Language ID validation** (rejects wrong-language inputs via langid)
- **Number consistency checks** (prevents invented or altered numeric values)
- **Named-entity consistency checks** (no fabricated names, places, or organizations)
  - Powered by dedicated NER microservice with spaCy models for 20+ languages
  - Lazy-loading architecture for memory efficiency
  - Multilingual fallback for unsupported languages
- **Repetition and length-ratio detection**
- **Hybrid decoding:** fast greedy pass → fallback constrained decode if unsafe

### ⚡ High-Performance Triton Integration
- **OPUS-MT:** 41 language pairs → English (specialized models, ~300MB each)
- **NLLB-200:** 200+ languages with any-to-any translation (unified model, ~1.2GB)
- ONNX-optimized models served through Triton Inference Server
- Sentence-level parallel processing
- Works with GPU or CPU backends
- Model selection via API: `"model": "opus"` (default) or `"model": "nllb"`

### 🔧 Modern Python Tooling (UV)
- UV for environment + dependency management
- Ruff + BasedPyright for strict linting and type checks
- Makefile-driven workflows (`make install`, `make test`, etc.)

### 🧱 Distributed Architecture
- **FastAPI Batch API:** Batch S3 parquet translation API
- **FastAPI Sidecar:** Single-text translation API with hallucination detection
- **FastAPI NER Service:** Named entity recognition microservice (20+ languages with spaCy)
- **Celery Worker:** Runs decoding, safety checks, and Triton inference (handles both single-text and batch jobs)
- **Redis:** Message broker & result backend
- **Triton Server:** High-performance inference engine (OPUS-MT + NLLB-200 models)

---

## 🏗 Architecture

```
┌─────────────────────────┐         ┌─────────────────────────┐
│  Single-Text Request    │         │  Batch S3 Parquet       │
│  (Sidecar API :8080)    │         │  (Batch API :8090)      │
└───────────┬─────────────┘         └───────────┬─────────────┘
            │                                   │
            ↓                                   ↓
     Triton Inference ←────────────────── Celery Queue (Redis)
            │                                   ↓
            │                             Celery Worker
            │                             ├─ S3 parquet task
            │                             ├─ Sentence Preprocess
            ↓                             ├─ Call Sidecar API
     Sidecar Translation                  ├─ Cache Results
     ├─ Sentence Split                    └─ Write S3 Output
     ├─ Triton Inference                        ↓
     ├─ Safety Checks                    Batch: S3 parquet output
     │     ├─ Language ID                       ↓
     │     ├─ Number Consistency    Client polls /batch/status/{job_id}
     │     └─ NER Consistency
     │              ↓
     │        NER Service (:8081)
     │        ├─ spaCy Models (20+ languages)
     │        ├─ Entity Extraction
     │        └─ Multilingual Fallback
     └─ Fallback Decode (if unsafe)
            ↓
     Translation Result
     (returned immediately)
```

**Key Design Points:**
- **Sidecar** handles synchronous translation with hallucination detection
- **Worker** orchestrates batch S3 parquet jobs, calling sidecar for each translation
- **NER Service** provides entity recognition as a microservice (scales independently)
- **Triton** serves both OPUS-MT (41 language pairs) and NLLB-200 (200+ languages)

---

## 📦 Directory Structure

```
sentineltranslate/
│
├── api/                  # FastAPI batch translation API (S3 parquet files)
├── sidecar/              # FastAPI single-text translation API with hallucination detection
├── ner-service/          # FastAPI NER microservice (spaCy models for 20+ languages)
├── worker/               # Celery worker (batch S3 parquet orchestrator)
├── triton/
│   └── model-repository/ # OPUS-MT + NLLB-200 ONNX models
│       ├── opus-mt-*/    # 41 language pairs to English
│       └── nllb-200-distilled-600m/  # Single model for 200+ languages
├── examples/             # Jupyter notebooks for 10 languages + tutorials
│   ├── 01_french_to_english.ipynb
│   ├── 02_spanish_to_english.ipynb
│   ├── ... (10 language pairs total)
│   ├── model_conversion/          # OPUS-MT to ONNX conversion guide
│   └── batch_translation/         # S3 batch processing examples
├── infrastructure/       # Production deployment
│   ├── terraform/        # AWS EKS cluster infrastructure
│   └── helm/             # Kubernetes Helm charts + monitoring
└── docker-compose.yaml
```

---

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- NVIDIA GPU + nvidia-docker (for GPU mode) OR CPU-only mode
- ONNX models placed in `triton/model-repository/` (see [Model Repository](#-model-repository))

### Start All Services

**With GPU:**
```bash
make up
```

**CPU-only mode:**
```bash
make up-cpu
```

**View logs:**
```bash
make logs
```

**Stop services:**
```bash
make down
```

### Access Points
- **Batch API:** http://localhost:8090 (batch S3 parquet translation)
- **Sidecar API:** http://localhost:8080 (single-text translation)
- **NER Service:** http://localhost:8081 (named entity recognition)
- **Triton Server:** http://localhost:8000
- **Redis:** localhost:6379

---

## 🔨 Development Workflow

### Install dependencies (UV)
```bash
# Install all components
make install

# Or install individually
make sidecar-install
make ner-install
make worker-install
```

### Run linting & formatting
```bash
# Format and lint all components
make format
make lint

# Or run individually
make sidecar-lint
make ner-lint
make worker-lint
```

### Run tests
```bash
# Test all components
make test

# Or test individually
make sidecar-test
make ner-test
make worker-test
```

### Docker Compose Commands
```bash
make up            # Start all services (GPU mode)
make up-cpu        # Start all services (CPU-only)
make down          # Stop all services
make logs          # View logs from all services
make ps            # List running services
make restart       # Restart all services
make rebuild       # Rebuild and restart all services
```

### Run components individually
```bash
# Sidecar (port 8080)
cd sidecar && make run

# NER Service (port 8081)
cd ner-service && make run

# Worker
cd worker && make run
```

---

## 🌍 API Endpoints

### Batch API - S3 Parquet Translation

**Submit batch translation job**
```http
POST http://localhost:8090/batch/translate
Content-Type: application/json

{
  "s3_bucket": "my-bucket",
  "s3_key": "data/input.parquet",
  "text_column": "text",
  "source_lang": "fr",
  "target_lang": "en",
  "output_s3_bucket": "my-bucket",  // optional, defaults to input bucket
  "output_s3_key": "data/output.parquet",  // optional, defaults to input_key_translated.parquet
  "id_column": "id"  // optional, preserves ID column in output
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

**Check batch job status**
```http
GET http://localhost:8090/batch/status/{job_id}
```

**Response (in progress):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROGRESS",
  "result": null,
  "error": null
}
```

**Response (completed):**
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

### Sidecar API - Single Text Translation

**Submit translation job (OPUS-MT)**
```http
POST http://localhost:8080/translate
Content-Type: application/json

{
  "text": "Bonjour le monde",
  "source_lang": "fr",
  "target_lang": "en"
}
```

**Submit translation job (NLLB-200)**
```http
POST http://localhost:8080/translate
Content-Type: application/json

{
  "text": "Bonjour le monde",
  "source_lang": "fr",
  "target_lang": "en",
  "model": "nllb"
}
```

**Response:**
```json
{
  "translation": "Hello world"
}
```

### NER Service API - Named Entity Recognition

**Extract entities from text**
```http
POST http://localhost:8081/extract-entities
Content-Type: application/json

{
  "text": "Apple Inc. was founded in Cupertino, California.",
  "lang_code": "en"
}
```

**Response:**
```json
{
  "entities": ["Apple Inc.", "Cupertino", "California"],
  "lang_code": "en",
  "model_used": "en_core_web_sm"
}
```

**Get supported languages**
```http
GET http://localhost:8081/supported-languages
```

**Response:**
```json
{
  "supported_languages": ["en", "fr", "de", "es", "zh", "ja", "ko", ...],
  "fallback_model": "xx_ent_wiki_sm"
}
```

**Get cache statistics**
```http
GET http://localhost:8081/cache-stats
```

**Response:**
```json
{
  "loaded_models": ["en_core_web_sm", "fr_core_news_sm"],
  "cache_size": 2
}
```

**Health check**
```http
GET http://localhost:8081/health
```

---

## 📁 Model Repository

SentinelTranslate supports two model architectures:

### OPUS-MT Models (Default)
ONNX model files should be placed under:

```
triton/model-repository/opus-mt-<src>-en/1/model.onnx
```

Pre-generated directories for 41 language pairs are included.

**Supported Languages:**
ar, bg, bn, cs, da, de, el, es, et, fa, fi, fr, he, hi, hr, hu, id, it, ja, ko, lt, lv, ms, nl, no, pl, pt, ro, ru, sk, sl, sr, sv, ta, te, th, tr, uk, ur, vi, zh

### NLLB-200-distilled-600M (Optional)
Single model supporting 200+ languages:

```
triton/model-repository/nllb-200-distilled-600m/1/model.onnx
```

**Usage:** Set `"model": "nllb"` in the `/translate` request body.

**Export Guide:** See `triton/model-repository/nllb-200-distilled-600m/README.txt` for ONNX export instructions.

---

## 📚 Examples & Tutorials

The `examples/` directory contains comprehensive Jupyter notebooks demonstrating SentinelTranslate for **10 major languages**:

| Language | Code | Script Family | Notebook |
|----------|------|---------------|----------|
| French | `fr` | Latin | `01_french_to_english.ipynb` |
| Spanish | `es` | Latin | `02_spanish_to_english.ipynb` |
| German | `de` | Latin | `03_german_to_english.ipynb` |
| Italian | `it` | Latin | `04_italian_to_english.ipynb` |
| Portuguese | `pt` | Latin | `05_portuguese_to_english.ipynb` |
| Russian | `ru` | Cyrillic | `06_russian_to_english.ipynb` |
| Chinese | `zh` | Logographic | `07_chinese_to_english.ipynb` |
| Japanese | `ja` | Mixed | `08_japanese_to_english.ipynb` |
| Arabic | `ar` | Right-to-Left | `09_arabic_to_english.ipynb` |
| Korean | `ko` | Hangul | `10_korean_to_english.ipynb` |

### Advanced Tutorials

- **`model_conversion/convert_opus_to_onnx.ipynb`** - Convert OPUS-MT models to ONNX format for Triton
- **`batch_translation/batch_s3_example.ipynb`** - Process parquet files from S3 at scale

Each notebook includes:
- Basic translation examples
- Common phrases and vocabulary
- Edge cases (numbers, entities, special characters)
- Hallucination detection demonstrations
- Performance benchmarking
- Error handling

### Getting Started with Examples

```bash
cd examples
jupyter notebook

# Open any language notebook, e.g.:
open 01_french_to_english.ipynb
```

See [`examples/README.md`](examples/README.md) for complete documentation.

---

## ☁️ Production Deployment

### AWS EKS Infrastructure

Production-ready Terraform infrastructure for deploying to AWS EKS:

```bash
cd infrastructure/terraform

# Initialize and deploy EKS cluster
make init
make plan
make apply

# Configure kubectl
make kubeconfig
```

**Features:**
- Free-tier optimized ($140-$550/month depending on configuration)
- CPU node group (t3.medium) + GPU node group (g4dn.xlarge)
- Auto-scaling (GPU nodes scale to 0 when idle)
- IRSA roles for secure S3 access
- VPC with public/private subnets
- CloudWatch logging and monitoring

See [`infrastructure/terraform/README.md`](infrastructure/terraform/README.md) for detailed deployment guide.

### Kubernetes Deployment (Helm)

Deploy all components to Kubernetes with auto-scaling and monitoring:

```bash
cd infrastructure/helm/sentineltranslate

# Install with production configuration
helm install sentineltranslate . -f values-prod.yaml

# Or install with monitoring enabled
helm install sentineltranslate . -f values-prod.yaml -f values-monitoring.yaml
```

**Components:**
- Redis (persistent storage, Bitnami chart)
- Triton Inference Server (GPU-accelerated, nvidia.com/gpu: 1)
- Sidecar API (single-text translation with hallucination detection)
- NER Service (named entity recognition microservice, 20+ languages)
- Batch API (S3 parquet translation)
- Celery Workers (2+ replicas with HPA)
- AWS ALB Ingress (TLS/HTTPS)
- Prometheus & Grafana (optional monitoring)

**Makefile Commands:**
```bash
make install-prod          # Install with production settings
make monitoring-install    # Deploy Prometheus/Grafana stack
make port-forward-grafana  # Access Grafana dashboard
make logs-sidecar          # View sidecar logs
make check-metrics         # Verify Prometheus metrics
```

See [`infrastructure/helm/sentineltranslate/README.md`](infrastructure/helm/sentineltranslate/README.md) for complete Helm documentation.

---

## 📊 Monitoring & Observability

SentinelTranslate includes comprehensive monitoring via **Prometheus & Grafana**:

### Metrics Exposed

- **Sidecar API** (`/metrics`): Request rate, latency, HTTP status codes, hallucination detection rate
- **NER Service** (`/metrics`): Entity extraction requests, model loading time, cache hit rate
- **Batch API** (`/metrics`): Job submissions, processing time, S3 operations
- **Triton Server** (port 8002): GPU utilization, inference latency, throughput
- **Celery Workers** (port 9808): Task success/failure, queue depth, processing time
- **Redis** (port 9121): Memory usage, connections, command stats

### Pre-configured Alerts

**Critical:**
- API/Server down
- Container OOM killed
- No active workers

**Warning:**
- High error rate (>5%)
- High latency (p95 >2s)
- High GPU utilization (>90%)
- High queue depth (>1000)

### Access Monitoring

```bash
cd infrastructure/helm/sentineltranslate

# Deploy monitoring stack
make monitoring-install-prod

# Access Grafana dashboard
make port-forward-grafana
# Login at http://localhost:3000 (admin/password)

# View Prometheus
make port-forward-prometheus
# Access at http://localhost:9090

# Check active alerts
make alerts-firing
```

See [`infrastructure/helm/sentineltranslate/MONITORING.md`](infrastructure/helm/sentineltranslate/MONITORING.md) for complete monitoring guide.

---

## 🛡 Why SentinelTranslate?

Hallucinations in MT can fabricate:

- names  
- locations  
- dates  
- amounts  
- domain-critical details  

SentinelTranslate stops this with layered verification, making it suitable for:

- Legal translations  
- Government workflows  
- Medical documents  
- Corporate data pipelines  
- High-precision multilingual ETL / NLP systems  

---

## 📜 License



---

## 🤝 Contributions

PRs and issues welcome!  
Add new language pairs, improve safety logic, or enhance infrastructure.
