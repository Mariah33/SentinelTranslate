# IAM Module for SentinelTranslate
#
# Creates IAM roles and policies for:
# - Worker pods (S3 access for parquet files)
# - API pods (S3 access for translation workloads)
# - Uses IRSA (IAM Roles for Service Accounts) for secure pod-level permissions

# Data source to get current AWS account info
data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

# IAM Role for S3 Access (used by worker and API pods via IRSA)
resource "aws_iam_role" "s3_access" {
  name_prefix = "${var.project_name}-${var.environment}-s3-access-"
  description = "IAM role for SentinelTranslate pods to access S3 buckets"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(var.oidc_provider_url, "https://", "")}:sub" = [
              "system:serviceaccount:default:${var.worker_service_account_name}",
              "system:serviceaccount:default:${var.api_service_account_name}"
            ]
            "${replace(var.oidc_provider_url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for S3 Access
resource "aws_iam_policy" "s3_access" {
  name_prefix = "${var.project_name}-${var.environment}-s3-access-"
  description = "Policy allowing read/write access to translation S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = var.s3_bucket_arn != "" ? [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ] : ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:GetBucketLocation"
        ]
        Resource = "*"
      }
    ]
  })

  tags = var.tags
}

# Attach S3 policy to S3 access role
resource "aws_iam_role_policy_attachment" "s3_access" {
  role       = aws_iam_role.s3_access.name
  policy_arn = aws_iam_policy.s3_access.arn
}

# Additional IAM Policy for CloudWatch Logs (optional, for pod logging)
resource "aws_iam_policy" "cloudwatch_logs" {
  count = var.enable_cloudwatch_logs ? 1 : 0

  name_prefix = "${var.project_name}-${var.environment}-cloudwatch-logs-"
  description = "Policy allowing pods to write to CloudWatch Logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:${data.aws_partition.current.partition}:logs:*:${data.aws_caller_identity.current.account_id}:log-group:/aws/eks/${var.cluster_name}/*"
      }
    ]
  })

  tags = var.tags
}

# Attach CloudWatch Logs policy to S3 access role
resource "aws_iam_role_policy_attachment" "cloudwatch_logs" {
  count = var.enable_cloudwatch_logs ? 1 : 0

  role       = aws_iam_role.s3_access.name
  policy_arn = aws_iam_policy.cloudwatch_logs[0].arn
}
