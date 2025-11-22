UV = uv

.PHONY: clean install download-models build format lint test run

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ .ruff_cache .venv

install:
	$(UV) sync
	@$(MAKE) download-models

download-models:
	@echo "📦 Downloading spaCy language model..."
	$(UV) pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

build:
	docker build -t worker:latest .

format:
	$(UV) run ruff check --select I --fix
	$(UV) run ruff format .

lint: format
	$(UV) run ruff check .
# 	$(UV) run basedpyright .

test:
	$(UV) run pytest -q

run:
	$(UV) run celery -A celery_app worker --loglevel=INFO
