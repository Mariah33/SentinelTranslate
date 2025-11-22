# VPC Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnet_ids" {
  description = "Private subnet IDs where EKS nodes run"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs for load balancers"
  value       = module.vpc.public_subnets
}

# EKS Cluster Outputs

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_id" {
  description = "EKS cluster ID"
  value       = module.eks.cluster_id
}

output "cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "EKS cluster Kubernetes version"
  value       = module.eks.cluster_version
}

output "cluster_security_group_id" {
  description = "Security group ID attached to EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data for cluster authentication"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for IRSA"
  value       = module.eks.cluster_oidc_issuer_url
}

output "oidc_provider_arn" {
  description = "ARN of OIDC provider for IRSA"
  value       = module.eks.oidc_provider_arn
}

# Node Group Outputs

output "cpu_node_group_id" {
  description = "CPU node group ID"
  value       = module.eks.eks_managed_node_groups["cpu_nodes"].node_group_id
}

output "cpu_node_group_arn" {
  description = "CPU node group ARN"
  value       = module.eks.eks_managed_node_groups["cpu_nodes"].node_group_arn
}

output "cpu_node_group_status" {
  description = "CPU node group status"
  value       = module.eks.eks_managed_node_groups["cpu_nodes"].node_group_status
}

output "gpu_node_group_id" {
  description = "GPU node group ID (if enabled)"
  value       = var.enable_gpu_nodes ? module.eks.eks_managed_node_groups["gpu_nodes"].node_group_id : null
}

output "gpu_node_group_arn" {
  description = "GPU node group ARN (if enabled)"
  value       = var.enable_gpu_nodes ? module.eks.eks_managed_node_groups["gpu_nodes"].node_group_arn : null
}

output "gpu_node_group_status" {
  description = "GPU node group status (if enabled)"
  value       = var.enable_gpu_nodes ? module.eks.eks_managed_node_groups["gpu_nodes"].node_group_status : null
}

# IAM Outputs

output "cluster_iam_role_arn" {
  description = "IAM role ARN for EKS cluster"
  value       = module.eks.cluster_iam_role_arn
}

output "node_iam_role_arn" {
  description = "IAM role ARN for EKS nodes"
  value       = module.eks.eks_managed_node_groups["cpu_nodes"].iam_role_arn
}

output "s3_access_role_arn" {
  description = "IAM role ARN for S3 access (IRSA)"
  value       = module.iam.s3_access_role_arn
}

output "s3_access_role_name" {
  description = "IAM role name for S3 access (IRSA)"
  value       = module.iam.s3_access_role_name
}

output "worker_service_account_name" {
  description = "Kubernetes service account name for worker pods"
  value       = var.worker_service_account_name
}

output "api_service_account_name" {
  description = "Kubernetes service account name for API pods"
  value       = var.api_service_account_name
}

# S3 Outputs

output "s3_bucket_name" {
  description = "S3 bucket name for translation workloads"
  value       = var.create_s3_bucket ? aws_s3_bucket.translation_data[0].id : null
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = var.create_s3_bucket ? aws_s3_bucket.translation_data[0].arn : null
}

output "s3_bucket_region" {
  description = "S3 bucket region"
  value       = var.create_s3_bucket ? aws_s3_bucket.translation_data[0].region : null
}

# Regional Outputs

output "region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "availability_zones" {
  description = "Availability zones in use"
  value       = var.availability_zones
}

# kubectl Configuration Command

output "configure_kubectl_command" {
  description = "Command to configure kubectl for this cluster"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

# Kubeconfig Output (for automation)

output "kubeconfig" {
  description = "Kubeconfig content for programmatic access"
  value       = <<-EOT
    apiVersion: v1
    kind: Config
    clusters:
    - cluster:
        certificate-authority-data: ${module.eks.cluster_certificate_authority_data}
        server: ${module.eks.cluster_endpoint}
      name: ${module.eks.cluster_name}
    contexts:
    - context:
        cluster: ${module.eks.cluster_name}
        user: ${module.eks.cluster_name}
      name: ${module.eks.cluster_name}
    current-context: ${module.eks.cluster_name}
    users:
    - name: ${module.eks.cluster_name}
      user:
        exec:
          apiVersion: client.authentication.k8s.io/v1beta1
          command: aws
          args:
            - eks
            - get-token
            - --cluster-name
            - ${module.eks.cluster_name}
            - --region
            - ${var.aws_region}
  EOT
  sensitive   = true
}

# Service Account Annotations (for Kubernetes manifests)

output "worker_service_account_annotation" {
  description = "Annotation to add to worker service account for IRSA"
  value = {
    "eks.amazonaws.com/role-arn" = module.iam.s3_access_role_arn
  }
}

output "api_service_account_annotation" {
  description = "Annotation to add to API service account for IRSA"
  value = {
    "eks.amazonaws.com/role-arn" = module.iam.s3_access_role_arn
  }
}

# Cost Estimation

output "estimated_monthly_cost_usd" {
  description = "Estimated monthly cost in USD (approximate)"
  value = {
    eks_control_plane = 73
    cpu_nodes         = var.cpu_node_desired_size * 30 * 0.0416 # t3.medium hourly rate
    gpu_nodes         = var.enable_gpu_nodes ? var.gpu_node_desired_size * 730 * 0.526 : 0 # g4dn.xlarge on-demand
    nat_gateway       = var.enable_nat_gateway ? (var.single_nat_gateway ? 32 : 32 * length(var.availability_zones)) : 0
    ebs_storage       = (var.cpu_node_desired_size * var.cpu_node_disk_size + (var.enable_gpu_nodes ? var.gpu_node_desired_size * var.gpu_node_disk_size : 0)) * 0.08 # gp3 pricing
    total_minimum     = 73 + (var.cpu_node_min_size * 30 * 0.0416) + (var.enable_nat_gateway ? 32 : 0) + ((var.cpu_node_min_size * var.cpu_node_disk_size) * 0.08)
    total_with_gpu    = 73 + (var.cpu_node_desired_size * 30 * 0.0416) + (var.enable_gpu_nodes ? var.gpu_node_desired_size * 730 * 0.526 : 0) + (var.enable_nat_gateway ? 32 : 0) + ((var.cpu_node_desired_size * var.cpu_node_disk_size + (var.enable_gpu_nodes ? var.gpu_node_desired_size * var.gpu_node_disk_size : 0)) * 0.08)
  }
}

# Deployment Summary

output "deployment_summary" {
  description = "Summary of deployed infrastructure"
  value = {
    project_name        = var.project_name
    environment         = var.environment
    cluster_name        = module.eks.cluster_name
    cluster_version     = module.eks.cluster_version
    region              = var.aws_region
    availability_zones  = var.availability_zones
    cpu_node_count      = var.cpu_node_desired_size
    cpu_instance_type   = var.cpu_node_instance_types[0]
    gpu_enabled         = var.enable_gpu_nodes
    gpu_node_count      = var.enable_gpu_nodes ? var.gpu_node_desired_size : 0
    gpu_instance_type   = var.enable_gpu_nodes ? var.gpu_node_instance_types[0] : "N/A"
    s3_bucket_created   = var.create_s3_bucket
    irsa_enabled        = var.enable_irsa
    autoscaler_enabled  = var.enable_cluster_autoscaler
  }
}
