#!/bin/bash
set -e

# Push locally built Docker images to AWS ECR
# This script assumes images are already built locally using make build
#
# Required environment variables:
#   AWS_ACCESS_KEY_ID      - AWS access key
#   AWS_SECRET_ACCESS_KEY  - AWS secret key
#   AWS_REGION (optional)  - AWS region (default: us-east-1)
#
# Usage:
#   source .env && ./push-to-ecr.sh
#   or
#   export AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=yyy && ./push-to-ecr.sh

# Configuration
REGION="${AWS_REGION:-us-east-1}"
TAG="${TAG:-dev}"  # Default to 'dev', override with: TAG=latest ./push-to-ecr.sh

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Push SentinelTranslate Images to ECR${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Check required environment variables
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${RED}Error: AWS credentials not set${NC}"
    echo ""
    echo "Please set the following environment variables:"
    echo "  export AWS_ACCESS_KEY_ID=your_access_key"
    echo "  export AWS_SECRET_ACCESS_KEY=your_secret_key"
    echo "  export AWS_REGION=us-east-1  # optional, defaults to us-east-1"
    echo ""
    echo "Or source a .env file:"
    echo "  source .env"
    echo ""
    exit 1
fi

# Get AWS account ID
echo "Getting AWS account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)

if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}Error: Could not get AWS account ID.${NC}"
    echo "Please verify your AWS credentials are correct."
    exit 1
fi

ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
echo -e "${GREEN}✓${NC} Account ID: $ACCOUNT_ID"
echo -e "${GREEN}✓${NC} ECR Registry: $ECR_REGISTRY"
echo ""

# Create ECR repositories if they don't exist
echo "Creating ECR repositories (if needed)..."
for repo in sentineltranslate-sidecar sentineltranslate-worker sentineltranslate-api sentineltranslate-triton; do
    aws ecr describe-repositories --repository-names $repo --region $REGION &>/dev/null || \
    aws ecr create-repository --repository-name $repo --region $REGION &>/dev/null && \
    echo -e "${GREEN}✓${NC} Created repository: $repo" || \
    echo -e "${GREEN}✓${NC} Repository exists: $repo"
done
echo ""

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin $ECR_REGISTRY

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Successfully logged in to ECR"
    echo ""
else
    echo "Error: ECR login failed"
    exit 1
fi

# Define image mappings: local_name:ecr_name
declare -A IMAGE_MAP=(
    ["sidecar:latest"]="sentineltranslate-sidecar"
    ["worker:latest"]="sentineltranslate-worker"
    ["frontend:latest"]="sentineltranslate-api"
    ["sentineltranslate-triton:dev"]="sentineltranslate-triton"
)

# Tag and push each image
echo "Tagging and pushing images..."
echo ""

for local_image in "${!IMAGE_MAP[@]}"; do
    ecr_repo="${IMAGE_MAP[$local_image]}"
    ecr_image="${ECR_REGISTRY}/${ecr_repo}:${TAG}"

    # Check if local image exists
    if ! docker image inspect "$local_image" &>/dev/null; then
        echo -e "${YELLOW}⚠${NC}  Image not found: $local_image (skipping)"
        continue
    fi

    echo "Processing: $local_image → $ecr_repo:$TAG"

    # Tag for ECR
    docker tag "$local_image" "$ecr_image"
    echo -e "${GREEN}✓${NC} Tagged: $ecr_image"

    # Push to ECR
    docker push "$ecr_image"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Pushed: $ecr_image"
        echo ""
    else
        echo "Error: Failed to push $ecr_image"
        exit 1
    fi
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ All images pushed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Images available at:"
for ecr_repo in "${IMAGE_MAP[@]}"; do
    echo "  ${ECR_REGISTRY}/${ecr_repo}:${TAG}"
done
echo ""
echo "Next steps:"
echo "  1. Update Helm values to use these ECR images"
echo "  2. Run: make upgrade-dev (from infrastructure/helm/sentineltranslate)"
