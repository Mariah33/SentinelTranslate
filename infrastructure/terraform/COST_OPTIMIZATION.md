# AWS EKS Cost Optimization Guide for SentinelTranslate

This guide provides strategies to minimize AWS costs while running SentinelTranslate on EKS.

## Current Cost Breakdown

### Base Configuration (24/7 Operation)

| Component | Configuration | Monthly Cost (USD) |
|-----------|---------------|-------------------|
| EKS Control Plane | 1 cluster | $73.00 |
| CPU Nodes | 2x t3.medium (on-demand) | $60.74 |
| GPU Node | 1x g4dn.xlarge (on-demand) | $384.04 |
| NAT Gateway | 1 gateway + data transfer | $32.85 + data |
| EBS Volumes | 200GB gp3 (100GB CPU + 100GB GPU) | $16.00 |
| CloudWatch Logs | 7-day retention, ~10GB | $5.00 |
| **Total** | | **$571.63/month** |

### Optimized Configuration (GPU 8h/day, Development)

| Component | Configuration | Monthly Cost (USD) |
|-----------|---------------|-------------------|
| EKS Control Plane | 1 cluster | $73.00 |
| CPU Nodes | 1x t3.medium (spot) | $9.11 |
| GPU Node | 1x g4dn.xlarge (8h/day spot) | $37.44 |
| NAT Gateway | 1 gateway + minimal transfer | $32.85 |
| EBS Volumes | 100GB gp3 | $8.00 |
| CloudWatch Logs | 1-day retention, ~5GB | $2.50 |
| **Total** | | **$162.90/month** |

**Savings: 71% ($408.73/month)**

## Cost Optimization Strategies

### 1. EKS Control Plane ($73/month - Fixed)

The EKS control plane is a fixed cost of $0.10/hour per cluster.

**Optimization**:
- **Delete cluster when not in use**: Save $73/month
- **Share cluster across projects**: Split cost among multiple applications
- **Use ECS Fargate instead**: If you don't need Kubernetes features, ECS is cheaper

**When to delete**:
```bash
# Friday evening
make destroy

# Monday morning
make init && make plan && make apply
```

**Break-even point**: If you use the cluster <50% of the month, consider deleting when idle.

### 2. GPU Nodes ($384/month on-demand, $115/month spot)

GPU instances are the largest cost driver. g4dn.xlarge costs:
- **On-demand**: $0.526/hour = $384.04/month
- **Spot**: ~$0.158/hour = $115.21/month (70% savings)
- **8 hours/day on-demand**: $127.36/month (67% savings)
- **8 hours/day spot**: $38.21/month (90% savings)

**Optimization Strategies**:

#### A. Enable Cluster Autoscaler (Automatic)

Configure autoscaler to scale GPU nodes to 0 when Triton is not running:

```hcl
# terraform.tfvars
gpu_node_min_size = 0  # Allow scaling to zero
gpu_node_desired_size = 1
enable_cluster_autoscaler = true
```

The autoscaler will:
- Scale down to 0 after 10 minutes of no GPU pods
- Scale up automatically when you deploy Triton
- **Startup delay**: 2-5 minutes when scaling from 0

**Savings**: ~$256/month if GPU idle 16 hours/day

#### B. Use Spot Instances (70% savings)

```hcl
# terraform.tfvars
enable_gpu_spot_instances = true
```

**Pros**:
- 70% cost reduction
- Works well for dev/test environments
- Automatic replacement if interrupted

**Cons**:
- Can be interrupted with 2-minute warning
- Less suitable for production workloads
- Availability varies by region/AZ

**Best practice**: Use spot for development, on-demand for production.

#### C. Manual Scaling (Maximum Control)

Scale Triton deployment to 0 when not in use:

```bash
# Before leaving work
kubectl scale deployment triton --replicas=0

# When returning
kubectl scale deployment triton --replicas=1
```

Or use Terraform to set desired size to 0:

```bash
# Edit terraform.tfvars
gpu_node_desired_size = 0

# Apply changes
terraform apply
```

**Savings**: Up to $384/month if GPU completely unused

#### D. Use Smaller GPU Instance (Not Recommended)

Alternative GPU instances:
- **g4dn.xlarge**: 1x T4 GPU, $0.526/hour (current choice)
- **g5.xlarge**: 1x A10G GPU, $1.006/hour (faster, but 2x cost)

**Recommendation**: Stick with g4dn.xlarge for cost optimization.

### 3. CPU Nodes ($60/month on-demand, $18/month spot)

t3.medium costs:
- **On-demand**: $0.0416/hour = $30.37/month per instance
- **Spot**: ~$0.0125/hour = $9.11/month per instance (70% savings)

**Optimization Strategies**:

#### A. Reduce Node Count

```hcl
# Development (single node, no HA)
cpu_node_desired_size = 1
cpu_node_min_size = 1

# Savings: $30/month
```

**Trade-off**: No high availability, downtime during node updates.

#### B. Use Spot Instances

```hcl
enable_cpu_spot_instances = true
```

**Savings**: ~$42/month (70% reduction)

**Recommendation**: Safe for dev/test, risky for production (can interrupt API/worker).

#### C. Use Smaller Instance Types (Not Recommended)

| Instance Type | vCPU | RAM | Cost/hour | Monthly |
|---------------|------|-----|-----------|---------|
| t3.micro | 2 | 1GB | $0.0104 | $7.59 |
| t3.small | 2 | 2GB | $0.0208 | $15.18 |
| t3.medium | 2 | 4GB | $0.0416 | $30.37 |

**Why t3.medium?**
- Kubernetes system pods use ~1.5GB RAM
- Redis needs ~500MB-1GB
- Worker/API/Sidecar each need ~512MB-1GB
- **Total**: ~3-4GB minimum

**Recommendation**: Stick with t3.medium. Smaller instances will cause OOM errors.

### 4. NAT Gateway ($32-65/month)

NAT Gateway costs:
- **Fixed**: $0.045/hour = $32.85/month per gateway
- **Data transfer**: $0.045/GB
- **Multi-AZ**: $32.85/month per AZ

**Optimization Strategies**:

#### A. Single NAT Gateway (Current Configuration)

```hcl
single_nat_gateway = true  # Use one NAT for all AZs
```

**Savings**: $32.85/month per additional AZ

**Trade-off**: If NAT gateway fails, all private subnets lose internet access.

#### B. Use VPC Endpoints (Already Configured)

VPC endpoints eliminate NAT gateway charges for AWS services:

```hcl
# Already enabled in main.tf
enable_s3_endpoint = true  # Free
```

**Savings**: $0.045/GB for S3 traffic (no NAT gateway data transfer)

#### C. Use Public Subnets (Not Recommended)

Deploy nodes in public subnets to avoid NAT gateway:

**Pros**: Save $32.85/month
**Cons**: Security risk, violates best practices

**Recommendation**: Keep NAT gateway for security.

### 5. EBS Volumes ($8-16/month)

EBS gp3 pricing: $0.08/GB/month

Current usage:
- CPU nodes: 2x 50GB = 100GB = $8/month
- GPU nodes: 1x 100GB = 100GB = $8/month
- **Total**: $16/month

**Optimization Strategies**:

#### A. Reduce Disk Size

```hcl
cpu_node_disk_size = 30  # Reduce from 50GB
gpu_node_disk_size = 80  # Reduce from 100GB
```

**Savings**: $4/month

**Risk**: Disk full errors if models/logs consume space.

#### B. Use gp2 Instead of gp3 (Not Recommended)

gp2 pricing: $0.10/GB/month (25% more expensive than gp3)

**Recommendation**: Stick with gp3.

### 6. CloudWatch Logs ($2-10/month)

CloudWatch Logs pricing:
- **Ingestion**: $0.50/GB
- **Storage**: $0.03/GB/month
- **Typical usage**: 5-10GB/month = $2.50-5.00/month

**Optimization Strategies**:

#### A. Reduce Retention

```hcl
cluster_log_retention_days = 1  # Reduce from 7 days
```

**Savings**: ~$2/month

#### B. Disable Non-Critical Logs

```hcl
cluster_log_types = ["api", "authenticator"]  # Remove audit, controllerManager, scheduler
```

**Savings**: ~50% reduction in log volume

#### C. Disable CloudWatch Logs Completely

```hcl
enable_cloudwatch_logs = false
```

**Savings**: $5/month

**Trade-off**: No centralized logging for troubleshooting.

### 7. Data Transfer (Variable)

AWS charges for data transfer:
- **In**: Free
- **Out to internet**: $0.09/GB (first 10TB/month)
- **Cross-AZ**: $0.01/GB each direction
- **Same-AZ**: Free

**Optimization Strategies**:

#### A. Single AZ Deployment (Current Configuration)

```hcl
availability_zones = ["us-east-1a"]  # Single AZ
```

**Savings**: $0.02/GB for intra-cluster traffic

#### B. Use VPC Endpoints

Already configured for S3. Consider adding for other AWS services:
- **ECR** (Docker images): $0.01/GB + $0.10/hour = ~$73/month
- **CloudWatch**: $0.01/GB + $0.10/hour = ~$73/month

**Recommendation**: Only add if you have high usage of these services.

## Cost Optimization Scenarios

### Scenario 1: Minimal Cost (~$105/month)

**Use case**: Development, intermittent usage

```hcl
# terraform.tfvars
environment = "dev"
availability_zones = ["us-east-1a"]

# CPU nodes
cpu_node_instance_types = ["t3.medium"]
cpu_node_desired_size = 1
cpu_node_min_size = 1
enable_cpu_spot_instances = false  # Better availability

# GPU nodes - disabled
enable_gpu_nodes = false  # Enable manually when needed

# Logging
enable_cloudwatch_logs = true
cluster_log_retention_days = 1
cluster_log_types = ["api", "authenticator"]
```

**Manual GPU enablement**:
```bash
# When you need GPU
terraform apply -var='enable_gpu_nodes=true' -var='gpu_node_desired_size=1'

# When done
terraform apply -var='gpu_node_desired_size=0'
```

**Monthly cost breakdown**:
- EKS control plane: $73
- 1x t3.medium CPU: $30
- NAT Gateway: $33
- EBS (50GB): $4
- **Total: ~$140/month** (without GPU)
- **Add GPU on-demand (8h/day): +$127 = $267/month**
- **Add GPU spot (8h/day): +$38 = $178/month**

### Scenario 2: Aggressive Optimization (~$80/month)

**Use case**: Personal projects, learning, demos

```hcl
# terraform.tfvars
environment = "dev"
availability_zones = ["us-east-1a"]

# CPU nodes - spot
cpu_node_instance_types = ["t3.medium"]
cpu_node_desired_size = 1
cpu_node_min_size = 1
enable_cpu_spot_instances = true  # 70% savings

# GPU nodes - spot, scalable to 0
enable_gpu_nodes = true
gpu_node_desired_size = 0  # Start at 0
gpu_node_min_size = 0
gpu_node_max_size = 1
enable_gpu_spot_instances = true
enable_cluster_autoscaler = true

# Logging - minimal
enable_cloudwatch_logs = false

# S3 - use existing bucket
create_s3_bucket = false
```

**Monthly cost breakdown**:
- EKS control plane: $73
- 1x t3.medium CPU (spot): $9
- NAT Gateway: $33
- EBS (50GB): $4
- **Total: ~$119/month** (GPU at 0)
- **GPU auto-scales when needed (spot): +$0.158/hour**

**Additional savings**:
- Delete cluster on weekends: **-$40/month** (saves ~30% of time)
- Delete cluster entirely when not in use: **-$119/month**

### Scenario 3: Production-Ready (~$550/month)

**Use case**: Production workload, HA required

```hcl
# terraform.tfvars
environment = "prod"
availability_zones = ["us-east-1a", "us-east-1b"]  # Multi-AZ HA

# CPU nodes - on-demand for reliability
cpu_node_instance_types = ["t3.medium"]
cpu_node_desired_size = 3  # HA across 2 AZs + 1 extra
cpu_node_min_size = 2
enable_cpu_spot_instances = false

# GPU nodes - on-demand for reliability
enable_gpu_nodes = true
gpu_node_desired_size = 1
gpu_node_min_size = 1
enable_gpu_spot_instances = false

# NAT - multi-AZ
single_nat_gateway = false

# Security
enable_secrets_encryption = true
```

**Monthly cost breakdown**:
- EKS control plane: $73
- 3x t3.medium CPU: $91
- 1x g4dn.xlarge GPU: $384
- 2x NAT Gateway: $66
- EBS (250GB): $20
- KMS: $1
- Logs: $5
- **Total: ~$640/month**

**Optimization without sacrificing reliability**:
- Use Reserved Instances (1-year): **-30%** = $448/month
- Use Savings Plans (1-year): **-40%** = $384/month
- Use GPU spot with fallback: **-70% on GPU** = $410/month

### Scenario 4: Weekend Delete Strategy (~$260/month)

**Use case**: Business hours usage, delete on weekends

**Strategy**:
1. Deploy cluster Monday morning (15 minutes)
2. Run Monday-Friday (5 days)
3. Destroy cluster Friday evening
4. Repeat weekly

**Cost calculation**:
- Active: 5 days/week = ~22 days/month
- Savings: 8 days/month = ~27% reduction
- Standard cost: $640/month
- **Weekend delete: ~$467/month**

**Automation**:
```bash
# Friday 6 PM (cron job)
0 18 * * 5 cd /path/to/terraform && make destroy -auto-approve

# Monday 6 AM (cron job)
0 6 * * 1 cd /path/to/terraform && make init && make apply -auto-approve
```

**Trade-offs**:
- 15-minute downtime during recreation
- Requires persistent state (S3 backend)
- Kubernetes manifests must be GitOps-managed

## Cost Monitoring and Alerts

### 1. AWS Cost Explorer

View costs by service, tag, or resource:

```bash
# Open Cost Explorer
open https://console.aws.amazon.com/cost-management/home

# Filter by tag
Project = SentinelTranslate
```

### 2. AWS Budgets

Set up budget alerts:

```bash
# Create budget (example: $500/month)
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

**budget.json**:
```json
{
  "BudgetName": "SentinelTranslate-Monthly",
  "BudgetLimit": {
    "Amount": "500",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST",
  "CostFilters": {
    "TagKeyValue": ["user:Project$SentinelTranslate"]
  }
}
```

### 3. Terraform Cost Estimation

Use `terraform output` to see estimated costs:

```bash
make cost

# Output:
eks_control_plane: $73
cpu_nodes: $60.74
gpu_nodes: $384.04
nat_gateway: $32
ebs_storage: $16
total_minimum: $105
total_with_gpu: $565.78
```

### 4. CloudWatch Alarms

Monitor resource usage:

```bash
# High CPU on nodes
aws cloudwatch put-metric-alarm \
  --alarm-name sentineltranslate-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

## Best Practices Summary

### Development/Testing

1. **Use single AZ**: `availability_zones = ["us-east-1a"]`
2. **Enable spot instances**: `enable_gpu_spot_instances = true`
3. **Scale GPU to 0**: `gpu_node_min_size = 0`
4. **Reduce node count**: `cpu_node_desired_size = 1`
5. **Minimal logging**: `cluster_log_retention_days = 1`
6. **Delete when not in use**: `make destroy`

**Estimated cost**: $120-180/month

### Production

1. **Multi-AZ for HA**: `availability_zones = ["us-east-1a", "us-east-1b"]`
2. **On-demand instances**: Disable spot for reliability
3. **Minimum 2 CPU nodes**: `cpu_node_min_size = 2`
4. **Reserved Instances**: Purchase 1-year commitments for 30-40% savings
5. **Monitor costs**: Set up AWS Budgets and alerts
6. **Optimize over time**: Review Cost Explorer monthly

**Estimated cost**: $450-550/month (without Reserved Instances)

## ROI Analysis

### Cost vs. Self-Managed Kubernetes

| Component | EKS Managed | Self-Managed EC2 |
|-----------|-------------|------------------|
| Control Plane | $73/month | $60/month (2x t3.medium HA) |
| Worker Nodes | Same | Same |
| Operations Time | 0 hours | 20 hours/month |
| Updates | Automatic | Manual |
| SLA | 99.95% | 99.5% |

**Break-even**: If your time is worth >$3.50/hour, EKS is cheaper than self-managed.

### Cost vs. ECS Fargate

| Component | EKS | ECS Fargate |
|-----------|-----|-------------|
| Control Plane | $73/month | $0 |
| Compute | $60-500/month | $100-600/month |
| GPU Support | Yes (g4dn) | Limited |
| Kubernetes Features | Full | N/A |

**Recommendation**: Use EKS if you need Kubernetes features or GPU. Use ECS Fargate for simpler workloads.

## Conclusion

**Minimum viable cost**: ~$120/month (dev, GPU disabled)
**Recommended dev cost**: ~$180/month (dev, GPU 8h/day spot)
**Production cost**: ~$450/month (on-demand, HA, Reserved Instances)

**Highest impact optimizations**:
1. GPU scaling to 0 when idle: **-$256/month**
2. GPU spot instances: **-$269/month**
3. Delete cluster when not in use: **-$640/month**
4. Single AZ deployment: **-$33/month** (NAT gateway)
5. Spot CPU instances: **-$42/month**

**Total maximum savings**: ~70% ($450/month) with aggressive optimization
