"""FastAPI application factory."""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import settings

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Jikai API",
        version=settings.app_version,
        docs_url="/docs" if settings.api.debug else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from .routes import corpus, database, health, jobs, llm, validation, workflow
    app.include_router(health.router)
    app.include_router(llm.router, prefix="/llm", tags=["llm"])
    app.include_router(corpus.router, prefix="/corpus", tags=["corpus"])
    app.include_router(workflow.router, prefix="/workflow", tags=["workflow"])
    app.include_router(database.router, prefix="/db", tags=["database"])
    app.include_router(validation.router, prefix="/validation", tags=["validation"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    return app

app = create_app()
