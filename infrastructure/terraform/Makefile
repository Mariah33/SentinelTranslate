.PHONY: help init plan apply destroy validate format clean kubeconfig cost

# Default AWS region (can be overridden)
AWS_REGION ?= us-east-1
CLUSTER_NAME ?= sentineltranslate-dev-eks

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## Initialize Terraform (run this first)
	terraform init -upgrade

validate: ## Validate Terraform configuration
	terraform validate
	terraform fmt -check -recursive

format: ## Format Terraform files
	terraform fmt -recursive

plan: ## Show Terraform execution plan
	terraform plan -out=tfplan

apply: ## Apply Terraform changes
	terraform apply tfplan

apply-auto: ## Apply changes without confirmation (dangerous!)
	terraform apply -auto-approve

destroy-plan: ## Plan infrastructure destruction
	terraform plan -destroy -out=tfplan-destroy

destroy: ## Destroy all infrastructure (requires confirmation)
	@echo "WARNING: This will destroy all infrastructure!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read
	terraform destroy

clean: ## Remove Terraform state and plan files
	rm -f tfplan tfplan-destroy
	rm -rf .terraform
	rm -f .terraform.lock.hcl

output: ## Show Terraform outputs
	terraform output

output-json: ## Show Terraform outputs in JSON format
	terraform output -json

kubeconfig: ## Update local kubeconfig for EKS cluster
	@echo "Updating kubeconfig for cluster: $(CLUSTER_NAME)"
	aws eks update-kubeconfig --region $(AWS_REGION) --name $(CLUSTER_NAME)
	kubectl cluster-info
	kubectl get nodes

cost: ## Show estimated monthly costs
	@terraform output -json | jq -r '.estimated_monthly_cost_usd.value | to_entries[] | "\(.key): $\(.value)"'

show: ## Show current Terraform state
	terraform show

graph: ## Generate Terraform dependency graph
	terraform graph | dot -Tpng > graph.png
	@echo "Graph saved to graph.png"

nodes: ## Show EKS node information
	kubectl get nodes -o wide

pods: ## Show all pods across namespaces
	kubectl get pods --all-namespaces

scale-gpu-up: ## Scale GPU nodes to 1
	kubectl scale deployment triton --replicas=1 || echo "Triton deployment not found"

scale-gpu-down: ## Scale GPU nodes to 0 (saves costs)
	kubectl scale deployment triton --replicas=0 || echo "Triton deployment not found"

install-addons: ## Install recommended Kubernetes addons
	@echo "Installing AWS Load Balancer Controller..."
	helm repo add eks https://aws.github.io/eks-charts
	helm repo update
	helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
		-n kube-system \
		--set clusterName=$(CLUSTER_NAME) \
		--set serviceAccount.create=false \
		--set serviceAccount.name=aws-load-balancer-controller
	@echo "Installing Metrics Server..."
	kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
	@echo "Installing NVIDIA Device Plugin..."
	kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

logs-cluster: ## Show EKS control plane logs
	@echo "Fetching EKS control plane logs from CloudWatch..."
	aws logs tail /aws/eks/$(CLUSTER_NAME)/cluster --follow

backend-init: ## Initialize S3 backend (run once before init)
	@echo "Creating S3 bucket for Terraform state..."
	@ACCOUNT_ID=$$(aws sts get-caller-identity --query Account --output text); \
	BUCKET_NAME=sentineltranslate-terraform-state-$$ACCOUNT_ID; \
	aws s3 mb s3://$$BUCKET_NAME --region $(AWS_REGION) || true; \
	aws s3api put-bucket-versioning --bucket $$BUCKET_NAME --versioning-configuration Status=Enabled; \
	echo "Creating DynamoDB table for state locking..."; \
	aws dynamodb create-table \
		--table-name sentineltranslate-terraform-locks \
		--attribute-definitions AttributeName=LockID,AttributeType=S \
		--key-schema AttributeName=LockID,KeyType=HASH \
		--billing-mode PAY_PER_REQUEST \
		--region $(AWS_REGION) || true; \
	echo "Backend resources created. Update backend.tf with bucket name: $$BUCKET_NAME"

check-aws: ## Verify AWS credentials
	@echo "AWS Account: $$(aws sts get-caller-identity --query Account --output text)"
	@echo "AWS Region: $(AWS_REGION)"
	@echo "AWS User: $$(aws sts get-caller-identity --query Arn --output text)"

refresh: ## Refresh Terraform state
	terraform refresh

taint-gpu: ## Taint GPU nodes for recreation
	terraform taint 'module.eks.eks_managed_node_groups["gpu_nodes"]'

untaint-gpu: ## Remove taint from GPU nodes
	terraform untaint 'module.eks.eks_managed_node_groups["gpu_nodes"]'

.DEFAULT_GOAL := help
