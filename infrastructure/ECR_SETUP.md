# ECR Setup and Image Push Guide

This guide shows how to build and push Docker images to AWS ECR using environment variables instead of AWS profiles.

## Prerequisites

1. Docker installed and running
2. AWS CLI installed
3. IAM user with ECR permissions (e.g., `infra-builder`)

## Step 1: Get AWS Credentials

If you don't already have the access key for the `infra-builder` user, create one:

```bash
# Create new access key
aws iam create-access-key --user-name infra-builder

# Save the output - you'll need the AccessKeyId and SecretAccessKey
```

The output will look like:
```json
{
    "AccessKey": {
        "AccessKeyId": "AKIAXXXXXXXXXXXXXXXX",
        "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        ...
    }
}
```

**⚠️ Save the SecretAccessKey immediately - you can never retrieve it again!**

## Step 2: Configure Environment Variables

### Option A: Using .env File (Recommended)

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```bash
   export AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
   export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   export AWS_REGION=us-east-1
   ```

3. Source the file before running scripts:
   ```bash
   source .env
   ```

### Option B: Export Directly in Shell

```bash
export AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_REGION=us-east-1
```

### Option C: Add to Shell Profile (Persistent)

Add to `~/.zshrc` or `~/.bashrc`:
```bash
# AWS Credentials for SentinelTranslate
export AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_REGION=us-east-1
```

Then reload:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

## Step 3: Build and Push Images

**Important**: All images are built for `linux/amd64` architecture to match AWS EKS nodes, even if you're building on Apple Silicon (ARM64). This is handled automatically by the build scripts.

### Quick Method: All-in-One

Build all images and push to ECR in one command:

```bash
# Source credentials first (from project root)
source .env

# Build and push everything
./infrastructure/build-and-push.sh
```

This will:
1. Build `sidecar`, `worker`, `api`, and `triton` images for **linux/amd64**
2. Create ECR repositories if needed
3. Tag images for ECR
4. Push to ECR

### Manual Method: Step by Step

If you prefer more control:

```bash
# 1. Source credentials
source .env

# 2. Build images locally
make build  # Builds sidecar, worker, and api

cd triton
docker build -t sentineltranslate-triton:dev .
cd ..

# 3. Push to ECR
./infrastructure/push-to-ecr.sh
```

## Step 4: Verify Images in ECR

```bash
# List repositories
aws ecr describe-repositories --region us-east-1

# List images in a repository
aws ecr list-images --repository-name sentineltranslate-sidecar --region us-east-1
```

## Step 5: Update Helm Deployment

Once images are in ECR, deploy to your Kubernetes cluster. The Makefile automatically detects your AWS account ID and configures the ECR registry URL:

```bash
cd infrastructure/helm/sentineltranslate

# Build dependencies (Redis, Prometheus)
make dependency-build

# Lint the chart
make lint

# Install or upgrade with ECR images (account ID auto-detected)
make upgrade-dev

# Check pod status
make get-pods
```

**How it works:**
- The Makefile runs `aws sts get-caller-identity` to get your account ID
- Automatically constructs the ECR registry URL: `<account-id>.dkr.ecr.us-east-1.amazonaws.com`
- Passes it to Helm via `--set global.ecrRegistry=...`
- Templates inject the registry URL before each image repository name

**No hardcoded account IDs!** The account ID is never committed to git - it's detected dynamically from your AWS credentials.

## Troubleshooting

### "AWS credentials not set"

Make sure you've sourced the .env file:
```bash
source .env
echo $AWS_ACCESS_KEY_ID  # Should print your access key
```

### "Could not get AWS account ID"

Your credentials may be incorrect. Verify them:
```bash
aws sts get-caller-identity
```

Expected output:
```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "606299458754",
    "Arn": "arn:aws:iam::606299458754:user/infra-builder"
}
```

### "Repository does not exist"

The script automatically creates repositories. If you see this error, you may not have ECR permissions. Check IAM policies:
```bash
aws iam list-attached-user-policies --user-name infra-builder
```

### "no basic auth credentials"

Your ECR login has expired. Re-run the login command:
```bash
source .env
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
```

## Image Tags

By default, images are tagged as `:dev`. To use a different tag:

```bash
TAG=v1.0.0 ./infrastructure/push-to-ecr.sh
```

## Security Best Practices

1. **Never commit `.env` to Git** - It's already in `.gitignore`
2. **Rotate access keys regularly** - Delete old keys after creating new ones
3. **Use least privilege** - The `infra-builder` user should only have ECR and EKS permissions
4. **Use environment-specific credentials** - Different credentials for dev/staging/prod

## Related Scripts

- `infrastructure/push-to-ecr.sh` - Push locally built images to ECR
- `infrastructure/build-and-push.sh` - Build and push in one command
- `.env.example` - Template for credentials (in project root)

## Questions?

See the main [README](README.md) or Helm chart documentation in `infrastructure/helm/sentineltranslate/`.
