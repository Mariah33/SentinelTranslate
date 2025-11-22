# SentinelTranslate AWS Architecture

This document describes the AWS infrastructure architecture for SentinelTranslate deployed on EKS.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AWS Account                                 │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        VPC (10.0.0.0/16)                           │ │
│  │                                                                    │ │
│  │  ┌──────────────────────┐      ┌──────────────────────┐          │ │
│  │  │  Public Subnet       │      │  Private Subnet      │          │ │
│  │  │  (10.0.1.0/24)       │      │  (10.0.11.0/24)      │          │ │
│  │  │                      │      │                      │          │ │
│  │  │  ┌────────────────┐  │      │  ┌────────────────┐ │          │ │
│  │  │  │ Internet       │  │      │  │ EKS Control    │ │          │ │
│  │  │  │ Gateway        │  │      │  │ Plane          │ │          │ │
│  │  │  └────────────────┘  │      │  └────────────────┘ │          │ │
│  │  │                      │      │                      │          │ │
│  │  │  ┌────────────────┐  │      │  ┌────────────────┐ │          │ │
│  │  │  │ NAT Gateway    │──┼──────┼─>│ Worker Nodes   │ │          │ │
│  │  │  │ (Elastic IP)   │  │      │  │                │ │          │ │
│  │  │  └────────────────┘  │      │  │ CPU: t3.medium │ │          │ │
│  │  │                      │      │  │ GPU: g4dn.xl   │ │          │ │
│  │  │  ┌────────────────┐  │      │  └────────────────┘ │          │ │
│  │  │  │ Application    │  │      │                      │          │ │
│  │  │  │ Load Balancer  │──┼──────┼──> Services         │          │ │
│  │  │  └────────────────┘  │      │                      │          │ │
│  │  └──────────────────────┘      └──────────────────────┘          │ │
│  │                                                                    │ │
│  │  VPC Endpoints:                                                   │ │
│  │  └─> S3 (Gateway Endpoint - Free)                                │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        IAM (Identity & Access)                     │ │
│  │                                                                    │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐│ │
│  │  │ Cluster Role     │  │ Node Role        │  │ IRSA Roles       ││ │
│  │  │ (EKS Control)    │  │ (EC2 Instances)  │  │ (Service Accts)  ││ │
│  │  │                  │  │                  │  │                  ││ │
│  │  │ - EKS Policies   │  │ - EKS Worker     │  │ - S3 Access      ││ │
│  │  │ - CloudWatch     │  │ - ECR Pull       │  │ - CloudWatch     ││ │
│  │  │                  │  │ - VPC CNI        │  │                  ││ │
│  │  └──────────────────┘  │ - EBS CSI        │  └──────────────────┘│ │
│  │                        └──────────────────┘                       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        Storage & Data                              │ │
│  │                                                                    │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐│ │
│  │  │ S3 Bucket        │  │ EBS Volumes      │  │ ECR (Images)     ││ │
│  │  │                  │  │                  │  │                  ││ │
│  │  │ - Parquet files  │  │ - Redis data     │  │ - API image      ││ │
│  │  │ - Translation    │  │ - Logs           │  │ - Sidecar image  ││ │
│  │  │   workloads      │  │ - Models (GPU)   │  │ - Worker image   ││ │
│  │  │                  │  │                  │  │ - Triton image   ││ │
│  │  │ Encryption: AES  │  │ Encryption: KMS  │  │                  ││ │
│  │  │ Versioning: Yes  │  │ Type: gp3        │  │                  ││ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘│ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    Monitoring & Logging                            │ │
│  │                                                                    │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐│ │
│  │  │ CloudWatch Logs  │  │ CloudWatch       │  │ Cost Explorer    ││ │
│  │  │                  │  │ Metrics          │  │                  ││ │
│  │  │ - EKS Control    │  │ - CPU/Memory     │  │ - Cost tracking  ││ │
│  │  │ - Application    │  │ - Network        │  │ - Budget alerts  ││ │
│  │  │                  │  │ - GPU usage      │  │                  ││ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘│ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## EKS Cluster Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       EKS Cluster (Kubernetes 1.28)                      │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        Control Plane (Managed)                     │ │
│  │                                                                    │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │ │
│  │  │ API Server   │  │ etcd         │  │ Scheduler    │            │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘            │ │
│  │  ┌──────────────┐  ┌──────────────┐                              │ │
│  │  │ Controller   │  │ Cloud        │                              │ │
│  │  │ Manager      │  │ Manager      │                              │ │
│  │  └──────────────┘  └──────────────┘                              │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        Node Groups                                 │ │
│  │                                                                    │ │
│  │  ┌────────────────────────────────────────────────────────────┐   │ │
│  │  │ CPU Node Group (Auto Scaling: 1-4 nodes)                  │   │ │
│  │  │                                                            │   │ │
│  │  │  Instance: t3.medium (2 vCPU, 4GB RAM)                    │   │ │
│  │  │  Disk: 50GB gp3                                           │   │ │
│  │  │  Labels: workload-type=general                            │   │ │
│  │  │                                                            │   │ │
│  │  │  Pods:                                                     │   │ │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │   │ │
│  │  │  │ API      │ │ Sidecar  │ │ Worker   │ │ Redis    │    │   │ │
│  │  │  │ (Port    │ │ (Port    │ │ (Celery) │ │ (Port    │    │   │ │
│  │  │  │  8090)   │ │  8080)   │ │          │ │  6379)   │    │   │ │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │   │ │
│  │  │                                                            │   │ │
│  │  │  System Pods:                                             │   │ │
│  │  │  - kube-proxy, aws-node (VPC CNI), ebs-csi-controller    │   │ │
│  │  └────────────────────────────────────────────────────────────┘   │ │
│  │                                                                    │ │
│  │  ┌────────────────────────────────────────────────────────────┐   │ │
│  │  │ GPU Node Group (Auto Scaling: 0-2 nodes)                  │   │ │
│  │  │                                                            │   │ │
│  │  │  Instance: g4dn.xlarge (4 vCPU, 16GB RAM, 1x T4 GPU)     │   │ │
│  │  │  Disk: 100GB gp3                                          │   │ │
│  │  │  Labels: workload-type=gpu, nvidia.com/gpu=true          │   │ │
│  │  │  Taints: nvidia.com/gpu=true:NoSchedule                  │   │ │
│  │  │                                                            │   │ │
│  │  │  Pods:                                                     │   │ │
│  │  │  ┌────────────────────────────────────────────┐           │   │ │
│  │  │  │ Triton Inference Server                    │           │   │ │
│  │  │  │                                             │           │   │ │
│  │  │  │ - HTTP: 8000 (Inference API)               │           │   │ │
│  │  │  │ - gRPC: 8001 (High-performance inference)  │           │   │ │
│  │  │  │ - Metrics: 8002 (Prometheus metrics)       │           │   │ │
│  │  │  │                                             │           │   │ │
│  │  │  │ Resources:                                  │           │   │ │
│  │  │  │ - nvidia.com/gpu: 1                         │           │   │ │
│  │  │  │ - Memory: 8Gi                               │           │   │ │
│  │  │  └────────────────────────────────────────────┘           │   │ │
│  │  │                                                            │   │ │
│  │  │  System Pods:                                             │   │ │
│  │  │  - nvidia-device-plugin (GPU discovery)                   │   │ │
│  │  └────────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        Cluster Addons                              │ │
│  │                                                                    │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐│ │
│  │  │ CoreDNS          │  │ VPC CNI          │  │ kube-proxy       ││ │
│  │  │ (DNS resolution) │  │ (Pod networking) │  │ (Service proxy)  ││ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘│ │
│  │                                                                    │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐│ │
│  │  │ EBS CSI Driver   │  │ Cluster          │  │ Metrics Server   ││ │
│  │  │ (Volumes)        │  │ Autoscaler       │  │ (HPA/kubectl top)││ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘│ │
│  │                                                                    │ │
│  │  ┌──────────────────┐  ┌──────────────────┐                      │ │
│  │  │ AWS LB           │  │ NVIDIA Device    │                      │ │
│  │  │ Controller       │  │ Plugin           │                      │ │
│  │  └──────────────────┘  └──────────────────┘                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Application Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Translation Request Flow                           │
└─────────────────────────────────────────────────────────────────────────┘

1. Batch Translation (via API):

   Client → ALB → API Pod → S3 Bucket (read parquet)
                   ↓
                   Create Celery tasks
                   ↓
                   Redis (queue tasks)
                   ↓
   Worker Pod ← Redis (consume tasks)
      ↓
      Process sentence-by-sentence:
      ↓
   Triton Pod (GPU inference)
      ↓
   Hallucination detection
      ↓
   Fallback if needed (truncate + retry)
      ↓
   Worker Pod → Redis (store result)
      ↓
   Client ← API Pod ← Redis (retrieve result)

2. Single-Text Translation (via Sidecar):

   Client → ALB → Sidecar Pod → Create Celery task
                                 ↓
                                 Redis (queue)
                                 ↓
   Same as above (Worker → Triton → Redis → Sidecar → Client)

3. Direct Inference (Triton only):

   Worker/Sidecar → Triton HTTP (port 8000)
                     ↓
                     ONNX Model (opus-mt-{lang}-en)
                     ↓
                     GPU Inference (NVIDIA T4)
                     ↓
                     Return translation
```

## Network Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Network Traffic Flow                            │
└─────────────────────────────────────────────────────────────────────────┘

Internet Traffic:
  Client (HTTPS) → ALB (Public Subnet) → Pods (Private Subnet)
                      ↓
                   Security Group Rules:
                   - ALB: Allow 80/443 from 0.0.0.0/0
                   - Nodes: Allow 80/443 from ALB SG
                   - Nodes: Allow all from Nodes SG (inter-pod)

Outbound Traffic (Private Subnet → Internet):
  Pods → NAT Gateway (Public Subnet) → Internet Gateway → Internet
         ↓
      Examples:
      - Pull Docker images from ECR
      - Access external APIs
      - Download models

AWS Service Traffic (No NAT charges):
  Pods → VPC Endpoint (S3) → S3 Service
         ↓
      Free data transfer for S3

EKS Control Plane Traffic:
  Nodes ↔ EKS Control Plane (AWS-managed networking)
         ↓
      - kubelet → API Server
      - API Server → Webhooks
      - Logs → CloudWatch
```

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Security Layers                                 │
└─────────────────────────────────────────────────────────────────────────┘

Layer 1: Network Security
  ┌────────────────────────────────────────────────────────────┐
  │ VPC Security Groups                                        │
  │ - EKS Cluster SG: Control plane ↔ Nodes                  │
  │ - Node SG: Allow inter-node, ALB → Nodes                 │
  │ - ALB SG: Allow 80/443 from internet                     │
  └────────────────────────────────────────────────────────────┘

Layer 2: IAM Security
  ┌────────────────────────────────────────────────────────────┐
  │ IAM Roles (IRSA - IAM Roles for Service Accounts)        │
  │                                                            │
  │ Worker Service Account:                                   │
  │ - AssumeRoleWithWebIdentity (OIDC)                       │
  │ - S3 Read/Write (translation bucket only)                │
  │ - CloudWatch Logs Write                                   │
  │                                                            │
  │ API Service Account:                                       │
  │ - Same permissions as Worker                              │
  │                                                            │
  │ Node IAM Role:                                            │
  │ - EKS Worker Node Policy                                  │
  │ - ECR Read Only                                           │
  │ - VPC CNI Policy                                          │
  │ - EBS CSI Driver Policy                                   │
  └────────────────────────────────────────────────────────────┘

Layer 3: Kubernetes Security
  ┌────────────────────────────────────────────────────────────┐
  │ RBAC (Role-Based Access Control)                          │
  │ - Service accounts with minimal permissions               │
  │ - No cluster-admin for application pods                   │
  │                                                            │
  │ Pod Security:                                              │
  │ - Run as non-root user (where possible)                   │
  │ - Read-only root filesystem                               │
  │ - Resource limits enforced                                │
  │ - Security context constraints                            │
  └────────────────────────────────────────────────────────────┘

Layer 4: Data Security
  ┌────────────────────────────────────────────────────────────┐
  │ Encryption at Rest:                                        │
  │ - S3 Bucket: AES-256 encryption                           │
  │ - EBS Volumes: KMS encryption (optional)                  │
  │ - Kubernetes Secrets: KMS encryption (optional)           │
  │                                                            │
  │ Encryption in Transit:                                     │
  │ - ALB → Pods: HTTPS/TLS                                   │
  │ - Pods → S3: HTTPS                                        │
  │ - Pods → Pods: Network policies (optional)                │
  └────────────────────────────────────────────────────────────┘

Layer 5: Compliance & Auditing
  ┌────────────────────────────────────────────────────────────┐
  │ CloudTrail:                                                │
  │ - All API calls logged                                     │
  │ - IAM, EKS, EC2, S3 activity tracked                      │
  │                                                            │
  │ EKS Control Plane Logs:                                    │
  │ - API server audit logs                                    │
  │ - Authenticator logs                                       │
  │ - Controller manager logs                                  │
  │                                                            │
  │ VPC Flow Logs (optional):                                  │
  │ - Network traffic monitoring                               │
  └────────────────────────────────────────────────────────────┘
```

## Disaster Recovery Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Backup & Recovery Strategy                          │
└─────────────────────────────────────────────────────────────────────────┘

State Management:
  ┌────────────────────────────────────────────────────────────┐
  │ Terraform State:                                           │
  │ - Stored in S3 (versioned)                                │
  │ - Locked with DynamoDB                                     │
  │ - Encrypted with AES-256                                  │
  │                                                            │
  │ Recovery: Point-in-time restore from S3 versions          │
  └────────────────────────────────────────────────────────────┘

Data Backup:
  ┌────────────────────────────────────────────────────────────┐
  │ S3 Bucket:                                                 │
  │ - Versioning enabled                                       │
  │ - Lifecycle rules: Archive to Glacier after 90 days       │
  │ - Cross-region replication (optional)                     │
  │                                                            │
  │ EBS Volumes:                                               │
  │ - Automated snapshots (AWS Backup)                         │
  │ - Retention: 7 days (configurable)                        │
  │                                                            │
  │ Redis Data:                                                │
  │ - Ephemeral (task queue/results only)                     │
  │ - No backup needed (stateless)                            │
  └────────────────────────────────────────────────────────────┘

Infrastructure Recovery:
  ┌────────────────────────────────────────────────────────────┐
  │ RTO (Recovery Time Objective): 30 minutes                 │
  │ - Run: terraform apply                                     │
  │ - Duration: ~20 minutes for EKS cluster creation          │
  │                                                            │
  │ RPO (Recovery Point Objective): <1 hour                   │
  │ - Terraform state: Real-time (S3 versioning)              │
  │ - Application code: Git commits                            │
  │ - Data: S3 versioning + lifecycle policies                │
  └────────────────────────────────────────────────────────────┘
```

## Scaling Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Auto-Scaling Strategy                           │
└─────────────────────────────────────────────────────────────────────────┘

Node-Level Scaling (Cluster Autoscaler):
  ┌────────────────────────────────────────────────────────────┐
  │ CPU Node Group:                                            │
  │ - Min: 1 node                                             │
  │ - Desired: 2 nodes                                         │
  │ - Max: 4 nodes                                            │
  │ - Scale up: When pods are pending due to insufficient     │
  │             CPU/memory                                     │
  │ - Scale down: After 10 min of node underutilization      │
  │                                                            │
  │ GPU Node Group:                                            │
  │ - Min: 0 nodes (cost optimization)                        │
  │ - Desired: 1 node                                          │
  │ - Max: 2 nodes                                            │
  │ - Scale up: When Triton pod is pending                    │
  │ - Scale down: 10 min after last GPU pod deleted           │
  └────────────────────────────────────────────────────────────┘

Pod-Level Scaling (Horizontal Pod Autoscaler):
  ┌────────────────────────────────────────────────────────────┐
  │ Worker Pods:                                               │
  │ - Min: 2 replicas                                         │
  │ - Max: 10 replicas                                        │
  │ - Metric: CPU > 70% or queue depth > 100                  │
  │                                                            │
  │ API Pods:                                                  │
  │ - Min: 2 replicas (HA)                                    │
  │ - Max: 5 replicas                                         │
  │ - Metric: CPU > 80% or requests/sec > 100                 │
  │                                                            │
  │ Triton Pods:                                               │
  │ - Fixed: 1 replica (GPU limitation)                       │
  │ - Scaling: Use multiple GPU nodes for scale               │
  └────────────────────────────────────────────────────────────┘
```

## Key Architectural Decisions

### 1. Single AZ vs Multi-AZ

**Decision**: Single AZ for development, Multi-AZ for production

**Rationale**:
- **Cost**: Single AZ saves $33/month (NAT gateway) + cross-AZ data transfer
- **Availability**: Multi-AZ provides 99.95% SLA vs 99.5% single AZ
- **Use case**: Development/test acceptable with single AZ downtime risk

### 2. Managed Node Groups vs Self-Managed

**Decision**: Use EKS Managed Node Groups

**Rationale**:
- **Automation**: Automatic node updates, patching, and lifecycle management
- **Integration**: Native integration with Cluster Autoscaler
- **Cost**: No additional cost vs self-managed
- **Operations**: Reduced operational overhead

### 3. GPU Node Scaling to Zero

**Decision**: Enable GPU node scaling to 0 replicas

**Rationale**:
- **Cost**: Save $384/month when GPU idle (70% of time for dev/test)
- **Startup**: 2-5 minute delay acceptable for batch workloads
- **Trade-off**: Not suitable for real-time inference (use min=1 for production)

### 4. VPC Endpoints for S3

**Decision**: Use S3 Gateway VPC Endpoint

**Rationale**:
- **Cost**: Free (no NAT gateway charges for S3 traffic)
- **Performance**: Lower latency than NAT gateway routing
- **Scale**: No bandwidth limitations

### 5. IRSA vs Instance Profiles

**Decision**: Use IRSA (IAM Roles for Service Accounts)

**Rationale**:
- **Security**: Pod-level permissions vs node-level
- **Least privilege**: Each service account has minimal required permissions
- **Audit**: CloudTrail logs show which pod made which API call

### 6. gp3 vs gp2 EBS Volumes

**Decision**: Use gp3 for all EBS volumes

**Rationale**:
- **Cost**: 20% cheaper than gp2 ($0.08/GB vs $0.10/GB)
- **Performance**: Baseline 3000 IOPS vs gp2's variable based on size
- **Predictable**: No performance degradation with smaller volumes

### 7. Spot vs On-Demand Instances

**Decision**: Offer both via configuration

**Rationale**:
- **Dev/Test**: Spot instances save 70%, interruptions acceptable
- **Production**: On-demand for reliability, consider Savings Plans for 40% discount
- **Flexibility**: User chooses based on workload requirements

## Resource Naming Convention

```
Format: {project}-{environment}-{resource-type}-{identifier}

Examples:
- VPC: sentineltranslate-dev-vpc
- EKS Cluster: sentineltranslate-dev-eks
- Node Group: sentineltranslate-dev-cpu-nodes
- S3 Bucket: sentineltranslate-translation-data-123456789012
- IAM Role: sentineltranslate-dev-s3-access-role
- Service Account: sentineltranslate-worker
```

## Tags Strategy

All resources are tagged with:
```
Project: SentinelTranslate
Environment: dev/staging/prod
ManagedBy: Terraform
Component: vpc/eks/iam/storage
CostCenter: engineering
Owner: platform-team
```

This enables:
- Cost allocation by project/environment
- Resource filtering in AWS Console
- Compliance reporting
- Automated lifecycle management

## Related Documentation

- **Deployment**: See `DEPLOYMENT.md` for step-by-step deployment guide
- **Cost Optimization**: See `COST_OPTIMIZATION.md` for detailed cost strategies
- **Quick Start**: See `QUICKSTART.md` for 30-minute setup
- **Operations**: See `README.md` for ongoing operations
