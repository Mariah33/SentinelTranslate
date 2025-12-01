# Makefile for OPUS-MT ONNX Conversion and Triton Deployment
# Requires: Python 3.11+, Docker (optional)

.PHONY: help install download-opus download-nllb clean \
        convert-opus-single convert-opus-common convert-opus-all \
        download-onnx validate-onnx generate-configs \
        build-converter triton-start triton-stop triton-test

# Configuration
PYTHON := python3
MODEL_DIR := model-repository
LANGUAGES ?= fr,de,es,it,pt,nl,pl,ro
WORKERS ?= 4
MAX_BATCH_SIZE ?= 8
TRITON_IMAGE := nvcr.io/nvidia/tritonserver:23.10-py3
TRITON_CONTAINER := triton-server

##@ General

help: ## Display this help message
	@echo "OPUS-MT ONNX Conversion & Triton Deployment"
	@echo ""
	@echo "Setup:"
	@echo "  make install                  - Install dependencies with UV"
	@echo ""
	@echo "Legacy Download (PyTorch):"
	@echo "  make download-opus            - Download all OPUS-MT PyTorch models (41 models, ~12GB)"
	@echo "  make download-nllb            - Download NLLB-200 model (~1.2GB)"
	@echo ""
	@echo "ONNX Conversion (Recommended):"
	@echo "  make convert-opus-single LANG=fr - Convert single language"
	@echo "  make convert-opus-common      - Convert 8 common languages (fr,de,es,it,pt,nl,pl,ro)"
	@echo "  make convert-opus-all         - Convert all 41 languages (60-90 min)"
	@echo "  make download-onnx            - Download pre-converted ONNX models"
	@echo "  make validate-onnx            - Validate all ONNX models"
	@echo "  make generate-configs         - Generate Triton config.pbtxt files"
	@echo ""
	@echo "Docker:"
	@echo "  make build-converter          - Build Docker image with ONNX conversion"
	@echo "  make triton-start             - Start Triton Inference Server"
	@echo "  make triton-stop              - Stop Triton Inference Server"
	@echo "  make triton-test              - Test inference endpoint"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean                    - Remove models and cache"

##@ Setup

install: ## Install dependencies with UV
	@echo "Installing dependencies with UV..."
	uv sync

##@ Legacy PyTorch Download

download-opus: ## Download all OPUS-MT PyTorch models (41 models, ~12GB)
	@echo "Downloading and converting OPUS-MT models..."
	@echo "This will download 41 models (~12GB total) and may take 30-60 minutes"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	uv run python download_model.py

download-nllb: ## Download NLLB-200-distilled-600M model (~1.2GB)
	@echo "Downloading and converting NLLB-200-distilled-600M model..."
	@echo "This will download ~1.2GB and may take 10-15 minutes"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	uv run python download_nllb.py

##@ ONNX Conversion (Recommended)

convert-opus-single: ## Convert single OPUS-MT model (usage: make convert-opus-single LANG=fr)
	@if [ -z "$(LANG)" ]; then \
		echo "Error: LANG not specified"; \
		echo "Usage: make convert-opus-single LANG=fr"; \
		exit 1; \
	fi
	@echo "Converting OPUS-MT model: $(LANG) → en"
	$(PYTHON) convert_opus_to_onnx.py \
		--language $(LANG) \
		--output-dir $(MODEL_DIR) \
		--validate

convert-opus-common: ## Convert 8 common European languages (fr,de,es,it,pt,nl,pl,ro)
	@echo "Converting 8 common OPUS-MT models..."
	$(PYTHON) convert_opus_to_onnx.py \
		--languages fr,de,es,it,pt,nl,pl,ro \
		--output-dir $(MODEL_DIR) \
		--workers $(WORKERS) \
		--validate

convert-opus-all: ## Convert all 41 OPUS-MT language pairs (60-90 minutes)
	@echo "WARNING: This will convert all 41 language pairs (60-90 minutes)"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(PYTHON) convert_opus_to_onnx.py \
		--all \
		--output-dir $(MODEL_DIR) \
		--workers $(WORKERS) \
		--validate

##@ ONNX Download

download-onnx: ## Download pre-converted ONNX models from Hugging Face
	@echo "Downloading ONNX models: $(LANGUAGES)"
	$(PYTHON) download_opus_onnx.py \
		--languages $(LANGUAGES) \
		--output-dir $(MODEL_DIR) \
		--workers $(WORKERS)

download-onnx-all: ## Download all available ONNX models
	@echo "Downloading all available ONNX models..."
	$(PYTHON) download_opus_onnx.py \
		--all \
		--output-dir $(MODEL_DIR) \
		--workers 8

##@ Validation & Configuration

validate-onnx: ## Validate all ONNX models in repository
	@echo "Validating ONNX models..."
	@$(PYTHON) -c "\
import onnx; \
import glob; \
import sys; \
onnx_files = glob.glob('$(MODEL_DIR)/**/*.onnx', recursive=True); \
print(f'Found {len(onnx_files)} ONNX files'); \
failed = []; \
for f in onnx_files: \
    try: \
        model = onnx.load(f); \
        onnx.checker.check_model(model); \
        print(f'✓ {f}'); \
    except Exception as e: \
        print(f'✗ {f}: {e}'); \
        failed.append(f); \
if failed: \
    print(f'Validation failed for {len(failed)} models'); \
    sys.exit(1); \
else: \
    print(f'All {len(onnx_files)} models validated successfully!'); \
"

generate-configs: ## Generate Triton config.pbtxt files for all models
	@echo "Generating Triton config files..."
	$(PYTHON) triton_config_generator.py \
		--model-dir $(MODEL_DIR) \
		--max-batch-size $(MAX_BATCH_SIZE) \
		--backend onnxruntime

##@ Docker Operations

build-converter: ## Build Docker image with ONNX conversion (LANGUAGES="fr,de,es")
	@echo "Building ONNX converter Docker image..."
	@echo "Languages: $(LANGUAGES)"
	docker build \
		--build-arg LANGUAGES="$(LANGUAGES)" \
		--build-arg WORKERS=$(WORKERS) \
		--build-arg VALIDATE=true \
		-f Dockerfile.convert \
		-t opus-converter:latest \
		.

##@ Triton Server

triton-start: ## Start Triton Inference Server with ONNX models
	@echo "Starting Triton Inference Server..."
	docker run -d --rm \
		--name $(TRITON_CONTAINER) \
		-p 8000:8000 -p 8001:8001 -p 8002:8002 \
		-v $(PWD)/$(MODEL_DIR):/models \
		$(TRITON_IMAGE) \
		tritonserver --model-repository=/models --strict-model-config=false
	@echo "Waiting for server to be ready..."
	@sleep 5
	@curl -f http://localhost:8000/v2/health/ready && echo "✓ Triton server ready" || echo "Check logs: make triton-logs"

triton-stop: ## Stop Triton Inference Server
	@echo "Stopping Triton server..."
	docker stop $(TRITON_CONTAINER) || true

triton-logs: ## Show Triton server logs
	docker logs -f $(TRITON_CONTAINER)

triton-test: ## Test Triton inference with sample request
	@echo "Testing Triton inference (opus-mt-fr-en)..."
	@curl -X POST http://localhost:8000/v2/models/opus-mt-fr-en/infer \
		-H "Content-Type: application/json" \
		-d '{"inputs": [{"name": "INPUT_TEXT", "shape": [1], "datatype": "BYTES", "data": ["Bonjour le monde"]}]}'
	@echo ""

##@ Cleanup

clean: ## Remove models, .venv, and cache
	rm -rf .venv
	rm -rf $(MODEL_DIR)/*/
	rm -rf __pycache__/
	@echo "Cleaned directories"
