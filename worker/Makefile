UV = uv

.PHONY: clean install download-models download-models-dev download-models-minimal build format lint test run

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ .ruff_cache .venv

install:
	$(UV) sync
	@$(MAKE) download-models

# Download all 21 spaCy models (20 language-specific + 1 multilingual fallback)
# Production-ready configuration for handling 20+ languages
# Total size: ~340MB
download-models:
	@echo "Warning: Downloading all 21 spaCy models (~340MB)..."
	$(UV) pip install \
		https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.8.0/zh_core_web_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/hr_core_news_sm-3.8.0/hr_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/da_core_news_sm-3.8.0/da_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/nl_core_news_sm-3.8.0/nl_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/fi_core_news_sm-3.8.0/fi_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/fr_core_news_sm-3.8.0/fr_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.8.0/de_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/el_core_news_sm-3.8.0/el_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/it_core_news_sm-3.8.0/it_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.8.0/ja_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/ko_core_news_sm-3.8.0/ko_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/lt_core_news_sm-3.8.0/lt_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/pl_core_news_sm-3.8.0/pl_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/pt_core_news_sm-3.8.0/pt_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/ro_core_news_sm-3.8.0/ro_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.8.0/ru_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/sl_core_news_sm-3.8.0/sl_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/es_core_news_sm-3.8.0/es_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/sv_core_news_sm-3.8.0/sv_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/uk_core_news_sm-3.8.0/uk_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.8.0/xx_ent_wiki_sm-3.8.0-py3-none-any.whl

# Download common languages for development (6 models + multilingual fallback)
# Faster installation for local development environments
# Total size: ~120MB
download-models-dev:
	@echo "Downloading common spaCy models for development (~120MB)..."
	$(UV) pip install \
		https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/fr_core_news_sm-3.8.0/fr_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.8.0/de_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/es_core_news_sm-3.8.0/es_core_news_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.8.0/zh_core_web_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.8.0/xx_ent_wiki_sm-3.8.0-py3-none-any.whl

# Download minimal models for CI/testing (2 models: English + multilingual fallback)
# Fastest installation for continuous integration and test environments
# Total size: ~60MB
download-models-minimal:
	@echo "Downloading minimal spaCy models for CI/testing (~60MB)..."
	$(UV) pip install \
		https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl \
		https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.8.0/xx_ent_wiki_sm-3.8.0-py3-none-any.whl

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
