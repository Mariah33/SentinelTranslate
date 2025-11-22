# Installation Guide for SentinelTranslate Helm Chart

## Quick Start

### Prerequisites Check

```bash
# Check Helm version (3.8+ required)
helm version

# Check kubectl access
kubectl cluster-info

# Check GPU nodes (for Triton)
kubectl get nodes -L node.kubernetes.io/instance-type,accelerator
```

## Step-by-Step Installation

### 1. Add Helm Dependencies

```bash
cd infrastructure/helm/sentineltranslate
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm dependency update
```

This will download the Redis chart dependency to the `charts/` directory.

### 2. Validate Chart

```bash
# Lint the chart
helm lint .

# Dry-run to check generated manifests
helm install sentineltranslate . \
  --namespace sentineltranslate \
  --dry-run \
  --debug
```

### 3. Build Docker Images

**Option A: Use ECR (Production)**

```bash
# Set variables
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REGISTRY=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
export IMAGE_TAG=v1.0.0

# Create ECR repositories (one-time)
aws ecr create-repository --repository-name sentineltranslate-sidecar --region $AWS_REGION
aws ecr create-repository --repository-name sentineltranslate-api --region $AWS_REGION
aws ecr create-repository --repository-name sentineltranslate-worker --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_REGISTRY

# Build and push images
cd sidecar
docker build -t $ECR_REGISTRY/sentineltranslate-sidecar:$IMAGE_TAG .
docker push $ECR_REGISTRY/sentineltranslate-sidecar:$IMAGE_TAG

cd ../api
docker build -t $ECR_REGISTRY/sentineltranslate-api:$IMAGE_TAG .
docker push $ECR_REGISTRY/sentineltranslate-api:$IMAGE_TAG

cd ../worker
docker build -t $ECR_REGISTRY/sentineltranslate-worker:$IMAGE_TAG .
docker push $ECR_REGISTRY/sentineltranslate-worker:$IMAGE_TAG
```

**Option B: Local Development (Minikube/Kind)**

```bash
# For Minikube - use Minikube's Docker daemon
eval $(minikube docker-env)

# Build images
cd sidecar
docker build -t sentineltranslate-sidecar:dev .

cd ../api
docker build -t sentineltranslate-api:dev .

cd ../worker
docker build -t sentineltranslate-worker:dev .
```

### 4. Configure IRSA (Production Only)

**Create IAM Policy for S3 Access:**

```bash
# Create policy document
cat > sentineltranslate-s3-policy.json <<EOF
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
EOF

# Create IAM policy
aws iam create-policy \
  --policy-name SentinelTranslateS3Access \
  --policy-document file://sentineltranslate-s3-policy.json
```

**Create IAM Roles with Trust Relationship:**

```bash
# Get OIDC provider URL
export OIDC_PROVIDER=$(aws eks describe-cluster \
  --name your-cluster-name \
  --query "cluster.identity.oidc.issuer" \
  --output text | sed -e "s/^https:\/\///")

# Create trust policy for API
cat > api-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "${OIDC_PROVIDER}:sub": "system:serviceaccount:sentineltranslate:sentineltranslate-api",
          "${OIDC_PROVIDER}:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Create IAM role for API
aws iam create-role \
  --role-name sentineltranslate-api-role \
  --assume-role-policy-document file://api-trust-policy.json

# Attach S3 policy to API role
aws iam attach-role-policy \
  --role-name sentineltranslate-api-role \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/SentinelTranslateS3Access

# Create trust policy for Worker (similar to API)
cat > worker-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "${OIDC_PROVIDER}:sub": "system:serviceaccount:sentineltranslate:sentineltranslate-worker",
          "${OIDC_PROVIDER}:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Create IAM role for Worker
aws iam create-role \
  --role-name sentineltranslate-worker-role \
  --assume-role-policy-document file://worker-trust-policy.json

# Attach S3 policy to Worker role
aws iam attach-role-policy \
  --role-name sentineltranslate-worker-role \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/SentinelTranslateS3Access
```

### 5. Create Custom Values File

**For Production:**

```bash
cat > my-prod-values.yaml <<EOF
# Use values-prod.yaml as base and customize
sidecar:
  image:
    repository: ${ECR_REGISTRY}/sentineltranslate-sidecar
    tag: ${IMAGE_TAG}

api:
  image:
    repository: ${ECR_REGISTRY}/sentineltranslate-api
    tag: ${IMAGE_TAG}
  serviceAccount:
    annotations:
      eks.amazonaws.com/role-arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/sentineltranslate-api-role

worker:
  image:
    repository: ${ECR_REGISTRY}/sentineltranslate-worker
    tag: ${IMAGE_TAG}
  serviceAccount:
    annotations:
      eks.amazonaws.com/role-arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/sentineltranslate-worker-role

ingress:
  annotations:
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:${AWS_REGION}:${AWS_ACCOUNT_ID}:certificate/YOUR_CERT_ID
  hosts:
    - host: translate.yourdomain.com
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
EOF
```

### 6. Install Chart

**Development:**

```bash
helm install sentineltranslate . \
  --namespace sentineltranslate \
  --create-namespace \
  --values values-dev.yaml
```

**Production:**

```bash
helm install sentineltranslate . \
  --namespace sentineltranslate \
  --create-namespace \
  --values values-prod.yaml \
  --values my-prod-values.yaml
```

### 7. Verify Installation

```bash
# Check all pods are running
kubectl get pods -n sentineltranslate

# Expected output:
# NAME                                          READY   STATUS    RESTARTS   AGE
# sentineltranslate-redis-master-0              1/1     Running   0          2m
# sentineltranslate-triton-xxxxxxxxx-xxxxx      1/1     Running   0          2m
# sentineltranslate-sidecar-xxxxxxxxx-xxxxx     1/1     Running   0          2m
# sentineltranslate-api-xxxxxxxxx-xxxxx         1/1     Running   0          2m
# sentineltranslate-worker-xxxxxxxxx-xxxxx      1/1     Running   0          2m

# Check services
kubectl get svc -n sentineltranslate

# Check ingress (if enabled)
kubectl get ingress -n sentineltranslate

# View deployment logs
kubectl logs -n sentineltranslate deployment/sentineltranslate-sidecar --tail=50
```

### 8. Test Endpoints

**With Port-Forward (Development):**

```bash
# Test Sidecar API
kubectl port-forward -n sentineltranslate svc/sentineltranslate-sidecar 8080:8080 &

curl -X POST http://localhost:8080/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "source_lang": "en",
    "target_lang": "fr"
  }'

# Test Batch API
kubectl port-forward -n sentineltranslate svc/sentineltranslate-api 8090:8090 &

curl http://localhost:8090/health
```

**With Ingress (Production):**

```bash
# Wait for ALB to be provisioned
kubectl get ingress -n sentineltranslate -w

# Once ADDRESS is populated, test
curl -X POST https://translate.yourdomain.com/api/v1/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "source_lang": "en",
    "target_lang": "fr"
  }'
```

## Upgrading

### Update Image Tags

```bash
helm upgrade sentineltranslate . \
  --namespace sentineltranslate \
  --values values-prod.yaml \
  --values my-prod-values.yaml \
  --set sidecar.image.tag=v1.1.0 \
  --set api.image.tag=v1.1.0 \
  --set worker.image.tag=v1.1.0
```

### Update Configuration

```bash
# Edit your values file, then:
helm upgrade sentineltranslate . \
  --namespace sentineltranslate \
  --values values-prod.yaml \
  --values my-prod-values.yaml
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod -n sentineltranslate <pod-name>

# Check events
kubectl get events -n sentineltranslate --sort-by='.lastTimestamp'
```

### Image Pull Errors

```bash
# Verify ECR access (for EKS nodes)
aws ecr get-login-password --region us-east-1

# Check if images exist
aws ecr describe-images --repository-name sentineltranslate-sidecar --region us-east-1
```

### GPU Not Available

```bash
# Check GPU nodes
kubectl get nodes -o json | jq '.items[].status.allocatable."nvidia.com/gpu"'

# Verify NVIDIA device plugin
kubectl get pods -n kube-system | grep nvidia
```

### Ingress Not Creating ALB

```bash
# Check AWS Load Balancer Controller
kubectl logs -n kube-system deployment/aws-load-balancer-controller

# Verify IAM permissions for controller
kubectl describe sa -n kube-system aws-load-balancer-controller
```

## Uninstalling

```bash
# Uninstall the release
helm uninstall sentineltranslate --namespace sentineltranslate

# Delete namespace
kubectl delete namespace sentineltranslate

# Clean up AWS resources (if no longer needed)
aws iam detach-role-policy \
  --role-name sentineltranslate-api-role \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/SentinelTranslateS3Access

aws iam delete-role --role-name sentineltranslate-api-role

aws iam detach-role-policy \
  --role-name sentineltranslate-worker-role \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/SentinelTranslateS3Access

aws iam delete-role --role-name sentineltranslate-worker-role

aws iam delete-policy \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/SentinelTranslateS3Access
```
