# NER Service

Multi-language Named Entity Recognition (NER) microservice supporting 20+ languages via spaCy and 60+ languages via Stanza.

## Features

- **Multi-framework**: Supports both spaCy (20 languages) and Stanza (60+ languages)
- **Volume-mounted models**: Lightweight containers (~200MB) with models stored separately (~10GB)
- **Lazy loading**: Models loaded on-demand to minimize memory usage
- **Thread-safe caching**: Optimal performance for concurrent requests
- **REST API**: Simple HTTP endpoints for entity extraction
- **Kubernetes-ready**: Includes manifests for scalable deployment

## Language Support

### spaCy Models (20 languages)

The service uses spaCy **large models** for maximum accuracy:

| Language | Code | Model |
|----------|------|-------|
| Chinese | zh | zh_core_web_lg |
| Croatian | hr | hr_core_news_lg |
| Danish | da | da_core_news_lg |
| Dutch | nl | nl_core_news_lg |
| English | en | en_core_web_lg |
| Finnish | fi | fi_core_news_lg |
| French | fr | fr_core_news_lg |
| German | de | de_core_news_lg |
| Greek | el | el_core_news_lg |
| Italian | it | it_core_news_lg |
| Japanese | ja | ja_core_news_lg |
| Korean | ko | ko_core_news_lg |
| Lithuanian | lt | lt_core_news_lg |
| Polish | pl | pl_core_news_lg |
| Portuguese | pt | pt_core_news_lg |
| Romanian | ro | ro_core_news_lg |
| Russian | ru | ru_core_news_lg |
| Slovenian | sl | sl_core_news_lg |
| Spanish | es | es_core_news_lg |
| Swedish | sv | sv_core_news_lg |
| Ukrainian | uk | uk_core_news_lg |

Plus multilingual fallback model: `xx_ent_wiki_sm`

### Stanza Models (60+ languages)

Stanza provides broader language coverage including:

af, ar, be, bg, ca, zh, hr, cs, da, nl, en, et, fi, fr, de, el, he, hi, hu, id, it, ja, ko, la, lv, lt, no, fa, pl, pt, ro, ru, sk, sl, es, sv, ta, te, th, tr, uk, ur, vi, eu, hy, ga, is, kk, kmr, ky, mr, my, nn, nb, sa, sr, wo, cy, gd, gl, mt

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for containerized deployment)
- Kubernetes cluster (optional, for production deployment)
- ~10GB disk space for full model set

### Local Development

```bash
cd ner-service

# Install dependencies
make install

# Download models (choose one):
make download-all-models              # All 21 spaCy + 60+ Stanza (~10GB, 30-60 min)
make download-languages LANGUAGES=en,fr,de  # Specific languages only

# Run service locally
make run

# Test the service
curl http://localhost:8081/health
```

### Docker Deployment

```bash
# Build lightweight container
make build

# Run with docker-compose (requires models downloaded first)
make run-with-volume

# Test
curl -X POST http://localhost:8081/extract-entities \
  -H "Content-Type: application/json" \
  -d '{"text": "John Smith works at Microsoft", "lang_code": "en"}'
```

### Kubernetes Deployment

```bash
# Create namespace and deploy
make k8s-deploy

# Check status
make k8s-status

# View logs
make k8s-logs

# Remove deployment
make k8s-delete
```

## Model Download Options

The service supports different model sets for different use cases:

### Full Production Deployment

```bash
# Download all 21 spaCy large models + 60+ Stanza models (~10GB)
make download-all-models
```

This downloads:
- 20 spaCy large models for maximum accuracy
- 1 multilingual fallback model
- 60+ Stanza models for broader language coverage

### Specific Languages Only

```bash
# Download only the languages you need
make download-languages LANGUAGES=en,fr,de,es

# Or use the script directly
uv run python download_all_models.py --output-dir ./models --languages en,fr,de
```

### Framework-Specific Downloads

```bash
# spaCy only
uv run python download_all_models.py --output-dir ./models --spacy-only

# Stanza only
uv run python download_all_models.py --output-dir ./models --stanza-only
```

### Download to Custom Path

```bash
# Download to mounted volume or custom directory
make download-to-volume VOLUME_PATH=/mnt/ner-models
```

## API Endpoints

### Extract Entities

```bash
POST /extract-entities
Content-Type: application/json

{
  "text": "Barack Obama was born in Hawaii",
  "lang_code": "en"
}
```

Response:
```json
{
  "entities": [
    {"text": "Barack Obama", "label": "PERSON", "start": 0, "end": 12},
    {"text": "Hawaii", "label": "GPE", "start": 28, "end": 34}
  ],
  "framework_used": "spacy"
}
```

### Health Check

```bash
GET /health
```

### Supported Languages

```bash
GET /supported-languages
```

Returns list of all supported language codes.

### Cache Statistics

```bash
GET /cache-stats
```

Returns information about loaded models and memory usage.

### Framework Information

```bash
GET /frameworks
```

Returns available NER frameworks (spaCy, Stanza, or both).

## Configuration

Configure the service using environment variables:

### Framework Selection

```bash
# Choose NER framework
export NER_FRAMEWORK=both        # Options: spacy, stanza, both (default: both)
```

### Model Paths

```bash
# Custom model storage locations
export SPACY_MODEL_PATH=/app/models/spacy     # Default
export STANZA_MODEL_PATH=/app/models/stanza   # Default
```

### Fallback Behavior

```bash
# Behavior for unsupported languages
export NER_FALLBACK_MODE=multilingual  # Options: multilingual, strict (default: multilingual)
```

- **multilingual**: Use multilingual fallback model for unsupported languages
- **strict**: Raise error for unsupported languages

### Logging

```bash
export LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR
```

## Architecture

### Volume-Mounted Models

The service uses a volume-mounted architecture for optimal deployment:

```
Container (~200MB)
├── Python application code
├── Dependencies (FastAPI, spaCy, Stanza)
└── Volume mount → /app/models/
                   ├── spacy/     (21 models, ~8GB)
                   └── stanza/    (60+ models, ~2GB)
```

**Benefits:**
- **Fast builds**: 1-2 minutes (vs 15-20 minutes with embedded models)
- **Small images**: 200MB (vs 2-3GB)
- **Easy updates**: Update models without rebuilding containers
- **Cost efficient**: Reduced registry bandwidth and storage costs
- **Kubernetes-friendly**: Shared PersistentVolume across pods

### Memory Usage

- **Startup**: ~50MB (no models loaded)
- **Per spaCy model**: ~150-200MB (lazy loaded on first use)
- **Per Stanza model**: ~20-50MB (lazy loaded on first use)
- **Typical usage**: 200MB-2GB depending on languages requested

Models are cached after first load, making subsequent requests fast.

## File Structure

```
ner-service/
├── app.py                      # FastAPI application
├── download_all_models.py      # Model download utility
├── download_models_from_s3.py  # S3-based download (for air-gap)
├── Dockerfile                  # Standard build
├── Dockerfile.s3               # Air-gapped build from S3
├── docker-compose.yml          # Local development
├── Makefile                    # Build automation
├── pyproject.toml              # Dependencies
├── uv.lock                     # Locked dependencies
├── k8s/
│   ├── pvc.yaml                # PersistentVolumeClaim (12Gi)
│   ├── deployment.yaml         # Kubernetes deployment
│   └── service.yaml            # Kubernetes service
└── models/                     # Downloaded models (created by download script)
    ├── spacy/
    │   ├── en_core_web_lg-3.8.0/
    │   ├── fr_core_news_lg-3.8.0/
    │   └── ... (19 more)
    ├── stanza/
    │   ├── en/
    │   ├── fr/
    │   └── ... (59 more)
    └── MANIFEST.json           # Download metadata
```

## Performance

- **First request per language**: 2-5 seconds (model loading)
- **Subsequent requests**: <100ms (cached model)
- **Container startup**: ~5 seconds (no models loaded)
- **Model download time**: 30-60 minutes for full set

## Troubleshooting

### Models Not Found

```bash
# Verify models directory exists
ls -la models/spacy models/stanza

# Download models if missing
make download-all-models
```

### Container Won't Start

```bash
# Check logs
docker logs ner-service

# Or in Kubernetes
kubectl -n sentineltranslate logs -l app=ner-service
```

### Slow Response Times

First request for each language takes 2-5 seconds to load the model. This is normal. Subsequent requests are fast (<100ms).

### Out of Memory

Increase container memory limits:

```yaml
# k8s/deployment.yaml
resources:
  limits:
    memory: 8Gi  # Increase if using many languages
```

Or reduce number of concurrent languages by restarting pods to clear cache.

### Pod Stuck in Pending

Check PersistentVolume availability:

```bash
kubectl describe pvc ner-models-pvc -n sentineltranslate
kubectl get pv
```

## Development

### Run Tests

```bash
make test
```

### Format Code

```bash
make format
```

### Lint Code

```bash
make lint
```

### Run with Auto-Reload

```bash
make run
```

## Production Deployment

### Prerequisites

1. Kubernetes cluster with persistent volume provisioner
2. Models downloaded and available (via PVC or volume mount)
3. Container image built and pushed to registry

### Deployment Steps

```bash
# 1. Create namespace
kubectl create namespace sentineltranslate

# 2. Create PVC for models (edit k8s/pvc.yaml if needed)
kubectl apply -f k8s/pvc.yaml

# 3. Populate models (one-time setup)
# Option A: Download directly to PVC using a helper pod
kubectl run -it --rm model-loader \
  --image=python:3.11 \
  --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"model-loader","volumeMounts":[{"name":"models","mountPath":"/models"}]}]}}' \
  --volumes='[{"name":"models","persistentVolumeClaim":{"claimName":"ner-models-pvc"}}]' \
  -- /bin/bash

# Inside the pod:
pip install uv
git clone https://github.com/your-org/SentinelTranslate.git
cd SentinelTranslate/ner-service
uv run python download_all_models.py --output-dir /models
exit

# Option B: Copy from local
kubectl cp ./models <helper-pod>:/models

# 4. Deploy service
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# 5. Verify deployment
kubectl -n sentineltranslate get pods
kubectl -n sentineltranslate logs -f deployment/ner-service

# 6. Test
kubectl -n sentineltranslate port-forward svc/ner-service 8081:8081
curl http://localhost:8081/health
```

### Scaling

The deployment includes Horizontal Pod Autoscaler (HPA):

```bash
# View HPA status
kubectl -n sentineltranslate get hpa

# Manual scaling
kubectl -n sentineltranslate scale deployment ner-service --replicas=5
```

## Air-Gapped Deployment

For environments without internet access, see [AIRGAP.md](./AIRGAP.md) for detailed instructions on deploying via S3 or local storage.

## License

See main project LICENSE file.

## Support

For issues or questions:
- Check logs: `make k8s-logs` or `docker logs ner-service`
- Verify models: `ls -la models/`
- Check health endpoint: `curl http://localhost:8081/health`
- Review configuration: Environment variables listed above
