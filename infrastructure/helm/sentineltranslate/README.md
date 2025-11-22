# SentinelTranslate Helm Chart

This Helm chart deploys SentinelTranslate, a distributed machine translation pipeline with hallucination prevention, to Kubernetes/EKS.

## Overview

SentinelTranslate is a production-ready translation system that uses:
- **NVIDIA Triton Inference Server** for GPU-accelerated OPUS-MT models
- **FastAPI** for REST API endpoints (single-text and batch processing)
- **Celery** workers for distributed translation with safety checks
- **Redis** as message broker and result backend

## Architecture

```
┌─────────────┐
│   Ingress   │ (AWS ALB)
└──────┬──────┘
       │
       ├─────────────┐
       │             │
┌──────▼──────┐ ┌───▼────────┐
│  Sidecar API│ │  Batch API │
│  (FastAPI)  │ │  (FastAPI) │
└──────┬──────┘ └─────┬──────┘
       │              │
       │   ┌──────────▼──────────┐
       │   │  Celery Workers     │
       │   │  (Translation +     │
       │   │   Safety Checks)    │
       │   └──────┬──────────────┘
       │          │
       ├──────────┼───────────┐
       │          │           │
┌──────▼──────┐ ┌▼─────┐ ┌───▼────────┐
│   Redis     │ │Triton│ │     S3     │
│  (Broker/   │ │(GPU) │ │  (Batch    │
│   Backend)  │ │      │ │   Files)   │
└─────────────┘ └──────┘ └────────────┘
```

## Components

### 1. Redis
- **Purpose**: Message broker (DB 0) and result backend (DB 1)
- **Deployment**: Single master (can be configured for HA)
- **Storage**: Persistent volume (20Gi default)
- **Chart**: Bitnami Redis as subchart dependency

### 2. NVIDIA Triton Inference Server
- **Purpose**: ML model serving for OPUS-MT translation models
- **GPU**: Requires 1 GPU per pod (nvidia.com/gpu)
- **Ports**: 8000 (HTTP), 8001 (gRPC), 8002 (metrics)
- **Storage**: EmptyDir (dev) or PVC (prod) for model repository
- **Node Selection**: Uses nodeSelector and tolerations for GPU nodes

### 3. Sidecar API
- **Purpose**: Single-text translation endpoint
- **Port**: 8080
- **Replicas**: 2+ (auto-scalable)
- **Health Check**: `/health`
- **Dependencies**: Redis, Triton

### 4. Batch API
- **Purpose**: Batch parquet file translation
- **Port**: 8090
- **Replicas**: 2+ (auto-scalable)
- **IRSA**: Requires IAM role for S3 access
- **Health Check**: `/health`
- **Dependencies**: Redis, Celery Workers

### 5. Celery Workers
- **Purpose**: Execute translation tasks with multi-layer safety checks
- **Replicas**: 2+ (auto-scalable based on queue length)
- **IRSA**: Requires IAM role for S3 access
- **Dependencies**: Redis, Triton, S3

## Prerequisites

### Kubernetes Cluster
- Kubernetes 1.21+
- Helm 3.8+
- kubectl configured to access your cluster

### GPU Support (for Triton)
- EKS cluster with GPU node group (e.g., g4dn.xlarge with T4 GPU)
- NVIDIA device plugin installed:
  ```bash
  kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
  ```

### AWS Load Balancer Controller (for Ingress)
- Required for ALB ingress
- Installation:
  ```bash
  helm repo add eks https://aws.github.io/eks-charts
  helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
    -n kube-system \
    --set clusterName=<your-cluster-name>
  ```

### IAM Roles for Service Accounts (IRSA)
For production deployments, create IAM roles for:
1. **Batch API**: S3 read/write access
2. **Celery Workers**: S3 read/write access

Example trust policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/oidc.eks.<REGION>.amazonaws.com/id/<OIDC_ID>"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.<REGION>.amazonaws.com/id/<OIDC_ID>:sub": "system:serviceaccount:<NAMESPACE>:sentineltranslate-api"
        }
      }
    }
  ]
}
```

S3 permissions policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-translation-bucket/*",
        "arn:aws:s3:::your-translation-bucket"
      ]
    }
  ]
}
```

## Installation

### 1. Add Helm Repository Dependencies

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
```

### 2. Build and Push Docker Images

Build images for all components:

```bash
# Set your ECR repository URL
export ECR_REGISTRY=<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
export IMAGE_TAG=v1.0.0

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REGISTRY

# Build and push sidecar
cd sidecar
docker build -t $ECR_REGISTRY/sentineltranslate-sidecar:$IMAGE_TAG .
docker push $ECR_REGISTRY/sentineltranslate-sidecar:$IMAGE_TAG

# Build and push batch API
cd ../api
docker build -t $ECR_REGISTRY/sentineltranslate-api:$IMAGE_TAG .
docker push $ECR_REGISTRY/sentineltranslate-api:$IMAGE_TAG

# Build and push worker
cd ../worker
docker build -t $ECR_REGISTRY/sentineltranslate-worker:$IMAGE_TAG .
docker push $ECR_REGISTRY/sentineltranslate-worker:$IMAGE_TAG
```

### 3. Install the Chart

#### Development (Local/Minikube)

```bash
helm install sentineltranslate ./infrastructure/helm/sentineltranslate \
  --namespace sentineltranslate \
  --create-namespace \
  --values ./infrastructure/helm/sentineltranslate/values-dev.yaml
```

#### Production (EKS)

First, update `values-prod.yaml` with your specific values:
- ECR image repositories and tags
- IAM role ARNs for IRSA
- ACM certificate ARN for HTTPS
- Ingress hostname
- Node selectors for GPU nodes

Then install:

```bash
helm install sentineltranslate ./infrastructure/helm/sentineltranslate \
  --namespace sentineltranslate \
  --create-namespace \
  --values ./infrastructure/helm/sentineltranslate/values-prod.yaml
```

### 4. Verify Deployment

```bash
# Check pod status
kubectl get pods -n sentineltranslate

# Check services
kubectl get svc -n sentineltranslate

# Check ingress (if enabled)
kubectl get ingress -n sentineltranslate

# View logs
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=sidecar --tail=100
```

## Configuration

### Key Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Enable Redis subchart | `true` |
| `triton.enabled` | Enable Triton Inference Server | `true` |
| `triton.resources.limits.nvidia.com/gpu` | Number of GPUs for Triton | `1` |
| `sidecar.enabled` | Enable Sidecar API | `true` |
| `sidecar.replicaCount` | Number of sidecar replicas | `2` |
| `sidecar.autoscaling.enabled` | Enable HPA for sidecar | `false` |
| `api.enabled` | Enable Batch API | `true` |
| `api.serviceAccount.annotations` | IRSA annotations for API | `{}` |
| `worker.enabled` | Enable Celery workers | `true` |
| `worker.replicaCount` | Number of worker replicas | `2` |
| `worker.celery.concurrency` | Celery worker concurrency | `4` |
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class name | `alb` |

### Image Configuration

Update image repositories and tags:

```yaml
sidecar:
  image:
    repository: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/sentineltranslate-sidecar
    tag: v1.0.0

api:
  image:
    repository: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/sentineltranslate-api
    tag: v1.0.0

worker:
  image:
    repository: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/sentineltranslate-worker
    tag: v1.0.0
```

### IRSA Configuration

Configure IAM roles for service accounts:

```yaml
api:
  serviceAccount:
    create: true
    annotations:
      eks.amazonaws.com/role-arn: "arn:aws:iam::<ACCOUNT_ID>:role/sentineltranslate-api-role"

worker:
  serviceAccount:
    create: true
    annotations:
      eks.amazonaws.com/role-arn: "arn:aws:iam::<ACCOUNT_ID>:role/sentineltranslate-worker-role"
```

### Resource Requests/Limits

Adjust based on your workload:

```yaml
sidecar:
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "2000m"

worker:
  resources:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "4Gi"
      cpu: "4000m"
```

### Autoscaling

Enable HPA for components:

```yaml
sidecar:
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetCPUUtilizationPercentage: 60
    targetMemoryUtilizationPercentage: 70

worker:
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 50
    targetCPUUtilizationPercentage: 70
```

### Ingress Configuration

Configure ALB ingress:

```yaml
ingress:
  enabled: true
  className: alb
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:us-east-1:<ACCOUNT_ID>:certificate/<CERT_ID>"
  hosts:
    - host: translate.example.com
      paths:
        - path: /api/v1/translate
          pathType: Prefix
          backend:
            service:
              name: sidecar
              port: 8080
        - path: /api/v1/batch
          pathType: Prefix
          backend:
            service:
              name: api
              port: 8090
```

## Upgrading

### Update Image Tags

```bash
helm upgrade sentineltranslate ./infrastructure/helm/sentineltranslate \
  --namespace sentineltranslate \
  --values ./infrastructure/helm/sentineltranslate/values-prod.yaml \
  --set sidecar.image.tag=v1.1.0 \
  --set api.image.tag=v1.1.0 \
  --set worker.image.tag=v1.1.0
```

### Update Configuration

```bash
helm upgrade sentineltranslate ./infrastructure/helm/sentineltranslate \
  --namespace sentineltranslate \
  --values ./infrastructure/helm/sentineltranslate/values-prod.yaml
```

## Uninstalling

```bash
helm uninstall sentineltranslate --namespace sentineltranslate
```

To delete the namespace:

```bash
kubectl delete namespace sentineltranslate
```

## Troubleshooting

### GPU Issues

Check GPU availability:
```bash
kubectl describe nodes | grep -A 10 "Allocatable:" | grep nvidia.com/gpu
```

Verify NVIDIA device plugin:
```bash
kubectl get pods -n kube-system | grep nvidia
```

### Triton Not Starting

Check logs:
```bash
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=triton
```

Verify model repository is populated:
```bash
kubectl exec -n sentineltranslate deployment/<release>-triton -- ls -la /models
```

### Workers Not Processing Tasks

Check Celery worker logs:
```bash
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=worker --tail=100
```

Verify Redis connection:
```bash
kubectl exec -n sentineltranslate deployment/<release>-worker -- env | grep REDIS
```

### Ingress Not Working

Check ALB controller logs:
```bash
kubectl logs -n kube-system deployment/aws-load-balancer-controller
```

Verify ingress status:
```bash
kubectl describe ingress -n sentineltranslate
```

### IRSA Issues

Verify service account annotations:
```bash
kubectl describe sa -n sentineltranslate sentineltranslate-api
kubectl describe sa -n sentineltranslate sentineltranslate-worker
```

Check pod environment variables:
```bash
kubectl exec -n sentineltranslate deployment/<release>-api -- env | grep AWS
```

## Monitoring

SentinelTranslate includes comprehensive Prometheus and Grafana monitoring for production observability.

### Quick Start - Enable Monitoring

Install with production monitoring stack:

```bash
# Development (minimal resources)
make monitoring-install-dev

# Production (full monitoring stack)
GRAFANA_PASSWORD='your-secure-password' make monitoring-install-prod
```

Or manually with Helm:

```bash
helm install sentineltranslate . \
  --namespace sentineltranslate \
  --create-namespace \
  --values values.yaml \
  --values values-monitoring.yaml \
  --set kube-prometheus-stack.grafana.adminPassword='your-secure-password'
```

### Monitoring Stack Components

- **Prometheus**: Time-series metrics database (30-day retention)
- **Grafana**: Dashboards and visualization
- **Alertmanager**: Alert routing and notifications
- **ServiceMonitors**: Automatic Prometheus scraping
- **PrometheusRules**: Pre-configured alerts

### Metrics Collected

| Component | Port | Metrics |
|-----------|------|---------|
| Triton | 8002 | GPU utilization, memory, inference latency, throughput |
| Sidecar API | 8080 | Request rate, latency, errors, status codes |
| Batch API | 8090 | Request rate, latency, errors, job processing |
| Celery Workers | 9808 | Task success/failure, queue depth, processing time |
| Redis | 9121 | Memory usage, connections, commands, keys |
| Kubernetes | - | Pod health, CPU/memory, node metrics |

### Accessing Monitoring Tools

**Grafana** (Recommended):
```bash
# Get admin password
make grafana-password

# Port-forward to localhost:3000
make port-forward-grafana

# Open http://localhost:3000
# Username: admin
# Password: (from command above)
```

**Prometheus**:
```bash
# Port-forward to localhost:9090
make port-forward-prometheus

# Open http://localhost:9090
```

### Pre-configured Dashboards

1. **SentinelTranslate - Overview**: High-level health, request rates, GPU usage, queue depth
2. **Triton GPU**: GPU metrics, inference performance, model status
3. **API**: Request/response metrics, endpoint breakdown, error tracking
4. **Worker**: Task metrics, queue depth, processing times
5. **Infrastructure**: Node and pod resource usage

### Pre-configured Alerts

**Critical Alerts** (severity: critical):
- SidecarAPIDown: No API pods responding
- TritonServerDown: No Triton pods responding
- WorkerNoActiveWorkers: All workers down
- ContainerOOMKilled: Pod killed due to out of memory
- SidecarCriticalErrorRate: Error rate > 20%

**Warning Alerts** (severity: warning):
- SidecarHighErrorRate: Error rate > 5%
- SidecarHighLatency: p95 latency > 2s
- TritonHighGPUUtilization: GPU > 90%
- WorkerHighQueueDepth: Queue > 1000 tasks
- RedisHighMemoryUsage: Memory > 80%

See [MONITORING.md](./MONITORING.md) for complete documentation.

### Useful Makefile Commands

```bash
make monitoring-status           # Check monitoring stack status
make monitoring-dashboards       # List Grafana dashboards
make check-metrics              # Verify metrics endpoints
make prometheus-targets         # View Prometheus scrape targets
make alerts-firing              # Show currently firing alerts
```

### Configuration Examples

**Development** (minimal resources, no persistence):
```yaml
monitoring:
  enabled: true

kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      retention: 7d
      resources:
        requests:
          memory: 1Gi
  grafana:
    persistence:
      enabled: false
  alertmanager:
    enabled: false
```

**Production** (full monitoring, persistent storage):
```yaml
monitoring:
  enabled: true

kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      retention: 30d
      storageSpec:
        volumeClaimTemplate:
          spec:
            resources:
              requests:
                storage: 60Gi
  grafana:
    persistence:
      enabled: true
      size: 10Gi
    ingress:
      enabled: true
      hosts:
        - grafana.your-domain.com
```

### Alert Notifications

Configure Alertmanager to send notifications via Slack, PagerDuty, email, or other channels.

Edit `values-monitoring.yaml`:

```yaml
kube-prometheus-stack:
  alertmanager:
    config:
      global:
        slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK'

      receivers:
        - name: 'slack-critical'
          slack_configs:
            - channel: '#alerts-critical'
              title: 'SentinelTranslate Critical Alert'
              text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
```

### Troubleshooting Monitoring

**Targets not being scraped**:
```bash
# Check ServiceMonitor labels match Prometheus selector
kubectl get servicemonitors -n sentineltranslate -o yaml | grep -A2 labels

# Ensure 'release: prometheus' label is present
```

**Dashboard shows "No Data"**:
```bash
# Verify Prometheus is scraping
make port-forward-prometheus
# Visit http://localhost:9090/targets

# Test metrics query
# http://localhost:9090 → Execute: http_requests_total
```

**Workers metrics not appearing**:
```bash
# Check celery-exporter sidecar is running
kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=worker
kubectl logs <worker-pod> -c celery-exporter
```

For complete monitoring documentation, see [MONITORING.md](./MONITORING.md).

### Logging

Forward logs to CloudWatch or your logging solution:

```bash
# Install Fluent Bit for CloudWatch
helm repo add fluent https://fluent.github.io/helm-charts
helm install fluent-bit fluent/fluent-bit \
  --namespace logging \
  --create-namespace \
  --set backend.type=cloudwatch \
  --set backend.cloudwatch.region=us-east-1 \
  --set backend.cloudwatch.log_group_name=/aws/eks/sentineltranslate
```

## Performance Tuning

### Worker Scaling

For high throughput, increase worker replicas and concurrency:

```yaml
worker:
  replicaCount: 10
  celery:
    concurrency: 8  # Adjust based on CPU cores
```

### Triton Scaling

For multiple language pairs, consider multiple Triton instances:

```yaml
triton:
  replicaCount: 3  # Load balanced across instances
```

### Redis Optimization

For production workloads, consider Redis Cluster or Sentinel:

```yaml
redis:
  architecture: replication  # or sentinel
  replica:
    replicaCount: 3
```

## Security Best Practices

1. **Use IRSA** for AWS credentials (never use access keys)
2. **Enable TLS** on ingress with ACM certificates
3. **Network Policies** to restrict traffic between pods
4. **Pod Security Context** with non-root users
5. **Secrets Management** using AWS Secrets Manager or Sealed Secrets
6. **Image Scanning** for vulnerabilities before deployment

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/SentinelTranslate/issues
- Documentation: https://github.com/yourusername/SentinelTranslate

## License

MIT License - see LICENSE file for details
