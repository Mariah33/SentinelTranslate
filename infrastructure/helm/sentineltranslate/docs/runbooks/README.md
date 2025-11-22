# Alert Runbooks

This directory contains runbooks for responding to alerts from the SentinelTranslate monitoring system.

## Critical Alerts

- [Sidecar API Down](./sidecar-down.md) - No sidecar API pods responding
- [Triton Server Down](./triton-down.md) - Triton Inference Server unavailable
- [Worker Down](./worker-down.md) - No active Celery workers
- [Redis Down](./redis-down.md) - Redis instance not responding
- [Container OOM](./container-oom.md) - Container killed due to out of memory

## Warning Alerts

- [High Error Rate](./high-error-rate.md) - API error rate above threshold
- [High Latency](./high-latency.md) - Request latency above threshold
- [High GPU Utilization](./triton-high-gpu.md) - GPU utilization above 90%
- [High Queue Depth](./worker-high-queue.md) - Celery queue depth above threshold
- [High Memory Usage](./redis-high-memory.md) - Redis memory usage above 80%

## Runbook Template

Each runbook should include:

1. **Alert Description**: What the alert means
2. **Impact**: What users will experience
3. **Severity**: Critical, Warning, Info
4. **Diagnosis**: How to investigate the issue
5. **Resolution**: Step-by-step fix procedures
6. **Prevention**: How to prevent recurrence
7. **Escalation**: When and who to escalate to

## Quick Reference

### Access Monitoring Tools

```bash
# Grafana (dashboards)
make port-forward-grafana
# http://localhost:3000

# Prometheus (metrics)
make port-forward-prometheus
# http://localhost:9090

# Get Grafana password
make grafana-password
```

### Check Component Status

```bash
# All pods
kubectl get pods -n sentineltranslate

# Specific component
kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=sidecar
kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=triton
kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=worker

# View logs
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=sidecar --tail=100
```

### Common Commands

```bash
# Restart deployment
kubectl rollout restart deployment/sentineltranslate-sidecar -n sentineltranslate

# Scale replicas
kubectl scale deployment/sentineltranslate-worker --replicas=10 -n sentineltranslate

# Describe pod (for events)
kubectl describe pod <pod-name> -n sentineltranslate

# Check resource usage
kubectl top pods -n sentineltranslate
kubectl top nodes
```

## On-Call Contacts

- **Primary**: #sentineltranslate-oncall (Slack)
- **Escalation**: ml-ops-team@example.com
- **PagerDuty**: SentinelTranslate service
