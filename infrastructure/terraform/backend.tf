# Terraform state backend configuration
#
# IMPORTANT: Before running terraform init, create the S3 bucket and DynamoDB table:
#
# 1. Create S3 bucket:
#    aws s3 mb s3://sentineltranslate-terraform-state-$(aws sts get-caller-identity --query Account --output text)
#    aws s3api put-bucket-versioning \
#      --bucket sentineltranslate-terraform-state-$(aws sts get-caller-identity --query Account --output text) \
#      --versioning-configuration Status=Enabled
#
# 2. Create DynamoDB table:
#    aws dynamodb create-table \
#      --table-name sentineltranslate-terraform-locks \
#      --attribute-definitions AttributeName=LockID,AttributeType=S \
#      --key-schema AttributeName=LockID,KeyType=HASH \
#      --billing-mode PAY_PER_REQUEST

terraform {
  backend "s3" {
    # Update this bucket name with your AWS account ID
    # Format: sentineltranslate-terraform-state-<account-id>
    bucket = "sentineltranslate-terraform-state"

    key            = "eks/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "sentineltranslate-terraform-locks"

    # Optional: Enable additional security features
    # kms_key_id = "arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID"
  }
}

# Alternative: Local backend for testing (comment out S3 backend above)
# terraform {
#   backend "local" {
#     path = "terraform.tfstate"
#   }
# }
