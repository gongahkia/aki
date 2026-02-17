"""
FastAPI application for Jikai legal hypothetical generation service.
Provides REST API endpoints for generating, validating, and managing legal hypotheticals.
"""

import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings
from ..services import (
    CorpusQuery,
    GenerationRequest,
    GenerationResponse,
    HypotheticalEntry,
    corpus_service,
    hypothetical_service,
    llm_service,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Jikai Legal Hypothetical Generator",
    description="AI-powered service for generating Singapore Tort Law hypotheticals for educational purposes",
    version=settings.app_version,
    docs_url="/docs" if settings.api.debug else None,
    redoc_url="/redoc" if settings.api.debug else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.api.debug else ["localhost", "127.0.0.1"],
)


# API Key authentication middleware
JIKAI_API_KEY = os.environ.get("JIKAI_API_KEY", "")
_EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate JIKAI_API_KEY header on every request (except exempt paths)."""

    async def dispatch(self, request: Request, call_next):
        if not JIKAI_API_KEY:
            # No key configured — skip auth
            return await call_next(request)
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        key = request.headers.get("X-API-Key", "")
        if key != JIKAI_API_KEY:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key. Set X-API-Key header."},
            )
        return await call_next(request)


# Token-bucket rate limiter middleware
class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter per client IP."""

    def __init__(self, app, rate_limit: int = 100, window: int = 60):
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window = window
        self._buckets: Dict[str, list] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        # Prune old timestamps
        self._buckets[client_ip] = [
            ts for ts in self._buckets[client_ip] if now - ts < self.window
        ]
        if len(self._buckets[client_ip]) >= self.rate_limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": f"Rate limit exceeded. Max {self.rate_limit} requests per {self.window}s."
                },
            )
        self._buckets[client_ip].append(now)
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)
app.add_middleware(
    RateLimiterMiddleware,
    rate_limit=settings.api.rate_limit,
    window=60,
)


# Request/Response Models
class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str
    services: Dict[str, Any]


class TopicsResponse(BaseModel):
    """Available topics response model."""

    topics: List[str]
    count: int


class GenerationStatsResponse(BaseModel):
    """Generation statistics response model."""

    total_generations: int
    average_generation_time: float
    success_rate: float
    recent_generations: List[Dict[str, Any]]


# Dependency functions
async def get_hypothetical_service():
    """Dependency to get hypothetical service instance."""
    return hypothetical_service


async def get_llm_service():
    """Dependency to get LLM service instance."""
    return llm_service


async def get_corpus_service():
    """Dependency to get corpus service instance."""
    return corpus_service


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(
        "Starting Jikai API",
        version=settings.app_version,
        environment=settings.environment,
    )

    # Initialize services
    try:
        # Health check all services
        health_status = await hypothetical_service.health_check()
        logger.info("Services initialized", health_status=health_status)
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down Jikai API")

    # Close service connections
    try:
        await llm_service.close()
        logger.info("Services closed successfully")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check all services
        hypothetical_health = await hypothetical_service.health_check()
        llm_health = await llm_service.health_check()
        corpus_health = await corpus_service.health_check()

        # Determine overall status
        overall_status = "healthy"
        if hypothetical_health.get("status") != "healthy":
            overall_status = "unhealthy"
        elif any(
            dep.get("status") == "unhealthy"
            for dep in hypothetical_health.get("dependencies", {}).values()
        ):
            overall_status = "degraded"

        return HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            version=settings.app_version,
            services={
                "hypothetical_service": hypothetical_health,
                "llm_service": llm_health,
                "corpus_service": corpus_health,
            },
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {e}",
        )


# Main generation endpoint
@app.post("/generate", response_model=GenerationResponse)
async def generate_hypothetical(
    request: GenerationRequest,
    background_tasks: BackgroundTasks,
    service: hypothetical_service = Depends(get_hypothetical_service),
):
    """Generate a legal hypothetical with analysis."""
    try:
        logger.info(
            "Hypothetical generation requested",
            topics=request.topics,
            parties=request.number_parties,
        )

        # Validate topics
        available_topics = await corpus_service.extract_all_topics()
        invalid_topics = [
            topic for topic in request.topics if topic not in available_topics
        ]

        if invalid_topics:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid topics: {invalid_topics}. Available topics: {available_topics[:10]}...",
            )

        # Generate hypothetical
        response = await service.generate_hypothetical(request)

        # Log generation in background
        background_tasks.add_task(log_generation_event, request.dict(), response.dict())

        logger.info(
            "Hypothetical generated successfully",
            generation_time=response.generation_time,
            validation_passed=response.validation_results.get("passed", False),
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Hypothetical generation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {e}",
        )


# Topics endpoint
@app.get("/topics", response_model=TopicsResponse)
async def get_available_topics(service: corpus_service = Depends(get_corpus_service)):
    """Get all available legal topics from the corpus."""
    try:
        topics = await service.extract_all_topics()

        return TopicsResponse(topics=topics, count=len(topics))

    except Exception as e:
        logger.error("Failed to get topics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get topics: {e}",
        )


# Corpus management endpoints
@app.get("/corpus/entries")
async def get_corpus_entries(
    topics: Optional[List[str]] = None,
    limit: int = Field(default=10, ge=1, le=100),
    service: corpus_service = Depends(get_corpus_service),
):
    """Get corpus entries with optional topic filtering."""
    try:
        if topics:
            query = CorpusQuery(topics=topics, sample_size=limit)
            entries = await service.query_relevant_hypotheticals(query)
        else:
            # Get all entries (limited)
            all_entries = await service.load_corpus()
            entries = all_entries[:limit]

        return {"entries": [entry.dict() for entry in entries], "count": len(entries)}

    except Exception as e:
        logger.error("Failed to get corpus entries", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get corpus entries: {e}",
        )


@app.post("/corpus/entries")
async def add_corpus_entry(
    entry: HypotheticalEntry, service: corpus_service = Depends(get_corpus_service)
):
    """Add a new entry to the corpus."""
    try:
        entry_id = await service.add_hypothetical(entry)

        logger.info("Corpus entry added", id=entry_id, topics=entry.topics)

        return {"id": entry_id, "message": "Entry added successfully"}

    except Exception as e:
        logger.error("Failed to add corpus entry", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add entry: {e}",
        )


# LLM service endpoints
@app.get("/llm/models")
async def get_available_models(service: llm_service = Depends(get_llm_service)):
    """Get available LLM models."""
    try:
        models = await service.list_models()
        return {"models": models}

    except Exception as e:
        logger.error("Failed to get models", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get models: {e}",
        )


@app.get("/llm/health")
async def llm_health_check(service: llm_service = Depends(get_llm_service)):
    """Check LLM service health."""
    try:
        health_status = await service.health_check()
        return {"health": health_status}

    except Exception as e:
        logger.error("LLM health check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM health check failed: {e}",
        )


# Statistics endpoint
@app.get("/stats", response_model=GenerationStatsResponse)
async def get_generation_stats(
    service: hypothetical_service = Depends(get_hypothetical_service),
):
    """Get generation statistics from database."""
    try:
        # Get statistics from database (persistent across restarts)
        from src.services.database_service import database_service

        db_stats = await database_service.get_statistics()

        # Get recent generations
        recent = await service.get_generation_history(limit=10)

        return GenerationStatsResponse(
            total_generations=db_stats["total_generations"],
            average_generation_time=db_stats["average_generation_time"],
            success_rate=db_stats["success_rate"],
            recent_generations=recent,
        )

    except Exception as e:
        logger.error("Failed to get statistics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {e}",
        )


# ML endpoints
@app.post("/ml/train")
async def train_ml_models(
    data_path: Optional[str] = None,
    n_clusters: int = 5,
):
    """Trigger ML model training."""
    try:
        from ..ml.pipeline import MLPipeline

        pipeline = MLPipeline()
        import asyncio

        path = data_path or settings.ml.training_data_path
        metrics = await asyncio.to_thread(
            pipeline.train_all, path, n_clusters=n_clusters
        )
        return {"status": "trained", "metrics": metrics}
    except Exception as e:
        logger.error("ML training failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Training failed: {e}")


@app.get("/ml/status")
async def ml_status():
    """Get ML model status and metrics."""
    try:
        from ..ml.pipeline import MLPipeline

        pipeline = MLPipeline()
        pipeline.load_all()
        return pipeline.get_status()
    except Exception as e:
        return {
            "classifier_trained": False,
            "regressor_trained": False,
            "clusterer_trained": False,
            "error": str(e),
        }


@app.get("/providers")
async def list_providers():
    """List all providers and their models."""
    try:
        models = await llm_service.list_models()
        health = await llm_service.health_check()
        return {
            "providers": {
                name: {"models": m, "health": health.get(name, {})}
                for name, m in models.items()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SetDefaultProviderRequest(BaseModel):
    provider: str
    model: Optional[str] = None


@app.put("/providers/default")
async def set_default_provider(req: SetDefaultProviderRequest):
    """Set default LLM provider and model."""
    try:
        llm_service.select_provider(req.provider)
        if req.model:
            llm_service.select_model(req.model)
        return {"default_provider": req.provider, "default_model": req.model}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# Background task functions
async def log_generation_event(
    request_data: Dict[str, Any], response_data: Dict[str, Any]
):
    """Log generation event for analytics."""
    try:
        # This could be extended to log to a database or analytics service
        logger.info(
            "Generation event logged",
            topics=request_data.get("topics"),
            generation_time=response_data.get("generation_time"),
            validation_passed=response_data.get("validation_results", {}).get("passed"),
        )
    except Exception as e:
        logger.error("Failed to log generation event", error=str(e))


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Jikai Legal Hypothetical Generator",
        "version": settings.app_version,
        "description": "AI-powered service for generating Singapore Tort Law hypotheticals",
        "docs_url": (
            "/docs"
            if settings.api.debug
            else "Documentation not available in production"
        ),
        "health_url": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
        log_level=settings.logging.level.lower(),
    )
