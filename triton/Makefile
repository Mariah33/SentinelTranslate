.PHONY: install download-opus download-nllb clean help

help:
	@echo "Available commands:"
	@echo "  make install          - Install dependencies with UV"
	@echo "  make download-opus    - Download and convert all OPUS-MT models (41 models, ~12GB)"
	@echo "  make download-nllb    - Download and convert NLLB-200 model (~1.2GB)"
	@echo "  make clean            - Remove .venv directory"

install:
	@echo "Installing dependencies with UV..."
	uv sync

download-opus:
	@echo "Downloading and converting OPUS-MT models..."
	@echo "This will download 41 models (~12GB total) and may take 30-60 minutes"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	uv run python download_model.py

download-nllb:
	@echo "Downloading and converting NLLB-200-distilled-600M model..."
	@echo "This will download ~1.2GB and may take 10-15 minutes"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	uv run python download_nllb.py

clean:
	rm -rf .venv
	@echo "Cleaned .venv directory"
