.PHONY: help python install format lint test run build \
	download-all-models download-to-volume download-languages \
	build-lightweight run-with-volume \
	k8s-create-namespace k8s-deploy k8s-delete k8s-status k8s-logs \
	deploy-full clean

# Default target
help:
	@echo "NER Service Volume-Mounted Architecture"
	@echo ""
	@echo "Setup targets:"
	@echo "  make install              Install dependencies"
	@echo "  make python               Install Python 3.11"
	@echo ""
	@echo "Development targets:"
	@echo "  make format               Format code (isort + ruff)"
	@echo "  make lint                 Lint code (format + ruff + type check)"
	@echo "  make test                 Run pytest tests"
	@echo "  make run                  Run locally with auto-reload"
	@echo ""
	@echo "Model download targets:"
	@echo "  make download-all-models              Download all 21 spaCy + 60+ Stanza models (~10GB)"
	@echo "  make download-languages LANGUAGES=en,fr,de  Download specific languages"
	@echo "  make download-to-volume VOLUME_PATH=/mnt/models  Download to mounted volume"
	@echo ""
	@echo "Container targets:"
	@echo "  make build                Build lightweight container (~200MB)"
	@echo "  make run-with-volume      Run with docker-compose (requires ./models)"
	@echo "  make clean                Remove downloaded models and containers"
	@echo ""
	@echo "Kubernetes targets:"
	@echo "  make k8s-create-namespace Create sentineltranslate namespace"
	@echo "  make k8s-deploy           Deploy to Kubernetes"
	@echo "  make k8s-status           Check deployment status"
	@echo "  make k8s-logs             Stream pod logs"
	@echo "  make k8s-delete           Delete from Kubernetes"
	@echo ""
	@echo "Full deployment:"
	@echo "  make deploy-full          Download models and deploy to K8s"

python:
	uv python install 3.11

install: python
	uv sync

# Download ALL models (21 spaCy + 60+ Stanza) to local directory
# New volume-mounted architecture: models stored separately from container
download-all-models:
	@echo "Downloading ALL 21 spaCy large models and 60+ Stanza models..."
	@echo "This may take 30-60 minutes and requires ~10GB disk space"
	uv run python download_all_models.py --output-dir ./models

# Download all models to a specific volume path
# Usage: make download-to-volume VOLUME_PATH=/mnt/models
download-to-volume:
	@if [ -z "$(VOLUME_PATH)" ]; then \
		echo "Error: VOLUME_PATH not specified"; \
		echo "Usage: make download-to-volume VOLUME_PATH=/mnt/models"; \
		exit 1; \
	fi
	@echo "Downloading models to: $(VOLUME_PATH)"
	@if [ ! -w "$(VOLUME_PATH)" ]; then \
		echo "Error: Volume path is not writable"; \
		exit 1; \
	fi
	uv run python download_all_models.py --output-dir "$(VOLUME_PATH)"

# Download specific languages only
# Usage: make download-languages LANGUAGES=en,fr,de
download-languages:
	@if [ -z "$(LANGUAGES)" ]; then \
		echo "Error: LANGUAGES not specified"; \
		echo "Usage: make download-languages LANGUAGES=en,fr,de"; \
		exit 1; \
	fi
	@echo "Downloading models for languages: $(LANGUAGES)"
	uv run python download_all_models.py --output-dir ./models --languages "$(LANGUAGES)"

# Build lightweight container (no models included)
build:
	@echo "Building lightweight NER service container (~200MB)..."
	docker build --platform linux/amd64 -t ner-service:latest .

# Run with volume mount (requires models to be downloaded first)
run-with-volume:
	@if [ ! -d "./models" ]; then \
		echo "Error: ./models directory not found"; \
		echo "Run 'make download-all-models' first"; \
		exit 1; \
	fi
	@echo "Starting NER service with volume-mounted models..."
	docker compose up

# Build and run in one step
build-lightweight: build run-with-volume

format:
	uv run ruff check --select I --fix
	uv run ruff format .

lint: format
	uv run ruff check . --fix
	uv run basedpyright .

test:
	uv run pytest -q

run:
	uv run uvicorn app:app --host 0.0.0.0 --port 8081 --reload

# Kubernetes targets
k8s-create-namespace:
	@echo "Creating sentineltranslate namespace..."
	kubectl create namespace sentineltranslate || echo "Namespace already exists"

k8s-deploy: k8s-create-namespace
	@echo "Deploying NER service to Kubernetes..."
	kubectl apply -f k8s/pvc.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/service.yaml
	@echo ""
	@echo "Waiting for deployment to be ready..."
	kubectl -n sentineltranslate rollout status deployment/ner-service
	@echo ""
	@echo "Service endpoints:"
	@echo "  Cluster IP: kubectl -n sentineltranslate get svc ner-service"
	@echo "  Logs: kubectl -n sentineltranslate logs -f deployment/ner-service"

k8s-status:
	@echo "Deployment status:"
	kubectl -n sentineltranslate get deployment ner-service
	@echo ""
	@echo "Pods:"
	kubectl -n sentineltranslate get pods -l app=ner-service
	@echo ""
	@echo "PVC status:"
	kubectl -n sentineltranslate get pvc ner-models-pvc
	@echo ""
	@echo "Service:"
	kubectl -n sentineltranslate get svc ner-service

k8s-logs:
	kubectl -n sentineltranslate logs -f deployment/ner-service

k8s-delete:
	@echo "Deleting NER service from Kubernetes..."
	kubectl delete -f k8s/deployment.yaml || true
	kubectl delete -f k8s/service.yaml || true
	kubectl delete -f k8s/pvc.yaml || true
	@echo "Deletion complete"

# Full deployment: download models + build + deploy to k8s
deploy-full: download-all-models build k8s-deploy
	@echo ""
	@echo "Full deployment complete!"
	@echo "Models: ./models/"
	@echo "Container: ner-service:latest"
	@echo "Kubernetes: sentineltranslate namespace"

# Clean up local files
clean:
	@echo "Cleaning up..."
	rm -rf ./models ./build ./dist ./*.egg-info .pytest_cache .ruff_cache
	docker compose down || true
	@echo "Cleanup complete"

