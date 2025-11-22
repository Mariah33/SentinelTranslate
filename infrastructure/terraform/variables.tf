# Core Configuration Variables

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "sentineltranslate"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1" # Free tier availability
}

# Network Configuration

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for subnet placement. Single AZ for cost optimization."
  type        = list(string)
  default     = ["us-east-1a"] # Change to multiple AZs for production HA
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets (required for EKS). Costs ~$32/month."
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use single NAT gateway for all AZs (cost optimization)"
  type        = bool
  default     = true
}

# EKS Cluster Configuration

variable "cluster_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

variable "cluster_endpoint_public_access" {
  description = "Enable public access to EKS API endpoint"
  type        = bool
  default     = true # Set to false for production, use VPN/bastion
}

variable "cluster_endpoint_private_access" {
  description = "Enable private access to EKS API endpoint"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "CIDR blocks allowed to access public EKS API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"] # Restrict to your IP in production
}

# CPU Node Group Configuration

variable "cpu_node_instance_types" {
  description = "Instance types for CPU node group. t3.medium provides 2 vCPU, 4GB RAM."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "cpu_node_desired_size" {
  description = "Desired number of CPU nodes"
  type        = number
  default     = 2
}

variable "cpu_node_min_size" {
  description = "Minimum number of CPU nodes"
  type        = number
  default     = 1
}

variable "cpu_node_max_size" {
  description = "Maximum number of CPU nodes for autoscaling"
  type        = number
  default     = 4
}

variable "cpu_node_disk_size" {
  description = "Disk size in GB for CPU nodes"
  type        = number
  default     = 50
}

variable "enable_cpu_spot_instances" {
  description = "Use spot instances for CPU nodes (up to 90% cost savings, but can be interrupted)"
  type        = bool
  default     = false # Enable for non-production environments
}

# GPU Node Group Configuration

variable "enable_gpu_nodes" {
  description = "Enable GPU node group for Triton Inference Server. Costs ~$380/month if running 24/7."
  type        = bool
  default     = true
}

variable "gpu_node_instance_types" {
  description = "Instance types for GPU node group. g4dn.xlarge has 1x NVIDIA T4 GPU."
  type        = list(string)
  default     = ["g4dn.xlarge"]
}

variable "gpu_node_desired_size" {
  description = "Desired number of GPU nodes. Set to 0 to save costs when not in use."
  type        = number
  default     = 1
}

variable "gpu_node_min_size" {
  description = "Minimum number of GPU nodes. Set to 0 to allow scaling to zero."
  type        = number
  default     = 0
}

variable "gpu_node_max_size" {
  description = "Maximum number of GPU nodes for autoscaling"
  type        = number
  default     = 2
}

variable "gpu_node_disk_size" {
  description = "Disk size in GB for GPU nodes (needs space for ONNX models)"
  type        = number
  default     = 100
}

variable "enable_gpu_spot_instances" {
  description = "Use spot instances for GPU nodes (up to 70% cost savings). Recommended for dev/test."
  type        = bool
  default     = false # Set to true for cost savings, but risk interruption
}

# Storage Configuration

variable "enable_ebs_csi_driver" {
  description = "Enable EBS CSI driver for persistent volumes (required for Redis)"
  type        = bool
  default     = true
}

variable "enable_efs_csi_driver" {
  description = "Enable EFS CSI driver for shared file storage (optional, not needed for base deployment)"
  type        = bool
  default     = false
}

# S3 Configuration

variable "create_s3_bucket" {
  description = "Create S3 bucket for translation workloads (parquet files)"
  type        = bool
  default     = true
}

variable "s3_bucket_name" {
  description = "Name for S3 bucket. Leave empty to auto-generate based on project name."
  type        = string
  default     = ""
}

variable "s3_bucket_force_destroy" {
  description = "Allow destroying S3 bucket even if it contains objects (dangerous in production)"
  type        = bool
  default     = true # Set to false in production
}

# Monitoring and Logging

variable "enable_cluster_autoscaler" {
  description = "Enable Cluster Autoscaler for automatic node scaling"
  type        = bool
  default     = true
}

variable "enable_metrics_server" {
  description = "Enable Kubernetes Metrics Server for HPA and kubectl top"
  type        = bool
  default     = true
}

variable "enable_cloudwatch_logs" {
  description = "Enable CloudWatch logging for EKS control plane"
  type        = bool
  default     = true
}

variable "cluster_log_types" {
  description = "EKS control plane log types to enable"
  type        = list(string)
  default = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]
}

variable "cluster_log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7 # Reduce to 1 for cost savings
}

# Security Configuration

variable "enable_irsa" {
  description = "Enable IAM Roles for Service Accounts (required for S3 access)"
  type        = bool
  default     = true
}

variable "enable_secrets_encryption" {
  description = "Enable encryption of Kubernetes secrets using AWS KMS"
  type        = bool
  default     = false # Enable for production
}

variable "kms_key_administrators" {
  description = "List of IAM user/role ARNs that can administer KMS key"
  type        = list(string)
  default     = []
}

# Tagging

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default = {
    ManagedBy = "Terraform"
    Project   = "SentinelTranslate"
  }
}

# Advanced Configuration

variable "enable_vpc_flow_logs" {
  description = "Enable VPC flow logs for network monitoring (additional CloudWatch costs)"
  type        = bool
  default     = false # Enable for security auditing
}

variable "enable_pod_security_policy" {
  description = "Enable Pod Security Policy (deprecated in K8s 1.25+, use Pod Security Standards)"
  type        = bool
  default     = false
}

variable "worker_service_account_name" {
  description = "Name for Kubernetes service account used by worker pods"
  type        = string
  default     = "sentineltranslate-worker"
}

variable "api_service_account_name" {
  description = "Name for Kubernetes service account used by API pods"
  type        = string
  default     = "sentineltranslate-api"
}
