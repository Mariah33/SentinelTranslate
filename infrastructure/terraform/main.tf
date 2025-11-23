# SentinelTranslate AWS EKS Infrastructure
#
# This Terraform configuration deploys a production-ready EKS cluster
# optimized for the SentinelTranslate translation pipeline with GPU support.
#
# Architecture:
# - VPC with public/private subnets (single AZ for cost optimization)
# - EKS cluster with managed node groups (CPU + GPU)
# - IAM roles for service accounts (IRSA) for S3 access
# - S3 bucket for translation workloads
# - Security groups for network isolation

# Provider Configuration

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      var.tags,
      {
        Project     = var.project_name
        Environment = var.environment
        Terraform   = "true"
      }
    )
  }
}

# Data Sources

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

# Local Variables

locals {
  name = "${var.project_name}-${var.environment}"

  # S3 bucket name with account ID for global uniqueness
  s3_bucket_name = var.s3_bucket_name != "" ? var.s3_bucket_name : "${var.project_name}-translation-data-${data.aws_caller_identity.current.account_id}"

  # Common tags applied to all resources
  common_tags = merge(
    var.tags,
    {
      Name        = local.name
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  )

  # Node group labels
  cpu_node_labels = {
    "workload-type"           = "general"
    "node.kubernetes.io/role" = "worker"
  }

  gpu_node_labels = {
    "workload-type"           = "gpu"
    "node.kubernetes.io/role" = "gpu-worker"
    "nvidia.com/gpu"          = "true"
  }

  # Node group taints (GPU nodes tainted to prevent non-GPU workloads)
  gpu_node_taints = [
    {
      key    = "nvidia.com/gpu"
      value  = "true"
      effect = "NO_SCHEDULE" # Must be uppercase per AWS EKS requirements
    }
  ]
}

# VPC Module
# Creates VPC with public and private subnets, NAT gateway, and VPC endpoints

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name}-vpc"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = [for k, v in var.availability_zones : cidrsubnet(var.vpc_cidr, 8, k + 10)]
  public_subnets  = [for k, v in var.availability_zones : cidrsubnet(var.vpc_cidr, 8, k)]

  # NAT Gateway configuration (required for private subnets to access internet)
  enable_nat_gateway = var.enable_nat_gateway
  single_nat_gateway = var.single_nat_gateway

  # DNS settings
  enable_dns_hostnames = true
  enable_dns_support   = true

  # VPC Flow Logs (optional, additional costs)
  enable_flow_log                      = var.enable_vpc_flow_logs
  create_flow_log_cloudwatch_iam_role  = var.enable_vpc_flow_logs
  create_flow_log_cloudwatch_log_group = var.enable_vpc_flow_logs

  # Tags required for EKS subnet discovery
  public_subnet_tags = {
    "kubernetes.io/role/elb"                                = "1"
    "kubernetes.io/cluster/${local.name}-eks"               = "shared"
    "karpenter.sh/discovery"                                = local.name
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"                       = "1"
    "kubernetes.io/cluster/${local.name}-eks"               = "shared"
    "karpenter.sh/discovery"                                = local.name
  }

  tags = local.common_tags
}

# S3 VPC Gateway Endpoint
# Free gateway endpoint to avoid NAT gateway charges for S3 traffic
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = concat(
    module.vpc.private_route_table_ids,
    module.vpc.public_route_table_ids
  )

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-s3-endpoint"
    }
  )
}

# EKS Cluster Module
# Creates EKS control plane and managed node groups

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${local.name}-eks"
  cluster_version = var.cluster_version

  # Enable cluster creator admin permissions
  enable_cluster_creator_admin_permissions = true

  # Cluster endpoint access
  cluster_endpoint_public_access       = var.cluster_endpoint_public_access
  cluster_endpoint_private_access      = var.cluster_endpoint_private_access
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs

  # Network configuration
  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.private_subnets

  # IRSA (IAM Roles for Service Accounts)
  enable_irsa = var.enable_irsa

  # Cluster logging
  cluster_enabled_log_types = var.enable_cloudwatch_logs ? var.cluster_log_types : []

  # Cluster addons
  cluster_addons = {
    # CoreDNS for DNS resolution
    coredns = {
      most_recent = true
    }

    # kube-proxy for networking
    kube-proxy = {
      most_recent = true
    }

    # VPC CNI for pod networking
    vpc-cni = {
      most_recent              = true
      before_compute           = true
      service_account_role_arn = module.vpc_cni_irsa.iam_role_arn
      configuration_values = jsonencode({
        env = {
          # Enable prefix delegation for more IPs per node
          ENABLE_PREFIX_DELEGATION = "true"
          WARM_PREFIX_TARGET       = "1"
        }
      })
    }

    # EBS CSI driver for persistent volumes (required for Redis)
    aws-ebs-csi-driver = var.enable_ebs_csi_driver ? {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    } : null

    # EFS CSI driver for shared file storage (optional)
    aws-efs-csi-driver = var.enable_efs_csi_driver ? {
      most_recent = true
    } : null
  }

  # Managed Node Groups
  eks_managed_node_groups = merge(
    # CPU Node Group (always created)
    {
      cpu_nodes = {
        name = "${local.name}-cpu" # Shortened to fit IAM role name_prefix limit

        instance_types = var.cpu_node_instance_types
        capacity_type  = var.enable_cpu_spot_instances ? "SPOT" : "ON_DEMAND"

        min_size     = var.cpu_node_min_size
        max_size     = var.cpu_node_max_size
        desired_size = var.cpu_node_desired_size

        disk_size = var.cpu_node_disk_size
        disk_type = "gp3" # General Purpose SSD (cheaper than gp2)

        labels = local.cpu_node_labels

        # Launch template configuration
        update_config = {
          max_unavailable_percentage = 50
        }

        # Metadata options for IMDSv2 (security best practice)
        metadata_options = {
          http_endpoint               = "enabled"
          http_tokens                 = "required"
          http_put_response_hop_limit = 1
        }

        tags = merge(
          local.common_tags,
          {
            Name = "${local.name}-cpu"
          }
        )
      }
    },

    # GPU Node Group (conditional)
    var.enable_gpu_nodes ? {
      gpu_nodes = {
        name = "${local.name}-gpu" # Shortened to fit IAM role name_prefix limit

        instance_types = var.gpu_node_instance_types
        capacity_type  = var.enable_gpu_spot_instances ? "SPOT" : "ON_DEMAND"

        min_size     = var.gpu_node_min_size
        max_size     = var.gpu_node_max_size
        desired_size = var.gpu_node_desired_size

        disk_size = var.gpu_node_disk_size
        disk_type = "gp3"

        labels = local.gpu_node_labels
        taints = local.gpu_node_taints

        # AMI type with GPU support
        ami_type = "AL2_x86_64_GPU"

        # Pre-bootstrap commands to install NVIDIA drivers
        pre_bootstrap_user_data = <<-EOT
          #!/bin/bash
          # NVIDIA driver installation is handled by AL2_x86_64_GPU AMI
          # Additional GPU optimizations can be added here
        EOT

        update_config = {
          max_unavailable_percentage = 50
        }

        metadata_options = {
          http_endpoint               = "enabled"
          http_tokens                 = "required"
          http_put_response_hop_limit = 1
        }

        tags = merge(
          local.common_tags,
          {
            Name                                          = "${local.name}-gpu"
            "k8s.io/cluster-autoscaler/node-template/label/nvidia.com/gpu" = "true"
          }
        )
      }
    } : {}
  )

  # Node security group rules
  node_security_group_additional_rules = {
    # Allow nodes to communicate with each other
    ingress_self_all = {
      description = "Node to node all ports/protocols"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      type        = "ingress"
      self        = true
    }

    # Allow nodes to receive traffic from ALB
    ingress_alb_http = {
      description              = "ALB to node HTTP"
      protocol                 = "tcp"
      from_port                = 80
      to_port                  = 80
      type                     = "ingress"
      source_security_group_id = aws_security_group.alb.id
    }

    ingress_alb_https = {
      description              = "ALB to node HTTPS"
      protocol                 = "tcp"
      from_port                = 443
      to_port                  = 443
      type                     = "ingress"
      source_security_group_id = aws_security_group.alb.id
    }

    # Allow nodes to reach internet
    egress_all = {
      description      = "Node all egress"
      protocol         = "-1"
      from_port        = 0
      to_port          = 0
      type             = "egress"
      cidr_blocks      = ["0.0.0.0/0"]
      ipv6_cidr_blocks = ["::/0"]
    }
  }

  tags = local.common_tags
}

# VPC CNI IRSA (allows VPC CNI to manage network interfaces)
module "vpc_cni_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name_prefix      = "${local.name}-vpc-cni-"
  attach_vpc_cni_policy = true
  vpc_cni_enable_ipv4   = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-node"]
    }
  }

  tags = local.common_tags
}

# EBS CSI IRSA (allows EBS CSI driver to manage EBS volumes)
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name_prefix      = "${local.name}-ebs-csi-"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }

  tags = local.common_tags
}

# IAM Module for Application Service Accounts
module "iam" {
  source = "./modules/iam"

  project_name = var.project_name
  environment  = var.environment

  cluster_name         = module.eks.cluster_name
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.cluster_oidc_issuer_url

  s3_bucket_arn = var.create_s3_bucket ? aws_s3_bucket.translation_data[0].arn : ""

  worker_service_account_name = var.worker_service_account_name
  api_service_account_name    = var.api_service_account_name

  tags = local.common_tags
}

# Security Group for ALB
resource "aws_security_group" "alb" {
  name_prefix = "${local.name}-alb-"
  description = "Security group for application load balancers"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-alb-sg"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# S3 Bucket for Translation Data
resource "aws_s3_bucket" "translation_data" {
  count = var.create_s3_bucket ? 1 : 0

  bucket        = local.s3_bucket_name
  force_destroy = var.s3_bucket_force_destroy

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-translation-data"
    }
  )
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "translation_data" {
  count = var.create_s3_bucket ? 1 : 0

  bucket = aws_s3_bucket.translation_data[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "translation_data" {
  count = var.create_s3_bucket ? 1 : 0

  bucket = aws_s3_bucket.translation_data[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "translation_data" {
  count = var.create_s3_bucket ? 1 : 0

  bucket = aws_s3_bucket.translation_data[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket Lifecycle Rules (optional cost optimization)
resource "aws_s3_bucket_lifecycle_configuration" "translation_data" {
  count = var.create_s3_bucket ? 1 : 0

  bucket = aws_s3_bucket.translation_data[0].id

  rule {
    id     = "archive-old-translations"
    status = "Enabled"

    filter {} # Apply to all objects in the bucket

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = 365
    }
  }

  rule {
    id     = "cleanup-incomplete-uploads"
    status = "Enabled"

    filter {} # Apply to all objects in the bucket

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# CloudWatch Log Group for EKS
resource "aws_cloudwatch_log_group" "eks_cluster" {
  count = var.enable_cloudwatch_logs ? 1 : 0

  name              = "/aws/eks/${local.name}-eks/cluster"
  retention_in_days = var.cluster_log_retention_days

  tags = local.common_tags
}

# Kubernetes Provider Configuration
# This allows Terraform to manage Kubernetes resources (service accounts, etc.)

data "aws_eks_cluster_auth" "cluster" {
  name = module.eks.cluster_name
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.cluster.token
}

# Create Kubernetes Service Accounts with IRSA annotations
resource "kubernetes_service_account" "worker" {
  metadata {
    name      = var.worker_service_account_name
    namespace = "default"
    annotations = {
      "eks.amazonaws.com/role-arn" = module.iam.s3_access_role_arn
    }
  }

  depends_on = [module.eks]
}

resource "kubernetes_service_account" "api" {
  metadata {
    name      = var.api_service_account_name
    namespace = "default"
    annotations = {
      "eks.amazonaws.com/role-arn" = module.iam.s3_access_role_arn
    }
  }

  depends_on = [module.eks]
}

# Install Cluster Autoscaler (optional)
# This enables automatic scaling of node groups based on pod resource requests

resource "kubernetes_service_account" "cluster_autoscaler" {
  count = var.enable_cluster_autoscaler ? 1 : 0

  metadata {
    name      = "cluster-autoscaler"
    namespace = "kube-system"
    annotations = {
      "eks.amazonaws.com/role-arn" = module.cluster_autoscaler_irsa[0].iam_role_arn
    }
  }

  depends_on = [module.eks]
}

module "cluster_autoscaler_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  count = var.enable_cluster_autoscaler ? 1 : 0

  role_name_prefix                 = "${local.name}-cluster-autoscaler-"
  attach_cluster_autoscaler_policy = true
  cluster_autoscaler_cluster_names = [module.eks.cluster_name]

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:cluster-autoscaler"]
    }
  }

  tags = local.common_tags
}
