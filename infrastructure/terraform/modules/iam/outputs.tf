output "s3_access_role_arn" {
  description = "ARN of the IAM role for S3 access (IRSA)"
  value       = aws_iam_role.s3_access.arn
}

output "s3_access_role_name" {
  description = "Name of the IAM role for S3 access"
  value       = aws_iam_role.s3_access.name
}

output "s3_access_policy_arn" {
  description = "ARN of the S3 access policy"
  value       = aws_iam_policy.s3_access.arn
}

output "cloudwatch_logs_policy_arn" {
  description = "ARN of the CloudWatch Logs policy (if enabled)"
  value       = var.enable_cloudwatch_logs ? aws_iam_policy.cloudwatch_logs[0].arn : null
}
