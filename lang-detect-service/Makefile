.PHONY: install python format lint typecheck test run build download-models help

help:
	@echo "Available targets:"
	@echo "  install           - Install dependencies with UV"
	@echo "  python            - Install and pin Python 3.11"
	@echo "  format            - Sort imports + format code with ruff"
	@echo "  lint              - Run format, then ruff check (fast)"
	@echo "  typecheck         - Run basedpyright type checking (slow)"
	@echo "  test              - Run pytest"
	@echo "  run               - Start lang-detect service (localhost:8082)"
	@echo "  build             - Build Docker image"
	@echo "  download-models   - Download all language detection models"

install:
	uv sync

python:
	uv python install 3.11
	uv python pin 3.11

format:
	uv run ruff check --select I --fix .
	uv run ruff format .

lint: format
	uv run ruff check .

typecheck:
	uv run basedpyright .

test:
	uv run pytest

run:
	uv run uvicorn app:app --host 0.0.0.0 --port 8082 --reload

build:
	docker build -t lang-detect-service:latest .

download-models:
	uv run python download_models.py
