# SentinelTranslate AWS EKS Infrastructure

This directory contains Terraform infrastructure code for deploying SentinelTranslate to AWS EKS with GPU support and cost optimization.

## Architecture Overview

### Components Deployed
- **VPC**: Custom VPC with public/private subnets across 2 availability zones (EKS requirement)
- **EKS Cluster**: Kubernetes 1.31 control plane with managed node groups
- **Node Groups**:
  - CPU nodes: t3.medium (1-4 nodes, auto-scaling) - API, worker, Redis
  - GPU nodes: g4dn.xlarge (disabled by default) - Triton Inference Server
- **IAM Roles**: IRSA for S3 access, node roles, cluster roles with proper permissions
- **Security Groups**: Proper network segmentation
- **S3 Bucket**: Auto-generated bucket for translation workloads with lifecycle policies
- **VPC Endpoints**: S3 gateway endpoint to reduce NAT costs

### Cost Optimization Features
- Single NAT gateway shared across both AZs (saves ~$32/month per additional gateway)
- t3.medium instances for CPU workloads (balance between cost and performance)
- GPU nodes disabled by default (enable after requesting Spot instance limits)
- CPU node group auto-scales down to 1 node minimum
- S3 VPC gateway endpoint eliminates NAT charges for S3 traffic
- gp3 EBS volumes with minimal sizes
- CloudWatch log retention set to 7 days (configurable)

### Network Architecture
```
VPC (10.0.0.0/16)
├── us-east-1a
│   ├── Public Subnet (10.0.1.0/24) - NAT Gateway, Load Balancers
│   └── Private Subnet (10.0.11.0/24) - EKS nodes, workloads
└── us-east-1b
    ├── Public Subnet (10.0.2.0/24) - (NAT traffic routes to 1a)
    └── Private Subnet (10.0.12.0/24) - EKS nodes, workloads
```

### Key Infrastructure Features

**✅ Production-Ready Configuration**
- Kubernetes 1.32 (latest stable version)
- Dual-AZ deployment for high availability
- Auto-scaling node groups (1-4 CPU nodes)
- IRSA (IAM Roles for Service Accounts) for secure S3 access
- VPC gateway endpoint for S3 (eliminates NAT charges)
- CloudWatch logging with configurable retention

**✅ Cost-Optimized Design**
- Single NAT gateway shared across AZs (~$142/month base cost)
- CPU nodes start at 1, scale to 4 based on demand
- GPU nodes disabled by default (enable after Spot limit approval)
- gp3 EBS volumes with right-sized storage (50GB)
- S3 lifecycle policies for automatic archival

**✅ Security Best Practices**
- Private subnets for all EKS workloads
- IAM roles with least-privilege access
- EBS encryption enabled by default
- Configurable cluster endpoint access controls
- Network security groups with proper segmentation

## Prerequisites

1. **AWS Account**: With appropriate IAM permissions (see IAM Requirements below)
2. **Terraform**: v1.6+ installed
3. **AWS CLI**: v2+ configured with credentials
4. **kubectl**: v1.32+ for cluster management

### IAM Requirements

Your AWS user/role needs comprehensive permissions to create EKS infrastructure. The following AWS managed policies provide base access:
- `AmazonEKSClusterPolicy`
- `AmazonEKSServicePolicy`
- `AmazonEC2FullAccess`
- `IAMFullAccess`

**IMPORTANT**: You must also attach a custom policy with additional permissions for EKS addons, VPC endpoints, and CloudWatch. See [IAM Policy](#required-iam-policy) section below for the complete policy.

## Quick Start

### 1. Configure Backend (First Time Setup)

Create an S3 bucket and DynamoDB table for state management:

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://sentinel-terraform-state-$(aws sts get-caller-identity --query Account --output text)

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket sentinel-terraform-state-$(aws sts get-caller-identity --query Account --output text) \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name sentinel-terraform-locks \
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
- `project_name`: Project identifier (default: `sentinel` - kept short to fit 38-char IAM limit)
- `environment`: Environment name (default: `dev`)
- `aws_region`: AWS region (default: `us-east-1` for best free tier coverage)
- `cluster_version`: Kubernetes version (default: `1.32` - latest stable, 1.31 is EOL)
- `availability_zones`: List of AZs (minimum 2 required for EKS)
- `enable_gpu_nodes`: Set to `false` initially (Spot instance limits require approval)
- `single_nat_gateway`: Set to `true` to share NAT across AZs (saves ~$32/month)

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

## Using the infra-builder IAM User

The `infra-builder` IAM user is configured for CI/CD pipelines and infrastructure automation with the following permissions:
- ECR access for pushing/pulling container images
- EKS cluster access for Helm chart deployments
- Kubernetes cluster admin permissions

### Configure infra-builder Credentials

```bash
# Configure AWS credentials for infra-builder
aws configure --profile infra-builder
# Enter the access key ID and secret access key for infra-builder

# Or export credentials directly (for CI/CD)
export AWS_ACCESS_KEY_ID=<infra-builder-access-key>
export AWS_SECRET_ACCESS_KEY=<infra-builder-secret-key>
export AWS_DEFAULT_REGION=us-east-1
```

### ECR Login and Docker Operations

```bash
# Login to ECR using infra-builder credentials
aws ecr get-login-password --region us-east-1 --profile infra-builder | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

# Create ECR repositories (if they don't exist)
aws ecr create-repository --repository-name sentinel-sidecar --region us-east-1 --profile infra-builder
aws ecr create-repository --repository-name sentinel-worker --region us-east-1 --profile infra-builder
aws ecr create-repository --repository-name sentinel-triton --region us-east-1 --profile infra-builder

# Build and push images
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"

# Sidecar
cd sidecar
docker build -t ${ECR_REGISTRY}/sentinel-sidecar:latest .
docker push ${ECR_REGISTRY}/sentinel-sidecar:latest

# Worker
cd ../worker
docker build -t ${ECR_REGISTRY}/sentinel-worker:latest .
docker push ${ECR_REGISTRY}/sentinel-worker:latest
```

### Configure kubectl with infra-builder

```bash
# Update kubeconfig using infra-builder credentials
aws eks update-kubeconfig \
  --region us-east-1 \
  --name sentinel-dev-eks \
  --profile infra-builder

# Verify access
kubectl get nodes
kubectl get pods --all-namespaces
```

### Deploy Helm Charts

```bash
# Install or upgrade the SentinelTranslate Helm chart
cd infrastructure/helm/sentineltranslate

# For development environment
helm upgrade --install sentineltranslate . \
  --namespace default \
  --set image.sidecar.repository=${ECR_REGISTRY}/sentinel-sidecar \
  --set image.sidecar.tag=latest \
  --set image.worker.repository=${ECR_REGISTRY}/sentinel-worker \
  --set image.worker.tag=latest \
  --set image.triton.repository=${ECR_REGISTRY}/sentinel-triton \
  --set image.triton.tag=latest

# Verify deployment
kubectl get pods
kubectl logs -l app=sentineltranslate-sidecar
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
| CPU Nodes | 1x t3.medium (24/7) | ~$30 |
| GPU Node | Disabled by default | $0 |
| NAT Gateway | Single gateway (2 AZs) | ~$32 |
| EBS Volumes | 50GB gp3 | ~$4 |
| CloudWatch Logs | 7-day retention | ~$3 |
| **Total (minimal config)** | | **~$142/month** |
| **With GPU enabled (8h/day)** | | **~$236/month** |
| **With 2 CPU nodes (HA)** | | **~$172/month** |

**Note**: GPU nodes are disabled by default. To enable, request Spot instance limit increase from AWS Support and set `enable_gpu_nodes = true`.

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

### Why Dual AZ?
- **EKS Requirement**: EKS requires subnets in at least 2 availability zones
- **High Availability**: Cluster can survive single AZ failure
- **Cost Optimization**: Single NAT gateway shared across both AZs (saves $32/month)
- **Production Ready**: Meets AWS Well-Architected Framework recommendations
- **Trade-off**: Minimal cross-AZ data transfer costs (~$0.01/GB for inter-AZ traffic)

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

### IAM Permission Errors

**Issue**: `AccessDeniedException: User is not authorized to perform: eks:DescribeAddonVersions`
**Solution**: Your IAM user/role is missing required permissions. Apply the comprehensive IAM policy:

```bash
# Save policy to file
cat > /tmp/terraform-eks-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "EKSClusterPermissions",
            "Effect": "Allow",
            "Action": ["eks:*"],
            "Resource": "*"
        },
        {
            "Sid": "EC2andVPCPermissions",
            "Effect": "Allow",
            "Action": ["ec2:*"],
            "Resource": "*"
        },
        {
            "Sid": "IAMPermissions",
            "Effect": "Allow",
            "Action": ["iam:*"],
            "Resource": "*"
        },
        {
            "Sid": "CloudWatchLogsPermissions",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:DeleteLogGroup",
                "logs:DescribeLogGroups",
                "logs:ListTagsLogGroup",
                "logs:PutRetentionPolicy",
                "logs:TagLogGroup",
                "logs:UntagLogGroup"
            ],
            "Resource": "*"
        },
        {
            "Sid": "S3Permissions",
            "Effect": "Allow",
            "Action": ["s3:*"],
            "Resource": "*"
        },
        {
            "Sid": "AutoScalingPermissions",
            "Effect": "Allow",
            "Action": ["autoscaling:*"],
            "Resource": "*"
        },
        {
            "Sid": "ElasticLoadBalancingPermissions",
            "Effect": "Allow",
            "Action": ["elasticloadbalancing:*"],
            "Resource": "*"
        },
        {
            "Sid": "KMSPermissions",
            "Effect": "Allow",
            "Action": [
                "kms:CreateGrant",
                "kms:DescribeKey",
                "kms:CreateKey",
                "kms:CreateAlias",
                "kms:DeleteAlias",
                "kms:ListAliases",
                "kms:TagResource",
                "kms:ScheduleKeyDeletion"
            ],
            "Resource": "*"
        },
        {
            "Sid": "DynamoDBPermissions",
            "Effect": "Allow",
            "Action": [
                "dynamodb:CreateTable",
                "dynamodb:DeleteTable",
                "dynamodb:DescribeTable",
                "dynamodb:DescribeContinuousBackups",
                "dynamodb:DescribeTimeToLive",
                "dynamodb:ListTagsOfResource",
                "dynamodb:TagResource",
                "dynamodb:UntagResource",
                "dynamodb:UpdateContinuousBackups",
                "dynamodb:UpdateTimeToLive"
            ],
            "Resource": "*"
        }
    ]
}
EOF

# Apply to IAM user
aws iam put-user-policy \
  --user-name YOUR_USERNAME \
  --policy-name TerraformEKSFullAccess \
  --policy-document file:///tmp/terraform-eks-policy.json

# Wait 30 seconds for IAM propagation
sleep 30
```

### EKS Cluster Creation Fails

**Issue**: Timeout during cluster creation
**Solution**: Check VPC subnet tags, ensure public subnets have `kubernetes.io/role/elb=1`

**Issue**: `Subnets specified must be in at least two different AZs`
**Solution**: Update `terraform.tfvars` to include at least 2 availability zones in `availability_zones` list

### GPU Spot Instance Limit Errors

**Issue**: `MaxSpotInstanceCountExceeded: Max spot instance count exceeded`
**Solution**:
1. GPU nodes are disabled by default (`enable_gpu_nodes = false`)
2. To enable GPU nodes, request a Spot instance limit increase:
   - Go to AWS Service Quotas console
   - Search for "EC2 Spot instances" → "All G and VT Spot Instance Requests"
   - Request limit increase (recommend at least 4 vCPUs for 1x g4dn.xlarge)
3. After approval, set `enable_gpu_nodes = true` in terraform.tfvars

### CloudWatch Log Group Already Exists

**Issue**: `ResourceAlreadyExistsException: The specified log group already exists`
**Solution**:
1. From a failed terraform apply - run `terraform destroy` to clean up
2. Or manually delete: `aws logs delete-log-group --log-group-name /aws/eks/sentinel-dev/cluster`
3. Then re-run `terraform apply`

### GPU Nodes Not Scheduling

**Issue**: Triton pods stuck in Pending (after enabling GPU nodes)
**Solution**:
1. Verify GPU node group is running: `kubectl get nodes -l node.kubernetes.io/instance-type=g4dn.xlarge`
2. Check device plugin: `kubectl get pods -n kube-system | grep nvidia`
3. Verify node labels: `kubectl describe node <gpu-node> | grep nvidia`
4. Check node taints are configured correctly (should be `nvidia.com/gpu=true:NO_SCHEDULE`)

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
# Delete all Kubernetes resources first (if deployed)
kubectl delete all --all --all-namespaces

# Wait for load balancers to be deleted (check AWS Console)
sleep 60

# Destroy Terraform infrastructure
terraform destroy

# Optionally delete Terraform state bucket
aws s3 rb s3://sentinel-terraform-state-$(aws sts get-caller-identity --query Account --output text) --force

# Optionally delete DynamoDB lock table
aws dynamodb delete-table --table-name sentinel-terraform-locks
```

## Security Best Practices

1. **Secrets**: Use AWS Secrets Manager or External Secrets Operator
2. **Network Policies**: Implement Kubernetes network policies (see k8s manifests)
3. **RBAC**: Use least-privilege service accounts
4. **Pod Security**: Enable Pod Security Standards
5. **Encryption**: EBS volumes encrypted by default
6. **Private Endpoints**: Consider private EKS endpoint for production

## Next Steps

1. Deploy application with Helm charts: `cd ../helm/sentineltranslate && helm install sentineltranslate . -f values-prod.yaml`
2. Configure horizontal pod autoscaling for workers
3. Enable monitoring stack (Prometheus/Grafana): `helm install -f values-monitoring.yaml`
4. Request GPU Spot instance limit increase (if needed)
5. Keep Kubernetes version up to date with quarterly EKS releases

## Recent Changes & Improvements

This infrastructure configuration has been updated with the following improvements:

**Configuration Updates:**
- ✅ Upgraded to Kubernetes 1.32 (latest stable, 1.31 is EOL)
- ✅ Changed from single-AZ to dual-AZ deployment (EKS requirement)
- ✅ Shortened project name from "sentineltranslate" to "sentinel" (38-char IAM limit)
- ✅ Added S3 VPC gateway endpoint (reduces NAT costs)
- ✅ Disabled GPU nodes by default (Spot instance limits)
- ✅ Fixed S3 lifecycle configuration (added required filter attribute)
- ✅ Fixed node taint casing (NO_SCHEDULE per AWS requirements)
- ✅ Added comprehensive IAM policy for Terraform operations

**Known Limitations:**
- GPU nodes disabled until AWS Spot instance limit increase approved
- Single NAT gateway creates single point of failure (cost optimization trade-off)
- EKS control plane costs $73/month (unavoidable AWS charge)
- Kubernetes version upgrades must be incremental (can't skip versions)

## Support

For issues with:
- **Terraform code**: Check troubleshooting section above or module documentation
- **IAM permissions**: Use the comprehensive policy in the Troubleshooting section
- **EKS cluster**: Refer to AWS EKS documentation
- **Application deployment**: See Helm charts in `../helm/sentineltranslate/README.md`
- **General questions**: See project root README.md
