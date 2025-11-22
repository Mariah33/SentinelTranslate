# SentinelTranslate AWS EKS Infrastructure

This directory contains Terraform infrastructure code for deploying SentinelTranslate to AWS EKS with GPU support and free tier optimization.

## Architecture Overview

### Components Deployed
- **VPC**: Custom VPC with public/private subnets (single AZ for cost optimization)
- **EKS Cluster**: Kubernetes control plane (v1.28+)
- **Node Groups**:
  - CPU nodes: t3.medium (2 nodes) - API, sidecar, worker, Redis
  - GPU nodes: g4dn.xlarge (0-1 nodes, scalable) - Triton Inference Server
- **IAM Roles**: IRSA for S3 access, node roles, cluster roles
- **Security Groups**: Proper network segmentation
- **S3 Bucket**: Optional bucket for translation workloads

### Cost Optimization Features
- Single availability zone deployment (reduces data transfer costs)
- t3.medium instances for CPU workloads (balance between free tier and performance)
- GPU node group scalable to 0 when not in use
- Spot instance support for non-critical workloads
- Minimal EBS volumes with gp3 optimization

### Network Architecture
```
VPC (10.0.0.0/16)
├── Public Subnet (10.0.1.0/24) - NAT Gateway, Load Balancers
└── Private Subnet (10.0.11.0/24) - EKS nodes, workloads
```

## Prerequisites

1. **AWS Account**: With appropriate credentials configured
2. **Terraform**: v1.6+ installed
3. **AWS CLI**: v2+ configured with credentials
4. **kubectl**: v1.28+ for cluster management

## Quick Start

### 1. Configure Backend (First Time Setup)

Create an S3 bucket and DynamoDB table for state management:

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://sentineltranslate-terraform-state-$(aws sts get-caller-identity --query Account --output text)

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket sentineltranslate-terraform-state-$(aws sts get-caller-identity --query Account --output text) \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name sentineltranslate-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

Update `backend.tf` with your bucket name.

### 2. Initialize Terraform

```bash
cd infrastructure/terraform
terraform init
```

### 3. Review and Customize Variables

Edit `terraform.tfvars` (create from example):

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

Key variables:
- `project_name`: Project identifier (default: sentineltranslate)
- `environment`: Environment name (dev/staging/prod)
- `aws_region`: AWS region (default: us-east-1 for free tier)
- `enable_gpu_nodes`: Set to `false` to disable GPU nodes initially

### 4. Plan and Apply

```bash
# Review changes
terraform plan

# Apply infrastructure
terraform apply

# Save outputs
terraform output -json > outputs.json
```

### 5. Configure kubectl

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --region $(terraform output -raw region) \
  --name $(terraform output -raw cluster_name)

# Verify connection
kubectl get nodes
```

## Post-Deployment Steps

### 1. Install GPU Device Plugin (if GPU enabled)

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
```

### 2. Install AWS Load Balancer Controller

```bash
# Add Helm repo
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Install controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=$(terraform output -raw cluster_name) \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

### 3. Deploy Application

See `../../kubernetes/` directory for Kubernetes manifests.

## Cost Management

### Estimated Monthly Costs (us-east-1)

| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| EKS Control Plane | 1 cluster | $73 |
| CPU Nodes | 2x t3.medium (24/7) | ~$60 |
| GPU Node | 1x g4dn.xlarge (8h/day) | ~$94 |
| NAT Gateway | Single AZ | ~$32 |
| EBS Volumes | 100GB gp3 | ~$8 |
| **Total (GPU 8h/day)** | | **~$267/month** |
| **Total (GPU off)** | | **~$173/month** |

### Cost Optimization Strategies

1. **Scale GPU to 0 when not in use**:
   ```bash
   kubectl scale deployment triton --replicas=0
   # GPU node will auto-scale down after 10 minutes
   ```

2. **Use Spot instances for workers** (see `enable_spot_instances` variable)

3. **Stop cluster outside business hours**:
   ```bash
   # Scale all nodes to 0
   aws eks update-nodegroup-config \
     --cluster-name $(terraform output -raw cluster_name) \
     --nodegroup-name cpu-nodes \
     --scaling-config desiredSize=0,minSize=0,maxSize=2
   ```

4. **Delete when not in use**:
   ```bash
   terraform destroy
   ```

## Architecture Decisions

### Why Single AZ?
- **Cost**: Reduces cross-AZ data transfer charges (~$0.01/GB)
- **Simplicity**: Easier to manage for dev/test environments
- **Trade-off**: Lower availability (acceptable for non-production)
- **Production**: Set `availability_zones` to multiple AZs

### Why t3.medium for CPU nodes?
- **Balance**: t3.micro/small too small for Kubernetes overhead
- **Performance**: 2 vCPU, 4GB RAM suitable for containerized workloads
- **Burst**: T3 burst credits handle traffic spikes
- **Cost**: ~$30/month per instance

### Why g4dn.xlarge for GPU?
- **Smallest GPU**: 1x NVIDIA T4 GPU (16GB)
- **Sufficient**: Handles OPUS-MT ONNX models efficiently
- **Cost**: ~$0.526/hour on-demand, ~$0.158 spot
- **Alternative**: Consider g4dn.2xlarge for larger models

### Why Cluster Autoscaler?
- **GPU**: Automatically scales GPU nodes to 0 when Triton is idle
- **Cost**: Saves ~$282/month when GPU unused (16h/day)
- **Caveat**: 2-5 minute startup delay when scaling from 0

## Module Structure

```
infrastructure/terraform/
├── main.tf                 # Root module orchestration
├── variables.tf            # Input variables
├── outputs.tf             # Exported values
├── versions.tf            # Provider versions
├── backend.tf             # State backend configuration
├── terraform.tfvars.example  # Example variable values
├── modules/
│   ├── vpc/               # VPC and networking
│   ├── eks/               # EKS cluster
│   ├── iam/               # IAM roles and policies
│   └── security-groups/   # Security group rules
└── README.md              # This file
```

## Troubleshooting

### EKS Cluster Creation Fails

**Issue**: Timeout during cluster creation
**Solution**: Check VPC subnet tags, ensure public subnets have `kubernetes.io/role/elb=1`

### GPU Nodes Not Scheduling

**Issue**: Triton pods stuck in Pending
**Solution**:
1. Verify GPU node group is running: `kubectl get nodes -l node.kubernetes.io/instance-type=g4dn.xlarge`
2. Check device plugin: `kubectl get pods -n kube-system | grep nvidia`
3. Verify node labels: `kubectl describe node <gpu-node> | grep nvidia`

### S3 Access Denied

**Issue**: Worker pods cannot access S3
**Solution**:
1. Verify IRSA annotation: `kubectl get sa worker-sa -o yaml`
2. Check IAM role trust policy: `terraform output s3_access_role_arn`
3. Ensure pod spec has correct service account

### High NAT Gateway Costs

**Issue**: NAT Gateway charges exceeding budget
**Solution**:
1. Use VPC endpoints for S3 (included in this Terraform)
2. Review CloudWatch metrics for traffic patterns
3. Consider public subnet deployment for non-sensitive workloads

## Cleanup

To destroy all infrastructure:

```bash
# Delete all Kubernetes resources first
kubectl delete all --all --all-namespaces

# Destroy Terraform infrastructure
terraform destroy

# Confirm bucket deletion
aws s3 rb s3://sentineltranslate-terraform-state-<account-id> --force
```

## Security Best Practices

1. **Secrets**: Use AWS Secrets Manager or External Secrets Operator
2. **Network Policies**: Implement Kubernetes network policies (see k8s manifests)
3. **RBAC**: Use least-privilege service accounts
4. **Pod Security**: Enable Pod Security Standards
5. **Encryption**: EBS volumes encrypted by default
6. **Private Endpoints**: Consider private EKS endpoint for production

## Next Steps

1. Deploy Kubernetes manifests (`kubectl apply -f ../../kubernetes/`)
2. Configure horizontal pod autoscaling for workers
3. Set up monitoring (Prometheus/Grafana)
4. Implement CI/CD pipeline
5. Configure backup strategy for Redis data

## Support

For issues with:
- **Terraform code**: Check module documentation in `modules/*/README.md`
- **EKS cluster**: AWS EKS documentation
- **Application deployment**: See project root README.md
