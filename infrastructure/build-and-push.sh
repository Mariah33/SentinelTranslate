#!/bin/bash
set -e

# Build all SentinelTranslate images locally and push to ECR
# This is a convenience script that combines building and pushing
#
# Prerequisites:
#   1. AWS credentials set in environment (or source .env file)
#   2. Docker installed and running
#
# Usage:
#   source .env && ./build-and-push.sh

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Build & Push SentinelTranslate${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check for AWS credentials
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${RED}Error: AWS credentials not set${NC}"
    echo ""
    echo "Please source your .env file first:"
    echo "  source .env"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓${NC} AWS credentials detected"
echo ""

# Step 1: Build all images
echo -e "${YELLOW}Step 1: Building all Docker images...${NC}"
echo ""

# Get to project root (infrastructure/ -> project root)
cd "$(dirname "$0")/.."

# Build sidecar
echo "Building sidecar..."
cd sidecar && make build && cd ..
echo -e "${GREEN}✓${NC} sidecar:latest built"
echo ""

# Build worker
echo "Building worker..."
cd worker && make build && cd ..
echo -e "${GREEN}✓${NC} worker:latest built"
echo ""

# Build api (frontend)
echo "Building api..."
cd api && make build && cd ..
echo -e "${GREEN}✓${NC} frontend:latest built"
echo ""

# Build triton
echo "Building triton..."
cd triton && docker build --platform linux/amd64 -t sentineltranslate-triton:dev . && cd ..
echo -e "${GREEN}✓${NC} sentineltranslate-triton:dev built"
echo ""

echo -e "${GREEN}✓ All images built successfully!${NC}"
echo ""

# Step 2: Push to ECR
echo -e "${YELLOW}Step 2: Pushing images to ECR...${NC}"
echo ""

# Run push script from infrastructure directory
cd infrastructure
./push-to-ecr.sh

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ Build and Push Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
