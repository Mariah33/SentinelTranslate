# Runbook: Worker High Queue Depth

**Alert Name**: `WorkerHighQueueDepth` (Warning) / `WorkerCriticalQueueDepth` (Critical)
**Severity**: Warning (>1000 tasks) / Critical (>5000 tasks)
**Auto-resolve**: Yes (when queue drains below threshold)

## Description

The Celery task queue has accumulated a large number of pending translation tasks. Workers are not processing tasks fast enough to keep up with incoming requests.

## Impact

**Warning Level (>1000 tasks)**:
- Increased translation latency (users wait longer for results)
- Some users may timeout waiting for translations
- System is under heavy load but functional

**Critical Level (>5000 tasks)**:
- Severe translation delays (minutes to hours)
- High probability of request timeouts
- Risk of Redis memory exhaustion
- Risk of data loss if Redis restarts

## Diagnosis

### 1. Check Current Queue Depth

```bash
# Via Prometheus
make port-forward-prometheus
# Visit http://localhost:9090
# Query: sum(celery_queue_length)

# Via Redis CLI
kubectl exec -it -n sentineltranslate sentineltranslate-redis-master-0 -- redis-cli
> LLEN celery  # Check queue length
> EXIT
```

### 2. Check Worker Status

```bash
# How many workers are running?
kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=worker

# Are workers processing tasks?
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=worker --tail=50 | grep "Task.*succeeded"

# Check worker resource usage
kubectl top pods -n sentineltranslate -l app.kubernetes.io/component=worker
```

### 3. Identify Bottleneck

```bash
# Check if Triton is the bottleneck
kubectl top pods -n sentineltranslate -l app.kubernetes.io/component=triton
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=triton --tail=50

# Check GPU utilization in Grafana
# Dashboard: SentinelTranslate - Triton GPU
# Metric: nv_gpu_utilization

# Check worker CPU/memory limits
kubectl describe pod -n sentineltranslate -l app.kubernetes.io/component=worker | grep -A 5 "Limits:"
```

### 4. Check for Failed Tasks

```bash
# View recent task failures
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=worker --tail=200 | grep -i "error\|failed\|exception"

# Check Celery exporter metrics
kubectl port-forward -n sentineltranslate <worker-pod> 9808:9808 &
curl http://localhost:9808/metrics | grep celery_task_failed
```

### 5. Check Incoming Request Rate

```bash
# Via Prometheus
# Query: sum(rate(http_requests_total{job=~".*sidecar"}[5m]))

# Is there unusual traffic spike?
# Compare with historical baseline in Grafana
```

## Resolution

### Immediate Actions (While Investigating)

#### 1. Scale Up Workers (Quick Win)

```bash
# Check current replica count
kubectl get deployment sentineltranslate-worker -n sentineltranslate

# Scale up to handle load
kubectl scale deployment sentineltranslate-worker --replicas=20 -n sentineltranslate

# Monitor queue depth
watch "kubectl exec -it -n sentineltranslate sentineltranslate-redis-master-0 -- redis-cli LLEN celery"
```

#### 2. Increase Worker Concurrency

```bash
# Edit worker environment to increase concurrency
kubectl set env deployment/sentineltranslate-worker -n sentineltranslate CELERY_CONCURRENCY=8

# This increases tasks processed per worker
# Monitor CPU usage after change
```

### Root Cause-Based Resolutions

#### Scenario 1: Triton GPU Bottleneck (GPU at 100%)

```bash
# Option A: Scale up Triton (if you have more GPUs)
kubectl scale deployment sentineltranslate-triton --replicas=2 -n sentineltranslate

# Option B: Add more GPU nodes to cluster
# (Requires infrastructure change - escalate)

# Option C: Reduce worker concurrency to avoid overwhelming Triton
kubectl set env deployment/sentineltranslate-worker -n sentineltranslate CELERY_CONCURRENCY=2
```

#### Scenario 2: Workers CPU/Memory Constrained

```bash
# Check if workers are hitting resource limits
kubectl top pods -n sentineltranslate -l app.kubernetes.io/component=worker

# If CPU/memory is maxed, increase limits temporarily
kubectl patch deployment sentineltranslate-worker -n sentineltranslate -p '
{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "worker",
          "resources": {
            "limits": {
              "cpu": "4000m",
              "memory": "4Gi"
            }
          }
        }]
      }
    }
  }
}'

# Note: Make permanent by updating values.yaml
```

#### Scenario 3: Slow Tasks (Large Texts, Complex Translations)

```bash
# Check task duration metrics
# Prometheus query: histogram_quantile(0.95, sum(rate(celery_task_duration_seconds_bucket[5m])) by (le))

# View logs for slow tasks
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=worker | grep "Task.*took"

# If tasks are legitimately slow:
# - Scale up workers
# - Consider implementing task timeout
# - Optimize translation logic
```

#### Scenario 4: Batch Job Flood

```bash
# Check if large batch job is causing the spike
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=api --tail=100 | grep "batch"

# If a single large batch is the issue:
# Option A: Wait it out (queue will drain)
# Option B: Rate limit batch submissions (requires code change)
# Option C: Temporarily scale workers aggressively
```

#### Scenario 5: Redis Connection Issues

```bash
# Check Redis health
kubectl logs -n sentineltranslate -l app.kubernetes.io/name=redis --tail=50

# Check Redis memory
kubectl exec -it -n sentineltranslate sentineltranslate-redis-master-0 -- redis-cli INFO memory

# If Redis is struggling, restart (CAREFUL!)
kubectl rollout restart statefulset/sentineltranslate-redis-master -n sentineltranslate
```

### Emergency Actions (Critical Level Only)

If queue depth is critical (>5000) and not draining:

```bash
# 1. Maximum scale-out (use with caution - check cluster capacity)
kubectl scale deployment sentineltranslate-worker --replicas=50 -n sentineltranslate

# 2. Pause new job submissions temporarily
# Edit sidecar/api to return 503 Service Unavailable
# (Requires deployment update)

# 3. If necessary, purge oldest tasks (LAST RESORT)
kubectl exec -it -n sentineltranslate sentineltranslate-redis-master-0 -- redis-cli
> LTRIM celery 0 999  # Keep only 1000 most recent tasks
> EXIT
# WARNING: This loses user data! Only do this if approved.
```

## Verification

After resolution, verify:

```bash
# 1. Queue depth is decreasing
watch "kubectl exec -it -n sentineltranslate sentineltranslate-redis-master-0 -- redis-cli LLEN celery"

# 2. Workers are processing tasks
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=worker --tail=20 -f

# 3. Task success rate is normal
# Grafana → Worker Dashboard → Task Success Rate

# 4. Translation latency is back to normal
# Grafana → API Dashboard → p95 Latency

# 5. Alert resolves
# Prometheus → Alerts → WorkerHighQueueDepth should disappear
```

## Prevention

### 1. Enable Worker Autoscaling

```yaml
worker:
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 50
    targetCPUUtilizationPercentage: 70
```

For queue-based autoscaling (requires custom metrics):

```yaml
worker:
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 50
    customMetrics:
      - type: External
        external:
          metric:
            name: celery_queue_length
          target:
            type: AverageValue
            averageValue: "100"  # Scale up if >100 tasks per worker
```

### 2. Set Task Timeouts

Add timeout to prevent hanging tasks:

```python
# In worker/tasks.py
@celery_app.task(name="tasks.translate", time_limit=300, soft_time_limit=240)
def translate(job_id, text, source_lang, target_lang):
    # Task will be killed after 300s
    # Warning sent at 240s
```

### 3. Implement Rate Limiting

```python
# In sidecar/api.py or api/app.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/translate")
@limiter.limit("100/minute")  # Max 100 requests per minute per IP
def translate(req: Req):
    ...
```

### 4. Monitor and Alert Earlier

Update alert thresholds to catch issues sooner:

```yaml
# In prometheusrule.yaml
- alert: WorkerQueueGrowing
  expr: sum(celery_queue_length) > 500
  for: 5m
  severity: info  # Early warning
```

### 5. Capacity Planning

- Monitor historical queue depth patterns
- Scale workers proactively during known high-traffic periods
- Ensure sufficient GPU capacity for peak load
- Consider multi-GPU Triton setup for better throughput

## Escalation

**Escalate if**:
- Queue depth continues growing despite scaling workers
- Workers are failing to process tasks (high error rate)
- Root cause is unclear or infrastructure-related
- Redis is running out of memory
- Cluster cannot accommodate more worker pods

**Escalation Path**:
1. Senior ML Engineer: @ml-ops-oncall
2. Infrastructure Team: #infrastructure-oncall
3. Incident Commander: Use PagerDuty escalation

## Related Alerts

- `WorkerHighTaskFailureRate`: Tasks failing instead of completing
- `WorkerNoActiveWorkers`: All workers down (more severe)
- `TritonHighGPUUtilization`: GPU bottleneck
- `RedisHighMemoryUsage`: Queue consuming too much memory
- `WorkerSlowTaskProcessing`: Individual tasks taking too long

## Long-term Improvements

1. **Implement Job Prioritization**: High-priority translation requests skip the queue
2. **Batch Job Throttling**: Limit concurrent batch jobs
3. **Dedicated Worker Pools**: Separate workers for single-text vs batch
4. **Triton Batching**: Enable dynamic batching in Triton for better GPU utilization
5. **Queue Monitoring Dashboard**: Real-time queue depth visualization
6. **Predictive Scaling**: ML-based autoscaling based on historical patterns

## Metrics to Track

```promql
# Queue depth
sum(celery_queue_length)

# Queue growth rate
deriv(sum(celery_queue_length)[5m])

# Task processing rate
sum(rate(celery_task_total[5m]))

# Worker count
count(kube_pod_status_phase{pod=~".*worker.*",phase="Running"})

# Average tasks per worker
sum(celery_queue_length) / count(kube_pod_status_phase{pod=~".*worker.*",phase="Running"})
```

## Post-Incident

1. Analyze queue depth timeline in Grafana
2. Identify what triggered the spike (batch job, traffic surge, etc.)
3. Calculate actual vs required capacity
4. Update autoscaling thresholds if needed
5. Document incident and update this runbook
6. Consider implementing preventive measures listed above
