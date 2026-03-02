# Jikai Makefile

.PHONY: help install dev test lint format clean run api tui tui-build warmup train preprocess health health-llm env-setup dev-setup

help: ## Show this help message
	@echo "Jikai - AI-Powered Legal Hypothetical Generator"
	@echo "=============================================="
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# -- setup --

install: ## Install Python dependencies
	pip install -r requirements.txt

dev: ## Install dev dependencies
	pip install -e ".[dev]"

# -- run --

api: ## Start FastAPI backend on :8000
	uvicorn src.api.main:app --host 127.0.0.1 --port 8000

tui-build: ## Build Rust TUI (release)
	cd tui && cargo build --release

tui: tui-build ## Run Rust TUI (connects to API on :8000)
	./tui/target/release/jikai-tui

run: ## Start API + TUI together
	@echo "Starting API server in background..."
	@uvicorn src.api.main:app --host 127.0.0.1 --port 8000 &
	@sleep 2
	@echo "Starting TUI..."
	@cd tui && cargo run --release
	@kill %1 2>/dev/null || true

# -- quality --

test: ## Run tests
	pytest tests/ -v --cov=src --cov-report=term

lint: ## Run linting
	flake8 src/ tests/
	mypy src/ --ignore-missing-imports || echo "mypy: warnings found"

format: ## Format code
	black src/ tests/
	isort src/ tests/

# -- ml/corpus --

warmup: ## Preload corpus and check provider health
	python -m src.warmup $(if $(INIT_EMBEDDINGS),--init-embeddings,)

train: ## Train ML models
	python -m src.ml.pipeline --data corpus/labelled/sample.csv

preprocess: ## Build corpus from raw files
	python -m src.services.corpus_preprocessor

# -- health --

health: ## Check API health
	curl -sf http://localhost:8000/health | python -m json.tool

health-llm: ## Check LLM health
	curl -sf http://localhost:8000/llm/health | python -m json.tool

# -- cleanup --

clean: ## Clean temp files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/
	cd tui && cargo clean

env-setup: ## Create .env from template
	@if [ ! -f .env ]; then cp env.example .env; echo "Created .env"; else echo ".env exists"; fi

dev-setup: env-setup install tui-build ## Full dev setup
	@echo "Done. Next: ollama serve && ollama pull llama2:7b && make run"
