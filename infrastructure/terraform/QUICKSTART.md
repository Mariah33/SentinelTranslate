# SentinelTranslate EKS Quick Start

Get SentinelTranslate running on AWS EKS in under 30 minutes.

## Prerequisites (5 minutes)

```bash
# Install required tools (if not already installed)
brew install awscli terraform kubectl helm  # macOS
# or
apt-get install awscli terraform kubectl helm  # Ubuntu

# Configure AWS credentials
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and region (us-east-1)
```

## Deploy Infrastructure (20 minutes)

### 1. Initialize Backend (2 minutes)

```bash
cd infrastructure/terraform

# Create S3 bucket and DynamoDB table for state
make backend-init

# Update backend.tf with your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
sed -i "s/sentineltranslate-terraform-state/sentineltranslate-terraform-state-${ACCOUNT_ID}/" backend.tf
```

### 2. Configure Variables (1 minute)

```bash
# Copy example configuration
cp terraform.tfvars.example terraform.tfvars

# For development (minimal cost ~$120/month):
cat > terraform.tfvars <<'EOF'
project_name = "sentineltranslate"
environment = "dev"
aws_region = "us-east-1"

# Single AZ for cost optimization
availability_zones = ["us-east-1a"]

# Minimal CPU nodes
cpu_node_desired_size = 1
cpu_node_min_size = 1

# GPU disabled initially (enable when needed)
enable_gpu_nodes = false

# Enable autoscaling
enable_cluster_autoscaler = true
EOF
```

### 3. Deploy (15 minutes)

```bash
# Initialize Terraform
make init

# Review plan
make plan

# Apply infrastructure (takes ~15 minutes)
make apply

# Note: EKS control plane creation takes 10-12 minutes
```

### 4. Configure kubectl (1 minute)

```bash
# Update kubeconfig
make kubeconfig

# Verify cluster access
kubectl get nodes
# Should show 1 node in Ready state
```

## Enable GPU Support (Optional, +5 minutes)

If you need GPU for Triton:

```bash
# Update terraform.tfvars
cat >> terraform.tfvars <<'EOF'

# Enable GPU node group
enable_gpu_nodes = true
gpu_node_desired_size = 1
gpu_node_min_size = 0  # Allow scaling to 0
enable_gpu_spot_instances = true  # Save 70% on costs
EOF

# Apply changes
terraform apply -auto-approve

# Wait for GPU node (~5 minutes)
kubectl get nodes -w

# Install NVIDIA device plugin
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# Verify GPU
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
# Should show "1"
```

## Deploy Application (5 minutes)

```bash
# Create Kubernetes manifests directory
cd ../../kubernetes  # From project root

# Create namespace
kubectl create namespace sentineltranslate

# Deploy Redis
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: sentineltranslate
spec:
  ports:
  - port: 6379
    targetPort: 6379
  selector:
    app: redis
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: sentineltranslate
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
EOF

# Deploy Triton (if GPU enabled)
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: triton
  namespace: sentineltranslate
spec:
  ports:
  - port: 8000
    targetPort: 8000
    name: http
  - port: 8001
    targetPort: 8001
    name: grpc
  - port: 8002
    targetPort: 8002
    name: metrics
  selector:
    app: triton
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: triton
  namespace: sentineltranslate
spec:
  replicas: 1
  selector:
    matchLabels:
      app: triton
  template:
    metadata:
      labels:
        app: triton
    spec:
      nodeSelector:
        workload-type: gpu
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
      containers:
      - name: triton
        image: nvcr.io/nvidia/tritonserver:23.10-py3
        ports:
        - containerPort: 8000
        - containerPort: 8001
        - containerPort: 8002
        resources:
          limits:
            nvidia.com/gpu: 1
        volumeMounts:
        - name: model-repository
          mountPath: /models
      volumes:
      - name: model-repository
        emptyDir: {}  # Replace with persistent volume for production
EOF

# Verify deployments
kubectl get pods -n sentineltranslate
```

## Verify Everything Works

```bash
# Check nodes
kubectl get nodes

# Check pods
kubectl get pods -n sentineltranslate

# Check services
kubectl get svc -n sentineltranslate

# Check GPU allocation (if enabled)
kubectl describe node -l workload-type=gpu | grep nvidia.com/gpu

# Port-forward Redis to test
kubectl port-forward -n sentineltranslate svc/redis 6379:6379 &
redis-cli ping  # Should return PONG
```

## Cost Management

### Check Estimated Costs

```bash
cd ../../infrastructure/terraform
make cost

# Example output:
# eks_control_plane: $73
# cpu_nodes: $30.37
# gpu_nodes: $0  (if disabled)
# nat_gateway: $32
# ebs_storage: $4
# total_minimum: $139.37
```

### Scale GPU to 0 (Save ~$380/month)

```bash
# Stop Triton
kubectl scale deployment triton -n sentineltranslate --replicas=0

# Cluster autoscaler will scale GPU node to 0 after ~10 minutes
kubectl get nodes -w
```

### Delete Everything (Save 100%)

```bash
cd infrastructure/terraform

# Delete Kubernetes resources first
kubectl delete namespace sentineltranslate

# Wait for load balancers to be deleted
kubectl get svc --all-namespaces

# Destroy infrastructure
make destroy
```

## Common Issues

### Issue: "Error: configuring Terraform AWS Provider: no valid credential sources"

**Fix**:
```bash
aws configure
# Enter credentials
```

### Issue: "Error creating EKS Cluster: UnsupportedAvailabilityZoneException"

**Fix**: Change availability zone in terraform.tfvars:
```hcl
availability_zones = ["us-east-1b"]  # Try different AZ
```

### Issue: GPU pods pending

**Fix**:
```bash
# Verify GPU node exists
kubectl get nodes -l workload-type=gpu

# If missing, check Terraform
cd infrastructure/terraform
terraform output gpu_node_group_status

# If "CREATING", wait 5 minutes. If error, check AWS console.
```

### Issue: "Error: Error acquiring the state lock"

**Fix**:
```bash
# Force unlock (use carefully!)
terraform force-unlock <LOCK_ID>
```

## Next Steps

1. **Deploy full application**: See `../../kubernetes/README.md`
2. **Set up monitoring**: Install Prometheus/Grafana
3. **Configure autoscaling**: Set up HPA for workers
4. **Implement CI/CD**: Automate deployments
5. **Review costs**: Check AWS Cost Explorer after 24 hours

## Useful Commands

```bash
# Terraform
make init          # Initialize
make plan          # Plan changes
make apply         # Apply changes
make destroy       # Destroy infrastructure
make kubeconfig    # Update kubectl config
make cost          # Show estimated costs

# Kubernetes
kubectl get nodes                          # List nodes
kubectl get pods -n sentineltranslate      # List pods
kubectl logs -f deployment/triton          # Follow logs
kubectl describe node <node-name>          # Node details
kubectl top nodes                          # Resource usage

# AWS
aws eks list-clusters                      # List EKS clusters
aws ec2 describe-instances                 # List EC2 instances
aws s3 ls                                  # List S3 buckets
```

## Cost Optimization Quick Wins

```bash
# 1. Use spot instances (save 70%)
echo 'enable_gpu_spot_instances = true' >> terraform.tfvars
echo 'enable_cpu_spot_instances = true' >> terraform.tfvars
terraform apply -auto-approve

# 2. Scale GPU to 0 when idle (save $380/month)
kubectl scale deployment triton -n sentineltranslate --replicas=0

# 3. Use single AZ (save $33/month)
# Already default in example config

# 4. Reduce logging (save $5/month)
echo 'cluster_log_retention_days = 1' >> terraform.tfvars
terraform apply -auto-approve

# 5. Delete cluster on weekends (save 27%)
# Friday 6 PM
terraform destroy -auto-approve

# Monday 6 AM
terraform init && terraform apply -auto-approve
```

## Support

- **Terraform issues**: Check `README.md` and `DEPLOYMENT.md`
- **Cost questions**: See `COST_OPTIMIZATION.md`
- **AWS issues**: Check CloudFormation console
- **Kubernetes issues**: Run `kubectl describe pod <pod-name>`

## Time Estimates

- **Initial setup**: 30 minutes
- **Enable GPU**: +5 minutes
- **Deploy application**: +5 minutes
- **Total**: ~40 minutes end-to-end

## Monthly Cost Estimates

| Configuration | Monthly Cost |
|---------------|--------------|
| Dev (no GPU) | ~$140 |
| Dev (GPU 8h/day spot) | ~$180 |
| Dev (GPU 24/7 spot) | ~$250 |
| Production (HA, on-demand) | ~$550 |
| Production (HA, Reserved) | ~$380 |

Choose based on your usage pattern!
