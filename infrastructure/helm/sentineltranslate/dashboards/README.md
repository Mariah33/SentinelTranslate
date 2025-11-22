# Grafana Dashboards for SentinelTranslate

This directory contains Grafana dashboard JSON files that are automatically loaded into Grafana when monitoring is enabled.

## Available Dashboards

1. **overview.json** - High-level overview of all components
   - Request rates, error rates, latency metrics
   - GPU utilization, queue depth
   - Pod health status

2. **triton-gpu.json** - Triton Inference Server and GPU metrics
   - GPU utilization, memory usage, temperature
   - Inference latency, throughput
   - Model status and performance

3. **api.json** - API endpoint metrics (Sidecar + Batch)
   - Request rates by endpoint
   - Response time percentiles
   - Error rates and status codes

4. **worker.json** - Celery worker metrics
   - Task success/failure rates
   - Queue depth and processing times
   - Worker pool utilization

5. **infrastructure.json** - Kubernetes infrastructure metrics
   - Node CPU/memory usage
   - Pod resource consumption
   - Container restarts and failures

## Dashboard Variables

All dashboards support the following template variables:

- `$namespace` - Kubernetes namespace filter
- `$pod` - Pod name filter (where applicable)
- `$interval` - Scrape interval for time-series data

## Customization

These dashboards can be customized through the Grafana UI. Changes made in the UI will be persisted to Grafana's database (not these JSON files).

To export modified dashboards:
1. Open the dashboard in Grafana
2. Click Settings (gear icon)
3. Click "JSON Model"
4. Copy the JSON and save to this directory

## Auto-Loading

Dashboards in this directory are automatically loaded via ConfigMap when the chart is deployed. See `templates/grafana-dashboards-configmap.yaml` for the ConfigMap definition.

## Metrics Reference

### Triton Metrics
- `nv_gpu_utilization` - GPU utilization percentage
- `nv_gpu_memory_used_bytes` - GPU memory used
- `nv_inference_request_duration_us` - Inference request duration
- `nv_inference_request_success` - Successful inference requests
- `nv_model_ready_state` - Model ready status

### FastAPI Metrics (Sidecar & Batch API)
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request duration histogram
- `http_requests_in_progress` - Active requests

### Celery Metrics (Worker)
- `celery_task_total` - Total tasks executed
- `celery_task_failed_total` - Failed tasks
- `celery_task_duration_seconds` - Task duration histogram
- `celery_queue_length` - Queue depth
- `celery_workers_active` - Active workers

### Redis Metrics
- `redis_up` - Redis availability
- `redis_memory_used_bytes` - Memory usage
- `redis_connected_clients` - Connected clients
- `redis_commands_processed_total` - Total commands

### Kubernetes Metrics
- `kube_pod_status_phase` - Pod phase (Running, Pending, etc.)
- `kube_pod_container_status_restarts_total` - Container restarts
- `container_cpu_usage_seconds_total` - CPU usage
- `container_memory_working_set_bytes` - Memory usage
