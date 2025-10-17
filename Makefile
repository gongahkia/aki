# Jikai Makefile - Development and deployment commands

.PHONY: help install dev test lint format clean build run docker-build docker-run docker-compose-up docker-compose-down

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
	pre-commit install

# Code quality
test: ## Run tests
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-unit: ## Run unit tests only
	pytest tests/ -v -m "not integration"

test-integration: ## Run integration tests only
	pytest tests/ -v -m "integration"

lint: ## Run linting
	flake8 src/ tests/
	mypy src/ --ignore-missing-imports

format: ## Format code
	black src/ tests/
	isort src/ tests/

format-check: ## Check code formatting
	black --check src/ tests/
	isort --check-only src/ tests/

# Pre-commit hooks
pre-commit: ## Run pre-commit hooks
	pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	pre-commit autoupdate

# Docker commands
docker-build: ## Build Docker image
	docker build -t jikai:latest .

docker-run: ## Run Docker container
	docker run -p 8000:8000 --env-file .env jikai:latest

docker-compose-up: ## Start all services with docker-compose
	docker-compose up -d

docker-compose-down: ## Stop all services
	docker-compose down

docker-compose-logs: ## View logs
	docker-compose logs -f

docker-compose-dev: ## Start development environment
	docker-compose -f docker-compose.dev.yml up -d

# Application commands
run: ## Run the application locally
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Run the application in production mode
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Database commands
db-migrate: ## Run database migrations
	alembic upgrade head

db-revision: ## Create new database revision
	alembic revision --autogenerate -m "$(message)"

# Health checks
health: ## Check application health
	curl -f http://localhost:8000/health || echo "Application not running"

health-llm: ## Check LLM service health
	curl -f http://localhost:8000/llm/health || echo "LLM service not available"

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

clean-docker: ## Clean up Docker resources
	docker system prune -f
	docker volume prune -f

# Security
security-scan: ## Run security scans
	bandit -r src/ -f json -o bandit-report.json
	safety check

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
	@echo "  2. Start Ollama: docker run -d -p 11434:11434 ollama/ollama"
	@echo "  3. Pull model: docker exec -it <container> ollama pull llama2:7b"
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
	docker-compose logs -f jikai-api

metrics: ## View application metrics
	@echo "Metrics available at:"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000"

# Backup and restore
backup: ## Backup application data
	@echo "Creating backup..."
	docker-compose exec chromadb tar -czf /tmp/chromadb-backup.tar.gz /chroma/chroma
	docker cp $$(docker-compose ps -q chromadb):/tmp/chromadb-backup.tar.gz ./backup-$$(date +%Y%m%d-%H%M%S).tar.gz

restore: ## Restore application data
	@echo "Restoring from backup..."
	@echo "Please specify backup file: make restore BACKUP_FILE=backup-YYYYMMDD-HHMMSS.tar.gz"
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Error: BACKUP_FILE not specified"; \
		exit 1; \
	fi
	docker cp $(BACKUP_FILE) $$(docker-compose ps -q chromadb):/tmp/restore.tar.gz
	docker-compose exec chromadb tar -xzf /tmp/restore.tar.gz -C /