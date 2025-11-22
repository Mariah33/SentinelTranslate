.PHONY: help install format lint test clean build
.PHONY: sidecar-install sidecar-format sidecar-lint sidecar-test sidecar-run sidecar-build sidecar-clean
.PHONY: worker-install worker-format worker-lint worker-test worker-run worker-build worker-clean
.PHONY: api-install api-format api-lint api-test api-run api-build api-clean
.PHONY: up up-gpu up-cpu down logs ps restart rebuild

# Default target
help:
	@echo "SentinelTranslate - Multi-component Makefile"
	@echo ""
	@echo "Docker Compose (Full Stack):"
	@echo "  make up            Start all services (CPU-only, works on any machine)"
	@echo "  make up-gpu        Start all services with GPU support (requires NVIDIA GPU)"
	@echo "  make up-cpu        Start all services with CPU optimizations"
	@echo "  make down          Stop all services"
	@echo "  make restart       Restart all services"
	@echo "  make logs          View logs from all services"
	@echo "  make ps            List running services"
	@echo "  make rebuild       Rebuild and restart all services"
	@echo ""
	@echo "Global targets (run for both sidecar and worker):"
	@echo "  make install       Install dependencies for all components"
	@echo "  make format        Format code for all components"
	@echo "  make lint          Lint all components"
	@echo "  make test          Run tests for all components"
	@echo "  make build         Build Docker images for all components"
	@echo "  make clean         Clean all components"
	@echo ""
	@echo "Sidecar-specific targets:"
	@echo "  make sidecar-install"
	@echo "  make sidecar-format"
	@echo "  make sidecar-lint"
	@echo "  make sidecar-test"
	@echo "  make sidecar-run"
	@echo "  make sidecar-build"
	@echo "  make sidecar-clean"
	@echo ""
	@echo "Worker-specific targets:"
	@echo "  make worker-install"
	@echo "  make worker-format"
	@echo "  make worker-lint"
	@echo "  make worker-test"
	@echo "  make worker-run"
	@echo "  make worker-build"
	@echo "  make worker-clean"
	@echo ""
	@echo "API-specific targets:"
	@echo "  make api-install"
	@echo "  make api-format"
	@echo "  make api-lint"
	@echo "  make api-test"
	@echo "  make api-run"
	@echo "  make api-build"
	@echo "  make api-clean"

# Global targets - run for all components
install: sidecar-install worker-install api-install

format: sidecar-format worker-format api-format

lint: sidecar-lint worker-lint api-lint

test: sidecar-test worker-test api-test

build: sidecar-build worker-build api-build

clean: sidecar-clean worker-clean api-clean

# Sidecar targets
sidecar-install:
	@echo "📦 Installing sidecar dependencies..."
	cd sidecar && $(MAKE) install

sidecar-format:
	@echo "🎨 Formatting sidecar code..."
	cd sidecar && $(MAKE) format

sidecar-lint:
	@echo "🔍 Linting sidecar..."
	cd sidecar && $(MAKE) lint

sidecar-test:
	@echo "🧪 Testing sidecar..."
	cd sidecar && $(MAKE) test

sidecar-run:
	@echo "🚀 Running sidecar..."
	cd sidecar && $(MAKE) run

sidecar-build:
	@echo "🐳 Building sidecar Docker image..."
	cd sidecar && $(MAKE) build

sidecar-clean:
	@echo "🧹 Cleaning sidecar..."
	cd sidecar && $(MAKE) clean

# Worker targets
worker-install:
	@echo "📦 Installing worker dependencies..."
	cd worker && $(MAKE) install

worker-format:
	@echo "🎨 Formatting worker code..."
	cd worker && $(MAKE) format

worker-lint:
	@echo "🔍 Linting worker..."
	cd worker && $(MAKE) lint

worker-test:
	@echo "🧪 Testing worker..."
	cd worker && $(MAKE) test

worker-run:
	@echo "🚀 Running worker..."
	cd worker && $(MAKE) run

worker-build:
	@echo "🐳 Building worker Docker image..."
	cd worker && $(MAKE) build

worker-clean:
	@echo "🧹 Cleaning worker..."
	cd worker && $(MAKE) clean

# API targets
api-install:
	@echo "📦 Installing API dependencies..."
	cd api && $(MAKE) install

api-format:
	@echo "🎨 Formatting API code..."
	cd api && $(MAKE) format

api-lint:
	@echo "🔍 Linting API..."
	cd api && $(MAKE) lint

api-test:
	@echo "🧪 Testing API..."
	cd api && $(MAKE) test

api-run:
	@echo "🚀 Running API..."
	cd api && $(MAKE) run

api-build:
	@echo "🐳 Building API Docker image..."
	cd api && $(MAKE) build

api-clean:
	@echo "🧹 Cleaning API..."
	cd api && $(MAKE) clean

# Docker Compose targets
up:
	@echo "🚀 Starting all services (CPU-only mode)..."
	docker-compose up -d
	@echo ""
	@echo "✅ Services started! Access points:"
	@echo "  - Batch API:      http://localhost:8090 (batch S3 parquet translation)"
	@echo "  - Sidecar API:    http://localhost:8080 (single-text translation)"
	@echo "  - Triton Server:  http://localhost:8000"
	@echo "  - Redis:          localhost:6379"
	@echo ""
	@echo "💡 Tip: For GPU support, use 'make up-gpu' instead"
	@echo "📋 View logs: make logs"

up-gpu:
	@echo "🚀 Starting all services with GPU support..."
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
	@echo ""
	@echo "✅ Services started with GPU! Access points:"
	@echo "  - Batch API:      http://localhost:8090 (batch S3 parquet translation)"
	@echo "  - Sidecar API:    http://localhost:8080 (single-text translation)"
	@echo "  - Triton Server:  http://localhost:8000"
	@echo "  - Redis:          localhost:6379"
	@echo ""
	@echo "📋 View logs: make logs"

up-cpu:
	@echo "🚀 Starting all services with CPU optimizations..."
	docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up -d
	@echo ""
	@echo "✅ Services started! Access points:"
	@echo "  - Batch API:      http://localhost:8090 (batch S3 parquet translation)"
	@echo "  - Sidecar API:    http://localhost:8080 (single-text translation)"
	@echo "  - Triton Server:  http://localhost:8000"
	@echo "  - Redis:          localhost:6379"
	@echo ""
	@echo "📋 View logs: make logs"

down:
	@echo "🛑 Stopping all services..."
	docker-compose down

logs:
	docker-compose logs -f

ps:
	docker-compose ps

restart:
	@echo "🔄 Restarting all services..."
	docker-compose restart

rebuild:
	@echo "🔨 Rebuilding and restarting all services..."
	docker-compose up -d --build
