UV = uv

.PHONY: clean install build format lint test run

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ .ruff_cache .venv

install:
	$(UV) sync

build:
	docker build --platform linux/amd64 -t worker:latest .

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
