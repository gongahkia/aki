"""Health and version endpoints."""

from fastapi import APIRouter

from ...config import settings

router = APIRouter()


@router.get("/health")
async def health():
    from ...services import corpus_service, database_service, llm_service
    db_ok = True
    try:
        await database_service.get_generation_count()
    except Exception:
        db_ok = False
    corpus_ok = True
    try:
        await corpus_service.health_check()
    except Exception:
        corpus_ok = False
    llm_health = {}
    try:
        llm_health = await llm_service.health_check()
    except Exception:
        pass
    status = "healthy" if db_ok and corpus_ok else "degraded"
    return {
        "status": status,
        "version": settings.app_version,
        "services": {
            "database": db_ok,
            "corpus": corpus_ok,
            "llm": llm_health,
        },
    }


@router.get("/version")
async def version():
    return {"version": settings.app_version, "name": settings.app_name}
