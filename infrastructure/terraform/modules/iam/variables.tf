variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the OIDC provider for the EKS cluster"
  type        = string
}

variable "oidc_provider_url" {
  description = "URL of the OIDC provider for the EKS cluster"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket for translation data"
  type        = string
  default     = ""
}

variable "worker_service_account_name" {
  description = "Name of the Kubernetes service account for worker pods"
  type        = string
}

variable "api_service_account_name" {
  description = "Name of the Kubernetes service account for API pods"
  type        = string
}

variable "enable_cloudwatch_logs" {
  description = "Enable CloudWatch Logs access for pods"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
