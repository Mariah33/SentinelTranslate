# SentinelTranslate

SentinelTranslate is a high-reliability machine translation pipeline built on NVIDIA Triton Inference Server, FastAPI, Celery, and UV-managed Python environments. It delivers GPU-accelerated OPUS-MT translations while actively preventing hallucinations using multi-layer safety checks, constrained fallback decoding, and sentence-level processing.

---

## 🚀 Features

### 🧠 Hallucination-Resistant Translation
SentinelTranslate includes advanced safeguards to ensure accurate, faithful translations:

- **Language ID validation** (rejects wrong-language inputs)
- **Number consistency checks** (prevents invented or altered numeric values)
- **Named-entity consistency checks** (no fabricated names, places, or organizations)
- **Repetition and length-ratio detection**
- **Hybrid decoding:** fast greedy pass → fallback constrained decode if unsafe

### ⚡ High-Performance Triton Integration
- ONNX-backed OPUS-MT models served through Triton
- Supports 40+ language pairs → English
- Sentence-level parallel processing
- Works with GPU or CPU backends

### 🔧 Modern Python Tooling (UV)
- UV for environment + dependency management
- Ruff + BasedPyright for strict linting and type checks
- Makefile-driven workflows (`make install`, `make test`, etc.)

### 🧱 Distributed Architecture
- **FastAPI Batch API:** Batch S3 parquet translation API
- **FastAPI Sidecar:** Single-text translation API
- **Celery Worker:** Runs decoding, safety checks, and Triton inference (handles both single-text and batch jobs)
- **Redis:** Message broker & result backend
- **Triton Server:** High-performance inference engine

---

## 🏗 Architecture

```
┌─────────────────────────┐         ┌─────────────────────────┐
│  Single-Text Request    │         │  Batch S3 Parquet       │
│  (Sidecar API :8080)    │         │  (Batch API :8090)      │
└───────────┬─────────────┘         └───────────┬─────────────┘
            │                                   │
            └──────────┬────────────────────────┘
                       ↓
                 Celery Queue (Redis)
                       ↓
                 Celery Worker
                 ├─ Single-text task OR Batch parquet task
                 ├─ Sentence Preprocess
                 ├─ Fast Greedy Decode
                 ├─ Safety Checks
                 │     ├─ Language ID
                 │     ├─ Number Consistency
                 │     └─ NER Consistency
                 └─ Fallback Decode (if required)
                       ↓
              Triton Inference Server
                       ↓
          Postprocessing & Assembly
                       ↓
     ┌─────────────────┴──────────────────┐
     ↓                                    ↓
Single-text: Redis result           Batch: S3 parquet output
     ↓                                    ↓
Client polls /status/{job_id}      Client polls /batch/status/{job_id}
```

---

## 📦 Directory Structure

```
sentineltranslate/
│
├── api/                  # FastAPI batch translation API (S3 parquet files)
├── sidecar/              # FastAPI single-text translation API
├── worker/               # Celery worker with safety checks
├── triton/
│   └── model-repository/ # All OPUS-MT ONNX models
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
make worker-install
```

### Run linting & formatting
```bash
# Format and lint all components
make format
make lint

# Or run individually
make sidecar-lint
make worker-lint
```

### Run tests
```bash
# Test all components
make test

# Or test individually
make sidecar-test
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
# Sidecar
cd sidecar && make run

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

**Submit translation job**
```http
POST http://localhost:8080/translate
Content-Type: application/json

{
  "text": "Bonjour le monde",
  "source_lang": "fr",
  "target_lang": "en"
}
```

**Check job status**
```http
GET http://localhost:8080/status/{job_id}
```

---

## 📁 Model Repository

ONNX model files should be placed under:

```
triton/model-repository/opus-mt-<src>-en/1/model.onnx
```

Pre-generated directories for 40+ languages are included.

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
- Sidecar API (single-text translation)
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

- **Sidecar API** (`/metrics`): Request rate, latency, HTTP status codes
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
