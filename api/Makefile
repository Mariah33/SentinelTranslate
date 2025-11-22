APP_NAME = app:app
UV = uv
PYTHON_VERSION = 3.11

.PHONY: clean install build format lint test run python

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ .ruff_cache .venv

python:
	@echo "🐍 Installing Python $(PYTHON_VERSION) with UV..."
	uv python install $(PYTHON_VERSION)
	@echo "🔧 Setting local Python version..."
	uv python pin $(PYTHON_VERSION)
	@echo "✅ Python $(PYTHON_VERSION) installed and pinned for this project."
	@echo "📌 Current Python version:"
	uv run python --version

install:
	$(UV) sync --dev

build:
	docker build -t frontend:latest .

format:
	$(UV) run ruff check --select I --fix
	$(UV) run ruff format .

lint: format
	$(UV) run ruff check .

test:
	$(UV) run pytest -q

run:
	$(UV) run uvicorn $(APP_NAME) --host 0.0.0.0 --port 8090 --reload
