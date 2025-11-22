# Runbook: Sidecar API Down

**Alert Name**: `SidecarAPIDown`
**Severity**: Critical
**Auto-resolve**: Yes (when pods become healthy)

## Description

No sidecar API pods are responding to health checks. The single-text translation endpoint is completely unavailable.

## Impact

- Users cannot submit single-text translation requests via `/translate`
- 100% of single-text translation traffic is failing
- Batch translation may still be functional (separate API)

## Diagnosis

### 1. Check Pod Status

```bash
# Check if any pods are running
kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=sidecar

# Possible states:
# - No pods exist → Deployment issue
# - Pods in CrashLoopBackOff → Application error
# - Pods in Pending → Resource/scheduling issue
# - Pods Running but not Ready → Health check failing
```

### 2. View Pod Events

```bash
# Get events for recent pod issues
kubectl describe deployment/sentineltranslate-sidecar -n sentineltranslate
kubectl get events -n sentineltranslate --sort-by='.lastTimestamp' | grep sidecar
```

### 3. Check Logs

```bash
# View recent logs
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=sidecar --tail=100

# Common error patterns:
# - "Connection refused" → Redis/Triton unavailable
# - "ModuleNotFoundError" → Missing dependency
# - "OOMKilled" → Out of memory
# - "FailedMount" → Volume mount issue
```

### 4. Check Dependencies

```bash
# Verify Redis is up
kubectl get pods -n sentineltranslate -l app.kubernetes.io/name=redis

# Verify Triton is up
kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=triton

# Test Redis connectivity
kubectl run -it --rm redis-test --image=redis:alpine --restart=Never -n sentineltranslate -- \
  redis-cli -h sentineltranslate-redis-master ping
```

### 5. Check Resource Availability

```bash
# Check node resources
kubectl top nodes

# Check if pods are pending due to resources
kubectl describe pod <pending-pod-name> -n sentineltranslate | grep -A 5 "Events:"
```

## Resolution

### Scenario 1: Pods CrashLooping (Application Error)

```bash
# Check recent deployment changes
kubectl rollout history deployment/sentineltranslate-sidecar -n sentineltranslate

# Rollback to previous version if recent deployment
kubectl rollout undo deployment/sentineltranslate-sidecar -n sentineltranslate

# Monitor rollback
kubectl rollout status deployment/sentineltranslate-sidecar -n sentineltranslate
```

### Scenario 2: Redis/Triton Unavailable

```bash
# Check Redis health
kubectl logs -n sentineltranslate -l app.kubernetes.io/name=redis --tail=50

# Restart Redis if needed (careful in production!)
kubectl rollout restart statefulset/sentineltranslate-redis-master -n sentineltranslate

# Check Triton health
kubectl logs -n sentineltranslate -l app.kubernetes.io/component=triton --tail=50

# Restart Triton if needed
kubectl rollout restart deployment/sentineltranslate-triton -n sentineltranslate
```

### Scenario 3: Resource Exhaustion

```bash
# Scale down temporarily to free resources
kubectl scale deployment/sentineltranslate-worker --replicas=1 -n sentineltranslate

# Wait for sidecar to start
kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=sidecar -n sentineltranslate --timeout=300s

# Scale workers back up
kubectl scale deployment/sentineltranslate-worker --replicas=5 -n sentineltranslate
```

### Scenario 4: Image Pull Error

```bash
# Check image pull secrets
kubectl get secrets -n sentineltranslate

# Verify ECR credentials (if using ECR)
aws ecr get-login-password --region us-east-1 | kubectl create secret docker-registry ecr-registry-secret \
  --docker-server=<account-id>.dkr.ecr.us-east-1.amazonaws.com \
  --docker-username=AWS \
  --docker-password="$(stdin)" \
  -n sentineltranslate \
  --dry-run=client -o yaml | kubectl apply -f -

# Update deployment to use secret
kubectl patch deployment sentineltranslate-sidecar -n sentineltranslate \
  -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"ecr-registry-secret"}]}}}}'
```

### Scenario 5: Pod Evicted/Scheduling Issue

```bash
# Manually delete evicted/failed pods
kubectl delete pod -n sentineltranslate -l app.kubernetes.io/component=sidecar --field-selector status.phase=Failed

# Deployment will automatically recreate them
kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=sidecar -w
```

## Verification

After resolution, verify:

```bash
# 1. All pods are Running and Ready
kubectl get pods -n sentineltranslate -l app.kubernetes.io/component=sidecar

# 2. Health check passes
kubectl port-forward -n sentineltranslate svc/sentineltranslate-sidecar 8080:8080 &
curl http://localhost:8080/health
# Expected: {"status": "ok"}

# 3. Translation request works
curl -X POST http://localhost:8080/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "Bonjour", "source_lang": "fr", "target_lang": "en"}'
# Expected: {"job_id": "<uuid>"}

# 4. Alert resolves in Prometheus
# Visit http://localhost:9090/alerts
# SidecarAPIDown should disappear within 2 minutes
```

## Prevention

### 1. Implement Pod Disruption Budget

```yaml
podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

### 2. Configure Resource Requests/Limits

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

### 3. Enable Horizontal Pod Autoscaling

```yaml
sidecar:
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
```

### 4. Set Up Health Monitoring

Ensure readiness and liveness probes are properly configured:

```yaml
sidecar:
  readinessProbe:
    httpGet:
      path: /health
      port: 8080
    initialDelaySeconds: 10
    periodSeconds: 5
  livenessProbe:
    httpGet:
      path: /health
      port: 8080
    initialDelaySeconds: 30
    periodSeconds: 10
```

### 5. Monitor Dependencies

Set up alerts for:
- Redis availability
- Triton server health
- Node resource pressure

## Escalation

**Escalate if**:
- Issue persists for > 15 minutes after attempted fixes
- Root cause is unclear
- Rollback doesn't resolve the issue
- Cluster-wide issues are suspected

**Escalation Path**:
1. Senior ML Ops Engineer: @ml-ops-oncall
2. Platform Team: platform-team@example.com
3. Incident Manager: Use PagerDuty escalation policy

## Related Alerts

- `SidecarHighErrorRate`: May precede total failure
- `RedisDown`: Redis unavailability causes sidecar failures
- `TritonServerDown`: Triton unavailability causes translation failures
- `PodCrashLooping`: Individual pod issues

## Post-Incident

After resolving:
1. Document root cause
2. Create post-mortem if downtime > 5 minutes
3. Update runbook with new learnings
4. Consider preventive measures
5. Review and improve monitoring/alerting
