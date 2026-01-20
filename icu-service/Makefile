.PHONY: help python install format lint typecheck test run build clean \
	k8s-create-namespace k8s-deploy k8s-delete k8s-status k8s-logs

# Default target
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

python: ## Install and pin Python 3.11
	uv python install 3.11
	uv python pin 3.11

install: python ## Install dependencies with UV
	uv sync

format: ## Format code with ruff (isort + format)
	uv run ruff check --select I --fix .
	uv run ruff format .

lint: format ## Run ruff linting
	uv run ruff check .

typecheck: ## Run basedpyright type checking
	uv run basedpyright .

test: ## Run pytest
	uv run pytest -q

run: ## Start FastAPI server with auto-reload
	uv run uvicorn app:app --host 127.0.0.1 --port 8083 --reload

build: ## Build Docker image
	docker build --platform linux/amd64 -t icu-service:latest .

clean: ## Remove build artifacts and cache
	@echo "Cleaning up..."
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "Cleanup complete"

# Kubernetes targets
k8s-create-namespace: ## Create sentinel-translate namespace
	@echo "Creating sentinel-translate namespace..."
	kubectl create namespace sentinel-translate || echo "Namespace already exists"

k8s-deploy: k8s-create-namespace ## Deploy ICU service to Kubernetes
	@echo "Deploying ICU service to Kubernetes..."
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/service.yaml
	kubectl apply -f k8s/hpa.yaml
	@echo ""
	@echo "Waiting for deployment to be ready..."
	kubectl -n sentinel-translate rollout status deployment/icu-service
	@echo ""
	@echo "Service endpoints:"
	@echo "  kubectl -n sentinel-translate get svc icu-service"
	@echo "  kubectl -n sentinel-translate logs -f deployment/icu-service"

k8s-status: ## Show Kubernetes deployment status
	@echo "Deployment status:"
	@kubectl -n sentinel-translate get deployment icu-service
	@echo ""
	@echo "Pods:"
	@kubectl -n sentinel-translate get pods -l app=icu-service
	@echo ""
	@echo "Service:"
	@kubectl -n sentinel-translate get svc icu-service
	@echo ""
	@echo "HPA status:"
	@kubectl -n sentinel-translate get hpa icu-service-hpa

k8s-logs: ## Stream deployment logs
	kubectl -n sentinel-translate logs -f deployment/icu-service

k8s-delete: ## Delete ICU service from Kubernetes
	@echo "Deleting ICU service from Kubernetes..."
	kubectl delete -f k8s/deployment.yaml -n sentinel-translate || true
	kubectl delete -f k8s/service.yaml -n sentinel-translate || true
	kubectl delete -f k8s/hpa.yaml -n sentinel-translate || true
	kubectl delete -f k8s/configmap.yaml -n sentinel-translate || true
	@echo "Deletion complete"
