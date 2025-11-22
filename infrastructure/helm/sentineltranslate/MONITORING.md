# SentinelTranslate Monitoring Guide

This guide covers the comprehensive Prometheus and Grafana monitoring setup for SentinelTranslate on Kubernetes.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Accessing Monitoring Tools](#accessing-monitoring-tools)
- [Dashboards](#dashboards)
- [Alerts](#alerts)
- [Metrics Reference](#metrics-reference)
- [Troubleshooting](#troubleshooting)

## Overview

SentinelTranslate includes a complete monitoring stack built on:

- **Prometheus**: Time-series metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Alertmanager**: Alert routing and notification
- **ServiceMonitors**: Automatic service discovery for Prometheus
- **PrometheusRules**: Pre-configured alerting rules

### Components Monitored

1. **Triton Inference Server**: GPU metrics, inference performance
2. **Sidecar API**: Request rates, latency, errors
3. **Batch API**: Job submission, processing metrics
4. **Celery Workers**: Task processing, queue depth, failures
5. **Redis**: Memory usage, connections, command stats
6. **Kubernetes**: Pod health, resource usage, node metrics

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Grafana Dashboards                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Overview │ │   GPU    │ │   API    │ │  Worker  │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────┬───────────────────────────────────┘
                          │ PromQL
┌─────────────────────────▼───────────────────────────────────┐
│                     Prometheus TSDB                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Retention: 30d | Storage: 60Gi PVC                │    │
│  └────────────────────────────────────────────────────┘    │
└──────┬───────┬───────┬───────┬────────┬────────┬───────────┘
       │       │       │       │        │        │
       │       │       │       │        │        │
   ┌───▼──┐ ┌─▼───┐ ┌─▼───┐ ┌─▼────┐ ┌▼─────┐ ┌▼─────┐
   │Triton│ │Side-│ │Batch│ │Worker│ │Redis │ │ K8s  │
   │:8002 │ │car  │ │ API │ │:9808 │ │:9121 │ │Metrics│
   │      │ │:8080│ │:8090│ │      │ │      │ │      │
   └──────┘ └─────┘ └─────┘ └──────┘ └──────┘ └──────┘
```

### Metrics Flow

1. **Service Endpoints**: Each component exposes metrics on `/metrics`
2. **ServiceMonitors**: Kubernetes CRDs define scrape targets
3. **Prometheus**: Scrapes metrics every 30s (configurable)
4. **Grafana**: Queries Prometheus for visualization
5. **Alertmanager**: Receives and routes alerts from Prometheus

## Installation

### Prerequisites

- Kubernetes cluster (1.28+)
- Helm 3.x
- kubectl configured
- Storage class supporting dynamic provisioning (e.g., `gp3` on AWS EKS)

### Quick Start (Development)

Install with minimal resources for development:

```bash
# Update Helm dependencies
helm dependency update

# Install with development monitoring
helm install sentineltranslate . \
  -f values.yaml \
  -f values-monitoring-dev.yaml \
  --namespace sentineltranslate \
  --create-namespace
```

This installs:
- Prometheus with 7-day retention, 1Gi memory
- Grafana with no persistence (ephemeral)
- No Alertmanager
- 60s scrape interval

### Production Installation

Install with full monitoring stack:

```bash
# Update dependencies
helm dependency update

# Install with production monitoring
helm install sentineltranslate . \
  -f values.yaml \
  -f values-monitoring.yaml \
  --namespace sentineltranslate \
  --create-namespace \
  --set kube-prometheus-stack.grafana.adminPassword='YOUR-SECURE-PASSWORD'
```

This installs:
- Prometheus with 30-day retention, 4Gi memory, 60Gi PVC
- Grafana with 10Gi PVC persistence
- Alertmanager with 10Gi PVC
- 30s scrape interval
- Full alerting rules

### Verify Installation

```bash
# Check all pods are running
kubectl get pods -n sentineltranslate

# Expected output includes:
# - sentineltranslate-kube-prometheus-stack-prometheus-*
# - sentineltranslate-kube-prometheus-stack-operator-*
# - sentineltranslate-kube-prometheus-stack-grafana-*
# - prometheus-sentineltranslate-kube-state-metrics-*
# - sentineltranslate-kube-prometheus-stack-prometheus-node-exporter-*

# Check ServiceMonitors are created
kubectl get servicemonitors -n sentineltranslate

# Check PrometheusRules are created
kubectl get prometheusrules -n sentineltranslate
```

## Configuration

### Enable Monitoring

Set `monitoring.enabled=true` in your values file:

```yaml
monitoring:
  enabled: true

  serviceMonitor:
    enabled: true
    interval: 30s
    scrapeTimeout: 10s
```

### Configure Retention

Adjust Prometheus retention in `values-monitoring.yaml`:

```yaml
kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      retention: 30d          # How long to keep data
      retentionSize: "50GB"   # Max storage size

      storageSpec:
        volumeClaimTemplate:
          spec:
            resources:
              requests:
                storage: 60Gi  # PVC size (should be > retentionSize)
```

### Configure Scrape Interval

Trade-off between granularity and resource usage:

```yaml
kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      scrapeInterval: 30s      # Recommended for production
      # scrapeInterval: 60s    # Use for cost optimization
      # scrapeInterval: 15s    # Use for high-resolution monitoring
```

### Enable Redis Metrics

Redis metrics are collected via Bitnami Redis exporter:

```yaml
redis:
  metrics:
    enabled: true
    serviceMonitor:
      enabled: true
      labels:
        release: prometheus
```

### Configure Alertmanager

Edit alerting routes and receivers in `values-monitoring.yaml`:

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
```

## Accessing Monitoring Tools

### Grafana

#### Port-Forward (Development)

```bash
# Forward Grafana to localhost:3000
kubectl port-forward -n sentineltranslate \
  svc/sentineltranslate-kube-prometheus-stack-grafana 3000:80

# Access at: http://localhost:3000
# Username: admin
# Password: (see below)
```

Get Grafana password:

```bash
kubectl get secret -n sentineltranslate \
  sentineltranslate-kube-prometheus-stack-grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
```

#### Ingress (Production)

Enable Grafana ingress in `values-monitoring.yaml`:

```yaml
kube-prometheus-stack:
  grafana:
    ingress:
      enabled: true
      ingressClassName: alb
      annotations:
        alb.ingress.kubernetes.io/certificate-arn: "arn:aws:acm:..."
      hosts:
        - grafana.your-domain.com
```

Then access at: `https://grafana.your-domain.com`

### Prometheus

#### Port-Forward

```bash
# Forward Prometheus to localhost:9090
kubectl port-forward -n sentineltranslate \
  svc/sentineltranslate-kube-prometheus-stack-prometheus 9090:9090

# Access at: http://localhost:9090
```

#### Query Examples

```promql
# Request rate for sidecar API
sum(rate(http_requests_total{job=~".*sidecar"}[5m]))

# Error rate
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m]))

# GPU utilization
avg(nv_gpu_utilization)

# Celery queue depth
sum(celery_queue_length)
```

### Alertmanager

#### Port-Forward

```bash
# Forward Alertmanager to localhost:9093
kubectl port-forward -n sentineltranslate \
  svc/sentineltranslate-kube-prometheus-stack-alertmanager 9093:9093

# Access at: http://localhost:9093
```

## Dashboards

### Pre-configured Dashboards

1. **SentinelTranslate - Overview**
   - High-level health metrics
   - Request rates, error rates, latency
   - GPU utilization, queue depth
   - Pod status across all components

2. **Triton GPU Dashboard** (coming soon)
   - GPU utilization, memory, temperature
   - Inference latency and throughput
   - Model status and load

3. **API Dashboard** (coming soon)
   - Request/response metrics by endpoint
   - Response time percentiles (p50, p95, p99)
   - Status code distribution

4. **Worker Dashboard** (coming soon)
   - Task success/failure rates
   - Queue depth over time
   - Task processing duration
   - Worker pool utilization

5. **Infrastructure Dashboard** (coming soon)
   - Node CPU and memory usage
   - Pod resource consumption
   - Container restarts
   - Storage usage

### Customizing Dashboards

1. Open Grafana UI
2. Navigate to the dashboard you want to modify
3. Click the gear icon (Settings) → "Make editable"
4. Edit panels, add queries, change visualizations
5. Click "Save" to persist changes

Note: Dashboard modifications are saved to Grafana's database, not the Helm chart.

### Importing New Dashboards

```bash
# Option 1: Via Grafana UI
# Dashboard → Import → Enter Grafana.com dashboard ID

# Option 2: Via JSON
# Dashboard → Import → Upload JSON file

# Popular community dashboards:
# - NVIDIA GPU: 12239
# - Redis: 11692
# - Celery: 11798
```

## Alerts

### Pre-configured Alert Rules

#### API Alerts

- **SidecarHighErrorRate**: Error rate > 5% for 5 minutes
- **SidecarCriticalErrorRate**: Error rate > 20% for 2 minutes
- **SidecarHighLatency**: p95 latency > 2s for 5 minutes
- **SidecarAPIDown**: No sidecar pods responding

#### GPU/Triton Alerts

- **TritonHighGPUUtilization**: GPU utilization > 90% for 10 minutes
- **TritonHighGPUMemory**: GPU memory > 85% for 10 minutes
- **TritonHighInferenceLatency**: Average latency > 500ms for 5 minutes
- **TritonInferenceFailures**: Inference failures detected
- **TritonServerDown**: No Triton pods responding
- **TritonModelNotReady**: Model not in ready state for 5 minutes

#### Worker Alerts

- **WorkerHighTaskFailureRate**: Task failure rate > 5% for 5 minutes
- **WorkerHighQueueDepth**: Queue > 1000 tasks for 10 minutes
- **WorkerCriticalQueueDepth**: Queue > 5000 tasks for 5 minutes
- **WorkerNoActiveWorkers**: All workers down
- **WorkerSlowTaskProcessing**: p95 task duration > 60s for 10 minutes

#### Redis Alerts

- **RedisHighMemoryUsage**: Memory usage > 80% for 10 minutes
- **RedisDown**: Redis instance not responding
- **RedisTooManyConnections**: > 1000 connected clients

#### Kubernetes Alerts

- **PodCrashLooping**: Pod restarting repeatedly
- **PodNotReady**: Pod not ready for 10 minutes
- **ContainerOOMKilled**: Container killed due to OOM
- **PodHighCPUUsage**: CPU usage > 90% for 10 minutes
- **PodHighMemoryUsage**: Memory usage > 1.5Gi for 10 minutes

### Alert Severity Levels

- **critical**: Immediate action required (pages on-call)
- **warning**: Attention needed soon (Slack notification)

### Customizing Alerts

Edit `templates/prometheusrule.yaml` or create custom rules:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: custom-alerts
  labels:
    release: prometheus
spec:
  groups:
    - name: custom
      rules:
        - alert: CustomAlert
          expr: your_metric > threshold
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Custom alert fired"
            description: "{{ $value }}"
```

## Metrics Reference

### Triton Metrics

Exposed on port 8002 `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `nv_gpu_utilization` | Gauge | GPU utilization percentage (0-100) |
| `nv_gpu_memory_used_bytes` | Gauge | GPU memory used in bytes |
| `nv_gpu_memory_total_bytes` | Gauge | Total GPU memory in bytes |
| `nv_inference_request_success` | Counter | Successful inference requests |
| `nv_inference_request_failure` | Counter | Failed inference requests |
| `nv_inference_request_duration_us` | Histogram | Inference duration in microseconds |
| `nv_inference_queue_duration_us` | Histogram | Time spent in queue in microseconds |
| `nv_model_ready_state` | Gauge | Model ready state (1=ready, 0=not ready) |

### FastAPI Metrics (Sidecar & Batch API)

Exposed on ports 8080/8090 `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests by method, status |
| `http_request_duration_seconds` | Histogram | Request duration in seconds |
| `http_requests_in_progress` | Gauge | Currently active requests |

### Celery Metrics (Worker)

Exposed on port 9808 `/metrics` (via celery-exporter sidecar):

| Metric | Type | Description |
|--------|------|-------------|
| `celery_task_total` | Counter | Total tasks by name, state |
| `celery_task_failed_total` | Counter | Failed tasks by name |
| `celery_task_duration_seconds` | Histogram | Task execution duration |
| `celery_queue_length` | Gauge | Number of tasks in queue |
| `celery_workers_active` | Gauge | Number of active workers |
| `celery_workers_total` | Gauge | Total number of workers |

### Redis Metrics

Exposed on port 9121 `/metrics` (via Bitnami exporter):

| Metric | Type | Description |
|--------|------|-------------|
| `redis_up` | Gauge | Redis instance availability (1=up, 0=down) |
| `redis_memory_used_bytes` | Gauge | Memory used by Redis |
| `redis_memory_max_bytes` | Gauge | Max memory limit |
| `redis_connected_clients` | Gauge | Number of connected clients |
| `redis_commands_processed_total` | Counter | Total commands processed |
| `redis_keyspace_keys` | Gauge | Number of keys by database |

### Kubernetes Metrics

Collected by kube-state-metrics and node-exporter:

| Metric | Type | Description |
|--------|------|-------------|
| `kube_pod_status_phase` | Gauge | Pod phase (Running, Pending, etc.) |
| `kube_pod_container_status_restarts_total` | Counter | Container restart count |
| `container_cpu_usage_seconds_total` | Counter | CPU usage in seconds |
| `container_memory_working_set_bytes` | Gauge | Memory working set in bytes |
| `node_cpu_seconds_total` | Counter | Node CPU usage |
| `node_memory_MemAvailable_bytes` | Gauge | Available memory on node |

## Troubleshooting

### Prometheus Not Scraping Targets

**Symptom**: Targets show as "down" in Prometheus UI

**Check**:
1. Verify ServiceMonitor labels match Prometheus selector:
   ```bash
   kubectl get servicemonitors -n sentineltranslate -o yaml | grep -A2 labels
   ```

2. Ensure `release: prometheus` label is present

3. Check Prometheus logs:
   ```bash
   kubectl logs -n sentineltranslate -l app.kubernetes.io/name=prometheus
   ```

**Fix**: Update ServiceMonitor labels in `values-monitoring.yaml`:
```yaml
monitoring:
  serviceMonitor:
    labels:
      release: prometheus
```

### Grafana Dashboard Shows "No Data"

**Symptom**: Panels in Grafana show "No data"

**Check**:
1. Verify Prometheus is scraping metrics:
   ```bash
   # Port-forward Prometheus
   kubectl port-forward -n sentineltranslate svc/sentineltranslate-kube-prometheus-stack-prometheus 9090:9090

   # Open http://localhost:9090/targets
   # Verify targets are UP
   ```

2. Test metric query in Prometheus UI:
   ```promql
   http_requests_total
   ```

3. Check Grafana data source configuration:
   - Settings → Data Sources → Prometheus
   - Test connection

**Fix**: Ensure correct Prometheus URL in Grafana:
```
http://sentineltranslate-kube-prometheus-stack-prometheus:9090
```

### Alerts Not Firing

**Symptom**: Expected alerts not appearing in Alertmanager

**Check**:
1. Verify PrometheusRule is loaded:
   ```bash
   kubectl get prometheusrules -n sentineltranslate
   ```

2. Check Prometheus rule evaluation:
   ```bash
   # Port-forward and visit http://localhost:9090/rules
   ```

3. Verify alert expression in Prometheus:
   ```promql
   # Test the alert query directly
   ```

**Fix**: Ensure PrometheusRule has correct labels:
```yaml
labels:
  release: prometheus
```

### High Cardinality Issues

**Symptom**: Prometheus using excessive memory/storage

**Check**:
```bash
# Check metric cardinality
kubectl port-forward -n sentineltranslate svc/sentineltranslate-kube-prometheus-stack-prometheus 9090:9090

# Visit http://localhost:9090/tsdb-status
```

**Fix**:
1. Reduce scrape interval: `60s` instead of `30s`
2. Add metric relabeling to drop high-cardinality labels
3. Increase Prometheus memory limits

### Worker Metrics Not Appearing

**Symptom**: Celery metrics not available in Prometheus

**Check**:
1. Verify celery-exporter sidecar is running:
   ```bash
   kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=worker
   kubectl logs -n sentineltranslate <worker-pod> -c celery-exporter
   ```

2. Test metrics endpoint:
   ```bash
   kubectl port-forward -n sentineltranslate <worker-pod> 9808:9808
   curl http://localhost:9808/metrics
   ```

**Fix**: Ensure monitoring is enabled in values:
```yaml
monitoring:
  enabled: true
  metrics:
    worker:
      enabled: true
```

### Grafana Persistence Issues

**Symptom**: Dashboards or settings lost after pod restart

**Check**:
```bash
# Check PVC is bound
kubectl get pvc -n sentineltranslate | grep grafana
```

**Fix**: Enable persistence in values:
```yaml
kube-prometheus-stack:
  grafana:
    persistence:
      enabled: true
      storageClassName: gp3
      size: 10Gi
```

## Cost Optimization

### Reduce Storage Costs

```yaml
kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      retention: 15d              # Reduce from 30d
      retentionSize: "20GB"       # Reduce from 50GB
      storageSpec:
        volumeClaimTemplate:
          spec:
            resources:
              requests:
                storage: 25Gi     # Reduce from 60Gi
```

### Reduce Compute Costs

```yaml
kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      scrapeInterval: 60s         # Increase from 30s
      resources:
        requests:
          memory: 2Gi             # Reduce from 4Gi
          cpu: 500m               # Reduce from 1000m
```

### Disable Components

```yaml
kube-prometheus-stack:
  alertmanager:
    enabled: false                # Disable if not using alerts

  nodeExporter:
    enabled: false                # Disable if not monitoring nodes
```

## Best Practices

1. **Set Resource Limits**: Always set requests/limits for Prometheus and Grafana
2. **Enable Persistence**: Use PVCs for production to prevent data loss
3. **Configure Retention**: Balance between data history and storage costs
4. **Use Recording Rules**: Pre-compute expensive queries
5. **Set Up Alerts**: Configure actionable alerts with clear runbooks
6. **Regular Backups**: Export Grafana dashboards and Prometheus config
7. **Monitor the Monitors**: Set up alerts for Prometheus/Grafana failures
8. **Use Labels Wisely**: Avoid high-cardinality labels (e.g., UUIDs)

## Support

For issues or questions:
- GitHub Issues: https://github.com/yourusername/SentinelTranslate/issues
- Runbooks: `/docs/runbooks/`
- Slack: #sentineltranslate-ops
