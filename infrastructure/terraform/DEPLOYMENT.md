# SentinelTranslate EKS Deployment Guide

This guide walks you through deploying SentinelTranslate to AWS EKS from scratch.

## Prerequisites Checklist

- [ ] AWS account with appropriate permissions
- [ ] AWS CLI v2+ installed and configured (`aws configure`)
- [ ] Terraform v1.6+ installed
- [ ] kubectl v1.28+ installed
- [ ] helm v3+ installed
- [ ] Make utility installed (optional, for convenience)

## Step 1: Verify AWS Access

```bash
# Check your AWS credentials
aws sts get-caller-identity

# Expected output shows your account ID and user ARN
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-username"
}
```

## Step 2: Configure Terraform Backend

Create S3 bucket and DynamoDB table for state management:

```bash
# Using Make (recommended)
make backend-init

# Or manually:
export AWS_REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create S3 bucket
aws s3 mb s3://sentineltranslate-terraform-state-${ACCOUNT_ID} --region ${AWS_REGION}

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket sentineltranslate-terraform-state-${ACCOUNT_ID} \
  --versioning-configuration Status=Enabled

# Create DynamoDB table
aws dynamodb create-table \
  --table-name sentineltranslate-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ${AWS_REGION}
```

Update `backend.tf` with your bucket name:

```hcl
terraform {
  backend "s3" {
    bucket = "sentineltranslate-terraform-state-123456789012"  # Update with your account ID
    key    = "eks/terraform.tfstate"
    region = "us-east-1"
    # ... rest of config
  }
}
```

## Step 3: Configure Variables

```bash
# Copy example configuration
cp terraform.tfvars.example terraform.tfvars

# Edit with your preferences
vim terraform.tfvars
```

### Recommended Configurations by Use Case

#### Development (Minimal Cost ~$105/month)

```hcl
environment = "dev"
availability_zones = ["us-east-1a"]
cpu_node_desired_size = 1
cpu_node_min_size = 1
gpu_node_desired_size = 0
enable_gpu_nodes = false  # Enable only when needed
```

#### Testing with GPU (8h/day ~$175/month)

```hcl
environment = "dev"
availability_zones = ["us-east-1a"]
cpu_node_desired_size = 2
gpu_node_desired_size = 1
gpu_node_min_size = 0  # Scales to 0 when idle
enable_cluster_autoscaler = true
```

#### Production (HA ~$550/month)

```hcl
environment = "prod"
availability_zones = ["us-east-1a", "us-east-1b"]
single_nat_gateway = false
cpu_node_min_size = 2
cpu_node_desired_size = 3
gpu_node_min_size = 1
gpu_node_desired_size = 1
cluster_endpoint_public_access = false  # Use VPN/bastion
enable_secrets_encryption = true
```

## Step 4: Initialize Terraform

```bash
# Initialize providers and modules
make init

# Or manually:
terraform init
```

This downloads required providers (AWS, Kubernetes, Helm) and modules.

## Step 5: Review Infrastructure Plan

```bash
# Generate execution plan
make plan

# Or manually:
terraform plan -out=tfplan
```

**Important**: Review the plan carefully! Look for:
- Number of resources to be created
- Instance types and counts
- Estimated costs (see outputs)
- Security group rules
- IAM permissions

Expected resource count: ~60-80 resources

## Step 6: Apply Infrastructure

```bash
# Apply the plan
make apply

# Or manually:
terraform apply tfplan
```

**Duration**: 15-20 minutes (EKS control plane takes ~10 minutes)

### What Gets Created?

1. **VPC Resources** (2-3 minutes):
   - VPC with public/private subnets
   - Internet Gateway
   - NAT Gateway
   - Route tables
   - VPC endpoints (S3)

2. **EKS Cluster** (10-12 minutes):
   - Control plane
   - OIDC provider for IRSA
   - Security groups
   - CloudWatch log groups

3. **Node Groups** (5-7 minutes):
   - CPU node group (t3.medium)
   - GPU node group (g4dn.xlarge, if enabled)
   - Launch templates
   - Auto-scaling groups

4. **IAM Resources** (1-2 minutes):
   - Service account roles (IRSA)
   - Node instance roles
   - Policies for S3, EBS, VPC CNI

5. **S3 Bucket** (<1 minute):
   - Translation data bucket
   - Encryption, versioning, lifecycle rules

## Step 7: Configure kubectl

```bash
# Update kubeconfig
make kubeconfig

# Or manually:
aws eks update-kubeconfig --region us-east-1 --name sentineltranslate-dev-eks

# Verify connection
kubectl cluster-info
kubectl get nodes
```

Expected output:
```
NAME                         STATUS   ROLES    AGE   VERSION
ip-10-0-11-xxx.ec2.internal  Ready    <none>   5m    v1.28.x
ip-10-0-11-yyy.ec2.internal  Ready    <none>   5m    v1.28.x
```

## Step 8: Install Kubernetes Addons

### GPU Device Plugin (if GPU nodes enabled)

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# Verify GPU availability
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
```

### AWS Load Balancer Controller

```bash
# Create IAM policy
curl -o iam-policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.6.0/docs/install/iam_policy.json

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam-policy.json

# Create service account
eksctl create iamserviceaccount \
  --cluster=sentineltranslate-dev-eks \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --attach-policy-arn=arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy \
  --override-existing-serviceaccounts \
  --approve

# Install controller via Helm
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=sentineltranslate-dev-eks \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

### Metrics Server

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify
kubectl top nodes
```

### Cluster Autoscaler (if enabled in tfvars)

```bash
# Download manifest
curl -o cluster-autoscaler-autodiscover.yaml https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml

# Edit to add cluster name
sed -i "s/<YOUR CLUSTER NAME>/sentineltranslate-dev-eks/g" cluster-autoscaler-autodiscover.yaml

# Apply
kubectl apply -f cluster-autoscaler-autodiscover.yaml

# Verify
kubectl get pods -n kube-system | grep cluster-autoscaler
```

## Step 9: Verify Infrastructure

### Check Terraform Outputs

```bash
# View all outputs
terraform output

# Key outputs:
terraform output cluster_name
terraform output cluster_endpoint
terraform output s3_bucket_name
terraform output s3_access_role_arn
terraform output configure_kubectl_command
```

### Verify Node Groups

```bash
# Check nodes
kubectl get nodes -o wide

# Check node labels
kubectl get nodes --show-labels

# Verify GPU nodes (if enabled)
kubectl get nodes -l workload-type=gpu
```

### Verify Service Accounts

```bash
# Check IRSA annotations
kubectl get sa sentineltranslate-worker -o yaml
kubectl get sa sentineltranslate-api -o yaml

# Should see annotation:
# eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/...
```

### Test S3 Access

```bash
# Create test pod with worker service account
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: s3-test
spec:
  serviceAccountName: sentineltranslate-worker
  containers:
  - name: aws-cli
    image: amazon/aws-cli
    command: ['sleep', '3600']
EOF

# Wait for pod to start
kubectl wait --for=condition=Ready pod/s3-test --timeout=60s

# Test S3 access
S3_BUCKET=$(terraform output -raw s3_bucket_name)
kubectl exec s3-test -- aws s3 ls s3://${S3_BUCKET}

# Cleanup
kubectl delete pod s3-test
```

## Step 10: Deploy SentinelTranslate

See `../../kubernetes/README.md` for Kubernetes manifest deployment.

Quick start:

```bash
cd ../../kubernetes
kubectl apply -f namespace.yaml
kubectl apply -f redis.yaml
kubectl apply -f triton.yaml
kubectl apply -f worker.yaml
kubectl apply -f sidecar.yaml
kubectl apply -f api.yaml
```

## Post-Deployment Operations

### Scaling GPU Nodes

```bash
# Scale GPU nodes to 0 to save costs when not in use
make scale-gpu-down

# Scale back up when needed
make scale-gpu-up

# Or directly with kubectl:
kubectl scale deployment triton --replicas=0
kubectl scale deployment triton --replicas=1
```

### Monitoring Costs

```bash
# View estimated monthly costs
make cost

# Monitor actual costs in AWS Cost Explorer:
# https://console.aws.amazon.com/cost-management/home
```

### Viewing Logs

```bash
# EKS control plane logs
make logs-cluster

# Application logs
kubectl logs -f deployment/api
kubectl logs -f deployment/sidecar
kubectl logs -f deployment/worker
kubectl logs -f deployment/triton
```

### Updating Infrastructure

```bash
# Edit terraform.tfvars
vim terraform.tfvars

# Plan changes
make plan

# Apply changes
make apply
```

## Troubleshooting

### Issue: Terraform Init Fails

**Error**: "Error configuring S3 Backend: NoSuchBucket"

**Solution**: Run `make backend-init` first to create S3 bucket and DynamoDB table.

### Issue: EKS Cluster Creation Timeout

**Error**: "waiting for EKS Cluster (sentineltranslate-dev-eks) to create: timeout"

**Solution**: Check CloudFormation console for stack errors. Common causes:
- Insufficient IAM permissions
- Service quota limits reached
- Subnet tag issues

### Issue: Nodes Not Joining Cluster

**Error**: Nodes stuck in "NotReady" state

**Solution**:
```bash
# Check node logs
kubectl describe node <node-name>

# Check CloudWatch logs for kubelet errors
aws logs tail /aws/eks/sentineltranslate-dev-eks/cluster --follow

# Verify security groups allow node-to-control-plane communication
```

### Issue: GPU Pods Pending

**Error**: Triton pod stuck in "Pending" state

**Solution**:
```bash
# Verify GPU nodes exist
kubectl get nodes -l workload-type=gpu

# Check GPU device plugin
kubectl get pods -n kube-system | grep nvidia-device-plugin

# Verify GPU capacity
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'

# Check pod events
kubectl describe pod <triton-pod-name>
```

### Issue: S3 Access Denied

**Error**: Worker pods cannot access S3 bucket

**Solution**:
```bash
# Verify service account annotation
kubectl get sa sentineltranslate-worker -o yaml

# Check IAM role trust policy
aws iam get-role --role-name $(terraform output -raw s3_access_role_name)

# Verify pod is using correct service account
kubectl get pod <worker-pod> -o yaml | grep serviceAccountName
```

### Issue: High Costs

**Problem**: AWS bill higher than expected

**Investigation**:
```bash
# Check current resource usage
kubectl top nodes
kubectl top pods --all-namespaces

# Review running instances
aws ec2 describe-instances --filters "Name=tag:Project,Values=sentineltranslate" \
  --query 'Reservations[].Instances[].[InstanceType,State.Name,PrivateIpAddress]' \
  --output table

# Check NAT Gateway data transfer
aws cloudwatch get-metric-statistics \
  --namespace AWS/NATGateway \
  --metric-name BytesOutToDestination \
  --dimensions Name=NatGatewayId,Value=<nat-gateway-id> \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum
```

**Cost Reduction**:
1. Scale GPU nodes to 0 when not in use: `make scale-gpu-down`
2. Reduce CPU node count: Update `cpu_node_desired_size` in tfvars
3. Use Spot instances: Set `enable_cpu_spot_instances = true`
4. Delete entire cluster when not needed: `make destroy`

## Cleanup

### Destroy All Infrastructure

**WARNING**: This will delete all resources including data in S3!

```bash
# Delete Kubernetes resources first
kubectl delete all --all --all-namespaces

# Wait for load balancers to be deleted (5-10 minutes)
kubectl get svc --all-namespaces

# Destroy Terraform infrastructure
make destroy

# Or manually:
terraform destroy

# Optionally, delete state backend
aws s3 rb s3://sentineltranslate-terraform-state-${ACCOUNT_ID} --force
aws dynamodb delete-table --table-name sentineltranslate-terraform-locks
```

### Partial Cleanup (Keep Cluster, Remove Workloads)

```bash
# Delete application workloads
kubectl delete -f ../../kubernetes/

# Scale nodes to minimum
kubectl scale deployment --all --replicas=0
```

## Security Hardening (Production)

Before going to production, implement these security measures:

1. **Restrict API Access**:
   ```hcl
   cluster_endpoint_public_access = false
   cluster_endpoint_public_access_cidrs = ["10.0.0.0/8"] # Your VPN CIDR
   ```

2. **Enable Secrets Encryption**:
   ```hcl
   enable_secrets_encryption = true
   ```

3. **Implement Network Policies**:
   ```bash
   kubectl apply -f ../../kubernetes/network-policies/
   ```

4. **Enable Pod Security Standards**:
   ```bash
   kubectl label namespace default pod-security.kubernetes.io/enforce=restricted
   ```

5. **Rotate Credentials Regularly**:
   - AWS IAM access keys
   - Kubernetes service account tokens
   - S3 bucket policies

6. **Enable Audit Logging**:
   ```hcl
   cluster_log_types = ["api", "audit", "authenticator"]
   ```

7. **Implement Backup Strategy**:
   - Regular snapshots of EBS volumes
   - S3 bucket replication
   - Velero for cluster backups

## Next Steps

1. Deploy application manifests (see `../../kubernetes/README.md`)
2. Set up monitoring (Prometheus/Grafana)
3. Configure CI/CD pipeline
4. Implement backup and disaster recovery
5. Set up alerting (CloudWatch Alarms, PagerDuty)
6. Performance testing and optimization
7. Cost optimization review

## Additional Resources

- [AWS EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Terraform AWS EKS Module](https://registry.terraform.io/modules/terraform-aws-modules/eks/aws/latest)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/getting-started.html)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
