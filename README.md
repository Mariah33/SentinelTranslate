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
- **FastAPI Frontend:** Batch S3 parquet translation API
- **FastAPI Sidecar:** Single-text translation API
- **Celery Worker:** Runs decoding, safety checks, and Triton inference (handles both single-text and batch jobs)
- **Redis:** Message broker & result backend
- **Triton Server:** High-performance inference engine

---

## 🏗 Architecture

```
┌─────────────────────────┐         ┌─────────────────────────┐
│  Single-Text Request    │         │  Batch S3 Parquet       │
│  (Sidecar API :8080)    │         │  (Frontend API :8090)   │
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
├── frontend/             # FastAPI batch translation API (S3 parquet files)
├── sidecar/              # FastAPI single-text translation API
├── worker/               # Celery worker with safety checks
├── triton/
│   └── model-repository/ # All OPUS-MT ONNX models
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
- **Frontend API:** http://localhost:8090 (batch S3 parquet translation)
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

### Frontend API - Batch S3 Parquet Translation

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
