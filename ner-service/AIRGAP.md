# Air-Gapped Deployment Guide

This guide covers deploying the NER service in environments without internet access.

## Overview

The NER service supports air-gapped deployments using pre-packaged models stored in S3 or local storage. All models are embedded in the container image at build time, ensuring no runtime internet dependencies.

## Prerequisites

- Docker or container build environment with S3 access (for S3 method)
- AWS credentials or IAM role (for private S3 buckets)
- ~12GB disk space for build artifacts
- Target deployment environment (Kubernetes, Docker, etc.)

## Deployment Methods

### Method 1: S3-Based Build (Recommended)

Best for organizations with existing S3 infrastructure.

#### Step 1: Prepare S3 Bucket

Upload pre-packaged models to S3:

```bash
# On a machine with internet access
cd ner-service

# Download all models
make download-all-models

# Create manifest and package
tar czf ner-models.tar.gz models/

# Upload to S3
aws s3 cp ner-models.tar.gz s3://your-bucket/ner-models/
aws s3 cp models/MANIFEST.json s3://your-bucket/ner-models/

# Or use the S3 upload script
uv run python upload_models_to_s3.py \
  --bucket your-bucket \
  --prefix ner-models/ \
  --models-dir ./models
```

#### Step 2: Build Container

On a build machine with S3 access:

```bash
# Build with all models (~3GB image)
make build-s3-full S3_BUCKET=your-bucket S3_PREFIX=ner-models/

# Or build with dev models (~1.5GB image)
make build-s3 S3_BUCKET=your-bucket S3_PREFIX=ner-models/

# Tag for your registry
docker tag ner-service:latest-s3-full your-registry.com/ner-service:v1.0

# Push to private registry
docker push your-registry.com/ner-service:v1.0
```

#### Step 3: Deploy to Air-Gapped Environment

```bash
# In air-gapped environment, update deployment with your registry
# Edit k8s/deployment.yaml
#   image: your-registry.com/ner-service:v1.0

kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### Method 2: Pre-Built Image Transfer

Best for fully isolated environments without S3.

#### Step 1: Build Image on Connected Machine

```bash
cd ner-service

# Download models
make download-all-models

# Build with embedded models using standard Dockerfile
docker build -t ner-service:latest --build-arg MODEL_SET=full .

# Save image to tarball
docker save ner-service:latest | gzip > ner-service-full.tar.gz
```

#### Step 2: Transfer to Air-Gapped Environment

```bash
# Copy tarball to air-gapped machine via approved transfer method
# (USB, secure file transfer, etc.)

# On air-gapped machine:
docker load < ner-service-full.tar.gz
docker tag ner-service:latest your-private-registry/ner-service:latest
docker push your-private-registry/ner-service:latest
```

#### Step 3: Deploy

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### Method 3: Volume Mount with Pre-Downloaded Models

Best for environments where you want to update models without rebuilding containers.

#### Step 1: Prepare Models

```bash
# On connected machine
cd ner-service
make download-all-models

# Package models
tar czf ner-models.tar.gz models/
```

#### Step 2: Transfer and Extract

```bash
# Copy to air-gapped environment
# Extract to persistent volume location
mkdir -p /mnt/ner-models
tar xzf ner-models.tar.gz -C /mnt/ner-models
```

#### Step 3: Deploy with Volume Mount

```bash
# Update k8s/deployment.yaml to mount the volume
# Set environment variables:
#   SPACY_MODEL_PATH=/mnt/ner-models/models/spacy
#   STANZA_MODEL_PATH=/mnt/ner-models/models/stanza

kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

## Model Sets

Choose the appropriate model set for your needs:

### Full Production Set

- **spaCy**: 21 large models (20 languages + multilingual fallback)
- **Stanza**: 60+ languages
- **Size**: ~10GB models + ~200MB container = ~10.2GB total
- **Use case**: Production with comprehensive language support

```bash
make download-all-models
# Or for S3 build
make build-s3-full S3_BUCKET=your-bucket
```

### Development Set

- **spaCy**: 6 large models (en, fr, de, es, zh, xx)
- **Stanza**: 6 common languages
- **Size**: ~3GB models + ~200MB container = ~3.2GB total
- **Use case**: Development, testing, or limited language requirements

```bash
make download-languages LANGUAGES=en,fr,de,es,zh
# Or for S3 build
make build-s3 S3_BUCKET=your-bucket
```

### Custom Language Set

```bash
# Download only the languages you need
make download-languages LANGUAGES=en,fr,ar,ja

# Build with custom set
docker build -t ner-service:custom \
  --build-arg MODEL_SET=full \
  .
```

## S3 Configuration

### Public Bucket

```bash
# No credentials needed
make build-s3-full S3_BUCKET=public-bucket S3_PREFIX=models/
```

### Private Bucket with IAM Role

```bash
# Use IAM role attached to build instance
make build-s3-full S3_BUCKET=private-bucket S3_PREFIX=models/
```

### Private Bucket with Credentials

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1

make build-s3-full S3_BUCKET=private-bucket S3_PREFIX=models/
```

## Verification

After deployment, verify the service:

```bash
# Health check
kubectl -n sentineltranslate port-forward svc/ner-service 8081:8081
curl http://localhost:8081/health

# Check available frameworks
curl http://localhost:8081/frameworks

# Test entity extraction
curl -X POST http://localhost:8081/extract-entities \
  -H "Content-Type: application/json" \
  -d '{"text": "John Smith works at Google", "lang_code": "en"}'

# Verify cache (should show loaded models)
curl http://localhost:8081/cache-stats
```

## Build Arguments

### Dockerfile (Standard Build)

```bash
docker build \
  --build-arg MODEL_SET=full \     # Options: full, dev, minimal
  -t ner-service:latest \
  .
```

### Dockerfile.s3 (Air-Gapped Build)

```bash
docker build \
  -f Dockerfile.s3 \
  --build-arg S3_BUCKET=your-bucket \
  --build-arg S3_PREFIX=models/ \    # Optional, default: ""
  --build-arg MODEL_SET=full \       # Options: full, dev, minimal
  -t ner-service:latest-s3 \
  .
```

## Troubleshooting

### Build Fails: "Models not found in S3"

```bash
# Verify S3 bucket and prefix
aws s3 ls s3://your-bucket/your-prefix/

# Check credentials
aws sts get-caller-identity

# Verify MANIFEST.json exists
aws s3 ls s3://your-bucket/your-prefix/MANIFEST.json
```

### Container Won't Start: "Models not loaded"

```bash
# Check logs
kubectl -n sentineltranslate logs -l app=ner-service

# Verify models in image
docker run -it ner-service:latest ls -la /app/models/spacy
docker run -it ner-service:latest ls -la /app/models/stanza

# For volume-mounted deployments, check volume
kubectl -n sentineltranslate exec -it <pod-name> -- ls /app/models/spacy
```

### Out of Disk Space During Build

```bash
# Clean up Docker build cache
docker system prune -a

# Build with specific model set
make build-s3 S3_BUCKET=your-bucket  # Dev set instead of full
```

### Models Loading Slowly

First request for each language loads the model (~2-5 seconds). This is normal. Subsequent requests are fast (<100ms).

To pre-warm models at startup, make requests for common languages after deployment:

```bash
# Pre-warm common models
for lang in en fr de es; do
  curl -X POST http://localhost:8081/extract-entities \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"test\", \"lang_code\": \"$lang\"}"
done
```

## Security Considerations

### Image Scanning

```bash
# Scan built image for vulnerabilities
docker scan ner-service:latest

# Or use Trivy
trivy image ner-service:latest
```

### S3 Bucket Security

- Use private buckets with least-privilege IAM policies
- Enable S3 encryption at rest
- Use VPC endpoints for S3 access from build instances
- Audit bucket access logs

### Container Security

The NER service runs as non-root user (UID 1001) in a Red Hat UBI base image:

```dockerfile
USER 1001
```

This provides security best practices out of the box.

## Performance

### Build Times

- **Full set**: 15-25 minutes (downloading + building)
- **Dev set**: 8-12 minutes
- **Minimal set**: 5-8 minutes

### Image Sizes

- **Standard Dockerfile (embedded models)**:
  - Full: ~3GB
  - Dev: ~1.5GB
  - Minimal: ~800MB

- **Volume-mounted (models separate)**:
  - Container: ~200MB
  - Models: ~10GB (shared volume)

### Runtime Performance

- **Memory**: 200MB base + 150-200MB per spaCy model (lazy loaded)
- **Startup**: ~5 seconds (no models loaded initially)
- **First request per language**: 2-5 seconds (model loading)
- **Subsequent requests**: <100ms

## Best Practices

1. **Use volume-mounted models for Kubernetes**: Smaller images, faster deployments, easier updates
2. **Pre-package models in S3**: Centralized model distribution, version control
3. **Test in staging**: Verify model loading and accuracy before production
4. **Monitor memory usage**: Scale pods based on number of languages needed
5. **Pre-warm models**: Make initial requests for common languages after deployment
6. **Keep models updated**: Periodically rebuild with latest spaCy/Stanza releases

## File References

- `Dockerfile` - Standard build (GitHub models)
- `Dockerfile.s3` - Air-gapped build (S3 models)
- `download_all_models.py` - Model download script
- `download_models_from_s3.py` - S3 download script
- `k8s/deployment.yaml` - Kubernetes deployment manifest
- `k8s/pvc.yaml` - PersistentVolumeClaim for models
- `k8s/service.yaml` - Kubernetes service

## Support

For issues:
1. Check container logs: `kubectl logs <pod-name>`
2. Verify models: `ls -la /app/models/`
3. Test health endpoint: `curl http://localhost:8081/health`
4. Review this guide's troubleshooting section
