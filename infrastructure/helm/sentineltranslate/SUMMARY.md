# SentinelTranslate Helm Chart - Summary

## Overview

A production-ready Helm chart for deploying SentinelTranslate distributed machine translation pipeline to Kubernetes/EKS.

## Chart Structure

```
sentineltranslate/
├── Chart.yaml                 # Chart metadata and dependencies
├── values.yaml                # Default configuration values
├── values-dev.yaml            # Development environment overrides
├── values-prod.yaml           # Production environment overrides
├── .helmignore               # Files to ignore when packaging
├── Makefile                  # Convenient make targets
├── validate.sh               # Structure validation script
├── README.md                 # Comprehensive documentation
├── INSTALL.md                # Step-by-step installation guide
├── charts/                   # Dependency charts (Redis)
└── templates/                # Kubernetes manifests
    ├── _helpers.tpl          # Template helpers and functions
    ├── NOTES.txt             # Post-install instructions
    ├── serviceaccounts.yaml  # Service accounts for all components
    ├── triton-deployment.yaml
    ├── triton-service.yaml
    ├── sidecar-deployment.yaml
    ├── sidecar-service.yaml
    ├── api-deployment.yaml
    ├── api-service.yaml
    ├── worker-deployment.yaml
    ├── ingress.yaml          # ALB ingress configuration
    ├── hpa.yaml              # HorizontalPodAutoscaler for APIs/workers
    └── pdb.yaml              # PodDisruptionBudget for HA
```

## Components Deployed

### 1. Redis (Bitnami subchart)
- **Purpose**: Message broker (DB 0) and result backend (DB 1)
- **Type**: StatefulSet
- **Persistence**: 20Gi PVC (production), emptyDir (dev)
- **Resources**: 256Mi-512Mi memory, 100m-500m CPU
- **Configuration**: Standalone mode (can be changed to replication/sentinel)

### 2. NVIDIA Triton Inference Server
- **Purpose**: GPU-accelerated ML model serving for OPUS-MT models
- **Type**: Deployment
- **Replicas**: 1 (default)
- **GPU**: 1x NVIDIA GPU per pod (nvidia.com/gpu: 1)
- **Ports**: 8000 (HTTP), 8001 (gRPC), 8002 (metrics)
- **Node Selection**: nodeSelector for GPU nodes + tolerations
- **Health Checks**: /v2/health/live and /v2/health/ready
- **Model Storage**: emptyDir (dev) or PVC (prod)

### 3. Sidecar API (FastAPI)
- **Purpose**: Single-text translation endpoint
- **Type**: Deployment
- **Replicas**: 2+ (auto-scalable)
- **Port**: 8080
- **Health Endpoint**: /health
- **Resources**: 256Mi-512Mi memory, 200m-1000m CPU
- **Environment**: REDIS_BROKER, REDIS_BACKEND, TRITON_URL
- **Features**: HPA, PDB, anti-affinity for HA

### 4. Batch API (FastAPI)
- **Purpose**: Batch parquet file translation via S3
- **Type**: Deployment
- **Replicas**: 2+ (auto-scalable)
- **Port**: 8090
- **Health Endpoint**: /health
- **Resources**: 512Mi-1Gi memory, 250m-1000m CPU
- **IRSA**: ServiceAccount with IAM role annotation for S3 access
- **Environment**: REDIS_BROKER, REDIS_BACKEND, AWS_REGION
- **Features**: HPA, PDB, anti-affinity for HA

### 5. Celery Workers
- **Purpose**: Execute translation tasks with hallucination detection
- **Type**: Deployment
- **Replicas**: 2+ (auto-scalable based on queue length)
- **Resources**: 512Mi-2Gi memory, 250m-2000m CPU
- **IRSA**: ServiceAccount with IAM role annotation for S3 access
- **Environment**: CELERY_BROKER_URL, CELERY_RESULT_BACKEND, TRITON_URL
- **Celery Config**: Concurrency, log level, max tasks per child
- **Features**: HPA, PDB, anti-affinity for distribution

### 6. Ingress (AWS ALB)
- **Type**: networking.k8s.io/v1 Ingress
- **Controller**: aws-load-balancer-controller
- **Scheme**: internet-facing (configurable)
- **Target Type**: IP (for Fargate compatibility)
- **TLS**: ACM certificate via annotations
- **Routes**:
  - `/api/v1/translate` → Sidecar API (8080)
  - `/api/v1/batch` → Batch API (8090)
- **Features**: SSL redirect, health checks, WAF integration (optional)

## Key Features

### High Availability
- Multiple replicas for all stateless components
- PodDisruptionBudget to prevent simultaneous pod terminations
- Anti-affinity rules to spread pods across nodes
- Redis persistence for message durability

### Auto-Scaling
- HorizontalPodAutoscaler for:
  - Sidecar API (CPU/Memory based)
  - Batch API (CPU/Memory based)
  - Workers (CPU/Memory + custom metrics for queue length)
- Configurable min/max replicas and target utilization

### Security
- IRSA (IAM Roles for Service Accounts) for AWS credentials
- No hard-coded access keys
- ServiceAccounts with role annotations
- Security contexts (non-root user, dropped capabilities)
- Optional network policies
- TLS/HTTPS via ACM certificates

### Observability
- Prometheus ServiceMonitor support
- Health check endpoints for all APIs
- Comprehensive logging
- Triton metrics endpoint (8002)
- Redis metrics (via bitnami/redis)

### GPU Support
- Dedicated GPU resources for Triton
- Node selector for GPU instance types
- Tolerations for GPU taints
- NVIDIA device plugin integration

### Environment Separation
- `values-dev.yaml`: Minimal resources, no persistence, single replicas
- `values-prod.yaml`: HA configuration, autoscaling, IRSA, monitoring

## Configuration Highlights

### Image Management
```yaml
sidecar:
  image:
    repository: <ECR_REGISTRY>/sentineltranslate-sidecar
    tag: v1.0.0
    pullPolicy: IfNotPresent
```

### IRSA Configuration
```yaml
api:
  serviceAccount:
    create: true
    annotations:
      eks.amazonaws.com/role-arn: "arn:aws:iam::<ACCOUNT>:role/sentineltranslate-api-role"
```

### Resource Limits
```yaml
sidecar:
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "2000m"
```

### Autoscaling
```yaml
sidecar:
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetCPUUtilizationPercentage: 60
    targetMemoryUtilizationPercentage: 70
```

### Ingress with ALB
```yaml
ingress:
  enabled: true
  className: alb
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:..."
  hosts:
    - host: translate.example.com
      paths:
        - path: /api/v1/translate
          backend:
            service:
              name: sidecar
              port: 8080
```

## Quick Start

### Prerequisites
- Kubernetes 1.21+ cluster
- Helm 3.8+
- GPU nodes with NVIDIA device plugin (for Triton)
- AWS Load Balancer Controller (for ingress)

### Installation Commands

```bash
# Add dependencies
cd infrastructure/helm/sentineltranslate
helm repo add bitnami https://charts.bitnami.com/bitnami
helm dependency update

# Validate chart
./validate.sh
helm lint .

# Install development
helm install sentineltranslate . \
  --namespace sentineltranslate \
  --create-namespace \
  --values values-dev.yaml

# Install production
helm install sentineltranslate . \
  --namespace sentineltranslate \
  --create-namespace \
  --values values-prod.yaml \
  --values my-custom-values.yaml
```

### Makefile Targets
```bash
make help                 # Show all available targets
make dependency-update    # Update chart dependencies
make lint                 # Lint the chart
make install-dev          # Install with dev values
make install-prod         # Install with prod values
make upgrade-dev          # Upgrade with dev values
make logs-sidecar         # Tail sidecar logs
make port-forward-sidecar # Port-forward sidecar to localhost:8080
```

## Testing

### Validation
```bash
# Structure validation
./validate.sh

# Helm lint
helm lint .

# Template rendering
helm template sentineltranslate . --values values-dev.yaml

# Dry-run installation
make dry-run-dev
```

### Health Checks
```bash
# Check all pods
kubectl get pods -n sentineltranslate

# Check services
kubectl get svc -n sentineltranslate

# Test Triton health
kubectl port-forward -n sentineltranslate svc/sentineltranslate-triton 8000:8000
curl http://localhost:8000/v2/health/live

# Test Sidecar API health
kubectl port-forward -n sentineltranslate svc/sentineltranslate-sidecar 8080:8080
curl http://localhost:8080/health
```

## Production Considerations

### Before Deploying to Production

1. **Build and Push Images**
   - Build Docker images for all components
   - Push to ECR with semantic version tags
   - Update image repositories and tags in values

2. **Create IRSA Roles**
   - Create IAM policies for S3 access
   - Create IAM roles with OIDC trust policy
   - Attach policies to roles
   - Update serviceAccount annotations with role ARNs

3. **Provision GPU Nodes**
   - Create EKS node group with GPU instances (g4dn.xlarge)
   - Install NVIDIA device plugin
   - Verify GPU availability

4. **Install AWS Load Balancer Controller**
   - Required for ALB ingress
   - Configure with cluster name

5. **Request ACM Certificate**
   - For HTTPS/TLS on ingress
   - Add certificate ARN to ingress annotations

6. **Configure DNS**
   - Create Route53 records pointing to ALB
   - Update ingress host to your domain

7. **Set Resource Limits**
   - Review and adjust based on expected load
   - Monitor and tune after initial deployment

8. **Enable Monitoring**
   - Install Prometheus/Grafana
   - Enable ServiceMonitors
   - Configure alerting

## Troubleshooting Guide

See README.md section "Troubleshooting" for detailed debugging steps for:
- GPU issues
- Triton not starting
- Workers not processing tasks
- Ingress not creating ALB
- IRSA permission errors

## Maintenance

### Upgrading
```bash
# Update image tags
helm upgrade sentineltranslate . \
  --values values-prod.yaml \
  --set sidecar.image.tag=v1.1.0

# Update configuration
helm upgrade sentineltranslate . \
  --values values-prod.yaml
```

### Scaling
```bash
# Manual scaling
kubectl scale deployment sentineltranslate-worker \
  -n sentineltranslate \
  --replicas=10

# Or edit HPA
kubectl edit hpa sentineltranslate-worker -n sentineltranslate
```

### Monitoring
```bash
# View resource usage
kubectl top pods -n sentineltranslate

# Check HPA status
kubectl get hpa -n sentineltranslate

# View events
kubectl get events -n sentineltranslate --sort-by='.lastTimestamp'
```

## Files Reference

| File | Purpose |
|------|---------|
| `Chart.yaml` | Chart metadata, version, dependencies |
| `values.yaml` | Default configuration values |
| `values-dev.yaml` | Development environment overrides |
| `values-prod.yaml` | Production environment overrides |
| `README.md` | Comprehensive documentation |
| `INSTALL.md` | Step-by-step installation guide |
| `SUMMARY.md` | This file - quick reference |
| `Makefile` | Convenient commands for common operations |
| `validate.sh` | Chart structure validation |
| `templates/_helpers.tpl` | Reusable template functions |
| `templates/NOTES.txt` | Post-install instructions |
| `templates/*-deployment.yaml` | Pod specifications for each component |
| `templates/*-service.yaml` | Service definitions |
| `templates/ingress.yaml` | ALB ingress configuration |
| `templates/hpa.yaml` | Auto-scaling configuration |
| `templates/pdb.yaml` | Pod disruption budgets |
| `templates/serviceaccounts.yaml` | IRSA service accounts |

## Next Steps

1. Review and customize `values-prod.yaml` for your environment
2. Build and push Docker images to ECR
3. Create IRSA roles and policies
4. Run validation: `./validate.sh && helm lint .`
5. Test with dry-run: `make dry-run-prod`
6. Deploy to staging first
7. Monitor and tune resources
8. Deploy to production

## Support

- Documentation: See README.md and INSTALL.md
- Chart Issues: Check validation with `./validate.sh`
- Helm Issues: Run `helm lint .` and `helm template .`
- Kubernetes Issues: Check pod logs and events

## License

MIT License - See LICENSE file in repository root
