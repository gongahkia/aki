# Jikai Makefile - Development and deployment commands

.PHONY: help install dev test lint format clean build run web warmup bench-latency demo-flow pre-commit pre-commit-update

# Default target
help: ## Show this help message
	@echo "Jikai - AI-Powered Legal Hypothetical Generator"
	@echo "=============================================="
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development setup
install: ## Install dependencies
	pip install -r requirements.txt

dev: ## Install development dependencies
	pip install -r requirements.txt

# Code quality
test: ## Run tests
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-unit: ## Run unit tests only
	pytest tests/ -v -m "not integration"

test-integration: ## Run integration tests only
	pytest tests/ -v -m "integration"

lint: ## Run linting
	flake8 src/ tests/
	mypy src/ --ignore-missing-imports || echo "mypy: warnings found (non-blocking)"

format: ## Format code
	black src/ tests/
	isort src/ tests/

format-check: ## Check code formatting
	black --check src/ tests/
	isort --check-only src/ tests/

# Application commands
run: ## Run both API and TUI
	python -m src.tui --both

tui: ## Run TUI only
	python -m src.tui --tui-only

api: ## Run API server only
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

web: ## Run optional web surface (keeps TUI workflow unchanged)
	python -m src.api.web

warmup: ## Preload corpus topics, check provider health, and optionally init embeddings
	python -m src.warmup $(if $(INIT_EMBEDDINGS),--init-embeddings,)

bench-latency: ## Run latency benchmark and print p50/p95 summary
	@mkdir -p data
	@KMP_DUPLICATE_LIB_OK=TRUE PYTHONPATH=. python3 tests/perf/benchmark_latency.py --iterations $${ITERATIONS:-20} --output data/bench_latency.json
	@python3 -c "import json; data=json.load(open('data/bench_latency.json', encoding='utf-8')); b=data['baseline']; f=data['fast_mode']; print(f'baseline p50={b[\"p50_ms\"]}ms p95={b[\"p95_ms\"]}ms'); print(f'fast_mode p50={f[\"p50_ms\"]}ms p95={f[\"p95_ms\"]}ms')"

demo-flow: ## Launch deterministic Textual demo flow for screenshot capture
	@mkdir -p asset/reference/demo
	@DEMO_MODE=1 JIKAI_DEMO_SEED=$${JIKAI_DEMO_SEED:-424242} DEFAULT_PROVIDER=ollama DEFAULT_MODEL=llama3 python -m src.tui --tui-only --ui textual

run-prod: ## Run the application in production mode
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Health checks
health: ## Check application health
	curl -f http://localhost:8000/health || echo "Application not running"

health-llm: ## Check LLM service health
	curl -f http://localhost:8000/llm/health || echo "LLM service not available"

# ML Training
train: ## Train ML models on labelled corpus
	python -m src.ml.pipeline --data corpus/labelled/sample.csv

# Corpus Preprocessing
preprocess: ## Build corpus from raw files (TXT/PDF/PNG/DOCX)
	python -m src.services.corpus_preprocessor

convert: ## Convert a single file to txt: make convert FILE=path/to/file.pdf
	python -m src.services.corpus_preprocessor convert $(FILE)

# Setup
setup: ## Install all dependencies
	pip install -r requirements.txt

# Cleanup
clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

# Security
security-scan: ## Run security scans
	bandit -r src/ -ll -ii --skip B101 -f json -o bandit-report.json || true

# Documentation
docs: ## Generate documentation
	@echo "Documentation is available at:"
	@echo "  - API Docs: http://localhost:8000/docs"
	@echo "  - README: README.md"

# Environment setup
env-setup: ## Set up environment file
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "Created .env file from env.example"; \
		echo "Please edit .env with your configuration"; \
	else \
		echo ".env file already exists"; \
	fi

# Development workflow
dev-setup: env-setup dev ## Complete development setup
	@echo "Development environment setup complete!"
	@echo "Next steps:"
	@echo "  1. Edit .env file with your configuration"
	@echo "  2. Start Ollama locally: ollama serve"
	@echo "  3. Pull model: ollama pull llama2:7b"
	@echo "  4. Run tests: make test"
	@echo "  5. Start app: make run"

# CI/CD simulation
ci-local: format-check lint test security-scan ## Run CI pipeline locally
	@echo "All CI checks passed!"

# Production deployment
deploy-staging: ## Deploy to staging
	@echo "Deploying to staging environment..."
	# Add your staging deployment commands here

deploy-prod: ## Deploy to production
	@echo "Deploying to production environment..."
	# Add your production deployment commands here

# Monitoring
logs: ## View application logs
	tail -f logs/jikai.log

metrics: ## View application metrics
	@echo "Metrics available at:"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000"

# Backup and restore
backup: ## Backup application data
	@echo "Creating backup..."
	tar -czf backup-$$(date +%Y%m%d-%H%M%S).tar.gz data/ corpus/

restore: ## Restore application data
	@echo "Restoring from backup..."
	@echo "Please specify backup file: make restore BACKUP_FILE=backup-YYYYMMDD-HHMMSS.tar.gz"
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Error: BACKUP_FILE not specified"; \
		exit 1; \
	fi
	tar -xzf $(BACKUP_FILE)
